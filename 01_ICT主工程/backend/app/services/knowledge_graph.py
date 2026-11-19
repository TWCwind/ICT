from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import math
import re

from app.repo import get_latest_profile_snapshot
from app.repo import list_resources

from app.services.knowledge_data import COURSE_DIR
from app.services.knowledge_data import GRAPH_DOMAIN_CONCEPTS
from app.services.knowledge_data import GRAPH_DOMAIN_CONCEPT_SET
from app.services.knowledge_data import GRAPH_GENERIC_TERMS
from app.services.knowledge_data import GRAPH_KEYWORD_NOISE_MARKERS
from app.services.knowledge_data import _chapter_knowledge_dir
from app.services.knowledge_state import _read_state
from app.services.knowledge_text import _chapter_display_title
from app.services.knowledge_text import _clean_course_keywords
from app.services.knowledge_text import _clean_keywords
from app.services.knowledge_text import _clean_summary
from app.services.knowledge_text import _guess_tags
from app.services.knowledge_text import _is_graph_keyword_candidate
from app.services.knowledge_text import _is_stale_chapter_title
from app.services.knowledge_text import _matched_course_domain_concepts
from app.services.knowledge_text import _node_status
from app.services.knowledge_text import _read_json_file
from app.services.knowledge_text import _read_text
from app.services.knowledge_text import _semantic_course_title
from app.services.knowledge_text import _stable_id

"""知识图谱构建：课程资料 → 章 → 概念 → 节点与边，含概念挑选的各种启发式。"""

def graph_data(
    student_id: str,
    course: str = "",
    source_type: str = "all",
    keyword: str = "",
    max_nodes: int = 56,
) -> dict[str, Any]:
    profile = get_latest_profile_snapshot(student_id) or {}
    weak_text = " ".join(str(x) for x in (profile.get("evidence") or {}).get("weak_points", []))
    weak_text += " " + str(profile.get("mistake_patterns", ""))
    state = _read_state(student_id)
    resources = list_resources(student_id)
    sources = _graph_sources(student_id)
    if not sources:
        return {
            "course": "暂无课程",
            "selected_course": "",
            "courses": [],
            "nodes": [],
            "edges": [],
            "legend": _graph_legend(),
            "stats": {"documents": 0, "chapters": 0, "concepts": 0, "resources": 0, "relations": 0},
        }

    selected = next(
        (item for item in sources if course and course in {item["id"], item["title"]}),
        sources[0],
    )
    selected = _hydrate_graph_source(selected)
    max_nodes = max(12, min(int(max_nodes), 100))
    nodes, edges = _build_course_graph(selected, resources, weak_text, state, source_type, max_nodes)

    normalized_keyword = keyword.strip().lower()
    if normalized_keyword:
        matching = {
            node["id"]
            for node in nodes
            if normalized_keyword in " ".join(
                [node.get("name", ""), node.get("desc", ""), " ".join(node.get("keywords", []))]
            ).lower()
        }
        connected = {
            endpoint
            for edge in edges
            if edge["source"] in matching or edge["target"] in matching
            for endpoint in (edge["source"], edge["target"])
        }
        keep = matching | connected | {selected["id"]}
        nodes = [node for node in nodes if node["id"] in keep]
        edges = [edge for edge in edges if edge["source"] in keep and edge["target"] in keep]

    degree = Counter()
    for edge in edges:
        degree[edge["source"]] += 1
        degree[edge["target"]] += 1
    nodes = [{**node, "relation_count": degree[node["id"]]} for node in nodes]

    chapter_count = len([node for node in nodes if node["kind"] == "chapter"])
    concept_count = len([node for node in nodes if node["kind"] == "concept"])
    return {
        "course": selected["title"],
        "selected_course": selected["id"],
        "course_summary": selected.get("summary", ""),
        "courses": [
            {
                "id": item["id"],
                "title": item["title"],
                "source_type": item["source_type"],
                "chapter_count": len(item.get("chapters", [])),
                "concept_count": sum(len(chapter.get("keywords", [])) for chapter in item.get("chapters", [])),
            }
            for item in sources
        ],
        "nodes": nodes,
        "edges": edges,
        "legend": _graph_legend(),
        "stats": {
            "documents": 1,
            "chapters": chapter_count,
            "concepts": concept_count,
            "resources": len([node for node in nodes if node["kind"] == "resource"]),
            "relations": len(edges),
        },
    }


def _graph_sources(student_id: str) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    chapter_knowledge_dir = _chapter_knowledge_dir()
    index = _read_json_file(chapter_knowledge_dir / "index.json")
    if isinstance(index, dict):
        for textbook_id, metadata in index.items():
            owner = str(metadata.get("student_id") or "") if isinstance(metadata, dict) else ""
            if owner and owner != student_id:
                continue
            payload = _read_json_file(chapter_knowledge_dir / f"book_{textbook_id}.json")
            if not isinstance(payload, dict):
                continue
            title = _semantic_course_title(
                str(payload.get("display_title") or payload.get("core_topic") or Path(str(payload.get("filename") or metadata.get("filename") or textbook_id)).stem),
                " ".join(str(chapter.get("chapter_title", "")) for chapter in payload.get("chapters") or []),
            )
            chapters = _deduplicate_chapters(payload.get("chapters") or [])
            sources.append(
                {
                    "id": f"textbook:{textbook_id}",
                    "title": title,
                    "source_type": "uploaded_textbook",
                    "path": str(chapter_knowledge_dir / f"book_{textbook_id}.json"),
                    "summary": f"由上传教材自动解析，共识别 {len(chapters)} 个章节。",
                    "chapters": chapters,
                }
            )
            seen_titles.add(title)

    for path in sorted(COURSE_DIR.glob("*")) if COURSE_DIR.exists() else []:
        if not path.is_file() or path.stem in seen_titles:
            continue
        sources.append(
            {
                "id": f"course_material:{path.name}",
                "title": _semantic_course_title(path.stem.replace("_", " "), _read_text(path)),
                "source_type": "course_material",
                "path": str(path),
                "summary": "课程资料库中的原始教学文档，选择后按正文内容提取知识模块。",
                "chapters": [],
            }
        )

    # The course selector represents source-of-truth teaching documents only.
    # Generated question banks, lecture notes, practice cases, QA reports,
    # extended readings and path outputs remain available as related resource
    # nodes, but must never be parsed as if they were courses.
    sources.sort(key=lambda item: (0 if item["source_type"] == "uploaded_textbook" else 1, item["title"]))
    return sources


def _hydrate_graph_source(source: dict[str, Any]) -> dict[str, Any]:
    if source.get("chapters"):
        return source
    path = Path(str(source.get("path", "")))
    text = _read_text(path)
    if not text:
        return source
    doc = {
        "id": source["id"],
        "title": source["title"],
        "source_type": source["source_type"],
        "path": source.get("path", ""),
        "text": text,
        "tags": _guess_tags(source["title"] + "\n" + text),
    }
    return {
        **source,
        "summary": _clean_summary(text, 180),
        "chapters": _document_modules(doc),
    }


def _build_course_graph(
    source: dict[str, Any],
    resources: list[dict[str, Any]],
    weak_text: str,
    state: dict[str, Any],
    source_filter: str,
    max_nodes: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    root_id = source["id"]
    nodes: list[dict[str, Any]] = [
        {
            "id": root_id,
            "name": source["title"],
            "kind": "course",
            "layer": "课程",
            "category": "课程中心",
            "difficulty": 1,
            "desc": source.get("summary") or "课程知识结构总览",
            "keywords": [source["title"]],
            "source_title": source["title"],
            "source_type": source["source_type"],
            "source_path": source.get("path", ""),
            "mastery": 0,
            "status": "available",
        }
    ]
    edges: list[dict[str, Any]] = []
    concept_nodes: dict[str, str] = {}
    chapters = source.get("chapters", [])

    if source_filter != "generated":
        available_slots = max_nodes - 1
        chapter_limit = min(len(chapters), max(3, available_slots // 4))
        selected_chapters = chapters[:chapter_limit]
        concept_slots = max(0, available_slots - len(selected_chapters))
        per_chapter = max(2, min(5, concept_slots // max(1, len(selected_chapters))))
        previous_chapter_id = ""
        for chapter_index, chapter in enumerate(selected_chapters):
            chapter_name = str(chapter.get("chapter_title") or f"知识模块 {chapter_index + 1}")
            chapter_id = _stable_id("chapter", f"{root_id}:{chapter_name}")
            # A concept that merely repeats the chapter heading adds a node with
            # nothing new (「七、从用例到可验收的需求」is the chapter itself).
            chapter_heading = re.sub(r"^[一二三四五六七八九十百\d]+[、.．]\s*", "", chapter_name).strip()
            semantic_keywords = [
                term
                for term in _extract_graph_keywords(
                    f"{chapter_name}\n{chapter.get('summary', '')}",
                    source["title"],
                    per_chapter * 2,
                )
                if term != chapter_heading
                and not _looks_like_clause_fragment(term)
                and not _only_in_negative_context(term, f"{chapter_name}\n{chapter.get('summary', '')}")
            ]
            keywords = _clean_course_keywords(semantic_keywords, source["title"])
            # The course-domain vocabulary is a whitelist, so it silently drops
            # concepts the uploaded chapter actually teaches (include / extend /
            # 参与者 for a requirements-modelling course).  Keep the whitelist for
            # statistically mined phrases, but always admit the chapter's own
            # authored keywords.
            for candidate in chapter.get("keywords") or []:
                if candidate in keywords:
                    continue
                if _is_authored_concept(candidate) or _is_graph_keyword_candidate(candidate, source["title"]):
                    keywords.append(candidate)
            keywords = keywords[:per_chapter]
            chapter_node = {
                "id": chapter_id,
                "name": chapter_name,
                "kind": "chapter",
                "layer": "章节与模块",
                "category": "课程章节",
                "difficulty": min(3, 1 + chapter_index // 5),
                "desc": _clean_summary(chapter.get("summary", ""), 220),
                "keywords": keywords,
                "source_title": source["title"],
                "source_type": source["source_type"],
                "source_path": source.get("path", ""),
                "chapter": chapter_name,
            }
            nodes.append(_with_mastery(chapter_node, state, resources, weak_text, chapter_index))
            edges.append({"source": root_id, "target": chapter_id, "label": "包含", "type": "hierarchy"})
            if previous_chapter_id:
                edges.append({"source": previous_chapter_id, "target": chapter_id, "label": "学习顺序", "type": "path"})
            previous_chapter_id = chapter_id

            for keyword_index, concept in enumerate(keywords):
                normalized = concept.lower()
                concept_id = concept_nodes.get(normalized)
                if not concept_id:
                    concept_id = _stable_id("concept", f"{root_id}:{normalized}")
                    concept_nodes[normalized] = concept_id
                    concept_node = {
                        "id": concept_id,
                        "name": concept,
                        "kind": "concept",
                        "layer": "核心知识点",
                        "category": "核心知识点",
                        "difficulty": min(3, 1 + (chapter_index + keyword_index) // 7),
                        "desc": f"“{concept}”是“{chapter_name}”中的核心概念，来源于课程文档关键词与章节内容解析。",
                        "keywords": [concept, chapter_name],
                        "source_title": source["title"],
                        "source_type": source["source_type"],
                        "source_path": source.get("path", ""),
                        "chapter": chapter_name,
                    }
                    nodes.append(_with_mastery(concept_node, state, resources, weak_text, len(nodes)))
                edges.append({"source": chapter_id, "target": concept_id, "label": "关键概念", "type": "knowledge"})

    if source_filter != "course":
        for resource in resources:
            if len(nodes) >= max_nodes:
                break
            resource_text = " ".join(
                [str(resource.get("title", "")), " ".join(map(str, resource.get("tags", []))), str(resource.get("type", ""))]
            )
            related = source_filter == "generated" or source["title"] in resource_text or any(
                concept in resource_text for concept in list(concept_nodes)[:20]
            )
            if not related:
                continue
            resource_id = f"resource:{resource.get('id')}"
            nodes.append(
                {
                    "id": resource_id,
                    "name": resource.get("title") or "个性化学习资源",
                    "kind": "resource",
                    "layer": "学习资源",
                    "category": "个性化资源",
                    "difficulty": 1,
                    "desc": f"由多智能体生成的 {resource.get('type') or '学习'} 资源，可用于巩固本课程知识点。",
                    "keywords": list(map(str, resource.get("tags", [])))[:5],
                    "source_title": resource.get("title") or "生成资源",
                    "source_type": "generated_resource",
                    "source_path": str(resource.get("content_uri", "")),
                    "mastery": 0,
                    "status": "available",
                }
            )
            edges.append({"source": root_id, "target": resource_id, "label": "配套资源", "type": "resource"})

    nodes = nodes[:max_nodes]
    keep_ids = {node["id"] for node in nodes}
    edges = [edge for edge in edges if edge["source"] in keep_ids and edge["target"] in keep_ids]
    child_mastery = [
        float(node["mastery"])
        for node in nodes[1:]
        if node["kind"] != "resource" and int(node.get("evidence_count") or 0) > 0
    ]
    nodes[0]["mastery"] = round(sum(child_mastery) / len(child_mastery), 1) if child_mastery else 0
    nodes[0]["evidence_count"] = sum(int(node.get("evidence_count") or 0) for node in nodes[1:])
    nodes[0]["status"] = _node_status(nodes[0]["mastery"], 0) if child_mastery else "unassessed"
    return nodes, edges


def _with_mastery(
    node: dict[str, Any],
    state: dict[str, Any],
    resources: list[dict[str, Any]],
    weak_text: str,
    index: int,
) -> dict[str, Any]:
    record = state.get("nodes", {}).get(node["id"], {})
    evidence_count = int(record.get("attempts") or len(record.get("history") or []))
    mastery = float(record.get("mastery", 0)) if evidence_count else 0
    return {
        **node,
        "mastery": round(mastery, 1),
        "evidence_count": evidence_count,
        "status": _node_status(mastery, index) if evidence_count else "unassessed",
    }


def _document_modules(doc: dict[str, Any]) -> list[dict[str, Any]]:
    keywords = _extract_graph_keywords(doc.get("text", ""), doc.get("title", ""), 24)
    if not keywords:
        keywords = doc.get("tags", []) or [doc.get("title", "课程概览")]
    module_names = ["基础概念", "核心原理", "方法与技术", "实践与应用"]
    modules: list[dict[str, Any]] = []
    chunk_size = max(3, math.ceil(len(keywords) / len(module_names)))
    for index, name in enumerate(module_names):
        chunk = keywords[index * chunk_size : (index + 1) * chunk_size]
        if not chunk:
            continue
        modules.append(
            {
                "chapter_title": name,
                "chapter_index": index,
                "keywords": chunk,
                "summary": f"从《{doc.get('title', '课程文档')}》正文中提取的{name}知识集合。",
            }
        )
    return modules


def _is_authored_concept(term: str, allow_generic: bool = False) -> bool:
    """Filter for author-emphasised concept names (headings, bold, code spans).

    `_is_graph_keyword_candidate` is tuned for statistically mined phrases and
    rejects both pure Latin words and Chinese terms without a known concept
    suffix, which discarded exactly the terms a lecturer marks as knowledge
    points (include / extend / 参与者 / 泛化).  Keep its noise rules, drop the
    shape rules.
    """
    normalized = re.sub(r"\s+", " ", str(term or "")).strip(" -_、，。:：•")
    if not normalized or len(normalized) > 24:
        return False
    lowered = normalized.lower()
    if lowered in GRAPH_GENERIC_TERMS and not allow_generic:
        return False
    if any(marker in lowered for marker in GRAPH_KEYWORD_NOISE_MARKERS):
        return False
    if re.search(r"(的|了|着|过)$", normalized):
        return False
    if re.search(r"(对比|要点|示例|模板|错误|自测题|参考答案)$", normalized):
        return False
    return bool(re.search(r"[\u4e00-\u9fff]{2,}", normalized) or re.fullmatch(r"[A-Za-z][A-Za-z0-9+#.]{2,}", normalized))


def _looks_like_clause_fragment(term: str) -> bool:
    """Reject verb-phrase fragments that a frequency splitter produces.

    「判冲突、排优先级、划边界、建模型」splits into 建模型, and 「不能留到测试」
    is a whole clause: neither is a knowledge point, while real terms such as
    「遗漏隐性需求」also start with a verb and must survive.
    """

    if not term:
        return False
    if term[0] in "不没别勿":
        return True
    if re.search(r"(?:测试|一下|了|着)$", term):
        return True
    if len(term) <= 6 and re.match(r"^[建排划判做用把让使留去掉]", term) and term not in {"建模", "用例"}:
        return True
    return False


def _only_in_negative_context(term: str, body: str) -> bool:
    """True when every occurrence of the term sits inside a negation.

    「用例不是界面、不是函数、不是步骤」must not turn 界面/函数/步骤 into
    knowledge points: they are counter-examples, and the graph would teach the
    exact opposite of the chapter.
    """

    hits = [match.start() for match in re.finditer(re.escape(term), body)]
    if not hits:
        return False
    negatives = ("不是", "不能", "不要", "不得", "避免", "禁止", "无需", "不必", "而非", "不算")
    for position in hits:
        window = body[max(0, position - 6):position]
        if not any(negative in window for negative in negatives):
            return False
    return True


def _chapter_concept_candidates(body: str, chapter_title: str, limit: int) -> list[str]:
    """Concept names for one chapter, author signals first.

    Frequency alone produced fragments such as「不能留到测试」while missing the
    concepts a lecturer actually emphasised.  Markdown carries the author's own
    emphasis, so prefer, in order: level-3 headings (a sub-section is usually
    one knowledge point), inline code / bold terms, then the statistical
    extractor as fallback.
    """
    candidates: list[str] = []

    # A heading is the strongest author signal available, so it bypasses the
    # generic-term blacklist:「参与者」「用例」are generic words in a random
    # sentence but the actual knowledge points of a UML chapter.
    for heading in re.findall(r"(?m)^\s*#{3,4}\s+([^\n]{2,40})\s*$", body):
        cleaned = re.sub(r"^\s*\d+(?:\.\d+)*\s*", "", heading)
        cleaned = re.sub(r"[（(][^）)]{0,20}[）)]\s*$", "", cleaned).strip()
        if cleaned and _is_authored_concept(cleaned, allow_generic=True):
            candidates.append(cleaned)

    for bold, code in re.findall(r"\*\*([^*\n]{2,24})\*\*|`([^`\n]{2,24})`", body):
        term = (bold or code).strip().strip("：:，,。.")
        # Bold sentences are emphasis, not concept names: a concept name is
        # reused across the chapter, a highlighted claim usually appears once.
        if term and len(term) <= 14 and not re.search(r"[，。；]", term) and (code or body.count(term) >= 2):
            if _is_authored_concept(term):
                candidates.append(term)

    authored: list[str] = []
    for term in candidates:
        normalized = re.sub(r"\s+", " ", term).strip(" -_、，。:：")
        # Candidates already passed their own gate (headings may be generic
        # words), so do not re-apply the strict shape filter here.
        if normalized and normalized not in authored:
            authored.append(normalized)

    # The author's own headings must survive verbatim: the statistical cleaner
    # drops generic-looking words such as「用例」, which are exactly the
    # knowledge points of this kind of chapter.
    merged = list(authored)
    if len(merged) < limit:
        for term in _clean_keywords(_extract_graph_keywords(body, chapter_title, limit), chapter_title):
            if term not in merged:
                merged.append(term)
            if len(merged) >= limit:
                break
    # Authored words still have to be taught positively somewhere in the body.
    return [
        term
        for term in merged
        if not _only_in_negative_context(term, body) and not _looks_like_clause_fragment(term)
    ][:limit]


def _extract_graph_keywords(text: str, title: str, limit: int) -> list[str]:
    content = str(text or "")
    content_lower = content.lower()
    title_lower = title.lower()
    matched_course_concepts = _matched_course_domain_concepts(title)
    course_concepts = matched_course_concepts or GRAPH_DOMAIN_CONCEPTS
    allowed_course_concepts = {item.lower() for item in course_concepts}
    ranked_domain: list[tuple[float, int, str]] = []
    for order, concept in enumerate(course_concepts):
        count = content_lower.count(concept.lower())
        if not count:
            continue
        score = count * 3 + min(len(concept), 12) + (24 if concept.lower() in title_lower else 0)
        ranked_domain.append((-score, order, concept))
    ranked_domain.sort()

    selected = _clean_keywords([item[2] for item in ranked_domain], title)
    if len(selected) >= limit or (matched_course_concepts and len(selected) >= 6):
        return selected[:limit]

    # Fallback for an uploaded course outside the built-in domain vocabulary.
    # It is intentionally conservative: only repeated, concept-shaped phrases
    # may supplement the semantic dictionary.
    phrases = re.split(
        r"[，。；、：:（）()\s]+|(?:以及|并且|或者|包括|包含|通过|用于|属于|作为|和|与|及|是|为|的)",
        content,
    )
    raw = [
        item.strip()
        for item in phrases
        if re.fullmatch(r"[\u4e00-\u9fff]{2,14}|[A-Za-z][A-Za-z0-9+#. -]{1,24}", item.strip())
    ]
    raw.extend(re.findall(r"[A-Za-z][A-Za-z0-9+#.]{1,20}|[\u4e00-\u9fff]{2,12}", content))
    counts = Counter(item.strip() for item in raw if item.strip())
    fallback = [
        term
        for term, count in counts.most_common(320)
        if count >= 2
        and _is_graph_keyword_candidate(term, title)
        and (term.lower() in allowed_course_concepts or term.lower() not in GRAPH_DOMAIN_CONCEPT_SET)
    ]
    return _clean_keywords([*selected, *fallback], title)[:limit]


def _deduplicate_chapters(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    display_titles: dict[str, tuple[int, str]] = {}
    for chapter in chapters:
        display_title = _chapter_display_title(chapter)
        if _is_stale_chapter_title(display_title):
            continue
        title = re.sub(r"\s+", "", display_title).lower()
        if not title:
            continue
        chapter_number = re.match(r"第\s*(\d+)\s*章", display_title)
        key = f"chapter:{int(chapter_number.group(1))}" if chapter_number else title
        current = selected.get(key)
        if current is None or int(chapter.get("char_count", 0)) > int(current.get("char_count", 0)):
            selected[key] = dict(chapter)
        unusual = len(re.findall(r"[^\w\s\u4e00-\u9fffA-Za-z0-9：:（）()、·.+#/-]", display_title))
        incomplete = 1 if re.search(r"(?:的|和|与)$", display_title) else 0
        title_score = min(len(display_title), 72) - unusual * 40 - incomplete * 20
        if key not in display_titles or title_score > display_titles[key][0]:
            display_titles[key] = (title_score, display_title)
    for key, chapter in selected.items():
        chapter["chapter_title"] = display_titles.get(key, (0, str(chapter.get("chapter_title", ""))))[1]
    return sorted(selected.values(), key=lambda item: int(item.get("chapter_index", 0)))


def _graph_legend() -> list[dict[str, str]]:
    return [
        {"category": "课程中心", "label": "当前课程", "color": "#1769e8"},
        {"category": "课程章节", "label": "章节模块", "color": "#18a874"},
        {"category": "核心知识点", "label": "核心知识点", "color": "#7c5ce7"},
        {"category": "个性化资源", "label": "个性化资源", "color": "#f59e0b"},
    ]
