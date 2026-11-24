from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
import hashlib
import re
import zipfile

from app.repo import get_latest_profile_snapshot
from app.repo import get_user_events
from app.repo import get_user_usages
from app.repo import insert_learning_event
from app.repo import list_resources
from app.repo import read_json
from app.repo import write_json

from app.services.knowledge_data import _chapter_knowledge_dir
from app.services.knowledge_data import _textbook_dir
from app.services.knowledge_documents import _collect_documents
from app.services.knowledge_graph import _chapter_concept_candidates
from app.services.knowledge_graph import graph_data
from app.services.knowledge_mastery import _activity_feed
from app.services.knowledge_mastery import mastery_data
from app.services.knowledge_mastery import record_search_event
from app.services.knowledge_mastery import track_by_topic
from app.services.knowledge_mastery import track_node
from app.services.knowledge_text import _cosine
from app.services.knowledge_text import _excerpt
from app.services.knowledge_text import _semantic_course_title
from app.services.knowledge_text import _stable_id
from app.services.knowledge_text import _tokenize

def overview(student_id: str) -> dict[str, Any]:
    docs = _collect_documents(student_id)
    resources = list_resources(student_id)
    events = get_user_events(student_id)
    usages = get_user_usages(student_id)
    profile = get_latest_profile_snapshot(student_id) or {}
    graph = graph_data(student_id)
    mastery = mastery_data(student_id)

    source_types = Counter(d["source_type"] for d in docs)
    return {
        "stats": {
            "course_documents": source_types.get("course_material", 0),
            "generated_resources": len(resources),
            "indexed_chunks": len(docs),
            "knowledge_nodes": len(graph["nodes"]),
            "learning_events": len(events),
            "feedback_records": len(usages),
            "average_mastery": mastery["summary"]["average_mastery"],
        },
        "profile": {
            "id": profile.get("id"),
            "knowledge_base_level": profile.get("knowledge_base_level", "待画像"),
            "cognitive_style": profile.get("cognitive_style", "待画像"),
            "modality_preference": profile.get("modality_preference", "待画像"),
            "mistake_patterns": profile.get("mistake_patterns", "待采集"),
        },
        "pipeline": [
            {"name": "课程资料解析", "status": "ready", "count": source_types.get("course_material", 0)},
            {"name": "生成资源沉淀", "status": "ready", "count": len(resources)},
            {"name": "轻量RAG检索", "status": "ready", "count": len(docs)},
            {"name": "掌握度闭环", "status": "ready", "count": len(mastery["nodes"])},
        ],
        "top_sources": [
            {
                "title": d["title"],
                "source_type": d["source_type"],
                "chars": len(d["text"]),
            }
            for d in docs[:8]
        ],
        "activity": _activity_feed(student_id),
    }


def search_index(student_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
    docs = _collect_documents(student_id)
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    q_counter = Counter(q_tokens)
    results: list[dict[str, Any]] = []
    for doc in docs:
        tokens = doc.get("tokens") or _tokenize(doc["title"] + "\n" + doc["text"])
        if not tokens:
            continue
        token_counter = Counter(tokens)
        common = set(q_counter) & set(token_counter)
        if not common:
            title_hit = any(k in doc["title"] for k in query.split())
            if not title_hit:
                continue
        score = _cosine(q_counter, token_counter)
        title_boost = 0.18 if any(t in _tokenize(doc["title"]) for t in q_tokens) else 0
        source_boost = 0.06 if doc["source_type"] in {"generated_resource", "course_material", "uploaded_textbook"} else 0
        final_score = min(1.0, score + title_boost + source_boost)
        if final_score <= 0.01:
            continue
        results.append(
            {
                "id": doc["id"],
                "title": doc["title"],
                "source_type": doc["source_type"],
                "resource_type": doc.get("resource_type", ""),
                "score": round(final_score, 4),
                "excerpt": _excerpt(doc["text"], q_tokens),
                "path": doc.get("path", ""),
                # 章节锚点：教材按章切分后带上，便于引用落到「第几章」。
                "chapter": doc.get("chapter", ""),
                "chapter_index": doc.get("chapter_index", 0),
                # 页码锚点：PDF 教材带物理页范围；非 PDF 或旧数据为 0（无页码）。
                "page_start": int(doc.get("page_start") or 0),
                "page_end": int(doc.get("page_end") or 0),
                "tags": doc.get("tags", []),
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[: max(1, min(limit, 10))]


def format_references(results: list[dict[str, Any]]) -> str:
    if not results:
        return ""
    parts = ["[知识库检索参考]"]
    for idx, item in enumerate(results[:5], 1):
        chapter = str(item.get("chapter") or "").strip()
        where = f"；章节：第{item.get('chapter_index')}章 {chapter}" if chapter else ""
        page_start = int(item.get("page_start") or 0)
        page_end = int(item.get("page_end") or 0)
        if page_start > 0 and page_end >= page_start:
            page_note = f"（第 {page_start}-{page_end} 页）" if page_end > page_start else f"（第 {page_start} 页）"
            where = f"{where}{page_note}"
        parts.append(f"{idx}. 来源：{item['title']}{where}；匹配度：{item['score']}")
        parts.append(item["excerpt"][:520])
    return "\n".join(parts)


def ingest_textbook(student_id: str, filename: str, content: bytes) -> dict[str, Any]:
    safe_name = Path(filename or "电子教材.txt").name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in {".txt", ".md", ".pdf", ".docx"}:
        raise ValueError("仅支持 TXT、Markdown、PDF 和 Word 电子教材")
    if not content:
        raise ValueError("上传的教材文件为空")
    if len(content) > 30 * 1024 * 1024:
        raise ValueError("教材文件不能超过 30MB")

    text, page_offsets = _extract_textbook_text(content, suffix)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 40:
        raise ValueError("教材中可识别的正文过少，无法生成知识结构")

    textbook_id = hashlib.sha256(content).hexdigest()[:16]
    textbook_dir = _textbook_dir()
    chapter_knowledge_dir = _chapter_knowledge_dir()
    textbook_dir.mkdir(parents=True, exist_ok=True)
    chapter_knowledge_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{textbook_id}{suffix}"
    (textbook_dir / stored_name).write_bytes(content)

    chapters = _build_uploaded_textbook_chapters(
        text, Path(safe_name).stem, page_offsets=page_offsets
    )
    display_title = _semantic_course_title(Path(safe_name).stem, text)
    payload = {
        "textbook_id": textbook_id,
        "filename": safe_name,
        "display_title": display_title,
        "content_hash": textbook_id,
        "core_topic": display_title,
        "chapter_count": len(chapters),
        "total_kp_count": sum(len(item.get("keywords", [])) for item in chapters),
        "chapters": chapters,
        "page_offsets": page_offsets or [],
    }
    write_json(chapter_knowledge_dir / f"book_{textbook_id}.json", payload)
    index_path = chapter_knowledge_dir / "index.json"
    index = read_json(index_path, {})
    if not isinstance(index, dict):
        index = {}
    index[textbook_id] = {"filename": safe_name, "student_id": student_id, "uploaded_at": datetime.now(timezone.utc).isoformat()}
    write_json(index_path, index)
    insert_learning_event(student_id, "textbook_uploaded", {
        "textbook_id": textbook_id,
        "filename": safe_name,
        "chapter_count": len(chapters),
        "concept_count": payload["total_kp_count"],
    })
    return {
        "textbook_id": textbook_id,
        "course_id": f"textbook:{textbook_id}",
        "filename": safe_name,
        "chapter_count": len(chapters),
        "concept_count": payload["total_kp_count"],
    }


def _extract_textbook_text(content: bytes, suffix: str) -> tuple[str, list[int] | None]:
    """提取教材正文；PDF 额外返回每页起始偏移（页码锚点用），其余格式第二项为 None。"""
    if suffix in {".txt", ".md"}:
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return content.decode(encoding), None
            except UnicodeDecodeError:
                continue
        raise ValueError("教材文本编码无法识别")
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                xml = archive.read("word/document.xml")
            root = ET.fromstring(xml)
            paragraphs = []
            for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                line = "".join(node.text or "" for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")).strip()
                if line:
                    paragraphs.append(line)
            return "\n".join(paragraphs), None
        except Exception as exc:
            raise ValueError("Word 教材解析失败，请确认文件未损坏") from exc
    try:
        import fitz
        document = fitz.open(stream=content, filetype="pdf")
        # 每页先做与 ingest_textbook 相同的换行规整，拼接后整本再规整一次成为
        # 幂等空操作——这样记录的页偏移在最终正文坐标系里始终有效。
        raw_pages = [
            re.sub(r"\n{3,}", "\n\n", re.sub(r"\r\n?", "\n", page.get_text("text"))).strip()
            for page in document
        ]
        document.close()
        # 页码锚点：记录每个非空页在拼接正文里的起始偏移。
        # 拼接规则与返回值严格一致（"\n\n".join），偏移即可反查页码。
        page_offsets: list[int] = []
        parts: list[str] = []
        cursor = 0
        for page_no, page in enumerate(raw_pages, 1):
            if not page:
                continue
            page_offsets.append(cursor)
            parts.append(page)
            cursor += len(page) + 2
        return "\n\n".join(parts), (page_offsets or None)
    except Exception as exc:
        raise ValueError("PDF 教材无法提取正文，请使用可复制文字的 PDF") from exc


def _page_of(page_offsets: list[int], pos: int) -> int:
    """字符位置 → 页码（1-based，bisect 右移再 +1）。"""
    import bisect

    return bisect.bisect_right(page_offsets, pos)


def _build_uploaded_textbook_chapters(
    text: str, title: str, page_offsets: list[int] | None = None
) -> list[dict[str, Any]]:
    # Markdown textbooks write chapters as "## 一、需求获取"; the numbering the
    # chapter pattern looks for sits behind the heading markers, so strip
    # level-1/2 markers first.  Deeper headings stay in the body on purpose:
    # treating every "###" as a chapter turns one course into 20 fragments.
    text = re.sub(r"(?m)^\s*#{1,2}\s+", "", text)
    page_count = len(page_offsets) if page_offsets else 0

    def _pages_for_range(start: int, end: int) -> tuple[int, int]:
        """把字符区间映射为页码区间（1-based，闭区间）。"""
        if not page_offsets:
            return (0, 0)
        page_start = _page_of(page_offsets, start)
        page_end = _page_of(page_offsets, max(start, end - 1))
        return (page_start, page_end)

    heading_pattern = re.compile(
        r"(?m)^\s*(第\s*[一二三四五六七八九十百零〇\d]+\s*(?:章|节|篇|部分)\s*[^\n]{0,48}|\d+(?:\.\d+){0,3}\s+[^\n]{2,48}|[一二三四五六七八九十]+[、.]\s*[^\n]{2,48})\s*$"
    )
    matches = list(heading_pattern.finditer(text))[:40]
    sections: list[tuple[str, str]] = []
    sections_pos: list[tuple[int, int]] = []
    if matches:
        for index, match in enumerate(matches):
            # 用 group(1) 的起点而非 match.start()：正则前缀 ^\s* 会把行首空白
            # （含页拼接分隔符的第二个换行）算进匹配，使 start 落到上一页，
            # 页码锚点因此偏小一章。group(1) 才是标题文本的真实起点。
            start = match.start(1)
            end = matches[index + 1].start(1) if index + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if len(body) >= 30:
                sections.append((match.group(1).strip(), body))
                sections_pos.append((start, end))
    if not sections:
        chunk_size = 5000
        fallback_titles = _fallback_chapter_titles(text)
        sections = []
        sections_pos = []
        for index, start in enumerate(range(0, min(len(text), chunk_size * 20), chunk_size)):
            piece = text[start:start + chunk_size]
            if not piece.strip():
                continue
            sections.append(
                (
                    fallback_titles[index] if index < len(fallback_titles) else f"实践应用与复盘·模块 {index + 1}",
                    piece,
                )
            )
            sections_pos.append((start, start + chunk_size))

    chapters = []
    for index, (chapter_title, body) in enumerate(sections):
        # A quiz section is exercise material, not a knowledge point: its option
        # lists ("借书 / 登录 / 选课") would otherwise become graph concepts.
        if re.search(r"自测|练习|习题|测验|作业", chapter_title):
            keywords: list[str] = []
        else:
            keywords = _chapter_concept_candidates(body, chapter_title, 14)
        summary_source = re.sub(r"\s+", " ", body)
        summary = summary_source[:180] + ("…" if len(summary_source) > 180 else "")
        body_start, body_end = sections_pos[index]
        page_start, page_end = _pages_for_range(body_start, body_end)
        chapters.append({
            "chapter_title": chapter_title,
            "chapter_index": index,
            "keywords": keywords,
            "summary": summary,
            "char_count": len(body),
            "page_start": page_start,
            "page_end": page_end,
            "knowledge_points": [
                {"id": _stable_id("textbook-concept", f"{title}:{chapter_title}:{keyword}"), "title": keyword, "keywords": [keyword], "chapter": chapter_title}
                for keyword in keywords
            ],
        })
    return chapters


def _fallback_chapter_titles(text: str) -> list[str]:
    """Provide semantic labels when an uploaded document has no headings."""
    semantic_titles = [
        "学习目标与业务背景",
        "核心概念与术语",
        "方法流程与结构建模",
        "质量约束与风险控制",
        "实践应用与案例验证",
        "综合评估与能力迁移",
    ]
    text_lower = (text or "").lower()
    if "需求" in text_lower and "用例" in text_lower:
        return [
            "业务场景与范围",
            "需求获取与表达",
            "用例与行为建模",
            "领域结构建模",
            "质量与约束",
            "验证与变更",
        ]
    return semantic_titles
