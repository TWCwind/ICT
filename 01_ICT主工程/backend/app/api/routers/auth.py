"""登录与会话隔离接口。

端点：GET /api/auth/config（前端据此切换登录门形态）、GET /api/auth/captcha、
POST /api/auth/login、GET /api/auth/me。

enforce_student_isolation 是挂在 main.py include_router 上的全接口依赖：
AUTH_REQUIRED=1 时，凡是请求里出现 student_id（query / path / JSON body
顶层）的接口都必须携带与该学号一致的会话令牌；不一致 403、缺失/无效 401。
不含 student_id 的接口（/health、/api/auth/*、诊断类）放行。
"""
from __future__ import annotations

import base64
import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core import security
from app.core.config import settings
from app.core.ids import new_id
from app.schemas import ApiResponse


router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    student_id: str = Field(min_length=1)
    captcha_id: str = Field(min_length=1)
    captcha_code: str = Field(min_length=1)


@router.get("/config", response_model=ApiResponse)
async def auth_config() -> ApiResponse:
    return ApiResponse(
        request_id=new_id(),
        success=True,
        data={"auth_required": settings.auth_required},
    )


@router.get("/captcha", response_model=ApiResponse)
async def auth_captcha() -> ApiResponse:
    captcha_id, code = security.create_captcha()
    svg = security.captcha_svg(code)
    image = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return ApiResponse(
        request_id=new_id(),
        success=True,
        data={"captcha_id": captcha_id, "image": image},
    )


@router.post("/login", response_model=ApiResponse)
async def auth_login(req: LoginRequest) -> ApiResponse:
    student_id = req.student_id.strip()
    if not student_id:
        return ApiResponse(
            request_id=new_id(),
            success=False,
            error={"code": "AUTH_LOGIN_ERROR", "message": "学号不能为空"},
        )
    if not security.consume_captcha(req.captcha_id, req.captcha_code):
        return ApiResponse(
            request_id=new_id(),
            success=False,
            error={"code": "AUTH_CAPTCHA_INVALID", "message": "验证码错误或已过期，请刷新后重试"},
        )
    token, expires_at = security.issue_token(student_id)
    return ApiResponse(
        request_id=new_id(),
        success=True,
        data={"student_id": student_id, "token": token, "expires_at": expires_at},
    )


@router.get("/me", response_model=ApiResponse)
async def auth_me(request: Request) -> ApiResponse:
    payload = security.verify_token(_token_from_request(request) or "")
    if payload is None:
        raise HTTPException(status_code=401, detail="缺少或无效的会话令牌，请先登录")
    return ApiResponse(
        request_id=new_id(),
        success=True,
        data={"student_id": payload["student_id"], "expires_at": payload.get("exp")},
    )


def _token_from_request(request: Request) -> str | None:
    header_token = request.headers.get("x-session-token")
    if header_token and header_token.strip():
        return header_token.strip()
    authorization = request.headers.get("authorization") or ""
    if authorization.lower().startswith("bearer "):
        candidate = authorization[7:].strip()
        if candidate:
            return candidate
    return None


async def enforce_student_isolation(request: Request) -> None:
    """会话级多用户隔离校验（AUTH_REQUIRED=1 时生效，默认关闭）。"""
    if not settings.auth_required:
        return
    path = request.url.path
    if path == "/health" or path.startswith("/api/auth/"):
        return
    student_id = request.query_params.get("student_id") or request.path_params.get("student_id")
    if not student_id:
        raw = await request.body()
        if raw:
            try:
                data = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                data = None
            if isinstance(data, dict):
                student_id = data.get("student_id")
    if not student_id:
        return
    payload = security.verify_token(_token_from_request(request) or "")
    if payload is None:
        raise HTTPException(status_code=401, detail="缺少或无效的会话令牌，请先登录")
    if payload.get("student_id") != student_id:
        raise HTTPException(status_code=403, detail="会话学号与目标学号不一致，已拒绝跨学号访问")
