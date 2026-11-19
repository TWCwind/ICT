from __future__ import annotations

from typing import Any, AsyncIterator
import re

from app.core.config import settings

"""内容生产与审计：题目载荷约束、资源正文加载、离线审计报告与 Markdown 渲染。"""

def _tutor_fallback_answer(references: list[dict[str, Any]], *, degraded: bool) -> dict[str, Any]:
    prefix = (
        "在线模型暂时不可用，已切换到本地知识库答疑框架。"
        if degraded
        else "未配置在线大模型，已使用本地知识库答疑框架。"
    )
    answer: dict[str, Any] = {
        "text": (
            f"{prefix}\n"
            "1) 复述问题并定位知识点\n"
            "2) 根据课程证据给出分步解释\n"
            "3) 给出一个最小例子\n"
            "4) 列出常见误区与自检方法\n"
            "5) 给出短视频分镜与画面提示"
        ),
        "diagram_hint": "可用 mermaid 或流程图展示关键步骤与变量变化",
        "video_storyboard": [
            {"scene": 1, "voice": "先说清问题是什么", "visual": "显示题目与关键词高亮"},
            {"scene": 2, "voice": "拆成三个小步骤", "visual": "逐步出现公式或伪代码"},
            {"scene": 3, "voice": "用一个例子跑一遍", "visual": "表格展示输入输出变化"},
        ],
        "references": references,
    }
    if degraded:
        answer["degraded_reason"] = "upstream_unavailable"
    return answer


_QUIZ_TYPE_LABELS = {
    "single_choice": "单选题",
    "multiple_choice": "多选题",
    "true_false": "判断题",
    "blank": "填空题",
    "short_answer": "简答题",
    "case_analysis": "案例分析题",
    "calculation": "计算题",
    "matching": "匹配题",
    "ordering": "排序题",
}


def _quiz_generation_config(requirement: dict[str, Any]) -> tuple[list[str], dict[str, int], int]:
    config = requirement.get("question_config") if isinstance(requirement.get("question_config"), dict) else {}
    requested = config.get("types") if isinstance(config.get("types"), list) else []
    allowed = [str(item) for item in requested if str(item) in _QUIZ_TYPE_LABELS]
    if not allowed:
        allowed = ["single_choice"]
    raw_counts = config.get("type_counts") if isinstance(config.get("type_counts"), dict) else {}
    counts = {
        item: max(0, min(20, int(raw_counts.get(item) or 0)))
        for item in allowed
    }
    counts = {key: value for key, value in counts.items() if value > 0}
    if not counts:
        total = max(1, min(50, int(config.get("count") or len(allowed))))
        counts = {item: max(1, total // len(allowed)) for item in allowed}
    total = max(1, min(50, int(config.get("count") or sum(counts.values()))))
    return list(counts), counts, total


def _constrain_quiz_payload(payload: dict[str, Any], requirement: dict[str, Any]) -> dict[str, Any]:
    allowed, counts, total = _quiz_generation_config(requirement)
    selected: list[dict[str, Any]] = []
    used = {item: 0 for item in allowed}
    raw_questions = payload.get("questions") if isinstance(payload.get("questions"), list) else []
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        question_type = str(item.get("type") or "").strip()
        if question_type not in used or used[question_type] >= counts[question_type]:
            continue
        selected.append(item)
        used[question_type] += 1
        if len(selected) >= total:
            break
    payload["questions"] = selected
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    payload["meta"] = {**meta, "requested_types": allowed, "requested_type_counts": counts}
    return payload


def _write_text(rel_path: str, content: str) -> str:
    p = settings.data_path / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return rel_path.replace("\\", "/")


def _load_resource_bodies(resources: list[dict[str, Any]], max_chars: int = 14000) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for resource in resources:
        content = ""
        content_uri = str(resource.get("content_uri") or "")
        if content_uri:
            path = settings.data_path / content_uri
            if path.exists() and path.is_file():
                content = path.read_text(encoding="utf-8", errors="replace")
        loaded.append(
            {
                "resource_id": resource.get("id"),
                "title": resource.get("title"),
                "type": resource.get("type"),
                "tags": resource.get("tags") or [],
                "content_chars": len(content),
                "content_truncated": len(content) > max_chars,
                "content": content[:max_chars],
            }
        )
    return loaded


def _deterministic_content_audit(
    resources: list[dict[str, Any]], references: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    reference_titles = [str(item.get("title") or "") for item in references]
    findings: list[dict[str, Any]] = []
    citation_pattern = re.compile(
        r"(?:https?://\S+|《[^》]{2,80}》|\b(?:19|20)\d{2}\b|第\s*\d+\s*(?:版|章|页)|"
        r"(?:GB|ISO|IEEE|RFC)\s*[-/:]?\s*[A-Z0-9.:-]+)",
        re.IGNORECASE,
    )
    for resource in resources:
        content = str(resource.get("content") or "")
        claims = sorted(set(citation_pattern.findall(content)))[:30]
        has_source_section = any(
            marker in content for marker in ("来源", "参考", "引用", "知识库参考", "待核验")
        )
        unsupported_markers = [
            claim
            for claim in claims
            if claim not in " ".join(reference_titles) and "待核验" not in content[max(0, content.find(claim) - 30) : content.find(claim) + len(claim) + 30]
        ]
        issues: list[str] = []
        if not content.strip():
            issues.append("资源正文为空，无法执行事实核验。")
        if claims and not has_source_section:
            issues.append("正文包含具体链接、书目、年份或标准编号，但没有来源/待核验说明。")
        if unsupported_markers:
            issues.append(f"发现 {len(unsupported_markers)} 个未与本地依据绑定的具体引用标记。")
        if resource.get("content_truncated"):
            issues.append("正文过长，本轮模型审查使用了截断文本，应对完整文件执行离线复核。")
        findings.append(
            {
                "resource_id": resource.get("resource_id"),
                "title": resource.get("title"),
                "claims": claims,
                "unsupported_markers": unsupported_markers,
                "has_source_section": has_source_section,
                "issues": issues,
            }
        )
    return findings


def _offline_audit_report(
    resources: list[dict[str, Any]], findings: list[dict[str, Any]]
) -> dict[str, Any]:
    audited: list[dict[str, Any]] = []
    highest = "pass"
    risk_score = 0
    finding_map = {item.get("resource_id"): item for item in findings}
    for resource in resources:
        finding = finding_map.get(resource.get("resource_id"), {})
        issues = list(finding.get("issues") or [])
        status = "warning" if issues else "pass"
        if not str(resource.get("content") or "").strip():
            status = "fail"
        if status == "fail":
            highest = "fail"
            risk_score = max(risk_score, 80)
        elif status == "warning" and highest != "fail":
            highest = "warning"
            risk_score = max(risk_score, 45)
        audited.append(
            {
                "resource_id": resource.get("resource_id"),
                "title": resource.get("title"),
                "status": status,
                "verified_claims": [],
                "unsupported_claims": finding.get("unsupported_markers") or [],
                "citation_issues": issues,
                "content_issues": ["未配置在线质检模型，当前仅执行确定性正文扫描。"],
                "rewrite_instructions": ["为具体事实补充本地知识库来源，无法核验时明确标注“待核验”。"] if issues else [],
            }
        )
    return {
        "overall_status": highest,
        "risk_score": risk_score,
        "summary": "已读取全部资源正文并完成确定性引用扫描；配置在线模型后可进一步进行语义事实核验。",
        "resources": audited,
        "global_actions": ["保留来源标记和待核验状态，禁止输出无法追溯的具体论文、版本、页码和链接。"],
    }


def _audit_markdown(audit: dict[str, Any], references: list[dict[str, Any]]) -> str:
    status_labels = {"pass": "通过", "warning": "需复核", "fail": "不通过"}
    status = str(audit.get("overall_status") or "warning").lower()
    lines = [
        "# 内容质检与防幻觉审查报告",
        "",
        "## 总体结论",
        f"- 审查状态：{status_labels.get(status, status)}",
        f"- 风险评分：{audit.get('risk_score', '--')}/100",
        f"- 结论摘要：{audit.get('summary') or '未提供'}",
        "- 审查范围：资源正文、事实主张、引用来源、题目答案、代码与结构完整性。",
        "",
        "## 分资源审查",
    ]
    for index, item in enumerate(audit.get("resources") or [], 1):
        item_status = str(item.get("status") or "warning").lower()
        lines.extend(
            [
                "",
                f"### {index}. {item.get('title') or item.get('resource_id') or '未命名资源'}",
                f"- 状态：{status_labels.get(item_status, item_status)}",
            ]
        )
        for label, key in (
            ("已核验主张", "verified_claims"),
            ("无依据主张", "unsupported_claims"),
            ("引用问题", "citation_issues"),
            ("内容问题", "content_issues"),
            ("修改要求", "rewrite_instructions"),
        ):
            values = item.get(key) or []
            if values:
                lines.append(f"- {label}：")
                lines.extend(f"  - {value}" for value in values)
    actions = audit.get("global_actions") or []
    if actions:
        lines.extend(["", "## 全局修正动作"])
        lines.extend(f"- {action}" for action in actions)
    lines.extend(["", "## 本轮知识库依据"])
    if references:
        for item in references:
            lines.append(f"- {item.get('title')}（匹配度 {item.get('score')}）")
    else:
        lines.append("- 未检索到高相关本地依据，所有具体外部事实均需标注“待核验”。")
    return "\n".join(lines) + "\n"
