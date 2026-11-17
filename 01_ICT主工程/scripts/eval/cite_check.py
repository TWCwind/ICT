"""Verify retrieval excerpts against readable local sources and chapter ranges."""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import tempfile

MAIN = pathlib.Path(__file__).resolve().parents[2]
REPO = MAIN.parent
EVAL_SET = pathlib.Path(__file__).with_name("agentarts_eval_set.jsonl")


def check_citation(item: dict, read_text, roots: list[pathlib.Path], metadata_dir: pathlib.Path) -> dict:
    excerpt = item.get("excerpt") or item.get("text") or item.get("snippet")
    path = item.get("path")
    chapter = item.get("chapter")
    result = {"title": item.get("title"), "path": path, "chapter": chapter,
              "chapter_index": item.get("chapter_index"), "source_type": item.get("source_type") or "unknown",
              "excerpt": excerpt, "metadata_complete": bool(item.get("title") and excerpt and path),
              "source_verified": False, "chapter_verified": False, "reason": ""}
    if not result["metadata_complete"]:
        result["reason"] = "missing_title_excerpt_or_path"
        return result
    source = pathlib.Path(path).resolve()
    if not any(source.is_relative_to(root.resolve()) for root in roots):
        result["reason"] = "source_outside_allowed_roots"
        return result
    if source.suffix.lower() not in {".md", ".txt", ".json", ".docx"} or not source.is_file():
        result["reason"] = "source_missing_or_non_text"
        return result
    body = read_text(source)
    if not body:
        result["reason"] = "source_unreadable"
        return result
    normalize = lambda value: "".join(str(value).split())
    quoted = str(excerpt).removeprefix("...").removesuffix("...")
    if normalize(quoted) not in normalize(body):
        result["reason"] = "excerpt_not_in_source"
        return result
    result["source_verified"] = True
    if chapter:
        from app.services.knowledge_hub import _chapter_documents
        textbook_id = str(item.get("id", "")).split(":", 1)[-1].split("#", 1)[0]
        metadata = metadata_dir / f"book_{textbook_id}.json"
        if not metadata.is_file():
            result["reason"] = "chapter_metadata_missing"
            return result
        try:
            payload = json.loads(metadata.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            result["reason"] = "chapter_metadata_unreadable"
            return result
        chapters = _chapter_documents(textbook_id, str(item.get("title")), body, payload, source)
        match = next((c for c in chapters if c["chapter"] == chapter and c["chapter_index"] == item.get("chapter_index")), None)
        if match is None or normalize(quoted) not in normalize(match["text"]):
            result["reason"] = "excerpt_not_in_claimed_chapter"
            return result
        result["chapter_verified"] = True
    result["reason"] = "verified"
    return result


async def run(student: str, limit: int, out: pathlib.Path) -> dict:
    for p in (str(REPO), str(MAIN), str(MAIN / "backend")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from app.core.config import settings
    from app.services.knowledge_hub import _read_text, _chapter_knowledge_dir
    from mcp_server import server as srv

    cases = [json.loads(line) for line in EVAL_SET.read_text(encoding="utf-8").splitlines() if line.strip()]
    cases = [case for case in cases if case["tool"] == "search_knowledge"]
    if limit:
        cases = cases[:limit]
    rows = []
    for case in cases:
        raw = srv.search_knowledge(student_id=student, query=case["prompt"], limit=3)
        if asyncio.iscoroutine(raw):
            raw = await raw
        data = raw if isinstance(raw, dict) else json.loads(raw)
        payload = data.get("data") if isinstance(data.get("data"), dict) else data
        items = payload.get("results") or payload.get("items") or []
        citations = [check_citation(item, _read_text, [REPO, settings.data_path], _chapter_knowledge_dir()) for item in items]
        rows.append({"id": case["id"], "hits": len(citations), "citations": citations})
    cites = [c for row in rows for c in row["citations"]]
    kinds = sorted({c["source_type"] for c in cites})
    summary = {"cases": len(rows), "cases_with_hits": sum(bool(r["hits"]) for r in rows),
               "citations": len(cites), "metadata_complete": sum(c["metadata_complete"] for c in cites),
               "source_verified": sum(c["source_verified"] for c in cites),
               "chapter_claims": sum(bool(c["chapter"]) for c in cites),
               "chapter_verified": sum(c["chapter_verified"] for c in cites),
               "by_source_type": {k: {"total": sum(c["source_type"] == k for c in cites), "verified": sum(c["source_type"] == k and c["source_verified"] for c in cites)} for k in kinds},
               "student": student, "rows": rows}
    out.mkdir(parents=True, exist_ok=True)
    (out / "cite_check.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, ensure_ascii=False))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--student", default="demo")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(pathlib.Path(tempfile.gettempdir()) / "ict-cite-check"))
    args = ap.parse_args()
    out = pathlib.Path(args.out).resolve()
    if out.is_relative_to(REPO.resolve()):
        ap.error("--out must be outside the repository")
    asyncio.run(run(args.student, args.limit, out))


if __name__ == "__main__":
    main()
