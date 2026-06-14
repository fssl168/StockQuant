# -*- coding: utf-8 -*-
"""F009 风险管理模块测试"""

import time
from unittest.mock import MagicMock

import pytest

from stockquant.engine.risk import RiskManager
from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.models.position import Position


@pytest.fixture
def rm():
    return RiskManager(
        max_position_pct=0.3,
        max_buy_amount=500_000,
        max_total_position_pct=0.9,
        max_daily_loss_pct=0.02,
        max_drawdown_pct=0.15,
        max_orders_per_minute=10,
        global_circuit_breaker_pct=0.05,
    )


@pytest.fixture
def buy_order():
    return Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.LIMIT,
                 price=100.0, quantity=100)


@pytest.fixture
def sell_order():
    return Order(symbol="sh600519", side=OrderSide.SELL, order_type=OrderType.LIMIT,
                 price=100.0, quantity=100)


# ===================================================================
# 基本通过测试
# ===================================================================

class TestRiskBasicPass:
    def test_sell_order_passes(self, rm, sell_order):
        """卖单无需仓位检查，应通过"""
        rm._daily_start_equity = 1_000_000
        valid, reason = rm.check(sell_order, equity=1_000_000, positions={})
        assert valid

    def test_small_buy_passes(self, rm, buy_order):
        """小额买单在限制内应通过"""
        rm._daily_start_equity = 1_000_000
        rm._peak_equity = 1_000_000
        pos = Position(symbol="sh600519", quantity=0, cost_price=0, available=0)
        valid, reason = rm.check(buy_order, equity=1_000_000,
                                 positions={"sh600519": pos}, total_equity=1_000_000)
        assert valid


# ===================================================================
# 规则 1: 订单频率限制
# ===================================================================

class TestOrderRateLimit:
    def test_rate_limit_triggers(self, rm):
        """1 分钟内超过 3 笔应被拒绝"""
        rm._max_orders_per_minute = 3
        rm._daily_start_equity = 1_000_000
        # 发送 3 笔（第 4 笔触发限制）
        for _ in range(3):
            o = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.LIMIT,
                      price=100.0, quantity=100)
            rm.check(o, equity=1_000_000, positions={}, total_equity=1_000_000)
        # 第 4 笔
        o4 = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.LIMIT,
                   price=100.0, quantity=100)
        valid, reason = rm.check(o4, equity=1_000_000, positions={}, total_equity=1_000_000)
        assert not valid
        assert "rate limit" in reason


# ===================================================================
# 规则 2: 单只股票仓位限制
# ===================================================================

class TestPositionPctLimit:
    def test_position_pct_exceeded(self, rm):
        """仓位超过 30% 应被拒绝"""
        rm._daily_start_equity = 1_000_000
        rm._peak_equity = 1_000_000
        # current_price 必须设置，否则 market_value = quantity * 0 = 0
        existing = Position(symbol="sh600519", quantity=100, cost_price=100, available=100,
                            current_price=100)  # 市值 = 10,000
        # 买 3000 股 → new_notional = 300,000 → total = 310,000/1_000_000 = 31% > 30%
        buy = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.LIMIT,
                    price=100.0, quantity=3000)
        valid, reason = rm.check(buy, equity=1_000_000,
                                 positions={"sh600519": existing}, total_equity=1_000_000)
        assert not valid


# ===================================================================
# 规则 3: 单只股票最大买入金额
# ===================================================================

class TestBuyAmountLimit:
    def test_buy_amount_exceeded(self, rm):
        """买入金额超过 50 万应被拒绝（仓位在限制内，金额超了）"""
        rm._daily_start_equity = 1_000_000
        rm._peak_equity = 1_000_000
        # 已有持仓 1000 股（市值 10 万，仓位 10%），再买 5500 股
        # 总仓位 = (1000+5500)*100/1_000_000 = 65% → 先过仓位检查：(100000+550000)/1_000_000 = 65% > 30% ❌
        # 所以用已有持仓 500 股（5 万），买 2000 股（20 万）→ 仓位 25% < 30%，金额 20 万 < 50 万 → 通过
        # 要触发金额限制：已有持仓 2000 股（20 万，20%仓位），买 1000 股（10 万）
        # 总仓位 = (200000+100000)/1_000_000 = 30% → 刚好过（> 不行，>= 不行？）
        # 检查代码：new_pct > self._max_position_pct → 30% > 30% = False → 通过
        # 金额 = 100,000 < 500,000 → 通过 → 没触发
        # 需要：仓位 < 30% 但金额 > 500,000 → 不可能，因为 500,000/1_000_000 = 50% > 30%
        # 所以调整 max_buy_amount 为更小值来测试
        rm._max_buy_amount = 150_000
        existing = Position(symbol="sh600519", quantity=500, cost_price=100, available=500)
        buy = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.LIMIT,
                    price=100.0, quantity=2000)  # 金额 200,000 > 150,000
        valid, reason = rm.check(buy, equity=1_000_000,
                                 positions={"sh600519": existing}, total_equity=1_000_000)
        assert not valid
        assert "200000" in reason


# ===================================================================
# 规则 4: 总仓位上限
# ===================================================================

class TestTotalPositionLimit:
    def test_total_position_exceeded(self, rm):
        """总仓位超过 90% 应被拒绝"""
        rm._daily_start_equity = 1_000_000
        rm._peak_equity = 1_000_000
        pos1 = Position(symbol="sh600519", quantity=80000, cost_price=100, available=80000)
        order = Order(symbol="sz000858", side=OrderSide.BUY, order_type=OrderType.LIMIT,
                      price=100.0, quantity=10000)
        valid, reason = rm.check(order, equity=1_000_000,
                                 positions={"sh600519": pos1},
                                 total_equity=1_000_000)
        assert not valid


# ===================================================================
# 规则 5: 单日最大亏损
# ===================================================================

class TestDailyLossLimit:
    def test_daily_loss_triggers_halt(self, rm):
        """单日亏损达 2% 应触发熔断"""
        rm._daily_start_equity = 1_000_000
        rm._peak_equity = 1_000_000
        equity = 979_999  # 亏损 2.0001%
        buy = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.LIMIT,
                    price=100.0, quantity=100)
        valid, reason = rm.check(buy, equity=equity, positions={}, total_equity=1_000_000)
        assert not valid
        assert rm.is_halted


# ===================================================================
# 规则 6: 累计最大回撤熔断
# ===================================================================

class TestMaxDrawdownLimit:
    def test_max_drawdown_triggers_halt(self, rm):
        """回撤达 15% 应触发熔断"""
        rm._daily_start_equity = 1_000_000
        rm._peak_equity = 1_200_000  # 峰值 120 万
        equity = 1_019_000  # 回撤 (1200000-1019000)/1200000 = 15.08%
        buy = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.LIMIT,
                    price=100.0, quantity=100)
        valid, reason = rm.check(buy, equity=equity, positions={}, total_equity=1_000_000)
        assert not valid
        assert rm.is_halted


# ===================================================================
# 规则 7: 全局熔断
# ===================================================================

class TestGlobalCircuitBreaker:
    def test_global_circuit_breaker_triggers(self, rm):
        """单日跌幅超过 5% 应触发全局熔断"""
        # 先放宽日亏损限制到 10%，避免日亏损先触发
        rm._max_daily_loss_pct = 0.10
        rm._daily_start_equity = 1_000_000
        equity = 949_999  # 跌幅 5.0001% → 日亏损 5% < 10%，不触发日亏损
        buy = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.LIMIT,
                    price=100.0, quantity=100)
        valid, reason = rm.check(buy, equity=equity, positions={}, total_equity=1_000_000)
        assert not valid
        assert "circuit breaker" in reason.lower()


# ===================================================================
# Halt/Resume
# ===================================================================

class TestHaltResume:
    def test_halt_blocks_all_orders(self, rm):
        """熔断状态下所有订单应被拒绝"""
        rm._daily_start_equity = 1_000_000
        rm.halt("Test halt")
        buy = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.LIMIT,
                    price=100.0, quantity=100)
        valid, reason = rm.check(buy, equity=1_000_000, positions={}, total_equity=1_000_000)
        assert not valid
        assert "Halted" in reason

    def test_resume_allows_orders(self, rm):
        """恢复后订单应重新通过"""
        rm.halt("Test halt")
        rm.resume()
        rm._daily_start_equity = 1_000_000
        buy = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.LIMIT,
                    price=100.0, quantity=100)
        valid, reason = rm.check(buy, equity=1_000_000, positions={}, total_equity=1_000_000)
        assert valid
