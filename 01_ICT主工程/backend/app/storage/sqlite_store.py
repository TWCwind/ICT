from __future__ import annotations

import json
from typing import Any

from app.core.ids import new_id
from app.db.sqlite import db_conn, fetch_all, fetch_one
from app.storage.json_io import now_iso, remove_content_file

_STUDENT_TEXT_FIELDS = ("name", "major", "grade", "current_course", "goals")

_PROFILE_COLUMNS = (
    "knowledge_base_level",
    "cognitive_style",
    "mistake_patterns",
    "modality_preference",
    "pace_preference",
    "motivation_style",
)


def _dump(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _load(raw: Any, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _assignments(columns) -> str:
    return ", ".join("%s = ?" % column for column in columns)


def _placeholders(count: int) -> str:
    return ", ".join("?" for _ in range(count))


class SqliteStorage:
    """SQLite 实现：元数据入 data/app.db，正文文件仍留在磁盘（content_uri 不变）。"""

    name = "sqlite"

    # ---------- student ----------

    @staticmethod
    def _student_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {key: value for key, value in row.items() if value is not None}

    def ensure_student(self, *, student_id: str, major: str | None, goals: str | None) -> None:
        with db_conn() as conn:
            row = fetch_one(conn, "SELECT * FROM student WHERE id = ?", (student_id,))
            if row is None:
                conn.execute(
                    "INSERT INTO student (id, name, major, grade, current_course, goals, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (student_id, "", major or "", "", "", goals or "", now_iso(), None),
                )
                return
            updates: dict[str, Any] = {}
            if major is not None:
                updates["major"] = major
            if goals is not None:
                updates["goals"] = goals
            if updates:
                conn.execute(
                    "UPDATE student SET %s WHERE id = ?" % _assignments(updates),
                    (*updates.values(), student_id),
                )

    def get_student(self, student_id: str) -> dict[str, Any] | None:
        with db_conn() as conn:
            row = fetch_one(conn, "SELECT * FROM student WHERE id = ?", (student_id,))
        return self._student_row(row)

    def patch_student(self, student_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        with db_conn() as conn:
            row = self._student_row(fetch_one(conn, "SELECT * FROM student WHERE id = ?", (student_id,)))
            if row is None:
                row = {"id": student_id, "created_at": now_iso()}

            changed: dict[str, Any] = {}
            for key in _STUDENT_TEXT_FIELDS:
                value = str(updates.get(key) or "").strip()
                if not value or str(row.get(key) or "").strip() == value:
                    continue
                row[key] = value
                changed[key] = value

            if not changed:
                return row

            updated_at = now_iso()
            row["updated_at"] = updated_at
            changed["updated_at"] = updated_at

            exists = fetch_one(conn, "SELECT id FROM student WHERE id = ?", (student_id,))
            if exists is None:
                columns = ["id", *changed.keys(), "created_at"]
                values = [student_id, *changed.values(), row["created_at"]]
                conn.execute(
                    "INSERT INTO student (%s) VALUES (%s)" % (", ".join(columns), _placeholders(len(columns))),
                    tuple(values),
                )
            else:
                conn.execute(
                    "UPDATE student SET %s WHERE id = ?" % _assignments(changed),
                    (*changed.values(), student_id),
                )
            return row

    # ---------- profile_snapshot ----------

    def insert_profile_snapshot(
        self, *, student_id: str, profile: dict[str, Any], evidence: dict[str, Any]
    ) -> dict[str, Any]:
        snapshot_id = new_id()
        created_at = now_iso()
        columns = ["id", "student_id", *_PROFILE_COLUMNS, "evidence_json", "created_at"]
        values = [
            snapshot_id,
            student_id,
            *[profile.get(column) for column in _PROFILE_COLUMNS],
            _dump(evidence),
            created_at,
        ]
        with db_conn() as conn:
            conn.execute(
                "INSERT INTO profile_snapshot (%s) VALUES (%s)"
                % (", ".join(columns), _placeholders(len(columns))),
                tuple(values),
            )
        return {
            "id": snapshot_id,
            "student_id": student_id,
            **{column: profile[column] for column in _PROFILE_COLUMNS if column in profile},
            "evidence": evidence,
            "created_at": created_at,
        }

    @staticmethod
    def _profile_row(row: dict[str, Any]) -> dict[str, Any]:
        snapshot: dict[str, Any] = {"id": row["id"], "student_id": row["student_id"]}
        for column in _PROFILE_COLUMNS:
            if row.get(column) is not None:
                snapshot[column] = row[column]
        snapshot["evidence"] = _load(row.get("evidence_json"), {})
        snapshot["created_at"] = row["created_at"]
        return snapshot

    def list_profile_snapshots(self, student_id: str) -> list[dict[str, Any]]:
        with db_conn() as conn:
            rows = fetch_all(
                conn,
                "SELECT * FROM profile_snapshot WHERE student_id = ? ORDER BY created_at ASC, rowid ASC",
                (student_id,),
            )
        return [self._profile_row(row) for row in rows]

    def get_latest_profile_snapshot(self, student_id: str) -> dict[str, Any] | None:
        with db_conn() as conn:
            row = fetch_one(
                conn,
                "SELECT * FROM profile_snapshot WHERE student_id = ?"
                " ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (student_id,),
            )
        if not row:
            return None
        snapshot: dict[str, Any] = {"id": row["id"], "student_id": row["student_id"]}
        for column in _PROFILE_COLUMNS:
            if row.get(column) is not None:
                snapshot[column] = row[column]
        snapshot["evidence"] = _load(row.get("evidence_json"), {})
        snapshot["created_at"] = row["created_at"]
        return snapshot

    # ---------- resource_item ----------

    @staticmethod
    def _resource_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "student_id": row["student_id"],
            "type": row["type"],
            "title": row["title"],
            "tags": _load(row.get("tags_json"), []),
            "content_uri": row["content_uri"],
            "meta": _load(row.get("meta_json"), {}),
            "created_at": row["created_at"],
        }

    def insert_resource_item(
        self,
        *,
        student_id: str,
        type: str,
        title: str,
        tags: list[str],
        content_uri: str,
        meta: dict[str, Any],
    ) -> dict[str, Any]:
        resource_id = new_id()
        created_at = now_iso()
        with db_conn() as conn:
            conn.execute(
                "INSERT INTO resource_item"
                " (id, student_id, type, title, tags_json, content_uri, meta_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    resource_id,
                    student_id,
                    type,
                    title,
                    _dump(tags),
                    content_uri,
                    _dump(meta),
                    created_at,
                ),
            )
        return {
            "id": resource_id,
            "student_id": student_id,
            "type": type,
            "title": title,
            "tags": tags,
            "content_uri": content_uri,
            "meta": meta,
            "created_at": created_at,
        }

    def get_resource_item(self, resource_id: str) -> dict[str, Any] | None:
        with db_conn() as conn:
            row = fetch_one(conn, "SELECT * FROM resource_item WHERE id = ?", (resource_id,))
        return self._resource_row(row) if row else None

    def list_resources(self, student_id: str) -> list[dict[str, Any]]:
        with db_conn() as conn:
            rows = fetch_all(
                conn,
                "SELECT * FROM resource_item WHERE student_id = ?"
                " ORDER BY created_at DESC, rowid DESC",
                (student_id,),
            )
        return [self._resource_row(row) for row in rows]

    def delete_resource_item(self, student_id: str, resource_id: str) -> dict[str, Any] | None:
        with db_conn() as conn:
            row = fetch_one(
                conn,
                "SELECT * FROM resource_item WHERE student_id = ? AND id = ?",
                (student_id, resource_id),
            )
            if not row:
                return None
            conn.execute(
                "DELETE FROM resource_item WHERE student_id = ? AND id = ?",
                (student_id, resource_id),
            )
        item = self._resource_row(row)
        removed_file = remove_content_file(str(item.get("content_uri") or ""))
        return {**item, "removed_file": removed_file}

    # ---------- learning_event ----------

    def insert_learning_event(self, student_id: str, event_type: str, payload: dict[str, Any]) -> None:
        with db_conn() as conn:
            conn.execute(
                "INSERT INTO learning_event (id, student_id, event_type, payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (new_id(), student_id, event_type, _dump(payload), now_iso()),
            )

    def get_user_events(self, student_id: str) -> list[dict[str, Any]]:
        with db_conn() as conn:
            rows = fetch_all(
                conn,
                "SELECT * FROM learning_event WHERE student_id = ? ORDER BY rowid ASC",
                (student_id,),
            )
        return [
            {
                "id": row["id"],
                "student_id": row["student_id"],
                "event_type": row["event_type"],
                "payload": _load(row.get("payload_json"), {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # ---------- resource_usage ----------

    def insert_resource_usage(
        self,
        *,
        student_id: str,
        resource_id: str,
        action: str,
        duration_sec: int | None,
        feedback: dict[str, Any],
    ) -> None:
        with db_conn() as conn:
            conn.execute(
                "INSERT INTO resource_usage"
                " (id, resource_id, student_id, action, duration_sec, feedback_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    new_id(),
                    resource_id,
                    student_id,
                    action,
                    duration_sec,
                    _dump(feedback),
                    now_iso(),
                ),
            )

    def get_user_usages(self, student_id: str) -> list[dict[str, Any]]:
        with db_conn() as conn:
            rows = fetch_all(
                conn,
                "SELECT * FROM resource_usage WHERE student_id = ? ORDER BY rowid ASC",
                (student_id,),
            )
        return [
            {
                "id": row["id"],
                "resource_id": row["resource_id"],
                "student_id": row["student_id"],
                "action": row["action"],
                "duration_sec": row.get("duration_sec"),
                "feedback": _load(row.get("feedback_json"), {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # ---------- 练习记录（原始记录整体存 detail_json，列只用于查询）----------

    @staticmethod
    def _quiz_row(row: dict[str, Any]) -> dict[str, Any]:
        detail = _load(row.get("detail_json"), None)
        if isinstance(detail, dict):
            return detail
        return {
            "id": row["id"],
            "student_id": row["student_id"],
            "question_id": row.get("question_id") or "",
            "correct": bool(row.get("is_correct")),
            "tags": _load(row.get("tags_json"), []),
            "course": row.get("course") or "",
            "major": row.get("major") or "",
            "chapter": row.get("chapter") or "",
        }

    @staticmethod
    def _insert_quiz(conn, record: dict[str, Any], student_id: str) -> None:
        columns = (
            "id", "student_id", "resource_id", "score", "weak_points_json", "created_at",
            "question_id", "is_correct", "tags_json", "course", "major", "chapter", "detail_json",
        )
        correct = record.get("correct")
        values = (
            str(record.get("id") or new_id()),
            str(student_id or record.get("student_id") or ""),
            str(record.get("resource_id") or "") or None,
            100 if correct is True else (0 if correct is False else None),
            None,
            str(record.get("created_at") or now_iso()),
            str(record.get("question_id") or "") or None,
            None if correct is None else (1 if correct else 0),
            _dump(record.get("tags") if isinstance(record.get("tags"), list) else []),
            str(record.get("course") or "") or None,
            str(record.get("major") or "") or None,
            str(record.get("chapter") or "") or None,
            _dump(record),
        )
        conn.execute(
            "INSERT OR REPLACE INTO quiz_attempt (%s) VALUES (%s)"
            % (", ".join(columns), _placeholders(len(columns))),
            values,
        )

    def list_quiz_records(self, student_id: str) -> list[dict[str, Any]]:
        with db_conn() as conn:
            rows = fetch_all(
                conn,
                "SELECT * FROM quiz_attempt WHERE student_id = ? ORDER BY rowid ASC",
                (student_id,),
            )
        return [self._quiz_row(row) for row in rows]

    def append_quiz_record(self, student_id: str, record: dict[str, Any]) -> None:
        """单条 INSERT：并发作答不再读改写整份记录，天然不丢写。"""
        with db_conn() as conn:
            self._insert_quiz(conn, record, student_id)

    def replace_quiz_records(self, student_id: str, records: list[dict[str, Any]]) -> None:
        """整表替换（删除单条 / 清空错题走这里），与 JSON 模式语义一致。"""
        with db_conn() as conn:
            conn.execute("DELETE FROM quiz_attempt WHERE student_id = ?", (student_id,))
            for record in records:
                self._insert_quiz(conn, record, student_id)

    # ---------- 路径进度 / 知识掌握状态（整块 JSON 存一列）----------

    def get_path_progress(self, student_id: str) -> dict[str, Any]:
        with db_conn() as conn:
            row = fetch_one(conn, "SELECT * FROM path_progress_state WHERE student_id = ?", (student_id,))
        if not row:
            return {}
        state = _load(row.get("state_json"), {})
        return state if isinstance(state, dict) else {}

    def save_path_progress(self, student_id: str, state: dict[str, Any]) -> None:
        with db_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO path_progress_state"
                " (student_id, version, plan_key, pass_threshold, current_stage_id, state_json, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    student_id,
                    str(state.get("version") or "") or None,
                    str(state.get("plan_key") or "") or None,
                    state.get("pass_threshold"),
                    str(state.get("current_stage_id") or "") or None,
                    _dump(state),
                    str(state.get("updated_at") or now_iso()),
                ),
            )

    def get_knowledge_state(self, student_id: str) -> dict[str, Any]:
        with db_conn() as conn:
            row = fetch_one(conn, "SELECT * FROM knowledge_state WHERE student_id = ?", (student_id,))
        if not row:
            return {"nodes": {}}
        nodes = _load(row.get("nodes_json"), {})
        return {"nodes": nodes if isinstance(nodes, dict) else {}}

    def save_knowledge_state(self, student_id: str, state: dict[str, Any]) -> None:
        nodes = state.get("nodes") if isinstance(state, dict) else {}
        with db_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO knowledge_state (student_id, nodes_json, updated_at) VALUES (?, ?, ?)",
                (student_id, _dump(nodes if isinstance(nodes, dict) else {}), now_iso()),
            )

