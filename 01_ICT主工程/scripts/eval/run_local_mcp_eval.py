"""Run all eval tool sequences against an isolated, authenticated local MCP server.

This checks execution and response shape only. It does not grade semantic answers.
Writes affect a temporary test/generated copy and are deleted at process exit.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

PROJECT = Path(__file__).resolve().parents[2]
REPO = PROJECT.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(PROJECT))
from mcp_server.smoke_client import _free_local_port, _wait_for_health, local_http_client_factory  # noqa: E402
from mcp_server.test_support import TEST_STUDENT_ID, prepare_generated_test_data  # noqa: E402
from scripts.eval.run_eval import EVAL_SET, load_cases  # noqa: E402

REFERENCE_FIELDS = {
    "get_student_profile": ["basic_info", "abilities", "weaknesses", "learning_summary"],
    "get_role_competency": ["requirements", "skill_level", "matching_basis"],
    "get_project_status": ["path"],
    "search_knowledge": ["results", "result_count"],
    "get_exercise_session": ["questions", "source"],
    "submit_exercise_answer": ["correct", "path_progress"],
    "get_wrong_book": ["records", "stats", "tag_summary"],
    "get_learning_evaluation": ["evaluation"],
    "add_learning_branch": ["branch", "parent_stage", "created"],
}


def payload_of(result) -> dict:
    value = getattr(result, "structuredContent", None)
    if isinstance(value, dict):
        return value
    for item in result.content:
        try:
            parsed = json.loads(getattr(item, "text", ""))
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError):
            pass
    code = "MCP_ARGUMENT_VALIDATION" if result.isError else "NO_JSON_RESULT"
    return {"ok": False, "error": {"code": code}, "data": None}


async def evaluate(url: str, api_key: str, cases: list[dict], question_id: str, stage_id: str) -> list[dict]:
    def client_factory(headers=None, timeout=None, auth=None):
        supplied = dict(headers or {})
        supplied["X-API-Key"] = api_key
        return local_http_client_factory(headers=supplied, timeout=timeout, auth=auth)

    records = []
    async with streamablehttp_client(url, httpx_client_factory=client_factory) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = {tool.name for tool in (await session.list_tools()).tools}
            for case in cases:
                trace = []
                for name in case.get("required_tools", [case["tool"]]):
                    if name not in listed:
                        trace.append({"tool": name, "ok": False, "error_code": "TOOL_NOT_LISTED"})
                        continue
                    args: dict = {"student_id": TEST_STUDENT_ID}
                    if name == "get_role_competency":
                        args = {"role_id": "job_001"}
                    elif name == "search_knowledge":
                        args["query"] = "软件需求分析"
                    elif name == "get_exercise_session":
                        args["limit"] = 3
                    elif name == "submit_exercise_answer":
                        args.update({"question_id": question_id, "answer": "A"})
                    elif name == "add_learning_branch":
                        args.update({"knowledge_node_id": stage_id, "title": f"test/generated {case['id']} 补强分支"})
                    if case["id"] == "E30" and name == "get_exercise_session":
                        args = {}  # boundary case: learner ID is intentionally absent
                    try:
                        result = payload_of(await session.call_tool(name, args))
                        data = result.get("data") or {}
                        observations = {}
                        if name == "get_project_status" and isinstance(data, dict):
                            nodes = ((data.get("path") or {}).get("nodes") or [])
                            observations["persisted_branch_count"] = sum(len(node.get("branches") or []) for node in nodes)
                        if name == "get_learning_evaluation" and isinstance(data, dict):
                            evidence = ((data.get("evaluation") or {}).get("evidence") or {})
                            observations["exercise_attempts"] = evidence.get("exercise_attempts", 0)
                        trace.append({"tool": name, "arguments": args, "ok": result.get("ok") is True,
                                      "expected_boundary": case["id"] == "E30" and name == "get_exercise_session",
                                      "error_code": (result.get("error") or {}).get("code"),
                                      "reference_fields": REFERENCE_FIELDS[name],
                                      "missing_reference_fields": [field for field in REFERENCE_FIELDS[name] if field not in data],
                                      "observations": observations,
                                      "data_fields": sorted(data) if isinstance(data, dict) else []})
                    except Exception as exc:
                        trace.append({"tool": name, "arguments": args, "ok": False,
                                      "error_code": type(exc).__name__, "data_fields": []})
                records.append({"id": case["id"], "data_classification": "test/generated",
                                "scene": case["scene"], "prompt": case["prompt"],
                                "expected": case["expect"], "trace": trace,
                                "human_rubric": {"task_completion": None, "citation_correctness": None,
                                                "parameter_suitability": None, "unsupported_claims": None},
                                "semantic_status": "unmeasured"})
    return records


async def run(output: Path) -> dict:
    cases = load_cases(EVAL_SET)
    with tempfile.TemporaryDirectory(prefix="ict-eval-generated-") as temporary:
        data_dir = prepare_generated_test_data(Path(temporary) / "test" / "generated" / "data")
        port = _free_local_port()
        key = secrets.token_urlsafe(32)
        env = os.environ.copy()
        env.update({"MCP_HOST": "127.0.0.1", "MCP_PORT": str(port), "MCP_API_KEY": key,
                    "MCP_RATE_LIMIT_PER_MIN": "1000", "MCP_DATA_DIR": str(data_dir),
                    "PYTHONPATH": str(REPO)})
        env.pop("MCP_TRANSPORT_DIRECT", None)
        process = subprocess.Popen([sys.executable, "-m", "mcp_server.server"], cwd=REPO,
                                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            await _wait_for_health(process, f"http://127.0.0.1:{port}/healthz")
            def factory(headers=None, timeout=None, auth=None):
                supplied = dict(headers or {})
                supplied["X-API-Key"] = key
                return local_http_client_factory(headers=supplied, timeout=timeout, auth=auth)
            async with streamablehttp_client(f"http://127.0.0.1:{port}/mcp", httpx_client_factory=factory) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    exercise = payload_of(await session.call_tool("get_exercise_session", {"student_id": TEST_STUDENT_ID, "limit": 1}))
                    status = payload_of(await session.call_tool("get_project_status", {"student_id": TEST_STUDENT_ID}))
                    question_id = exercise["data"]["questions"][0]["id"]
                    stage_id = status["data"]["path"]["nodes"][0]["id"]
            records = await evaluate(f"http://127.0.0.1:{port}/mcp", key, cases, question_id, stage_id)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n", encoding="utf-8")
    calls = [step for item in records for step in item["trace"]]
    return {"cases": len(records), "tool_calls": len(calls), "successful_calls": sum(step["ok"] for step in calls),
            "successful_calls_missing_reference_fields": sum(bool(step.get("missing_reference_fields")) for step in calls if step["ok"]),
            "expected_boundary_errors": sum(bool(step.get("expected_boundary")) and not step["ok"] for step in calls),
            "unexpected_errors": sum(not step["ok"] and not step.get("expected_boundary") for step in calls),
            "failed_calls": [{"case": item["id"], "tool": step["tool"], "code": step["error_code"]}
                             for item in records for step in item["trace"] if not step["ok"]],
            "semantic_cases_unmeasured": len(records), "output": str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.output)), ensure_ascii=False, indent=2))
