# -*- coding: utf-8 -*-
"""F014 策略模板测试"""

import os
import tempfile

import numpy as np
import pytest

from stockquant import Cerebro, BacktestBroker, CSVFeed, CommissionInfo
from stockquant.strategy.base import BaseStrategy
from stockquant.strategy.templates import (
    DualMACrossoverStrategy,
    RSIReversalStrategy,
    BollingerBounceStrategy,
    MACDDivergenceStrategy,
    DualThrustStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
)


# ========================================================================
# 共享 fixture
# ========================================================================

@pytest.fixture
def test_csv():
    """创建 200 天测试数据"""
    csv_content = "timestamp,open,high,low,close,volume\n"
    price = 100.0
    for i in range(200):
        dt = f"2024-{(i // 30) + 1:02d}-{(i % 28) + 1:02d}"
        price *= (1 + np.random.randn() * 0.01)
        csv_content += (
            f"{dt},{price:.2f},{price+1:.2f},{price-1:.2f},{price:.2f},{1000000}\n"
        )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8",
    ) as f:
        f.write(csv_content)
        path = f.name
    try:
        yield path
    finally:
        os.unlink(path)


@pytest.fixture
def cerebro_with_feed(test_csv):
    """创建带数据源的 Cerebro"""
    feed = CSVFeed(test_csv, symbol="test", timeframe="1d")
    cerebro = Cerebro(
        cash=1_000_000, broker=BacktestBroker(), commission=CommissionInfo(),
    )
    cerebro.add_data(feed)
    return cerebro


# ========================================================================
# 子类包装 — 确保策略不在 on_bar 中做会报错的事
# ========================================================================

class TestDualMACrossover(DualMACrossoverStrategy):
    pass


class TestRSIReversal(RSIReversalStrategy):
    pass


class TestBollingerBounce(BollingerBounceStrategy):
    pass


class TestMACDDivergence(MACDDivergenceStrategy):
    pass


class TestDualThrust(DualThrustStrategy):
    pass


class TestMeanReversion(MeanReversionStrategy):
    pass


class TestMomentum(MomentumStrategy):
    pass


# ========================================================================
# 测试用例
# ========================================================================


def test_dual_ma_crossover(cerebro_with_feed):
    """双均线交叉策略可运行"""
    cerebro = cerebro_with_feed
    cerebro.add_strategy(TestDualMACrossover)
    results = cerebro.run()
    assert len(results) == 1
    assert "metrics" in results[0]


def test_rsi_reversal(cerebro_with_feed):
    """RSI 反转策略可运行"""
    cerebro = cerebro_with_feed
    cerebro.add_strategy(TestRSIReversal)
    results = cerebro.run()
    assert len(results) == 1


def test_bollinger_bounce(cerebro_with_feed):
    """布林带策略可运行"""
    cerebro = cerebro_with_feed
    cerebro.add_strategy(TestBollingerBounce)
    results = cerebro.run()
    assert len(results) == 1


def test_macd_divergence(cerebro_with_feed):
    """MACD 背离策略可运行"""
    cerebro = cerebro_with_feed
    cerebro.add_strategy(TestMACDDivergence)
    results = cerebro.run()
    assert len(results) == 1


def test_dual_thrust(cerebro_with_feed):
    """Dual Thrust 策略可运行"""
    cerebro = cerebro_with_feed
    cerebro.add_strategy(TestDualThrust)
    results = cerebro.run()
    assert len(results) == 1


def test_mean_reversion(cerebro_with_feed):
    """均值回归策略可运行"""
    cerebro = cerebro_with_feed
    cerebro.add_strategy(TestMeanReversion)
    results = cerebro.run()
    assert len(results) == 1


def test_momentum(cerebro_with_feed):
    """动量策略可运行"""
    cerebro = cerebro_with_feed
    cerebro.add_strategy(TestMomentum)
    results = cerebro.run()
    assert len(results) == 1


def test_all_templates_have_parameters():
    """所有模板都有 parameters 定义"""
    templates = [
        DualMACrossoverStrategy,
        RSIReversalStrategy,
        BollingerBounceStrategy,
        MACDDivergenceStrategy,
        DualThrustStrategy,
        MeanReversionStrategy,
        MomentumStrategy,
    ]
    for tpl in templates:
        assert hasattr(tpl, "parameters")
        assert isinstance(tpl.parameters, dict)
        assert len(tpl.parameters) > 0


def test_all_templates_have_name():
    """所有模板都有 name 定义"""
    templates = [
        DualMACrossoverStrategy,
        RSIReversalStrategy,
        BollingerBounceStrategy,
        MACDDivergenceStrategy,
        DualThrustStrategy,
        MeanReversionStrategy,
        MomentumStrategy,
    ]
    for tpl in templates:
        assert hasattr(tpl, "name")
        assert isinstance(tpl.name, str)
        assert len(tpl.name) > 0
