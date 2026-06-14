# -*- coding: utf-8 -*-
"""pytest fixtures — 共享测试数据和夹具"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta

import numpy as np
import pytest


# ========================================================================
# 模拟价格数据
# ========================================================================

@pytest.fixture
def price_data():
    """生成 200 天模拟价格数据"""
    np.random.seed(42)
    prices = [100.0]
    for _ in range(200):
        prices.append(prices[-1] * (1 + np.random.randn() * 0.02))
    return prices


@pytest.fixture
def ohlcv_data():
    """生成 200 天 OHLCV 数据"""
    np.random.seed(42)
    prices = [100.0]
    for _ in range(200):
        prices.append(prices[-1] * (1 + np.random.randn() * 0.02))
    highs = [p * (1 + abs(np.random.randn()) * 0.01) for p in prices]
    lows = [p * (1 - abs(np.random.randn()) * 0.01) for p in prices]
    volumes = [1_000_000 * (1 + abs(np.random.randn()) * 0.5) for _ in prices]
    return prices, highs, lows, volumes


# ========================================================================
# 模拟权益曲线
# ========================================================================

@pytest.fixture
def equity_curve():
    """生成 500 天模拟权益曲线"""
    np.random.seed(123)
    equity = [1_000_000.0]
    for _ in range(500):
        equity.append(equity[-1] * (1 + np.random.randn() * 0.01))
    return list(zip(equity, range(len(equity))))


# ========================================================================
# 模拟交易记录
# ========================================================================

@pytest.fixture
def sample_trades():
    """生成模拟成交记录"""
    from stockquant.models.trade import TradeData
    return [
        TradeData(
            trade_id="t1", order_id="o1", symbol="sh600519",
            side="Buy", price=1800.0, quantity=100,
        ),
        TradeData(
            trade_id="t2", order_id="o2", symbol="sh600519",
            side="Sell", price=1850.0, quantity=100,
        ),
        TradeData(
            trade_id="t3", order_id="o3", symbol="sz000858",
            side="Buy", price=25.0, quantity=500,
        ),
        TradeData(
            trade_id="t4", order_id="o4", symbol="sz000858",
            side="Sell", price=23.0, quantity=500,
        ),
    ]


# ========================================================================
# 模拟 CSV 文件
# ========================================================================

@pytest.fixture
def csv_file():
    """创建临时 CSV 文件（100 天数据）"""
    csv_content = "timestamp,open,high,low,close,volume\n"
    for i in range(100):
        dt = (datetime(2024, 1, 1) + timedelta(days=i)).strftime("%Y-%m-%d")
        price = 100 + i * 0.1
        csv_content += f"{dt},{price:.2f},{price+1:.2f},{price-1:.2f},{price:.2f},{1000000}\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        csv_path = f.name

    try:
        yield csv_path
    finally:
        os.unlink(csv_path)


# ========================================================================
# 模拟 Cerebro 引擎
# ========================================================================

@pytest.fixture
def simple_cerebro(csv_file):
    """创建配置好的简单 Cerebro 引擎"""
    from stockquant import Cerebro, BacktestBroker, CSVFeed, CommissionInfo
    from stockquant.strategy.base import BaseStrategy

    class DummyStrategy(BaseStrategy):
        name = "Dummy"
        def on_bar(self, bars):
            pass

    feed = CSVFeed(csv_file, symbol="test", timeframe="1d")
    cerebro = Cerebro(cash=1_000_000, broker=BacktestBroker(), commission=CommissionInfo())
    cerebro.add_data(feed)
    cerebro.add_strategy(DummyStrategy)
    return cerebro


# ========================================================================
# 模拟订单
# ========================================================================

@pytest.fixture
def sample_order():
    """创建模拟买单"""
    from stockquant.models.order import Order, OrderSide, OrderType
    return Order(
        symbol="sh600519",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=1800.0,
        quantity=100,
    )


# ========================================================================
# 模拟 BarData
# ========================================================================

@pytest.fixture
def sample_bar():
    """创建模拟 K 线"""
    from stockquant.models.bar import BarData
    from datetime import datetime
    return BarData(
        symbol="sh600519",
        datetime=datetime.now(),
        open=99.0, high=101.0, low=98.0, close=100.0, volume=1_000_000,
    )


# ========================================================================
# 模拟风控管理器
# ========================================================================

@pytest.fixture
def risk_manager():
    """创建风控管理器"""
    from stockquant.engine.risk import RiskManager
    return RiskManager(
        max_position_pct=0.3,
        max_buy_amount=500_000,
        max_total_position_pct=0.9,
        max_daily_loss_pct=0.02,
        max_drawdown_pct=0.15,
    )
