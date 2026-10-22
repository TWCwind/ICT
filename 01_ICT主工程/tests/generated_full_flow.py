from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from testlib import assert_success, assert_true, record_result, request_json, run_case


BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
DATA_ROOT = Path(os.environ.get("DATA_DIR", ""))
BAD_NAME = re.compile(r"(?:[0-9a-f]{16,32}|book_|textbook_|第\d+部分)", re.IGNORECASE)


def get(path: str):
    return request_json(BASE_URL, "GET", path)


def post(path: str, payload: dict):
    return request_json(BASE_URL, "POST", path, payload)


def success(path: str, payload: dict | None = None) -> dict:
    response = post(path, payload or {}) if payload is not None else get(path)
    return assert_success(response, path)


def load_manifest() -> dict:
    return json.loads((DATA_ROOT / "dataset_manifest.json").read_text(encoding="utf-8"))


def test_generated_dataset_contract() -> None:
    manifest = load_manifest()
    assert_true(manifest.get("dataset_id") == "test/generated/full-flow-v1", "generated dataset marker missing")
    assert_true(len(manifest.get("students") or []) == 3, "generated student count must be 3")
    assert_true(len(manifest.get("roles") or []) == 5, "generated role count must be 5")
    course = manifest.get("course") or {}
    assert_true(course.get("chapter_count", 0) >= 6, "generated course must have at least 6 chapters")
    assert_true(course.get("knowledge_point_count", 0) >= 18, "generated course must have at least 18 knowledge points")
    assert_true(manifest.get("resource_count", 0) >= 2, "generated dataset must have at least 2 resources")
    assert_true(all(str(role.get("role_id", "")).startswith("generated-") for role in manifest["roles"]), "role data must be generated")


def test_health_and_three_learners() -> None:
    health = success("/api/health")
    assert_true(health.get("data_dir_ready") is True, "generated data directory is not ready")
    for student_id in ("demo", "active-learner", "new-learner"):
        profile = success(f"/api/profile/{student_id}/overview")
        assert_true(profile.get("learner", {}).get("student_id") == student_id, f"profile identity mismatch: {student_id}")


def test_demo_graph_counts_and_semantics() -> None:
    graph = success("/api/knowledge/graph?student_id=demo&max_nodes=100")
    nodes = graph.get("nodes") or []
    chapters = [node for node in nodes if node.get("kind") == "chapter"]
    concepts = [node for node in nodes if node.get("kind") == "concept"]
    assert_true(len(chapters) >= 6, f"demo graph chapters={len(chapters)}")
    assert_true(len(concepts) >= 18, f"demo graph concepts={len(concepts)}")
    assert_true((graph.get("stats") or {}).get("chapters") == len(chapters), "chapter stats do not match nodes")
    assert_true((graph.get("stats") or {}).get("concepts") == len(concepts), "concept stats do not match nodes")
    names = [str(node.get("name") or "") for node in chapters + concepts]
    assert_true(not any(BAD_NAME.search(name) for name in names), f"non-semantic graph name found: {names}")
    required = {"业务场景与范围", "需求获取与表达", "用例与行为建模", "领域结构建模", "质量与约束", "验证与变更"}
    assert_true(required.issubset(set(names)), "semantic chapter names are incomplete")


def test_new_learner_isolated_from_demo_course() -> None:
    graph = success("/api/knowledge/graph?student_id=new-learner&max_nodes=100")
    assert_true(graph.get("nodes") == [], "new learner unexpectedly inherited demo course nodes")
    assert_true((graph.get("stats") or {}).get("chapters") == 0, "new learner unexpectedly has course chapters")


def test_active_learner_state_and_writes() -> None:
    resources = success("/api/workshop/resources?student_id=active-learner")
    resource_items = resources.get("resources") or []
    assert_true(len(resource_items) >= 2, "active learner resources missing")
    assert_true(all("test/generated" in (item.get("tags") or []) for item in resource_items), "generated resource marker missing")

    stats = success("/api/exercise/stats?student_id=active-learner").get("stats") or {}
    assert_true(stats.get("total", 0) >= 2, "active learner exercise evidence missing")
    assert_true(stats.get("wrong", 0) >= 1, "active learner wrong-answer evidence missing")
    wrong_book = success("/api/exercise/wrong-book?student_id=active-learner")
    assert_true(wrong_book.get("records"), "wrong-book records missing")

    path = success("/api/path/overview?student_id=active-learner")
    assert_true(path.get("nodes"), "active learner path missing")
    branch = success(
        "/api/path/branch",
        {
            "student_id": "active-learner",
            "knowledge_node_id": "kp-performance",
            "title": "测试数据：性能指标补强",
            "description": "围绕性能指标建立可度量的验收证据。",
            "mastery": 42,
        },
    )
    assert_true(branch.get("path", {}).get("branches"), "path branch was not persisted")

    profile = success(
        "/api/profile/chat",
        {
            "student_id": "active-learner",
            "messages": [{"role": "user", "content": "我希望用验收标准和需求追踪矩阵完成课程项目。"}],
            "major": "软件工程",
            "goals": "完成需求建模项目",
        },
    )
    snapshot = profile.get("snapshot") or {}
    assert_true(snapshot.get("student_id") == "active-learner", "profile update did not persist learner")
    assert_true(len(snapshot.get("dimensions") or {}) >= 6, "profile update did not return six dimensions")

    tracked = success(
        "/api/knowledge/track",
        {"student_id": "active-learner", "node_id": "kp-performance", "score": 55, "note": "generated QA tracking"},
    )
    assert_true(tracked.get("node_id") == "kp-performance", "knowledge mastery update missing")


def test_explainable_errors() -> None:
    missing_resource = get("/api/resources/not-found-resource")
    assert_true(missing_resource.get("status") == 404, "missing resource must return 404")
    missing_body = missing_resource.get("body") or {}
    assert_true(missing_body.get("success") is False, "missing resource should fail explicitly")
    assert_true((missing_body.get("error") or {}).get("message") == "resource_not_found", "missing resource error is not explainable")

    invalid = get("/api/knowledge/graph?student_id=new-learner&max_nodes=1000")
    invalid_body = invalid.get("body") or {}
    assert_true(invalid.get("status") == 422, "invalid max_nodes must return validation error")
    assert_true(invalid_body.get("detail"), "invalid max_nodes error detail missing")


def main() -> int:
    results: list[dict] = []
    cases = [
        test_generated_dataset_contract,
        test_health_and_three_learners,
        test_demo_graph_counts_and_semantics,
        test_new_learner_isolated_from_demo_course,
        test_active_learner_state_and_writes,
        test_explainable_errors,
    ]
    for case in cases:
        run_case(results, case.__name__, case)
    record_result("generated_full_flow.json", results)
    return 1 if any(item["status"] != "passed" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
