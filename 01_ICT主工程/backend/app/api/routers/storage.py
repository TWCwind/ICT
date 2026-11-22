from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.ids import new_id
from app.schemas import ApiResponse
from app.storage import backend_name
from app.storage.migration_window import MIGRATION_WINDOW, MigrationWindowError

router = APIRouter(prefix="/api/storage", tags=["storage"])


def require_migration_admin(x_migration_admin_key: str | None = Header(default=None)) -> None:
    configured = os.environ.get("MIGRATION_ADMIN_KEY", "")
    if not configured:
        raise HTTPException(status_code=503, detail="迁移管理接口未配置管理员密钥")
    if not x_migration_admin_key or not hmac.compare_digest(x_migration_admin_key, configured):
        raise HTTPException(status_code=403, detail="无迁移管理权限")


class MigrateActionRequest(BaseModel):
    action: str = Field(..., min_length=1)


def _status_payload() -> dict:
    payload = MIGRATION_WINDOW.status_snapshot()
    payload["current_backend"] = backend_name()
    return payload


@router.get("/migration-window")
def get_migration_window(_: None = Depends(require_migration_admin)):
    """迁移窗口当前状态（phase / frozen / 迁移与核对结果 / 差异明细）。"""
    return ApiResponse(request_id=new_id(), success=True, data=_status_payload())


@router.post("/migrate")
def run_migrate(request: MigrateActionRequest, _: None = Depends(require_migration_admin)):
    """在线迁移控制：prepare 冻结写入，commit 迁移+核对+切换，abort 解冻回滚。"""
    action = request.action.strip().lower()
    try:
        if action == "prepare":
            data = MIGRATION_WINDOW.prepare()
        elif action == "commit":
            data = MIGRATION_WINDOW.commit()
        elif action == "abort":
            data = MIGRATION_WINDOW.abort()
        else:
            return ApiResponse(
                request_id=new_id(),
                success=False,
                data=None,
                error={
                    "code": "MIGRATION_UNKNOWN_ACTION",
                    "message": "action 只支持 prepare / commit / abort",
                },
            )
    except MigrationWindowError as exc:
        return ApiResponse(
            request_id=new_id(),
            success=False,
            data=_status_payload(),
            error={"code": exc.code, "message": str(exc)},
        )
    data["current_backend"] = backend_name()
    return ApiResponse(request_id=new_id(), success=True, data=data)
