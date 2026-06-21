# -*- coding: utf-8 -*-
"""T5 实盘 Broker 集成测试 — 使用 Mock SDK 测试 XTP / CTP / QMT 代码路径

验证三个实盘 Broker 在没有真实 SDK 时，使用 Mock SDK 能正确执行：
- 连接与登录
- 下单（市价单/限价单）
- 撤单
- 持仓/余额查询
- 100 股整数倍校验（A 股）
- CTP 期货不校验 100 股整数倍
"""
import pytest

from stockquant.execution.brokers.mock_sdk import (
    MockXtpApi,
    MockCtpApi,
    MockXtTrader,
    MockXTPAsset,
    MockXTPPosition,
    MockCTPLoginResponse,
    MockCTPPosition,
    MockCTPTradingAccount,
    MockQMTAsset,
    MockQMTPosition,
)
from stockquant.execution.brokers.xtp_broker import XTPBroker
from stockquant.execution.brokers.ctp_broker import CTPBroker
from stockquant.execution.brokers.qmt_broker import QMTBroker

from stockquant.models.order import Order, OrderSide, OrderType, OrderStatus
from stockquant.models.bar import BarData
from datetime import datetime


@pytest.fixture
def bar():
    return BarData(
        symbol="sh600519",
        datetime=datetime.now(),
        open=100.0, high=102.0, low=98.0, close=100.0, volume=1_000_000,
    )


# ====================================================================
# XTPBroker 测试
# ====================================================================

class TestXTPBrokerMock:
    """XTPBroker 使用 Mock SDK 的集成测试"""

    def _make_broker(self):
        """创建使用 Mock SDK 的 XTPBroker 实例"""
        mock_api = MockXtpApi()
        return XTPBroker(
            user="test_user",
            password="test_pass",
            app_id=1,
            client_id=0,
            server_addr="127.0.0.1:6002",
            _mock_api=mock_api,
        )

    def test_connect_and_login(self):
        """Mock SDK 模式应直接连接成功"""
        broker = self._make_broker()
        assert broker.connected is True
        assert broker._logged_in is True
        assert broker._session_id == 1

    def test_place_market_order(self, bar):
        """Mock SDK 下单应正常返回 TradeData"""
        broker = self._make_broker()
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=100.0, quantity=100)
        trade = broker.place_order(order, bar)
        assert trade is not None
        assert trade.symbol == "sh600519"
        assert trade.price == 100.0
        assert trade.quantity == 100
        assert order.status.name == "SUBMITTED"

    def test_place_limit_order(self, bar):
        """Mock SDK 限价单应正常返回 TradeData"""
        broker = self._make_broker()
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.LIMIT, price=99.0, quantity=200)
        trade = broker.place_order(order, bar)
        assert trade is not None
        assert trade.symbol == "sh600519"

    def test_cancel_order(self, bar):
        """Mock SDK 撤单应正常"""
        broker = self._make_broker()
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.LIMIT, price=100.0, quantity=100)
        broker.place_order(order, bar)
        result = broker.cancel_order(order)
        assert result is True
        assert order.status.name == "CANCELLED"

    def test_get_positions(self):
        """Mock SDK 持仓查询应返回预设数据"""
        broker = self._make_broker()
        positions = broker.get_positions()
        assert len(positions) >= 1
        assert "sh600519" in positions
        assert positions["sh600519"]["quantity"] == 1000
        assert positions["sh600519"]["price"] == 1800.0

    def test_get_balance(self):
        """Mock SDK 余额查询应返回预设数据"""
        broker = self._make_broker()
        balance = broker.get_balance()
        assert balance["live"] is True
        assert balance["api"] == "xtp"
        assert balance["cash"] == 950000.0
        assert balance["equity"] == 1000000.0

    def test_lot_size_rejected(self, bar):
        """100 股非整数倍应被拒绝"""
        broker = self._make_broker()
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=100.0, quantity=50)
        trade = broker.place_order(order, bar)
        assert trade is None
        assert order.status.name == "REJECTED"

    def test_order_audit_log(self, bar):
        """下单应记录审计日志"""
        broker = self._make_broker()
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=100.0, quantity=100)
        broker.place_order(order, bar)
        log = broker.order_audit_log
        assert len(log) >= 1
        assert log[0].symbol == "sh600519"


# ====================================================================
# CTPBroker 测试
# ====================================================================

class TestCTPBrokerMock:
    """CTPBroker 使用 Mock SDK 的集成测试"""

    def _make_broker(self):
        """创建使用 Mock SDK 的 CTPBroker 实例"""
        mock_api = MockCtpApi()
        return CTPBroker(
            user="test_user",
            password="test_pass",
            broker_id="9999",
            front_addr="tcp://127.0.0.1:10201",
            app_id="test_app",
            _mock_api=mock_api,
        )

    def test_connect_and_login(self):
        """Mock SDK 模式应直接连接成功"""
        broker = self._make_broker()
        assert broker.connected is True
        assert broker._logged_in is True

    def test_place_order(self, bar):
        """Mock SDK 下单应正常返回 TradeData"""
        broker = self._make_broker()
        order = Order(symbol="IF2406", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=4000.0, quantity=1)
        trade = broker.place_order(order, bar)
        assert trade is not None
        assert trade.symbol == "IF2406"
        assert order.status.name == "SUBMITTED"

    def test_no_lot_validation(self, bar):
        """CTP 期货不应校验 100 股整数倍"""
        broker = self._make_broker()
        order = Order(symbol="IF2406", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=4000.0, quantity=3)
        trade = broker.place_order(order, bar)
        assert trade is not None  # 期货以手为单位，3手有效

    def test_cancel_order(self, bar):
        """Mock SDK 撤单应正常"""
        broker = self._make_broker()
        order = Order(symbol="IF2406", side=OrderSide.BUY,
                      order_type=OrderType.LIMIT, price=4000.0, quantity=1)
        broker.place_order(order, bar)
        result = broker.cancel_order(order)
        assert result is True
        assert order.status.name == "CANCELLED"

    def test_get_positions(self):
        """Mock SDK 持仓查询应返回预设数据（含多空）"""
        broker = self._make_broker()
        positions = broker.get_positions()
        # Mock 回调填充了 _positions_cache
        assert len(positions) >= 1
        assert "IF2406" in positions
        assert positions["IF2406"]["long_qty"] == 10

    def test_get_balance(self):
        """Mock SDK 余额查询应返回预设数据（含保证金）"""
        broker = self._make_broker()
        balance = broker.get_balance()
        assert balance["live"] is True
        assert balance["api"] == "ctp"
        assert balance["cash"] == 500000.0
        assert balance["equity"] == 1000000.0

    def test_order_audit_log(self, bar):
        """下单应记录审计日志"""
        broker = self._make_broker()
        order = Order(symbol="IF2406", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=4000.0, quantity=1)
        broker.place_order(order, bar)
        log = broker.order_audit_log
        assert len(log) >= 1
        assert log[0].symbol == "IF2406"


# ====================================================================
# QMTBroker 测试
# ====================================================================

class TestQMTBrokerMock:
    """QMTBroker 使用 Mock SDK 的集成测试"""

    def _make_broker(self):
        """创建使用 Mock SDK 的 QMTBroker 实例"""
        mock_trader = MockXtTrader()
        return QMTBroker(
            qmt_path="D:\\QMT\\userdata_mini",
            account_id="test_account",
            _mock_xt_trader=mock_trader,
        )

    def test_connect(self):
        """Mock SDK 模式应直接连接成功"""
        broker = self._make_broker()
        assert broker.connected is True

    def test_place_market_order(self, bar):
        """Mock SDK 市价单应正常返回 TradeData"""
        broker = self._make_broker()
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=1800.0, quantity=100)
        trade = broker.place_order(order, bar)
        assert trade is not None
        assert trade.symbol == "sh600519"
        assert order.status.name == "SUBMITTED"

    def test_place_limit_order(self, bar):
        """Mock SDK 限价单应正常返回 TradeData"""
        broker = self._make_broker()
        order = Order(symbol="sh600519", side=OrderSide.SELL,
                      order_type=OrderType.LIMIT, price=1850.0, quantity=200)
        trade = broker.place_order(order, bar)
        assert trade is not None

    def test_cancel_order(self, bar):
        """Mock SDK 撤单应正常"""
        broker = self._make_broker()
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.LIMIT, price=1800.0, quantity=100)
        broker.place_order(order, bar)
        result = broker.cancel_order(order)
        assert result is True
        assert order.status.name == "CANCELLED"

    def test_get_positions(self):
        """Mock SDK 持仓查询应返回预设数据"""
        broker = self._make_broker()
        positions = broker.get_positions()
        assert len(positions) >= 1
        assert "600519.SH" in positions
        assert positions["600519.SH"]["quantity"] == 1000

    def test_get_balance(self):
        """Mock SDK 余额查询应返回预设数据"""
        broker = self._make_broker()
        balance = broker.get_balance()
        assert balance["live"] is True
        assert balance["api"] == "qmt"
        assert balance["cash"] == 950000.0
        assert balance["equity"] == 1000000.0

    def test_lot_size_rejected(self, bar):
        """100 股非整数倍应被拒绝"""
        broker = self._make_broker()
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=100.0, quantity=50)
        trade = broker.place_order(order, bar)
        assert trade is None
        assert order.status.name == "REJECTED"

    def test_order_audit_log(self, bar):
        """下单应记录审计日志"""
        broker = self._make_broker()
        order = Order(symbol="sh600519", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, price=1800.0, quantity=100)
        broker.place_order(order, bar)
        log = broker.order_audit_log
        assert len(log) >= 1
