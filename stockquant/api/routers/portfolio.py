# -*- coding: utf-8 -*-
"""F029 投资组合路由 — 持仓/行业/盈亏/权益曲线

与 trading.py 共享真实交易数据。
权益曲线基于真实交易记录和 K 线数据计算。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from stockquant.api.deps import get_current_user

from stockquant.engine.commission import CommissionInfo

logger = logging.getLogger("stockquant.api.portfolio")

router = APIRouter()

# 行业映射表（简化版，覆盖主要 A 股标的）
_SECTOR_MAP: dict[str, str] = {
    "sh600519": "白酒", "sz000858": "白酒", "sz000568": "白酒",
    "sh601318": "保险", "sh601601": "保险", "sh601628": "保险",
    "sh600036": "银行", "sh601398": "银行", "sh600000": "银行",
    "sh600030": "券商", "sh601211": "券商", "sz000776": "券商",
    "sz300750": "新能源", "sz002594": "新能源", "sh600104": "汽车",
    "sz000333": "家电", "sh600276": "医药", "sz300015": "医药",
    "sh600900": "电力", "sh601012": "电力",
    "sz002475": "电子", "sz300059": "互联网",
}

_commission_info = CommissionInfo()


def _get_trading_state():
    """从 trading.py 导入 Portfolio 和 PaperBroker"""
    from stockquant.api.routers.trading import (
        _portfolio, _paper_broker,
    )
    return _portfolio, _paper_broker


def _get_latest_price(symbol: str) -> float | None:
    """获取标的最新收盘价"""
    try:
        from stockquant.data.providers.baostock_feed import BaoStockFeed
        feed = BaoStockFeed(symbols=[symbol], timeframe="1d")
        feed.start()
        df = feed.get_dataframe()
        feed.stop()
        if df is not None and not df.empty:
            return float(df.iloc[-1]["close"])
    except Exception as e:
        logger.warning(f"获取最新价格失败: {symbol}, {e}")
    return None


def _get_kline_prices(symbol: str, days: int = 60) -> list[tuple[str, float]]:
    """获取历史 K 线收盘价，返回 [(date, close), ...]"""
    try:
        from stockquant.data.providers.baostock_feed import BaoStockFeed
        end = datetime.now().strftime("%Y-%m-%d")
        start_dt = datetime.now() - timedelta(days=days + 30)  # 多取一些确保交易日足够
        start = start_dt.strftime("%Y-%m-%d")
        feed = BaoStockFeed(symbols=[symbol], timeframe="1d")
        feed.start()
        df = feed.get_dataframe(start_date=start, end_date=end)
        feed.stop()
        if df is not None and not df.empty:
            results = []
            for _, row in df.iterrows():
                date_str = str(row.get("date", ""))
                close = float(row["close"])
                if date_str:
                    results.append((date_str, close))
            # 只返回最近 days 条
            return results[-days:]
    except Exception as e:
        logger.warning(f"获取 K 线数据失败: {symbol}, {e}")
    return []


def _compute_equity_curve_from_snapshots(days: int = 30) -> tuple[list[str], list[float]]:
    """从权益快照表获取历史权益曲线"""
    try:
        from stockquant.persistence.models import EquitySnapshot
        from stockquant.persistence.database import get_engine
        from sqlalchemy import create_engine as _create_engine, select

        engine = get_engine()
        if engine is None:
            return [], []

        from sqlalchemy.orm import Session
        with Session(engine) as session:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            stmt = (
                select(EquitySnapshot)
                .where(EquitySnapshot.date >= cutoff)
                .order_by(EquitySnapshot.date.asc())
            )
            rows = session.execute(stmt).scalars().all()

            if not rows:
                return [], []

            dates = [r.date for r in rows]
            values = [round(r.equity, 2) for r in rows]
            return dates, values
    except Exception as e:
        logger.debug(f"从权益快照获取权益曲线失败: {e}")
        return [], []


def _compute_equity_curve_from_backtest(days: int = 30) -> tuple[list[str], list[float]]:
    """从最近的回测结果获取权益曲线"""
    try:
        from stockquant.persistence.repository import Repository
        from stockquant.persistence.models import BacktestResult
        repo = Repository(BacktestResult)
        backtests = repo.list(limit=10)
        if not backtests:
            return [], []
        # 按创建时间排序取最近一个
        latest = sorted(backtests, key=lambda b: b.created_at, reverse=True)[0]
        equity_data = latest.equity_curve
        if not equity_data:
            return [], []

        # equity_data 格式: [[equity, bar_index], ...] 或 [equity, ...]
        if isinstance(equity_data[0], (list, tuple)):
            # [(equity, bar_index), ...]
            equity_values = [float(eq) for eq, _ in equity_data]
        else:
            equity_values = [float(v) for v in equity_data]

        # 截取最近 days 个点
        if len(equity_values) > days:
            equity_values = equity_values[-days:]

        # 生成日期序列（最近 days 个交易日）
        end = datetime.now()
        dates = [(end - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d") for i in range(days)]

        # 如果 equity_values 长度与 days 不匹配，调整 dates
        actual_days = len(equity_values)
        dates = [(end - timedelta(actual_days - 1 - i)).strftime("%Y-%m-%d") for i in range(actual_days)]

        return dates, equity_values
    except Exception as e:
        logger.warning(f"从回测结果获取权益曲线失败: {e}")
        return [], []


def _compute_live_equity_curve(days: int = 30) -> tuple[list[str], list[float]]:
    """从真实交易记录 + K 线数据计算权益曲线

    逻辑：
    1. 遍历持仓标的的历史 K 线
    2. 从初始资金开始，逐日计算：现金 + 持仓市值
    3. 考虑买入/卖出的现金流
    """
    _portfolio, _paper_broker = _get_trading_state()
    acc = _portfolio.account

    # 获取所有持仓标的
    positions = {s: p for s, p in _portfolio.positions.items() if p.quantity > 0}

    if not positions:
        # 无持仓：权益 = 现金，返回一条水平线
        end = datetime.now()
        values = [round(acc.total_equity, 2)] * days
        dates = [(end - timedelta(days - 1 - i)).strftime("%Y-%m-%d") for i in range(days)]
        return dates, values

    # 收集所有有历史数据的时间点
    # 简化策略：取所有持仓标的的最长 K 线日期范围
    all_prices: dict[str, list[tuple[str, float]]] = {}
    all_dates: set[str] = set()

    for symbol in positions:
        prices = _get_kline_prices(symbol, days * 2)  # 多取一些确保覆盖
        if prices:
            all_prices[symbol] = prices
            for date_str, _ in prices:
                all_dates.add(date_str)

    if not all_dates:
        # 无 K 线数据，退化为当前权益
        end = datetime.now()
        values = [round(acc.total_equity, 2)] * days
        dates = [(end - timedelta(days - 1 - i)).strftime("%Y-%m-%d") for i in range(days)]
        return dates, values

    sorted_dates = sorted(all_dates)
    if len(sorted_dates) < 2:
        end = datetime.now()
        values = [round(acc.total_equity, 2)] * days
        dates = [(end - timedelta(days - 1 - i)).strftime("%Y-%m-%d") for i in range(days)]
        return dates, values

    # 取最近 days 个交易日
    if len(sorted_dates) > days:
        sorted_dates = sorted_dates[-days:]

    # 从初始资金开始计算每日权益
    # 精确计算：权益 = 初始资金 + 累计未实现盈亏 + 累计已实现盈亏
    # 简化近似：从第一天开始，权益 = 初始资金
    # 之后每天：权益 = 前一天权益 + 持仓市值日变化
    # 这保证了权益曲线连续性

    initial_cash = acc.initial_cash

    # 先建价格查找表
    price_map: dict[str, dict[str, float]] = {}
    for symbol, prices in all_prices.items():
        price_map[symbol] = {d: p for d, p in prices}

    dates: list[str] = []
    values: list[float] = []
    prev_equity = initial_cash

    for i, date_str in enumerate(sorted_dates):
        # 当前日的持仓市值
        mv = 0.0
        for symbol, pos in positions.items():
            daily_price = price_map.get(symbol, {}).get(date_str)
            if daily_price:
                mv += pos.quantity * daily_price

        if i == 0:
            # 第一天：权益 = 初始资金（假设建仓前）
            equity = initial_cash
        else:
            # 后续天：权益 = 前一天权益 + (今日市值 - 昨日市值)
            prev_date = sorted_dates[i - 1]
            prev_mv = 0.0
            for symbol, pos in positions.items():
                prev_price = price_map.get(symbol, {}).get(prev_date)
                if prev_price:
                    prev_mv += pos.quantity * prev_price
            equity = prev_equity + (mv - prev_mv)

        prev_equity = equity
        dates.append(date_str)
        values.append(round(equity, 2))

    return dates, values


@router.get("/portfolio/positions", summary="持仓列表")
async def get_positions():
    """获取持仓列表 — 来自真实交易数据"""
    _portfolio, _paper_broker = _get_trading_state()
    result = []
    for symbol, pos in _portfolio.positions.items():
        if pos.quantity <= 0:
            continue
        entry = {
            "symbol": pos.symbol,
            "name": pos.symbol,
            "shares": pos.quantity,
            "cost": round(pos.cost_price, 2),
            "price": round(pos.current_price, 2),
            "market_value": round(pos.market_value, 2),
            "pnl": round(pos.pnl, 2),
            "pnl_pct": round((pos.current_price - pos.cost_price) / pos.cost_price * 100, 2)
                        if pos.cost_price > 0 else 0,
            "sector": _SECTOR_MAP.get(symbol, "其他"),
        }
        result.append(entry)
    return result


@router.get("/portfolio/account", summary="账户汇总")
async def get_account(_user=Depends(get_current_user)):
    """获取账户汇总信息 — 来自真实交易数据"""
    _portfolio, _paper_broker = _get_trading_state()
    acc = _portfolio.account
    positions = _portfolio.positions

    market_value = sum(p.market_value for p in positions.values() if p.quantity > 0)

    total_cost = sum(
        p.cost_price * p.quantity for p in positions.values() if p.quantity > 0
    )
    total_pnl = acc.total_equity - acc.initial_cash
    total_pnl_pct = round(total_pnl / acc.initial_cash * 100, 2) if acc.initial_cash > 0 else 0

    return {
        "total_value": round(acc.total_equity, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": total_pnl_pct,
        "position_count": len([p for p in positions.values() if p.quantity > 0]),
    }


@router.get("/portfolio/sector", summary="行业分布")
async def get_sector():
    """获取行业分布 — 基于持仓动态计算"""
    _portfolio, _paper_broker = _get_trading_state()
    positions = _portfolio.positions

    sector_values: dict[str, float] = {}
    total_value = 0.0

    for symbol, pos in positions.items():
        if pos.quantity <= 0:
            continue
        sector = _SECTOR_MAP.get(symbol, "其他")
        mv = pos.market_value
        sector_values[sector] = sector_values.get(sector, 0) + mv
        total_value += mv

    result = []
    for sector, value in sector_values.items():
        weight = round(value / total_value, 4) if total_value > 0 else 0
        result.append({
            "sector": sector,
            "value": round(value, 2),
            "weight": weight,
        })

    return result


@router.get("/portfolio/pnl", summary="盈亏分析")
async def get_pnl():
    """获取盈亏分析 — 基于真实成交记录"""
    _portfolio, paper_broker = _get_trading_state()

    trades = paper_broker.trade_log
    if not trades:
        return {
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
        }

    # 按 symbol 配对买卖计算盈亏
    trades_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for trade in trades:
        trades_by_symbol.setdefault(trade.symbol, []).append({
            "side": trade.side,
            "price": trade.price,
            "quantity": trade.quantity,
            "commission": trade.commission,
        })

    wins = []
    losses = []

    for symbol, symbol_trades in trades_by_symbol.items():
        buys = [t for t in symbol_trades if t["side"] == "Buy"]
        sells = [t for t in symbol_trades if t["side"] == "Sell"]

        # 简单配对：每笔卖出配对最早的一笔买入
        buy_queue = list(buys)
        for sell in sells:
            if buy_queue:
                buy = buy_queue.pop(0)
                # 计算这笔配对的盈亏
                buy_notional = buy["price"] * buy["quantity"]
                sell_notional = sell["price"] * sell["quantity"]
                buy_cost = _commission_info.calc_buy_cost(buy_notional)
                sell_cost = _commission_info.calc_sell_cost(sell_notional)
                pnl = sell_notional - buy_notional - buy_cost - sell_cost
                if pnl > 0:
                    wins.append(pnl)
                else:
                    losses.append(abs(pnl))

    win_count = len(wins)
    loss_count = len(losses)
    total_trades = win_count + loss_count
    avg_win = round(sum(wins) / win_count, 2) if wins else 0
    avg_loss = round(sum(losses) / loss_count, 2) if losses else 0
    total_win = sum(wins)
    total_loss = sum(losses)
    profit_factor = round(total_win / total_loss, 2) if total_loss > 0 else 0

    return {
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": round(win_count / total_trades, 3) if total_trades > 0 else 0,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
    }


@router.get("/portfolio/equity-curve", summary="组合权益曲线")
async def get_equity_curve(_user=Depends(get_current_user)):
    """获取组合整体权益曲线 — 优先快照数据，其次回测结果，最后实时交易数据"""
    # 优先从权益快照获取
    dates, values = _compute_equity_curve_from_snapshots()
    if dates and values:
        return {"dates": dates, "values": values, "source": "snapshot"}

    # 其次从回测结果获取
    dates, values = _compute_equity_curve_from_backtest()
    if dates and values:
        return {"dates": dates, "values": values, "source": "backtest"}

    # 最后从实时交易数据计算
    dates, values = _compute_live_equity_curve()
    return {"dates": dates, "values": values, "source": "live"}


@router.get("/portfolio/equity-curve/{symbol}", summary="个股权益曲线")
async def get_stock_equity_curve(symbol: str, _user=Depends(get_current_user)):
    """获取个股权益曲线 — 基于该标的的历史 K 线价格 + 交易记录"""
    _portfolio, _paper_broker = _get_trading_state()
    pos = _portfolio.positions.get(symbol)

    if not pos or pos.quantity <= 0:
        # 无持仓：用买入价格 + K 线价格计算
        # 查找该标的的历史交易
        trades = _paper_broker.trade_log
        buy_trades = [t for t in trades if t.symbol == symbol and t.side == "Buy"]
        if not buy_trades:
            return {"symbol": symbol, "dates": [], "values": []}

        # 取最近一笔买入作为基准
        last_buy = buy_trades[-1]
        base_price = last_buy.price
        base_quantity = last_buy.quantity
    else:
        base_price = pos.cost_price
        base_quantity = pos.quantity

    # 获取 K 线价格并计算每日市值
    kline = _get_kline_prices(symbol, days=30)
    if not kline:
        return {"symbol": symbol, "dates": [], "values": []}

    dates = [d for d, _ in kline]
    values = [round(base_quantity * price, 2) for _, price in kline]

    return {"symbol": symbol, "dates": dates, "values": values}


@router.post("/portfolio/snapshot", summary="保存权益快照")
async def save_equity_snapshot(_user=Depends(get_current_user)):
    """手动触发权益快照保存。

    将当前账户权益状态持久化到 equity_snapshots 表，
    用于历史权益曲线展示和回溯分析。
    """
    try:
        from stockquant.persistence.models import EquitySnapshot
        from stockquant.persistence.database import get_engine
        from sqlalchemy.orm import Session

        _portfolio, _paper_broker = _get_trading_state()
        acc = _portfolio.account
        positions = {s: p for s, p in _portfolio.positions.items() if p.quantity > 0}

        today = datetime.now().strftime("%Y-%m-%d")
        snapshot_id = f"snap_{today}_{id(acc)}"

        engine = get_engine()
        if engine is None:
            raise HTTPException(status_code=500, detail="数据库不可用")

        with Session(engine) as session:
            # 检查今日是否已有快照
            existing = session.query(EquitySnapshot).filter(
                EquitySnapshot.date == today
            ).first()
            if existing:
                # 更新已有快照
                existing.equity = round(acc.total_equity, 2)
                existing.cash = round(acc.available_cash, 2)
                existing.market_value = round(acc.total_equity - acc.available_cash, 2)
                existing.positions_count = len(positions)
            else:
                snapshot = EquitySnapshot(
                    id=snapshot_id,
                    date=today,
                    equity=round(acc.total_equity, 2),
                    cash=round(acc.available_cash, 2),
                    market_value=round(acc.total_equity - acc.available_cash, 2),
                    positions_count=len(positions),
                )
                session.add(snapshot)
            session.commit()

        return {
            "status": "ok",
            "date": today,
            "equity": round(acc.total_equity, 2),
            "cash": round(acc.available_cash, 2),
            "positions_count": len(positions),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存权益快照失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
