from __future__ import annotations

import os
from typing import Any, TypedDict

from mcp.server.fastmcp import FastMCP

from mcp_server.services import (
    get_project_status_data,
    get_role_competency_data,
    get_student_profile_data,
)


HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "8010"))


class ToolEnvelope(TypedDict):
    ok: bool
    data: dict[str, Any] | None
    error: dict[str, Any] | None
    meta: dict[str, Any]

mcp = FastMCP(
    "ict-agentarts-tools",
    instructions="为 AgentArts 提供学生画像、岗位能力和学习项目状态查询。",
    host=HOST,
    port=PORT,
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
def get_student_profile(student_id: str) -> ToolEnvelope:
    """按学生 ID 查询基础信息、六维能力、薄弱点和学习记录摘要。

    当前协作包包含可验证的测试学生 ID：demo。
    """

    return get_student_profile_data(student_id)


@mcp.tool()
def get_role_competency(role_name: str = "", role_id: str = "") -> ToolEnvelope:
    """按岗位完整名称或岗位 ID 查询能力要求、技能层级和匹配依据。

    role_name 与 role_id 至少提供一个；同时提供时优先使用 role_id。
    """

    return get_role_competency_data(role_name=role_name, role_id=role_id)


@mcp.tool()
def get_project_status(student_id: str) -> ToolEnvelope:
    """按学生 ID 查询当前学习路径和项目阶段状态。"""

    return get_project_status_data(student_id)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

