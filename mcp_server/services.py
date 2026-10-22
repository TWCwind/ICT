from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MAIN_PROJECT_ROOT = WORKSPACE_ROOT / "01_ICT主工程"
BACKEND_ROOT = MAIN_PROJECT_ROOT / "backend"
BACKEND_DATA_ROOT = BACKEND_ROOT / "data"
JOB_MODULE_ROOT = WORKSPACE_ROOT / "02_服创岗位能力模块" / "岗位图谱子系统"
JOB_DATA_PATH = WORKSPACE_ROOT / "02_服创岗位能力模块" / "结构化岗位画像.json"

# The original backend resolves DATA_DIR from the process working directory.
# Set a stable package-relative default before importing its service layer.
os.environ.setdefault("DATA_DIR", str(BACKEND_DATA_ROOT))
for import_root in (BACKEND_ROOT, JOB_MODULE_ROOT):
    import_path = str(import_root)
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from app.repo import get_user_events  # noqa: E402
from app.services.exercise_bank import exercise_summary  # noqa: E402
from app.services.learning_state import activity_feed, path_overview, profile_overview  # noqa: E402
from job_database import JobDatabase  # noqa: E402


_SAFE_STUDENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _success(data: dict[str, Any], *, source: str, data_mode: str) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "error": None,
        "meta": {"source": source, "data_mode": data_mode},
    }


def _failure(code: str, message: str, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "error": {"code": code, "message": message, "details": details or {}},
        "meta": {},
    }


def get_student_profile_data(student_id: str) -> dict[str, Any]:
    """Return an explainable student profile assembled by the existing service layer."""

    normalized_id = (student_id or "").strip()
    if not _SAFE_STUDENT_ID.fullmatch(normalized_id):
        return _failure(
            "INVALID_STUDENT_ID",
            "student_id 只能包含字母、数字、下划线或连字符，长度为 1-64。",
        )

    user_dir = BACKEND_DATA_ROOT / "users" / normalized_id
    if not user_dir.is_dir() or not (user_dir / "student.json").is_file():
        return _failure(
            "STUDENT_NOT_FOUND",
            f"未找到学生 {normalized_id} 的项目数据。",
            details={"student_id": normalized_id},
        )

    try:
        profile = profile_overview(normalized_id)
        events = get_user_events(normalized_id)
        stats = exercise_summary(normalized_id)
        recent_activity = activity_feed(normalized_id, limit=5)
        return _success(
            {
                "student_id": normalized_id,
                "basic_info": profile.get("learner", {}),
                "abilities": profile.get("dimensions", []),
                "weaknesses": profile.get("focus", {}).get("weak_points", []),
                "learning_summary": {
                    "profile_completeness": profile.get("completeness", 0),
                    "evidence_count": profile.get("evidence_count", 0),
                    "learning_event_count": len(events),
                    "exercise": stats,
                    "recent_activity": recent_activity,
                },
            },
            source="01_ICT主工程/backend/data + app.services",
            data_mode="bundled_demo_data" if normalized_id == "demo" else "project_local_data",
        )
    except Exception as exc:
        return _failure(
            "STUDENT_PROFILE_SERVICE_ERROR",
            "读取学生画像时发生服务异常。",
            details={"type": type(exc).__name__, "message": str(exc)},
        )


def _job_database() -> JobDatabase:
    return JobDatabase(data_path=str(JOB_DATA_PATH))


def _experience_level(experience_requirement: str) -> dict[str, str]:
    """Infer a display level while preserving the exact source requirement."""

    match = re.search(r"(\d+)", experience_requirement or "")
    years = int(match.group(1)) if match else 0
    if years >= 5:
        level = "高级"
    elif years >= 3:
        level = "中高级"
    elif years >= 2:
        level = "中级"
    else:
        level = "初级/未明确"
    return {
        "level": level,
        "basis": "由 experience_require 字段映射，仅用于展示，不替代原始岗位要求。",
        "source_value": experience_requirement or "未明确",
    }


def get_role_competency_data(role_name: str = "", role_id: str = "") -> dict[str, Any]:
    """Query the existing structured job profiles by exact ID or name."""

    normalized_name = (role_name or "").strip()
    normalized_id = (role_id or "").strip()
    if not normalized_name and not normalized_id:
        return _failure("MISSING_ROLE_QUERY", "role_name 和 role_id 至少提供一个。")
    if len(normalized_name) > 100 or len(normalized_id) > 64:
        return _failure("INVALID_ROLE_QUERY", "岗位名称或岗位 ID 长度超出限制。")

    try:
        jobs = _job_database().get_all_jobs()
        matched = None
        match_type = ""
        if normalized_id:
            matched = next((job for job in jobs if job.job_id == normalized_id), None)
            match_type = "exact_role_id"
        if matched is None and normalized_name:
            matched = next((job for job in jobs if job.job_name == normalized_name), None)
            match_type = "exact_role_name"
        if matched is None and normalized_name:
            candidates = [job for job in jobs if normalized_name.lower() in job.job_name.lower()]
            if len(candidates) == 1:
                matched = candidates[0]
                match_type = "unique_partial_role_name"
            elif len(candidates) > 1:
                return _failure(
                    "AMBIGUOUS_ROLE_NAME",
                    "岗位名称匹配到多个结果，请改用完整岗位名称或岗位 ID。",
                    details={"candidates": [{"role_id": j.job_id, "role_name": j.job_name} for j in candidates[:10]]},
                )

        if matched is None:
            return _failure(
                "ROLE_NOT_FOUND",
                "未在结构化岗位画像中找到对应岗位。",
                details={"role_name": normalized_name, "role_id": normalized_id},
            )

        job = matched.model_dump() if hasattr(matched, "model_dump") else matched.dict()
        skills = job.get("skill_require") or {}
        experience = str(job.get("experience_require") or "")
        return _success(
            {
                "role_id": job.get("job_id"),
                "role_name": job.get("job_name"),
                "category": job.get("job_category"),
                "requirements": {
                    "hard_skills": skills.get("hard_skills", []),
                    "soft_skills": skills.get("soft_skills", []),
                    "education": job.get("education_require", []),
                    "certificates": job.get("certificate_require", []),
                    "experience": experience,
                },
                "skill_level": _experience_level(experience),
                "core_competencies": job.get("core_competency", []),
                "responsibilities": job.get("job_responsibility", []),
                "matching_basis": {
                    "match_type": match_type,
                    "query": {"role_name": normalized_name, "role_id": normalized_id},
                    "evidence_fields": [
                        "skill_require.hard_skills",
                        "skill_require.soft_skills",
                        "experience_require",
                        "core_competency",
                        "job_responsibility",
                    ],
                },
            },
            source="02_服创岗位能力模块/结构化岗位画像.json + JobDatabase",
            data_mode="project_structured_data",
        )
    except Exception as exc:
        return _failure(
            "ROLE_COMPETENCY_SERVICE_ERROR",
            "读取岗位能力时发生服务异常。",
            details={"type": type(exc).__name__, "message": str(exc)},
        )


def get_project_status_data(student_id: str) -> dict[str, Any]:
    """Optional MCP tool: expose the persisted learning-path project status."""

    normalized_id = (student_id or "").strip()
    if not _SAFE_STUDENT_ID.fullmatch(normalized_id):
        return _failure("INVALID_STUDENT_ID", "student_id 格式不正确。")
    if not (BACKEND_DATA_ROOT / "users" / normalized_id / "student.json").is_file():
        return _failure("STUDENT_NOT_FOUND", f"未找到学生 {normalized_id} 的项目数据。")
    try:
        path = path_overview(normalized_id)
        return _success(
            {"student_id": normalized_id, "path": path},
            source="01_ICT主工程/backend/data + app.services.learning_state.path_overview",
            data_mode="bundled_demo_data" if normalized_id == "demo" else "project_local_data",
        )
    except Exception as exc:
        return _failure(
            "PROJECT_STATUS_SERVICE_ERROR",
            "读取项目状态时发生服务异常。",
            details={"type": type(exc).__name__, "message": str(exc)},
        )

