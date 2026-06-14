# -*- coding: utf-8 -*-
"""F012 PaperBroker 模拟盘测试"""

import pytest

from stockquant.engine.broker import PaperBroker
from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.models.bar import BarData
from datetime import datetime


@pytest.fixture
def broker():
    return PaperBroker()


@pytest.fixture
def bar():
    return BarData(
        symbol="sh600519",
        datetime=datetime.now(),
        open=100.0, high=102.0, low=98.0, close=100.0, volume=1_000_000,
    )


class TestPaperBrokerPlaceOrder:
    def test_market_order_filled(self, broker, bar):
        """市价买单应正常成交"""
        order = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.MARKET,
                      price=100.0, quantity=100)
        trade = broker.place_order(order, bar)
        assert trade is not None
        assert trade.symbol == "sh600519"
        assert trade.side == "Buy"
        assert order.status.name == "FILLED"

    def test_lot_size_rejected(self, broker, bar):
        """100 股非整数倍的买单应被拒绝"""
        order = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.MARKET,
                      price=100.0, quantity=50)
        trade = broker.place_order(order, bar)
        assert trade is None
        assert order.status.name == "REJECTED"

    def test_limit_up_rejected(self, broker, bar):
        """涨停板以上的买单应被拒绝"""
        order = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.MARKET,
                      price=120.0, quantity=100)
        trade = broker.place_order(order, bar)
        assert trade is None
        assert order.status.name == "REJECTED"

    def test_limit_down_rejected(self, broker, bar):
        """跌停板以下的卖单应被拒绝"""
        order = Order(symbol="sh600519", side=OrderSide.SELL, order_type=OrderType.MARKET,
                      price=80.0, quantity=100)
        trade = broker.place_order(order, bar)
        assert trade is None
        assert order.status.name == "REJECTED"

    def test_trade_log_captured(self, broker, bar):
        """成交记录应被添加到日志"""
        order = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.MARKET,
                      price=100.0, quantity=100)
        broker.place_order(order, bar)
        assert len(broker.trade_log) == 1
        assert broker.trade_log[0].quantity == 100


class TestPaperBrokerCancelOrder:
    def test_cancel_pending_order(self, broker, bar):
        """待成交的订单可以撤销"""
        order = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.LIMIT,
                      price=100.0, quantity=100)
        result = broker.cancel_order(order)
        assert result is True
        assert order.status.name == "CANCELLED"

    def test_cancel_filled_order_fails(self, broker, bar):
        """已成交订单不能撤销"""
        order = Order(symbol="sh600519", side=OrderSide.BUY, order_type=OrderType.MARKET,
                      price=100.0, quantity=100)
        broker.place_order(order, bar)
        result = broker.cancel_order(order)
        assert result is False


class TestPaperBrokerGetBalance:
    def test_returns_paper_flag(self, broker):
        """余额应包含 paper 标志"""
        balance = broker.get_balance()
        assert balance.get("paper") is True
