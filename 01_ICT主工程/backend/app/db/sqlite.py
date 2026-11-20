from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.core.config import settings


DDL = [
    """
CREATE TABLE IF NOT EXISTS student (
  id TEXT PRIMARY KEY,
  name TEXT,
  major TEXT,
  grade TEXT,
  current_course TEXT,
  goals TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT
);
""",
    """
CREATE TABLE IF NOT EXISTS profile_snapshot (
  id TEXT PRIMARY KEY,
  student_id TEXT NOT NULL,
  knowledge_base_level TEXT,
  cognitive_style TEXT,
  mistake_patterns TEXT,
  modality_preference TEXT,
  pace_preference TEXT,
  motivation_style TEXT,
  evidence_json TEXT,
  created_at TEXT NOT NULL
);
""",
    """
CREATE TABLE IF NOT EXISTS resource_item (
  id TEXT PRIMARY KEY,
  student_id TEXT NOT NULL,
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  tags_json TEXT,
  content_uri TEXT NOT NULL,
  meta_json TEXT,
  created_at TEXT NOT NULL
);
""",
    """
CREATE TABLE IF NOT EXISTS path_plan (
  id TEXT PRIMARY KEY,
  student_id TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  rationale TEXT,
  created_at TEXT NOT NULL
);
""",
    """
CREATE TABLE IF NOT EXISTS path_step (
  id TEXT PRIMARY KEY,
  path_plan_id TEXT NOT NULL,
  order_index INTEGER NOT NULL,
  objective TEXT NOT NULL,
  prerequisites_json TEXT,
  resource_ids_json TEXT,
  assessment TEXT
);
""",
    """
CREATE TABLE IF NOT EXISTS quiz_attempt (
  id TEXT PRIMARY KEY,
  student_id TEXT NOT NULL,
  resource_id TEXT,
  score INTEGER,
  weak_points_json TEXT,
  created_at TEXT NOT NULL,
  question_id TEXT,
  is_correct INTEGER,
  tags_json TEXT,
  course TEXT,
  major TEXT,
  chapter TEXT,
  detail_json TEXT
);
""",
    """
CREATE TABLE IF NOT EXISTS learning_event (
  id TEXT PRIMARY KEY,
  student_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT,
  created_at TEXT NOT NULL
);
""",
    """
CREATE TABLE IF NOT EXISTS resource_usage (
  id TEXT PRIMARY KEY,
  resource_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  action TEXT NOT NULL,
  duration_sec INTEGER,
  feedback_json TEXT,
  created_at TEXT NOT NULL
);
""",
    """
CREATE TABLE IF NOT EXISTS path_progress_state (
  student_id TEXT PRIMARY KEY,
  version TEXT,
  plan_key TEXT,
  pass_threshold REAL,
  current_stage_id TEXT,
  state_json TEXT NOT NULL,
  updated_at TEXT
);
""",
    """
CREATE TABLE IF NOT EXISTS knowledge_state (
  student_id TEXT PRIMARY KEY,
  nodes_json TEXT NOT NULL,
  updated_at TEXT
);
""",
]


# 早期版本的 student 表缺少这些列；init_db 时按需补齐（只加列，不动已有数据）。
_STUDENT_EXTRA_COLUMNS = {
    "name": "TEXT",
    "current_course": "TEXT",
    "updated_at": "TEXT",
}


# 早期版本的 quiz_attempt 缺少这些列（阶段 2 迁移扩展），同样按需补齐。
_QUIZ_EXTRA_COLUMNS = {
    "question_id": "TEXT",
    "is_correct": "INTEGER",
    "tags_json": "TEXT",
    "course": "TEXT",
    "major": "TEXT",
    "chapter": "TEXT",
    "detail_json": "TEXT",
}


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(%s)" % table)}
    for column, ddl_type in columns.items():
        if column in existing:
            continue
        conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, ddl_type))


def init_storage() -> None:
    settings.data_path.mkdir(parents=True, exist_ok=True)
    settings.files_path.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    init_storage()
    db_path: Path = settings.db_path
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=OFF;")
        for sql in DDL:
            conn.executescript(sql)
        _ensure_columns(conn, "student", _STUDENT_EXTRA_COLUMNS)
        _ensure_columns(conn, "quiz_attempt", _QUIZ_EXTRA_COLUMNS)
        conn.commit()


@contextmanager
def db_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def fetch_one(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    cur = conn.execute(sql, params)
    row = cur.fetchone()
    return dict(row) if row else None


def fetch_all(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]

