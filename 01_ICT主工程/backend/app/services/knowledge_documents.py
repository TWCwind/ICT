from __future__ import annotations

from pathlib import Path
from typing import Any
import re

from app.core.config import settings
from app.repo import list_resources

from app.services.knowledge_data import COURSE_DIR
from app.services.knowledge_data import PATH_OUTPUT_DIR
from app.services.knowledge_data import SAMPLE_DIR
from app.services.knowledge_data import _chapter_knowledge_dir
from app.services.knowledge_data import _textbook_dir
from app.services.knowledge_text import _guess_tags
from app.services.knowledge_text import _read_json_file
from app.services.knowledge_text import _read_text
from app.services.knowledge_text import _tokenize

"""检索语料收集：把课程材料、教材章节、示例资源、路径输出、已生成资源统一成文档条目。"""

def _collect_documents(student_id: str) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []

    for path in sorted(COURSE_DIR.glob("*")) if COURSE_DIR.exists() else []:
        if not path.is_file():
            continue
        text = _read_text(path)
        if not text:
            continue
        docs.append(_doc_item(path=path, text=text, source_type="course_material"))

    # Uploaded textbooks used to feed the knowledge graph only, so a search for
    # a concept that lives in the textbook body still fell back to generated
    # question banks.  Index the textbook body itself (the original upload when
    # readable, otherwise the parsed chapter keywords) so textbook content is
    # retrievable and outranks derived resources.
    chapter_knowledge_dir = _chapter_knowledge_dir()
    textbook_dir = _textbook_dir()
    textbook_index = _read_json_file(chapter_knowledge_dir / "index.json")
    if isinstance(textbook_index, dict):
        for textbook_id, metadata in textbook_index.items():
            owner = str(metadata.get("student_id") or "") if isinstance(metadata, dict) else ""
            if owner and owner != student_id:
                continue
            filename = str(metadata.get("filename") or textbook_id) if isinstance(metadata, dict) else str(textbook_id)
            stored = textbook_dir / f"{textbook_id}{Path(filename).suffix.lower()}"
            text = _read_text(stored)
            doc_path = stored
            payload = _read_json_file(chapter_knowledge_dir / f"book_{textbook_id}.json")
            # Roadshow/imported metadata may point to a readable original in
            # the data root even when the upload copy is absent. Prefer that
            # original over synthetic keyword text so excerpts are checkable.
            if not text and isinstance(payload, dict) and payload.get("source_document"):
                candidate = (settings.data_path / str(payload["source_document"])).resolve()
                if candidate.is_relative_to(settings.data_path.resolve()):
                    original = _read_text(candidate)
                    if original:
                        text, doc_path = original, candidate
            if not text:
                if not isinstance(payload, dict):
                    continue
                parts: list[str] = []
                for chapter in payload.get("chapters") or []:
                    if not isinstance(chapter, dict):
                        continue
                    for key in ("chapter_title", "title", "name", "summary", "description"):
                        value = str(chapter.get(key) or "").strip()
                        if value:
                            parts.append(value)
                    parts.extend(str(k).strip() for k in chapter.get("keywords") or [] if str(k).strip())
                text = "\n".join(parts)
                doc_path = chapter_knowledge_dir / f"book_{textbook_id}.json"
            if not text:
                continue
            title = Path(filename).stem
            # 按章切分后再入库：这样每条检索结果都带 `chapter` 锚点，
            # 引用能落到「第几章」而不只是一个文件路径。
            chapter_docs = _chapter_documents(
                textbook_id=textbook_id,
                book_title=title,
                text=text,
                payload=payload if doc_path.suffix.lower() != ".json" else None,
                doc_path=doc_path,
            )
            if chapter_docs:
                docs.extend(chapter_docs)
                continue
            docs.append(
                {
                    "id": f"textbook:{textbook_id}",
                    "title": title,
                    "source_type": "uploaded_textbook",
                    "resource_type": "",
                    "path": str(doc_path),
                    "text": text,
                    "chapter": "",
                    "chapter_index": 0,
                    "tags": _guess_tags(title + "\n" + text),
                    "tokens": _tokenize(title + "\n" + text),
                }
            )

    for path in sorted(SAMPLE_DIR.glob("*.md")) if SAMPLE_DIR.exists() else []:
        text = _read_text(path)
        if text:
            docs.append(_doc_item(path=path, text=text, source_type="sample_resource"))

    for path in sorted(PATH_OUTPUT_DIR.glob("*")) if PATH_OUTPUT_DIR.exists() else []:
        if path.suffix.lower() not in {".md", ".json"}:
            continue
        text = _read_text(path)
        if text:
            docs.append(_doc_item(path=path, text=text, source_type="path_output"))

    for resource in list_resources(student_id):
        p = settings.data_path / str(resource.get("content_uri", ""))
        text = _read_text(p)
        if not text:
            continue
        docs.append(
            {
                "id": f"resource:{resource.get('id')}",
                "title": resource.get("title") or p.stem,
                "source_type": "generated_resource",
                "resource_type": resource.get("type", ""),
                "path": str(p),
                "text": text,
                "tags": resource.get("tags", []),
                "tokens": _tokenize((resource.get("title") or "") + "\n" + text),
            }
        )

    return docs


def _chapter_documents(
    textbook_id: str,
    book_title: str,
    text: str,
    payload: Any,
    doc_path: Path,
) -> list[dict[str, Any]]:
    """把教材正文按章切开，每章一个文档，带 `chapter` 锚点。

    只有能在正文里逐一定位到每一章标题时才切分；只要有一章标题定位不到，
    就退回「整本一条文档」，避免切出错误的章节归属。切分后每条结果的
    `path` 仍指向原文件，`chapter`/`chapter_index` 说明这句话出自第几章。
    """

    if not isinstance(payload, dict):
        return []
    chapters = payload.get("chapters") or []
    located: list[dict[str, Any]] = []
    # Only standalone headings can delimit a chapter. A title mentioned in a
    # table of contents or ordinary prose is not a chapter boundary.
    chapter_titles = {str(c.get("chapter_title") or c.get("title") or c.get("name") or "").strip() for c in chapters if isinstance(c, dict)}
    heading_lines = []
    cursor = 0
    for line in text.splitlines(keepends=True):
        clean = line.strip()
        heading = re.sub(r"^#{1,6}\s+", "", clean).strip()
        if heading in chapter_titles and (clean.startswith("#") or clean == heading):
            heading_lines.append((cursor, heading, clean.startswith("#")))
        cursor += len(line)
    previous = -1
    for index, chapter in enumerate(chapters):
        if not isinstance(chapter, dict):
            return []
        title = str(
            chapter.get("chapter_title") or chapter.get("title") or chapter.get("name") or ""
        ).strip()
        if not title:
            return []
        candidates = [(pos, marked) for pos, heading, marked in heading_lines if heading == title and pos > previous]
        # A real chapter has substantive body text before the next heading;
        # TOC entries grouped together do not.
        valid = []
        for candidate, marked in candidates:
            next_heading = min((pos for pos, _, _ in heading_lines if pos > candidate), default=len(text))
            body_start = text.find("\n", candidate) + 1
            if body_start and len(text[body_start:next_heading].strip()) >= 30:
                valid.append((candidate, marked))
        marked = [pos for pos, is_markdown in valid if is_markdown]
        plain = [pos for pos, is_markdown in valid if not is_markdown]
        # Ambiguous duplicate headings must not silently assign a false chapter.
        chosen = marked if marked else plain
        if len(chosen) != 1:
            return []
        position = chosen[0]
        previous = position
        keywords = [str(k).strip() for k in chapter.get("keywords") or [] if str(k).strip()]
        located.append({
            "index": index,
            "title": title,
            "pos": position,
            "keywords": keywords,
            "page_start": int(chapter.get("page_start") or 0),
            "page_end": int(chapter.get("page_end") or 0),
        })
    if len(located) < 2:
        return []

    documents: list[dict[str, Any]] = []
    for offset, item in enumerate(located):
        start = item["pos"]
        end = located[offset + 1]["pos"] if offset + 1 < len(located) else len(text)
        body = text[start:end].strip()
        if len(body) < 30:
            return []
        documents.append(
            {
                "id": f"textbook:{textbook_id}#{item['index']}",
                "title": f"{book_title} · {item['title']}",
                "source_type": "uploaded_textbook",
                "resource_type": "",
                "path": str(doc_path),
                "text": body,
                "chapter": item["title"],
                "chapter_index": item["index"] + 1,
                "page_start": item["page_start"],
                "page_end": item["page_end"],
                "source_start": start,
                "source_end": end,
                "tags": item["keywords"] or _guess_tags(body),
                "tokens": _tokenize(f"{item['title']}\n{body}"),
            }
        )
    return documents if len(documents) >= 2 else []


def _doc_item(path: Path, text: str, source_type: str) -> dict[str, Any]:
    title = path.stem.replace("_", " ")
    return {
        "id": f"{source_type}:{path.name}",
        "title": title,
        "source_type": source_type,
        "resource_type": "",
        "path": str(path),
        "text": text,
        "tags": _guess_tags(title + "\n" + text),
        "tokens": _tokenize(title + "\n" + text),
    }
