from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator

"""生成智能体注册表：AgentSpec、六个智能体定义、工具绑定校验与选择。"""

@dataclass(frozen=True)
class AgentSpec:
    key: str
    title: str
    resource_type: str
    ext: str
    # P1-1：每个生成智能体必须显式声明它依赖哪些 MCP 工具。
    # 空 tuple 会被 `validate_agent_tool_binding()` 判为缺陷——不再允许「有标签没工具」。
    tools: tuple[str, ...] = ()


AGENTS: list[AgentSpec] = [
    AgentSpec(
        key="lecture",
        title="专业课程讲解文档",
        resource_type="lecture_doc",
        ext="md",
        tools=("search_knowledge", "get_student_profile"),
    ),
    AgentSpec(
        key="mindmap",
        title="知识点思维导图",
        resource_type="mindmap",
        ext="md",
        tools=("search_knowledge",),
    ),
    AgentSpec(
        key="quiz",
        title="个性化题库",
        resource_type="question_bank",
        ext="json",
        tools=("get_exercise_session", "submit_exercise_answer"),
    ),
    AgentSpec(
        key="reading",
        title="拓展阅读材料",
        resource_type="reading",
        ext="md",
        tools=("search_knowledge",),
    ),
    AgentSpec(
        key="practice",
        title="代码/实操案例",
        resource_type="practice_case",
        ext="md",
        tools=("search_knowledge", "get_role_competency"),
    ),
    AgentSpec(
        key="video",
        title="多模态视频/动画脚本",
        resource_type="video_script",
        ext="md",
        tools=("get_student_profile", "get_learning_evaluation"),
    ),
]


def validate_agent_tool_binding() -> list[str]:
    """返回绑定缺陷列表；空列表表示每个生成智能体都挂了真实工具。

    只做静态检查（不访问网络/数据库），可被测试或启动自检直接调用。
    """
    problems: list[str] = []
    for spec in AGENTS:
        if not spec.tools:
            problems.append(f"{spec.key}({spec.resource_type}) 没有绑定任何 MCP 工具")
            continue
        duplicated = {tool for tool in spec.tools if spec.tools.count(tool) > 1}
        if duplicated:
            problems.append(f"{spec.key} 重复绑定 {sorted(duplicated)}")
    return problems


def _requested_agents(requirement: dict[str, Any]) -> list[AgentSpec]:
    raw_types = requirement.get("resource_types") or []
    requested = {str(item).strip() for item in raw_types if str(item).strip()} if isinstance(raw_types, list) else set()
    if not requested:
        single = str(requirement.get("resource_type") or "").strip()
        requested = {single} if single else set()
    if not requested:
        raise ValueError("至少选择一种资源类型，后端不会再默认执行全部生成智能体")
    selected = [spec for spec in AGENTS if spec.resource_type in requested]
    unknown = requested - {spec.resource_type for spec in selected}
    if unknown:
        raise ValueError("不支持的资源类型：" + "、".join(sorted(unknown)))
    return selected
