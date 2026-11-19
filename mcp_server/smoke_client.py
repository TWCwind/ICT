from __future__ import annotations

import asyncio
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx
from mcp import ClientSession
from mcp.shared._httpx_utils import McpHttpClientFactory
from mcp.client.streamable_http import streamablehttp_client

from mcp_server.test_support import TEST_STUDENT_ID, prepare_generated_test_data


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOOLS = {
    "get_student_profile",
    "get_role_competency",
    "get_project_status",
    "search_knowledge",
    "get_exercise_session",
    "submit_exercise_answer",
    "get_wrong_book",
    "get_learning_evaluation",
    "add_learning_branch",
}


def local_http_client_factory(
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    auth: httpx.Auth | None = None,
) -> httpx.AsyncClient:
    """Keep local MCP verification off machine-level HTTP proxy settings."""
    kwargs: dict[str, object] = {"trust_env": False}
    if headers is not None:
        kwargs["headers"] = headers
    if timeout is not None:
        kwargs["timeout"] = timeout
    if auth is not None:
        kwargs["auth"] = auth
    return httpx.AsyncClient(**kwargs)


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _result_payload(result: Any, tool_name: str) -> dict[str, Any]:
    if result.isError:
        raise RuntimeError(f"MCP tool {tool_name} returned isError=true")

    payload = getattr(result, "structuredContent", None)
    if payload is None:
        for item in result.content:
            text = getattr(item, "text", "")
            if not text:
                continue
            try:
                payload = json.loads(text)
                break
            except json.JSONDecodeError:
                continue
    if not isinstance(payload, dict):
        raise RuntimeError(f"MCP tool {tool_name} returned no JSON object")
    if payload.get("ok") is not True:
        error = payload.get("error") or {}
        raise RuntimeError(
            f"MCP tool {tool_name} failed: {error.get('code', 'UNKNOWN')} "
            f"{error.get('message', 'no error message')}"
        )
    return payload


async def _wait_for_health(process: subprocess.Popen[str], url: str) -> None:
    async with httpx.AsyncClient(trust_env=False, timeout=1.5) as client:
        for _ in range(80):
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise RuntimeError(f"isolated MCP server exited before health check:\n{output}")
            try:
                response = await client.get(url)
                if response.status_code == 200 and response.json().get("ok") is True:
                    return
            except (httpx.HTTPError, ValueError):
                pass
            await asyncio.sleep(0.25)
    raise RuntimeError("isolated MCP server did not become healthy within 20 seconds")


async def _call_all_tools(url: str, api_key: str) -> None:
    def authenticated_factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        merged = dict(headers or {})
        merged["X-API-Key"] = api_key
        return local_http_client_factory(headers=merged, timeout=timeout, auth=auth)

    factory: McpHttpClientFactory = authenticated_factory
    async with streamablehttp_client(url, httpx_client_factory=factory) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()
            tool_names = {tool.name for tool in listed.tools}
            if tool_names != EXPECTED_TOOLS:
                raise RuntimeError(
                    f"expected exactly 9 MCP tools; missing={sorted(EXPECTED_TOOLS - tool_names)}, "
                    f"unexpected={sorted(tool_names - EXPECTED_TOOLS)}"
                )
            print(json.dumps({"tools_listed": len(tool_names), "result": "PASS"}, ensure_ascii=False))

            async def call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
                result = await session.call_tool(name, arguments)
                payload = _result_payload(result, name)
                print(json.dumps({"tool": name, "ok": True}, ensure_ascii=False))
                return payload

            await call("get_student_profile", {"student_id": TEST_STUDENT_ID})
            await call("get_role_competency", {"role_id": "job_001"})
            status = await call("get_project_status", {"student_id": TEST_STUDENT_ID})
            await call(
                "search_knowledge",
                {"student_id": TEST_STUDENT_ID, "query": "软件需求分析", "limit": 3},
            )

            exercise = await call("get_exercise_session", {"student_id": TEST_STUDENT_ID, "limit": 2})
            questions = (exercise.get("data") or {}).get("questions") or []
            if not questions:
                raise RuntimeError("get_exercise_session returned no generated test question")
            question_id = str(questions[0].get("id") or "")
            if not question_id:
                raise RuntimeError("generated test question did not include an id")

            answer = await call(
                "submit_exercise_answer",
                {"student_id": TEST_STUDENT_ID, "question_id": question_id, "answer": "A"},
            )
            if answer.get("data", {}).get("correct") is not True:
                raise RuntimeError("generated smoke question was not scored as expected")

            await call("get_wrong_book", {"student_id": TEST_STUDENT_ID})
            await call("get_learning_evaluation", {"student_id": TEST_STUDENT_ID})

            path = (status.get("data") or {}).get("path") or {}
            nodes = path.get("nodes") or []
            if not nodes or not nodes[0].get("id"):
                raise RuntimeError("get_project_status returned no path node for branch test")
            branch = await call(
                "add_learning_branch",
                {
                    "student_id": TEST_STUDENT_ID,
                    "knowledge_node_id": str(nodes[0]["id"]),
                    "title": "MCP 自动化验证分支",
                    "description": "test/generated 写入闭环",
                    "mastery": 0,
                },
            )
            if branch.get("data", {}).get("created") is not True:
                raise RuntimeError("add_learning_branch did not create the isolated test branch")


async def run_isolated(data_root: Path) -> None:
    port = _free_local_port()
    api_key = secrets.token_urlsafe(32)
    env = os.environ.copy()
    env.update(
        {
            "MCP_HOST": "127.0.0.1",
            "MCP_PORT": str(port),
            "MCP_API_KEY": api_key,
            "MCP_RATE_LIMIT_PER_MIN": "240",
            "MCP_DATA_DIR": str(data_root),
            "PYTHONPATH": str(WORKSPACE_ROOT),
        }
    )
    env.pop("MCP_TRANSPORT_DIRECT", None)
    process = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.server"],
        cwd=WORKSPACE_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    url = f"http://127.0.0.1:{port}/mcp"
    try:
        await _wait_for_health(process, f"http://127.0.0.1:{port}/healthz")
        print(json.dumps({"isolated_test_data": "test/generated", "health": "PASS"}, ensure_ascii=False))
        await _call_all_tools(url, api_key)
        print(json.dumps({"business_tool_calls": 9, "writes_confined_to_temp_copy": True, "result": "PASS"}, ensure_ascii=False))
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if process.stdout:
            process.stdout.close()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ict-mcp-smoke-") as temporary_root:
        data_root = prepare_generated_test_data(Path(temporary_root) / "test" / "generated" / "data")
        asyncio.run(run_isolated(data_root))


if __name__ == "__main__":
    main()
