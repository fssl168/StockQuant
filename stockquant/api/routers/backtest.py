# -*- coding: utf-8 -*-
"""F029 回测路由 — 提交/查询/删除/列表"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

logger = logging.getLogger("stockquant.api.backtest")

router = APIRouter()

# 存储引用（由 main.py 注入）
_tasks: dict = {}


def set_storage(storage: dict):
    global _tasks
    _tasks = storage


# ====================================================================
# 端点
# ====================================================================

@router.post("/backtest", response_model=dict, summary="提交回测任务")
async def submit_backtest(payload: dict):
    """
    提交回测任务。

    MVP 暂不实际执行回测，仅记录任务并返回 queued 状态。
    未来接入实际引擎时，此处触发 Cerebro 回测。
    """
    task_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    task = {
        "task_id": task_id,
        "status": "queued",
        "strategy_name": payload.get("strategy_name", "未命名策略"),
        "strategy_code": payload.get("strategy_code", ""),
        "symbols": payload.get("symbols", []),
        "start_date": payload.get("start_date", ""),
        "end_date": payload.get("end_date", ""),
        "cash": payload.get("cash", 1_000_000),
        "commission_type": payload.get("commission_type", "ashare"),
        "slippage_type": payload.get("slippage_type", "none"),
        "created_at": now,
        "updated_at": now,
        "metrics": {},
        "trades": [],
        "equity_curve": [],
        "error": None,
    }

    _tasks[task_id] = task
    logger.info(f"回测任务已提交: {task_id}")

    return {
        "task_id": task_id,
        "status": "queued",
        "created_at": now,
    }


@router.get("/backtest", response_model=list[dict], summary="回测任务列表")
async def list_backtests():
    """获取所有回测任务"""
    return list(_tasks.values())


@router.get("/backtest/{task_id}", response_model=dict, summary="回测结果")
async def get_backtest(task_id: str):
    """获取指定回测任务的结果"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "strategy_name": task["strategy_name"],
        "metrics": task["metrics"],
        "trades": task["trades"],
        "equity_curve": task["equity_curve"],
        "error": task["error"],
    }


@router.delete("/backtest/{task_id}", response_model=dict, summary="删除回测任务")
async def delete_backtest(task_id: str):
    """删除回测任务"""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    del _tasks[task_id]
    logger.info(f"回测任务已删除: {task_id}")
    return {"success": True, "task_id": task_id}

