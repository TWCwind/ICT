"""三组对照实验：规则流程 / 单 Agent / 多 Agent 九步。

同一批任务、同一份数据（学生 demo、岗位 前端开发工程师），比较：
  耗时、工具调用次数与覆盖、引用可回溯条数、判据命中数、疑似编造 id 数、token（估算）。

用法（backend 目录下用 venv python 跑）：
    python D:/工作区/_runtime/compare_three_arms.py --task T1
    python D:/工作区/_runtime/compare_three_arms.py            # 三条任务全跑
结果落盘 --out（默认 D:/工作区/_runtime/three_arms/）。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(os.environ.get("ARM_ROOT", r"D:/工作区/ICT"))
PROJECT = ROOT if (ROOT / "backend").is_dir() else ROOT / "01_主工程"
BACKEND = PROJECT / "backend"
DATA = Path(os.environ.get("ARM_DATA", r"D:/工作区/_runtime/ict-data"))

for p in (str(ROOT), str(PROJECT), str(BACKEND), str(PROJECT / "backend" / "app" / "agents")):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ["DATA_DIR"] = str(DATA)
os.environ.setdefault("WORKSPACE_DIR", str(PROJECT))

STUDENT = "demo"
ROLE = "前端开发工程师"

TASKS = {
    "T1": {
        "prompt": "demo 现在离目标岗位（前端开发工程师）还差哪些能力？请给出证据与补强建议。",
        "need_tools": ["get_student_profile", "get_role_competency"],
    },
    "T2": {
        "prompt": "demo 这本教材里「需求和用例建模」的关键概念是什么？请引用教材原文片段。",
        "need_tools": ["search_knowledge"],
    },
    "T3": {
        "prompt": "给 demo 出 2 道诊断练习题，并说明选题依据。",
        "need_tools": ["get_exercise_session"],
    },
}


# ---------------------------------------------------------------- 工具调用辅助
def _load_services():
    from mcp_server import services  # noqa: PLC0415

    names = [n for n in dir(services) if n.endswith("_data")]
    return services, {n: getattr(services, n) for n in names}


def _instrument(registry, sink):
    def wrap(name, fn):
        def inner(*a, **kw):
            sink.append(name)
            return fn(*a, **kw)
        return inner
    return {name: wrap(name, fn) for name, fn in registry.items()}


def _call_tool(registry, name, args):
    fn = registry.get(name)
    if fn is None:
        return {"ok": False, "error": {"code": "UNKNOWN_TOOL", "message": name}}
    try:
        return fn(**args)
    except TypeError as exc:
        return {"ok": False, "error": {"code": "BAD_ARGS", "message": str(exc)}}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": {"code": type(exc).__name__, "message": str(exc)}}


def _load_llm_env():
    env_file = Path(r"D:/工作区/ICT/01_主工程/backend/.env")
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if k.startswith("LLM_") and k not in os.environ:
            os.environ[k] = v.strip()


def _pin_data_dir():
    from app.core.config import settings  # noqa: PLC0415
    settings.data_dir = str(DATA)
    return settings


# ---------------------------------------------------------------- 判据与指标
def source_blob() -> str:
    """把学生数据与岗位库拼成可回溯语料，用于校验引用是否真实存在。"""
    parts = []
    user_dir = DATA / "users" / STUDENT
    if user_dir.is_dir():
        for f in user_dir.glob("*.json"):
            try:
                parts.append(f.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
    job_file = PROJECT / "02_服创岗位能力模块" / "岗位图谱子系统" / "structured_job_data.json"
    if job_file.is_file():
        parts.append(job_file.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def citations(text: str, blob: str) -> tuple[int, int]:
    spans = re.findall(r"[「『《]([^」』》]{4,60})[」』》]", text or "")
    ok = sum(1 for s in spans if s in blob)
    return ok, len(spans)


def fabricated_ids(text: str, blob: str) -> int:
    ids = set(re.findall(r"\b[0-9a-f]{16,}\b", text or ""))
    return sum(1 for i in ids if i not in blob)


def checks(task: dict, text: str, tools: list[str], blob: str) -> dict:
    t = text or ""
    out = {
        "引用可回溯": citations(t, blob)[0] > 0,
        "用了必需工具": all(x in tools for x in task["need_tools"]),
        "给出可执行结论": any(k in t for k in ("建议", "补强", "步骤", "练习", "差异")),
        "无编造 id": fabricated_ids(t, blob) == 0,
    }
    return out


# ---------------------------------------------------------------- A 规则流程
def arm_a(task_id: str, task: dict, registry) -> dict:
    from app.agents.role_pipeline import RolePipeline, build_default_registry  # noqa: PLC0415

    calls: list[str] = []
    reg = _instrument(build_default_registry(), calls)
    pipe = RolePipeline(registry=reg)
    t0 = time.perf_counter()
    tools: list[str] = []
    text = ""
    err = None
    try:
        summary = pipe.run(student_id=STUDENT, answer="B", role_name=ROLE)
        text = json.dumps(summary, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"
    tools = list(calls)
    return {
        "arm": "A_规则流程",
        "elapsed_ms": round((time.perf_counter() - t0) * 1000),
        "tool_calls": len(tools),
        "tools": tools,
        "text": text[:4000],
        "error": err,
        "llm_calls": 0,
        "token_est": 0,
    }


# ---------------------------------------------------------------- C 多 Agent
def arm_c(task_id: str, task: dict, registry) -> dict:
    agents_dir = str(PROJECT / "backend" / "app" / "agents")
    if agents_dir not in sys.path:
        sys.path.insert(0, agents_dir)
    from multi_agent import MultiAgentRuntime  # noqa: PLC0415

    rt = MultiAgentRuntime(registry_module="mcp_server.services")
    t0 = time.perf_counter()
    tools: list[str] = []
    text = ""
    err = None
    pids: list[int] = []
    try:
        result = rt.run(student_id=STUDENT, answer="B", role_name=ROLE)
        records = result.get("steps") if isinstance(result, dict) else result
        for rec in records or []:
            d = rec if isinstance(rec, dict) else rec.as_dict()
            tools.append(d.get("tool"))
            if d.get("pid"):
                pids.append(d["pid"])
        text = json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            rt.shutdown()
        except Exception:  # noqa: BLE001
            pass
    return {
        "arm": "C_多Agent九步",
        "elapsed_ms": round((time.perf_counter() - t0) * 1000),
        "tool_calls": len([t for t in tools if t]),
        "tools": [t for t in tools if t],
        "distinct_pids": len(set(pids)),
        "text": text[:4000],
        "error": err,
        "llm_calls": 0,
        "token_est": 0,
    }


# ---------------------------------------------------------------- B 单 Agent
SCHEMA_HINT = (
    "返回对象：{\"thought\": \"简短推理\", \"action\": \"tool_call 或 final\", "
    "\"tool\": \"工具名\", \"args\": {参数对象}, \"answer\": \"最终回答（action=final 时必填）\"}"
)

SYSTEM = f"""你是慧思智学平台的职业能力伴学智能体。可用工具（只这些）：
- get_student_profile(student_id)
- get_role_competency(role_name)
- get_project_status(student_id)
- search_knowledge(query, student_id, limit=5)
- get_exercise_session(student_id, limit=2)
- get_wrong_book(student_id)
- get_learning_evaluation(student_id)
- get_project_status(student_id)
- submit_exercise_answer 与 add_learning_branch 为写操作，本实验不调用。
规则：先调工具拿真实数据，回答里引用返回的 title 与关键数字；数据不足就说「现有数据不支持」。
学生固定为 {STUDENT}。最多 3 步工具调用。"""


async def arm_b(task_id: str, task: dict, registry, blob: str) -> dict:
    from app.llm.router import get_llm_client_for  # noqa: PLC0415

    client = get_llm_client_for("generate")
    tools: list[str] = []
    transcript: list[str] = []
    prompt_chars = 0
    completion_chars = 0
    t0 = time.perf_counter()
    err = None
    answer = ""
    try:
        for step in range(3):
            msgs = [
                {"role": "user", "content": task["prompt"]},
                {"role": "assistant", "content": "\n".join(transcript) or "（尚未调用工具）"},
            ]
            prompt_chars += sum(len(m["content"]) for m in msgs) + len(SYSTEM)
            decision = await client.chat_json(messages=msgs, schema_hint=SCHEMA_HINT, system=SYSTEM)
            completion_chars += len(json.dumps(decision, ensure_ascii=False))
            action = str(decision.get("action") or "").strip()
            if action == "tool_call" and decision.get("tool"):
                name = str(decision["tool"])
                args = decision.get("args") or {}
                if not isinstance(args, dict):
                    args = {}
                args.setdefault("student_id", STUDENT)
                payload = _call_tool(registry, name, args)
                tools.append(name)
                transcript.append(
                    f"第{step+1}步 调用 {name} 参数 {json.dumps(args, ensure_ascii=False)} → "
                    f"{json.dumps(payload, ensure_ascii=False)[:1200]}"
                )
                continue
            answer = str(decision.get("answer") or "")
            break
        if not answer:
            final_msgs = [
                {"role": "user", "content": task["prompt"]},
                {"role": "assistant", "content": "\n".join(transcript)},
                {"role": "user", "content": "基于以上工具返回，直接给出最终回答（不要 JSON）。"},
            ]
            prompt_chars += sum(len(m["content"]) for m in final_msgs)
            answer = await client.chat_text(messages=final_msgs, system=SYSTEM, temperature=0.2)
            completion_chars += len(answer)
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"
    return {
        "arm": "B_单Agent",
        "elapsed_ms": round((time.perf_counter() - t0) * 1000),
        "tool_calls": len(tools),
        "tools": tools,
        "text": (answer + "\n---\n" + "\n".join(transcript))[:4000],
        "answer": answer,
        "error": err,
        "llm_calls": 1 + len(tools),
        "token_est": round((prompt_chars + completion_chars) / 4),
    }


# ---------------------------------------------------------------- 主流程
async def main_async(args) -> int:
    _load_llm_env()
    _pin_data_dir()
    _, registry = _load_services()
    blob = source_blob()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    picked = [args.task] if args.task else list(TASKS)
    all_rows = []
    for task_id in picked:
        task = TASKS[task_id]
        for fn in (lambda: arm_a(task_id, task, registry),
                   None,
                   lambda: arm_c(task_id, task, registry)):
            if fn is None:
                row = await arm_b(task_id, task, registry, blob)
            else:
                try:
                    row = fn()
                except Exception as exc:  # noqa: BLE001
                    row = {"arm": "?", "elapsed_ms": 0, "tool_calls": 0, "tools": [],
                           "text": "", "error": f"{type(exc).__name__}: {exc}",
                           "llm_calls": 0, "token_est": 0,
                           "traceback": traceback.format_exc()[-800:]}
            ok, total = citations(row.get("text", ""), blob)
            row.update({
                "task": task_id,
                "citations_ok": ok,
                "citations_total": total,
                "fabricated_ids": fabricated_ids(row.get("text", ""), blob),
                "checks": checks(task, row.get("text", "") + url_text(row), row.get("tools", []), blob),
            })
            row["checks_passed"] = sum(1 for v in row["checks"].values() if v)
            all_rows.append(row)
            print(f"{task_id} {row['arm']}: {row['elapsed_ms']}ms tools={row['tool_calls']} "
                  f"cite={row['citations_ok']}/{row['citations_total']} "
                  f"checks={row['checks_passed']}/4 err={bool(row.get('error'))}")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (out_dir / f"three_arms_{stamp}.json").write_text(
        json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out_dir / f"three_arms_{stamp}.json")
    return 0


def url_text(row: dict) -> str:
    return json.dumps(row.get("tools", []), ensure_ascii=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="", help="T1/T2/T3，留空跑全部")
    ap.add_argument("--out", default=r"D:/工作区/_runtime/three_arms")
    a = ap.parse_args()
    raise SystemExit(asyncio.run(main_async(a)))
