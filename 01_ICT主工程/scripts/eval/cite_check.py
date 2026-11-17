"""引用出处可核验性检查：对评测集里所有 search_knowledge 用例实跑工具，统计返回片段是否带出处。

判分口径：一个片段算「有出处」当且仅当同时具备
- `title`（来源资源/文档标题）
- `excerpt`（可核对的原文片段）
- 可回溯位置：`path`（源文件）或 `chapter`/`page`/`tags` 之一
三项齐全才算可核验，避免「只给一段裸文本没有下文」被算成引用正确。
同时单独统计「是否有章节/页码级锚点」——当前实现只有 `tags`（首标签＝章节名）与 `path`，
没有独立的 `chapter`/`page` 字段，这一点在报告里如实说明。

用法：
    python scripts/eval/cite_check.py                 # 默认学生 demo
    python scripts/eval/cite_check.py --student demo --limit 3 --out eval-results
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

MAIN = pathlib.Path(__file__).resolve().parents[2]  # 01_主工程
REPO = MAIN.parent
EVAL_SET = pathlib.Path(__file__).with_name("agentarts_eval_set.jsonl")


async def run(student: str, limit: int, out: pathlib.Path) -> dict:
    for p in (str(REPO), str(MAIN)):
        if p not in sys.path:
            sys.path.insert(0, p)
    from mcp_server import server as srv  # noqa: PLC0415

    cases = [json.loads(l) for l in EVAL_SET.read_text(encoding="utf-8").splitlines() if l.strip()]
    cases = [c for c in cases if c["tool"] == "search_knowledge"]
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
        citations = []
        for it in items:
            tags = it.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.strip("[]").replace("'", "").split(",") if t.strip()]
            explicit_anchor = it.get("chapter") or it.get("page") or it.get("section")
            citations.append(
                {
                    "title": it.get("title"),
                    "anchor": explicit_anchor,
                    "tag_anchor": tags[0] if tags else None,
                    "score": it.get("score"),
                    "has_excerpt": bool(it.get("excerpt") or it.get("text") or it.get("snippet")),
                    "path": it.get("path"),
                }
            )
        verified = bool(citations) and all(
            c["title"] and c["has_excerpt"] and (c["path"] or c["anchor"] or c["tag_anchor"]) for c in citations
        )
        rows.append(
            {
                "id": case["id"],
                "query": case["prompt"],
                "expect": case.get("expect"),
                "hits": len(citations),
                "verifiable": verified,
                "citations": citations,
            }
        )
        print(f"{case['id']} hits={len(citations)} verifiable={verified}", flush=True)

    total = len(rows)
    ok = sum(1 for r in rows if r["verifiable"])
    all_cites = [c for r in rows for c in r["citations"]]
    summary = {
        "cases": total,
        "verifiable": ok,
        "ratio": round(ok / total, 4) if total else 0,
        "empty": sum(1 for r in rows if r["hits"] == 0),
        "citations": len(all_cites),
        "with_explicit_chapter_anchor": sum(1 for c in all_cites if c["anchor"]),
        "with_path": sum(1 for c in all_cites if c["path"]),
        "with_title": sum(1 for c in all_cites if c["title"]),
        "with_excerpt": sum(1 for c in all_cites if c["has_excerpt"]),
        "student": student,
        "rows": rows,
    }
    out.mkdir(parents=True, exist_ok=True)
    target = out / "cite_check.json"
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, ensure_ascii=False))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--student", default="demo")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="eval-results")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    if not out.is_absolute():
        out = MAIN / out
    asyncio.run(run(args.student, args.limit, out))


if __name__ == "__main__":
    main()
