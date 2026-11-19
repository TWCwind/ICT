from __future__ import annotations

from typing import Any, AsyncIterator

"""学习路径工具：掌握度/风险分级、证据化路径建议、路径计划稳定化。"""

def _bounded_score(value: Any, fallback: Any = 0) -> float:
    try:
        score = float(value if value not in (None, "") else fallback)
    except (TypeError, ValueError):
        score = 0.0
    return round(max(0.0, min(100.0, score)), 1)


def _mastery_level(value: Any) -> str:
    score = _bounded_score(value)
    if score >= 80:
        return "稳定掌握"
    if score >= 60:
        return "基本掌握"
    if score >= 40:
        return "持续提升"
    return "基础补强"


def _risk_level(value: Any) -> str:
    score = _bounded_score(value)
    if score >= 75:
        return "低风险"
    if score >= 55:
        return "中风险"
    return "高风险"


def _evidence_recommendations(*, accuracy: float, weak_points: list[str], disliked: int) -> list[str]:
    recommendations: list[str] = []
    if weak_points:
        recommendations.append(f"优先围绕“{weak_points[0]}”完成一次讲解、练习、复盘闭环")
    if accuracy < 60:
        recommendations.append("降低下一阶段题目跨度，先完成基础辨析题再进入综合应用")
    if disliked:
        recommendations.append("降低最近收到负反馈的资源类型权重，并切换为其他表达模态")
    if not recommendations:
        recommendations.append("继续积累答题、知识节点和资源反馈证据后再次评估")
    return recommendations[:3]


def _default_path_steps(available: list[str]) -> list[dict[str, Any]]:
    base_docs = [item for item in ("lecture_doc", "mindmap") if item in available] or ["lecture_doc"]
    practice = [item for item in ("question_bank", "practice_case") if item in available] or ["question_bank"]
    review = [item for item in ("reading", "video_script") if item in available] or ["reading", "video_script"]
    return [
        {
            "order": 1,
            "objective": "学习状态诊断与薄弱点确认",
            "resources": ["question_bank"] if "question_bank" in available else practice,
            "assessment": "完成诊断题并标记错因，确认需要优先补强的 2 到 3 个知识点。",
        },
        {
            "order": 2,
            "objective": "补齐核心概念和知识结构",
            "resources": base_docs,
            "assessment": "能够用自己的话复述核心概念，并输出一张概念对照表或思维导图。",
        },
        {
            "order": 3,
            "objective": "围绕易错点进行强化练习",
            "resources": practice,
            "assessment": "同类题目正确率达到 80%，并能解释每个错误对应的知识点。",
        },
        {
            "order": 4,
            "objective": "通过实操案例完成知识迁移",
            "resources": ["practice_case"] if "practice_case" in available else practice,
            "assessment": "提交一个小型实操作品或案例分析，并说明用到了哪些课程知识。",
        },
        {
            "order": 5,
            "objective": "拓展阅读、多模态复盘与下一轮评估",
            "resources": review,
            "assessment": "输出复盘笔记和阶段评估，说明下一轮还需要系统推送哪些资源。",
        },
    ]


def _stabilize_path_plan(plan: Any, *, available: list[str]) -> dict[str, Any]:
    data = dict(plan) if isinstance(plan, dict) else {}
    raw_steps = data.get("steps") if isinstance(data.get("steps"), list) else []
    steps: list[dict[str, Any]] = []
    for index in range(len(raw_steps)):
        raw = raw_steps[index] if index < len(raw_steps) and isinstance(raw_steps[index], dict) else {}
        fallback = {
            "order": index + 1,
            "objective": "",
            "resources": [],
            "assessment": "",
        }
        resources = raw.get("resources") if isinstance(raw.get("resources"), list) else []
        steps.append(
            {
                **raw,
                "order": raw.get("order") or raw.get("step") or index + 1,
                "objective": raw.get("objective") or raw.get("title") or fallback["objective"],
                "resources": resources,
                "assessment": raw.get("assessment") or raw.get("checkpoint") or fallback["assessment"],
            }
        )

    strategy = data.get("strategy") if isinstance(data.get("strategy"), list) else []
    dynamic_rules = data.get("dynamic_rules") if isinstance(data.get("dynamic_rules"), list) else []
    data.update(
        {
            "title": data.get("title") or "个性化学习路径与资源推送方案",
            "steps": steps,
            "strategy": strategy,
            "dynamic_rules": dynamic_rules,
            "rationale": data.get("rationale") or "",
        }
    )
    return data


def _evidence_path_plan(
    *,
    goals: str,
    weak_points: list[str],
    weak_mastery_nodes: list[dict[str, Any]],
    tutor_questions: list[str],
    resources: list[dict[str, Any]],
    accuracy: float,
    attempts: int,
    liked_count: int,
    disliked_count: int,
) -> dict[str, Any]:
    """Create a variable path only from persisted learner evidence and the stated goal."""
    focus_items: list[str] = []
    for value in [
        *weak_points,
        *[str(item.get("name") or item.get("title") or "") for item in weak_mastery_nodes],
        *tutor_questions[-3:],
    ]:
        normalized = " ".join(str(value or "").split())[:80]
        if normalized and normalized not in focus_items:
            focus_items.append(normalized)

    resource_types = sorted({str(item.get("type") or "") for item in resources if item.get("type")})
    resource_titles = [str(item.get("title") or "") for item in resources if item.get("title")]
    steps: list[dict[str, Any]] = []

    for focus in focus_items[:3]:
        steps.append(
            {
                "order": len(steps) + 1,
                "objective": f"处理已识别薄弱点：{focus}",
                "resources": resource_types[:3],
                "assessment": f"围绕“{focus}”完成一次可记录的练习、复述或实操证据",
                "evidence_source": "profile_or_learning_history",
            }
        )

    if attempts and accuracy < 70:
        steps.append(
            {
                "order": len(steps) + 1,
                "objective": f"修复练习正确率偏低问题（当前 {accuracy:.1f}%）",
                "resources": [item for item in resource_types if item in {"lecture_doc", "mindmap", "question_bank"}],
                "assessment": "再次完成同知识点练习，并用新的作答记录验证变化",
                "evidence_source": "exercise_records",
            }
        )

    normalized_goal = " ".join(str(goals or "").split())[:160]
    if normalized_goal:
        steps.append(
            {
                "order": len(steps) + 1,
                "objective": f"达成用户目标：{normalized_goal}",
                "resources": resource_types,
                "assessment": "提交与目标对应的学习产物，并进入评估页面生成证据报告",
                "evidence_source": "user_goal",
            }
        )

    if resource_titles and not steps:
        steps.append(
            {
                "order": 1,
                "objective": "使用现有资源形成首轮学习证据",
                "resources": resource_types,
                "assessment": f"完成并反馈资源：{resource_titles[0]}",
                "evidence_source": "resource_history",
            }
        )

    if not steps:
        raise ValueError("尚无可用于路径分析的学习目标或行为证据，请先填写目标、更新画像或完成一次练习")

    strategy = [
        f"路径由 {len(focus_items)} 个薄弱信号、{attempts} 次作答和 {len(resources)} 份已有资源计算生成。",
    ]
    if resource_types:
        strategy.append("仅推荐当前学生已经生成的资源类型：" + "、".join(resource_types))
    if liked_count or disliked_count:
        strategy.append(f"资源反馈参与排序：有帮助 {liked_count} 次，负反馈 {disliked_count} 次。")

    dynamic_rules: list[str] = []
    if attempts:
        dynamic_rules.append(f"当前练习正确率为 {accuracy:.1f}%，后续作答会重新计算阶段优先级。")
    if weak_mastery_nodes:
        dynamic_rules.append(f"检测到 {len(weak_mastery_nodes)} 个低掌握知识节点，优先安排对应补强。")
    if disliked_count:
        dynamic_rules.append(f"检测到 {disliked_count} 次资源负反馈，同类资源在下一次规划中降权。")

    return {
        "title": f"围绕“{normalized_goal}”的证据驱动学习路径" if normalized_goal else "证据驱动学习路径",
        "steps": steps,
        "strategy": strategy,
        "dynamic_rules": dynamic_rules,
        "rationale": "；".join(strategy),
        "analysis_mode": "evidence_rules",
    }
