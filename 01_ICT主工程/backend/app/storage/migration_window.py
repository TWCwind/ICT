from __future__ import annotations

"""旧库在线迁移窗口（JSON -> SQLite）。

在同一个后端进程内完成「冻结写入 -> 迁移 -> 核对 -> 切换」，全程不停服务：

    POST /api/storage/migrate {"action": "prepare"}  冻结写请求，开启窗口
    POST /api/storage/migrate {"action": "commit"}   迁移 + 核对 + 切换到 sqlite
    POST /api/storage/migrate {"action": "abort"}    解冻，继续用 json 后端

行为口径：
- 冻结期间读请求不受影响。写请求分两条路：
  * 同步上下文（线程池端点 / MCP / 脚本）：阻塞排队，窗口关闭后继续执行；
  * 事件循环上下文（async 端点）：直接抛 MigrationFrozenError（HTTP 503 +
    Retry-After），由客户端重试——同步等锁会卡死整个事件循环，使 commit
    永远进不来（2026-11-20 实测踩坑）。
- 迁移复用 scripts/migrate/json_to_sqlite.py 的 migrate/verify，行为与离线脚本
  完全一致（created_at 缺失用文件 mtime、quiz_attempt.detail_json 保整条记录、
  跨目录重复 id 只留首次出现）。
- commit 前强制核对：JSON 与 SQLite 条数逐学号一致才切换后端；不一致则保持
  json 后端并解冻，差异记录在 status.errors 里，可直接重试。
- 窗口有 TTL（默认 300 秒，环境变量 MIGRATION_WINDOW_TTL_SEC），超时自动 abort，
  防止忘记 commit 导致写请求无限排队。
- 切换成功后 JSON 文件原样保留（冻结期间没有写入落到 JSON），可作为回退快照；
  切换后的新写入只进 SQLite。切换后再想回退属于人工决策，abort 会明确拒绝并
  给出说明，避免静默丢新数据。
"""

import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import settings

# 迁移口径实现位于仓库 scripts/ 目录（backend 之外），这里把它挂进 sys.path。
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.migrate.json_to_sqlite import migrate as _run_migration  # noqa: E402
from scripts.migrate.json_to_sqlite import verify as _run_verify  # noqa: E402


class MigrationWindowError(Exception):
    """状态机拒绝（重复开启、非法 abort 等）。"""

    code = "MIGRATION_STATE_ERROR"


class MigrationVerifyError(MigrationWindowError):
    """迁移后的核对未通过，已保持原后端并解冻。"""

    code = "MIGRATION_VERIFY_FAILED"


class MigrationFrozenError(BaseException):
    """迁移窗口冻结期间，事件循环线程的写请求被拒（客户端应稍后重试）。

    HTTP 层映射为 503 + Retry-After；同步上下文不抛这个错，走阻塞排队。
    """

    code = "MIGRATION_FROZEN"


def _in_event_loop() -> bool:
    """当前线程是否正在跑 asyncio 事件循环（async 端点 = True）。"""
    try:
        import asyncio

        return asyncio.get_running_loop() is not None
    except RuntimeError:
        return False


def _window_ttl_sec() -> int:
    raw = os.environ.get("MIGRATION_WINDOW_TTL_SEC") or "300"
    try:
        return max(1, int(raw))
    except ValueError:
        return 300


@dataclass
class WindowStatus:
    phase: str = "idle"  # idle / prepared / migrating / committed
    backend: str = "json"
    frozen: bool = False
    opened_at: float | None = None
    committed_at: float | None = None
    ttl_sec: int = 300
    last_action: str = ""
    migrate_result: dict[str, Any] | None = None
    verify_result: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "backend": self.backend,
            "frozen": self.frozen,
            "opened_at": self.opened_at,
            "committed_at": self.committed_at,
            "ttl_sec": self.ttl_sec,
            "last_action": self.last_action,
            "migrate_result": self.migrate_result,
            "verify_result": self.verify_result,
            "errors": list(self.errors),
        }


class MigrationWindow:
    """进程内迁移窗口，模块底部提供单例 MIGRATION_WINDOW。"""

    def __init__(self) -> None:
        self._freeze = threading.Lock()  # 写冻结：窗口期间所有仓储写阻塞在这
        self._state = threading.Lock()
        self._status = WindowStatus()
        self._watchdog: threading.Thread | None = None

    # ---------- 状态 ----------

    def status_snapshot(self) -> dict[str, Any]:
        with self._state:
            return self._status.snapshot()

    # ---------- 写路径入口（app.repo 的每个写方法都调用） ----------

    def write_guard(self) -> None:
        """窗口期间阻塞调用线程；窗口关闭后放行。

        空闲时是一次无竞争的锁获取，开销可忽略。注意不能改成 RLock：
        prepare 和 commit 可能来自不同线程，必须用无主锁。

        事件循环线程例外：async 端点里同步等锁会卡死整个事件循环，
        commit 请求就永远进不来（2026-11-20 实测）。所以事件循环上下文
        在冻结时抛 MigrationFrozenError，由 HTTP 层转 503 + Retry-After。
        """
        if self._freeze.locked():
            # 快速路径之外才区分上下文：冻结中 + 事件循环 → 拒绝并让客户端重试。
            if _in_event_loop():
                raise MigrationFrozenError(
                    "存储迁移窗口开启中，写请求暂时被拒，请稍后重试"
                )
        with self._freeze:
            pass

    # ---------- 三个动作 ----------

    def prepare(self) -> dict[str, Any]:
        with self._state:
            if self._status.phase in ("prepared", "migrating"):
                raise MigrationWindowError("迁移窗口已开启，请先 commit 或 abort")
            if self._status.phase == "committed":
                raise MigrationWindowError("已切换到 sqlite 后端，无需再次迁移")
            if str(settings.storage_backend).strip().lower() == "sqlite":
                raise MigrationWindowError("当前已是 sqlite 后端，无需迁移")

        acquired = self._freeze.acquire(timeout=30)
        if not acquired:
            raise MigrationWindowError("等待在途写入完成超时，请重试 prepare")
        try:
            with self._state:
                if self._status.phase != "idle":
                    raise MigrationWindowError("迁移窗口已被其他请求开启")
                self._status = WindowStatus(
                    phase="prepared",
                    backend="json",
                    frozen=True,
                    opened_at=time.time(),
                    ttl_sec=_window_ttl_sec(),
                )
            self._start_watchdog()
            return self.status_snapshot()
        except BaseException:
            self._freeze.release()
            raise

    def commit(self) -> dict[str, Any]:
        with self._state:
            if self._status.phase != "prepared":
                raise MigrationWindowError(
                    "迁移窗口未开启（当前阶段 %s），请先 prepare" % self._status.phase
                )
            self._status.phase = "migrating"

        switched = False
        try:
            try:
                migrate_result = _run_migration(
                    settings.data_path, settings.db_path, dry_run=False, force=False
                )
                verify_result = _run_verify(settings.data_path, settings.db_path)
            except SystemExit as exc:  # verify 对缺库等情况直接 SystemExit
                raise MigrationWindowError("迁移失败：%s" % exc) from exc

            problems = list(migrate_result.get("problems") or [])
            problems += list(verify_result.get("problems") or [])

            with self._state:
                self._status.migrate_result = migrate_result
                self._status.verify_result = verify_result
                self._status.errors = problems

            if problems:
                raise MigrationVerifyError(
                    "迁移核对未通过（%d 处差异），已保持 json 后端并解冻；差异见 status.errors"
                    % len(problems)
                )

            settings.storage_backend = "sqlite"
            switched = True
            from app.storage import reset_backend_cache

            reset_backend_cache()

            with self._state:
                self._status.phase = "committed"
                self._status.backend = "sqlite"
                self._status.frozen = False
                self._status.committed_at = time.time()
                self._status.last_action = "commit"
            self._freeze.release()
            return self.status_snapshot()
        except BaseException:
            if switched:
                # 切换动作本身抛了异常：退回 json，保持与磁盘数据一致
                settings.storage_backend = "json"
                try:
                    from app.storage import reset_backend_cache

                    reset_backend_cache()
                except Exception:
                    pass
            with self._state:
                if self._status.phase == "migrating":
                    self._status.phase = "idle"
                    self._status.frozen = False
                    self._status.last_action = "commit-failed"
            try:
                self._freeze.release()
            except RuntimeError:
                pass
            raise

    def abort(self) -> dict[str, Any]:
        with self._state:
            if self._status.phase == "idle":
                raise MigrationWindowError("迁移窗口未开启")
            if self._status.phase == "migrating":
                raise MigrationWindowError("迁移正在进行，无法 abort")
            if self._status.phase == "committed":
                raise MigrationWindowError(
                    "已提交切换；JSON 文件保留为迁移前快照，切换后的新写入仅在 SQLite。"
                    "如需回退请将 STORAGE_BACKEND 设回 json 并重启服务后人工评估。"
                )
            self._status.phase = "idle"
            self._status.frozen = False
            self._status.last_action = "abort"
        try:
            self._freeze.release()
        except RuntimeError:
            pass
        return self.status_snapshot()

    # ---------- 测试 / 故障恢复辅助 ----------

    def reset(self) -> None:
        """强制回到初始状态（只用于测试与故障恢复，正常流程走 abort）。"""
        try:
            self._freeze.release()
        except RuntimeError:
            pass
        with self._state:
            self._status = WindowStatus()

    # ---------- 内部 ----------

    def _start_watchdog(self) -> None:
        ttl = self._status.ttl_sec

        def _watch() -> None:
            deadline = time.time() + ttl
            while time.time() < deadline:
                with self._state:
                    if self._status.phase != "prepared":
                        return
                time.sleep(0.2)
            with self._state:
                if self._status.phase != "prepared":
                    return
                self._status.errors.append("窗口超时（TTL %d 秒），自动 abort" % ttl)
            try:
                self.abort()
            except MigrationWindowError:
                pass

        self._watchdog = threading.Thread(
            target=_watch, daemon=True, name="migration-window-ttl"
        )
        self._watchdog.start()


MIGRATION_WINDOW = MigrationWindow()
