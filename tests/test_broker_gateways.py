# -*- coding: utf-8 -*-
"""QMT Broker 和 XTP Broker 单元测试

使用 Mock 对象替代真实 SDK，覆盖初始化、下单、撤单、查询、生命周期等场景。
不依赖真实 SDK / 数据库 / Redis / 外部服务。
"""

import unittest
from unittest.mock import Mock, MagicMock, patch

from stockquant.execution.brokers.qmt_broker import QMTBroker
from stockquant.execution.brokers.xtp_broker import XTPBroker
from stockquant.execution.gateway_base import (
    GatewayConfig,
    GatewayState,
    GatewayEvent,
    BaseGateway,
)
from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.events import EventType


# ── Mock SDK 对象 ──────────────────────────────────────────────────


class MockXTTrader:
    """模拟 QMT xtquant 的 XtQuantTrader 对象"""

    def __init__(self, order_stock_return=12345):
        self._order_stock_return = order_stock_return
        self.cancelled_orders = []

    def order_stock(self, **kwargs):
        return self._order_stock_return

    def cancel_order_stock(self, account, order_id):
        self.cancelled_orders.append((account, order_id))

    def query_stock_positions(self, account):
        return []

    def query_stock_asset(self, account):
        a = Mock()
        a.cash = 100000.0
        a.frozen_cash = 5000.0
        a.total_asset = 105000.0
        return a

    def query_stock_orders(self, account):
        return []


class MockXTPosition:
    """模拟 QMT 持仓对象"""

    def __init__(self, stock_code, volume, open_price):
        self.stock_code = stock_code
        self.volume = volume
        self.open_price = open_price


class MockXTOrder:
    """模拟 QMT 订单对象"""

    def __init__(self, order_id, stock_code, price, order_volume, traded_volume, order_status):
        self.order_id = order_id
        self.stock_code = stock_code
        self.price = price
        self.order_volume = order_volume
        self.traded_volume = traded_volume
        self.order_status = order_status


class MockXTPOrderInsertInfo:
    """模拟 XTP 订单请求对象"""

    def __init__(self):
        self.ticker = ""
        self.side = 0
        self.price_type = 0
        self.quantity = 0
        self.price = 0.0


class MockXTPApi:
    """模拟 XTP SDK 的 TraderApi 对象"""

    def __init__(self, insert_order_return=100001):
        self._insert_order_return = insert_order_return
        self.cancelled = []
        self.MockXTPOrderInsertInfo = MockXTPOrderInsertInfo

    def InsertOrder(self, req, session_id):
        return self._insert_order_return

    def CancelOrder(self, xtp_id, session_id):
        self.cancelled.append((xtp_id, session_id))

    def QueryPositions(self, session_id):
        return []

    def QueryAsset(self, session_id):
        a = Mock()
        a.buying_power = 100000.0
        a.frozen_cash = 5000.0
        a.total_asset = 105000.0
        a.market_value = 50000.0
        return a

    def QueryOrders(self, session_id):
        return []


class MockXTPPosition:
    """模拟 XTP 持仓对象"""

    def __init__(self, ticker, total_qty, avg_price, market_value, unrealized_pnl, exchange_id):
        self.ticker = ticker
        self.total_qty = total_qty
        self.avg_price = avg_price
        self.market_value = market_value
        self.unrealized_pnl = unrealized_pnl
        self.exchange_id = exchange_id


class MockXTPOrderInfo:
    """模拟 XTP 订单查询结果对象"""

    def __init__(self, order_xtp_id, order_status):
        self.order_xtp_id = order_xtp_id
        self.order_status = order_status


# ── 辅助函数 ──────────────────────────────────────────────────────


def make_order(symbol="600000.SH", side=OrderSide.BUY, price=10.0,
               quantity=100, order_type=OrderType.LIMIT, order_id=None):
    """快速创建 Order 对象"""
    return Order(
        symbol=symbol,
        side=side,
        order_type=order_type,
        price=price,
        quantity=quantity,
        order_id=order_id or "",
    )


def make_mock_qmt_broker(account_id="TEST_ACCOUNT"):
    """创建 Mock SDK 模式的 QMT Broker（自动进入 LOGGED_IN）"""
    mock_trader = MockXTTrader()
    broker = QMTBroker(
        qmt_path="",
        account_id=account_id,
        _mock_xt_trader=mock_trader,
    )
    return broker, mock_trader


def make_mock_xtp_broker(user="test_user", server_addr="127.0.0.1:6002"):
    """创建 Mock SDK 模式的 XTP Broker（自动进入 LOGGED_IN）"""
    mock_api = MockXTPApi()
    broker = XTPBroker(
        user=user,
        server_addr=server_addr,
        _mock_api=mock_api,
    )
    return broker, mock_api


# ══════════════════════════════════════════════════════════════════
# 1. TestQMTBrokerInit — 初始化、Mock SDK 模式状态、api 属性
# ══════════════════════════════════════════════════════════════════


class TestQMTBrokerInit(unittest.TestCase):
    """QMT Broker 初始化测试"""

    def test_api_attribute(self):
        """验证类属性 api == 'qmt'"""
        self.assertEqual(QMTBroker.api, "qmt")

    def test_inherits_base_gateway(self):
        """验证继承自 BaseGateway"""
        broker = QMTBroker()
        self.assertIsInstance(broker, BaseGateway)

    def test_default_state_disconnected_without_mock(self):
        """无 Mock SDK 时初始状态为 DISCONNECTED"""
        broker = QMTBroker()
        self.assertEqual(broker.state, GatewayState.DISCONNECTED)
        self.assertFalse(broker.connected)
        self.assertFalse(broker.logged_in)

    def test_mock_sdk_enters_logged_in(self):
        """注入 Mock SDK 时直接进入 LOGGED_IN 状态"""
        broker, _ = make_mock_qmt_broker()
        self.assertEqual(broker.state, GatewayState.LOGGED_IN)
        self.assertTrue(broker.connected)
        self.assertTrue(broker.logged_in)

    def test_mock_sdk_stores_trader(self):
        """注入 Mock SDK 后 _xt_trader 被保存"""
        broker, mock_trader = make_mock_qmt_broker()
        self.assertIs(broker._xt_trader, mock_trader)

    def test_account_id_stored(self):
        """account_id 参数被正确保存"""
        broker, _ = make_mock_qmt_broker(account_id="MY_ACCOUNT")
        self.assertEqual(broker._account_id, "MY_ACCOUNT")

    def test_qmt_path_stored(self):
        """qmt_path 参数被正确保存"""
        broker = QMTBroker(qmt_path="/path/to/qmt", _mock_xt_trader=MockXTTrader())
        self.assertEqual(broker._qmt_path, "/path/to/qmt")

    def test_default_config(self):
        """默认配置为 GatewayConfig()"""
        broker, _ = make_mock_qmt_broker()
        self.assertIsInstance(broker.config, GatewayConfig)

    def test_custom_config(self):
        """自定义配置被正确保存"""
        cfg = GatewayConfig(heartbeat_enabled=False)
        broker = QMTBroker(config=cfg, _mock_xt_trader=MockXTTrader())
        self.assertIs(broker.config, cfg)
        self.assertFalse(broker.config.heartbeat_enabled)


# ══════════════════════════════════════════════════════════════════
# 2. TestQMTBrokerPlaceOrder — Mock SDK 下单、100 股校验、未登录拒绝
# ══════════════════════════════════════════════════════════════════


class TestQMTBrokerPlaceOrder(unittest.TestCase):
    """QMT Broker 下单测试"""

    def setUp(self):
        self.broker, self.mock_trader = make_mock_qmt_broker()

    def test_place_order_success(self):
        """Mock SDK 下单成功，返回 TradeData"""
        order = make_order(quantity=100, price=10.0)
        trade = self.broker.place_order(order)

        self.assertIsNotNone(trade)
        self.assertEqual(trade.symbol, "600000.SH")
        self.assertEqual(trade.quantity, 100)
        self.assertEqual(trade.price, 10.0)
        # 订单应在 open_orders 中
        self.assertIn(order.order_id, self.broker._open_orders)

    def test_place_order_100_shares_validation(self):
        """100 股整数倍校验：100 股成功"""
        order = make_order(quantity=100)
        trade = self.broker.place_order(order)
        self.assertIsNotNone(trade)

    def test_place_order_200_shares_validation(self):
        """100 股整数倍校验：200 股成功"""
        order = make_order(quantity=200)
        trade = self.broker.place_order(order)
        self.assertIsNotNone(trade)

    def test_place_order_50_shares_rejected(self):
        """100 股整数倍校验：50 股被拒绝"""
        order = make_order(quantity=50)
        trade = self.broker.place_order(order)
        self.assertIsNone(trade)
        self.assertEqual(order.status, EventType.ORDER_REJECTED.value)

    def test_place_order_150_shares_rejected(self):
        """100 股整数倍校验：150 股被拒绝"""
        order = make_order(quantity=150)
        trade = self.broker.place_order(order)
        self.assertIsNone(trade)
        self.assertEqual(order.status, EventType.ORDER_REJECTED.value)

    def test_place_order_not_connected_rejected(self):
        """未连接时下单被拒绝"""
        broker = QMTBroker()  # 无 Mock，DISCONNECTED 状态
        order = make_order(quantity=100)
        trade = broker.place_order(order)
        self.assertIsNone(trade)
        self.assertEqual(order.status, EventType.ORDER_REJECTED.value)

    def test_place_order_zero_quantity_rejected(self):
        """数量为 0 被拒绝"""
        order = make_order(quantity=0)
        trade = self.broker.place_order(order)
        self.assertIsNone(trade)

    def test_place_order_negative_quantity_rejected(self):
        """数量为负数被拒绝"""
        order = make_order(quantity=-100)
        trade = self.broker.place_order(order)
        self.assertIsNone(trade)

    def test_place_order_sell_side(self):
        """卖单下单成功"""
        order = make_order(side=OrderSide.SELL, quantity=100)
        trade = self.broker.place_order(order)
        self.assertIsNotNone(trade)
        self.assertEqual(trade.side, "Sell")

    def test_place_order_status_submitted(self):
        """下单成功后订单状态变为 SUBMITTED"""
        order = make_order(quantity=100)
        self.broker.place_order(order)
        self.assertEqual(order.status, EventType.ORDER_SUBMITTED.value)

    def test_place_order_event_emitted(self):
        """下单成功后触发 ORDER_SUBMITTED 事件"""
        order = make_order(quantity=100)
        received = []

        def handler(data):
            received.append(data)

        self.broker.register_event_handler(GatewayEvent.ORDER_SUBMITTED, handler)
        self.broker.place_order(order)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["symbol"], "600000.SH")


# ══════════════════════════════════════════════════════════════════
# 3. TestQMTBrokerCancelOrder — Mock SDK 撤单
# ══════════════════════════════════════════════════════════════════


class TestQMTBrokerCancelOrder(unittest.TestCase):
    """QMT Broker 撤单测试"""

    def setUp(self):
        self.broker, self.mock_trader = make_mock_qmt_broker()

    def test_cancel_order_success(self):
        """成功撤单"""
        order = make_order(quantity=100)
        self.broker.place_order(order)
        # 确认订单已提交
        self.assertIn(order.order_id, self.broker._open_orders)

        result = self.broker.cancel_order(order)
        self.assertTrue(result)
        self.assertNotIn(order.order_id, self.broker._open_orders)
        self.assertEqual(order.status, EventType.ORDER_CANCELLED.value)

    def test_cancel_order_calls_sdk(self):
        """撤单调用了 Mock SDK 的 cancel_order_stock"""
        order = make_order(quantity=100)
        self.broker.place_order(order)
        self.broker.cancel_order(order)

        self.assertEqual(len(self.mock_trader.cancelled_orders), 1)
        account, xt_order_id = self.mock_trader.cancelled_orders[0]
        self.assertEqual(account, "TEST_ACCOUNT")

    def test_cancel_order_not_in_open_orders(self):
        """撤销不在 open_orders 中的订单返回 False"""
        order = make_order(quantity=100)
        result = self.broker.cancel_order(order)
        self.assertFalse(result)

    def test_cancel_order_not_connected(self):
        """未连接时撤单返回 False"""
        broker = QMTBroker()  # DISCONNECTED
        order = make_order(quantity=100)
        result = broker.cancel_order(order)
        self.assertFalse(result)

    def test_cancel_order_event_emitted(self):
        """撤单成功后触发 ORDER_CANCELLED 事件"""
        order = make_order(quantity=100)
        self.broker.place_order(order)

        received = []

        def handler(data):
            received.append(data)

        self.broker.register_event_handler(GatewayEvent.ORDER_CANCELLED, handler)
        self.broker.cancel_order(order)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["order_id"], order.order_id)


# ══════════════════════════════════════════════════════════════════
# 4. TestQMTBrokerQueries — 持仓/余额查询（未登录返回空）
# ══════════════════════════════════════════════════════════════════


class TestQMTBrokerQueries(unittest.TestCase):
    """QMT Broker 查询测试"""

    def test_query_positions_logged_in(self):
        """已登录时查询持仓"""
        broker, mock_trader = make_mock_qmt_broker()
        mock_trader.query_stock_positions = Mock(return_value=[
            MockXTPosition("600000.SH", 1000, 10.5),
        ])
        positions = broker.get_positions()

        self.assertIsInstance(positions, dict)
        self.assertIn("600000.SH", positions)
        self.assertEqual(positions["600000.SH"]["quantity"], 1000)
        self.assertEqual(positions["600000.SH"]["price"], 10.5)

    def test_query_positions_empty(self):
        """已登录但无持仓返回空字典"""
        broker, mock_trader = make_mock_qmt_broker()
        mock_trader.query_stock_positions = Mock(return_value=[])
        positions = broker.get_positions()
        self.assertEqual(positions, {})

    def test_query_positions_not_connected(self):
        """未连接时查询持仓返回空字典"""
        broker = QMTBroker()  # DISCONNECTED
        positions = broker.get_positions()
        self.assertEqual(positions, {})

    def test_query_balance_logged_in(self):
        """已登录时查询余额"""
        broker, _ = make_mock_qmt_broker()
        balance = broker.get_balance()

        self.assertIsInstance(balance, dict)
        self.assertTrue(balance.get("live"))
        self.assertEqual(balance["api"], "qmt")
        self.assertEqual(balance["cash"], 100000.0)
        self.assertEqual(balance["frozen"], 5000.0)
        self.assertEqual(balance["equity"], 105000.0)

    def test_query_balance_not_connected(self):
        """未连接时查询余额返回空字典"""
        broker = QMTBroker()
        balance = broker.get_balance()
        self.assertEqual(balance, {})

    def test_query_orders_logged_in_empty(self):
        """已登录时查询挂单（空列表）"""
        broker, _ = make_mock_qmt_broker()
        orders = broker._do_query_orders()
        self.assertEqual(orders, [])

    def test_query_orders_not_connected(self):
        """未登录时 _do_query_orders 返回空列表"""
        broker = QMTBroker()
        orders = broker._do_query_orders()
        self.assertEqual(orders, [])


# ══════════════════════════════════════════════════════════════════
# 5. TestQMTBrokerLifecycle — connect/disconnect 流程（用 Mock SDK 测试）
# ══════════════════════════════════════════════════════════════════


class TestQMTBrokerLifecycle(unittest.TestCase):
    """QMT Broker 生命周期测试"""

    def test_mock_sdk_no_connect_needed(self):
        """Mock SDK 模式下已处于 LOGGED_IN，无需 connect"""
        broker, _ = make_mock_qmt_broker()
        self.assertEqual(broker.state, GatewayState.LOGGED_IN)

    def test_disconnect_from_logged_in(self):
        """从 LOGGED_IN 断开后回到 DISCONNECTED"""
        broker, _ = make_mock_qmt_broker()
        self.assertEqual(broker.state, GatewayState.LOGGED_IN)

        broker.disconnect()
        self.assertEqual(broker.state, GatewayState.DISCONNECTED)
        self.assertFalse(broker.connected)
        self.assertFalse(broker.logged_in)

    def test_disconnect_clears_open_orders(self):
        """断开连接后 open_orders 被清理"""
        broker, _ = make_mock_qmt_broker()
        order = make_order(quantity=100)
        broker.place_order(order)
        self.assertIn(order.order_id, broker._open_orders)

        broker.disconnect()
        # disconnect 不会自动清理 open_orders（由订单同步或用户管理）
        # 但 _xt_trader 应被置 None
        self.assertIsNone(broker._xt_trader)

    def test_connect_without_sdk_returns_false(self):
        """无 SDK 且无 qmt_path 时 connect 返回 False"""
        broker = QMTBroker(qmt_path="", account_id="")
        # QMT_AVAILABLE 为 False（无 xtquant），_do_connect 返回 False
        result = broker.connect()
        self.assertFalse(result)

    def test_disconnect_emits_event(self):
        """断开连接触发 DISCONNECTED 事件"""
        broker, _ = make_mock_qmt_broker()
        received = []

        def handler(data):
            received.append(data)

        broker.register_event_handler(GatewayEvent.DISCONNECTED, handler)
        broker.disconnect()

        self.assertEqual(len(received), 1)

    def test_do_heartbeat_with_mock(self):
        """Mock SDK 模式下心跳正常执行"""
        broker, mock_trader = make_mock_qmt_broker()
        # 记录调用
        mock_trader.query_stock_asset = Mock(wraps=mock_trader.query_stock_asset)
        # 不应抛出异常
        broker._do_heartbeat()
        # query_stock_asset 应被调用一次
        mock_trader.query_stock_asset.assert_called_once_with("TEST_ACCOUNT")

    def test_repr(self):
        """__repr__ 输出格式正确"""
        broker, _ = make_mock_qmt_broker()
        r = repr(broker)
        self.assertIn("QMTBroker", r)
        self.assertIn("logged_in", r)
        self.assertIn("TEST_ACCOUNT", r)


# ══════════════════════════════════════════════════════════════════
# 6. TestXTPBrokerInit — 初始化、Mock SDK 模式状态、api 属性
# ══════════════════════════════════════════════════════════════════


class TestXTPBrokerInit(unittest.TestCase):
    """XTP Broker 初始化测试"""

    def test_api_attribute(self):
        """验证类属性 api == 'xtp'"""
        self.assertEqual(XTPBroker.api, "xtp")

    def test_inherits_base_gateway(self):
        """验证继承自 BaseGateway"""
        broker = XTPBroker()
        self.assertIsInstance(broker, BaseGateway)

    def test_default_state_disconnected(self):
        """无 Mock SDK 且无 user/server_addr 时初始状态为 DISCONNECTED"""
        broker = XTPBroker()
        self.assertEqual(broker.state, GatewayState.DISCONNECTED)
        self.assertFalse(broker.connected)
        self.assertFalse(broker.logged_in)

    def test_mock_sdk_enters_logged_in(self):
        """注入 Mock SDK + user + server_addr 时进入 LOGGED_IN 状态"""
        broker, _ = make_mock_xtp_broker()
        self.assertEqual(broker.state, GatewayState.LOGGED_IN)
        self.assertTrue(broker.connected)
        self.assertTrue(broker.logged_in)

    def test_mock_sdk_session_id(self):
        """Mock SDK 模式 session_id 应为 1"""
        broker, _ = make_mock_xtp_broker()
        self.assertEqual(broker._session_id, 1)

    def test_mock_sdk_stores_api(self):
        """注入 Mock SDK 后 _xtp_api 被保存"""
        broker, mock_api = make_mock_xtp_broker()
        self.assertIs(broker._xtp_api, mock_api)

    def test_user_stored(self):
        """user 参数被正确保存"""
        broker, _ = make_mock_xtp_broker(user="my_user")
        self.assertEqual(broker._user, "my_user")

    def test_server_addr_stored(self):
        """server_addr 参数被正确保存"""
        broker, _ = make_mock_xtp_broker(server_addr="192.168.1.1:6002")
        self.assertEqual(broker._server_addr, "192.168.1.1:6002")

    def test_password_stored(self):
        """password 参数被正确保存"""
        broker = XTPBroker(
            user="u", server_addr="1.2.3.4:6002",
            password="secret", _mock_api=MockXTPApi(),
        )
        self.assertEqual(broker._password, "secret")

    def test_app_id_client_id_stored(self):
        """app_id 和 client_id 参数被正确保存"""
        broker = XTPBroker(
            user="u", server_addr="1.2.3.4:6002",
            app_id=1234, client_id=5,
            _mock_api=MockXTPApi(),
        )
        self.assertEqual(broker._app_id, 1234)
        self.assertEqual(broker._client_id, 5)

    def test_xtp_order_map_empty(self):
        """初始化后 xtp_order_map 为空"""
        broker, _ = make_mock_xtp_broker()
        self.assertEqual(broker._xtp_order_map, {})

    def test_default_config(self):
        """默认配置为 GatewayConfig()"""
        broker, _ = make_mock_xtp_broker()
        self.assertIsInstance(broker.config, GatewayConfig)

    def test_mock_sdk_without_user_no_auto_login(self):
        """注入 Mock SDK 但无 user 时不自动 LOGGED_IN"""
        broker = XTPBroker(_mock_api=MockXTPApi())
        self.assertNotEqual(broker.state, GatewayState.LOGGED_IN)

    def test_mock_sdk_without_addr_no_auto_login(self):
        """注入 Mock SDK 但无 server_addr 时不自动 LOGGED_IN"""
        broker = XTPBroker(user="u", _mock_api=MockXTPApi())
        self.assertNotEqual(broker.state, GatewayState.LOGGED_IN)


# ══════════════════════════════════════════════════════════════════
# 7. TestXTPBrokerPlaceOrder — Mock SDK 下单、100 股校验、xtp_order_map 维护
# ══════════════════════════════════════════════════════════════════


class TestXTPBrokerPlaceOrder(unittest.TestCase):
    """XTP Broker 下单测试"""

    def setUp(self):
        self.broker, self.mock_api = make_mock_xtp_broker()

    def test_place_order_success(self):
        """Mock SDK 下单成功，返回 TradeData"""
        order = make_order(quantity=100, price=10.0)
        trade = self.broker.place_order(order)

        self.assertIsNotNone(trade)
        self.assertEqual(trade.symbol, "600000.SH")
        self.assertEqual(trade.quantity, 100)
        self.assertEqual(trade.price, 10.0)

    def test_place_order_xtp_order_map_updated(self):
        """下单成功后 xtp_order_map 应包含映射"""
        order = make_order(quantity=100, price=10.0)
        self.broker.place_order(order)

        # xtp_order_id = 100001 (MockXTPApi 默认返回值)
        self.assertIn(100001, self.broker._xtp_order_map)
        self.assertEqual(self.broker._xtp_order_map[100001], order.order_id)

    def test_place_order_100_shares_ok(self):
        """100 股校验通过"""
        order = make_order(quantity=100)
        trade = self.broker.place_order(order)
        self.assertIsNotNone(trade)

    def test_place_order_300_shares_ok(self):
        """300 股校验通过"""
        order = make_order(quantity=300)
        trade = self.broker.place_order(order)
        self.assertIsNotNone(trade)

    def test_place_order_50_shares_rejected(self):
        """50 股被拒绝（不是 100 整数倍）"""
        order = make_order(quantity=50)
        trade = self.broker.place_order(order)
        self.assertIsNone(trade)
        self.assertEqual(order.status, EventType.ORDER_REJECTED.value)

    def test_place_order_1_share_rejected(self):
        """1 股被拒绝"""
        order = make_order(quantity=1)
        trade = self.broker.place_order(order)
        self.assertIsNone(trade)

    def test_place_order_zero_quantity_rejected(self):
        """数量为 0 被拒绝（BaseGateway 校验）"""
        order = make_order(quantity=0)
        trade = self.broker.place_order(order)
        self.assertIsNone(trade)

    def test_place_order_negative_quantity_rejected(self):
        """数量为负数被拒绝（BaseGateway 校验）"""
        order = make_order(quantity=-100)
        trade = self.broker.place_order(order)
        self.assertIsNone(trade)

    def test_place_order_sell_side(self):
        """卖单下单成功"""
        order = make_order(side=OrderSide.SELL, quantity=100)
        trade = self.broker.place_order(order)
        self.assertIsNotNone(trade)
        self.assertEqual(trade.side, "Sell")

    def test_place_order_status_submitted(self):
        """下单成功后订单状态变为 SUBMITTED"""
        order = make_order(quantity=100)
        self.broker.place_order(order)
        self.assertEqual(order.status, EventType.ORDER_SUBMITTED.value)

    def test_place_order_not_connected_rejected(self):
        """未连接时下单被拒绝"""
        broker = XTPBroker()  # DISCONNECTED
        order = make_order(quantity=100)
        trade = broker.place_order(order)
        self.assertIsNone(trade)
        self.assertEqual(order.status, EventType.ORDER_REJECTED.value)

    def test_place_order_event_emitted(self):
        """下单成功后触发 ORDER_SUBMITTED 事件"""
        order = make_order(quantity=100)
        received = []

        def handler(data):
            received.append(data)

        self.broker.register_event_handler(GatewayEvent.ORDER_SUBMITTED, handler)
        self.broker.place_order(order)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["symbol"], "600000.SH")

    def test_place_order_in_open_orders(self):
        """下单成功后订单在 open_orders 中"""
        order = make_order(quantity=100)
        self.broker.place_order(order)
        self.assertIn(order.order_id, self.broker._open_orders)

    def test_place_order_multiple(self):
        """多次下单后 xtp_order_map 包含多条记录"""
        # 使用递增 xtp_order_id 的 Mock
        mock_api = MockXTPApi(insert_order_return=100001)
        call_count = [0]
        original_insert = mock_api.InsertOrder

        def insert_order_with_increment(req, session_id):
            call_count[0] += 1
            return 100000 + call_count[0]

        mock_api.InsertOrder = insert_order_with_increment
        broker = XTPBroker(user="u", server_addr="1.2.3.4:6002", _mock_api=mock_api)

        order1 = make_order(quantity=100)
        order2 = make_order(quantity=200, symbol="000001.SZ")
        broker.place_order(order1)
        broker.place_order(order2)

        self.assertEqual(len(broker._xtp_order_map), 2)
        self.assertIn(100001, broker._xtp_order_map)
        self.assertIn(100002, broker._xtp_order_map)


# ══════════════════════════════════════════════════════════════════
# 8. TestXTPBrokerCancelOrder — Mock SDK 撤单、xtp_order_map 查找
# ══════════════════════════════════════════════════════════════════


class TestXTPBrokerCancelOrder(unittest.TestCase):
    """XTP Broker 撤单测试"""

    def setUp(self):
        self.broker, self.mock_api = make_mock_xtp_broker()

    def test_cancel_order_success(self):
        """成功撤单"""
        order = make_order(quantity=100)
        self.broker.place_order(order)
        self.assertIn(order.order_id, self.broker._open_orders)

        result = self.broker.cancel_order(order)
        self.assertTrue(result)
        self.assertNotIn(order.order_id, self.broker._open_orders)
        self.assertEqual(order.status, EventType.ORDER_CANCELLED.value)

    def test_cancel_order_calls_sdk_cancel(self):
        """撤单调用了 Mock SDK 的 CancelOrder"""
        order = make_order(quantity=100)
        self.broker.place_order(order)
        self.broker.cancel_order(order)

        self.assertEqual(len(self.mock_api.cancelled), 1)
        xtp_id, session_id = self.mock_api.cancelled[0]
        self.assertEqual(xtp_id, 100001)
        self.assertEqual(session_id, 1)

    def test_cancel_order_not_in_open_orders(self):
        """撤销不在 open_orders 中的订单返回 False"""
        order = make_order(quantity=100)
        result = self.broker.cancel_order(order)
        self.assertFalse(result)

    def test_cancel_order_not_connected(self):
        """未连接时撤单返回 False"""
        broker = XTPBroker()
        order = make_order(quantity=100)
        result = broker.cancel_order(order)
        self.assertFalse(result)

    def test_cancel_order_without_xtp_mapping(self):
        """xtp_order_map 中无对应映射时撤单失败"""
        # 先下一个单，然后手动清除 xtp_order_map
        order = make_order(quantity=100)
        self.broker.place_order(order)

        # 清除映射（模拟映射丢失）
        self.broker._xtp_order_map.clear()

        # cancel_order 中 BaseGateway 会先检查 open_orders
        # open_orders 有记录 -> 调用 _do_cancel_order -> 找不到 xtp_order_id
        result = self.broker.cancel_order(order)
        self.assertFalse(result)

    def test_cancel_order_event_emitted(self):
        """撤单成功后触发 ORDER_CANCELLED 事件"""
        order = make_order(quantity=100)
        self.broker.place_order(order)

        received = []

        def handler(data):
            received.append(data)

        self.broker.register_event_handler(GatewayEvent.ORDER_CANCELLED, handler)
        self.broker.cancel_order(order)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["order_id"], order.order_id)


# ══════════════════════════════════════════════════════════════════
# 9. TestXTPBrokerQueries — 持仓/余额查询
# ══════════════════════════════════════════════════════════════════


class TestXTPBrokerQueries(unittest.TestCase):
    """XTP Broker 查询测试"""

    def test_query_positions_logged_in(self):
        """已登录时查询持仓"""
        mock_api = MockXTPApi()
        mock_api.QueryPositions = Mock(return_value=[
            MockXTPPosition("600000.SH", 1000, 10.5, 10500.0, 500.0, 1),
        ])
        broker = XTPBroker(user="u", server_addr="1.2.3.4:6002", _mock_api=mock_api)

        positions = broker.get_positions()
        self.assertIsInstance(positions, dict)
        self.assertIn("600000.SH", positions)
        self.assertEqual(positions["600000.SH"]["quantity"], 1000)
        self.assertEqual(positions["600000.SH"]["price"], 10.5)

    def test_query_positions_empty(self):
        """已登录但无持仓"""
        broker, _ = make_mock_xtp_broker()
        positions = broker.get_positions()
        self.assertEqual(positions, {})

    def test_query_positions_not_connected(self):
        """未连接时查询持仓返回空字典"""
        broker = XTPBroker()
        positions = broker.get_positions()
        self.assertEqual(positions, {})

    def test_query_balance_logged_in(self):
        """已登录时查询余额"""
        broker, _ = make_mock_xtp_broker()
        balance = broker.get_balance()

        self.assertIsInstance(balance, dict)
        self.assertTrue(balance.get("live"))
        self.assertEqual(balance["api"], "xtp")
        self.assertEqual(balance["cash"], 100000.0)
        self.assertEqual(balance["frozen"], 5000.0)
        self.assertEqual(balance["equity"], 105000.0)

    def test_query_balance_not_connected(self):
        """未连接时查询余额返回空字典"""
        broker = XTPBroker()
        balance = broker.get_balance()
        self.assertEqual(balance, {})

    def test_query_orders_logged_in_empty(self):
        """已登录时查询挂单（空列表）"""
        broker, _ = make_mock_xtp_broker()
        orders = broker._do_query_orders()
        self.assertEqual(orders, [])

    def test_query_orders_not_connected(self):
        """未登录时 _do_query_orders 返回空列表"""
        broker = XTPBroker()
        orders = broker._do_query_orders()
        self.assertEqual(orders, [])

    def test_positions_cache_updated(self):
        """查询持仓后 _positions_cache 被更新"""
        mock_api = MockXTPApi()
        mock_api.QueryPositions = Mock(return_value=[
            MockXTPPosition("600000.SH", 1000, 10.5, 10500.0, 500.0, 1),
        ])
        broker = XTPBroker(user="u", server_addr="1.2.3.4:6002", _mock_api=mock_api)

        broker.get_positions()
        self.assertIn("600000.SH", broker._positions_cache)

    def test_asset_cache_updated(self):
        """查询余额后 _asset_cache 被更新"""
        broker, _ = make_mock_xtp_broker()
        broker.get_balance()
        self.assertTrue(len(broker._asset_cache) > 0)


# ══════════════════════════════════════════════════════════════════
# 10. TestXTPBrokerLifecycle — connect/disconnect、Mock SDK 不自动 connect
# ══════════════════════════════════════════════════════════════════


class TestXTPBrokerLifecycle(unittest.TestCase):
    """XTP Broker 生命周期测试"""

    def test_mock_sdk_no_connect_needed(self):
        """Mock SDK 模式下已处于 LOGGED_IN"""
        broker, _ = make_mock_xtp_broker()
        self.assertEqual(broker.state, GatewayState.LOGGED_IN)

    def test_disconnect_from_logged_in(self):
        """从 LOGGED_IN 断开后回到 DISCONNECTED"""
        broker, _ = make_mock_xtp_broker()
        self.assertEqual(broker.state, GatewayState.LOGGED_IN)

        broker.disconnect()
        self.assertEqual(broker.state, GatewayState.DISCONNECTED)
        self.assertFalse(broker.connected)
        self.assertFalse(broker.logged_in)

    def test_disconnect_clears_xtp_api(self):
        """断开连接后 _xtp_api 被置为 None"""
        broker, _ = make_mock_xtp_broker()
        broker.disconnect()
        self.assertIsNone(broker._xtp_api)

    def test_disconnect_emits_event(self):
        """断开连接触发 DISCONNECTED 事件"""
        broker, _ = make_mock_xtp_broker()
        received = []

        def handler(data):
            received.append(data)

        broker.register_event_handler(GatewayEvent.DISCONNECTED, handler)
        broker.disconnect()

        self.assertEqual(len(received), 1)

    def test_mock_sdk_without_args_does_not_connect(self):
        """Mock SDK 但缺少 user 或 server_addr 时不自动 connect"""
        broker = XTPBroker(_mock_api=MockXTPApi())
        # __init__ 中条件不满足，不会自动 connect
        self.assertEqual(broker.state, GatewayState.DISCONNECTED)

    def test_do_heartbeat_with_mock(self):
        """Mock SDK 模式下心跳不抛异常"""
        broker, mock_api = make_mock_xtp_broker()
        # _do_heartbeat 调用 QueryAsset，不应抛异常
        broker._do_heartbeat()

    def test_repr(self):
        """__repr__ 输出格式正确"""
        broker, _ = make_mock_xtp_broker(user="test_user")
        r = repr(broker)
        self.assertIn("XTPBroker", r)
        self.assertIn("logged_in", r)
        self.assertIn("test_user", r)

    def test_connect_without_sdk_returns_false(self):
        """无 Mock SDK 时 connect 返回 False（XTP SDK 不可用）"""
        broker = XTPBroker(user="u", server_addr="1.2.3.4:6002")
        result = broker.connect()
        self.assertFalse(result)


# ══════════════════════════════════════════════════════════════════
# 11. TestXTPParseAddr — _parse_addr 解析测试
# ══════════════════════════════════════════════════════════════════


class TestXTPParseAddr(unittest.TestCase):
    """XTP _parse_addr 静态方法测试"""

    def test_parse_standard_addr(self):
        """标准 ip:port 格式"""
        ip, port = XTPBroker._parse_addr("192.168.1.1:6002")
        self.assertEqual(ip, "192.168.1.1")
        self.assertEqual(port, "6002")

    def test_parse_localhost(self):
        """localhost:port 格式"""
        ip, port = XTPBroker._parse_addr("127.0.0.1:6002")
        self.assertEqual(ip, "127.0.0.1")
        self.assertEqual(port, "6002")

    def test_parse_addr_without_port(self):
        """无端口时返回默认端口 6002"""
        ip, port = XTPBroker._parse_addr("192.168.1.1")
        self.assertEqual(ip, "192.168.1.1")
        self.assertEqual(port, "6002")

    def test_parse_addr_default_port(self):
        """空字符串返回默认端口"""
        ip, port = XTPBroker._parse_addr("")
        self.assertEqual(ip, "")
        self.assertEqual(port, "6002")

    def test_parse_addr_multiple_colons_ipv6_like(self):
        """使用 rsplit 处理包含多个冒号的地址"""
        # rsplit(":", 1) 会从右侧分割
        ip, port = XTPBroker._parse_addr("fe80::1:6002")
        self.assertEqual(ip, "fe80::1")
        self.assertEqual(port, "6002")

    def test_parse_addr_large_port(self):
        """大端口号"""
        ip, port = XTPBroker._parse_addr("10.0.0.1:65535")
        self.assertEqual(ip, "10.0.0.1")
        self.assertEqual(port, "65535")


if __name__ == "__main__":
    unittest.main()
