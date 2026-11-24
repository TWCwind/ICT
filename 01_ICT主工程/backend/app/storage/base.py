from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """仓储层契约：签名与改造前的 app.repo 公共函数完全一致。

    路由、服务、测试都只依赖这些签名与返回结构，任何实现都必须保持等价。
    """

    name: str

    def ensure_student(self, *, student_id: str, major: str | None, goals: str | None) -> None:
        ...

    def get_student(self, student_id: str) -> dict[str, Any] | None:
        ...

    def patch_student(self, student_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        ...

    def insert_profile_snapshot(
        self, *, student_id: str, profile: dict[str, Any], evidence: dict[str, Any]
    ) -> dict[str, Any]:
        ...

    def get_latest_profile_snapshot(self, student_id: str) -> dict[str, Any] | None:
        ...

    def list_profile_snapshots(self, student_id: str) -> list[dict[str, Any]]:
        ...

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
        ...

    def get_resource_item(self, resource_id: str) -> dict[str, Any] | None:
        ...

    def list_resources(self, student_id: str) -> list[dict[str, Any]]:
        ...

    def delete_resource_item(self, student_id: str, resource_id: str) -> dict[str, Any] | None:
        ...

    def insert_learning_event(self, student_id: str, event_type: str, payload: dict[str, Any]) -> None:
        ...

    def insert_resource_usage(
        self,
        *,
        student_id: str,
        resource_id: str,
        action: str,
        duration_sec: int | None,
        feedback: dict[str, Any],
    ) -> None:
        ...

    def get_user_events(self, student_id: str) -> list[dict[str, Any]]:
        ...

    def get_user_usages(self, student_id: str) -> list[dict[str, Any]]:
        ...

    # ---- 练习记录 / 路径进度 / 知识掌握状态（阶段 3：原先直接读写 JSON 文件）----

    def list_quiz_records(self, student_id: str) -> list[dict[str, Any]]:
        ...

    def append_quiz_record(self, student_id: str, record: dict[str, Any]) -> None:
        ...

    def replace_quiz_records(self, student_id: str, records: list[dict[str, Any]]) -> None:
        ...

    def get_path_progress(self, student_id: str) -> dict[str, Any]:
        ...

    def save_path_progress(self, student_id: str, state: dict[str, Any]) -> None:
        ...

    def get_knowledge_state(self, student_id: str) -> dict[str, Any]:
        ...

    def save_knowledge_state(self, student_id: str, state: dict[str, Any]) -> None:
        ...
