# -*- coding: utf-8 -*-
"""F029 策略路由 — 策略 CRUD"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

logger = logging.getLogger("stockquant.api.strategy")

router = APIRouter()

# 存储引用（由 main.py 注入）
_strategies: dict = {}


def set_storage(storage: dict):
    global _strategies
    _strategies = storage


# ====================================================================
# 端点
# ====================================================================

@router.post("/strategy", response_model=dict, summary="创建策略")
async def create_strategy(payload: dict):
    """
    创建策略。

    MVP 将策略代码以字符串形式存储，暂不验证语法。
    """
    strategy_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    strategy = {
        "id": strategy_id,
        "name": payload.get("name", "未命名策略"),
        "code": payload.get("code", ""),
        "description": payload.get("description", ""),
        "created_at": now,
        "updated_at": now,
    }

    _strategies[strategy_id] = strategy
    logger.info(f"策略已创建: {strategy_id} ({strategy['name']})")

    return strategy


@router.get("/strategy", response_model=list[dict], summary="策略列表")
async def list_strategies():
    """获取所有策略"""
    return list(_strategies.values())


@router.get("/strategy/{strategy_id}", response_model=dict, summary="策略详情")
async def get_strategy(strategy_id: str):
    """获取指定策略的详细信息"""
    strategy = _strategies.get(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")
    return strategy


@router.put("/strategy/{strategy_id}", response_model=dict, summary="更新策略")
async def update_strategy(strategy_id: str, payload: dict):
    """更新策略"""
    if strategy_id not in _strategies:
        raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")

    strategy = _strategies[strategy_id]
    strategy["name"] = payload.get("name", strategy["name"])
    strategy["code"] = payload.get("code", strategy["code"])
    strategy["description"] = payload.get("description", strategy["description"])
    strategy["updated_at"] = datetime.now().isoformat()

    logger.info(f"策略已更新: {strategy_id}")
    return strategy


@router.delete("/strategy/{strategy_id}", response_model=dict, summary="删除策略")
async def delete_strategy(strategy_id: str):
    """删除策略"""
    if strategy_id not in _strategies:
        raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")

    del _strategies[strategy_id]
    logger.info(f"策略已删除: {strategy_id}")
    return {"success": True, "strategy_id": strategy_id}
