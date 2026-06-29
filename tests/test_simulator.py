# -*- coding: utf-8 -*-
"""仿真交易模拟器集成测试

完整交易场景测试：
1. 简单买入->卖出完整流程
2. 集合竞价开盘->连续竞价交易
3. 涨跌停订单拒绝
4. 部分成交
5. 资金不足拒绝
6. 可卖数量不足拒绝
7. 多标的并行撮合
"""

import time
from datetime import datetime

import pytest

from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.models.bar import BarData
from stockquant.events import EventType
from stockquant.execution.simulator import Simulator, SimulationAccount
from stockquant.execution.matching_engine import MatchingEngine, PriceLimitCalculator


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
# 场景 1：简单买入->卖出完整流程
# ═══════════════════════════════════════════════════════════════════

class TestScenarioBuySell:

    def test_buy_then_sell_full_cycle(self):
        """场景1：买入1000股 -> 推送行情触发成交 -> 卖出1000股"""
        sim = Simulator(initial_cash=1_000_000.0)

        # 步骤1：买入 1000 股 @ 10.0
        buy_order = _make_order(
            symbol="000001",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=10.0,
            quantity=1000,
            order_id="buy_001",
        )
        ok, msg = sim.place_order(buy_order, prev_close=10.0)
        assert ok is True, msg

        # 账户冻结 10,000
        assert sim.account.frozen_cash == 10000.0
        assert sim.account.available_cash == 990000.0

        # 步骤2：推送行情 close=10.0 触发撮合
        bar = _make_bar(symbol="000001", close=10.0)
        trades = sim.on_bar(bar)

        # 验证成交
        assert len(trades) >= 1
        buy_trade = None
        for t in trades:
            if t.order_id == "buy_001":
                buy_trade = t
                break
        assert buy_trade is not None
        assert buy_trade.price == 10.0
        assert buy_trade.quantity == 1000.0

        # 步骤3：验证账户状态
        # 现金减少了 10000
        assert sim.account.cash == 990000.0
        assert sim.account.frozen_cash == 0.0  # 成交后解冻
        # 持仓 1000 股，均价 10.0
        pos = sim.account.get_position("000001")
        assert pos["quantity"] == 1000.0
        assert pos["avg_cost"] == 10.0

        # 步骤4：卖出 1000 股 @ 11.0
        sell_order = _make_order(
            symbol="000001",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=11.0,
            quantity=1000,
            order_id="sell_001",
        )
        ok, msg = sim.place_order(sell_order, prev_close=10.0)
        assert ok is True, msg

        # 步骤5：推送行情 close=11.0 触发卖出撮合
        bar = _make_bar(symbol="000001", close=11.0)
        trades = sim.on_bar(bar)

        sell_trade = None
        for t in trades:
            if t.order_id == "sell_001":
                sell_trade = t
                break
        assert sell_trade is not None
        assert sell_trade.price == 11.0
        assert sell_trade.quantity == 1000.0

        # 步骤6：验证最终状态
        # 现金 = 990000 + 11000 = 1001000
        assert sim.account.cash == 1001000.0
        # 持仓清空
        pos = sim.account.get_position("000001")
        assert pos["quantity"] == 0.0
        # 总权益
        assert sim.account.total_equity == 1001000.0


# ═══════════════════════════════════════════════════════════════════
# 场景 2：集合竞价开盘->连续竞价交易
# ═══════════════════════════════════════════════════════════════════

class TestScenarioCallAuction:

    def test_call_auction_then_continuous(self):
        """场景2：集合竞价开盘 -> 连续竞价交易"""
        sim = Simulator(initial_cash=1_000_000.0)

        buy_order = _make_order(
            symbol="000001",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=10.5,
            quantity=100,
            order_id="buy_auction_1",
        )
        sell_order = _make_order(
            symbol="000001",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=10.0,
            quantity=100,
            order_id="sell_auction_1",
        )

        # 集合竞价
        trades = sim.on_call_auction(
            symbol="000001",
            orders=[buy_order, sell_order],
            prev_close=10.0,
        )

        # 验证引擎状态
        engine = sim.get_engine("000001", 10.0)
        assert engine.phase == MatchingEngine.PHASE_CONTINUOUS

        # 连续竞价下单
        new_buy = _make_order(
            symbol="000001",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=10.5,
            quantity=100,
            order_id="buy_cont_1",
        )
        ok, _ = sim.place_order(new_buy, prev_close=10.0)
        assert ok is True

        # 推送行情触发连续竞价撮合
        bar = _make_bar(symbol="000001", close=10.5)
        sim.on_bar(bar)


# ═══════════════════════════════════════════════════════════════════
# 场景 3：涨跌停订单拒绝
# ═══════════════════════════════════════════════════════════════════

class TestScenarioPriceLimit:

    def test_buy_above_limit_up_rejected(self):
        """场景3a：买入价超出涨停价被拒绝"""
        sim = Simulator(initial_cash=1_000_000.0)

        order = _make_order(
            symbol="000001",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=11.5,  # prev_close=10.0, limit_up=11.0
            quantity=100,
            order_id="buy_limit_up",
        )
        ok, msg = sim.place_order(order, prev_close=10.0)
        assert ok is False
        assert "price limit" in msg.lower() or "limit" in msg.lower()
        assert order.status == EventType.ORDER_REJECTED.value

    def test_sell_below_limit_down_rejected(self):
        """场景3b：卖出价低于跌停价被拒绝"""
        sim = Simulator(initial_cash=1_000_000.0)
        # 先买入
        buy = _make_order(
            symbol="000001", side=OrderSide.BUY, price=10.0,
            quantity=100, order_id="buy_pre",
        )
        sim.place_order(buy, prev_close=10.0)
        sim.on_bar(_make_bar(symbol="000001", close=10.0))

        # 卖出价低于跌停
        sell = _make_order(
            symbol="000001", side=OrderSide.SELL, price=8.5,
            quantity=100, order_id="sell_limit_down",
        )
        ok, msg = sim.place_order(sell, prev_close=10.0)
        assert ok is False
        assert order_check_rejected(sell)

    def test_gem_wider_limits(self):
        """场景3c：创业板涨跌停 20%"""
        sim = Simulator(initial_cash=1_000_000.0)

        # 12.0 是创业板 prev_close=10.0 的涨停价
        order = _make_order(
            symbol="300001",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=12.0,
            quantity=100,
            order_id="buy_gem",
        )
        ok, _ = sim.place_order(order, prev_close=10.0)
        assert ok is True

    def test_st_narrow_limits(self):
        """场景3d：ST 涨跌停 5%"""
        sim = Simulator(initial_cash=1_000_000.0)

        # 10.5 是 ST prev_close=10.0 的涨停价
        order = _make_order(
            symbol="000001",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=10.5,
            quantity=100,
            order_id="buy_st",
        )
        ok, _ = sim.place_order(order, prev_close=10.0, name="ST测试")
        assert ok is True

        # 10.6 超出涨停
        order2 = _make_order(
            symbol="000001",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=10.6,
            quantity=100,
            order_id="buy_st_over",
        )
        ok, _ = sim.place_order(order2, prev_close=10.0, name="ST测试")
        assert ok is False


def order_check_rejected(order: Order) -> bool:
    """检查订单是否被拒绝"""
    return order.status == EventType.ORDER_REJECTED.value


# ═══════════════════════════════════════════════════════════════════
# 场景 4：部分成交
# ═══════════════════════════════════════════════════════════════════

class TestScenarioPartialFill:

    def test_partial_fill_on_sell(self):
        """场景4：卖出后部分成交"""
        sim = Simulator(initial_cash=1_000_000.0)

        # 买入 1000 股
        buy = _make_order(
            symbol="000001", side=OrderSide.BUY, price=10.0,
            quantity=1000, order_id="buy_001",
        )
        sim.place_order(buy, prev_close=10.0)
        sim.on_bar(_make_bar(symbol="000001", close=10.0))

        # 挂卖单 1000 股 @ 11.0
        sell = _make_order(
            symbol="000001", side=OrderSide.SELL, price=11.0,
            quantity=1000, order_id="sell_001",
        )
        ok, _ = sim.place_order(sell, prev_close=10.0)
        assert ok is True

        # 推送 bar close=10.5 < 卖单价格 11.0，不会撮合
        bar = _make_bar(symbol="000001", close=10.5)
        trades = sim.on_bar(bar)
        sell_trades = [t for t in trades if t.order_id == "sell_001"]
        assert len(sell_trades) == 0

        # 推送 bar close=11.0 >= 卖单价格 11.0，会撮合
        bar = _make_bar(symbol="000001", close=11.0)
        trades = sim.on_bar(bar)
        sell_trades = [t for t in trades if t.order_id == "sell_001"]
        assert len(sell_trades) >= 1


# ═══════════════════════════════════════════════════════════════════
# 场景 5：资金不足拒绝
# ═══════════════════════════════════════════════════════════════════

class TestScenarioInsufficientCash:

    def test_insufficient_cash_rejected(self):
        """场景5：资金不足拒绝"""
        sim = Simulator(initial_cash=10000.0)

        order = _make_order(
            symbol="000001", side=OrderSide.BUY, price=200.0,
            quantity=100, order_id="buy_big",
        )
        # 200 * 100 = 20000 > 10000
        ok, msg = sim.place_order(order, prev_close=10.0)
        assert ok is False
        assert "insufficient" in msg.lower()
        assert order.status == EventType.ORDER_REJECTED.value

    def test_exact_cash_accepted(self):
        """刚好够的资金"""
        sim = Simulator(initial_cash=10000.0)

        order = _make_order(
            symbol="000001", side=OrderSide.BUY, price=10.0,
            quantity=1000, order_id="buy_exact",
        )
        ok, _ = sim.place_order(order, prev_close=10.0)
        assert ok is True

    def test_no_prev_close_rejected(self):
        """无前收盘价被拒绝"""
        sim = Simulator(initial_cash=1_000_000.0)

        order = _make_order(
            symbol="000001", side=OrderSide.BUY, price=10.0,
            quantity=100, order_id="buy_no_prev",
        )
        ok, msg = sim.place_order(order, prev_close=0.0)
        assert ok is False


# ═══════════════════════════════════════════════════════════════════
# 场景 6：可卖数量不足拒绝
# ═══════════════════════════════════════════════════════════════════

class TestScenarioInsufficientSellable:

    def test_sell_without_position_rejected(self):
        """场景6a：无持仓卖出被拒绝"""
        sim = Simulator(initial_cash=1_000_000.0)

        order = _make_order(
            symbol="000001", side=OrderSide.SELL, price=10.0,
            quantity=100, order_id="sell_no_pos",
        )
        ok, msg = sim.place_order(order, prev_close=10.0)
        assert ok is False
        assert "sellable" in msg.lower() or "quantity" in msg.lower()

    def test_sell_more_than_holding_rejected(self):
        """场景6b：卖出超过持仓被拒绝"""
        sim = Simulator(initial_cash=1_000_000.0)

        # 买入 100 股
        buy = _make_order(
            symbol="000001", side=OrderSide.BUY, price=10.0,
            quantity=100, order_id="buy_small",
        )
        sim.place_order(buy, prev_close=10.0)
        sim.on_bar(_make_bar(symbol="000001", close=10.0))

        # 尝试卖出 200 股
        sell = _make_order(
            symbol="000001", side=OrderSide.SELL, price=11.0,
            quantity=200, order_id="sell_too_much",
        )
        ok, msg = sim.place_order(sell, prev_close=10.0)
        assert ok is False

    def test_sell_exact_holding_accepted(self):
        """场景6c：卖出刚好等于持仓"""
        sim = Simulator(initial_cash=1_000_000.0)

        buy = _make_order(
            symbol="000001", side=OrderSide.BUY, price=10.0,
            quantity=100, order_id="buy_100",
        )
        sim.place_order(buy, prev_close=10.0)
        sim.on_bar(_make_bar(symbol="000001", close=10.0))

        sell = _make_order(
            symbol="000001", side=OrderSide.SELL, price=11.0,
            quantity=100, order_id="sell_100",
        )
        ok, _ = sim.place_order(sell, prev_close=10.0)
        assert ok is True


# ═══════════════════════════════════════════════════════════════════
# 场景 7：多标的并行撮合
# ═══════════════════════════════════════════════════════════════════

class TestScenarioMultiSymbol:

    def test_multi_symbol_parallel(self):
        """场景7：多标的并行撮合"""
        sim = Simulator(initial_cash=2_000_000.0)

        # 标的 A：000001 主板
        buy_a = _make_order(
            symbol="000001", side=OrderSide.BUY, price=10.0,
            quantity=100, order_id="buy_a",
        )
        ok, _ = sim.place_order(buy_a, prev_close=10.0)
        assert ok is True

        # 标的 B：300001 创业板
        buy_b = _make_order(
            symbol="300001", side=OrderSide.BUY, price=20.0,
            quantity=100, order_id="buy_b",
        )
        ok, _ = sim.place_order(buy_b, prev_close=20.0)
        assert ok is True

        # 推送 A 的行情
        bar_a = _make_bar(symbol="000001", close=10.0)
        trades_a = sim.on_bar(bar_a)

        # 推送 B 的行情
        bar_b = _make_bar(symbol="300001", close=20.0)
        trades_b = sim.on_bar(bar_b)

        # 验证两个标的都有引擎
        assert sim.get_engine("000001", 10.0) is not None
        assert sim.get_engine("300001", 20.0) is not None

        # 验证两个引擎独立
        assert sim.get_engine("000001", 10.0).limit_up == 11.0  # 主板 10%
        assert sim.get_engine("300001", 20.0).limit_up == 24.0  # 创业板 20%

        # 订单簿独立
        ob_a = sim.get_order_book("000001")
        ob_b = sim.get_order_book("300001")
        assert "bids" in ob_a
        assert "bids" in ob_b

    def test_multi_symbol_independent_phases(self):
        """多标的独立阶段"""
        sim = Simulator(initial_cash=2_000_000.0)

        # A 进入集合竞价
        engine_a = sim.get_engine("000001", 10.0)
        engine_a.enter_call_auction_phase()
        assert engine_a.phase == MatchingEngine.PHASE_CALL_AUCTION

        # B 进入连续竞价
        engine_b = sim.get_engine("300001", 20.0)
        engine_b.enter_continuous_phase()
        assert engine_b.phase == MatchingEngine.PHASE_CONTINUOUS

        # 互不影响
        assert sim.get_engine("000001", 10.0).phase == MatchingEngine.PHASE_CALL_AUCTION
        assert sim.get_engine("300001", 20.0).phase == MatchingEngine.PHASE_CONTINUOUS


# ═══════════════════════════════════════════════════════════════════
# 撤单测试
# ═══════════════════════════════════════════════════════════════════

class TestCancelOrder:

    def test_cancel_buy_order_unfreezes_cash(self):
        """撤买单解冻资金"""
        sim = Simulator(initial_cash=1_000_000.0)

        order = _make_order(
            symbol="000001", side=OrderSide.BUY, price=10.0,
            quantity=1000, order_id="buy_cancel",
        )
        sim.place_order(order, prev_close=10.0)
        assert sim.account.frozen_cash == 10000.0

        success = sim.cancel_order("buy_cancel")
        assert success is True
        assert sim.account.frozen_cash == 0.0
        assert sim.account.available_cash == 1_000_000.0

    def test_cancel_sell_order(self):
        """撤卖单"""
        sim = Simulator(initial_cash=1_000_000.0)

        # 先买入
        buy = _make_order(
            symbol="000001", side=OrderSide.BUY, price=10.0,
            quantity=100, order_id="buy_pre",
        )
        sim.place_order(buy, prev_close=10.0)
        sim.on_bar(_make_bar(symbol="000001", close=10.0))

        # 卖单
        sell = _make_order(
            symbol="000001", side=OrderSide.SELL, price=11.0,
            quantity=100, order_id="sell_cancel",
        )
        sim.place_order(sell, prev_close=10.0)

        success = sim.cancel_order("sell_cancel")
        assert success is True

    def test_cancel_nonexistent_order(self):
        """撤不存在的订单"""
        sim = Simulator(initial_cash=1_000_000.0)
        assert sim.cancel_order("not_exist") is False


# ═══════════════════════════════════════════════════════════════════
# SimulationAccount 独立测试
# ═══════════════════════════════════════════════════════════════════

class TestSimulationAccount:

    def test_initial_state(self):
        """初始状态"""
        acc = SimulationAccount(1_000_000.0)
        assert acc.cash == 1_000_000.0
        assert acc.available_cash == 1_000_000.0
        assert acc.frozen_cash == 0.0
        assert acc.total_equity == 1_000_000.0
        assert len(acc.positions) == 0

    def test_freeze_and_unfreeze(self):
        """冻结与解冻"""
        acc = SimulationAccount(100000.0)

        assert acc.freeze_cash(50000.0) is True
        assert acc.frozen_cash == 50000.0
        assert acc.available_cash == 50000.0

        acc.unfreeze_cash(20000.0)
        assert acc.frozen_cash == 30000.0
        assert acc.available_cash == 70000.0

    def test_freeze_insufficient_fails(self):
        """冻结超过可用资金"""
        acc = SimulationAccount(100000.0)
        assert acc.freeze_cash(200000.0) is False

    def test_freeze_zero_fails(self):
        """冻结 0"""
        acc = SimulationAccount(100000.0)
        assert acc.freeze_cash(0.0) is False

    def test_buy_updates_position(self):
        """买入更新持仓"""
        acc = SimulationAccount(100000.0)
        acc.update_position("000001", "Buy", 100, 10.0)

        pos = acc.get_position("000001")
        assert pos["quantity"] == 100.0
        assert pos["avg_cost"] == 10.0
        assert pos["available"] == 100.0

    def test_buy_updates_avg_cost(self):
        """多次买入更新均价"""
        acc = SimulationAccount(100000.0)
        acc.update_position("000001", "Buy", 100, 10.0)
        acc.update_position("000001", "Buy", 100, 12.0)

        pos = acc.get_position("000001")
        assert pos["quantity"] == 200.0
        assert pos["avg_cost"] == 11.0

    def test_sell_updates_position(self):
        """卖出更新持仓"""
        acc = SimulationAccount(100000.0)
        acc.update_position("000001", "Buy", 200, 10.0)
        acc.update_position("000001", "Sell", 100, 11.0)

        pos = acc.get_position("000001")
        assert pos["quantity"] == 100.0

    def test_sell_all_clears_position(self):
        """全部卖出清空持仓"""
        acc = SimulationAccount(100000.0)
        acc.update_position("000001", "Buy", 100, 10.0)
        acc.update_position("000001", "Sell", 100, 11.0)

        pos = acc.get_position("000001")
        assert pos["quantity"] == 0.0
        assert pos["avg_cost"] == 0.0

    def test_check_buy_power(self):
        """购买力检查"""
        acc = SimulationAccount(100000.0)
        assert acc.check_buy_power(10.0, 5000) is True   # 50000 < 100000
        assert acc.check_buy_power(10.0, 15000) is False  # 150000 > 100000

    def test_check_sellable(self):
        """可卖检查"""
        acc = SimulationAccount(100000.0)
        assert acc.check_sellable("000001", 100) is False

        acc.update_position("000001", "Buy", 100, 10.0)
        assert acc.check_sellable("000001", 100) is True
        assert acc.check_sellable("000001", 200) is False

    def test_total_equity(self):
        """总权益计算"""
        acc = SimulationAccount(100000.0)
        acc.update_position("000001", "Buy", 100, 10.0)
        acc.update_market_price("000001", 12.0)

        # 现金 100000 + 持仓市值 1200 = 101200
        assert acc.total_equity == 101200.0

    def test_snapshot(self):
        """快照"""
        acc = SimulationAccount(100000.0)
        acc.update_position("000001", "Buy", 100, 10.0)
        acc.update_market_price("000001", 11.0)

        snap = acc.snapshot()
        assert snap["initial_cash"] == 100000.0
        assert "000001" in snap["positions"]
        assert snap["positions"]["000001"]["quantity"] == 100.0
        assert snap["positions"]["000001"]["market_price"] == 11.0
        assert snap["positions"]["000001"]["pnl"] == 100.0  # (11-10)*100
        assert snap["total_trades"] == 0  # 记录交易后才增加

    def test_record_trade(self):
        """交易记录"""
        acc = SimulationAccount(100000.0)

        from stockquant.models.trade import TradeData
        trade = TradeData(
            trade_id="t1",
            order_id="o1",
            symbol="000001",
            side="Buy",
            price=10.0,
            quantity=100,
        )
        acc.record_trade(trade)

        assert len(acc.trade_history) == 1
        assert acc.trade_history[0]["trade_id"] == "t1"

    def test_reset(self):
        """重置"""
        acc = SimulationAccount(100000.0)
        acc.update_position("000001", "Buy", 100, 10.0)
        acc.freeze_cash(50000.0)

        acc.reset()
        assert acc.cash == 100000.0
        assert acc.frozen_cash == 0.0
        assert len(acc.positions) == 0

    def test_reset_with_new_cash(self):
        """重置为新资金"""
        acc = SimulationAccount(100000.0)
        acc.reset(initial_cash=200000.0)
        assert acc.cash == 200000.0


# ═══════════════════════════════════════════════════════════════════
# Simulator 辅助功能测试
# ═══════════════════════════════════════════════════════════════════

class TestSimulatorUtilities:

    def test_statistics(self):
        """统计信息"""
        sim = Simulator(initial_cash=1_000_000.0)
        buy = _make_order(
            symbol="000001", side=OrderSide.BUY, price=10.0,
            quantity=100, order_id="buy_001",
        )
        sim.place_order(buy, prev_close=10.0)

        stats = sim.statistics
        assert "account" in stats
        assert "engines" in stats
        assert "pending_orders" in stats

    def test_order_book(self):
        """订单簿"""
        sim = Simulator(initial_cash=1_000_000.0)
        buy = _make_order(
            symbol="000001", side=OrderSide.BUY, price=10.0,
            quantity=100, order_id="buy_001",
        )
        sim.place_order(buy, prev_close=10.0)

        ob = sim.get_order_book("000001")
        assert "bids" in ob
        assert "asks" in ob

    def test_order_book_empty_symbol(self):
        """不存在的标的订单簿"""
        sim = Simulator(initial_cash=1_000_000.0)
        ob = sim.get_order_book("999999")
        assert ob == {"bids": [], "asks": []}

    def test_reset(self):
        """重置模拟器"""
        sim = Simulator(initial_cash=1_000_000.0)
        buy = _make_order(
            symbol="000001", side=OrderSide.BUY, price=10.0,
            quantity=100, order_id="buy_001",
        )
        sim.place_order(buy, prev_close=10.0)

        sim.reset()
        assert sim.account.cash == 1_000_000.0
        assert len(sim.pending_orders) == 0

    def test_100_shares_check(self):
        """100 股整数倍检查"""
        sim = Simulator(initial_cash=1_000_000.0)

        order = _make_order(
            symbol="000001", side=OrderSide.BUY, price=10.0,
            quantity=50, order_id="buy_50",
        )
        ok, msg = sim.place_order(order, prev_close=10.0)
        assert ok is False
        assert "100" in msg

    def test_pending_orders_property(self):
        """挂单属性"""
        sim = Simulator(initial_cash=1_000_000.0)

        order = _make_order(
            symbol="000001", side=OrderSide.BUY, price=10.0,
            quantity=100, order_id="buy_001",
        )
        sim.place_order(order, prev_close=10.0)
        assert len(sim.pending_orders) == 1
        assert "buy_001" in sim.pending_orders

    def test_on_bar_no_engine(self):
        """推送不存在标的的行情"""
        sim = Simulator(initial_cash=1_000_000.0)
        bar = _make_bar(symbol="999999")
        trades = sim.on_bar(bar)
        assert len(trades) == 0
