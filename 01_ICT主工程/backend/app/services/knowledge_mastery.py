from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import time

from app.repo import get_latest_profile_snapshot
from app.repo import get_user_events
from app.repo import get_user_usages
from app.repo import insert_learning_event
from app.repo import list_resources
from app.repo import write_json

from app.services.knowledge_graph import graph_data
from app.services.knowledge_state import _decayed_mastery
from app.services.knowledge_state import _read_state
from app.services.knowledge_state import _state_file
from app.services.knowledge_state import _update_mastery
from app.services.knowledge_text import _node_status

"""掌握度与学习痕迹：掌握度计算、节点打卡、维度分、徽章、活动流与搜索事件。"""

def mastery_data(student_id: str) -> dict[str, Any]:
    graph = graph_data(student_id)
    state = _read_state(student_id)
    now = time.time()
    nodes: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []

    for node in graph["nodes"]:
        record = state.get("nodes", {}).get(node["id"], {})
        evidence_count = int(record.get("attempts") or len(record.get("history") or []))
        last_review = float(record.get("last_review_ts", 0)) if evidence_count else 0
        mastery = float(record.get("mastery", 0)) if evidence_count else 0
        decayed = _decayed_mastery(mastery, last_review, now) if evidence_count else 0
        item = {
            **node,
            "mastery": mastery,
            "current_mastery": decayed,
            "last_review_ts": last_review,
            "evidence_count": evidence_count,
            "status": _node_status(decayed, 0) if evidence_count else "unassessed",
        }
        nodes.append(item)
        if evidence_count and mastery >= 70 and decayed < 70:
            review.append({"id": node["id"], "name": node["name"], "current_mastery": decayed})

    assessed_nodes = [node for node in nodes if int(node.get("evidence_count") or 0) > 0]
    avg = round(sum(n["current_mastery"] for n in assessed_nodes) / len(assessed_nodes), 1) if assessed_nodes else 0
    completed = len([n for n in assessed_nodes if n["current_mastery"] >= 80])
    in_progress = len([n for n in assessed_nodes if 50 <= n["current_mastery"] < 80])
    dimensions = _dimension_scores(assessed_nodes)

    return {
        "summary": {
            "average_mastery": avg,
            "completed_nodes": completed,
            "in_progress_nodes": in_progress,
            "total_nodes": len(nodes),
            "assessed_nodes": len(assessed_nodes),
            "progress_percent": round(completed / len(nodes) * 100) if nodes else 0,
        },
        "dimensions": dimensions,
        "nodes": nodes,
        "review_suggestions": review,
        "badges": _badges(student_id),
        "activity": _activity_feed(student_id),
    }


def track_node(student_id: str, node_id: str, score: float, note: str = "") -> dict[str, Any]:
    state = _read_state(student_id)
    node_state = state.setdefault("nodes", {}).setdefault(
        node_id,
        {"mastery": 0, "attempts": 0, "history": []},
    )
    attempts = int(node_state.get("attempts", 0)) + 1
    current = float(node_state.get("mastery", 0))
    score = max(0, min(100, float(score)))
    new_mastery = _update_mastery(current, score, attempts)
    now_ts = time.time()
    history = list(node_state.get("history", []))
    history.append({"score": score, "mastery": new_mastery, "note": note, "ts": now_ts})
    node_state.update(
        {
            "mastery": new_mastery,
            "attempts": attempts,
            "last_review_ts": now_ts,
            "history": history[-12:],
        }
    )
    write_json(_state_file(student_id), state)
    insert_learning_event(student_id, "knowledge_mastery", {"node_id": node_id, "score": score, "mastery": new_mastery})
    return {"node_id": node_id, "mastery": new_mastery, "attempts": attempts}


def track_by_topic(student_id: str, topics: list[str], score: float, note: str = "") -> dict[str, Any] | None:
    """按题目标签/知识点匹配图谱节点再回写掌握度。

    匹配规则：题目标签与概念/章节节点的 `name` 或 `keywords` 有包含关系才算命中。
    命中不了就返回 None —— 宁可不记，也不能把掌握度算到不相干的节点上
    （那才是真正的假数据）。
    """
    probes = [str(item).strip() for item in topics if str(item).strip()]
    if not probes:
        return None
    graph = graph_data(student_id)
    target: dict[str, Any] | None = None
    for node in graph.get("nodes") or []:
        if node.get("kind") not in {"concept", "chapter"}:
            continue
        haystack = [str(node.get("name") or "")] + [str(item) for item in (node.get("keywords") or [])]
        if any(probe and item and (probe in item or item in probe) for probe in probes for item in haystack):
            target = node
            break
    if not target:
        return None
    result = track_node(student_id, node_id=str(target.get("id")), score=score, note=note)
    return {
        "node_id": target.get("id"),
        "node_name": target.get("name"),
        "mastery": result.get("mastery"),
        "attempts": result.get("attempts"),
    }


def _dimension_scores(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = {}
    for node in nodes:
        grouped.setdefault(node["layer"], []).append(float(node["current_mastery"]))
    return [
        {"label": label, "value": round(sum(values) / len(values), 1)}
        for label, values in grouped.items()
    ]


def _badges(student_id: str) -> list[dict[str, Any]]:
    profile = get_latest_profile_snapshot(student_id)
    resources = list_resources(student_id)
    events = get_user_events(student_id)
    usages = get_user_usages(student_id)
    resource_types = {r.get("type") for r in resources if r.get("type")}
    event_types = [e.get("event_type") for e in events]

    rules = [
        ("profile_builder", "画像建档", "完成一次对话式学习画像", bool(profile), 1 if profile else 0, 1),
        ("resource_maker", "资源生产者", "生成至少 3 个个性化资源", len(resources) >= 3, min(len(resources), 3), 3),
        ("multimodal_collector", "多模态收集", "覆盖至少 5 类资源类型", len(resource_types) >= 5, min(len(resource_types), 5), 5),
        ("path_executor", "路径执行者", "生成或更新个性化学习路径", "path_plan" in event_types, event_types.count("path_plan"), 1),
        ("active_questioner", "主动提问者", "完成一次智能辅导提问", "tutor" in event_types, event_types.count("tutor"), 1),
        ("feedback_loop", "反馈闭环", "提交 2 次资源反馈", len(usages) >= 2, min(len(usages), 2), 2),
        ("knowledge_searcher", "知识检索员", "使用课程知识库检索", "knowledge_search" in event_types, event_types.count("knowledge_search"), 1),
        ("reviewer", "复盘达人", "生成学习效果评估报告", "evaluate" in event_types, event_types.count("evaluate"), 1),
    ]
    return [
        {
            "id": rid,
            "name": name,
            "description": desc,
            "earned": earned,
            "progress": progress,
            "target": target,
        }
        for rid, name, desc, earned, progress, target in rules
    ]


def _activity_feed(student_id: str) -> list[dict[str, Any]]:
    events = get_user_events(student_id)
    usages = get_user_usages(student_id)
    resources = list_resources(student_id)
    items: list[dict[str, Any]] = []

    for e in events[-10:]:
        items.append(
            {
                "type": e.get("event_type", "event"),
                "title": _event_title(e.get("event_type", "")),
                "detail": e.get("payload", {}),
                "created_at": e.get("created_at"),
            }
        )
    for u in usages[-6:]:
        items.append(
            {
                "type": "resource_feedback",
                "title": "资源反馈",
                "detail": {"resource_id": u.get("resource_id"), "action": u.get("action")},
                "created_at": u.get("created_at"),
            }
        )
    for r in resources[:5]:
        items.append(
            {
                "type": "resource_created",
                "title": r.get("title", "资源生成"),
                "detail": {"type": r.get("type")},
                "created_at": r.get("created_at"),
            }
        )
    items.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return items[:12]


def _event_title(event_type: str) -> str:
    mapping = {
        "profile_update": "学习画像更新",
        "clarify": "需求澄清",
        "generate": "资源生成",
        "path_plan": "路径规划",
        "push_feedback": "推送反馈",
        "tutor": "智能辅导",
        "evaluate": "效果评估",
        "knowledge_search": "知识库检索",
        "knowledge_mastery": "掌握度更新",
    }
    return mapping.get(event_type, event_type or "学习事件")


def record_search_event(student_id: str, query: str, count: int) -> None:
    insert_learning_event(
        student_id,
        "knowledge_search",
        {"query": query[:120], "result_count": count, "created_at": datetime.now(timezone.utc).isoformat()},
    )
