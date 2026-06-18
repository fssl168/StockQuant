# -*- coding: utf-8 -*-
"""F029 仪表盘路由 — 聚合指标"""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger("stockquant.api.dashboard")

router = APIRouter()

# 存储引用（由 main.py 注入）
_tasks: dict = {}


def set_backtest_storage(storage: dict):
    global _tasks
    _tasks = storage


# ====================================================================
# 端点
# ====================================================================

@router.get("/dashboard/metrics", response_model=dict, summary="仪表盘核心指标")
async def get_dashboard_metrics():
    """
    返回聚合仪表盘指标。
    从所有已完成回测任务中提取汇总数据。
    同时从 trading.py 获取当前投资组合状态。
    """
    completed = [t for t in _tasks.values() if t.get("status") == "completed"]

    total_equity = 0.0
    total_pnl = 0.0
    sharpe_sum = 0.0
    max_dd_sum = 0.0
    total_trades = 0
    latest_return = ""
    latest_status = ""
    position_count = 0

    for t in completed:
        metrics = t.get("metrics", {})
        # 从 equity_curve 获取最终权益
        eq = t.get("equity_curve")
        if eq and len(eq) > 0:
            total_equity = eq[-1][1] if isinstance(eq[-1], (list, tuple)) and len(eq[-1]) >= 2 else eq[-1][0]

        # 获取初始资金
        initial_cash = t.get("initial_cash", 1_000_000)
        pnl = total_equity - initial_cash if total_equity > 0 else 0
        total_pnl += pnl

        # Sharpe 值
        sharpe_str = metrics.get("Sharpe Ratio", "0")
        try:
            sharpe_sum += float(sharpe_str)
        except (ValueError, TypeError):
            pass

        # 最大回撤
        dd_str = metrics.get("Max Drawdown", "0")
        try:
            dd_val = float(dd_str.replace("%", "")) / 100 if "%" in dd_str else 0
            max_dd_sum += abs(dd_val)
        except (ValueError, TypeError):
            pass

        total_trades += len(t.get("trades", []))

        # 从 trades 计算持仓数
        symbols = set()
        for trade in t.get("trades", []):
            if isinstance(trade, dict):
                qty = trade.get("qty", 0)
                if qty > 0:
                    symbols.add(trade.get("symbol", ""))
        position_count += len(symbols)

    count = len(completed) or 1

    latest_task = completed[-1] if completed else None
    if latest_task:
        latest_status = latest_task.get("status", "")
        ret = latest_task.get("metrics", {}).get("Total Return", "N/A")
        latest_return = ret if isinstance(ret, str) else ""

    return {
        "total_equity": round(total_equity, 2),
        "daily_pnl": round(total_pnl, 2),
        "position_count": position_count,
        "sharpe": round(sharpe_sum / count, 4),
        "max_drawdown": round(-max_dd_sum / count, 4),
        "total_trades": total_trades,
        "backtest_count": len(completed),
        "latest_backtest_status": latest_status,
        "latest_backtest_return": latest_return,
    }


@router.get("/dashboard/signals", response_model=list, summary="仪表盘信号列表")
async def get_dashboard_signals():
    """返回最近的交易信号列表（供仪表盘展示）"""
    # TODO: 接入真实的信号存储
    return []
