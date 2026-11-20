from __future__ import annotations

"""仓储层门面。

对外暴露的函数签名、参数名与返回结构与改造前完全一致（路由 / 服务 / 测试的契约），
具体实现由环境变量 STORAGE_BACKEND 决定：
    json   —— data/users/<学号>/*.json（默认，保持原有行为）
    sqlite —— data/app.db（元数据入库，正文文件仍在磁盘）

底层 JSON 读写工具（read_json / write_json / get_user_dir / now_iso）继续从这里导出，
因为 path_progress、knowledge_state、exercise_bank 等模块直接依赖它们。
"""

from typing import Any

from app.storage import get_backend
from app.storage.json_io import get_user_dir, now_iso, read_json, write_json

__all__ = [
    "now_iso",
    "get_user_dir",
    "read_json",
    "write_json",
    "ensure_student",
    "patch_student",
    "insert_profile_snapshot",
    "get_latest_profile_snapshot",
    "insert_resource_item",
    "get_resource_item",
    "list_resources",
    "delete_resource_item",
    "insert_learning_event",
    "insert_resource_usage",
    "get_user_events",
    "get_user_usages",
]


def ensure_student(*, student_id: str, major: str | None, goals: str | None) -> None:
    get_backend().ensure_student(student_id=student_id, major=major, goals=goals)


def patch_student(student_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """只写入非空且与现值不同的基本信息字段，返回落盘后的 student 数据。"""
    return get_backend().patch_student(student_id, updates)


def insert_profile_snapshot(
    *, student_id: str, profile: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    return get_backend().insert_profile_snapshot(student_id=student_id, profile=profile, evidence=evidence)


def get_latest_profile_snapshot(student_id: str) -> dict[str, Any] | None:
    return get_backend().get_latest_profile_snapshot(student_id)


def insert_resource_item(
    *,
    student_id: str,
    type: str,
    title: str,
    tags: list[str],
    content_uri: str,
    meta: dict[str, Any],
) -> dict[str, Any]:
    return get_backend().insert_resource_item(
        student_id=student_id,
        type=type,
        title=title,
        tags=tags,
        content_uri=content_uri,
        meta=meta,
    )


def get_resource_item(resource_id: str) -> dict[str, Any] | None:
    return get_backend().get_resource_item(resource_id)


def list_resources(student_id: str) -> list[dict[str, Any]]:
    return get_backend().list_resources(student_id)


def delete_resource_item(student_id: str, resource_id: str) -> dict[str, Any] | None:
    """删除一条资源（档案袋条目）及正文文件；返回被删除的记录，未找到返回 None。"""
    return get_backend().delete_resource_item(student_id, resource_id)


def insert_learning_event(student_id: str, event_type: str, payload: dict[str, Any]) -> None:
    get_backend().insert_learning_event(student_id, event_type, payload)


def insert_resource_usage(
    *, student_id: str, resource_id: str, action: str, duration_sec: int | None, feedback: dict[str, Any]
) -> None:
    get_backend().insert_resource_usage(
        student_id=student_id,
        resource_id=resource_id,
        action=action,
        duration_sec=duration_sec,
        feedback=feedback,
    )


def get_user_events(student_id: str) -> list[dict[str, Any]]:
    """获取用户的所有学习事件（用于潜在问题发现等场景）"""
    return get_backend().get_user_events(student_id)


def get_user_usages(student_id: str) -> list[dict[str, Any]]:
    """获取用户的所有资源使用记录（包含反馈信息）"""
    return get_backend().get_user_usages(student_id)
