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

    def patch_student(self, student_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        ...

    def insert_profile_snapshot(
        self, *, student_id: str, profile: dict[str, Any], evidence: dict[str, Any]
    ) -> dict[str, Any]:
        ...

    def get_latest_profile_snapshot(self, student_id: str) -> dict[str, Any] | None:
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
