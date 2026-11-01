from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.streaming import stream_live_operation, stream_response
from app.agents import Orchestrator
from app.core.config import settings
from app.core.ids import new_id
from app.repo import delete_resource_item, list_resources
from app.schemas import ApiResponse, ClarifyRequest, GenerateRequest
from app.services.keyword_extract import extract_keywords
from app.services.learning_state import workshop_overview


router = APIRouter(prefix="/api/workshop", tags=["workshop"])
orchestrator = Orchestrator()


@router.get("/overview", response_model=ApiResponse)
async def overview(student_id: str = Query(..., min_length=1)) -> ApiResponse:
    request_id = new_id()
    try:
        return ApiResponse(request_id=request_id, success=True, data=workshop_overview(student_id))
    except Exception as e:
        return ApiResponse(
            request_id=request_id,
            success=False,
            error={"code": "WORKSHOP_OVERVIEW_ERROR", "message": str(e)},
        )


def _read_resource_text(content_uri: str) -> str:
    uri = content_uri.strip().lstrip("/")
    if not uri:
        return ""
    data_root = settings.data_path.resolve()
    candidate = (settings.data_path / uri).resolve()
    try:
        candidate.relative_to(data_root)
    except ValueError:
        return ""
    if not candidate.is_file():
        return ""
    try:
        return candidate.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


@router.get("/keywords", response_model=ApiResponse)
async def resource_keywords(
    resource_id: str = Query(..., min_length=1),
    student_id: str = Query(..., min_length=1),
) -> ApiResponse:
    request_id = new_id()
    try:
        item = next((r for r in list_resources(student_id) if r.get("id") == resource_id), None)
        if item is None:
            return ApiResponse(
                request_id=request_id,
                success=False,
                error={"code": "RESOURCE_NOT_FOUND", "message": "未找到这份档案记录"},
            )
        text = _read_resource_text(str(item.get("content_uri") or ""))
        keywords = extract_keywords(text)
        return ApiResponse(
            request_id=request_id,
            success=True,
            data={
                "resource_id": resource_id,
                "title": item.get("title", ""),
                "type": item.get("type", ""),
                "keywords": keywords,
                "has_content": bool(text.strip()),
            },
        )
    except Exception as e:
        return ApiResponse(
            request_id=request_id,
            success=False,
            error={"code": "RESOURCE_KEYWORDS_ERROR", "message": str(e)},
        )


@router.delete("/resources/{resource_id}", response_model=ApiResponse)
async def delete_resource(resource_id: str, student_id: str = Query(..., min_length=1)) -> ApiResponse:
    request_id = new_id()
    try:
        removed = delete_resource_item(student_id=student_id, resource_id=resource_id)
        if removed is None:
            return ApiResponse(
                request_id=request_id,
                success=False,
                error={"code": "RESOURCE_NOT_FOUND", "message": "未找到这份档案记录"},
            )
        return ApiResponse(request_id=request_id, success=True, data=removed)
    except Exception as e:
        return ApiResponse(
            request_id=request_id,
            success=False,
            error={"code": "RESOURCE_DELETE_ERROR", "message": str(e)},
        )


@router.post("/clarify", response_model=ApiResponse)
async def clarify(req: ClarifyRequest) -> ApiResponse:
    request_id = new_id()
    try:
        result = await orchestrator.clarify(student_id=req.student_id, messages=[m.model_dump() for m in req.messages])
        return ApiResponse(request_id=request_id, success=True, data=result)
    except Exception as e:
        return ApiResponse(request_id=request_id, success=False, error={"code": "CLARIFY_ERROR", "message": str(e)})


@router.post("/clarify/stream")
async def clarify_stream(req: ClarifyRequest):
    request_id = new_id()

    async def work(on_chunk):
        return await orchestrator.clarify(
            student_id=req.student_id,
            messages=[m.model_dump() for m in req.messages],
            on_chunk=on_chunk,
        )

    def text(result: dict) -> str:
        requirement = result.get("requirement", result)
        return json.dumps(requirement, ensure_ascii=False, indent=2)

    return stream_response(
        stream_live_operation(
            request_id=request_id,
            work=work,
            start_message="开始澄清资源生成需求",
            final_key="result",
            fallback_text=text,
            chunk_path="requirement_text",
        )
    )


@router.post("/generate")
async def generate(req: GenerateRequest):
    request_id = new_id()

    if req.stream:
        async def event_stream() -> AsyncIterator[str]:
            try:
                async for evt in orchestrator.stream_generate(student_id=req.student_id, requirement=req.requirement):
                    yield f"event: message\ndata: {json.dumps({'request_id': request_id, 'event': evt}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'request_id': request_id, 'error': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    try:
        resources = await orchestrator.generate(student_id=req.student_id, requirement=req.requirement)
        return ApiResponse(request_id=request_id, success=True, data={"resources": resources})
    except Exception as e:
        return ApiResponse(request_id=request_id, success=False, error={"code": "GENERATE_ERROR", "message": str(e)})

