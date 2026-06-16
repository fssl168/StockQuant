# -*- coding: utf-8 -*-
"""F029 参数优化路由 — 提交/查询优化任务"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

logger = logging.getLogger("stockquant.api.optimize")

router = APIRouter()

# 内存存储 (MVP)
_optimize_tasks: dict = {}


@router.post("/backtest/optimize", summary="提交参数优化任务")
async def submit_optimize(payload: dict):
    """提交参数优化任务"""
    task_id = f"OPT-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now().isoformat()

    task = {
        "task_id": task_id,
        "status": "queued",
        "strategy_name": payload.get("strategy_name", "未命名策略"),
        "params": payload.get("params", []),
        "method": payload.get("method", "grid"),
        "target_metric": payload.get("target_metric", "sharpe_ratio"),
        "max_iterations": payload.get("max_iterations", 50),
        "created_at": now,
        "updated_at": now,
        "results": [],
        "best_result": None,
        "progress": 0,
    }

    _optimize_tasks[task_id] = task
    logger.info(f"参数优化任务已提交: {task_id}")

    return {"task_id": task_id, "status": "queued", "created_at": now}


@router.get("/backtest/optimize/{task_id}", summary="查询优化状态/结果")
async def get_optimize_status(task_id: str):
    """查询参数优化任务状态和结果"""
    task = _optimize_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"优化任务 {task_id} 不存在")

    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "progress": task["progress"],
        "results": task["results"],
        "best_result": task["best_result"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }
