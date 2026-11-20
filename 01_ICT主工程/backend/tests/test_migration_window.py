# -*- coding: utf-8 -*-
"""旧库在线迁移窗口：状态机、冻结、切换与回滚。"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.storage import reset_backend_cache
from app.storage.migration_window import (
    MIGRATION_WINDOW,
    MigrationVerifyError,
    MigrationWindowError,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


def _runtime_tmp() -> Path:
    """venv python 写不了 ICT 子树，临时目录固定用 D:/工作区/_runtime。"""
    root = Path(os.environ.get("ICT_RUNTIME_DIR") or "D:/工作区/_runtime")
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="migwin-", dir=str(root)))


class MigrationWindowTestBase(unittest.TestCase):
    """公共脚手架：临时数据目录 + 干净的窗口单例。"""

    def setUp(self):
        self.tmp = _runtime_tmp()
        self.users = self.tmp / "users" / "demo"
        self.users.mkdir(parents=True)
        (self.users / "student.json").write_text(
            json.dumps(
                {
                    "id": "demo",
                    "major": "软件工程",
                    "grade": "大三",
                    "created_at": "2026-11-01T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        (self.users / "events.json").write_text(
            json.dumps(
                [
                    {
                        "id": "evt-1",
                        "student_id": "demo",
                        "event_type": "login",
                        "payload": {"source": "test"},
                        "created_at": "2026-11-01T01:00:00+00:00",
                    }
                ]
            ),
            encoding="utf-8",
        )

        self._old_env = {
            key: os.environ.get(key)
            for key in ("DATA_DIR", "STORAGE_BACKEND", "MIGRATION_WINDOW_TTL_SEC")
        }
        os.environ["DATA_DIR"] = str(self.tmp)
        os.environ["STORAGE_BACKEND"] = "json"
        os.environ["MIGRATION_WINDOW_TTL_SEC"] = "300"

        self._old_data_dir = settings.data_dir
        self._old_backend = settings.storage_backend
        settings.data_dir = str(self.tmp)
        settings.storage_backend = "json"

        reset_backend_cache()
        MIGRATION_WINDOW.reset()

    def tearDown(self):
        MIGRATION_WINDOW.reset()
        settings.data_dir = self._old_data_dir
        settings.storage_backend = self._old_backend
        reset_backend_cache()
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)


class WindowStateMachineTest(MigrationWindowTestBase):
    def test_prepare_freezes_and_commit_switches_backend(self):
        status = MIGRATION_WINDOW.prepare()
        self.assertEqual(status["phase"], "prepared")
        self.assertTrue(status["frozen"])
        self.assertEqual(settings.storage_backend, "json")

        status = MIGRATION_WINDOW.commit()
        self.assertEqual(status["phase"], "committed")
        self.assertEqual(status["backend"], "sqlite")
        self.assertFalse(status["frozen"])
        self.assertEqual(settings.storage_backend, "sqlite")
        self.assertEqual(status["errors"], [])

        from app.storage import backend_name

        self.assertEqual(backend_name(), "sqlite")

        import sqlite3

        conn = sqlite3.connect(self.tmp / "app.db")
        try:
            (event_count,) = conn.execute(
                "SELECT COUNT(*) FROM learning_event WHERE student_id = 'demo'"
            ).fetchone()
            (student_count,) = conn.execute(
                "SELECT COUNT(*) FROM student WHERE id = 'demo'"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(event_count, 1)
        self.assertEqual(student_count, 1)

    def test_prepare_twice_rejected(self):
        MIGRATION_WINDOW.prepare()
        with self.assertRaises(MigrationWindowError):
            MIGRATION_WINDOW.prepare()
        MIGRATION_WINDOW.abort()

    def test_commit_without_prepare_rejected(self):
        with self.assertRaises(MigrationWindowError):
            MIGRATION_WINDOW.commit()

    def test_abort_unfreezes_and_stays_json(self):
        MIGRATION_WINDOW.prepare()
        status = MIGRATION_WINDOW.abort()
        self.assertEqual(status["phase"], "idle")
        self.assertFalse(status["frozen"])
        self.assertEqual(settings.storage_backend, "json")
        self.assertFalse((self.tmp / "app.db").exists())

    def test_abort_after_commit_rejected_with_guidance(self):
        MIGRATION_WINDOW.prepare()
        MIGRATION_WINDOW.commit()
        with self.assertRaises(MigrationWindowError) as ctx:
            MIGRATION_WINDOW.abort()
        self.assertIn("人工", str(ctx.exception))

    def test_prepare_rejected_when_already_sqlite(self):
        MIGRATION_WINDOW.prepare()
        MIGRATION_WINDOW.commit()
        with self.assertRaises(MigrationWindowError):
            MIGRATION_WINDOW.prepare()

    def test_write_guard_blocks_during_window(self):
        MIGRATION_WINDOW.prepare()
        from app import repo

        release = threading.Event()

        def _writer():
            repo.insert_learning_event("demo", "blocked-test", {})

        def _unfreeze():
            time.sleep(0.3)
            MIGRATION_WINDOW.abort()
            release.set()

        thread = threading.Thread(target=_writer, daemon=True)
        watcher = threading.Thread(target=_unfreeze, daemon=True)
        thread.start()
        watcher.start()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive(), "写线程应在窗口关闭后完成")
        self.assertTrue(release.is_set())

        # abort 已解冻：事件没有写进 JSON（写线程在冻结期间被挡住，
        # 解冻后写入，但那时窗口已 abort——注意 json 后端仍生效，事件应已落盘）。
        events = json.loads((self.users / "events.json").read_text(encoding="utf-8"))
        self.assertEqual(len(events), 2)

    def test_commit_verify_failure_keeps_json_backend(self):
        MIGRATION_WINDOW.prepare()
        # 在迁移源里塞一条缺 id 的脏数据：migrate 会记 problem -> verify 不通过口径
        (self.users / "usage.json").write_text(
            json.dumps([{"id": None, "resource_id": "r1"}]), encoding="utf-8"
        )
        with self.assertRaises(MigrationVerifyError):
            MIGRATION_WINDOW.commit()
        # 状态已回 idle、解冻、后端仍是 json
        status = MIGRATION_WINDOW.status_snapshot()
        self.assertEqual(status["phase"], "idle")
        self.assertFalse(status["frozen"])
        self.assertEqual(settings.storage_backend, "json")

    def test_ttl_watchdog_auto_aborts(self):
        with patch.dict(os.environ, {"MIGRATION_WINDOW_TTL_SEC": "1"}):
            status = MIGRATION_WINDOW.prepare()
            self.assertEqual(status["ttl_sec"], 1)
            time.sleep(2.5)
            status = MIGRATION_WINDOW.status_snapshot()
        self.assertEqual(status["phase"], "idle")
        self.assertFalse(status["frozen"])
        self.assertIn("窗口超时", "".join(status["errors"]))


class StorageRouterTest(MigrationWindowTestBase):
    def _client(self) -> TestClient:
        from app.api.app_router import api_router

        app = FastAPI()
        app.include_router(api_router)
        return TestClient(app)

    def test_status_endpoint_reports_idle(self):
        with self._client() as client:
            resp = client.get("/api/storage/migration-window")
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertTrue(body["success"])
            self.assertEqual(body["data"]["phase"], "idle")
            self.assertEqual(body["data"]["current_backend"], "json")

    def test_full_flow_via_http(self):
        with self._client() as client:
            resp = client.post("/api/storage/migrate", json={"action": "prepare"})
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.json()["success"])
            self.assertTrue(resp.json()["data"]["frozen"])

            # 冻结期间 GET status 仍可用（读不冻结）
            resp = client.get("/api/storage/migration-window")
            self.assertEqual(resp.status_code, 200)

            resp = client.post("/api/storage/migrate", json={"action": "commit"})
            self.assertEqual(resp.status_code, 200)
            data = resp.json()["data"]
            self.assertEqual(data["phase"], "committed")
            self.assertEqual(data["current_backend"], "sqlite")

            # commit 后写请求直接进 sqlite（不再冻结）
            resp = client.post(
                "/api/knowledge/track",
                json={"student_id": "demo", "node_id": "node-1", "score": 90},
            )
            self.assertEqual(resp.status_code, 200)

    def test_unknown_action_rejected(self):
        with self._client() as client:
            resp = client.post("/api/storage/migrate", json={"action": "explode"})
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertFalse(body["success"])
            self.assertEqual(body["error"]["code"], "MIGRATION_UNKNOWN_ACTION")


class FrozenAsyncWriteTest(MigrationWindowTestBase):
    """冻结窗口期，async 端点的写请求必须返回 503 + Retry-After。

    历史踩坑（2026-11-20）：async 端点在事件循环线程上同步等锁会卡死整个
    事件循环，commit 请求永远进不来；write_guard 对事件循环上下文改为抛
    MigrationFrozenError，由 main.py 的异常处理器转成 503。
    """

    def _client(self) -> TestClient:
        from app.main import create_app

        app = create_app()
        return TestClient(app)

    def test_async_write_gets_503_then_succeeds_after_abort(self):
        # 不用 with 上下文：BaseException 穿透路由兜底后会被中间件转成 503 响应，
        # 但 TestClient 的 lifespan portal 在退出阶段对 BaseException 敏感，
        # 直接裸用 + addCleanup 关闭更稳。
        client = self._client()
        self.addCleanup(client.close)
        MIGRATION_WINDOW.prepare()

        resp = client.post(
            "/api/knowledge/track",
            json={"student_id": "demo", "node_id": "frozen-1", "score": 80},
        )
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.headers.get("Retry-After"), "5")
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "MIGRATION_FROZEN")

        # 冻结期读请求不受影响
        resp = client.get("/api/storage/migration-window")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["data"]["frozen"])

        MIGRATION_WINDOW.abort()

        resp = client.post(
            "/api/knowledge/track",
            json={"student_id": "demo", "node_id": "frozen-1", "score": 80},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])


if __name__ == "__main__":
    unittest.main()
