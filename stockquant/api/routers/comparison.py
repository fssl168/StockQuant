# -*- coding: utf-8 -*-
"""F027 策略对比路由 — 多策略横向对比 + 组合优化"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from stockquant.ai.comparison_agent import ComparisonAgent
from stockquant.api.deps import get_current_user, get_required_user
from stockquant.persistence.models import get_engine, init_db

logger = logging.getLogger("stockquant.api.comparison")
router = APIRouter()

# 存储引用（由 main.py 注入）
_backtest_tasks: dict = {}
_comparison_history: list[dict] = []


def set_storage(storage: dict):
    global _backtest_tasks, _comparison_history
    _backtest_tasks = storage
    _comparison_history = storage.get("_comparison_history", [])


# ── SQLite 持久化 ──

_COMPARISON_TABLE_CREATED = False


def _ensure_comparison_table() -> None:
    """首次使用时创建 comparison_results 表"""
    global _COMPARISON_TABLE_CREATED
    if _COMPARISON_TABLE_CREATED:
        return
    try:
        init_db()
        with get_engine().begin() as conn:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS comparison_results ("
                "id TEXT PRIMARY KEY, "
                "timestamp TEXT, "
                "strategy_ids TEXT, "
                "names TEXT, "
                "result TEXT)"
            ))
        _COMPARISON_TABLE_CREATED = True
    except Exception as exc:
        logger.warning("创建 comparison_results 表失败: %s", exc)


def _persist_comparison(entry: dict) -> None:
    """将对比结果持久化到 SQLite"""
    _ensure_comparison_table()
    try:
        with get_engine().begin() as conn:
            conn.execute(text(
                "INSERT OR REPLACE INTO comparison_results "
                "(id, timestamp, strategy_ids, names, result) "
                "VALUES (:id, :timestamp, :strategy_ids, :names, :result)"
            ), {
                "id": entry["id"],
                "timestamp": entry["timestamp"],
                "strategy_ids": json.dumps(entry.get("strategy_ids", []), ensure_ascii=False),
                "names": json.dumps(entry.get("names", []), ensure_ascii=False),
                "result": json.dumps(entry.get("result", {}), ensure_ascii=False),
            })
    except Exception as exc:
        logger.warning("对比结果持久化失败: %s", exc)


def _load_comparisons(limit: int = 100) -> list[dict]:
    """从 SQLite 加载对比历史"""
    _ensure_comparison_table()
    try:
        with get_engine().connect() as conn:
            rows = conn.execute(text(
                "SELECT id, timestamp, strategy_ids, names, result "
                "FROM comparison_results ORDER BY timestamp DESC LIMIT :limit"
            ), {"limit": limit}).fetchall()
            return [
                {
                    "id": r[0],
                    "timestamp": r[1],
                    "strategy_ids": json.loads(r[2]) if r[2] else [],
                    "names": json.loads(r[3]) if r[3] else [],
                    "result": json.loads(r[4]) if r[4] else {},
                }
                for r in rows
            ]
    except Exception:
        return []


@router.post("/comparison", response_model=dict, summary="多策略对比")
async def compare_strategies(payload: dict, _user=Depends(get_required_user)):
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

    # 记录对比历史
    history_entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "strategy_ids": strategy_ids,
        "names": names,
        "result": {
            "strategies": comparison.strategies,
            "rankings": comparison.rankings,
            "recommendations": comparison.recommendations,
            "portfolio_weights": comparison.portfolio_weights,
            "correlation_matrix": comparison.correlation_matrix,
            "recent_performance": recent_perf,
        },
    }
    _comparison_history.append(history_entry)
    _persist_comparison(history_entry)

    return return_data


@router.get("/comparison/history", response_model=list, summary="对比历史")
async def comparison_history():
    """获取历史对比结果（最新的在前），优先从 SQLite 加载"""
    db_results = _load_comparisons()
    if not db_results and _comparison_history:
        # SQLite 为空时降级到内存
        return list(reversed(_comparison_history))
    if not _comparison_history:
        return db_results
    # 合并：内存中可能有 SQLite 尚未包含的新条目
    db_ids = {r["id"] for r in db_results}
    merged = list(db_results)
    for entry in reversed(_comparison_history):
        if entry["id"] not in db_ids:
            merged.insert(0, entry)
    return merged


@router.post("/comparison/optimize", response_model=dict, summary="组合优化")
async def optimize_portfolio(payload: dict, _user=Depends(get_current_user)):
    """策略组合优化 — 相关性+最优权重。

    请求体:
        strategy_ids: list[str] — 回测任务 ID 列表（至少 2 个）
    """
    strategy_ids = payload.get("strategy_ids", [])
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
async def lifecycle_advice(strategy_id: str, _user=Depends(get_current_user)):
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
