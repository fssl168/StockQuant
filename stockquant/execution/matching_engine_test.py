# -*- coding: utf-8 -*-
"""仿真撮合引擎 + 模拟盘账户管理 — 完整测试

覆盖场景:
1. 涨跌停价格计算（各板块）
2. 连续竞价撮合（限价/市价/部分成交/撤单）
3. 集合竞价撮合（开盘 + 收盘，最大成交量原则）
4. 模拟盘账户管理（资金、持仓、费用、盈亏）
5. T+1 约束
6. 状态持久化
7. 行情驱动撮合（on_bar）
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, time as dt_time

import pytest

from stockquant.execution.matching_engine import (
    ASharePriceLimit,
    CallAuctionEngine,
    ContinuousMatchingEngine,
    OrderBook,
    OrderEntry,
    SimulationMatchingEngine,
)
from stockquant.execution.account_manager import (
    CommissionConfig,
    FeeCalculator,
    PaperAccount,
    PositionInfo,
)
from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.models.bar import BarData


# ═══════════════════════════════════════════════════════════════════
# 1. 涨跌停价格计算
# ═══════════════════════════════════════════════════════════════════

class TestASharePriceLimit:

    def test_main_board_10pct(self):
        """主板 10% 涨跌停"""
        ratio = ASharePriceLimit.get_ratio("000001")
        assert ratio == 0.10
        ratio = ASharePriceLimit.get_ratio("600000")
        assert ratio == 0.10

    def test_gem_20pct(self):
        """创业板 20% 涨跌停"""
        ratio = ASharePriceLimit.get_ratio("300001")
        assert ratio == 0.20
        ratio = ASharePriceLimit.get_ratio("300123")
        assert ratio == 0.20

    def test_starch_20pct(self):
        """科创板 20% 涨跌停"""
        ratio = ASharePriceLimit.get_ratio("688001")
        assert ratio == 0.20

    def test_bse_30pct(self):
        """北交所 30% 涨跌停"""
        ratio = ASharePriceLimit.get_ratio("830001")
        assert ratio == 0.30
        ratio = ASharePriceLimit.get_ratio("870001")
        assert ratio == 0.30
        ratio = ASharePriceLimit.get_ratio("430001")
        assert ratio == 0.30

    def test_default_ratio(self):
        """未知代码使用默认 10%"""
        ratio = ASharePriceLimit.get_ratio("")
        assert ratio == 0.10
        ratio = ASharePriceLimit.get_ratio("unknown")
        assert ratio == 0.10

    def test_calculate_limits(self):
        """计算涨跌停价格"""
        up, down = ASharePriceLimit.calculate_limits(10.0, "600000")
        assert up == 11.0
        assert down == 9.0

    def test_calculate_limits_20pct(self):
        """20% 涨跌停"""
        up, down = ASharePriceLimit.calculate_limits(10.0, "300001")
        assert up == 12.0
        assert down == 8.0

    def test_round_to_cent(self):
        """四舍五入到分"""
        up, down = ASharePriceLimit.calculate_limits(10.05, "600000")
        assert up == 11.06  # 10.05 * 1.1 = 11.055 -> 11.06
        assert down == 9.05  # 10.05 * 0.9 = 9.045 -> 9.04 或 9.05

    def test_is_within_limits(self):
        """涨跌停范围检查"""
        assert ASharePriceLimit.is_within_limits(10.5, 10.0, "600000")
        assert not ASharePriceLimit.is_within_limits(11.1, 10.0, "600000")
        assert not ASharePriceLimit.is_within_limits(8.9, 10.0, "600000")

    def test_zero_previous_close(self):
        """前收盘为 0 时放行"""
        assert ASharePriceLimit.is_within_limits(100.0, 0.0)


# ═══════════════════════════════════════════════════════════════════
# 2. OrderBook 测试
# ═══════════════════════════════════════════════════════════════════

class TestOrderBook:

    def test_buy_sorted_by_price_desc(self):
        """买单按价格降序"""
        book = OrderBook()
        book.add_order(OrderEntry("o1", "600000", OrderSide.BUY, 10.0, 100, time.time()))
        book.add_order(OrderEntry("o2", "600000", OrderSide.BUY, 10.5, 100, time.time()))
        assert book.best_bid == 10.5

    def test_sell_sorted_by_price_asc(self):
        """卖单按价格升序"""
        book = OrderBook()
        book.add_order(OrderEntry("o1", "600000", OrderSide.SELL, 11.0, 100, time.time()))
        book.add_order(OrderEntry("o2", "600000", OrderSide.SELL, 10.5, 100, time.time()))
        assert book.best_ask == 10.5

    def test_time_priority_same_price(self):
        """同价格时间优先"""
        t1 = time.time()
        t2 = time.time()
        book = OrderBook()
        book.add_order(OrderEntry("o1", "600000", OrderSide.BUY, 10.0, 100, t1))
        book.add_order(OrderEntry("o2", "600000", OrderSide.BUY, 10.0, 100, t2))
        # o1 先于 o2 到达，在买单簿中排在前面（优先）
        assert book._buy_orders[0].order_id == "o1"

    def test_remove_order(self):
        """移除订单"""
        book = OrderBook()
        entry = OrderEntry("o1", "600000", OrderSide.BUY, 10.0, 100, time.time())
        book.add_order(entry)
        removed = book.remove_order("o1")
        assert removed is not None
        assert removed.order_id == "o1"
        assert book.buy_count == 0

    def test_get_order(self):
        """获取订单"""
        book = OrderBook()
        entry = OrderEntry("o1", "600000", OrderSide.BUY, 10.0, 100, time.time())
        book.add_order(entry)
        found = book.get_order("o1")
        assert found is not None
        assert found.price == 10.0

    def test_clear_symbol(self):
        """清空指定股票"""
        book = OrderBook()
        book.add_order(OrderEntry("o1", "600000", OrderSide.BUY, 10.0, 100, time.time()))
        book.add_order(OrderEntry("o2", "300001", OrderSide.BUY, 20.0, 100, time.time()))
        book.clear_symbol("600000")
        assert book.buy_count == 1
        assert book.get_order("o2") is not None
        assert book.get_order("o1") is None

    def test_clear(self):
        """清空全部"""
        book = OrderBook()
        book.add_order(OrderEntry("o1", "600000", OrderSide.BUY, 10.0, 100, time.time()))
        book.add_order(OrderEntry("o2", "600000", OrderSide.SELL, 11.0, 100, time.time()))
        book.clear()
        assert book.buy_count == 0
        assert book.sell_count == 0

    def test_total_quantity(self):
        """总数量查询"""
        book = OrderBook()
        book.add_order(OrderEntry("o1", "600000", OrderSide.BUY, 10.0, 300, time.time()))
        book.add_order(OrderEntry("o2", "600000", OrderSide.BUY, 9.5, 200, time.time()))
        tq = book.total_quantity
        assert tq["buy"][10.0] == 300
        assert tq["buy"][9.5] == 200


# ═══════════════════════════════════════════════════════════════════
# 3. 连续竞价撮合
# ═══════════════════════════════════════════════════════════════════

class TestContinuousMatching:

    def _create_order(self, order_id, symbol, side, price, quantity):
        return Order(
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            price=price,
            quantity=quantity,
            order_id=order_id,
        )

    def test_immediate_fill(self):
        """买入限价单立即成交（有卖单在下方）"""
        engine = ContinuousMatchingEngine()
        # 先放一个卖单
        sell = self._create_order("s1", "600000", OrderSide.SELL, 10.0, 100)
        sell_entry = OrderEntry("s1", "600000", OrderSide.SELL, 10.0, 100, time.time())
        engine.book.add_order(sell_entry)

        # 买入限价单
        buy = self._create_order("b1", "600000", OrderSide.BUY, 10.5, 100)
        trades = engine.match_order(buy, "600000", 10.0)

        assert len(trades) == 1
        assert trades[0].quantity == 100
        assert trades[0].price == 10.0  # 以卖单价格成交

    def test_no_match(self):
        """买单价格低于卖单价格，不成交"""
        engine = ContinuousMatchingEngine()
        sell_entry = OrderEntry("s1", "600000", OrderSide.SELL, 10.5, 100, time.time())
        engine.book.add_order(sell_entry)

        buy = self._create_order("b1", "600000", OrderSide.BUY, 10.0, 100)
        trades = engine.match_order(buy, "600000", 10.0)

        assert len(trades) == 0
        assert engine.get_order_status("b1") in (
            "ORDER_PENDING", "ORDER_PARTIAL_FILL",
        )

    def test_partial_fill(self):
        """部分成交"""
        engine = ContinuousMatchingEngine()
        # 只有一笔 200 股的卖单
        sell_entry = OrderEntry("s1", "600000", OrderSide.SELL, 10.0, 200, time.time())
        engine.book.add_order(sell_entry)

        buy = self._create_order("b1", "600000", OrderSide.BUY, 10.5, 500)
        trades = engine.match_order(buy, "600000", 10.0)

        assert len(trades) == 1
        assert trades[0].quantity == 200

        # 剩余 300 股进入订单簿
        assert engine.get_order_status("b1") == "ORDER_PARTIAL_FILL"
        assert engine.book.get_order("b1") is not None
        assert engine.book.get_order("b1").remaining == 300

    def test_multiple_level_fill(self):
        """跨价位撮合"""
        engine = ContinuousMatchingEngine()
        # 两档卖单
        s1 = OrderEntry("s1", "600000", OrderSide.SELL, 10.0, 100, time.time())
        s2 = OrderEntry("s2", "600000", OrderSide.SELL, 10.2, 100, time.time())
        engine.book.add_order(s1)
        engine.book.add_order(s2)

        buy = self._create_order("b1", "600000", OrderSide.BUY, 10.5, 200)
        trades = engine.match_order(buy, "600000", 10.0)

        assert len(trades) == 2
        assert trades[0].price == 10.0
        assert trades[1].price == 10.2
        assert sum(t.quantity for t in trades) == 200

    def test_market_buy(self):
        """市价买入"""
        engine = ContinuousMatchingEngine()
        sell_entry = OrderEntry("s1", "600000", OrderSide.SELL, 10.0, 100, time.time())
        engine.book.add_order(sell_entry)

        buy = self._create_order("b1", "600000", OrderSide.BUY, 0.0, 100)
        buy.order_type = OrderType.MARKET
        trades = engine.match_order(buy, "600000", 10.0)

        assert len(trades) == 1
        assert trades[0].quantity == 100
        assert trades[0].price == 10.0

    def test_100_lot_rejection(self):
        """非 100 股整数倍被拒绝"""
        engine = ContinuousMatchingEngine()
        buy = self._create_order("b1", "600000", OrderSide.BUY, 10.0, 50)
        result = engine.submit_order(buy, "600000", 10.0)
        assert result is False

    def test_limit_up_rejection(self):
        """超过涨停价被拒绝"""
        engine = ContinuousMatchingEngine()
        buy = self._create_order("b1", "600000", OrderSide.BUY, 11.5, 100)
        result = engine.submit_order(buy, "600000", 10.0)
        assert result is False

    def test_limit_down_rejection(self):
        """低于跌停价被拒绝"""
        engine = ContinuousMatchingEngine()
        sell = self._create_order("s1", "600000", OrderSide.SELL, 8.5, 100)
        result = engine.submit_order(sell, "600000", 10.0)
        assert result is False

    def test_cancel_order(self):
        """撤单"""
        engine = ContinuousMatchingEngine()
        buy = self._create_order("b1", "600000", OrderSide.BUY, 10.0, 100)
        # 不成交，进入订单簿
        trades = engine.match_order(buy, "600000", 10.0)
        assert len(trades) == 0

        result = engine.cancel_order("b1")
        assert result is True
        assert engine.get_order_status("b1") == "ORDER_CANCELLED"

    def test_clear_symbol(self):
        """清空指定股票订单簿"""
        engine = ContinuousMatchingEngine()
        b1 = OrderEntry("b1", "600000", OrderSide.BUY, 10.0, 100, time.time())
        b2 = OrderEntry("b2", "300001", OrderSide.BUY, 20.0, 100, time.time())
        engine.book.add_order(b1)
        engine.book.add_order(b2)

        engine.clear(symbol="600000")
        assert engine.book.get_order("b1") is None
        assert engine.book.get_order("b2") is not None

    def test_trade_log(self):
        """交易记录"""
        engine = ContinuousMatchingEngine()
        sell_entry = OrderEntry("s1", "600000", OrderSide.SELL, 10.0, 100, time.time())
        engine.book.add_order(sell_entry)

        buy = self._create_order("b1", "600000", OrderSide.BUY, 10.5, 100)
        engine.match_order(buy, "600000", 10.0)

        log = engine.trade_log
        assert len(log) == 1
        assert log[0].side == "Buy"
        assert log[0].price == 10.0


# ═══════════════════════════════════════════════════════════════════
# 4. 集合竞价
# ═══════════════════════════════════════════════════════════════════

class TestCallAuction:

    def test_auction_price_calculation(self):
        """集合竞价成交价计算（最大成交量原则）"""
        buys = [
            OrderEntry("b1", "600000", OrderSide.BUY, 11.0, 100, time.time()),
            OrderEntry("b2", "600000", OrderSide.BUY, 10.5, 200, time.time()),
            OrderEntry("b3", "600000", OrderSide.BUY, 10.0, 300, time.time()),
        ]
        sells = [
            OrderEntry("s1", "600000", OrderSide.SELL, 10.0, 200, time.time()),
            OrderEntry("s2", "600000", OrderSide.SELL, 10.5, 100, time.time()),
            OrderEntry("s3", "600000", OrderSide.SELL, 11.0, 100, time.time()),
        ]

        price = CallAuctionEngine.calculate_implementation_price(buys, sells)
        assert price is not None
        # 在 10.0 价位：买方可成交 600，卖方可成交 200 -> 200
        # 在 10.5 价位：买方可成交 300，卖方可成交 200 -> 200
        # 成交量相同取更低价格 10.0
        assert price == 10.0

    def test_auction_no_match(self):
        """没有可撮合的订单"""
        price = CallAuctionEngine.calculate_implementation_price([], [])
        assert price is None

        price = CallAuctionEngine.calculate_implementation_price([],
                                                               [OrderEntry("s1", "", OrderSide.SELL, 10.0, 100, time.time())])
        assert price is None

    def test_auction_execute(self):
        """执行集合竞价"""
        buys = [
            OrderEntry("b1", "600000", OrderSide.BUY, 11.0, 100, time.time()),
            OrderEntry("b2", "600000", OrderSide.BUY, 10.5, 100, time.time()),
        ]
        sells = [
            OrderEntry("s1", "600000", OrderSide.SELL, 10.0, 100, time.time()),
            OrderEntry("s2", "600000", OrderSide.SELL, 10.5, 100, time.time()),
        ]

        filled = CallAuctionEngine.execute_call_auction(buys, sells, 10.5)
        assert len(filled) == 4
        # b1: price=11 >= 10.5 -> 成交 100
        # b2: price=10.5 >= 10.5 -> 成交 100
        # s1: price=10 <= 10.5 -> 成交 100
        # s2: price=10.5 <= 10.5 -> 成交 100

    def test_time_period_detection(self):
        """集合竞价时段检测"""
        assert CallAuctionEngine.is_in_open_auction(dt_time(9, 20, 0)) is True
        assert CallAuctionEngine.is_in_open_auction(dt_time(9, 14, 0)) is False
        assert CallAuctionEngine.is_in_open_auction(dt_time(9, 25, 0)) is False

        assert CallAuctionEngine.is_in_close_auction(dt_time(14, 58, 0)) is True
        assert CallAuctionEngine.is_in_close_auction(dt_time(14, 56, 0)) is False
        assert CallAuctionEngine.is_in_close_auction(dt_time(15, 0, 0)) is False


# ═══════════════════════════════════════════════════════════════════
# 5. SimulationMatchingEngine 集成测试
# ═══════════════════════════════════════════════════════════════════

class TestSimulationMatchingEngine:

    def _create_order(self, symbol, side, price, quantity, order_type=OrderType.LIMIT):
        return Order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            price=price,
            quantity=quantity,
        )

    def _create_bar(self, symbol, open, high, low, close, dt=None):
        if dt is None:
            dt = datetime(2024, 1, 15, 9, 30)
        return BarData(
            symbol=symbol,
            datetime=dt,
            open=open,
            high=high,
            low=low,
            close=close,
        )

    def test_full_cycle_buy_sell(self):
        """完整买卖循环"""
        engine = SimulationMatchingEngine(initial_cash=1_000_000.0)
        bar = self._create_bar("600000", 10.0, 10.5, 9.8, 10.0)

        # 买入
        order = self._create_order("600000", OrderSide.BUY, 10.0, 1000)
        assert engine.submit_order(order, "600000", 10.0) is True

        trades = engine.match_continuous(order, "600000", 10.0)
        assert len(trades) == 1
        assert trades[0].quantity == 1000
        assert trades[0].price == 10.0

        # 资金变化
        assert engine.cash == 1_000_000.0 - 10.0 * 1000

        # 卖出（价格涨到 11 元）
        bar2 = self._create_bar("600000", 10.5, 11.0, 10.4, 11.0,
                                datetime(2024, 1, 16, 9, 30))
        sell_order = self._create_order("600000", OrderSide.SELL, 10.5, 500)
        # 先挂单进入订单簿
        trades2 = engine.match_continuous(sell_order, "600000", 11.0)
        # 500 股 @ 10.5 卖出
        # 需要等待有买单才能成交，这里先测试挂单
        assert len(trades2) == 0

    def test_insufficient_cash(self):
        """资金不足被拒绝"""
        engine = SimulationMatchingEngine(initial_cash=1_000.0)
        order = self._create_order("600000", OrderSide.BUY, 100.0, 100)
        assert engine.submit_order(order, "600000", 10.0) is False

    def test_portfolio_summary(self):
        """投资组合摘要"""
        engine = SimulationMatchingEngine(initial_cash=1_000_000.0)
        bar = self._create_bar("600000", 10.0, 10.5, 9.8, 10.0)

        order = self._create_order("600000", OrderSide.BUY, 10.0, 1000)
        engine.submit_order(order, "600000", 10.0)
        trades = engine.match_continuous(order, "600000", 10.0)

        summary = engine.get_portfolio_summary()
        assert summary["total_trades"] == 1
        assert summary["num_buy_trades"] == 1
        assert summary["num_positions"] == 1
        assert summary["positions"]["600000"]["quantity"] == 1000

    def test_state_save_load(self):
        """状态持久化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "state.json")
            engine = SimulationMatchingEngine(initial_cash=500_000.0, state_file=filepath)

            # 进行交易
            bar = self._create_bar("600000", 10.0, 10.5, 9.8, 10.0)
            order = self._create_order("600000", OrderSide.BUY, 10.0, 1000)
            engine.submit_order(order, "600000", 10.0)
            engine.match_continuous(order, "600000", 10.0)

            engine.save_state(filepath)

            # 加载到新引擎
            engine2 = SimulationMatchingEngine(initial_cash=100.0, state_file=filepath)
            engine2.load_state(filepath)
            assert engine2.cash == engine.cash

    def test_cancel_buy_order(self):
        """撤买单"""
        engine = SimulationMatchingEngine(initial_cash=100_000.0)
        order = self._create_order("600000", OrderSide.BUY, 10.0, 100)
        engine.submit_order(order, "600000", 10.0)

        # 撤单
        result = engine.cancel_order(order.order_id)
        assert result is True

    def test_call_auction_integration(self):
        """集合竞价集成测试"""
        engine = SimulationMatchingEngine(initial_cash=1_000_000.0)

        # 添加集合竞价订单
        engine.add_auction_order("ba1", "600000", OrderSide.BUY, 11.0, 500)
        engine.add_auction_order("ba2", "600000", OrderSide.BUY, 10.5, 300)
        engine.add_auction_order("sa1", "600000", OrderSide.SELL, 10.0, 400)
        engine.add_auction_order("sa2", "600000", OrderSide.SELL, 10.5, 200)

        trades = engine.execute_call_auction("600000")
        assert trades is not None
        assert len(trades) > 0
        assert all(t.price == trades[0].price for t in trades)


# ═══════════════════════════════════════════════════════════════════
# 6. FeeCalculator 测试
# ═══════════════════════════════════════════════════════════════════

class TestFeeCalculator:

    def test_buy_cost(self):
        """买入费用计算"""
        calc = FeeCalculator()
        result = calc.calculate_buy_cost(10.0, 1000)
        assert result["notional"] == 10000.0
        assert result["commission"] >= 5.0  # 最低 5 元
        assert result["stamp_tax"] == 0.0  # 买入不收印花税

    def test_sell_cost(self):
        """卖出费用计算"""
        calc = FeeCalculator()
        result = calc.calculate_sell_cost(10.0, 1000)
        assert result["notional"] == 10000.0
        assert result["stamp_tax"] == 5.0  # 10000 * 0.0005

    def test_min_commission(self):
        """最低佣金 5 元"""
        calc = FeeCalculator()
        # 100 股 @ 5 元 = 500 元，按 0.025% 佣金只有 0.125 元
        result = calc.calculate_buy_cost(5.0, 100)
        assert result["commission"] == 5.0

    def test_large_trade(self):
        """大额交易按比例收取"""
        calc = FeeCalculator()
        result = calc.calculate_buy_cost(100.0, 10000)
        # 100 * 10000 * 0.00025 = 250 元（无最低限制）
        assert result["commission"] == 250.0


# ═══════════════════════════════════════════════════════════════════
# 7. PaperAccount 测试
# ═══════════════════════════════════════════════════════════════════

class TestPaperAccount:

    def test_initial_state(self):
        """初始状态"""
        account = PaperAccount(initial_cash=500_000.0)
        assert account.cash == 500_000.0
        assert account.available_cash == 500_000.0
        assert account.frozen_cash == 0.0
        assert account.total_equity == 500_000.0

    def test_buy_fill(self):
        """买入成交"""
        account = PaperAccount(initial_cash=500_000.0)
        fees = {"commission": 5.0, "transfer_fee": 0.1, "regulatory_fee": 0.02,
                "total_fee": 5.12}

        pos = account.handle_buy_fill("600000", 1000, 10.0, fees)
        assert pos.quantity == 1000
        assert pos.cost_price == 10.0
        assert account.cash == 500_000.0 - 10.0 * 1000 - 5.12

    def test_sell_fill(self):
        """卖出成交（含已实现盈亏）"""
        account = PaperAccount(initial_cash=500_000.0)
        buy_fees = {"commission": 5.0, "transfer_fee": 0.1, "regulatory_fee": 0.02,
                     "total_fee": 5.12}
        sell_fees = {"commission": 5.0, "transfer_fee": 0.1, "regulatory_fee": 0.02,
                      "stamp_tax": 5.0, "total_fee": 10.12}

        account.handle_buy_fill("600000", 1000, 10.0, buy_fees)
        pos = account.handle_sell_fill("600000", 500, 12.0, sell_fees)

        assert pos is not None
        assert pos.quantity == 500
        assert pos.realized_pnl == (12.0 - 10.0) * 500  # 1000 元

    def test_full_close(self):
        """全部卖出清仓"""
        account = PaperAccount(initial_cash=500_000.0)
        fees = {"commission": 5.0, "transfer_fee": 0.1, "regulatory_fee": 0.02,
                "total_fee": 5.12}

        account.handle_buy_fill("600000", 1000, 10.0, fees)
        result = account.handle_sell_fill("600000", 1000, 10.0, fees)
        assert result is None  # 清仓后返回 None

    def test_freeze_release(self):
        """冻结/释放资金"""
        account = PaperAccount(initial_cash=100_000.0)
        assert account.freeze_cash(10000.0, "order1") is True
        assert account.available_cash == 90000.0
        assert account.frozen_cash == 10000.0

        account.release_cash(10000.0, "order1")
        assert account.available_cash == 100000.0
        assert account.frozen_cash == 0.0

    def test_insufficient_freeze(self):
        """资金不足冻结失败"""
        account = PaperAccount(initial_cash=100.0)
        assert account.freeze_cash(200.0, "order1") is False

    def test_unrealized_pnl(self):
        """未实现盈亏"""
        account = PaperAccount(initial_cash=500_000.0)
        fees = {"commission": 5.0, "transfer_fee": 0.1, "regulatory_fee": 0.02,
                "total_fee": 5.12}
        account.handle_buy_fill("600000", 1000, 10.0, fees)

        account.update_price("600000", 11.0)
        pos = account.get_position("600000")
        assert pos.unrealized_pnl == 1000.0  # (11 - 10) * 1000

    def test_t1_unlock(self):
        """T+1 解除冻结"""
        account = PaperAccount(initial_cash=500_000.0)
        fees = {"commission": 5.0, "transfer_fee": 0.1, "regulatory_fee": 0.02,
                "total_fee": 5.12}
        account.handle_buy_fill("600000", 1000, 10.0, fees)

        pos = account.get_position("600000")
        assert pos.today_bought == 1000
        assert pos.available == 0.0

        unlocked = account.unlock_today_frozen()
        assert unlocked == 1000
        pos = account.get_position("600000")
        assert pos.available == 1000.0
        assert pos.today_bought == 0.0

    def test_summary(self):
        """账户摘要"""
        account = PaperAccount(initial_cash=500_000.0)
        fees = {"commission": 5.0, "transfer_fee": 0.1, "regulatory_fee": 0.02,
                "total_fee": 5.12}

        account.handle_buy_fill("600000", 1000, 10.0, fees)
        account.update_price("600000", 11.0)

        summary = account.summary()
        assert summary["initial_cash"] == 500_000.0
        assert summary["num_positions"] == 1
        assert summary["positions"]["600000"]["quantity"] == 1000
        assert summary["positions"]["600000"]["pnl_pct"] > 0

    def test_state_save_load(self):
        """状态持久化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "account.json")
            account = PaperAccount(
                account_id="test",
                initial_cash=100_000.0,
                state_file=filepath,
            )

            fees = {"commission": 5.0, "transfer_fee": 0.1, "regulatory_fee": 0.02,
                    "total_fee": 5.12}
            account.handle_buy_fill("600000", 500, 20.0, fees)
            account.save_state(filepath)

            # 新账户加载
            account2 = PaperAccount(initial_cash=1000.0, state_file=filepath)
            account2.load_state(filepath)
            assert account2.cash == account.cash
            assert "600000" in account2._positions

    def test_total_pnl(self):
        """总盈亏计算"""
        account = PaperAccount(initial_cash=100_000.0)
        buy_fees = {"commission": 5.0, "transfer_fee": 0.1, "regulatory_fee": 0.02,
                     "total_fee": 5.12}
        sell_fees = {"commission": 5.0, "transfer_fee": 0.1, "regulatory_fee": 0.02,
                      "stamp_tax": 5.0, "total_fee": 10.12}

        # 买 1000 @ 10 元
        account.handle_buy_fill("600000", 1000, 10.0, buy_fees)
        # 卖 1000 @ 12 元
        account.handle_sell_fill("600000", 1000, 12.0, sell_fees)

        # 总盈亏 = (12-10)*1000 - buy_fees - sell_fees
        expected_pnl = 2000 - 5.12 - 10.12
        assert abs(account.total_pnl - expected_pnl) < 1.0


# ═══════════════════════════════════════════════════════════════════
# 8. 综合测试：on_bar 行情驱动
# ═══════════════════════════════════════════════════════════════════

class TestOnBar:

    def _create_order(self, symbol, side, price, quantity):
        return Order(
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            price=price,
            quantity=quantity,
        )

    def _create_bar(self, symbol, open, high, low, close, dt=None):
        if dt is None:
            dt = datetime(2024, 1, 15, 9, 30)
        return BarData(
            symbol=symbol,
            datetime=dt,
            open=open,
            high=high,
            low=low,
            close=close,
        )

    def test_order_book_on_bar(self):
        """on_bar 触发订单簿撮合"""
        engine = SimulationMatchingEngine(initial_cash=1_000_000.0)

        # 先挂一笔 10 元买单
        buy_order = self._create_order("600000", OrderSide.BUY, 10.0, 100)
        engine.submit_order(buy_order, "600000", 10.0)
        # 挂入订单簿（当前行情价格 12 元，不立即成交）
        trades = engine.match_continuous(buy_order, "600000", 10.0)
        assert len(trades) == 0

        # 新 bar：价格跌到 9 元，触及买单
        bar = self._create_bar("600000", 11.0, 11.0, 9.0, 9.0,
                               datetime(2024, 1, 16, 9, 30))
        trades = engine.on_bar(bar)
        # 买单 @10.0, bar low=9.0, 10.0 >= 9.0 可成交
        assert len(trades) > 0
        assert trades[0].quantity == 100

    def test_sell_on_bar(self):
        """on_bar 触发卖出挂单成交"""
        engine = SimulationMatchingEngine(initial_cash=1_000_000.0)

        # 先买 1000 股 @ 10 元
        buy_order = self._create_order("600000", OrderSide.BUY, 10.0, 1000)
        engine.submit_order(buy_order, "600000", 10.0)
        engine.match_continuous(buy_order, "600000", 10.0)

        # 挂卖单 @ 12 元
        sell_order = self._create_order("600000", OrderSide.SELL, 12.0, 500)
        trades = engine.match_continuous(sell_order, "600000", 10.0)
        assert len(trades) == 0  # 当前没有 12 元以下的买单

        # 新 bar：价格涨到 13 元，触及卖单
        bar = self._create_bar("600000", 11.0, 13.0, 11.0, 13.0,
                               datetime(2024, 1, 17, 9, 30))
        trades = engine.on_bar(bar)
        assert len(trades) > 0
        assert trades[0].side == "Sell"


# ═══════════════════════════════════════════════════════════════════
# 9. 涨跌停板边界测试
# ═══════════════════════════════════════════════════════════════════

class TestPriceLimitBoundaries:

    def test_exact_limit_up(self):
        """恰好涨停价应被接受"""
        engine = SimulationMatchingEngine()
        order = Order(
            symbol="600000",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=11.0,  # 10.0 * 1.1 = 11.0
            quantity=100,
        )
        assert engine.submit_order(order, "600000", 10.0) is True

    def test_over_limit_up(self):
        """超过涨停价被拒绝"""
        engine = SimulationMatchingEngine()
        order = Order(
            symbol="600000",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=11.01,
            quantity=100,
        )
        assert engine.submit_order(order, "600000", 10.0) is False

    def test_exact_limit_down(self):
        """恰好跌停价应被接受"""
        engine = SimulationMatchingEngine()
        order = Order(
            symbol="600000",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=9.0,  # 10.0 * 0.9 = 9.0
            quantity=100,
        )
        assert engine.submit_order(order, "600000", 10.0) is True

    def test_below_limit_down(self):
        """低于跌停价被拒绝"""
        engine = SimulationMatchingEngine()
        order = Order(
            symbol="600000",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=8.99,
            quantity=100,
        )
        assert engine.submit_order(order, "600000", 10.0) is False


# ═══════════════════════════════════════════════════════════════════
# 10. 创业板 20% 涨跌停
# ═══════════════════════════════════════════════════════════════════

class TestGEMPriceLimit:

    def test_gem_limit_up(self):
        """创业板涨停 20%"""
        engine = SimulationMatchingEngine()
        order = Order(
            symbol="300001",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=12.0,  # 10.0 * 1.2 = 12.0
            quantity=100,
        )
        assert engine.submit_order(order, "300001", 10.0) is True

    def test_gem_over_limit_up(self):
        """创业板超过 20% 被拒绝"""
        engine = SimulationMatchingEngine()
        order = Order(
            symbol="300001",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=12.01,
            quantity=100,
        )
        assert engine.submit_order(order, "300001", 10.0) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
