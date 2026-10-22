from __future__ import annotations

import argparse
import asyncio
import json

import httpx
from mcp import ClientSession
from mcp.shared._httpx_utils import McpHttpClientFactory
from mcp.client.streamable_http import streamablehttp_client


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


async def run(url: str) -> None:
    factory: McpHttpClientFactory = local_http_client_factory
    async with streamablehttp_client(url, httpx_client_factory=factory) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools.tools]
            print(json.dumps({"available_tools": tool_names}, ensure_ascii=False))

            calls = [
                ("get_student_profile", {"student_id": "demo"}),
                ("get_role_competency", {"role_id": "job_001"}),
            ]
            for name, arguments in calls:
                result = await session.call_tool(name, arguments)
                payload = result.structuredContent
                if payload is None:
                    payload = [getattr(item, "text", str(item)) for item in result.content]
                print(json.dumps({"tool": name, "is_error": result.isError, "result": payload}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Call the local ICT AgentArts MCP server.")
    parser.add_argument("--url", default="http://127.0.0.1:8010/mcp")
    args = parser.parse_args()
    asyncio.run(run(args.url))


if __name__ == "__main__":
    main()

