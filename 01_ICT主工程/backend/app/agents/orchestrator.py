from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, AsyncIterator
import asyncio
import json

from app.core.config import settings
from app.core.ids import new_id
from app.llm import get_glm_client
from app.llm import get_llm_client_for
from app.llm import is_glm_configured
from app.llm import is_llm_configured
from app.repo import ensure_student
from app.repo import get_latest_profile_snapshot
from app.repo import get_user_events
from app.repo import get_user_usages
from app.repo import insert_learning_event
from app.repo import insert_profile_snapshot
from app.repo import insert_resource_item
from app.repo import list_resources
from app.repo import patch_student
from app.services.exercise_bank import exercise_summary
from app.services.knowledge_hub import format_references
from app.services.knowledge_hub import mastery_data
from app.services.knowledge_hub import search_index

from app.agents.agent_registry import AGENTS
from app.agents.agent_registry import AgentSpec
from app.agents.agent_registry import _requested_agents
from app.agents.agent_registry import validate_agent_tool_binding
from app.agents.content_audit import _QUIZ_TYPE_LABELS
from app.agents.content_audit import _audit_markdown
from app.agents.content_audit import _constrain_quiz_payload
from app.agents.content_audit import _deterministic_content_audit
from app.agents.content_audit import _load_resource_bodies
from app.agents.content_audit import _offline_audit_report
from app.agents.content_audit import _quiz_generation_config
from app.agents.content_audit import _tutor_fallback_answer
from app.agents.content_audit import _write_text
from app.agents.path_tools import _bounded_score
from app.agents.path_tools import _default_path_steps
from app.agents.path_tools import _evidence_path_plan
from app.agents.path_tools import _evidence_recommendations
from app.agents.path_tools import _mastery_level
from app.agents.path_tools import _risk_level
from app.agents.path_tools import _stabilize_path_plan
from app.agents.profile_tools import _COURSE_WORDS
from app.agents.profile_tools import _DIM_PLACEHOLDERS
from app.agents.profile_tools import _KEYWORD_BLACKLIST
from app.agents.profile_tools import _clean_dim_value
from app.agents.profile_tools import _extract_basic_info
from app.agents.profile_tools import _extract_field
from app.agents.profile_tools import _extract_keywords
from app.agents.profile_tools import _extract_weak_points
from app.agents.profile_tools import _guess_cognitive_style
from app.agents.profile_tools import _guess_modality
from app.agents.profile_tools import _guess_pace
from app.agents.profile_tools import _infer_preferences
from app.agents.profile_tools import _parse_json_maybe
from app.agents.text_utils import _FENCE
from app.agents.text_utils import _GENERIC_TITLES
from app.agents.text_utils import _JUNK_LATIN
from app.agents.text_utils import _MINDMAP_PLAIN
from app.agents.text_utils import _MINDMAP_ROOT
from app.agents.text_utils import _SHORT_TYPE_LABELS
from app.agents.text_utils import _TITLE_MD
from app.agents.text_utils import _TOPIC_BREAK
from app.agents.text_utils import _clean_node
from app.agents.text_utils import _clean_title
from app.agents.text_utils import _resource_title
from app.agents.text_utils import _safe_text
from app.agents.text_utils import _short_topic
from app.agents.text_utils import _title_from_content
from app.agents.text_utils import _wants_quality_check
from app.agents.text_utils import logger

class Orchestrator:
    async def profile_chat(
        self,
        *,
        student_id: str,
        messages: list[dict[str, str]],
        major: str | None,
        goals: str | None,
        on_chunk: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        ensure_student(student_id=student_id, major=major, goals=goals)
        prev = get_latest_profile_snapshot(student_id)
        user_text = "\n".join([m["content"] for m in messages if m["role"] == "user"])[-2000:]
        # 用户改了口径（例如"我大三，软件工程专业"）时必须以最新一条为准，
        # 否则拼接全文会让第一轮说过的话永远压住后面的修正。
        latest_user_text = ""
        for _item in messages:
            if _item.get("role") == "user" and str(_item.get("content") or "").strip():
                latest_user_text = str(_item.get("content"))
        
        # 引入本地历史数据：资源反馈与答疑记录（潜在问题）
        usages = get_user_usages(student_id)
        events = get_user_events(student_id)
        negative_feedbacks = [u for u in usages if u.get("action") == "dislike"]
        tutor_questions = [e.get("payload", {}).get("question") for e in events if e.get("event_type") == "tutor"]
        
        history_context = ""
        if negative_feedbacks or tutor_questions:
            history_context = "【系统注入：用户历史潜在问题】\n"
            if negative_feedbacks:
                history_context += f"- 近期对 {len(negative_feedbacks)} 个资源表示不喜欢（可能内容不匹配或过难）。\n"
            if tutor_questions:
                history_context += f"- 近期答疑记录（反映薄弱点）：{'; '.join(tutor_questions[-3:])}\n"

        base_profile = {
            "knowledge_base_level": prev.get("knowledge_base_level", "") if prev else "",
            "cognitive_style": prev.get("cognitive_style", "") if prev else "",
            "mistake_patterns": prev.get("mistake_patterns", "") if prev else "",
            "modality_preference": prev.get("modality_preference", "") if prev else "",
            "pace_preference": prev.get("pace_preference", "") if prev else "",
            "motivation_style": prev.get("motivation_style", "") if prev else "",
        }
        basic_info: dict[str, str] = {}

        if is_llm_configured("profile"):
            llm = get_llm_client_for("profile")
            schema_hint = (
                '{"knowledge_base_level": "...", "cognitive_style": "...", "mistake_patterns": "...", '
                '"modality_preference": "...", "pace_preference": "...", "motivation_style": "...", '
                '"basic_info": {"major": "...", "grade": "...", "current_course": "...", "goals": "..."}, '
                '"rationale": "...", "evidence": {"weak_points": ["..."], "keywords": ["..."]}}'
            )
            
            # 将历史潜在问题注入到对话最后一条中，让模型参考
            if history_context:
                messages = list(messages)
                last_msg = messages[-1]
                messages[-1] = {"role": last_msg["role"], "content": last_msg["content"] + "\n\n" + history_context}
                
            data = await llm.chat_json(messages=messages, schema_hint=schema_hint, on_chunk=on_chunk)
            profile = {**base_profile, **(data or {})}
            raw_basic = profile.pop("basic_info", {})
            if isinstance(raw_basic, dict):
                basic_info = {
                    key: _safe_text(raw_basic.get(key) or "")
                    for key in ("major", "grade", "current_course", "goals")
                    if _safe_text(raw_basic.get(key) or "")
                }
            rationale = str(profile.pop("rationale", "") or "")
            evidence = profile.pop("evidence", {}) if isinstance(profile.get("evidence", {}), dict) else {}
        else:
            focused_text = latest_user_text or user_text
            weak_points = _extract_weak_points(focused_text)
            if tutor_questions:
                weak_points.extend(tutor_questions[-2:])
            keywords = _extract_keywords(focused_text)
            previous = {
                key: _clean_dim_value(base_profile.get(key))
                for key in (
                    "knowledge_base_level",
                    "cognitive_style",
                    "mistake_patterns",
                    "modality_preference",
                    "pace_preference",
                    "motivation_style",
                )
            }
            inferred = _infer_preferences(user_text)
            stale_patterns = previous["mistake_patterns"]
            if weak_points:
                stale_patterns = "; ".join(weak_points)
            profile = {
                "knowledge_base_level": previous["knowledge_base_level"] or "待评估",
                "cognitive_style": inferred.get("cognitive_style") or previous["cognitive_style"] or _guess_cognitive_style(user_text),
                "mistake_patterns": stale_patterns or "待采集",
                "modality_preference": inferred.get("modality_preference") or previous["modality_preference"] or _guess_modality(user_text),
                "pace_preference": inferred.get("pace_preference") or previous["pace_preference"] or _guess_pace(user_text),
                "motivation_style": inferred.get("motivation_style") or previous["motivation_style"] or "目标驱动",
            }
            rationale = "已基于对话内容及本地历史潜在问题进行启发式画像抽取；配置在线大模型后可获得更精准的维度识别与依据。"
            evidence = {"weak_points": weak_points, "keywords": keywords}
            basic_info = _extract_basic_info(latest_user_text or user_text)
            for _key, _value in _extract_basic_info(user_text).items():
                basic_info.setdefault(_key, _value)

        snapshot = insert_profile_snapshot(student_id=student_id, profile=profile, evidence=evidence)
        if basic_info:
            patch_student(student_id, basic_info)
        insert_learning_event(student_id, "profile_update", {"snapshot_id": snapshot["id"]})

        delta: dict[str, Any] = {}
        if prev:
            for k in [
                "knowledge_base_level",
                "cognitive_style",
                "mistake_patterns",
                "modality_preference",
                "pace_preference",
                "motivation_style",
            ]:
                if prev.get(k) != snapshot.get(k):
                    delta[k] = {"from": prev.get(k), "to": snapshot.get(k)}

        return {"snapshot": snapshot, "delta": delta, "rationale": rationale, "basic_info": basic_info}

    async def clarify(
        self,
        *,
        student_id: str,
        messages: list[dict[str, str]],
        on_chunk: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        user_text = "\n".join([m["content"] for m in messages if m["role"] == "user"])[-2000:]
        weak_points = _extract_weak_points(user_text)

        if is_llm_configured("clarify"):
            llm = get_llm_client_for("clarify")
            schema_hint = (
                '{"course": "...", "chapter": "...", "goals": "...", "weak_points": ["..."], '
                '"preferred_resources": ["lecture_doc","mindmap","question_bank","reading","practice_case","video_script"], '
                '"constraints": {"time_budget": "...", "difficulty": "..."}}'
            )
            data = await llm.chat_json(messages=messages, schema_hint=schema_hint, on_chunk=on_chunk)
            requirement = data or {}
            if not isinstance(requirement.get("weak_points"), list):
                requirement["weak_points"] = weak_points
        else:
            course = _extract_field(user_text, "课程")
            chapter = _extract_field(user_text, "章节")
            goals = _extract_field(user_text, "目标")
            requirement = {
                "course": course,
                "chapter": chapter,
                "goals": goals,
                "weak_points": weak_points,
                "preferred_resources": [a.resource_type for a in AGENTS],
                "constraints": {"time_budget": "", "difficulty": ""},
                "note": "未配置在线大模型：当前为启发式需求单，可在设置页填入模型信息后重新澄清。",
            }

        insert_learning_event(student_id, "clarify", {"weak_points": weak_points})
        return {"requirement": requirement}

    async def generate(
        self,
        *,
        student_id: str,
        requirement: dict[str, Any],
        on_chunk: Callable[[str], Awaitable[None]] | None = None,
    ) -> list[dict[str, Any]]:
        resources: list[dict[str, Any]] = []
        selected_agents = _requested_agents(requirement)
        generated_contents = await asyncio.gather(*[
            self._generate_one(spec=spec, requirement=requirement, student_id=student_id, on_chunk=on_chunk)
            for spec in selected_agents
        ])
        for spec, content in zip(selected_agents, generated_contents):
            file_id = new_id()
            rel_path = f"files/{student_id}/{file_id}.{spec.ext}"
            content_uri = _write_text(rel_path, content)
            meta = {"agent": spec.key, "requirement": requirement}
            item = insert_resource_item(
                student_id=student_id,
                type=spec.resource_type,
                title=_title_from_content(content, spec.title, requirement),
                tags=(requirement.get("weak_points") or [])[:5],
                content_uri=content_uri,
                meta=meta,
            )
            resources.append(item)

        constraints = requirement.get("constraints") if isinstance(requirement.get("constraints"), dict) else {}
        qa_item = None
        if _wants_quality_check(constraints):
            qa_item = await self._run_quality_check(
                resources=resources,
                requirement=requirement,
                student_id=student_id,
                on_chunk=on_chunk,
            )
        if qa_item:
            resources.append(qa_item)

        insert_learning_event(student_id, "generate", {"count": len(resources)})
        return resources

    async def stream_generate(
        self, *, student_id: str, requirement: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        selected_agents = _requested_agents(requirement)
        constraints = requirement.get("constraints") if isinstance(requirement.get("constraints"), dict) else {}
        run_quality_check = _wants_quality_check(constraints)
        agent_keys = [a.key for a in selected_agents] + (["quality_check"] if run_quality_check else [])
        yield {"type": "start", "ts": datetime.utcnow().isoformat(), "agents": agent_keys}
        resources: list[dict[str, Any]] = []
        for idx, spec in enumerate(selected_agents):
            yield {"type": "agent_start", "agent": spec.key, "title": spec.title, "index": idx}
            queue: asyncio.Queue[str] = asyncio.Queue()

            async def on_chunk(text: str) -> None:
                await queue.put(text)

            task = asyncio.create_task(
                self._generate_one(
                    spec=spec,
                    requirement=requirement,
                    student_id=student_id,
                    on_chunk=on_chunk,
                )
            )
            while not task.done() or not queue.empty():
                try:
                    text = await asyncio.wait_for(queue.get(), timeout=0.08)
                    yield {"type": "agent_chunk", "agent": spec.key, "text": text}
                except asyncio.TimeoutError:
                    continue
            content = await task
            file_id = new_id()
            rel_path = f"files/{student_id}/{file_id}.{spec.ext}"
            content_uri = _write_text(rel_path, content)
            meta = {"agent": spec.key, "requirement": requirement}
            item = insert_resource_item(
                student_id=student_id,
                type=spec.resource_type,
                title=_title_from_content(content, spec.title, requirement),
                tags=(requirement.get("weak_points") or [])[:5],
                content_uri=content_uri,
                meta=meta,
            )
            resources.append(item)
            yield {"type": "agent_done", "agent": spec.key, "resource": item}

        if not run_quality_check:
            insert_learning_event(student_id, "generate", {"count": len(resources)})
            yield {"type": "done", "ts": datetime.utcnow().isoformat()}
            return

        yield {"type": "agent_start", "agent": "quality_check", "title": "内容质检与防幻觉审查", "index": len(selected_agents)}
        qa_queue: asyncio.Queue[str] = asyncio.Queue()

        async def on_qa_chunk(text: str) -> None:
            await qa_queue.put(text)

        qa_task = asyncio.create_task(
            self._run_quality_check(
                resources=resources,
                requirement=requirement,
                student_id=student_id,
                on_chunk=on_qa_chunk,
            )
        )
        while not qa_task.done() or not qa_queue.empty():
            try:
                text = await asyncio.wait_for(qa_queue.get(), timeout=0.08)
                yield {"type": "agent_chunk", "agent": "quality_check", "text": text}
            except asyncio.TimeoutError:
                continue
        qa_item = await qa_task
        if qa_item:
            yield {"type": "agent_done", "agent": "quality_check", "resource": qa_item}

        insert_learning_event(student_id, "generate", {"count": len(resources) + (1 if qa_item else 0)})
        yield {"type": "done", "ts": datetime.utcnow().isoformat()}

    async def plan_path(
        self,
        *,
        student_id: str,
        goals: str | None,
        on_chunk: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        profile = get_latest_profile_snapshot(student_id) or {}
        weak_points = (profile.get("evidence") or {}).get("weak_points", [])
        resources = list_resources(student_id)
        usages = get_user_usages(student_id)
        events = get_user_events(student_id)
        tutor_questions = [e.get("payload", {}).get("question", "") for e in events if e.get("event_type") == "tutor"]
        disliked = [u for u in usages if u.get("action") == "dislike"]
        liked = [u for u in usages if u.get("action") == "like"]
        knowledge_mastery = mastery_data(student_id)
        exercise = exercise_summary(student_id)
        weak_mastery_nodes = [
            n for n in knowledge_mastery.get("nodes", [])
            if int(n.get("evidence_count") or 0) > 0 and float(n.get("current_mastery", 0)) < 60
        ][:4]

        resource_types = sorted({r.get("type", "") for r in resources if r.get("type")})
        available = resource_types
        recent_problem_text = "；".join([str(x) for x in weak_points + tutor_questions[-3:] if x])

        if is_llm_configured("plan"):
            llm = get_llm_client_for("plan")
            prompt = (
                "请为学生规划学习路径，输出 JSON："
                '{"title":"...","steps":[{"order":1,"objective":"...","resources":["lecture_doc"],"assessment":"..."}],'
                '"strategy":["..."],"dynamic_rules":["..."],"rationale":"..."}'
            )
            data = await llm.chat_json(
                messages=[
                    {"role": "user", "content": f"学生画像：{json.dumps(profile, ensure_ascii=False)}"},
                    {"role": "user", "content": f"学习目标：{goals or ''}"},
                    {"role": "user", "content": f"已生成资源类型：{json.dumps(resource_types, ensure_ascii=False)}"},
                    {"role": "user", "content": f"近期薄弱点与答疑问题：{recent_problem_text}"},
                    {"role": "user", "content": f"知识图谱掌握度：{json.dumps(knowledge_mastery.get('summary', {}), ensure_ascii=False)}；低掌握节点：{json.dumps(weak_mastery_nodes, ensure_ascii=False)}"},
                    {"role": "user", "content": f"资源反馈：喜欢 {len(liked)} 条，不喜欢 {len(disliked)} 条"},
                ],
                schema_hint=prompt,
                on_chunk=on_chunk,
            )
            plan = data or {}
            if not isinstance(plan.get("steps"), list) or not plan.get("steps"):
                raise RuntimeError("路径规划模型没有返回可执行步骤，本次没有生成固定路径")
            plan["analysis_mode"] = "llm"
            plan["evidence_summary"] = {
                "profile_snapshot_id": profile.get("id"),
                "weak_point_count": len(weak_points),
                "weak_mastery_node_count": len(weak_mastery_nodes),
                "exercise_attempts": int(exercise.get("total") or 0),
                "resource_count": len(resources),
                "feedback_count": len(usages),
                "goal": str(goals or "").strip(),
            }
        else:
            base_docs = [r for r in ["lecture_doc", "mindmap"] if r in available] or ["lecture_doc"]
            practice_resources = [r for r in ["question_bank", "practice_case"] if r in available] or ["question_bank"]
            review_resources = [r for r in ["reading", "video_script"] if r in available] or ["reading", "video_script"]
            weak_desc = "、".join(weak_points) if weak_points else "待进一步诊断"
            weak_mastery_desc = "、".join([n.get("name", "") for n in weak_mastery_nodes if n.get("name")]) or "暂无低掌握图谱节点"
            plan = {
                "title": "个性化学习路径与资源推送方案",
                "strategy": [
                    "先诊断薄弱点，再补齐概念框架，随后进入练习和实操迁移。",
                    "优先使用学生已经生成或最近使用过的资源，避免学习材料分散。",
                    "根据答疑问题、资源反馈和练习结果动态调整下一阶段资源权重。",
                    f"结合知识图谱掌握度，优先处理低掌握节点：{weak_mastery_desc}。",
                ],
                "steps": [
                    {
                        "order": 1,
                        "objective": "学习状态诊断与薄弱点确认",
                        "resources": ["question_bank"] if "question_bank" in available else practice_resources,
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
                        "resources": practice_resources,
                        "assessment": "同类题目正确率达到 80%，并能解释每个错误对应的知识点。",
                    },
                    {
                        "order": 4,
                        "objective": "通过实操案例完成知识迁移",
                        "resources": ["practice_case"] if "practice_case" in available else practice_resources,
                        "assessment": "提交一个小型实操作品或案例分析，并说明用到了哪些课程知识。",
                    },
                    {
                        "order": 5,
                        "objective": "拓展阅读与多模态复盘",
                        "resources": review_resources,
                        "assessment": "输出复盘笔记，说明下一轮学习还需要系统推送哪些资源。",
                    },
                ],
                "dynamic_rules": [
                    "若诊断题正确率低于 60%，回到第 2 步并提高讲解文档、思维导图、视频脚本的推荐权重。",
                    "若学生对某类资源连续点踩，降低该类型资源排序，并改推同知识点的其他模态资源。",
                    "若答疑中反复出现同一知识点，将该知识点加入下一轮路径的第 1 优先级。",
                    "若连续两次阶段任务达标，进入进阶阅读或实操案例，减少基础讲解资源推送。",
                ],
                "rationale": f"当前启发式规划；已识别弱点：{weak_desc}；知识图谱低掌握节点：{weak_mastery_desc}；已生成资源类型：{', '.join(resource_types) if resource_types else '暂无，将使用默认资源类型'}。",
            }

        if not is_llm_configured("plan"):
            plan = _evidence_path_plan(
                goals=str(goals or ""),
                weak_points=[str(item) for item in weak_points],
                weak_mastery_nodes=weak_mastery_nodes,
                tutor_questions=[str(item) for item in tutor_questions if item],
                resources=resources,
                accuracy=float(exercise.get("accuracy") or 0),
                attempts=int(exercise.get("total") or 0),
                liked_count=len(liked),
                disliked_count=len(disliked),
            )
        plan = _stabilize_path_plan(plan, available=available)
        insert_learning_event(
            student_id,
            "path_plan",
            {"title": plan.get("title"), "goals": goals, "path": plan},
        )
        return {"plan": plan}

    async def tutor_ask(
        self,
        *,
        student_id: str,
        question: str,
        context: dict[str, Any],
        on_chunk: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        profile = get_latest_profile_snapshot(student_id) or {}
        references = search_index(student_id=student_id, query=question, limit=3)
        reference_text = format_references(references)
        if is_llm_configured("tutor"):
            llm = get_llm_client_for("tutor")
            system = (
                "你是耐心的大学课程助教，优先基于知识库参考回答，用学生听得懂的话讲清概念。"
                "直接输出解答正文：不要写『说明』『备注』『本次回答主要基于……』这类前言，"
                "不要提及检索匹配度、知识库命中率、历史反馈统计等元信息；参考不足时同样不要写免责说明段落。"
                "正文用小标题与步骤组织，必要时给出图解建议与讲解要点。"
            )
            try:
                request = llm.chat_text(
                    system=system,
                    messages=[
                        {"role": "user", "content": f"学生画像：{json.dumps(profile, ensure_ascii=False)}"},
                        {"role": "user", "content": reference_text or "知识库未命中高相关片段。"},
                        {"role": "user", "content": f"问题：{question}"},
                        {"role": "user", "content": f"上下文：{json.dumps(context, ensure_ascii=False)}"},
                    ],
                    temperature=0.4,
                    on_chunk=on_chunk,
                )
                if on_chunk:
                    text = await request
                else:
                    response_budget = max(5.0, min(float(settings.llm_timeout_sec), 60.0))
                    text = await asyncio.wait_for(request, timeout=response_budget)
                answer = {"text": text}
                parsed = _parse_json_maybe(text)
                if parsed:
                    answer = parsed
            except Exception as exc:
                logger.warning("Tutor LLM unavailable; refusing synthetic fallback (%s)", type(exc).__name__)
                raise RuntimeError("智能辅导模型暂时不可用，本次没有生成回答，也没有写入伪造分析结果") from exc
        else:
            raise RuntimeError("智能辅导模型尚未配置，本次没有生成回答，也没有写入伪造分析结果")

        if isinstance(answer, dict):
            answer.setdefault("references", references)
        insert_learning_event(student_id, "tutor", {"question": question[:120]})
        return {"answer": answer}

    async def evaluate(
        self,
        *,
        student_id: str,
        on_chunk: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        profile = get_latest_profile_snapshot(student_id) or {}
        
        # 收集历史潜在问题与交互数据
        usages = get_user_usages(student_id)
        events = get_user_events(student_id)
        knowledge_mastery = mastery_data(student_id)
        exercise = exercise_summary(student_id)
        
        history_summary = {
            "total_resources_used": len(usages),
            "liked_resources": len([u for u in usages if u.get("action") == "like"]),
            "disliked_resources": len([u for u in usages if u.get("action") == "dislike"]),
            "tutor_questions_asked": len([e for e in events if e.get("event_type") == "tutor"]),
            "exercise_total": exercise.get("total", 0),
            "exercise_accuracy": exercise.get("accuracy", 0),
            "exercise_weak_tags": exercise.get("weak_tags", []),
            "recent_tutor_topics": [e.get("payload", {}).get("question") for e in events if e.get("event_type") == "tutor"][-5:]
        }
        
        if is_llm_configured("evaluate"):
            llm = get_llm_client_for("evaluate")
            schema_hint = (
                '{"summary":"...",'
                '"dimensions":{"knowledge_mastery":0,"stability":0,"transfer":0,"resource_efficiency":0},'
                '"weak_points":["..."],'
                '"recommendations":["..."],'
                '"next_actions":["..."]}'
            )
            data = await llm.chat_json(
                messages=[
                    {"role": "user", "content": f"学生画像快照：{json.dumps(profile, ensure_ascii=False)}"},
                    {"role": "user", "content": f"近期行为与潜在问题数据：{json.dumps(history_summary, ensure_ascii=False)}"},
                    {"role": "user", "content": f"知识图谱掌握度与复习预警：{json.dumps(knowledge_mastery, ensure_ascii=False)}"},
                    {"role": "user", "content": f"练习闭环统计与错题：{json.dumps(exercise, ensure_ascii=False)}"},
                    {
                        "role": "user",
                        "content": "请基于画像和本地行为数据输出学习效果评估报告（重点分析潜在问题并给出闭环优化建议）。",
                    },
                ],
                schema_hint=schema_hint,
                on_chunk=on_chunk,
            )
            report = data or {}
            report["profile_snapshot_id"] = profile.get("id")
            report["knowledge_mastery_summary"] = knowledge_mastery.get("summary", {})
            report["exercise_summary"] = exercise
            report["analysis_mode"] = "llm"
        else:
            report = {"analysis_mode": "evidence_rules"}

        dimensions = report.get("dimensions") if isinstance(report.get("dimensions"), dict) else {}
        normalized_dimensions = {
            "knowledge_mastery": _bounded_score(
                dimensions.get("knowledge_mastery"),
                knowledge_mastery.get("summary", {}).get("average_mastery", 0),
            ),
            "stability": _bounded_score(dimensions.get("stability"), exercise.get("accuracy", 0)),
            "transfer": _bounded_score(dimensions.get("transfer"), min(100, len(events) * 4)),
            "resource_efficiency": _bounded_score(
                dimensions.get("resource_efficiency"),
                round(len(usages) * 100 / max(1, len(list_resources(student_id))), 1),
            ),
        }
        overall_score = round(
            normalized_dimensions["knowledge_mastery"] * 0.35
            + normalized_dimensions["stability"] * 0.25
            + normalized_dimensions["transfer"] * 0.2
            + normalized_dimensions["resource_efficiency"] * 0.2,
            1,
        )
        weak_points = [str(item.get("tag")) for item in exercise.get("weak_tags", []) if item.get("tag")]
        weak_points.extend(
            str(item.get("name"))
            for item in knowledge_mastery.get("nodes", [])
            if float(item.get("current_mastery", 0)) < 60 and item.get("name")
        )
        weak_points.extend(str(item) for item in (profile.get("evidence") or {}).get("weak_points", []) if item)
        weak_points = list(dict.fromkeys(weak_points))[:8]
        if report.get("analysis_mode") == "evidence_rules":
            evidence_count = history_summary["exercise_total"] + history_summary["total_resources_used"] + len(events)
            report.update(
                {
                    "summary": (
                        f"本次评估读取 {evidence_count} 条本地行为证据、"
                        f"{history_summary['exercise_total']} 次练习和 {len(knowledge_mastery.get('nodes', []))} 个知识节点；"
                        f"练习正确率 {history_summary['exercise_accuracy']}%，综合得分 {overall_score}。"
                    ),
                    "findings": [
                        f"练习正确率为 {history_summary['exercise_accuracy']}%",
                        f"资源正反馈 {history_summary['liked_resources']} 次、负反馈 {history_summary['disliked_resources']} 次",
                        f"最近累计提问 {history_summary['tutor_questions_asked']} 次",
                    ],
                    "weak_points": weak_points,
                    "recommendations": _evidence_recommendations(
                        accuracy=float(history_summary["exercise_accuracy"] or 0),
                        weak_points=weak_points,
                        disliked=int(history_summary["disliked_resources"]),
                    ),
                    "profile_snapshot_id": profile.get("id"),
                    "knowledge_mastery_summary": knowledge_mastery.get("summary", {}),
                    "exercise_summary": exercise,
                }
            )
        report.update(
            {
                "dimensions": normalized_dimensions,
                "overall_score": overall_score,
                "mastery_level": _mastery_level(knowledge_mastery.get("summary", {}).get("average_mastery", 0)),
                "risk_level": _risk_level(overall_score),
                "evidence_summary": history_summary,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        insert_learning_event(student_id, "evaluate", {"report": report})
        return {"report": report}

    async def _run_quality_check(
        self,
        resources: list[dict[str, Any]],
        requirement: dict[str, Any],
        student_id: str,
        on_chunk: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict[str, Any] | None:
        audited_resources = _load_resource_bodies(resources)
        reference_query = " ".join(
            [
                str(requirement.get("course", "")),
                str(requirement.get("chapter", "")),
                " ".join(map(str, requirement.get("weak_points") or [])),
            ]
        )
        references = search_index(student_id=student_id, query=reference_query, limit=6)
        reference_text = format_references(references)
        deterministic_findings = _deterministic_content_audit(audited_resources, references)

        if is_llm_configured("generate"):
            llm = get_llm_client_for("generate")
            system = (
                "你是正文级内容质检与防幻觉智能体。必须阅读每份资源正文，逐项核验事实主张、引用、链接、"
                "标准版本、论文书目信息、题目答案和代码可执行性。不得只根据标题判断。"
                "输出严格 JSON，不要输出 Markdown 代码围栏。"
            )
            schema_hint = (
                '{"overall_status":"pass|warning|fail","risk_score":0,'
                '"summary":"...","resources":[{"resource_id":"...","title":"...",'
                '"status":"pass|warning|fail","verified_claims":["..."],'
                '"unsupported_claims":["..."],"citation_issues":["..."],'
                '"content_issues":["..."],"rewrite_instructions":["..."]}],'
                '"global_actions":["..."]}'
            )
            prompt = f"""
请对本次多智能体生成资源执行正文级审查。

需求单：
{json.dumps(requirement, ensure_ascii=False, indent=2)}

本地知识库检索依据：
{reference_text or "未检索到可靠依据；所有具体外部事实、版本、论文、链接均应标为待核验。"}

程序预检结果：
{json.dumps(deterministic_findings, ensure_ascii=False, indent=2)}

待审查资源正文：
{json.dumps(audited_resources, ensure_ascii=False, indent=2)}

审查要求：
1. 对每份资源给出独立结论，不得遗漏。
2. 无法由知识库依据支持的具体事实必须列入 unsupported_claims 或 citation_issues。
3. 发现错误答案、矛盾定义、虚假链接、具体版本/页码无依据时，status=fail。
4. 仅缺少来源但内容可能正确时，status=warning，并给出可执行 rewrite_instructions。
5. risk_score 范围 0-100，风险越高分数越高。
"""
            audit = await llm.chat_json(
                messages=[{"role": "user", "content": prompt}],
                schema_hint=schema_hint,
                on_chunk=on_chunk,
            )
        else:
            audit = _offline_audit_report(audited_resources, deterministic_findings)

        content = _audit_markdown(audit, references)

        file_id = new_id()
        rel_path = f"files/{student_id}/{file_id}.md"
        content_uri = _write_text(rel_path, content)
        meta = {
            "agent": "quality_check",
            "requirement": requirement,
            "audit": audit,
            "reference_count": len(references),
            "body_level": True,
        }
        item = insert_resource_item(
            student_id=student_id,
            type="quality_check",
            title="内容质检与防幻觉审查报告",
            tags=["质检", "防幻觉"],
            content_uri=content_uri,
            meta=meta,
        )
        return item

    async def _generate_one(
        self,
        *,
        spec: AgentSpec,
        requirement: dict[str, Any],
        student_id: str,
        on_chunk: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        profile = get_latest_profile_snapshot(student_id) or {}
        reference_query = " ".join(
            [
                str(requirement.get("course", "")),
                str(requirement.get("chapter", "")),
                " ".join(map(str, requirement.get("weak_points") or [])),
                spec.title,
            ]
        )
        reference_text = format_references(search_index(student_id=student_id, query=reference_query, limit=4))
        
        constraints = requirement.get("constraints") if isinstance(requirement.get("constraints"), dict) else {}
        use_glm = (
            spec.key == "quiz"
            and constraints.get("source") in {
                "exercise_custom_bank",
                "multimodal_chat_quiz",
                "path_stage_quiz",
            }
            and is_glm_configured()
        )
        model_configured = is_glm_configured() if use_glm else is_llm_configured("generate")
        if model_configured:
            llm = get_glm_client() if use_glm else get_llm_client_for("generate")
            
            # 引入主工程优质Prompt模板
            if spec.key == "lecture":
                system = (
                    "你是高校课程资源生成智能体，负责生成严谨、结构完整、适合学生自学的中文 Markdown 课程讲解文档。"
                    "不要编造不存在的教材页码、论文和链接；不确定的事实必须标注“待核验”。"
                )
                user_content = f"""请基于以下信息生成一份“专业课程讲解文档”。
学生画像：{json.dumps(profile, ensure_ascii=False)}
需求单：{json.dumps(requirement, ensure_ascii=False)}
课程知识库参考：
{reference_text or "未检索到高相关参考，请仅基于确定知识生成，并标注待核验内容。"}

输出要求：
1. 只输出 Markdown，不要输出解释性前言。
2. 必须包含：文档概览、学习目标、先修知识、核心概念、关键公式/流程/模型、标准学习流程、针对知识短板的讲解、专业案例、可模仿模板、常见误区、课堂练习、自检清单、课后复盘任务。
3. 核心概念至少拆成 3 到 6 个小节，每节包含“定义/作用/例子/易错点/自测题”。
4. 内容要针对学生画像，不要泛泛而谈；若学生基础弱，先给直观类比，再给正式定义。"""
            
            elif spec.key == "reading":
                system = (
                    "你是高校课程拓展阅读规划智能体，负责生成分层、可执行、带产出要求的中文 Markdown 阅读材料。"
                    "不要编造真实链接、论文页码和具体版本；不确定来源必须标注“待核验”。"
                )
                user_content = f"""请基于以下信息生成一份“拓展阅读材料”。
学生画像：{json.dumps(profile, ensure_ascii=False)}
需求单：{json.dumps(requirement, ensure_ascii=False)}
课程知识库参考：
{reference_text or "未检索到高相关参考，请仅基于确定知识生成，并标注待核验内容。"}

输出要求：
1. 只输出 Markdown，不要输出解释性前言。
2. 必须包含：阅读材料概览、入门阅读、案例阅读、进阶阅读、前沿阅读方向、阅读问题、阶段产出、7 天阅读安排、阅读后任务、学习成果评价标准、防幻觉与来源核验。
3. 每类阅读都要说明“适合解决的薄弱点、阅读方法、读后产物”，不要只列书名或资料名。"""

            elif spec.key == "mindmap":
                system = (
                    "你是知识结构建模智能体，负责把课程主题转成可解析的 Mermaid mindmap 和配套学习说明。"
                    "输出必须严谨，不要引入与课程无关的分支。"
                )
                user_content = f"""请基于以下信息生成一份“知识点思维导图”。
学生画像：{json.dumps(profile, ensure_ascii=False)}
需求单：{json.dumps(requirement, ensure_ascii=False)}
课程知识库参考：
{reference_text or "未检索到高相关参考，请仅基于确定知识生成。"}

输出要求：
1. 只输出 Markdown。
2. 必须先给一个 Mermaid mindmap 代码块，代码块内第一行必须是 mindmap。
3. Mermaid 使用 2 个空格表示层级，根节点为课程或章节名称；必须包含“核心概念、关键流程、易错点、练习路径、拓展方向”五个一级分支。
4. Mermaid 后补充“节点学习顺序”和“薄弱点定位说明”。
5. 结构严格控制在三层以内：根节点 → 一级分支（5-6 个）→ 二级节点（每个分支 3-5 个）→ 三级节点只在确有具体方法或例子时出现（每个二级节点最多 3 个）。
6. 每个节点写成名词性短语，不超过 10 个字，禁止整句话、禁止句号逗号等标点；同一父节点下的子节点必须互斥，不许同义重复。
7. 叶子节点必须是可复习的知识点（概念、步骤、公式、易错点），不要写“介绍”“概述”“相关内容”这类空话。"""

            elif spec.key == "quiz":
                quiz_types, quiz_counts, quiz_total = _quiz_generation_config(requirement)
                quiz_type_text = "、".join(f"{_QUIZ_TYPE_LABELS[item]} {quiz_counts[item]} 道" for item in quiz_types)
                system = (
                    "你是题库生成智能体，负责生成可被系统解析的个性化练习题。"
                    "必须严格遵守用户选择的题型和数量，只输出 JSON，不要输出 Markdown、注释或解释性前言。"
                )
                user_content = f"""请基于以下信息生成一份“个性化题库”。
学生画像：{json.dumps(profile, ensure_ascii=False)}
需求单：{json.dumps(requirement, ensure_ascii=False)}
课程知识库参考：
{reference_text or "未检索到高相关参考，请仅基于确定知识生成。"}

输出 JSON 结构必须为：
{{
  "meta": {{"course": "...", "chapter": "...", "weak_points": ["..."], "generated_by": "quiz"}},
  "questions": [{{"type": "题型英文标识", "stem": "题干", "options": ["A. 选项内容", "B. 选项内容"], "answer": "答案", "analysis": "解析", "difficulty": 1, "tags": ["知识点"]}}],
  "review_plan": ["..."]
}}

本次只能生成以下题型，禁止添加未选择的题型：{quiz_type_text}。
总题量必须为 {quiz_total} 道。选择题的每个选项必须是数组中的独立元素，只保留一个 A/B/C/D 标号，不得把多个选项拼成一行。代码必须放进题干中的独立代码围栏，并保留换行和缩进。题目必须围绕薄弱点递进。
数学书写必须符合 LaTeX 规范：行内公式写成 $...$，独立公式写成 $$...$$；分数用 \\frac{{分子}}{{分母}}，乘幂用 ^{{}}、下标用 _{{}}，开方用 \\sqrt{{}}，积分用 \\int_{{下限}}^{{上限}}，求和用 \\sum_{{下限}}^{{上限}}，极限用 \\lim_{{x \\to 0}}，希腊字母用 \\alpha、\\beta、\\theta；禁止用 x^2、1/2、√、Σ、∫、≤、≥ 这类纯文本或 Unicode 符号直接拼公式。"""

            elif spec.key == "practice":
                system = (
                    "你是实操案例智能体，负责把课程知识转成可运行、可复现实操任务。"
                    "输出 Markdown，代码必须放在带语言标识的代码块中。"
                )
                user_content = f"""请基于以下信息生成一份“代码/实操案例”。
学生画像：{json.dumps(profile, ensure_ascii=False)}
需求单：{json.dumps(requirement, ensure_ascii=False)}
课程知识库参考：
{reference_text or "未检索到高相关参考，请仅基于确定知识生成。"}

输出要求：
1. 只输出 Markdown。
2. 必须包含：案例总览、环境准备、3 个由易到难的实操任务、完整代码或操作步骤、运行结果示例、常见错误与排查、扩展挑战、提交物要求。
3. 每个实操任务都要标注对应知识点、难度、预计耗时和验收标准。"""

            elif spec.key == "video":
                system = (
                    "你是多模态教学视频脚本智能体，负责生成可拍摄、可动画化的教学视频脚本。"
                    "输出 Markdown，重点体现画面、口播、动画和互动检查。"
                )
                user_content = f"""请基于以下信息生成一份“多模态视频/动画脚本”。
学生画像：{json.dumps(profile, ensure_ascii=False)}
需求单：{json.dumps(requirement, ensure_ascii=False)}
课程知识库参考：
{reference_text or "未检索到高相关参考，请仅基于确定知识生成。"}

输出要求：
1. 只输出 Markdown。
2. 必须包含：视频定位、目标观众、总时长、分镜表、关键画面设计、动画建议、口播稿、暂停互动题、素材清单、制作注意事项。
3. 分镜表至少 6 个镜头，每个镜头包含时间段、画面、动画/操作、口播、对应知识点。"""

            else:
                system = (
                    "你是多智能体系统中的一个角色。请根据需求单生成高质量学习资源。"
                    "输出应可直接用于大学生学习，结构清晰，可操作。"
                )
                user_content = f"""你的角色：{spec.title}
需求单：{json.dumps(requirement, ensure_ascii=False)}
学生画像：{json.dumps(profile, ensure_ascii=False)}
课程知识库参考：
{reference_text or "未检索到高相关参考。"}
请生成对应资源内容。"""

            content = await llm.chat_text(
                system=system,
                messages=[{"role": "user", "content": user_content}],
                temperature=0.6,
                on_chunk=on_chunk,
            )
            if spec.ext == "json":
                parsed = _parse_json_maybe(content)
                if parsed is not None:
                    if spec.key == "quiz":
                        parsed = _constrain_quiz_payload(parsed, requirement)
                    return json.dumps(parsed, ensure_ascii=False, indent=2)
                raise RuntimeError("模型返回的题库 JSON 格式异常，系统已停止保存损坏文件，请重新生成。")
            return content

        if use_glm:
            raise RuntimeError("多模态智能出题仅使用智谱 GLM，请先配置 GLM_TEXT_API_KEY 或 GLM_API_KEY")
        raise RuntimeError("内容生成模型尚未配置，本次没有生成模板资源或演示题库")
