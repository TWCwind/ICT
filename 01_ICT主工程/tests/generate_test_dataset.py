from __future__ import annotations

import argparse
import copy
import json
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEED_ROOT = PROJECT_ROOT / "roadshow-seed"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def student_files(root: Path, student_id: str, *, profile: list[dict], events: list[dict], resources: list[dict], exercises: list[dict], path_progress: dict | None = None) -> None:
    user_root = root / "users" / student_id
    user_root.mkdir(parents=True, exist_ok=True)
    write_json(
        user_root / "student.json",
        {
            "id": student_id,
            "major": "软件工程",
            "grade": "大二",
            "goals": "完成需求分析课程项目，并能独立完成需求建模与验收。",
            "created_at": "2026-10-22T00:00:00+08:00",
        },
    )
    write_json(user_root / "profiles.json", profile)
    write_json(user_root / "events.json", events)
    write_json(user_root / "resources.json", resources)
    write_json(user_root / "exercise_records.json", exercises)
    if path_progress is not None:
        write_json(user_root / "path_progress.json", path_progress)


def build_dataset(output: Path) -> dict:
    if not SEED_ROOT.is_dir():
        raise FileNotFoundError(f"missing seed directory: {SEED_ROOT}")
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(SEED_ROOT, output)

    active_profile = {
        "id": "generated-profile-active",
        "student_id": "active-learner",
        "knowledge_base_level": "intermediate",
        "cognitive_style": "structured",
        "mistake_patterns": "容易遗漏非功能需求的度量方式，需要加强验收证据整理。",
        "modality_preference": "diagram_and_case",
        "pace_preference": "moderate",
        "motivation_style": "project-oriented",
        "evidence": {
            "weak_points": ["性能指标", "需求追踪"],
            "keywords": ["领域模型", "验收标准", "需求追踪"],
        },
        "created_at": "2026-10-22T01:00:00+08:00",
    }
    active_events = [
        {
            "id": "generated-event-profile",
            "student_id": "active-learner",
            "event_type": "profile_snapshot",
            "payload": {"source": "test/generated", "topic": "需求建模"},
            "created_at": "2026-10-22T01:01:00+08:00",
        },
        {
            "id": "generated-event-resource",
            "student_id": "active-learner",
            "event_type": "resource_view",
            "payload": {"resource_id": "generated-resource-checklist", "duration_sec": 420},
            "created_at": "2026-10-22T01:02:00+08:00",
        },
    ]
    demo_path_event = next(
        item for item in json.loads((SEED_ROOT / "users" / "demo" / "events.json").read_text(encoding="utf-8"))
        if item.get("event_type") == "path_plan"
    )
    generated_path_event = copy.deepcopy(demo_path_event)
    generated_path_event["id"] = "generated-event-path"
    generated_path_event["student_id"] = "active-learner"
    generated_path_event["created_at"] = "2026-10-22T01:02:30+08:00"
    generated_path_event["payload"]["created_by"] = "test/generated"
    active_events.append(generated_path_event)
    active_resources = [
        {
            "id": "generated-resource-lecture",
            "student_id": "active-learner",
            "type": "lecture_doc",
            "title": "测试数据：需求建模讲义",
            "tags": ["test/generated", "需求建模", "领域模型"],
            "content_uri": "files/demo/软件需求分析与建模-演示讲义.md",
            "meta": {"source": "test/generated", "local_only": True},
            "created_at": "2026-10-22T01:03:00+08:00",
        },
        {
            "id": "generated-resource-checklist",
            "student_id": "active-learner",
            "type": "reading",
            "title": "测试数据：需求验收清单",
            "tags": ["test/generated", "验收标准", "需求追踪"],
            "content_uri": "files/demo/需求验收与追踪清单.md",
            "meta": {"source": "test/generated", "local_only": True},
            "created_at": "2026-10-22T01:04:00+08:00",
        },
    ]
    active_exercises = [
        {
            "id": "generated-exercise-1",
            "question_id": "generated:requirements:1",
            "source": "test/generated",
            "type": "single_choice",
            "stem": "下列哪项最适合作为可验收的性能指标？",
            "answer": "A",
            "correct_answer": "B",
            "correct": False,
            "analysis": "性能指标需要可测量，例如响应时间和并发量。",
            "tags": ["test/generated", "性能指标"],
        },
        {
            "id": "generated-exercise-2",
            "question_id": "generated:requirements:2",
            "source": "test/generated",
            "type": "single_choice",
            "stem": "需求追踪矩阵主要用于连接哪些证据？",
            "answer": "A",
            "correct_answer": "A",
            "correct": True,
            "analysis": "需求追踪矩阵连接需求、设计、实现和测试证据。",
            "tags": ["test/generated", "需求追踪"],
        },
    ]
    path_progress = json.loads((SEED_ROOT / "users" / "demo" / "path_progress.json").read_text(encoding="utf-8"))
    path_progress["plan_key"] = "test-generated-path"
    path_progress["updated_at"] = "2026-10-22T01:05:00+08:00"

    student_files(
        output,
        "active-learner",
        profile=[active_profile],
        events=active_events,
        resources=active_resources,
        exercises=active_exercises,
        path_progress=path_progress,
    )
    student_files(
        output,
        "new-learner",
        profile=[],
        events=[],
        resources=[],
        exercises=[],
    )

    roles = [
        {"role_id": "generated-role-1", "role_name": "后端开发工程师", "level": "中级", "skills": ["Python", "FastAPI", "数据库"]},
        {"role_id": "generated-role-2", "role_name": "前端开发工程师", "level": "中级", "skills": ["Vue", "TypeScript", "可访问性"]},
        {"role_id": "generated-role-3", "role_name": "测试开发工程师", "level": "中高级", "skills": ["Python", "Playwright", "质量工程"]},
        {"role_id": "generated-role-4", "role_name": "产品需求分析师", "level": "中级", "skills": ["需求访谈", "用例建模", "验收标准"]},
        {"role_id": "generated-role-5", "role_name": "数据分析师", "level": "初级/未明确", "skills": ["SQL", "数据可视化", "指标分析"]},
    ]
    graph = json.loads((output / "uploads" / "textbooks" / "chapter_knowledge" / "book_roadshow-requirements.json").read_text(encoding="utf-8"))
    manifest = {
        "dataset_id": "test/generated/full-flow-v1",
        "students": ["demo", "active-learner", "new-learner"],
        "roles": roles,
        "course": {
            "title": graph["filename"],
            "chapter_count": graph["chapter_count"],
            "knowledge_point_count": graph["total_kp_count"],
            "source_type": "lecture",
        },
        "resource_count": 2,
        "generated_only": True,
        "source": "roadshow-seed copied into an isolated test runtime",
    }
    write_json(output / "roles.json", roles)
    write_json(output / "dataset_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate isolated full-flow test data.")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "test-results" / "generated-dataset")
    args = parser.parse_args()
    manifest = build_dataset(args.output.resolve())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"generated_dataset={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
