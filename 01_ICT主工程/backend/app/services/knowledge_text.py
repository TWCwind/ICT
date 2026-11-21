from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
import hashlib
import json
import math
import re
import zipfile

from app.services.knowledge_data import GRAPH_CONCEPT_SUFFIXES
from app.services.knowledge_data import GRAPH_COURSE_CONCEPT_HINTS
from app.services.knowledge_data import GRAPH_DOMAIN_CONCEPTS
from app.services.knowledge_data import GRAPH_DOMAIN_CONCEPT_SET
from app.services.knowledge_data import GRAPH_GENERIC_TERMS
from app.services.knowledge_data import GRAPH_KEYWORD_NOISE_MARKERS

"""通用文本与文件工具：读取课程材料、分词、余弦相似度、片段摘取、关键字清洗。"""

def _semantic_course_title(raw_title: str, evidence: str = "") -> str:
    """Return a human-facing course title instead of an internal file key."""
    title = re.sub(r"[_\-]+", " ", str(raw_title or "")).strip()
    title = re.sub(r"\s+", " ", title)
    if title and not _is_stale_chapter_title(title):
        return title[:80]
    evidence_lower = str(evidence or "").lower()
    matches = [term for term in GRAPH_DOMAIN_CONCEPTS if term.lower() in evidence_lower]
    if matches:
        return f"{matches[0]}综合课程"
    return "课程知识结构"


def _matched_course_domain_concepts(title: str) -> tuple[str, ...]:
    title_lower = str(title or "").lower()
    selected: list[str] = []
    for hints, concepts in GRAPH_COURSE_CONCEPT_HINTS:
        if any(hint in title_lower for hint in hints):
            selected.extend(concepts)
    return tuple(dict.fromkeys(selected))


def _chapter_display_title(chapter: dict[str, Any]) -> str:
    original = re.sub(r"\s+", " ", str(chapter.get("chapter_title", ""))).strip()
    first_line = str(chapter.get("summary", "")).splitlines()[0].strip()
    first_line = re.sub(r"[\t ]+\d+\s*$", "", first_line)
    first_line = re.sub(r"\s+", " ", first_line).strip()
    if re.match(r"第\s*\d+\s*章", first_line) and len(first_line) <= 80:
        return first_line
    return original


def _is_stale_chapter_title(title: str) -> bool:
    normalized = re.sub(r"\s+", "", str(title or "")).lower()
    return bool(
        not normalized
        or re.search(r"(?:book_|textbook_|第1部分|第01部分|视频推荐|b站|腾讯视频)", normalized, re.I)
        or re.fullmatch(r"[0-9a-f]{16,32}", normalized)
    )


def _clean_keywords(values: list[Any], title: str = "") -> list[str]:
    output: list[str] = []
    for value in values:
        term = re.sub(r"\s+", " ", str(value)).strip(" -_、，。:：")
        if not _is_graph_keyword_candidate(term, title):
            continue
        if term not in output:
            output.append(term)
    return output


def _clean_course_keywords(values: list[Any], title: str) -> list[str]:
    cleaned = _clean_keywords(values, title)
    course_concepts = _matched_course_domain_concepts(title)
    if not course_concepts:
        return cleaned
    allowed = {item.lower() for item in course_concepts}
    return [item for item in cleaned if item.lower() in allowed]


def _is_graph_keyword_candidate(term: str, title: str = "") -> bool:
    normalized = re.sub(r"\s+", " ", str(term or "")).strip(" -_、，。:：")
    lowered = normalized.lower()
    if len(normalized) < 2 or len(normalized) > 18 or normalized.isdigit():
        return False
    if lowered in GRAPH_GENERIC_TERMS or any(marker in lowered for marker in GRAPH_KEYWORD_NOISE_MARKERS):
        return False
    if any(char.isdigit() for char in normalized) and not re.search(r"[A-Za-z]", normalized):
        return False
    if re.search(r"(?:了|着|过|丰富|扎实|目前|所示)$", normalized):
        return False
    if lowered in GRAPH_DOMAIN_CONCEPT_SET:
        return True
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9+#. /-]*", normalized):
        return False
    return bool(re.search(r"[\u4e00-\u9fff]{2,}", normalized)) and normalized.endswith(GRAPH_CONCEPT_SUFFIXES)


def _clean_summary(text: str, limit: int) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return clean[:limit] + ("…" if len(clean) > limit else "")


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}:{hashlib.sha1(value.encode('utf-8')).hexdigest()[:12]}"


def _read_json_file(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _read_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return _read_text_cached(str(path), path.stat().st_mtime)
    except Exception:
        return ""


def _read_text_cached(path_str: str, mtime: float) -> str:
    path = Path(path_str)
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _read_docx(path)
    if suffix in {".md", ".txt", ".json"}:
        for enc in ("utf-8", "gbk", "gb2312"):
            try:
                return path.read_text(encoding=enc)[:12000]
            except UnicodeDecodeError:
                continue
    if suffix == ".pdf":
        return _read_pdf(path)
    return ""


def _read_pdf(path: Path) -> str:
    """读取 PDF 全文用于知识检索（教材上传路径的统一文本读取入口）。

    与上传链路不同：这里不做页偏移，只取可检索文本；空页跳过，
    读取失败返回空串由调用方降级（回退章节关键字文本）。
    """
    try:
        import fitz  # PyMuPDF

        document = fitz.open(path)
        parts = [page.get_text("text").strip() for page in document]
        document.close()
        return "\n\n".join(part for part in parts if part)
    except Exception:
        return ""


def _read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    texts = [node.text for node in root.iter() if node.tag.endswith("}t") and node.text]
    # Converted textbooks often spend the first several thousand characters
    # on publishing metadata.  A larger bounded sample reaches real chapter
    # content while keeping graph construction predictable.
    return "\n".join(texts)[:240000]


def _tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    raw = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", text)
    tokens: list[str] = []
    for item in raw:
        if re.fullmatch(r"[\u4e00-\u9fff]+", item):
            if len(item) <= 8:
                tokens.append(item)
            tokens.extend(item[i : i + 2] for i in range(max(0, len(item) - 1)))
        else:
            tokens.append(item)
    return [t for t in tokens if len(t) >= 2]


def _cosine(a: Counter, b: Counter) -> float:
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[k] * b[k] for k in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def _excerpt(text: str, q_tokens: list[str]) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return ""
    positions = [clean.find(t) for t in q_tokens if clean.find(t) >= 0]
    pos = min(positions) if positions else 0
    start = max(0, pos - 90)
    end = min(len(clean), pos + 260)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(clean) else ""
    return prefix + clean[start:end] + suffix


def _guess_tags(text: str) -> list[str]:
    candidates = [
        "需求分析",
        "用例建模",
        "非功能需求",
        "软件工程",
        "Python",
        "机器学习",
        "数据结构",
        "操作系统",
        "数据库",
        "Web前端",
        "嵌入式",
        "区块链",
    ]
    tags = [c for c in candidates if c.lower() in text.lower()]
    return tags[:5]


def _node_status(mastery: float, idx: int) -> str:
    if mastery >= 80:
        return "completed"
    if mastery >= 55:
        return "in_progress"
    if idx <= 2 or mastery >= 40:
        return "available"
    return "locked"
