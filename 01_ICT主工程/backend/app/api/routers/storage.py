from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.ids import new_id
from app.schemas import ApiResponse
from app.storage import backend_name
from app.storage.migration_window import MIGRATION_WINDOW, MigrationWindowError

router = APIRouter(prefix="/api/storage", tags=["storage"])


class MigrateActionRequest(BaseModel):
    action: str = Field(..., min_length=1)


def _status_payload() -> dict:
    payload = MIGRATION_WINDOW.status_snapshot()
    payload["current_backend"] = backend_name()
    return payload


@router.get("/migration-window")
def get_migration_window():
    """迁移窗口当前状态（phase / frozen / 迁移与核对结果 / 差异明细）。"""
    return ApiResponse(request_id=new_id(), success=True, data=_status_payload())


@router.post("/migrate")
def run_migrate(request: MigrateActionRequest):
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
