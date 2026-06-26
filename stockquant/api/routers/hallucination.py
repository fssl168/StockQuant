# -*- coding: utf-8 -*-
"""F020 反幻觉系统 API — /api/hallucination"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query

from stockquant.api.deps import get_current_user, get_admin_user
from stockquant.api.schemas import UserToken
from stockquant.ai.hallucination.database import HallucinationDatabase
from stockquant.ai.hallucination.modes import VerificationMode

router = APIRouter(tags=["反幻觉系统"])
logger = logging.getLogger("stockquant.api.hallucination")

# 模块级单例
_db: Optional[HallucinationDatabase] = None
_config: Dict[str, Any] = {
    "mode": "STANDARD",
    "threshold": 0.5,
}


def init_database(database: HallucinationDatabase) -> None:
    """由 main.py 注入"""
    global _db
    _db = database


@router.get("/hallucination/config", summary="获取幻觉检测配置")
async def get_config(
    _user: UserToken = Depends(get_current_user),
):
    return _config


@router.put("/hallucination/config", summary="配置幻觉检测模式")
async def update_config(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
):
    mode = payload.get("mode", "STANDARD")
    if mode not in [m.value for m in VerificationMode]:
        raise HTTPException(status_code=400, detail=f"无效模式: {mode}，可选: {', '.join(m.value for m in VerificationMode)}")
    _config["mode"] = mode
    _config["threshold"] = payload.get("threshold", 0.5)
    return {"success": True, "config": _config}


@router.get("/hallucination/records", response_model=List[Dict[str, Any]], summary="查询幻觉记录")
async def list_records(
    _user: UserToken = Depends(get_current_user),
    agent: Optional[str] = Query(None, description="按 Agent 过滤"),
    hallucination_type: Optional[str] = Query(None, description="按类型过滤"),
    limit: int = Query(50, ge=1, le=200, description="最大返回条数"),
):
    if _db is None:
        raise HTTPException(status_code=503, detail="反幻觉数据库未初始化")
    return _db.query(agent=agent, hallucination_type=hallucination_type, limit=limit)


@router.post("/hallucination/record", summary="手动记录幻觉事件")
async def record_hallucination(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
):
    if _db is None:
        raise HTTPException(status_code=503, detail="反幻觉数据库未初始化")
    required_fields = ["agent", "input_summary", "hallucination_type"]
    for field in required_fields:
        if field not in payload:
            raise HTTPException(status_code=400, detail=f"缺少必填字段: {field}")
    record_id = _db.record(payload)
    return {"success": True, "id": record_id}


@router.get("/hallucination/analysis", summary="幻觉模式分析")
async def analyze_patterns(
    _user: UserToken = Depends(get_current_user),
):
    if _db is None:
        raise HTTPException(status_code=503, detail="反幻觉数据库未初始化")
    return _db.analyze_patterns()


@router.get("/hallucination/suggestions", summary="Prompt 优化建议")
async def get_suggestions(
    _user: UserToken = Depends(get_current_user),
):
    if _db is None:
        raise HTTPException(status_code=503, detail="反幻觉数据库未初始化")
    return _db.optimize_prompt()
