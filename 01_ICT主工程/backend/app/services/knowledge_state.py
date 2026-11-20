from __future__ import annotations

from pathlib import Path
from typing import Any
import math

from app.repo import get_knowledge_state
from app.repo import save_knowledge_state

"""掌握度状态文件的读写与衰减/更新公式：图谱与掌握度模块共用。"""

def _read_state(student_id: str) -> dict[str, Any]:
    """掌握度状态统一走仓储层：JSON 模式读 knowledge_state.json，SQLite 模式读 knowledge_state 表。"""
    state = get_knowledge_state(student_id)
    return state if isinstance(state, dict) else {"nodes": {}}


def _write_state(student_id: str, state: dict[str, Any]) -> None:
    save_knowledge_state(student_id, state)


def _infer_node_mastery(node: dict[str, Any], resources: list[dict[str, Any]], weak_text: str, idx: int) -> float:
    base = 48 - idx * 2
    if any(k in weak_text for k in node["keywords"]):
        base -= 12
    for r in resources:
        text = " ".join([str(r.get("title", "")), " ".join(map(str, r.get("tags", []))), str(r.get("type", ""))])
        if any(k in text for k in node["keywords"]):
            base += 10
    return max(20, min(78, base))


def _decayed_mastery(mastery: float, last_review_ts: float, now_ts: float) -> float:
    days = max(0.0, (now_ts - last_review_ts) / 86400)
    return round(max(10, mastery * math.exp(-0.08 * days)), 1)


def _update_mastery(current: float, score: float, attempt: int) -> float:
    factor = 1.0 / (1 + 0.18 * max(0, attempt - 1))
    if score >= current:
        value = current * 0.35 + score * 0.65 * factor
    else:
        value = current * 0.78 + score * 0.22
    return round(max(0, min(100, value)), 1)
