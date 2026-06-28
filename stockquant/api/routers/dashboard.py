# -*- coding: utf-8 -*-
"""F029 仪表盘路由 — 聚合指标"""

import logging

from typing import Any, Dict, List

from fastapi import APIRouter

from stockquant.api.schemas import DashboardMetrics
from stockquant.persistence.persistent_store import BacktestTaskStore

logger = logging.getLogger("stockquant.api.dashboard")

router = APIRouter()

# 存储引用（由 main.py 注入）
_tasks: BacktestTaskStore = {}  # type: ignore[assignment]


def set_backtest_storage(storage: BacktestTaskStore):
    global _tasks
    _tasks = storage


# ====================================================================
# 端点
# ====================================================================

@router.get("/dashboard/metrics", response_model=DashboardMetrics, summary="仪表盘核心指标")
async def get_dashboard_metrics() -> DashboardMetrics:
    """
    返回聚合仪表盘指标。
    优先从 trading.py 获取实盘/模拟盘真实持仓数据；
    若无实盘数据，则从已完成回测任务中提取汇总数据。
    持仓数据从数据库 persistence.models.Position 表补充。
    """
    # ── 优先：实盘/模拟盘真实持仓 ──────────────────────────────
    live_equity = 0.0
    live_pnl = 0.0
    live_position_count = 0
    live_available_cash = 0.0
    live_market_value = 0.0
    has_live_data = False

    try:
        from stockquant.api.routers.trading import _portfolio
        acc = _portfolio.account
        positions = {s: p for s, p in _portfolio.positions.items() if p.quantity > 0}
        pos_count = len(positions)
        logger.info(f"dashboard: _portfolio positions={pos_count}, equity={acc.total_equity}, initial={acc.initial_cash}")
        if positions or acc.total_equity != acc.initial_cash:
            has_live_data = True
            live_equity = acc.total_equity
            live_pnl = acc.total_equity - acc.initial_cash
            live_position_count = pos_count
            live_available_cash = acc.available_cash
            live_market_value = sum(p.market_value for p in positions.values())
    except Exception as e:
        logger.warning(f"获取实盘数据失败，降级为回测数据: {e}")

    # ── 从数据库补充持仓（内存可能为空） ──────────────────────
    db_pos_count = 0
    try:
        from stockquant.persistence.models import get_engine as _get_db_engine
        from stockquant.persistence.models import _default_db_url as _default_db_url_str
        from stockquant.persistence.models import Position as PositionORM
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        import os
        db_url = os.environ.get("DATABASE_URL", _default_db_url_str)
        engine = _get_db_engine(db_url)
        logger.info(f"dashboard: db_url={db_url}")
        with Session(engine) as session:
            stmt = select(PositionORM).where(PositionORM.quantity > 0)
            db_positions = session.execute(stmt).scalars().all()
            db_pos_count = len(db_positions)
            logger.info(f"dashboard: db positions={db_pos_count}")
            if db_positions:
                has_live_data = True
                # 数据库持仓数量 + 内存持仓数量（去重）
                live_position_count = db_pos_count
                # 数据库暂无价格，用成本价估算市值
                live_market_value = sum(p.quantity * p.cost_price for p in db_positions)
    except Exception as e:
        logger.warning(f"从数据库加载持仓失败: {e}")

    logger.info(f"dashboard: has_live_data={has_live_data}, position_count={live_position_count}, db_positions={db_pos_count}")

    # ── 回测数据聚合 ──────────────────────────────────────────
    completed = [t for t in _tasks.values() if t.get("status") == "completed"]

    bt_total_equity = 0.0
    bt_total_pnl = 0.0
    sharpe_sum = 0.0
    max_dd_sum = 0.0
    total_trades = 0
    latest_return = ""
    latest_status = ""
    bt_position_count = 0

    for t in completed:
        metrics = t.get("metrics", {})
        eq = t.get("equity_curve")
        if eq and len(eq) > 0:
            bt_total_equity = eq[-1][1] if isinstance(eq[-1], (list, tuple)) and len(eq[-1]) >= 2 else eq[-1][0]

        initial_cash = t.get("initial_cash", 1_000_000)
        pnl = bt_total_equity - initial_cash if bt_total_equity > 0 else 0
        bt_total_pnl += pnl

        sharpe_str = metrics.get("Sharpe Ratio", "0")
        try:
            sharpe_sum += float(sharpe_str)
        except (ValueError, TypeError):
            pass

        dd_str = metrics.get("Max Drawdown", "0")
        try:
            dd_val = float(dd_str.replace("%", "")) / 100 if "%" in dd_str else 0
            max_dd_sum += abs(dd_val)
        except (ValueError, TypeError):
            pass

        total_trades += len(t.get("trades", []))

        symbols = set()
        for trade in t.get("trades", []):
            if isinstance(trade, dict):
                qty = trade.get("qty", 0)
                if qty > 0:
                    symbols.add(trade.get("symbol", ""))
        bt_position_count += len(symbols)

    count = len(completed) or 1

    latest_task = completed[-1] if completed else None
    if latest_task:
        latest_status = latest_task.get("status", "")
        ret = latest_task.get("metrics", {}).get("Total Return", "N/A")
        latest_return = ret if isinstance(ret, str) else ""

    # ── 合并：实盘优先，回测补充 ──────────────────────────────
    if has_live_data:
        total_equity = live_equity
        total_pnl = live_pnl
        position_count = live_position_count
        data_source = "live"
        available_cash = live_available_cash
        market_value = live_market_value
    else:
        total_equity = bt_total_equity
        total_pnl = bt_total_pnl
        position_count = bt_position_count
        data_source = "backtest"
        available_cash = 0
        market_value = 0

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
        "data_source": data_source,
        "available_cash": round(available_cash, 2),
        "market_value": round(market_value, 2),
    }


@router.get("/dashboard/signals", response_model=List[Dict[str, Any]], summary="仪表盘信号列表")
async def get_dashboard_signals() -> List[Dict[str, Any]]:
    """返回最近的交易信号列表（供仪表盘展示）"""
    try:
        # 从信号管线获取活跃信号
        from stockquant.api.routers.signal import get_signal_manager
        signal_manager = get_signal_manager()

        # SignalManager.get_active_signals(symbol) 需要 symbol 参数
        # 我们直接访问内部信号列表，过滤过期信号
        signals = [s for s in signal_manager._signals if not s.is_expired()]

        if not signals:
            logger.debug("仪表盘信号列表为空")
            return []

        # 转换为字典列表
        result = []
        for s in signals:
            result.append({
                "symbol": s.symbol,
                "side": s.side.value,
                "confidence": s.confidence,
                "source": s.source.value,
                "timestamp": s.created_at.isoformat() if s.created_at else None,
                "reasoning": s.reasoning if s.reasoning else [],
            })

        return result
    except Exception as e:
        logger.warning(f"获取仪表盘信号失败: {e}")
        return []
