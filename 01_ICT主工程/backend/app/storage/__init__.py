from __future__ import annotations

import threading

from app.core.config import settings
from app.storage.base import StorageBackend

_backend: StorageBackend | None = None
_backend_key: tuple[str, str] | None = None
_BACKEND_LOCK = threading.Lock()


def backend_name() -> str:
    """当前生效的存储后端名（环境变量 STORAGE_BACKEND，默认 json）。"""
    name = str(getattr(settings, "storage_backend", "json") or "json").strip().lower()
    return name or "json"


def get_backend() -> StorageBackend:
    global _backend, _backend_key
    name = backend_name()
    key = (name, str(settings.data_path))
    if _backend is not None and _backend_key == key:
        return _backend

    with _BACKEND_LOCK:
        if _backend is not None and _backend_key == key:
            return _backend

        if name == "json":
            from app.storage.json_store import JsonStorage

            backend: StorageBackend = JsonStorage()
        elif name == "sqlite":
            from app.db import init_db
            from app.storage.sqlite_store import SqliteStorage

            init_db()
            backend = SqliteStorage()
        else:
            raise ValueError("未知的 STORAGE_BACKEND=%r，可选值：json / sqlite" % name)

        _backend = backend
        _backend_key = key
        return backend


def reset_backend_cache() -> None:
    global _backend, _backend_key
    _backend = None
    _backend_key = None


__all__ = ["StorageBackend", "backend_name", "get_backend", "reset_backend_cache"]
