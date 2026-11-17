"""P1-3 评测集静态校验与工程指标计算。

设计原则：指标必须能脱离云端复算，否则评委无法验证。
- 静态模式（默认）只读源码与评测集，交叉校验「评测集引用的工具是否真实存在」，
  这一步是真实交叉验证，不是自查自证。
- live 模式不在本脚本内实现，留在报告里说明（需要云端 IAM 凭据），
  因此「引用正确率」「工具调用成功率」在此明确标为未测。

用法：
    python scripts/eval/run_eval.py
    python scripts/eval/run_eval.py --json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]          # 01_ICT主工程
EVAL_SET = pathlib.Path(__file__).with_name("agentarts_eval_set.jsonl")
SERVER_PY = ROOT / "backend" / ".." / ".." / "mcp_server" / "server.py"
PATH_STAGES = {"stage-1", "stage-2", "stage-3"}

def load_tools(server: pathlib.Path) -> set[str]:
    """从 server.py 真实解析 @mcp.tool() 装饰的函数名。"""
    text = server.read_text(encoding="utf-8")
    return set(re.findall(r"@mcp\.tool\([^)]*\)\s*\ndef\s+([A-Za-z_][A-Za-z0-9_]*)", text))


def load_cases(path: pathlib.Path) -> list[dict]:
    cases, seen = [], set()
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"评测集第 {lineno} 行不是合法 JSON：{exc}")
        for key in ("id", "scene", "prompt", "tool", "expect"):
            if not case.get(key):
                raise SystemExit(f"评测集第 {lineno} 行缺少字段 {key}")
        if case["id"] in seen:
            raise SystemExit(f"评测集出现重复 id：{case['id']}")
        required = case.get("required_tools", [case["tool"]])
        if not isinstance(required, list) or not required or not all(isinstance(name, str) and name for name in required):
            raise SystemExit(f"评测集第 {lineno} 行 required_tools 必须是非空工具名列表")
        if required[0] != case["tool"]:
            raise SystemExit(f"评测集第 {lineno} 行首个 required_tools 必须等于 tool")
        seen.add(case["id"])
        cases.append(case)
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="只输出 JSON 指标")
    args = parser.parse_args()

    if not SERVER_PY.exists():
        raise SystemExit(f"找不到 MCP 入口：{SERVER_PY}")
    tools = load_tools(SERVER_PY)
    cases = load_cases(EVAL_SET)

    unknown_tool = [c["id"] for c in cases if any(
        name not in tools for name in c.get("required_tools", [c["tool"]])
    )]
    bad_stage = [
        c["id"]
        for c in cases
        if c.get("path_stage") and c["path_stage"] not in PATH_STAGES
    ]
    used = {name for c in cases for name in c.get("required_tools", [c["tool"]])}
    multi_tool_cases = [c["id"] for c in cases if len(c.get("required_tools", [c["tool"]])) > 1]
    scenes: dict[str, int] = {}
    for case in cases:
        scenes[case["scene"]] = scenes.get(case["scene"], 0) + 1

    metrics = {
        "cases": len(cases),
        "scenes": scenes,
        "tools_in_source": len(tools),
        "tools_referenced": len(used),
        "tools_never_referenced": sorted(tools - used),
        "unknown_tool_refs": unknown_tool,
        "bad_path_stage_refs": bad_stage,
        "tool_coverage": f"{len(used & tools)}/{len(tools)}",
        "static_pass": not unknown_tool and not bad_stage,
        "semantic_cases_unmeasured": len(cases),
        "multi_tool_cases": multi_tool_cases,
        "unmeasured": {
            "citation_correctness": "未测：需带参考出处的运行结果与人工核验",
            "path_executable_rate": "未测：需实际执行评测集中的学习路径任务",
            "tool_success_rate": "未测：本脚本只验证源码契约，不调用工具；本地 MCP 调用另见 test_mcp.ps1",
            "agentarts_cloud": "未测：需 AgentArts 工作流运行记录和实际调用轨迹",
        },
    }

    if args.json:
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
    else:
        print(f"评测集：{EVAL_SET.name}  场景：{scenes}")
        print(f"工具覆盖：{metrics['tool_coverage']}（源码解析出 {len(tools)} 个）")
        print(f"未引用的工具：{metrics['tools_never_referenced'] or '无'}")
        print(f"非法工具引用：{unknown_tool or '无'}")
        print(f"非法路径阶段：{bad_stage or '无'}")
        print(f"工具调用成功率：{metrics['unmeasured']['tool_success_rate']}")
        print(f"静态校验：{'通过' if metrics['static_pass'] else '失败'}")

    return 0 if metrics["static_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
