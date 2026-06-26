# -*- coding: utf-8 -*-
"""F029 策略路由 — 策略 CRUD"""


import logging
import uuid
from datetime import datetime

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from stockquant.api.deps import get_trader_user
from stockquant.api.schemas import MessageResponse, StrategyCreate, StrategyInfo, UserToken
from stockquant.persistence.persistent_store import StrategyStore

logger = logging.getLogger(__name__)

router = APIRouter()
admin_router = APIRouter()

# 存储引用（由 main.py 注入）
_strategies: StrategyStore = {}  # type: ignore[assignment]


def set_storage(storage: StrategyStore):
    global _strategies
    _strategies = storage


# ====================================================================
# 端点
# ====================================================================

@router.post("/strategy", response_model=StrategyInfo, summary="创建策略")
async def create_strategy(payload: StrategyCreate, _user: UserToken = Depends(get_trader_user)):
    """
    创建策略。

    MVP 将策略代码以字符串形式存储，暂不验证语法。
    """
    strategy_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    strategy = {
        "id": strategy_id,
        "name": payload.name,
        "code": payload.code,
        "description": payload.description,
        "user_id": _user.sub,
        "created_at": now,
        "updated_at": now,
    }

    _strategies[strategy_id] = strategy
    logger.info(f"策略已创建: {strategy_id} ({strategy['name']})")

    return strategy


@router.get("/strategy", response_model=List[StrategyInfo], summary="策略列表")
async def list_strategies() -> List[StrategyInfo]:
    """获取所有策略"""
    return list(_strategies.values())


@router.get("/strategy/{strategy_id}", response_model=StrategyInfo, summary="策略详情")
async def get_strategy(strategy_id: str) -> StrategyInfo:
    """获取指定策略的详细信息"""
    strategy = _strategies.get(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")
    return strategy


@router.put("/strategy/{strategy_id}", response_model=StrategyInfo, summary="更新策略")
async def update_strategy(strategy_id: str, payload: Dict[str, Any], _user: UserToken = Depends(get_trader_user)):
    """更新策略"""
    if strategy_id not in _strategies:
        raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")

    strategy = _strategies[strategy_id]
    if "name" in payload:
        strategy["name"] = payload["name"]
    if "code" in payload:
        strategy["code"] = payload["code"]
    if "description" in payload:
        strategy["description"] = payload["description"]
    strategy["updated_at"] = datetime.now().isoformat()
    # 触发 StrategyStore.__setitem__ 写入数据库
    _strategies[strategy_id] = strategy

    logger.info(f"策略已更新: {strategy_id}")
    return strategy


@router.delete("/strategy/{strategy_id}", response_model=MessageResponse, summary="删除策略")
async def delete_strategy(strategy_id: str, _user: UserToken = Depends(get_trader_user)) -> MessageResponse:
    """删除策略"""
    if strategy_id not in _strategies:
        raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")

    del _strategies[strategy_id]
    logger.info(f"策略已删除: {strategy_id}")
    return {"success": True, "strategyId": strategy_id}


@admin_router.delete("/strategy/clear-all", response_model=MessageResponse, summary="清空所有策略")
async def clear_all_strategies() -> MessageResponse:
    """删除所有已保存的策略（包括内存缓存和数据库）"""
    global _strategies
    from stockquant.persistence.persistent_store import _get_db_url
    from stockquant.persistence.repository_v2 import Repository
    _repo = Repository.instance()
    count = len(_strategies)
    _strategies.clear()
    try:
        _repo.delete_all_strategies(_get_db_url())
    except Exception as e:
        logger.warning(f"清空策略数据库记录失败: {e}")
    logger.info(f"已清空所有策略: {count} 个")
    return {"success": True, "deletedCount": count}
