# -*- coding: utf-8 -*-
"""F020 GAP-M6 — CollectorAuditLog 查询 API 路由

提供对采集器审计日志的查询与统计能力：
- 查询审计条目（支持过滤 + 分页）
- 返回统计摘要
- 按采集器/数据源分组计数
- 清空审计日志（管理员）

路径前缀：/api/pipeline/audit/*
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from stockquant.api.deps import get_admin_user, get_current_user
from stockquant.api.schemas import UserToken

router = APIRouter(tags=["采集审计日志"])
logger = logging.getLogger("stockquant.api.pipeline_audit")


def _get_audit_log_safe():
    """安全获取 CollectorAuditLog 单例（导入失败时抛 503）"""
    try:
        from stockquant.ai.collectors.audit_log import get_audit_log, CollectorAuditLog
        return get_audit_log(), CollectorAuditLog
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"CollectorAuditLog 模块未安装: {exc}",
        )


@router.get("/pipeline/audit", summary="查询审计日志")
async def query_audit(
    _user: UserToken = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000, description="最多返回条目数"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    collector: Optional[str] = Query(None, description="按采集器过滤"),
    action: Optional[str] = Query(None, description="按操作类型过滤"),
    source: Optional[str] = Query(None, description="按数据源过滤"),
    result: Optional[str] = Query(
        None,
        description="按结果过滤（success/failure/partial/skipped）",
    ),
):
    try:
        log, CollectorAuditLogCls = _get_audit_log_safe()
        if result and result not in CollectorAuditLogCls.VALID_RESULTS:
            raise HTTPException(
                status_code=400,
                detail=f"无效 result 值: {result}，可选: {', '.join(CollectorAuditLogCls.VALID_RESULTS)}",
            )
        entries = log.query(
            limit=limit,
            offset=offset,
            collector=collector,
            action=action,
            source=source,
            result=result,
        )
        return {
            "count": len(entries),
            "offset": offset,
            "limit": limit,
            "entries": [e.to_dict() for e in entries],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("查询审计日志失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/pipeline/audit/stats", summary="审计日志统计")
async def get_stats(
    _user: UserToken = Depends(get_current_user),
):
    try:
        log, _ = _get_audit_log_safe()
        return {
            "stats": log.stats(),
            "summary": log.summary(),
            "success_rate": log.success_rate(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("获取审计统计失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/pipeline/audit/by-collector", summary="按采集器分组计数")
async def count_by_collector(
    _user: UserToken = Depends(get_current_user),
):
    try:
        log, _ = _get_audit_log_safe()
        return log.count_by_collector()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("按采集器分组失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/pipeline/audit/by-source", summary="按数据源分组计数")
async def count_by_source(
    _user: UserToken = Depends(get_current_user),
):
    try:
        log, _ = _get_audit_log_safe()
        return log.count_by_source()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("按数据源分组失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/pipeline/audit", summary="清空审计日志")
async def clear_audit(
    _user: UserToken = Depends(get_admin_user),
):
    try:
        log, _ = _get_audit_log_safe()
        cleared = log.clear()
        logger.warning(
            "审计日志已被清空（操作者: %s）: 清除 %d 条",
            _user.sub, cleared,
        )
        return {"success": True, "cleared": cleared}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("清空审计日志失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
