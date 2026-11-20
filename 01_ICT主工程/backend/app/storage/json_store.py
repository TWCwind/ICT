from __future__ import annotations

from typing import Any

from app.core.ids import new_id
from app.storage.json_io import get_user_dir, now_iso, read_json, remove_content_file, write_json


class JsonStorage:
    """JSON 文件实现：每个学生一个目录，行为与改造前的 app.repo 完全一致。"""

    name = "json"

    def ensure_student(self, *, student_id: str, major: str | None, goals: str | None) -> None:
        user_dir = get_user_dir(student_id)
        student_file = user_dir / "student.json"
        data = read_json(student_file, {})

        if not data:
            data = {
                "id": student_id,
                "major": major or "",
                "grade": "",
                "goals": goals or "",
                "created_at": now_iso(),
            }
        else:
            if major is not None:
                data["major"] = major
            if goals is not None:
                data["goals"] = goals

        write_json(student_file, data)

    def patch_student(self, student_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """只写入非空且与现值不同的基本信息字段，返回落盘后的 student 数据。"""
        user_dir = get_user_dir(student_id)
        student_file = user_dir / "student.json"
        data = read_json(student_file, {})
        if not data:
            data = {"id": student_id, "created_at": now_iso()}

        changed = False
        for key in _STUDENT_TEXT_FIELDS:
            value = str(updates.get(key) or "").strip()
            if not value or str(data.get(key) or "").strip() == value:
                continue
            data[key] = value
            changed = True

        if changed:
            data["updated_at"] = now_iso()
            write_json(student_file, data)

        return data

    def insert_profile_snapshot(
        self, *, student_id: str, profile: dict[str, Any], evidence: dict[str, Any]
    ) -> dict[str, Any]:
        user_dir = get_user_dir(student_id)
        profiles_file = user_dir / "profiles.json"
        profiles = read_json(profiles_file, [])

        snapshot_id = new_id()
        created_at = now_iso()

        snapshot = {
            "id": snapshot_id,
            "student_id": student_id,
            **profile,
            "evidence": evidence,
            "created_at": created_at,
        }

        profiles.append(snapshot)
        write_json(profiles_file, profiles)
        return snapshot

    def get_latest_profile_snapshot(self, student_id: str) -> dict[str, Any] | None:
        user_dir = get_user_dir(student_id)
        profiles_file = user_dir / "profiles.json"
        profiles = read_json(profiles_file, [])
        if not profiles:
            return None
        # 按创建时间降序
        profiles.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return profiles[0]

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
        user_dir = get_user_dir(student_id)
        resources_file = user_dir / "resources.json"
        resources = read_json(resources_file, [])

        resource_id = new_id()
        created_at = now_iso()

        item = {
            "id": resource_id,
            "student_id": student_id,
            "type": type,
            "title": title,
            "tags": tags,
            "content_uri": content_uri,
            "meta": meta,
            "created_at": created_at,
        }
        resources.append(item)
        write_json(resources_file, resources)
        return item

    def get_resource_item(self, resource_id: str) -> dict[str, Any] | None:
        from app.core.config import settings

        users_dir = settings.data_path / "users"
        if not users_dir.exists():
            return None
        for user_dir in users_dir.iterdir():
            if user_dir.is_dir():
                resources_file = user_dir / "resources.json"
                resources = read_json(resources_file, [])
                for r in resources:
                    if r.get("id") == resource_id:
                        return r
        return None

    def list_resources(self, student_id: str) -> list[dict[str, Any]]:
        user_dir = get_user_dir(student_id)
        resources_file = user_dir / "resources.json"
        resources = read_json(resources_file, [])
        resources.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return resources

    def delete_resource_item(self, student_id: str, resource_id: str) -> dict[str, Any] | None:
        user_dir = get_user_dir(student_id)
        resources_file = user_dir / "resources.json"
        resources = read_json(resources_file, [])
        target = next((item for item in resources if item.get("id") == resource_id), None)
        if target is None:
            return None
        remaining = [item for item in resources if item.get("id") != resource_id]
        write_json(resources_file, remaining)
        removed_file = remove_content_file(str(target.get("content_uri") or ""))
        return {**target, "removed_file": removed_file}

    def insert_learning_event(self, student_id: str, event_type: str, payload: dict[str, Any]) -> None:
        user_dir = get_user_dir(student_id)
        events_file = user_dir / "events.json"
        events = read_json(events_file, [])

        events.append(
            {
                "id": new_id(),
                "student_id": student_id,
                "event_type": event_type,
                "payload": payload,
                "created_at": now_iso(),
            }
        )
        write_json(events_file, events)

    def insert_resource_usage(
        self,
        *,
        student_id: str,
        resource_id: str,
        action: str,
        duration_sec: int | None,
        feedback: dict[str, Any],
    ) -> None:
        user_dir = get_user_dir(student_id)
        usage_file = user_dir / "usage.json"
        usages = read_json(usage_file, [])

        usages.append(
            {
                "id": new_id(),
                "resource_id": resource_id,
                "student_id": student_id,
                "action": action,
                "duration_sec": duration_sec,
                "feedback": feedback,
                "created_at": now_iso(),
            }
        )
        write_json(usage_file, usages)

    def get_user_events(self, student_id: str) -> list[dict[str, Any]]:
        user_dir = get_user_dir(student_id)
        events_file = user_dir / "events.json"
        return read_json(events_file, [])

    def get_user_usages(self, student_id: str) -> list[dict[str, Any]]:
        user_dir = get_user_dir(student_id)
        usage_file = user_dir / "usage.json"
        return read_json(usage_file, [])


_STUDENT_TEXT_FIELDS = ("name", "major", "grade", "current_course", "goals")
