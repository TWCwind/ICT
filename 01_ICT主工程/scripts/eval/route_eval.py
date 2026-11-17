"""50 条评测集的工具路由判分（真实模型，temperature=0，可复算，不依赖云端 IAM）。

背景：`run_eval.py` 只做静态交叉校验并明确声明「live 模式不在本脚本内实现」，
因此评测集里 50 条用例的「模型是否选对工具」一直没有量化结论。
本脚本补上这一层：把 `agentarts_eval_set.jsonl` 的每条 prompt 喂给配置好的
OpenAI 兼容模型（默认读 `backend/.env` 的 LLM_* 配置），拿到它实际调用的工具名，
与用例标注的 `tool` 字段比对，统计单步命中率与执行计划覆盖率。

判分口径（写进报告时必须照抄，避免过度声明）：
- **单步 Top-1 命中**：只给一轮，禁止多步，模型第一个 tool_call 是否等于 expect.tool。
  这是最严格的口径，写类工具（submit_exercise_answer / add_learning_branch）
  天然吃亏，因为真实 ReAct 里必须先读再写。
- **执行计划覆盖**：让模型列出 1~3 步的工具执行序列，expect.tool 是否出现在序列里。
  这一项衡量「模型是否知道该用哪个工具」，而不是「第一步就猜中」。
- 两者都只是**路由层**指标；答案正确性、引用适当性另由 `cite_check.py` 与平台评估覆盖。

用法：
    python scripts/eval/route_eval.py                 # 全量 50 条
    python scripts/eval/route_eval.py --limit 5       # 抽查
    python scripts/eval/route_eval.py --out results   # 指定输出目录（相对 01_主工程）

输出：<out>/route_eval_<日期>.jsonl（逐条明细）、`.summary.json`、`.md`（汇总表）。
脚本不打印任何密钥；只读 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL / LLM_CHAT_PATH 等公开配置项。
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import os
import pathlib
import re
import sys
import time

MAIN = pathlib.Path(__file__).resolve().parents[2]  # 01_主工程
REPO = MAIN.parent
EVAL_SET = pathlib.Path(__file__).with_name("agentarts_eval_set.jsonl")
MCP_SERVER = REPO / "mcp_server" / "server.py"


def load_llm() -> tuple[str, dict[str, str], str]:
    from dotenv import load_dotenv  # noqa: PLC0415

    env_file = MAIN / "backend" / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)
    base = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "")
    chat_path = os.environ.get("LLM_CHAT_PATH") or "/v1/chat/completions"
    header = os.environ.get("LLM_AUTH_HEADER") or "Authorization"
    prefix = os.environ.get("LLM_AUTH_PREFIX") or ""
    if not (base and key and model):
        raise SystemExit("缺少 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL，无法复算")
    url = base if base.endswith("/chat/completions") else base + (chat_path if chat_path.startswith("/") else "/" + chat_path)
    # 与 backend/app/llm/openai_compatible.py 的 _headers() 一致：prefix 末尾无空格时补一个分隔空格，
    # 否则会拼成 "Bearersk-..." 被服务端判成 401。
    sep = " " if prefix and not prefix.endswith(" ") else ""
    return url, {header: f"{prefix}{sep}{key}", "Content-Type": "application/json"}, model


def parse_tools() -> list[dict]:
    """优先用 FastMCP 自己的 tools/list（与线上一致），失败再退回 ast 解析。"""
    try:
        for p in (str(REPO), str(MAIN)):
            if p not in sys.path:
                sys.path.insert(0, p)
        from mcp_server.server import mcp  # noqa: PLC0415

        listed = asyncio.run(mcp.list_tools())
        tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": (t.description or "")[:800],
                    "parameters": getattr(t, "inputSchema", None) or {"type": "object", "properties": {}},
                },
            }
            for t in listed
        ]
        if tools:
            return tools
    except Exception as exc:  # noqa: BLE001
        print(f"[提示] FastMCP 不可用（{type(exc).__name__}），改用源码解析工具名与参数")

    tree = ast.parse(MCP_SERVER.read_text(encoding="utf-8"))
    tools = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if not any("mcp.tool" in ast.unparse(d) for d in node.decorator_list):
            continue
        doc = (ast.get_docstring(node) or "").strip().split("\n\n")[0]
        props = {a.arg: {"type": "string"} for a in node.args.args if a.arg not in ("self", "cls")}
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": node.name,
                    "description": doc[:800],
                    "parameters": {"type": "object", "properties": props, "required": list(props)},
                },
            }
        )
    return tools


SYSTEM = "你是工具路由器。根据用户问题，从给定工具里选择唯一最合适的一个并调用它。只能调用一个工具；不要输出解释文字。"
PLAN_SYSTEM = (
    "你是工具规划器。按执行顺序列出你会调用的工具名（只写工具名，来自给定列表，最多 3 个）。"
    "只输出 JSON 数组，例如 [\"get_student_profile\",\"get_role_competency\"]。"
)


def pick_tool(client, url, headers, model, tools, case) -> dict:
    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": 200,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": case["prompt"]},
        ],
        "tools": tools,
        "tool_choice": "auto",
    }
    t0 = time.time()
    resp = client.post(url, headers=headers, json=body)
    ms = int((time.time() - t0) * 1000)
    if resp.status_code != 200:
        return {"chosen": None, "ms": ms, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    msg = ((resp.json().get("choices") or [{}])[0].get("message")) or {}
    calls = msg.get("tool_calls") or []
    if calls:
        fn = calls[0].get("function") or {}
        return {"chosen": fn.get("name"), "args": fn.get("arguments"), "ms": ms}
    text = msg.get("content") or ""
    for t in tools:
        if t["function"]["name"] in text:
            return {"chosen": t["function"]["name"], "ms": ms, "raw": text[:200]}
    return {"chosen": None, "ms": ms, "error": "no_tool_call"}


def plan_tools(client, url, headers, model, tools, case) -> list[str]:
    names = [t["function"]["name"] for t in tools]
    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": 200,
        "messages": [
            {"role": "system", "content": PLAN_SYSTEM + " 可用工具：" + "、".join(names)},
            {"role": "user", "content": case["prompt"]},
        ],
    }
    resp = client.post(url, headers=headers, json=body)
    if resp.status_code != 200:
        return []
    text = ((resp.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    found = re.search(r"\[[^\]]*\]", text)
    if not found:
        return [n for n in names if n in text][:3]
    try:
        return [p for p in json.loads(found.group(0)) if isinstance(p, str)]
    except json.JSONDecodeError:
        return [n for n in names if n in found.group(0)][:3]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="eval-results", help="输出目录（相对 01_主工程）")
    args = ap.parse_args()

    import httpx  # noqa: PLC0415

    url, headers, model = load_llm()
    tools = parse_tools()
    cases = [json.loads(l) for l in EVAL_SET.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        cases = cases[: args.limit]

    out_dir = pathlib.Path(args.out)
    if not out_dir.is_absolute():
        out_dir = MAIN / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d")
    detail = out_dir / f"route_eval_{stamp}.jsonl"

    rows = []
    with httpx.Client(timeout=120.0) as client, detail.open("w", encoding="utf-8") as fh:
        for i, case in enumerate(cases, 1):
            try:
                res = pick_tool(client, url, headers, model, tools, case)
            except Exception as exc:  # noqa: BLE001
                res = {"chosen": None, "ms": 0, "error": f"{type(exc).__name__}: {exc}"[:200]}
            try:
                plan = plan_tools(client, url, headers, model, tools, case)
            except Exception:  # noqa: BLE001
                plan = []
            required = case.get("required_tools") or [case["tool"]]
            row = {
                "id": case["id"],
                "scene": case["scene"],
                "prompt": case["prompt"],
                "expect_tool": case["tool"],
                "expect": case.get("expect"),
                "required_tools": required,
                "chosen_tool": res.get("chosen"),
                "hit": res.get("chosen") == case["tool"],
                "plan": plan,
                "plan_hit": case["tool"] in plan,
                # 评测集用 required_tools 标注「多工具协作」用例（首个元素等于 tool）。
                # 计划里必须覆盖全部必选工具才算这条多工具用例可执行。
                "req_hit": all(t in plan for t in required),
                "ms": res.get("ms"),
                "error": res.get("error"),
                "args": res.get("args"),
            }
            rows.append(row)
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            print(
                f"[{i}/{len(cases)}] {case['id']} expect={case['tool']} got={res.get('chosen')} "
                f"top1={row['hit']} plan={row['plan_hit']} required={row['req_hit']} {res.get('ms')}ms",
                flush=True,
            )

    total = len(rows)
    hit = sum(r["hit"] for r in rows)
    plan_hit = sum(r["plan_hit"] for r in rows)
    multi = [r for r in rows if len(r["required_tools"]) > 1]
    req_hit = sum(r["req_hit"] for r in multi)
    by_tool: dict[str, dict[str, int]] = {}
    for r in rows:
        b = by_tool.setdefault(r["expect_tool"], {"n": 0, "hit": 0, "plan_hit": 0})
        b["n"] += 1
        b["hit"] += int(r["hit"])
        b["plan_hit"] += int(r["plan_hit"])
    summary = {
        "cases": total,
        "top1_hit": hit,
        "top1_accuracy": round(hit / total, 4) if total else 0,
        "plan_hit": plan_hit,
        "plan_accuracy": round(plan_hit / total, 4) if total else 0,
        "errors": sum(1 for r in rows if r["error"]),
        "avg_ms": int(sum(r["ms"] or 0 for r in rows) / total) if total else 0,
        "multi_tool_cases": len(multi),
        "multi_tool_plan_hit": req_hit,
        "multi_tool_plan_accuracy": round(req_hit / len(multi), 4) if multi else 0,
        "by_tool": by_tool,
        "model": model,
        "measured_at": time.strftime("%Y-%m-%d %H:%M"),
    }
    (out_dir / f"route_eval_{stamp}.summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# 50 条评测集 · 工具路由判分（真实模型，temperature=0）",
        "",
        f"- 测于 {summary['measured_at']}，模型 `{model}`，工具集为 FastMCP `tools/list` 导出的 {len(tools)} 个工具",
        f"- 单步 Top-1 **{hit}/{total}（{summary['top1_accuracy'] * 100:.1f}%）**；"
        f"执行计划覆盖 **{plan_hit}/{total}（{summary['plan_accuracy'] * 100:.1f}%）**；"
        f"多工具用例（`required_tools` >1）的计划全覆盖 **{req_hit}/{len(multi)}**；"
        f"异常 {summary['errors']} 条；平均 {summary['avg_ms']}ms/条",
        "",
        "| 期望工具 | 用例数 | 单步命中 | 计划覆盖 |",
        "| --- | --- | --- | --- |",
    ]
    for name, stat in sorted(by_tool.items(), key=lambda kv: -kv[1]["n"]):
        lines.append(f"| `{name}` | {stat['n']} | {stat['hit']}/{stat['n']} | {stat['plan_hit']}/{stat['n']} |")
    miss = [r for r in rows if not r["plan_hit"]]
    if miss:
        lines += ["", "## 计划未覆盖明细", "", "| id | prompt | 期望 | 计划 |", "| --- | --- | --- | --- |"]
        for r in miss:
            lines.append(f"| {r['id']} | {r['prompt']} | `{r['expect_tool']}` | {r['plan'] or r['error']} |")
    (out_dir / f"route_eval_{stamp}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n明细：{detail}\n汇总：{out_dir / f'route_eval_{stamp}.md'}")


if __name__ == "__main__":
    main()
