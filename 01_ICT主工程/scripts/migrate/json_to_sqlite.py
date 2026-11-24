#!/usr/bin/env python
"""JSON 文件存储 -> SQLite 回填迁移（阶段 2）。

读 data/users/<学号>/*.json，写入 data/app.db 的对应表；只搬元数据，不动磁盘正文文件。

用法：
    # 1) 先看会写多少行、跳过多少脏数据（不落库）
    python scripts/migrate/json_to_sqlite.py --data-dir D:/工作区/_runtime/ict-data-copy --dry-run
    # 2) 真正回填（幂等：已存在的行跳过）
    python scripts/migrate/json_to_sqlite.py --data-dir D:/工作区/_runtime/ict-data-copy
    # 3) 只做条数核对（JSON 条数 == 表行数）
    python scripts/migrate/json_to_sqlite.py --data-dir D:/工作区/_runtime/ict-data-copy --verify-only

默认数据目录解析顺序：--data-dir > ICT_DATA_DIR/DATA_DIR > <repo>/../_runtime/ict-data > <repo>/data
默认数据库：<data-dir>/app.db，可用 --db 覆盖。

注意：本脚本用 venv python 运行（D:/工作区/_venv-be/Scripts/python.exe），
因为要 import app.db.sqlite 复用 DDL；PATH 上的 MSYS python 没有 pydantic/dotenv。
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.sqlite import DDL, _QUIZ_EXTRA_COLUMNS, _STUDENT_EXTRA_COLUMNS, _ensure_columns  # noqa: E402

PROFILE_COLUMNS = (
    "knowledge_base_level",
    "cognitive_style",
    "mistake_patterns",
    "modality_preference",
    "pace_preference",
    "motivation_style",
)

# 源文件 -> 目标表（数组型 JSON）
ARRAY_FILES = (
    ("profiles.json", "profile_snapshot"),
    ("resources.json", "resource_item"),
    ("exercise_records.json", "quiz_attempt"),
    ("events.json", "learning_event"),
    ("usage.json", "resource_usage"),
)

BAK_SUFFIX = ".bak"


def dump(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def mtime_iso(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return now_iso()


def resolve_data_dir(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    for key in ("ICT_DATA_DIR", "DATA_DIR"):
        value = os.environ.get(key)
        if value:
            candidates.append(Path(value))
    candidates.append(PROJECT_DIR.parent / "_runtime" / "ict-data")
    candidates.append(PROJECT_DIR.parents[1] / "_runtime" / "ict-data")
    candidates.append(PROJECT_DIR / "data")
    for candidate in candidates:
        if candidate and candidate.is_dir():
            return candidate.resolve()
    raise SystemExit("找不到数据目录，请用 --data-dir 指定")


def read_json(path: Path, default: Any, problems: list[str]) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        problems.append("%s 解析失败：%s" % (path, exc))
        return default


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=OFF;")
    for sql in DDL:
        conn.executescript(sql)
    _ensure_columns(conn, "student", _STUDENT_EXTRA_COLUMNS)
    _ensure_columns(conn, "quiz_attempt", _QUIZ_EXTRA_COLUMNS)
    conn.commit()


# ---------------- 行构造：JSON 记录 -> 表列 ----------------

def student_row(student_id: str, data: dict[str, Any], created_at: str, updated_at: str) -> dict[str, Any]:
    return {
        "id": student_id,
        "name": str(data.get("name") or ""),
        "major": data.get("major"),
        "grade": data.get("grade"),
        "current_course": data.get("current_course"),
        "goals": data.get("goals"),
        "created_at": data.get("created_at") or created_at,
        "updated_at": data.get("updated_at") or updated_at,
    }


def profile_row(student_id: str, item: dict[str, Any]) -> dict[str, Any]:
    row = {"id": item.get("id"), "student_id": student_id}
    for column in PROFILE_COLUMNS:
        row[column] = item.get(column)
    row["evidence_json"] = dump(item.get("evidence"))
    row["created_at"] = item.get("created_at") or now_iso()
    return row


def resource_row(student_id: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "student_id": student_id,
        "type": item.get("type"),
        "title": item.get("title"),
        "tags_json": dump(item.get("tags")),
        "content_uri": item.get("content_uri"),
        "meta_json": dump(item.get("meta")),
        "created_at": item.get("created_at") or now_iso(),
    }


def quiz_row(student_id: str, item: dict[str, Any], fallback_created_at: str) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "student_id": student_id,
        "resource_id": item.get("resource_id"),
        "score": item.get("score"),
        "weak_points_json": dump(item.get("weak_points") or item.get("tags")),
        "created_at": item.get("created_at") or fallback_created_at,
        "question_id": item.get("question_id"),
        "is_correct": None if item.get("correct") is None else int(bool(item.get("correct"))),
        "tags_json": dump(item.get("tags")),
        "course": item.get("course"),
        "major": item.get("major"),
        "chapter": item.get("chapter"),
        "detail_json": dump(item),
    }


def event_row(student_id: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "student_id": student_id,
        "event_type": item.get("event_type") or "unknown",
        "payload_json": dump(item.get("payload")),
        "created_at": item.get("created_at") or now_iso(),
    }


def usage_row(student_id: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "resource_id": item.get("resource_id") or "",
        "student_id": student_id,
        "action": item.get("action") or "unknown",
        "duration_sec": item.get("duration_sec"),
        "feedback_json": dump(item.get("feedback")),
        "created_at": item.get("created_at") or now_iso(),
    }


BUILDERS = {
    "profile_snapshot": lambda sid, item, mt: profile_row(sid, item),
    "resource_item": lambda sid, item, mt: resource_row(sid, item),
    "quiz_attempt": lambda sid, item, mt: quiz_row(sid, item, mt),
    "learning_event": lambda sid, item, mt: event_row(sid, item),
    "resource_usage": lambda sid, item, mt: usage_row(sid, item),
}


def insert_rows(conn: sqlite3.Connection, table: str, rows: list[dict[str, Any]], force: bool, dry_run: bool) -> int:
    if not rows:
        return 0
    if dry_run:
        return len(rows)
    columns = list(rows[0].keys())
    verb = "INSERT OR REPLACE" if force else "INSERT OR IGNORE"
    sql = "%s INTO %s (%s) VALUES (%s)" % (
        verb,
        table,
        ", ".join(columns),
        ", ".join("?" for _ in columns),
    )
    before = conn.total_changes
    conn.executemany(sql, [tuple(row.get(column) for column in columns) for row in rows])
    return conn.total_changes - before


def insert_single(conn: sqlite3.Connection, table: str, row: dict[str, Any], force: bool, dry_run: bool) -> int:
    if dry_run:
        return 1
    columns = list(row.keys())
    verb = "INSERT OR REPLACE" if force else "INSERT OR IGNORE"
    sql = "%s INTO %s (%s) VALUES (%s)" % (
        verb,
        table,
        ", ".join(columns),
        ", ".join("?" for _ in columns),
    )
    before = conn.total_changes
    conn.execute(sql, tuple(row.get(column) for column in columns))
    return conn.total_changes - before


def user_dirs(user_root: Path) -> list[Path]:
    if not user_root.is_dir():
        return []
    return sorted(path for path in user_root.iterdir() if path.is_dir())


def migrate(data_dir: Path, db_path: Path, dry_run: bool, force: bool) -> dict[str, Any]:
    problems: list[str] = []
    user_root = data_dir / "users"
    stats: dict[str, dict[str, int]] = {}
    synthesized: list[str] = []

    def bump(table: str, expected: int, written: int) -> None:
        entry = stats.setdefault(table, {"json": 0, "written": 0})
        entry["json"] += expected
        entry["written"] += written

    dirs = user_dirs(user_root)
    if not dry_run:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)

        for student_dir in dirs:
            student_id = student_dir.name
            student_json = read_json(student_dir / "student.json", None, problems)
            if isinstance(student_json, dict) and student_json:
                row = student_row(
                    student_id,
                    student_json,
                    mtime_iso(student_dir / "student.json"),
                    now_iso(),
                )
                bump("student", 1, insert_single(conn, "student", row, force, dry_run))
                student_known = True
            else:
                student_known = False

            for filename, table in ARRAY_FILES:
                path = student_dir / filename
                items = read_json(path, [], problems)
                if not isinstance(items, list):
                    problems.append("%s 不是数组，已跳过" % path)
                    continue
                fallback = mtime_iso(path)
                rows: list[dict[str, Any]] = []
                skipped = 0
                for item in items:
                    if not isinstance(item, dict) or not item.get("id"):
                        skipped += 1
                        continue
                    sid = str(item.get("student_id") or student_id)
                    rows.append(BUILDERS[table](sid, item, fallback))
                if skipped:
                    problems.append("%s 有 %d 条缺 id，已跳过" % (path, skipped))
                if rows and not student_known:
                    student_ids = {row["student_id"] for row in rows}
                    for sid in sorted(student_ids):
                        if sid not in synthesized and not _student_exists(conn, sid):
                            stub = {
                                "id": sid,
                                "name": "",
                                "major": None,
                                "grade": None,
                                "current_course": None,
                                "goals": None,
                                "created_at": now_iso(),
                                "updated_at": None,
                            }
                            insert_single(conn, "student", stub, force, dry_run)
                            synthesized.append(sid)
                    student_known = True
                bump(table, len(rows), insert_rows(conn, table, rows, force, dry_run))

            progress = read_json(student_dir / "path_progress.json", {}, problems)
            if isinstance(progress, dict) and progress:
                row = {
                    "student_id": student_id,
                    "version": progress.get("version"),
                    "plan_key": progress.get("plan_key"),
                    "pass_threshold": progress.get("pass_threshold"),
                    "current_stage_id": progress.get("current_stage_id"),
                    "state_json": dump(progress),
                    "updated_at": progress.get("updated_at"),
                }
                bump("path_progress_state", 1, insert_single(conn, "path_progress_state", row, force, dry_run))

            knowledge = read_json(student_dir / "knowledge_state.json", {}, problems)
            if isinstance(knowledge, dict) and knowledge:
                row = {
                    "student_id": student_id,
                    "nodes_json": dump(knowledge.get("nodes") or {}),
                    "updated_at": now_iso(),
                }
                bump("knowledge_state", 1, insert_single(conn, "knowledge_state", row, force, dry_run))

        if not dry_run:
            conn.commit()

        return {
            "data_dir": str(data_dir),
            "db": str(db_path),
            "dry_run": dry_run,
            "force": force,
            "students": len(dirs),
            "stats": stats,
            "synthesized_students": synthesized,
            "problems": problems,
        }
    finally:
        conn.close()


def _student_exists(conn: sqlite3.Connection, student_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM student WHERE id = ?", (student_id,)).fetchone()
    return row is not None


TABLE_SCOPE_COLUMN = {
    "profile_snapshot": "student_id",
    "resource_item": "student_id",
    "quiz_attempt": "student_id",
    "learning_event": "student_id",
    "resource_usage": "student_id",
    "student": "id",
    "path_progress_state": "student_id",
    "knowledge_state": "student_id",
}

SINGLE_OBJECT_FILES = (
    ("student.json", "student"),
    ("path_progress.json", "path_progress_state"),
    ("knowledge_state.json", "knowledge_state"),
)


def collect_expected(user_root: Path, problems: list[str]) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    """统计每张表按 student_id 分组应有多少行。

    注意：跨学号目录可能出现同一 id 的记录（例如 layout-demo 复制了 demo 的
    roadshow-* 种子数据）。表主键是 id，所以这些重复只能落一行；这里按
    "首次出现归属" 计数，与 INSERT OR IGNORE 的顺序一致，并把重复数单独报出来。
    """
    expected: dict[str, dict[str, int]] = {}
    duplicates: dict[str, int] = {}
    seen: dict[str, set[str]] = {}

    for student_dir in user_dirs(user_root):
        for filename, table in ARRAY_FILES:
            items = read_json(student_dir / filename, [], problems)
            if not isinstance(items, list):
                continue
            bucket = seen.setdefault(table, set())
            counts = expected.setdefault(table, {})
            for item in items:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                key = str(item["id"])
                if key in bucket:
                    duplicates[table] = duplicates.get(table, 0) + 1
                    continue
                bucket.add(key)
                student_id = str(item.get("student_id") or student_dir.name)
                counts[student_id] = counts.get(student_id, 0) + 1

    for filename, table in SINGLE_OBJECT_FILES:
        counts = expected.setdefault(table, {})
        for student_dir in user_dirs(user_root):
            payload = read_json(student_dir / filename, None, problems)
            if payload in (None, {}, []):
                continue
            if isinstance(payload, dict):
                student_id = str(payload.get("id") or student_dir.name)
            else:
                student_id = student_dir.name
            counts[student_id] = counts.get(student_id, 0) + 1

    return expected, duplicates


def verify(data_dir: Path, db_path: Path) -> dict[str, Any]:
    problems: list[str] = []
    user_root = data_dir / "users"
    if not db_path.is_file():
        raise SystemExit("数据库不存在：%s（先跑迁移）" % db_path)
    expected, duplicates = collect_expected(user_root, problems)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    checked = 0
    rows = 0
    try:
        for table, counts in sorted(expected.items()):
            column = TABLE_SCOPE_COLUMN.get(table, "student_id")
            sql = "SELECT COUNT(*) FROM %s WHERE %s = ?" % (table, column)
            for student_id, wanted in sorted(counts.items()):
                actual = conn.execute(sql, (student_id,)).fetchone()[0]
                checked += 1
                if wanted != actual:
                    problems.append(
                        "%s(%s)：JSON=%d DB=%d" % (table, student_id, wanted, actual)
                    )
        for table in expected:
            rows += conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
        return {
            "data_dir": str(data_dir),
            "db": str(db_path),
            "students": len(user_dirs(user_root)),
            "checked": checked,
            "rows": rows,
            "duplicates": duplicates,
            "problems": problems,
        }
    finally:
        conn.close()


def print_summary(result: dict[str, Any]) -> None:
    print("数据目录：%s" % result["data_dir"])
    print("数据库  ：%s" % result["db"])
    print("学号目录：%d" % result["students"])

    if "stats" not in result:
        print("")
        print("核对范围：%d 组（表 x 学号），库内命中的目标表总行数：%d" % (result["checked"], result["rows"]))
        if result.get("duplicates"):
            print("跨目录重复 id（表主键去重后只落一行）：%s" % result["duplicates"])
        if result["problems"]:
            print("差异 %d 条：" % len(result["problems"]))
            for line in result["problems"][:40]:
                print("  - %s" % line)
        else:
            print("结论：JSON 与 SQLite 条数逐学号一致")
        return

    if result.get("dry_run"):
        print("模式    ：dry-run（未写库）")
    elif result.get("force"):
        print("模式    ：force（覆盖已存在的行）")
    print("")
    print("%-22s %8s %8s %8s" % ("表", "JSON 条数", "本次写入", "跳过"))
    total_json = total_written = 0
    for table, entry in sorted(result["stats"].items()):
        skipped = entry["json"] - entry["written"]
        print("%-22s %8d %8d %8d" % (table, entry["json"], entry["written"], skipped))
        total_json += entry["json"]
        total_written += entry["written"]
    print("%-22s %8d %8d %8d" % ("合计", total_json, total_written, total_json - total_written))
    print("（跳过 = 主键已存在；同一 id 被复制到多个学号目录时只保留首次出现）")
    if result.get("synthesized_students"):
        print("")
        print("补建 student 行（只有画像/资源、缺 student.json）：%s"
              % ", ".join(result["synthesized_students"]))
    if result.get("problems"):
        print("")
        print("异常 %d 条：" % len(result["problems"]))
        for line in result["problems"][:40]:
            print("  - %s" % line)
        if len(result["problems"]) > 40:
            print("  ...（还有 %d 条）" % (len(result["problems"]) - 40))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="JSON 数据回填到 SQLite")
    parser.add_argument("--data-dir", default=None, help="数据目录（含 users/ 与 app.db）")
    parser.add_argument("--db", default=None, help="数据库路径，默认 <data-dir>/app.db")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写库")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的行（默认跳过）")
    parser.add_argument("--verify-only", action="store_true", help="只做条数核对")
    parser.add_argument("--report", default=None, help="把结果写成 JSON 文件")
    args = parser.parse_args(argv)

    data_dir = resolve_data_dir(args.data_dir)
    db_path = Path(args.db).resolve() if args.db else data_dir / "app.db"

    result = verify(data_dir, db_path) if args.verify_only else migrate(
        data_dir, db_path, args.dry_run, args.force
    )
    print_summary(result)
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("")
        print("报表已写入：%s" % report_path)

    if result.get("problems"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
