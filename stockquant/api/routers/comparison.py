# -*- coding: utf-8 -*-
"""F027 策略对比路由 — 多策略横向对比 + 组合优化"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from stockquant.ai.comparison_agent import ComparisonAgent
from stockquant.api.deps import get_current_user, get_required_user
from stockquant.api.schemas import CompareStrategiesRequest, UserToken
from stockquant.persistence.persistent_store import BacktestTaskStore, ComparisonHistoryStore

logger = logging.getLogger("stockquant.api.comparison")
router = APIRouter()

# 存储引用（由 main.py 注入）
_backtest_tasks: BacktestTaskStore = {}  # type: ignore[assignment]
_comparison_history: ComparisonHistoryStore = []  # type: ignore[assignment]


def set_storage(backtest_storage: BacktestTaskStore, comparison_storage: ComparisonHistoryStore):
    global _backtest_tasks, _comparison_history
    _backtest_tasks = backtest_storage
    _comparison_history = comparison_storage


# ── 数据库持久化（通过 ComparisonHistoryStore，由 main.py 注入）──


@router.post("/comparison", response_model=dict, summary="多策略对比")
async def compare_strategies(payload: CompareStrategiesRequest, _user: UserToken = Depends(get_required_user)) -> Dict[str, Any]:
    """对比多个策略的回测结果。

    请求体:
        strategy_ids: list[str] — 回测任务 ID 列表（至少 2 个）
    """
    strategy_ids = payload.strategy_ids
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

    return_data = {
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

    # 记录对比历史（ComparisonHistoryStore 会自动持久化到 DB）
    history_entry = {
        "strategy_ids": ",".join(strategy_ids),
        "result": json.dumps({
            "strategies": comparison.strategies,
            "rankings": comparison.rankings,
            "recommendations": comparison.recommendations,
            "portfolio_weights": comparison.portfolio_weights,
            "correlation_matrix": comparison.correlation_matrix,
            "recent_performance": recent_perf,
        }),
    }
    _comparison_history.append(history_entry)

    return return_data


@router.get("/comparison/history", response_model=list, summary="对比历史")
async def comparison_history():
    """获取历史对比结果（最新的在前），使用 ComparisonHistoryStore"""
    if not _comparison_history:
        return []
    return list(reversed(_comparison_history))


@router.post("/comparison/optimize", response_model=dict, summary="组合优化")
async def optimize_portfolio(payload: CompareStrategiesRequest, _user: UserToken = Depends(get_current_user)) -> Dict[str, Any]:
    """策略组合优化 — 相关性+最优权重。

    请求体:
        strategy_ids: list[str] — 回测任务 ID 列表（至少 2 个）
    """
    strategy_ids = payload.strategy_ids
    if len(strategy_ids) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 个策略 ID 进行组合优化")

    # 从存储加载回测结果
    results = []
    for tid in strategy_ids:
        task = _backtest_tasks.get(tid)
        if task is None:
            raise HTTPException(status_code=404, detail=f"回测任务 {tid} 不存在")
        results.append(task)

    agent = ComparisonAgent()
    return agent.optimize_portfolio(results)


@router.get("/comparison/lifecycle/{strategy_id}", response_model=dict, summary="生命周期建议")
async def lifecycle_advice(strategy_id: str, _user: UserToken = Depends(get_current_user)) -> Dict[str, Any]:
    """策略生命周期建议 — 启用/停用/调整。

    基于近 30 天表现给出建议。
    """
    task = _backtest_tasks.get(strategy_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"回测任务 {strategy_id} 不存在")

    # 从回测结果提取近期指标
    agent = ComparisonAgent()
    recent_perf_list = agent._compute_recent_performance([task], window=30)
    strategy_name = task.get("strategy_name", task.get("strategy", strategy_id))
    recent = recent_perf_list.get(strategy_name, {})

    # 构建 lifecycle_advice 所需的指标
    metrics = {
        "recent_return": recent.get("recent_return", 0.0) / 100.0 if recent.get("recent_return") else 0.0,
        "recent_sharpe": _extract_sharpe(task),
        "recent_max_drawdown": abs(recent.get("recent_drawdown", 0.0) / 100.0) if recent.get("recent_drawdown") else 0.0,
    }

    return agent.lifecycle_advice(strategy_id, metrics)


def _extract_sharpe(task: dict) -> float:
    """从回测任务中提取 Sharpe Ratio"""
    try:
        sharpe = task.get("Sharpe Ratio")
        if sharpe is not None:
            return float(str(sharpe).replace("%", ""))
        metrics = task.get("metrics", {})
        if isinstance(metrics, dict):
            s = metrics.get("Sharpe Ratio")
            if s is not None:
                return float(str(s).replace("%", ""))
    except (ValueError, TypeError):
        pass
    return 0.0
