# -*- coding: utf-8 -*-
"""T4 LiveBroker 骨架测试"""

import pytest

from stockquant.engine.broker import LiveBroker, OrderAuditLog
from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.events import EventType as OrderStatus
from stockquant.models.bar import BarData
from datetime import datetime


@pytest.fixture
def broker():
    return LiveBroker()


@pytest.fixture
def bar():
    return BarData(
        symbol="sh600519",
        datetime=datetime.now(),
        open=100.0, high=102.0, low=98.0, close=100.0, volume=1_000_000,
    )


# ---------------------------------------------------------------------------
# place_order
# ---------------------------------------------------------------------------

class TestLiveBrokerPlaceOrder:
    def test_place_order_submitted(self, broker, bar):
        """正常买单应被提交，状态为 SUBMITTED"""
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=100.0, quantity=100)
        trade = broker.place_order(order, bar)
        assert trade is not None
        assert trade.symbol == "sh600519"
        assert order.status == "ORDER_SUBMITTED"

    def test_place_order_logged(self, broker, bar):
        """下单应记录审计日志"""
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=100.0, quantity=100)
        broker.place_order(order, bar)
        log = broker.order_audit_log
        submitted = [e for e in log if e.order_id == order.order_id and e.status == "SUBMITTED"]
        assert len(submitted) >= 1

    def test_lot_size_rejected(self, broker, bar):
        """100 股非整数倍的买单应被拒绝"""
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=100.0, quantity=50)
        trade = broker.place_order(order, bar)
        assert trade is None
        assert order.status == "ORDER_REJECTED"

    def test_limit_up_rejected(self, broker, bar):
        """涨停板以上的买单应被拒绝"""
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=120.0, quantity=100)
        trade = broker.place_order(order, bar)
        assert trade is None
        assert order.status == "ORDER_REJECTED"

    def test_limit_down_rejected(self, broker, bar):
        """跌停板以下的卖单应被拒绝"""
        order = Order(symbol="sh600519", side=OrderSide.SELL,
                      order_type=OrderType.MARKET, price=80.0, quantity=100)
        trade = broker.place_order(order, bar)
        assert trade is None
        assert order.status == "ORDER_REJECTED"

    def test_buy_limit_order_submitted(self, broker, bar):
        """限价买单应被提交"""
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.LIMIT, price=99.0, quantity=100)
        trade = broker.place_order(order, bar)
        assert trade is not None
        assert order.status == "ORDER_SUBMITTED"


# ---------------------------------------------------------------------------
# cancel_order
# ---------------------------------------------------------------------------

class TestLiveBrokerCancelOrder:
    def test_cancel_pending_order(self, broker, bar):
        """待成交订单可撤销"""
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.LIMIT, price=100.0, quantity=100)
        result = broker.cancel_order(order)
        assert result is True
        assert order.status == "ORDER_CANCELLED"

    def test_cancel_submitted_order(self, broker, bar):
        """已提交的订单可撤销"""
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=100.0, quantity=100)
        broker.place_order(order, bar)
        assert order.status == "ORDER_SUBMITTED"
        result = broker.cancel_order(order)
        assert result is True
        assert order.status == "ORDER_CANCELLED"

    def test_cancel_filled_order_fails(self, broker, bar):
        """已成交订单不能撤销"""
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=100.0, quantity=100)
        order.update_status(OrderStatus.ORDER_FILLED.value)
        result = broker.cancel_order(order)
        assert result is False

    def test_cancel_rejected_order_fails(self, broker, bar):
        """被拒绝的订单不能撤销"""
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=100.0, quantity=50)
        broker.place_order(order, bar)  # should be REJECTED
        assert order.status == "ORDER_REJECTED"
        result = broker.cancel_order(order)
        assert result is False


# ---------------------------------------------------------------------------
# get_positions
# ---------------------------------------------------------------------------

class TestLiveBrokerGetPositions:
    def test_empty_without_portfolio(self, broker):
        """无 portfolio 时返回空字典"""
        assert broker.get_positions() == {}

    def test_empty_with_empty_portfolio(self, broker):
        """空 portfolio 对象返回空字典"""
        broker._data_feeds = []

        class FakePosition:
            quantity = 0

        class FakePortfolio:
            positions = {}

        assert broker.get_positions(FakePortfolio()) == {}


# ---------------------------------------------------------------------------
# get_balance
# ---------------------------------------------------------------------------

class TestLiveBrokerGetBalance:
    def test_returns_live_flag(self, broker):
        """余额应包含 live 标志和 api 信息"""
        balance = broker.get_balance()
        assert balance.get("live") is True
        assert balance.get("api") == "xtp"

    def test_custom_api(self):
        broker = LiveBroker(api="ctp")
        balance = broker.get_balance()
        assert balance["api"] == "ctp"

    def test_has_required_fields(self, broker):
        balance = broker.get_balance()
        for key in ("cash", "frozen", "equity"):
            assert key in balance


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------

class TestLiveBrokerGetHistory:
    def test_empty_when_no_feeds(self, broker):
        assert broker.get_history("sh600519", 10) == []

    def test_returns_bars_from_feed(self, broker):
        """有数据源时应返回 K 线"""
        bars = [
            BarData(
                symbol="sh600519",
                datetime=datetime(2025, 1, i + 1),
                open=100, high=102, low=98, close=100, volume=1000,
            )
            for i in range(20)
        ]

        class FakeFeed:
            symbol = "sh600519"

            def __len__(self):
                return len(bars)

            def __getitem__(self, idx):
                return bars[idx]

        result = broker.get_history("sh600519", 5, data_feeds=[FakeFeed()])
        assert len(result) == 5
        assert result[0].symbol == "sh600519"

    def test_symbol_not_found(self, broker):
        class FakeFeed:
            symbol = "sz000001"

            def __len__(self):
                return 5

            def __getitem__(self, idx):
                raise IndexError

        result = broker.get_history("sh600519", 10, data_feeds=[FakeFeed()])
        assert result == []


# ---------------------------------------------------------------------------
# order_audit_log
# ---------------------------------------------------------------------------

class TestOrderAuditLog:
    def test_log_entries(self):
        """审计日志条目应包含所有必要字段"""
        log = OrderAuditLog(
            order_id="oid", symbol="sh600519", side="Buy",
            price=100.0, quantity=100, status="FILLED",
            reason="test",
        )
        assert log.order_id == "oid"
        assert log.symbol == "sh600519"
        assert log.side == "Buy"
        assert log.price == 100.0
        assert log.quantity == 100
        assert log.status == "FILLED"
        assert log.reason == "test"
        assert isinstance(log.timestamp, datetime)

    def test_multiple_logs(self, broker, bar):
        """多次下单应累积审计日志"""
        for i in range(3):
            order = Order(symbol="sh600519", side=OrderSide.BUY,
                          order_type=OrderType.MARKET, price=100.0, quantity=100)
            broker.place_order(order, bar)
        assert len(broker.order_audit_log) >= 3
