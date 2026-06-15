# -*- coding: utf-8 -*-
"""F027 策略对比路由 — 多策略横向对比 + 组合优化"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from stockquant.ai.comparison_agent import ComparisonAgent

logger = logging.getLogger("stockquant.api.comparison")
router = APIRouter()

# 存储引用（由 main.py 注入）
_backtest_tasks: dict = {}


def set_storage(storage: dict):
    global _backtest_tasks
    _backtest_tasks = storage


@router.post("/comparison", response_model=dict, summary="多策略对比")
async def compare_strategies(payload: dict):
    """对比多个策略的回测结果。

    请求体:
        strategy_ids: list[str] — 回测任务 ID 列表（至少 2 个）
    """
    strategy_ids = payload.get("strategy_ids", [])
    if len(strategy_ids) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 个策略 ID 进行对比")

    # 从存储加载回测结果
    results = []
    names = []
    for tid in strategy_ids:
        task = _backtest_tasks.get(tid)
        if task is None:
            raise HTTPException(status_code=404, detail=f"回测任务 {tid} 不存在")
        results.append(task)
        names.append(task.get("strategy_name", f"Strategy {len(names)+1}"))

    agent = ComparisonAgent()
    comparison = agent.compare(results, names)

    # 包含近期表现
    recent_perf = agent._compute_recent_performance(results)

    return {
        "strategies": comparison.strategies,
        "rankings": {
            k: [(n, round(v, 3)) for n, v in entries]
            for k, entries in comparison.rankings.items()
        },
        "recommendations": comparison.recommendations,
        "portfolio_weights": comparison.portfolio_weights,
        "correlation_matrix": comparison.correlation_matrix,
        "recent_performance": recent_perf,
    }


@router.get("/comparison/history", response_model=list, summary="对比历史")
async def comparison_history():
    """获取历史对比结果"""
    return []
