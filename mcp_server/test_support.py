"""Helpers for reproducible MCP tests using isolated generated data."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = next(
    path
    for path in (WORKSPACE_ROOT / "01_主工程", WORKSPACE_ROOT / "01_ICT主工程")
    if (path / "roadshow-seed" / "users" / "demo" / "student.json").is_file()
)
ROADSHOW_SEED = PROJECT_ROOT / "roadshow-seed"
TEST_STUDENT_ID = "demo"
TEST_STAGE_ID = "mcp-smoke-stage-1"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_generated_test_data(destination: Path) -> Path:
    """Copy the bundled sample into a fresh directory and add generated fixtures."""
    destination = Path(destination).expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty test data directory: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROADSHOW_SEED, destination, dirs_exist_ok=True)

    marker = destination / "test" / "generated" / "manifest.json"
    _write_json(
        marker,
        {
            "classification": "test/generated",
            "source": "01_ICT主工程/roadshow-seed",
            "purpose": "MCP tool integration smoke test",
        },
    )

    user_dir = destination / "users" / TEST_STUDENT_ID
    resources_path = user_dir / "resources.json"
    resources = json.loads(resources_path.read_text(encoding="utf-8")) if resources_path.is_file() else []
    resource_id = "test-generated-mcp-question-bank"
    resources = [item for item in resources if str(item.get("id")) != resource_id]
    resources.append(
        {
            "id": resource_id,
            "student_id": TEST_STUDENT_ID,
            "type": "question_bank",
            "title": "MCP 隔离验证题库",
            "tags": ["test/generated", "MCP"],
            "content_uri": "files/test/generated/mcp-question-bank.json",
            "meta": {
                "requirement": {
                    "constraints": {
                        "source": "exercise_custom_bank",
                        "path_stage_id": TEST_STAGE_ID,
                        "path_stage_title": "MCP 隔离验证阶段",
                    }
                }
            },
            "created_at": "2099-01-01T00:00:00+00:00",
        }
    )
    _write_json(resources_path, resources)
    _write_json(
        destination / "files" / "test" / "generated" / "mcp-question-bank.json",
        {
            "meta": {"course": "MCP 隔离验证课程", "chapter": "题库读取"},
            "questions": [
                {
                    "type": "single_choice",
                    "stem": "此题库用于验证 MCP 练习闭环。",
                    "options": ["A. 隔离测试数据", "B. 生产用户数据"],
                    "answer": "A",
                    "analysis": "自动化验证只能写入临时 test/generated 数据副本。",
                    "knowledge_point": "测试数据隔离",
                    "tags": ["test/generated", "隔离"],
                }
            ],
        },
    )

    events_path = user_dir / "events.json"
    events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.is_file() else []
    events.append(
        {
            "id": "test-generated-mcp-path-plan",
            "student_id": TEST_STUDENT_ID,
            "event_type": "path_plan",
            "payload": {
                "title": "MCP 隔离验证路径",
                "path": {
                    "title": "MCP 隔离验证路径",
                    "nodes": [
                        {
                            "id": TEST_STAGE_ID,
                            "title": "MCP 隔离验证阶段",
                            "objective": "验证路径分支写入",
                            "status": "current",
                        }
                    ],
                },
            },
            "created_at": "2099-01-01T00:00:00+00:00",
        }
    )
    _write_json(events_path, events)
    return destination
