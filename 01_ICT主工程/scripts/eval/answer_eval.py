"""50 条评测集的「答案级」判分：真跑工具、记录证据、按可核验项自动判分。

与另外两个脚本的分工（写报告时必须照抄，避免过度声明）：

- `run_eval.py`：静态交叉校验（评测集 ↔ 工具清单 ↔ 路径阶段），不调模型、不调云端。
- `route_eval.py`：只判「路由」——模型第一步选哪个工具、计划是否覆盖该工具。
- `run_local_mcp_eval.py`（队友的）：真执行 MCP 工具，统计工具执行成功率。
- **本脚本**：把「工具跑通」推进到「答案能不能验」——模型带工具跑完整一轮，
  把每次工具调用与返回完整落盘，再对最终答案做**可自动核验**的判分：
    1. `route_ok`：第一步工具是否等于用例标注的 `tool`；
    2. `required_ok`：用例 `required_tools`（缺省为 [tool]）是否都被真正调用；
    3. `tools_ok`：本次所有工具调用都没有抛错、返回体没有 `ok: false`；
    4. `grounded_ratio`：答案里引号/书名号内的引用片段，能在本次工具返回体里逐字找到的比例；
    5. `no_fabricated_id`：答案里出现的 id/编号类字符串，是否都能在工具返回体里找到。
- **本脚本不做**的（必须留给人工）：能力诊断、岗位差距、补强建议是否「判断正确」；
  每条用例的参考结论需要有经验的人来写。脚本为每条用例预留 `human_score`（0-2）与
  `human_note` 字段，跑完后由人填写，再回填到报告里。

用法（在 `01_ICT主工程` 下，解释器需能 import `mcp_server` 与 `app`）：

    python scripts/eval/answer_eval.py --list-tools          # CI 用：只校验工具清单与评测集对齐
    python scripts/eval/answer_eval.py --limit 3             # 抽查 3 条
    python scripts/eval/answer_eval.py --out D:/tmp/ans      # 全量 50 条

脚本不打印任何密钥，只读取 `LLM_BASE_URL / LLM_API_KEY / LLM_MODEL / LLM_CHAT_PATH` 等配置项。
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
import traceback

MAIN = pathlib.Path(__file__).resolve().parents[2]  # 01_主工程
REPO = MAIN.parent
BACKEND = MAIN / "backend"
EVAL_SET = pathlib.Path(__file__).with_name("agentarts_eval_set.jsonl")

for _p in (str(BACKEND), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

MAX_STEPS = 4
PROMPT_SYSTEM = (
    "你是「慧思智学」学习平台的助手，可以调用工具查询学生画像、岗位能力、项目进展、"
    "学习资料、练习记录与评估结果。规则：\n"
    "1. 需要事实时先调用工具，不要凭空编造学生数据、岗位要求或资料出处；\n"
    "2. 写类操作（提交答案、新增学习分支）必须先用读类工具拿到真实 id；\n"
    "3. 工具返回为空或查不到时，明确说明「没有查到」，并说明下一步该做什么；\n"
    "4. 回答用中文，先给结论，再给依据；引用资料时写清标题与出处路径。"
)


def load_llm() -> tuple[str, dict[str, str], str]:
    """读 backend/.env 的 LLM 配置；与 backend/app/llm/openai_compatible.py 的拼接规则一致。"""
    from dotenv import load_dotenv

    env_file = BACKEND / ".env"
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
    sep = " " if prefix and not prefix.endswith(" ") else ""
    url = base if base.endswith("/chat/completions") else base + (
        chat_path if chat_path.startswith("/") else "/" + chat_path
    )
    return url, {header: f"{prefix}{sep}{key}", "Content-Type": "application/json"}, model


def load_cases() -> list[dict]:
    cases = []
    for line in EVAL_SET.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def tool_schemas() -> list[dict]:
    """工具 schema 取自注册到 FastMCP 的实例，保证与线上一致（比 ast 猜测可靠）。"""
    import asyncio

    from mcp_server.server import mcp

    out = []
    for tool in asyncio.run(mcp.list_tools()):
        out.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": (tool.description or "").strip()[:600],
                    "parameters": tool.inputSchema or {"type": "object", "properties": {}},
                },
            }
        )
    return out


def call_tool(name: str, arguments: dict) -> dict:
    """直接调用注册在 server 模块上的同名函数（与 MCP 传输层等价，省掉握手）。"""
    from mcp_server import server as server_module

    fn = getattr(server_module, name, None)
    if fn is None:
        return {"ok": False, "error": f"未注册的工具：{name}"}
    try:
        result = fn(**arguments)
        return {"ok": not (isinstance(result, dict) and result.get("ok") is False), "result": result}
    except Exception as exc:  # noqa: BLE001 - 工具异常要落盘而不是中断整轮
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(limit=3),
        }


def chat(client, url: str, headers: dict, model: str, messages: list[dict], tools: list[dict]):
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0,
    }
    resp = client.post(url, headers=headers, json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()


QUOTE_PATTERNS = (re.compile(r"「([^」]{6,})」"), re.compile(r"《([^》]{2,})》"), re.compile(r"“([^”]{6,})”"))
ID_PATTERN = re.compile(r"\b[0-9a-f]{16,}\b")


def judge(case: dict, trace: list[dict], answer: str) -> dict:
    first_tool = trace[0]["name"] if trace else None
    executed = [step["name"] for step in trace]
    required = case.get("required_tools") or [case["tool"]]
    tool_outputs = json.dumps([step.get("output") for step in trace], ensure_ascii=False)

    quotes = []
    for pattern in QUOTE_PATTERNS:
        quotes.extend(pattern.findall(answer or ""))
    grounded = [q for q in quotes if q in tool_outputs] if tool_outputs else []
    ids = ID_PATTERN.findall(answer or "")

    tools_ok = all(step.get("ok") for step in trace) if trace else False
    return {
        "route_ok": first_tool == case["tool"],
        "first_tool": first_tool,
        "expected_tool": case["tool"],
        "expected_called": case["tool"] in executed,
        "required_ok": all(name in executed for name in required),
        "required_tools": required,
        "executed_tools": executed,
        "tool_calls": len(trace),
        "tools_ok": tools_ok,
        "quotes": len(quotes),
        "grounded_quotes": len(grounded),
        "grounded_ratio": (len(grounded) / len(quotes)) if quotes else None,
        "fabricated_ids": [i for i in ids if i not in tool_outputs],
        "answer_chars": len(answer or ""),
        "answered": bool((answer or "").strip()),
    "model_self_score": None,
    "model_self_note": "",
    "human_score": None,
    "human_note": "",
    }


def run_case(client, url, headers, model, tools, case) -> dict:
    messages = [
        {"role": "system", "content": PROMPT_SYSTEM},
        {"role": "user", "content": case["prompt"]},
    ]
    trace: list[dict] = []
    answer = ""
    started = time.time()
    for step in range(MAX_STEPS):
        data = chat(client, url, headers, model, messages, tools)
        message = (data.get("choices") or [{}])[0].get("message") or {}
        calls = message.get("tool_calls") or []
        if not calls:
            answer = (message.get("content") or "").strip()
            break
        messages.append(
            {"role": "assistant", "content": message.get("content") or "", "tool_calls": calls}
        )
        for call in calls:
            fn = call.get("function") or {}
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {"__unparsable__": raw_args}
            outcome = call_tool(fn.get("name", ""), args if isinstance(args, dict) else {})
            trace.append(
                {
                    "name": fn.get("name", ""),
                    "arguments": args,
                    "ok": outcome["ok"],
                    "output": outcome.get("result", outcome.get("error")),
                    "step": step + 1,
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "content": json.dumps(outcome, ensure_ascii=False)[:6000],
                }
            )
    else:
        answer = "(未在步数上限内给出最终回答)"

    result = {
        "id": case["id"],
        "scene": case.get("scene"),
        "prompt": case["prompt"],
        "expect": case.get("expect", ""),
        "elapsed_ms": round((time.time() - started) * 1000),
        "answer": answer,
        "trace": trace,
    }
    result.update(judge(case, trace, answer))
    return result


def summarize(results: list[dict]) -> str:
    total = len(results)
    route = sum(1 for r in results if r["route_ok"])
    called = sum(1 for r in results if r.get("expected_called"))
    required = sum(1 for r in results if r["required_ok"])
    tools_ok = sum(1 for r in results if r["tools_ok"])
    answered = sum(1 for r in results if r["answered"])
    cited = [r for r in results if r["quotes"]]
    grounded = sum(r["grounded_quotes"] for r in cited)
    quotes = sum(r["quotes"] for r in cited)
    fabricated = sum(len(r["fabricated_ids"]) for r in results)
    avg_ms = round(sum(r["elapsed_ms"] for r in results) / total) if total else 0
    lines = [
        "# 50 条评测集：答案级自动判分",
        "",
    ]
    scored = [r for r in results if r.get("model_self_score") is not None]
    if scored:
        full = sum(1 for r in scored if r["model_self_score"] == 2)
        partial = sum(1 for r in scored if r["model_self_score"] == 1)
        zero = sum(1 for r in scored if r["model_self_score"] == 0)
        lines += [
            "评分口径：2=判据要素齐全且有工具依据；1=方向正确或如实说明但要素缺失；0=不满足或臆造。",
            f"模型自评（{len(scored)}/{total} 条，非独立人工评分）：完全满足 {full}、部分 {partial}、不满足 {zero}；"
            f"加权得分 {sum(r['model_self_score'] for r in scored) / (2 * len(scored)):.3f}。",
            "评分者：模型自评（同一 agent 编写 harness 并评分，存在自评偏差，需人工抽检复核）。",
        ]
    else:
        lines += [
            "判分口径见 `scripts/eval/answer_eval.py` 顶部说明；`human_score` 全部留空，",
            "「判断是否正确」需要人工逐条填写，本文不给出该结论。",
        ]
    lines += [
        "",
        f"- 用例数：{total}",
        f"- 首步路由命中：{route}/{total}（最严口径：第一步就要选对）",
        f"- 期望工具被调用到：{called}/{total}（放宽口径：允许先读再做）",
        f"- 必需工具全部调用：{required}/{total}",
        f"- 工具调用均无异常或业务错误：{tools_ok}/{total}",
        f"- 给出最终回答：{answered}/{total}",
        f"- 引用片段可逐字回溯：{grounded}/{quotes}（涉及 {len(cited)} 条用例）",
        f"- 疑似编造 id：{fabricated}",
        f"- 平均耗时：{avg_ms} ms/条",
        "",
        "| 用例 | 场景 | 期望工具 | 首步 | 首步命中 | 工具被调用 | 必需工具 | 引用可回溯 | 模型自评分 | 评分说明 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        ratio = "—" if r["grounded_ratio"] is None else f"{r['grounded_quotes']}/{r['quotes']}"
        score = r.get("model_self_score")
        score_cell = {2: "2 完全满足", 1: "1 部分", 0: "0 不满足"}.get(score, "—")
        note = (r.get("model_self_note") or "").replace("|", "｜")
        lines.append(
            "| {id} | {scene} | {tool} | {first} | {route} | {called} | {req} | {ratio} | {score} | {note} |".format(
                id=r["id"],
                scene=r.get("scene") or "",
                tool=r["expected_tool"],
                first=r["first_tool"] or "—",
                route="✓" if r["route_ok"] else "✗",
                called="✓" if r.get("expected_called") else "✗",
                req="✓" if r["required_ok"] else "✗",
                ratio=ratio,
                score=score_cell,
                note=note,
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条（0 = 全量）")
    parser.add_argument("--out", default="", help="输出目录；缺省写到 01_ICT主工程/scripts/eval/evidence")
    parser.add_argument("--list-tools", action="store_true", help="只校验工具清单与评测集对齐，不调模型")
    parser.add_argument("--render", default="", help="从已有 jsonl 重新渲染 md（不调模型），值为 jsonl 路径")
    args = parser.parse_args()

    if args.render:
        source = pathlib.Path(args.render)
        rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        md = source.with_suffix(".md")
        md.write_text(summarize(rows), encoding="utf-8", newline="\n")
        print(f"已重新渲染：{md}")
        return

    cases = load_cases()
    tools = tool_schemas()
    names = {t["function"]["name"] for t in tools}
    missing = sorted({c["tool"] for c in cases} - names)
    required_missing = sorted(
        {n for c in cases for n in (c.get("required_tools") or []) if n not in names}
    )
    if args.list_tools:
        print(f"cases={len(cases)} tools={len(names)}")
        print("tools:", ", ".join(sorted(names)))
        if missing or required_missing:
            print("缺失：", missing + required_missing)
            raise SystemExit(1)
        print("OK: 评测集引用的工具全部已注册")
        return

    if missing or required_missing:
        raise SystemExit(f"评测集引用了未注册的工具：{missing + required_missing}")

    import httpx

    url, headers, model = load_llm()
    subset = cases[: args.limit] if args.limit else cases
    out_dir = pathlib.Path(args.out) if args.out else EVAL_SET.parent / "evidence" / "answer_eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d")
    jsonl_path = out_dir / f"answer_eval_{stamp}.jsonl"
    md_path = out_dir / f"answer_eval_{stamp}.md"
    summary_path = out_dir / f"answer_eval_{stamp}.summary.json"

    results: list[dict] = []
    with httpx.Client() as client, jsonl_path.open("w", encoding="utf-8", newline="\n") as fh:
        for index, case in enumerate(subset, 1):
            result = run_case(client, url, headers, model, tools, case)
            results.append(result)
            fh.write(json.dumps(result, ensure_ascii=False) + "\n")
            fh.flush()
            print(
                f"[{index}/{len(subset)}] {result['id']} route={'OK' if result['route_ok'] else 'MISS'}"
                f" tools={result['tool_calls']} {result['elapsed_ms']}ms",
                flush=True,
            )

    md_path.write_text(summarize(results), encoding="utf-8", newline="\n")
    summary_path.write_text(
        json.dumps(
            {
                "cases": len(results),
                "route_ok": sum(1 for r in results if r["route_ok"]),
                "required_ok": sum(1 for r in results if r["required_ok"]),
                "tools_ok": sum(1 for r in results if r["tools_ok"]),
                "answered": sum(1 for r in results if r["answered"]),
                "model": model,
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"明细：{jsonl_path}\n汇总：{md_path}")


if __name__ == "__main__":
    main()
