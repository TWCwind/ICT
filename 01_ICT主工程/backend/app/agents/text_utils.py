from __future__ import annotations

from typing import Any, AsyncIterator
import json
import logging
import re

from app.services.keyword_extract import extract_keywords

"""文本与标题工具：质量检查触发词、标题清洗、Markdown 标题/Mermaid 提取、日志器。"""

logger = logging.getLogger(__name__)


def _wants_quality_check(constraints: dict[str, Any]) -> bool:
    """质检报告默认不再自动生成。

    只有显式要求时才跑：constraints.quality_check / quality_review 为真，
    或显式给出 skip_quality_check=False。缺省（不带该键）视为跳过。
    """
    if constraints.get("skip_quality_check"):
        return False
    if constraints.get("quality_check") or constraints.get("quality_review") or constraints.get("run_quality_check"):
        return True
    return constraints.get("skip_quality_check") is False


def _safe_text(s: str) -> str:
    return (s or "").strip()


_SHORT_TYPE_LABELS = {
    "专业课程讲解文档": "讲解文档",
    "知识点思维导图": "思维导图",
    "个性化题库": "题库",
    "拓展阅读材料": "拓展阅读",
    "代码/实操案例": "实操案例",
    "多模态视频/动画脚本": "视频脚本",
}


_TOPIC_BREAK = re.compile(r"[，。；;、,/\n\r\t]+")


def _short_topic(requirement: dict[str, Any]) -> str:
    """从需求里抽一个便于辨认的短主题（<=12 字）。"""
    for key in ("topic", "course"):
        value = _safe_text(str(requirement.get(key) or ""))
        if value:
            return value[:12]
    raw = _safe_text(str(requirement.get("chapter") or requirement.get("raw") or ""))
    if raw:
        first = _TOPIC_BREAK.split(raw)[0].strip() or raw
        return first[:12]
    return ""


def _resource_title(spec_title: str, requirement: dict[str, Any]) -> str:
    """档案袋里的显示名：短主题 + 资源类型，便于区分同类文档。"""
    label = _SHORT_TYPE_LABELS.get(spec_title, spec_title)
    topic = _short_topic(requirement)
    if not topic:
        return label
    return f"{topic} · {label}"[:26]


_TITLE_MD = re.compile(r"[*`#>]+")


_MINDMAP_ROOT = re.compile(r"root\s*[\(\[]+\s*([^\)\]\n]+?)\s*[\)\]]+")


_MINDMAP_PLAIN = re.compile(r"mindmap[ \t]*\r?\n[ \t]*([^\r\n]+)")


_FENCE = re.compile(r"```[A-Za-z]*\s*")


_JUNK_LATIN = {
    "choice",
    "choices",
    "answer",
    "answers",
    "option",
    "options",
    "explanation",
    "correct",
    "true",
    "false",
    "meta",
    "course",
    "chapter",
    "quiz",
    "question",
    "questions",
    "stem",
    "index",
    "type",
    "count",
    "title",
    "json",
    "markdown",
    "mermaid",
    "mindmap",
}


_GENERIC_TITLES = {
    "专业课程讲解文档",
    "知识点思维导图",
    "个性化题库",
    "拓展阅读材料",
    "代码/实操案例",
    "多模态视频/动画脚本",
    "课程讲解文档",
    "讲解文档",
    "思维导图",
    "题库",
    "拓展阅读",
    "实操案例",
    "视频脚本",
}


def _clean_title(text: str) -> str:
    return re.sub(r"\s+", " ", _TITLE_MD.sub("", text or "")).strip()


def _clean_node(text: str) -> str:
    value = _clean_title(text)
    value = re.sub(r"::icon\([^)]*\)", "", value)
    value = re.sub(r"^[A-Za-z0-9_-]+\s*(?=[\(\[\{])", "", value)
    value = re.sub(r"^[\(\[\{]+|[\)\]\}]+$", "", value.strip())
    return value.strip()


def _title_from_content(markdown: str, spec_title: str, requirement: dict[str, Any]) -> str:
    """档案名要能一眼看出内容：正文一级标题 > 结构化元数据 > 导图根节点 > 正文关键词。"""
    label = _SHORT_TYPE_LABELS.get(spec_title, spec_title)
    text = markdown or ""
    topic = _short_topic(requirement)

    for line in text.splitlines()[:40]:
        stripped = line.strip()
        if stripped.startswith("# "):
            heading = _clean_title(stripped[2:])
            if heading and heading not in _GENERIC_TITLES:
                return heading[:26]
            break

    stripped_text = text.lstrip()
    if stripped_text.startswith("{"):
        try:
            payload = json.loads(stripped_text)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
            course = _clean_title(str(meta.get("course") or "")) or topic
            weak = meta.get("weak_points")
            focus = ""
            if isinstance(weak, list) and weak:
                focus = _clean_title(str(weak[0] or ""))
            elif topic and course and topic != course:
                focus = topic
            if course:
                tail = f"{focus} · {label}" if focus else label
                return f"{course} · {tail}"[:26]

    root = _MINDMAP_ROOT.search(text)
    if not root:
        root = _MINDMAP_PLAIN.search(text)
    if root:
        node = _clean_node(root.group(1))
        if node and node not in _GENERIC_TITLES:
            if "导图" in node or node.endswith(label):
                return node[:26]
            return f"{node} · {label}"[:26]

    try:
        plain = _FENCE.sub("\n", text)
        keywords = [
            word
            for word in extract_keywords(plain, limit=6)
            if word not in _GENERIC_TITLES
            and len(word) >= 2
            and word.lower() not in _JUNK_LATIN
        ][:2]
    except Exception:
        keywords = []
    if keywords:
        core = "·".join(keywords)
        topic = _short_topic(requirement)
        if topic and topic not in core:
            return f"{topic} · {core}"[:26]
        return f"{core} · {label}"[:26]

    return _resource_title(spec_title, requirement)
