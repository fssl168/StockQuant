# -*- coding: utf-8 -*-
"""F029 审计日志路由 — /api/audit"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from stockquant.api.deps import get_current_user
from stockquant.api.schemas import UserToken

router = APIRouter(tags=["审计日志"])
logger = logging.getLogger("stockquant.audit")


@router.get("/audit/logs", response_model=list[Dict[str, Any]], summary="操作审计日志")
async def list_audit_logs(
    _user: UserToken = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """获取操作审计日志（仅 ADMIN 可查全部）。"""
    try:
        from stockquant.api.routers.auth import _get_db_url
        from stockquant.persistence.repository import list_op_audit_logs

        db_url = _get_db_url()
        user_id = _user.get("sub", "anonymous")
        logs = list_op_audit_logs(db_url, user_id=user_id, limit=limit)
        return logs
    except Exception as e:
        logger.error("Failed to load audit logs: %s", e)
        return []


@router.get("/audit/logs/all", response_model=list[Dict[str, Any]], summary="全部审计日志（ADMIN）")
async def list_all_audit_logs(
    _user: UserToken = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    user_id: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """获取全部操作审计日志（需 ADMIN 权限）。"""
    if _user.get("role") != "ADMIN":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        from stockquant.api.routers.auth import _get_db_url
        from stockquant.persistence.repository import list_op_audit_logs

        db_url = _get_db_url()
        # ADMIN 可查全部用户日志（user_id=None 时不限制）
        logs = list_op_audit_logs(db_url, user_id=user_id, limit=limit)
        if resource_type:
            logs = [l for l in logs if l.get("resource_type") == resource_type]
        return logs[:limit]
    except Exception as e:
        logger.error("Failed to load audit logs: %s", e)
        return []
