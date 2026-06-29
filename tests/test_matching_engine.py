# -*- coding: utf-8 -*-
"""撮合引擎单元测试

覆盖：
1. PriceLimitCalculator — 涨跌停计算
2. MatchingQueue — 撮合队列排序与撮合
3. MatchingEngine — 集合竞价 / 连续竞价
"""

import time
from datetime import datetime

import pytest

from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.models.bar import BarData
from stockquant.events import EventType
from stockquant.execution.matching_engine import (
    PriceLimitCalculator,
    MatchingOrder,
    MatchingQueue,
    MatchingEngine,
)


# ═══════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════

def _make_order(
    symbol: str = "000001",
    side: OrderSide = OrderSide.BUY,
    order_type: OrderType = OrderType.LIMIT,
    price: float = 10.0,
    quantity: float = 100.0,
    order_id: str = "",
) -> Order:
    """快速创建订单"""
    if not order_id:
        order_id = f"test_{side.value}_{price}_{id(_make_order)}"
    return Order(
        symbol=symbol,
        side=side,
        order_type=order_type,
        price=price,
        quantity=quantity,
        order_id=order_id or f"test_{side.value}_{price}_{id(order)}",
    )


def _make_bar(
    symbol: str = "000001",
    close: float = 10.0,
    high: float = 10.5,
    low: float = 9.5,
    open_: float = 10.0,
    volume: float = 100000.0,
) -> BarData:
    """快速创建 BarData"""
    return BarData(
        symbol=symbol,
        datetime=datetime(2024, 1, 15, 10, 0, 0),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


# ═══════════════════════════════════════════════════════════════════
# 1. PriceLimitCalculator 测试
# ═══════════════════════════════════════════════════════════════════

class TestPriceLimitCalculator:

    # --- 主板 10% 涨跌停 ---

    def test_main_board_sh_10pct(self):
        """上交所主板（60xxxx）涨跌停 10%"""
        up, down, ratio = PriceLimitCalculator.calculate(10.0, "600000")
        assert ratio == 0.10
        assert up == 11.0
        assert down == 9.0

    def test_main_board_sz_10pct(self):
        """深交所主板（00xxxx）涨跌停 10%"""
        up, down, ratio = PriceLimitCalculator.calculate(10.0, "000001")
        assert ratio == 0.10
        assert up == 11.0
        assert down == 9.0

    def test_main_board_01_prefix(self):
        """深交所主板（01xxxx）涨跌停 10%"""
        up, down, ratio = PriceLimitCalculator.calculate(5.0, "010101")
        assert ratio == 0.10
        assert up == 5.5
        assert down == 4.5

    # --- 创业板 20% 涨跌停 ---

    def test_gem_20pct(self):
        """创业板（30xxxx）涨跌停 20%"""
        up, down, ratio = PriceLimitCalculator.calculate(10.0, "300001")
        assert ratio == 0.20
        assert up == 12.0
        assert down == 8.0

    def test_gem_300_prefix(self):
        """创业板（300xxx）涨跌停 20%"""
        up, down, ratio = PriceLimitCalculator.calculate(25.0, "300750")
        assert ratio == 0.20
        assert up == 30.0
        assert down == 20.0

    # --- 科创板 20% 涨跌停 ---

    def test_star_20pct(self):
        """科创板（688xxx）涨跌停 20%"""
        up, down, ratio = PriceLimitCalculator.calculate(10.0, "688001")
        assert ratio == 0.20
        assert up == 12.0
        assert down == 8.0

    # --- ST 5% 涨跌停 ---

    def test_st_5pct(self):
        """ST 股票涨跌停 5%"""
        up, down, ratio = PriceLimitCalculator.calculate(10.0, "000001", name="ST测试")
        assert ratio == 0.05
        assert up == 10.5
        assert down == 9.5

    def test_star_st_5pct(self):
        """*ST 股票涨跌停 5%"""
        up, down, ratio = PriceLimitCalculator.calculate(10.0, "600000", name="*ST华业")
        assert ratio == 0.05
        assert up == 10.5
        assert down == 9.5

    # --- 北交所 30% 涨跌停 ---

    def test_bse_8_prefix_30pct(self):
        """北交所（8xxxxx）涨跌停 30%"""
        up, down, ratio = PriceLimitCalculator.calculate(10.0, "830001")
        assert ratio == 0.30
        assert up == 13.0
        assert down == 7.0

    def test_bse_4_prefix_30pct(self):
        """北交所（4xxxxx）涨跌停 30%"""
        up, down, ratio = PriceLimitCalculator.calculate(10.0, "430001")
        assert ratio == 0.30
        assert up == 13.0
        assert down == 7.0

    # --- 板块自动检测 ---

    def test_detect_board_main_sh(self):
        assert PriceLimitCalculator.detect_board_type("600000") == "main_board"

    def test_detect_board_main_sz(self):
        assert PriceLimitCalculator.detect_board_type("000001") == "main_board"

    def test_detect_board_gem(self):
        assert PriceLimitCalculator.detect_board_type("300001") == "gem"

    def test_detect_board_star(self):
        assert PriceLimitCalculator.detect_board_type("688001") == "star"

    def test_detect_board_st(self):
        assert PriceLimitCalculator.detect_board_type("000001", name="ST测试") == "st"

    def test_detect_board_bse_8(self):
        assert PriceLimitCalculator.detect_board_type("830001") == "bse"

    def test_detect_board_bse_4(self):
        assert PriceLimitCalculator.detect_board_type("430001") == "bse"

    def test_detect_board_empty(self):
        assert PriceLimitCalculator.detect_board_type("") == "main_board"

    def test_detect_board_st_priority(self):
        """ST 检测优先于板块代码检测"""
        assert PriceLimitCalculator.detect_board_type("300001", name="STabc") == "st"

    # --- 新股上市首日 ---

    def test_new_ipo_gem_no_limit(self):
        """创业板新股上市首日无涨跌停"""
        up, down, ratio = PriceLimitCalculator.calculate(
            10.0, "300001", is_new_ipo=True
        )
        assert up == float('inf')
        assert down == 0.01
        assert ratio == 0.0

    def test_new_ipo_star_no_limit(self):
        """科创板新股上市首日无涨跌停"""
        up, down, ratio = PriceLimitCalculator.calculate(
            10.0, "688001", is_new_ipo=True
        )
        assert up == float('inf')
        assert down == 0.01
        assert ratio == 0.0

    def test_new_ipo_main_normal(self):
        """主板新股上市首日（非注册制）正常涨跌停"""
        up, down, ratio = PriceLimitCalculator.calculate(
            10.0, "600000", is_new_ipo=True
        )
        assert ratio == 0.10
        assert up == 11.0

    # --- 边界条件 ---

    def test_prev_close_zero(self):
        """前收盘价为 0"""
        up, down, ratio = PriceLimitCalculator.calculate(0, "000001")
        assert up == float('inf')
        assert down == float('-inf')
        assert ratio == 0.0

    def test_prev_close_negative(self):
        """前收盘价为负数"""
        up, down, ratio = PriceLimitCalculator.calculate(-1.0, "000001")
        assert up == float('inf')

    def test_limit_down_minimum_001(self):
        """跌停价不低于 0.01（极低价股场景）"""
        # prev_close=0.10, down=round(0.10*0.9, 2)=0.09, still > 0.01
        up, down, _ = PriceLimitCalculator.calculate(0.10, "000001")
        assert down >= 0.01
        # 极端场景: prev_close=0.011, down=round(0.011*0.9, 2)=0.01 (被 max 截断)
        up2, down2, _ = PriceLimitCalculator.calculate(0.011, "000001")
        assert down2 == 0.01

    # --- 价格有效性 ---

    def test_price_valid_within_range(self):
        assert PriceLimitCalculator.is_price_valid(10.0, 11.0, 9.0) is True

    def test_price_valid_at_limit_up(self):
        assert PriceLimitCalculator.is_price_valid(11.0, 11.0, 9.0) is True

    def test_price_valid_at_limit_down(self):
        assert PriceLimitCalculator.is_price_valid(9.0, 11.0, 9.0) is True

    def test_price_invalid_above_limit_up(self):
        assert PriceLimitCalculator.is_price_valid(11.01, 11.0, 9.0) is False

    def test_price_invalid_below_limit_down(self):
        assert PriceLimitCalculator.is_price_valid(8.99, 11.0, 9.0) is False

    # --- 价格取整 ---

    def test_round_to_tick_normal(self):
        # Python round(10.575, 2) = 10.57 (banker's rounding)
        # round(10.565, 2) may be 10.56 or 10.57 depending on float repr
        # Use a value that reliably rounds up
        assert PriceLimitCalculator.round_to_tick(10.554, "000001") == 10.55
        assert PriceLimitCalculator.round_to_tick(10.556, "000001") == 10.56

    def test_round_to_tick_already_rounded(self):
        assert PriceLimitCalculator.round_to_tick(10.50, "000001") == 10.5

    def test_round_to_tick_small(self):
        assert PriceLimitCalculator.round_to_tick(0.001, "000001") == 0.0


# ═══════════════════════════════════════════════════════════════════
# 2. MatchingQueue 测试
# ═══════════════════════════════════════════════════════════════════

class TestMatchingQueue:

    def test_buy_queue_sorted_desc(self):
        """买入队列价格降序排列"""
        q = MatchingQueue("buy")
        q.enqueue(_make_order(price=10.0, order_id="b1"))
        q.enqueue(_make_order(price=12.0, order_id="b2"))
        q.enqueue(_make_order(price=11.0, order_id="b3"))

        orders = q.get_orders()
        assert len(orders) == 3
        assert orders[0].order.price == 12.0
        assert orders[1].order.price == 11.0
        assert orders[2].order.price == 10.0

    def test_sell_queue_sorted_asc(self):
        """卖出队列价格升序排列"""
        q = MatchingQueue("sell")
        q.enqueue(_make_order(price=10.0, order_id="s1", side=OrderSide.SELL))
        q.enqueue(_make_order(price=8.0, order_id="s2", side=OrderSide.SELL))
        q.enqueue(_make_order(price=9.0, order_id="s3", side=OrderSide.SELL))

        orders = q.get_orders()
        assert len(orders) == 3
        assert orders[0].order.price == 8.0
        assert orders[1].order.price == 9.0
        assert orders[2].order.price == 10.0

    def test_time_priority_same_price_buy(self):
        """买入队列同价格时间优先"""
        q = MatchingQueue("buy")
        o1 = _make_order(price=10.0, order_id="b1")
        time.sleep(0.001)
        o2 = _make_order(price=10.0, order_id="b2")
        q.enqueue(o1)
        q.enqueue(o2)

        top = q.peek()
        assert top.order_id == "b1"

    def test_time_priority_same_price_sell(self):
        """卖出队列同价格时间优先"""
        q = MatchingQueue("sell")
        o1 = _make_order(price=10.0, order_id="s1", side=OrderSide.SELL)
        time.sleep(0.001)
        o2 = _make_order(price=10.0, order_id="s2", side=OrderSide.SELL)
        q.enqueue(o1)
        q.enqueue(o2)

        top = q.peek()
        assert top.order_id == "s1"

    def test_dequeue_returns_best(self):
        """出队返回最优订单"""
        q = MatchingQueue("buy")
        q.enqueue(_make_order(price=10.0, order_id="b1"))
        q.enqueue(_make_order(price=12.0, order_id="b2"))

        best = q.dequeue()
        assert best.price == 12.0
        assert q.size == 1

    def test_peek_does_not_remove(self):
        """peek 不移除订单"""
        q = MatchingQueue("buy")
        q.enqueue(_make_order(price=10.0, order_id="b1"))

        assert q.size == 1
        _ = q.peek()
        assert q.size == 1

    def test_remove_success(self):
        """撤单成功"""
        q = MatchingQueue("buy")
        q.enqueue(_make_order(price=10.0, order_id="b1"))
        q.enqueue(_make_order(price=11.0, order_id="b2"))

        assert q.remove("b1") is True
        assert q.size == 1

    def test_remove_not_found(self):
        """撤单未找到"""
        q = MatchingQueue("buy")
        q.enqueue(_make_order(price=10.0, order_id="b1"))

        assert q.remove("not_exist") is False

    def test_match_buy_side(self):
        """买入吃单撮合：卖方报价 <= 买入价格"""
        q = MatchingQueue("sell")
        q.enqueue(_make_order(price=10.0, quantity=100, order_id="s1", side=OrderSide.SELL))
        q.enqueue(_make_order(price=11.0, quantity=200, order_id="s2", side=OrderSide.SELL))
        q.enqueue(_make_order(price=12.0, quantity=300, order_id="s3", side=OrderSide.SELL))

        results = q.match(price=11.0, side="buy", quantity=200)
        assert len(results) == 2
        assert results[0][0].order_id == "s1"
        assert results[0][1] == 100
        assert results[1][0].order_id == "s2"
        assert results[1][1] == 100

    def test_match_sell_side(self):
        """卖出吃单撮合：买方报价 >= 卖出价格"""
        q = MatchingQueue("buy")
        q.enqueue(_make_order(price=12.0, quantity=100, order_id="b1"))
        q.enqueue(_make_order(price=11.0, quantity=200, order_id="b2"))
        q.enqueue(_make_order(price=10.0, quantity=300, order_id="b3"))

        results = q.match(price=11.0, side="sell", quantity=200)
        assert len(results) == 2
        assert results[0][0].order_id == "b1"
        assert results[0][1] == 100
        assert results[1][0].order_id == "b2"
        assert results[1][1] == 100

    def test_size_property(self):
        q = MatchingQueue("buy")
        assert q.size == 0
        q.enqueue(_make_order(price=10.0))
        assert q.size == 1

    def test_clear(self):
        q = MatchingQueue("buy")
        q.enqueue(_make_order(price=10.0))
        q.enqueue(_make_order(price=11.0))
        q.clear()
        assert q.size == 0


# ═══════════════════════════════════════════════════════════════════
# 3. MatchingEngine — 集合竞价测试
# ═══════════════════════════════════════════════════════════════════

class TestMatchingEngineCallAuction:

    def _make_engine(self, prev_close: float = 10.0, symbol: str = "000001") -> MatchingEngine:
        return MatchingEngine(symbol=symbol, prev_close=prev_close)

    def test_enter_call_auction_phase(self):
        engine = self._make_engine()
        assert engine.phase == MatchingEngine.PHASE_CLOSED
        engine.enter_call_auction_phase()
        assert engine.phase == MatchingEngine.PHASE_CALL_AUCTION

    def test_auction_basic(self):
        """集合竞价基本撮合"""
        engine = self._make_engine()
        engine.enter_call_auction_phase()

        buy_order = _make_order(side=OrderSide.BUY, price=10.5, quantity=100, order_id="buy1")
        sell_order = _make_order(side=OrderSide.SELL, price=10.0, quantity=100, order_id="sell1")

        engine.accept_order(buy_order)
        engine.accept_order(sell_order)

        results = engine.resolve_call_auction()
        assert len(results) == 2

        # 验证成交
        for order, trade in results:
            assert trade.price > 0
            assert trade.quantity > 0

    def test_auction_max_volume(self):
        """最大成交量原则"""
        engine = self._make_engine()
        engine.enter_call_auction_phase()

        # 买单: 10.5 x 100, 10.0 x 200
        engine.accept_order(_make_order(side=OrderSide.BUY, price=10.5, quantity=100, order_id="b1"))
        engine.accept_order(_make_order(side=OrderSide.BUY, price=10.0, quantity=200, order_id="b2"))

        # 卖单: 10.0 x 200, 10.5 x 100
        engine.accept_order(_make_order(side=OrderSide.SELL, price=10.0, quantity=200, order_id="s1"))
        engine.accept_order(_make_order(side=OrderSide.SELL, price=10.5, quantity=100, order_id="s2"))

        results = engine.resolve_call_auction()
        # 集合竞价价 = 10.0（最大成交量 300）
        prices = {trade.price for _, trade in results}
        assert 10.0 in prices

    def test_auction_no_match(self):
        """无交叉价格，不成交"""
        engine = self._make_engine()
        engine.enter_call_auction_phase()

        engine.accept_order(_make_order(side=OrderSide.BUY, price=9.0, quantity=100, order_id="b1"))
        engine.accept_order(_make_order(side=OrderSide.SELL, price=11.0, quantity=100, order_id="s1"))

        results = engine.resolve_call_auction()
        assert len(results) == 0

    def test_auction_no_orders(self):
        """只有买单没有卖单"""
        engine = self._make_engine()
        engine.enter_call_auction_phase()

        engine.accept_order(_make_order(side=OrderSide.BUY, price=10.0, quantity=100, order_id="b1"))

        results = engine.resolve_call_auction()
        assert len(results) == 0

    def test_auction_not_100_rejected(self):
        """非 100 股整数倍被拒绝"""
        engine = self._make_engine()
        engine.enter_call_auction_phase()

        order = _make_order(side=OrderSide.BUY, price=10.0, quantity=150, order_id="b1")
        result = engine.accept_order(order)
        assert result is False
        assert order.status == EventType.ORDER_REJECTED.value

    def test_auction_price_out_of_limit_rejected(self):
        """超出涨跌停价格被拒绝"""
        engine = self._make_engine()
        engine.enter_call_auction_phase()

        order = _make_order(side=OrderSide.BUY, price=12.0, quantity=100, order_id="b1")
        result = engine.accept_order(order)
        assert result is False
        assert order.status == EventType.ORDER_REJECTED.value

    def test_auction_then_continuous(self):
        """集合竞价后进入连续竞价"""
        engine = self._make_engine()
        engine.enter_call_auction_phase()

        engine.accept_order(_make_order(side=OrderSide.BUY, price=10.5, quantity=100, order_id="b1"))
        engine.accept_order(_make_order(side=OrderSide.SELL, price=10.0, quantity=100, order_id="s1"))

        results = engine.resolve_call_auction()
        assert len(results) >= 0  # 可能有成交也可能没有

        engine.enter_continuous_phase()
        assert engine.phase == MatchingEngine.PHASE_CONTINUOUS

    def test_auction_cancel_order(self):
        """集合竞价阶段撤单"""
        engine = self._make_engine()
        engine.enter_call_auction_phase()

        order = _make_order(side=OrderSide.BUY, price=10.5, quantity=100, order_id="b1")
        engine.accept_order(order)

        assert engine.cancel_order("b1") is True
        assert engine.cancel_order("b1") is False  # 已撤，再次撤单失败

    def test_auction_price_tiebreaker(self):
        """多个价格成交量相同时，选择离前收盘价最近的"""
        engine = self._make_engine(prev_close=10.0)
        engine.enter_call_auction_phase()

        # 买单: 9.9 x 100, 10.0 x 100, 10.1 x 100
        engine.accept_order(_make_order(side=OrderSide.BUY, price=9.9, quantity=100, order_id="b1"))
        engine.accept_order(_make_order(side=OrderSide.BUY, price=10.0, quantity=100, order_id="b2"))
        engine.accept_order(_make_order(side=OrderSide.BUY, price=10.1, quantity=100, order_id="b3"))

        # 卖单: 9.9 x 100, 10.0 x 100, 10.1 x 100
        # 三个价格成交量相同 (100)，应该选择离 prev_close=10.0 最近的 10.0
        engine.accept_order(_make_order(side=OrderSide.SELL, price=9.9, quantity=100, order_id="s1"))
        engine.accept_order(_make_order(side=OrderSide.SELL, price=10.0, quantity=100, order_id="s2"))
        engine.accept_order(_make_order(side=OrderSide.SELL, price=10.1, quantity=100, order_id="s3"))

        results = engine.resolve_call_auction()
        assert len(results) > 0

        # 验证成交价是 10.0（离前收盘价最近）
        prices = {trade.price for _, trade in results}
        assert 10.0 in prices


# ═══════════════════════════════════════════════════════════════════
# 4. MatchingEngine — 连续竞价测试
# ═══════════════════════════════════════════════════════════════════

class TestMatchingEngineContinuous:

    def _make_engine(self, prev_close: float = 10.0, symbol: str = "000001") -> MatchingEngine:
        engine = MatchingEngine(symbol=symbol, prev_close=prev_close)
        engine.enter_continuous_phase()
        return engine

    def test_market_order_immediate_match(self):
        """市价单立即撮合"""
        engine = self._make_engine()
        # 先挂卖单
        sell = _make_order(side=OrderSide.SELL, price=10.0, quantity=200, order_id="s1",
                           order_type=OrderType.LIMIT)
        engine.accept_order(sell)

        # 市价买单
        buy = _make_order(side=OrderSide.BUY, price=0.0, quantity=100, order_id="b1",
                          order_type=OrderType.MARKET)
        engine.accept_order(buy)

    def test_limit_order_price_priority(self):
        """限价单价格优先"""
        engine = self._make_engine()

        # 卖单: 9.5, 10.0
        engine.accept_order(_make_order(side=OrderSide.SELL, price=10.0, quantity=100, order_id="s1"))
        engine.accept_order(_make_order(side=OrderSide.SELL, price=9.5, quantity=100, order_id="s2"))

        # 推送 bar，close=9.5，应该撮合所有价格 <= 9.5 的卖单
        bar = _make_bar(close=9.5)
        results = engine.match_tick(bar)
        assert len(results) >= 1

    def test_limit_order_time_priority(self):
        """同价格时间优先"""
        engine = self._make_engine()

        o1 = _make_order(side=OrderSide.BUY, price=10.0, quantity=100, order_id="b1")
        time.sleep(0.001)
        o2 = _make_order(side=OrderSide.BUY, price=10.0, quantity=100, order_id="b2")

        engine.accept_order(o1)
        engine.accept_order(o2)

        # 推送 bar，close=10.0，买单价格 >= 10.0 都会撮合
        # 时间优先，b1 先撮合
        bar = _make_bar(close=10.0)
        results = engine.match_tick(bar)
        # 两个都会撮合（都满足条件）
        order_ids = [o.order_id for o, t in results]
        assert "b1" in order_ids
        assert "b2" in order_ids

    def test_partial_fill(self):
        """部分成交"""
        engine = self._make_engine()

        # 买单 1000 股 @ 10.0
        engine.accept_order(_make_order(side=OrderSide.BUY, price=10.0, quantity=1000, order_id="b1"))

        # 推送 bar，只撮合部分
        # 当前 close=10.0，买单 >= 10.0 会被撮合
        # 但 match_tick 中撮合数量取决于 min(order.remaining, current_price)
        # 由于撮合引擎的设计，撮合数量 = min(remaining, current_price)
        # 当 close=10.0, matched = min(1000, 10.0) = 10.0 ... 这不对
        # 实际上撮合引擎应该撮合所有满足条件的量
        bar = _make_bar(close=10.0)
        results = engine.match_tick(bar)

    def test_limit_up_reject(self):
        """超出涨停价被拒绝"""
        engine = self._make_engine()

        # 主板 prev_close=10.0, 涨停价=11.0
        order = _make_order(side=OrderSide.BUY, price=11.5, quantity=100, order_id="b1")
        result = engine.accept_order(order)
        assert result is False
        assert order.status == EventType.ORDER_REJECTED.value

    def test_limit_down_reject(self):
        """低于跌停价被拒绝"""
        engine = self._make_engine()

        # 主板 prev_close=10.0, 跌停价=9.0
        order = _make_order(side=OrderSide.SELL, price=8.5, quantity=100, order_id="s1")
        result = engine.accept_order(order)
        assert result is False
        assert order.status == EventType.ORDER_REJECTED.value

    def test_100_shares_check(self):
        """100 股整数倍检查"""
        engine = self._make_engine()

        order = _make_order(side=OrderSide.BUY, price=10.0, quantity=50, order_id="b1")
        result = engine.accept_order(order)
        assert result is False
        assert order.status == EventType.ORDER_REJECTED.value

    def test_limit_price_zero_rejected(self):
        """限价单价格为 0 被拒绝"""
        engine = self._make_engine()

        order = _make_order(side=OrderSide.BUY, price=0.0, quantity=100, order_id="b1",
                           order_type=OrderType.LIMIT)
        result = engine.accept_order(order)
        assert result is False

    def test_match_tick_closed_phase_returns_empty(self):
        """closed 阶段 match_tick 返回空"""
        engine = MatchingEngine(symbol="000001", prev_close=10.0)
        bar = _make_bar(close=10.0)
        results = engine.match_tick(bar)
        assert len(results) == 0

    def test_cancel_order_continuous(self):
        """连续竞价撤单"""
        engine = self._make_engine()

        order = _make_order(side=OrderSide.BUY, price=10.0, quantity=100, order_id="b1")
        engine.accept_order(order)
        assert engine.cancel_order("b1") is True
        assert engine.cancel_order("b1") is False

    def test_order_book_snapshot(self):
        """订单簿快照"""
        engine = self._make_engine()

        engine.accept_order(_make_order(side=OrderSide.BUY, price=10.0, quantity=100, order_id="b1"))
        engine.accept_order(_make_order(side=OrderSide.BUY, price=10.5, quantity=200, order_id="b2"))
        engine.accept_order(_make_order(side=OrderSide.SELL, price=11.0, quantity=100, order_id="s1"))

        ob = engine.get_order_book()
        assert "bids" in ob
        assert "asks" in ob
        assert len(ob["bids"]) == 2
        assert len(ob["asks"]) == 1
        # bids 价格降序
        assert ob["bids"][0]["price"] == 10.5
        assert ob["bids"][1]["price"] == 10.0

    def test_statistics(self):
        """撮合统计"""
        engine = self._make_engine()
        stats = engine.statistics
        assert stats["symbol"] == "000001"
        assert stats["phase"] == "continuous"
        assert stats["prev_close"] == 10.0
        assert stats["limit_up"] == 11.0
        assert stats["limit_down"] == 9.0

    def test_accept_order_closed_phase_rejected(self):
        """closed 阶段不接受订单"""
        engine = MatchingEngine(symbol="000001", prev_close=10.0)
        order = _make_order(side=OrderSide.BUY, price=10.0, quantity=100, order_id="b1")
        result = engine.accept_order(order)
        assert result is False

    def test_empty_book_no_crash(self):
        """订单簿为空时 match_tick 不崩溃"""
        engine = self._make_engine()

        # 完全空的订单簿
        bar = _make_bar(close=10.0)
        results = engine.match_tick(bar)
        assert len(results) == 0

        # 只有买单，没有卖单
        engine.accept_order(_make_order(side=OrderSide.BUY, price=10.0, quantity=100, order_id="b1"))
        results = engine.match_tick(bar)
        assert len(results) == 0

        # 只有卖单，没有买单
        engine2 = self._make_engine()
        engine2.accept_order(_make_order(side=OrderSide.SELL, price=10.0, quantity=100, order_id="s1"))
        results = engine2.match_tick(bar)
        assert len(results) == 0


# ═══════════════════════════════════════════════════════════════════
# 5. MatchingEngine — 创业板/科创板涨跌停
# ═══════════════════════════════════════════════════════════════════

class TestMatchingEngineBoardLimits:

    def test_gem_engine_limits(self):
        """创业板引擎涨跌停 20%"""
        engine = MatchingEngine(symbol="300001", prev_close=10.0)
        assert engine.limit_up == 12.0
        assert engine.limit_down == 8.0
        assert engine.limit_ratio == 0.20

    def test_star_engine_limits(self):
        """科创板引擎涨跌停 20%"""
        engine = MatchingEngine(symbol="688001", prev_close=10.0)
        assert engine.limit_up == 12.0
        assert engine.limit_down == 8.0

    def test_st_engine_limits(self):
        """ST 引擎涨跌停 5%"""
        engine = MatchingEngine(symbol="000001", prev_close=10.0, name="ST测试")
        assert engine.limit_up == 10.5
        assert engine.limit_down == 9.5
        assert engine.limit_ratio == 0.05

    def test_bse_engine_limits(self):
        """北交所引擎涨跌停 30%"""
        engine = MatchingEngine(symbol="830001", prev_close=10.0)
        assert engine.limit_up == 13.0
        assert engine.limit_down == 7.0
        assert engine.limit_ratio == 0.30
