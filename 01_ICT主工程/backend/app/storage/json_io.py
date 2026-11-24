from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_user_dir(student_id: str) -> Path:
    user_dir = settings.data_path / "users" / student_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def remove_content_file(content_uri: str) -> bool:
    """删除 content_uri 指向的磁盘正文文件；只允许 data 目录内的相对路径。"""
    uri = content_uri.strip().lstrip("/")
    if not uri:
        return False
    data_root = settings.data_path.resolve()
    candidate = (settings.data_path / uri).resolve()
    try:
        candidate.relative_to(data_root)
    except ValueError:
        return False
    if not candidate.is_file():
        return False
    try:
        candidate.unlink()
        return True
    except OSError:
        return False
