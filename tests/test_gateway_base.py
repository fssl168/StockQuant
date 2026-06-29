# -*- coding: utf-8 -*-
"""Gateway 基类单元测试

测试覆盖：
1. GatewayConfig 默认值和自定义
2. GatewayState 状态机转换
3. BaseGateway 生命周期（connect/disconnect/reconnect）
4. BaseGateway 统一下单流程（校验/日志/状态更新）
5. BaseGateway 撤单流程
6. 事件系统（注册/触发）
7. ReconnectStrategy（延迟计算/重试限制/成功重置）
8. ConnectionStats（统计更新）
9. 交易日志审计
10. Mock Gateway 完整集成测试（连接→登录→下单→撤单→断开）
"""

from __future__ import annotations

import time
import threading
from unittest.mock import MagicMock, patch

import pytest

from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.models.trade import TradeData
from stockquant.events import EventType
from stockquant.execution.gateway_base import (
    BaseGateway,
    GatewayConfig,
    GatewayState,
    GatewayEvent,
    ConnectionStats,
)
from stockquant.execution.reconnect import ReconnectStrategy


# ── Mock Gateway（用于测试） ────────────────────────────────────────


class MockGateway(BaseGateway):
    """测试用 Mock Gateway — 所有操作都是内存模拟"""

    def __init__(self, config=None, **kwargs):
        super().__init__(config=config, **kwargs)
        self.connect_called = False
        self.disconnect_called = False
        self.login_called = False
        self.logout_called = False
        self.heartbeat_count = 0
        self.place_order_results = {}  # order_id -> (order_id_str, True)
        self.cancel_order_results = {}  # order_id -> bool
        self.connect_should_fail = False
        self.login_should_fail = False
        self.heartbeat_should_fail = False

    def _do_connect(self) -> bool:
        self.connect_called = True
        return not self.connect_should_fail

    def _do_disconnect(self) -> None:
        self.disconnect_called = True

    def _do_login(self) -> bool:
        self.login_called = True
        return not self.login_should_fail

    def _do_heartbeat(self) -> None:
        self.heartbeat_count += 1
        if self.heartbeat_should_fail:
            raise ConnectionError("heartbeat failed")

    def _do_place_order(self, order):
        if order.order_id in self.place_order_results:
            return self.place_order_results[order.order_id]
        return (order.order_id, True)

    def _do_cancel_order(self, order):
        if order.order_id in self.cancel_order_results:
            return self.cancel_order_results[order.order_id]
        return True

    def _do_query_positions(self):
        return {"600000.SH": {"quantity": 1000, "price": 10.5}}

    def _do_query_balance(self):
        return {"cash": 100000.0, "frozen": 5000.0, "equity": 150000.0}


# ── 辅助函数 ──────────────────────────────────────────────────────


def make_order(symbol="600000.SH", side=OrderSide.BUY, price=10.0,
               quantity=100, order_type=OrderType.LIMIT, order_id=""):
    """创建测试订单"""
    return Order(
        symbol=symbol,
        side=side,
        order_type=order_type,
        price=price,
        quantity=quantity,
        order_id=order_id,
    )


def _no_heartbeat_config():
    """创建禁用心跳和订单同步的配置（避免线程干扰）"""
    return GatewayConfig(
        heartbeat_enabled=False,
        order_sync_enabled=False,
        reconnect_enabled=False,
    )


def _no_threads_config():
    """创建禁用所有后台线程的配置"""
    return GatewayConfig(
        heartbeat_enabled=False,
        order_sync_enabled=False,
        reconnect_enabled=False,
    )


# ══════════════════════════════════════════════════════════════════
# 1. GatewayConfig 测试
# ══════════════════════════════════════════════════════════════════


class TestGatewayConfig:
    """GatewayConfig 默认值和自定义测试"""

    def test_default_values(self):
        """默认配置值应正确"""
        cfg = GatewayConfig()
        assert cfg.reconnect_enabled is True
        assert cfg.reconnect_max_retries == 10
        assert cfg.reconnect_initial_delay == 1.0
        assert cfg.reconnect_max_delay == 60.0
        assert cfg.reconnect_backoff_factor == 2.0
        assert cfg.heartbeat_enabled is True
        assert cfg.heartbeat_interval == 30.0
        assert cfg.heartbeat_timeout == 10.0
        assert cfg.order_sync_enabled is True
        assert cfg.order_sync_interval == 5.0
        assert cfg.connect_timeout == 10.0

    def test_custom_values(self):
        """自定义配置值应正确"""
        cfg = GatewayConfig(
            reconnect_enabled=False,
            reconnect_max_retries=5,
            reconnect_initial_delay=2.0,
            reconnect_max_delay=30.0,
            heartbeat_enabled=False,
            heartbeat_interval=10.0,
            order_sync_enabled=False,
        )
        assert cfg.reconnect_enabled is False
        assert cfg.reconnect_max_retries == 5
        assert cfg.reconnect_initial_delay == 2.0
        assert cfg.reconnect_max_delay == 30.0
        assert cfg.heartbeat_enabled is False
        assert cfg.heartbeat_interval == 10.0
        assert cfg.order_sync_enabled is False


# ══════════════════════════════════════════════════════════════════
# 2. GatewayState 状态机测试
# ══════════════════════════════════════════════════════════════════


class TestGatewayState:
    """GatewayState 状态机转换测试"""

    def test_initial_state(self):
        """初始状态应为 DISCONNECTED"""
        gw = MockGateway(config=_no_threads_config())
        assert gw.state == GatewayState.DISCONNECTED
        assert gw.connected is False
        assert gw.logged_in is False
        gw.disconnect()

    def test_valid_transition_disconnected_to_connecting(self):
        """DISCONNECTED → CONNECTING 应成功"""
        gw = MockGateway(config=_no_threads_config())
        assert gw._transition(GatewayState.CONNECTING) is True
        assert gw.state == GatewayState.CONNECTING
        gw.disconnect()

    def test_invalid_transition_disconnected_to_connected(self):
        """DISCONNECTED → CONNECTED 应被拒绝（需经过 CONNECTING）"""
        gw = MockGateway(config=_no_threads_config())
        assert gw._transition(GatewayState.CONNECTED) is False
        assert gw.state == GatewayState.DISCONNECTED
        gw.disconnect()

    def test_valid_transition_connecting_to_connected(self):
        """CONNECTING → CONNECTED 应成功"""
        gw = MockGateway(config=_no_threads_config())
        gw._transition(GatewayState.CONNECTING)
        assert gw._transition(GatewayState.CONNECTED) is True
        assert gw.state == GatewayState.CONNECTED
        assert gw.connected is True
        gw.disconnect()

    def test_valid_transition_connecting_to_error(self):
        """CONNECTING → ERROR 应成功"""
        gw = MockGateway(config=_no_threads_config())
        gw._transition(GatewayState.CONNECTING)
        assert gw._transition(GatewayState.ERROR) is True
        assert gw.state == GatewayState.ERROR
        gw.disconnect()

    def test_valid_transition_connected_to_logged_in(self):
        """CONNECTED → LOGGED_IN 应成功"""
        gw = MockGateway(config=_no_threads_config())
        gw._transition(GatewayState.CONNECTING)
        gw._transition(GatewayState.CONNECTED)
        assert gw._transition(GatewayState.LOGGED_IN) is True
        assert gw.state == GatewayState.LOGGED_IN
        assert gw.logged_in is True
        gw.disconnect()

    def test_valid_transition_logged_in_to_disconnected(self):
        """LOGGED_IN → DISCONNECTED 应成功"""
        gw = MockGateway(config=_no_threads_config())
        gw._transition(GatewayState.CONNECTING)
        gw._transition(GatewayState.CONNECTED)
        gw._transition(GatewayState.LOGGED_IN)
        assert gw._transition(GatewayState.DISCONNECTED) is True
        assert gw.state == GatewayState.DISCONNECTED

    def test_invalid_transition_disconnected_to_logged_in(self):
        """DISCONNECTED → LOGGED_IN 应被拒绝"""
        gw = MockGateway(config=_no_threads_config())
        assert gw._transition(GatewayState.LOGGED_IN) is False
        assert gw.state == GatewayState.DISCONNECTED

    def test_invalid_transition_connected_to_connecting(self):
        """CONNECTED → CONNECTING 应被拒绝"""
        gw = MockGateway(config=_no_threads_config())
        gw._transition(GatewayState.CONNECTING)
        gw._transition(GatewayState.CONNECTED)
        assert gw._transition(GatewayState.CONNECTING) is False
        assert gw.state == GatewayState.CONNECTED
        gw.disconnect()

    def test_error_to_connecting(self):
        """ERROR → CONNECTING 应成功"""
        gw = MockGateway(config=_no_threads_config())
        gw._transition(GatewayState.CONNECTING)
        gw._transition(GatewayState.ERROR)
        assert gw._transition(GatewayState.CONNECTING) is True
        gw.disconnect()

    def test_error_to_reconnecting(self):
        """ERROR → RECONNECTING 应成功"""
        gw = MockGateway(config=_no_threads_config())
        gw._transition(GatewayState.CONNECTING)
        gw._transition(GatewayState.ERROR)
        assert gw._transition(GatewayState.RECONNECTING) is True
        gw.disconnect()

    def test_reconnecting_to_connected(self):
        """RECONNECTING → CONNECTED 应成功"""
        gw = MockGateway(config=_no_threads_config())
        gw._transition(GatewayState.CONNECTING)
        gw._transition(GatewayState.ERROR)
        gw._transition(GatewayState.RECONNECTING)
        assert gw._transition(GatewayState.CONNECTED) is True
        gw.disconnect()

    def test_state_change_callback(self):
        """状态变更回调应被调用"""
        gw = MockGateway(config=_no_threads_config())
        changes = []
        gw.on_state_change(lambda old, new: changes.append((old, new)))

        gw._transition(GatewayState.CONNECTING)
        gw._transition(GatewayState.CONNECTED)
        gw.disconnect()

        assert len(changes) >= 3  # CONNECTING, CONNECTED, DISCONNECTED
        assert changes[0] == (GatewayState.DISCONNECTED, GatewayState.CONNECTING)
        assert changes[1] == (GatewayState.CONNECTING, GatewayState.CONNECTED)

    def test_state_change_callback_exception_does_not_break(self):
        """状态变更回调异常不应中断转换流程"""
        gw = MockGateway(config=_no_threads_config())
        gw.on_state_change(lambda old, new: 1 / 0)
        # 不应抛异常
        assert gw._transition(GatewayState.CONNECTING) is True
        gw.disconnect()


# ══════════════════════════════════════════════════════════════════
# 3. BaseGateway 生命周期测试
# ══════════════════════════════════════════════════════════════════


class TestBaseGatewayLifecycle:
    """BaseGateway connect/disconnect/reconnect 测试"""

    def test_connect_success(self):
        """连接成功应到达 LOGGED_IN 状态"""
        gw = MockGateway(config=_no_heartbeat_config())
        assert gw.connect() is True
        assert gw.state == GatewayState.LOGGED_IN
        assert gw.logged_in is True
        assert gw.connect_called is True
        assert gw.login_called is True
        gw.disconnect()

    def test_connect_failure(self):
        """连接失败应到达 ERROR 状态"""
        gw = MockGateway(config=_no_threads_config())
        gw.connect_should_fail = True
        assert gw.connect() is False
        assert gw.state == GatewayState.ERROR
        assert gw.connect_called is True
        gw.disconnect()

    def test_login_failure_still_connected(self):
        """登录失败但连接成功应返回 True，状态 CONNECTED"""
        gw = MockGateway(config=_no_threads_config())
        gw.login_should_fail = True
        result = gw.connect()
        # 连接成功但登录失败，connect() 返回 True
        assert result is True
        assert gw.state == GatewayState.CONNECTED
        gw.disconnect()

    def test_disconnect(self):
        """断开应到达 DISCONNECTED 状态"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        gw.disconnect()
        assert gw.state == GatewayState.DISCONNECTED
        assert gw.connected is False
        assert gw.disconnect_called is True

    def test_disconnect_when_disconnected(self):
        """已断开时再次断开不应报错"""
        gw = MockGateway(config=_no_threads_config())
        gw.disconnect()  # 不应抛异常

    def test_reconnect(self):
        """手动重连应成功"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        gw.disconnect()
        gw.login_should_fail = False
        assert gw.reconnect() is True
        assert gw.state == GatewayState.LOGGED_IN
        gw.disconnect()

    def test_connect_connects_sdk(self):
        """connect 应调用子类 _do_connect 和 _do_login"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        assert gw.connect_called is True
        assert gw.login_called is True
        gw.disconnect()

    def test_connect_emits_events(self):
        """连接成功应触发 CONNECTED 和 LOGIN_SUCCESS 事件"""
        gw = MockGateway(config=_no_heartbeat_config())
        events = []
        gw.register_event_handler(GatewayEvent.CONNECTED, lambda d: events.append("connected"))
        gw.register_event_handler(GatewayEvent.LOGIN_SUCCESS, lambda d: events.append("login"))
        gw.connect()
        assert "connected" in events
        assert "login" in events
        gw.disconnect()


# ══════════════════════════════════════════════════════════════════
# 4. BaseGateway 下单流程测试
# ══════════════════════════════════════════════════════════════════


class TestBaseGatewayPlaceOrder:
    """BaseGateway 统一下单流程测试"""

    def test_place_order_success(self):
        """成功下单应返回 TradeData"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        order = make_order()
        trade = gw.place_order(order)
        assert trade is not None
        assert trade.order_id == order.order_id
        assert trade.symbol == order.symbol
        assert order.order_id in gw._open_orders
        gw.disconnect()

    def test_place_order_not_connected(self):
        """未连接时下单应返回 None"""
        gw = MockGateway(config=_no_threads_config())
        order = make_order()
        trade = gw.place_order(order)
        assert trade is None
        assert order.status == EventType.ORDER_REJECTED.value

    def test_place_order_invalid_quantity(self):
        """无效数量下单应被拒绝"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        order = make_order(quantity=0)
        trade = gw.place_order(order)
        assert trade is None
        assert order.status == EventType.ORDER_REJECTED.value

    def test_place_order_negative_quantity(self):
        """负数数量下单应被拒绝"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        order = make_order(quantity=-100)
        trade = gw.place_order(order)
        assert trade is None
        assert order.status == EventType.ORDER_REJECTED.value

    def test_place_order_broker_rejects(self):
        """子类拒绝下单时应返回 None"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        order = make_order()
        order.order_id = "test_reject"
        gw.place_order_results["test_reject"] = ("test_reject", False)
        trade = gw.place_order(order)
        assert trade is None
        assert order.status == EventType.ORDER_REJECTED.value
        gw.disconnect()

    def test_place_order_emits_event(self):
        """成功下单应触发 ORDER_SUBMITTED 事件"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        events = []
        gw.register_event_handler(GatewayEvent.ORDER_SUBMITTED,
                                  lambda d: events.append(d))
        order = make_order()
        gw.place_order(order)
        assert len(events) == 1
        assert events[0]["order_id"] == order.order_id
        gw.disconnect()

    def test_place_order_creates_audit_log(self):
        """下单应创建审计日志"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        order = make_order()
        gw.place_order(order)
        logs = gw.order_audit_log
        assert len(logs) >= 1
        assert logs[-1].order_id == order.order_id
        assert logs[-1].status == "SUBMITTED"
        gw.disconnect()

    def test_place_order_exception_handling(self):
        """下单异常应被捕获并返回 None"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()

        def bad_place_order(order):
            raise RuntimeError("SDK error")

        gw._do_place_order = bad_place_order
        order = make_order()
        trade = gw.place_order(order)
        assert trade is None
        assert "SDK error" in gw.stats.last_error
        gw.disconnect()


# ══════════════════════════════════════════════════════════════════
# 5. BaseGateway 撤单流程测试
# ══════════════════════════════════════════════════════════════════


class TestBaseGatewayCancelOrder:
    """BaseGateway 统一撤单流程测试"""

    def test_cancel_order_success(self):
        """成功撤单应返回 True"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        order = make_order()
        gw.place_order(order)
        assert gw.cancel_order(order) is True
        assert order.status == EventType.ORDER_CANCELLED.value
        assert order.order_id not in gw._open_orders
        gw.disconnect()

    def test_cancel_order_not_connected(self):
        """未连接时撤单应返回 False"""
        gw = MockGateway(config=_no_threads_config())
        order = make_order()
        assert gw.cancel_order(order) is False

    def test_cancel_order_not_in_open_orders(self):
        """撤销未提交的订单应返回 False"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        order = make_order()
        # 未先 place_order
        assert gw.cancel_order(order) is False
        gw.disconnect()

    def test_cancel_order_broker_fails(self):
        """子类撤单失败应返回 False"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        order = make_order()
        order.order_id = "test_cancel_fail"
        gw.place_order(order)
        gw.cancel_order_results["test_cancel_fail"] = False
        assert gw.cancel_order(order) is False
        gw.disconnect()

    def test_cancel_order_emits_event(self):
        """成功撤单应触发 ORDER_CANCELLED 事件"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        events = []
        gw.register_event_handler(GatewayEvent.ORDER_CANCELLED,
                                  lambda d: events.append(d))
        order = make_order()
        gw.place_order(order)
        gw.cancel_order(order)
        assert len(events) == 1
        assert events[0]["order_id"] == order.order_id
        gw.disconnect()

    def test_cancel_order_creates_audit_log(self):
        """撤单应创建审计日志"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        order = make_order()
        gw.place_order(order)
        gw.cancel_order(order)
        logs = gw.order_audit_log
        cancel_logs = [l for l in logs if l.status == "CANCELLED"]
        assert len(cancel_logs) >= 1
        gw.disconnect()


# ══════════════════════════════════════════════════════════════════
# 6. 事件系统测试
# ══════════════════════════════════════════════════════════════════


class TestEventSystem:
    """事件注册/触发/注销测试"""

    def test_register_and_emit(self):
        """注册处理器后触发事件应被调用"""
        gw = MockGateway(config=_no_threads_config())
        received = []
        gw.register_event_handler(GatewayEvent.CONNECTED, lambda d: received.append(d))
        gw.emit_event(GatewayEvent.CONNECTED, {"test": True})
        assert len(received) == 1
        assert received[0]["test"] is True

    def test_multiple_handlers(self):
        """同一事件可注册多个处理器"""
        gw = MockGateway(config=_no_threads_config())
        results = []
        gw.register_event_handler(GatewayEvent.CONNECTED, lambda d: results.append(1))
        gw.register_event_handler(GatewayEvent.CONNECTED, lambda d: results.append(2))
        gw.emit_event(GatewayEvent.CONNECTED)
        assert results == [1, 2]

    def test_different_events(self):
        """不同事件应独立触发"""
        gw = MockGateway(config=_no_threads_config())
        connected = []
        disconnected = []
        gw.register_event_handler(GatewayEvent.CONNECTED, lambda d: connected.append(True))
        gw.register_event_handler(GatewayEvent.DISCONNECTED, lambda d: disconnected.append(True))
        gw.emit_event(GatewayEvent.CONNECTED)
        assert len(connected) == 1
        assert len(disconnected) == 0
        gw.emit_event(GatewayEvent.DISCONNECTED)
        assert len(disconnected) == 1

    def test_handler_exception_does_not_break_others(self):
        """一个处理器异常不影响其他处理器"""
        gw = MockGateway(config=_no_threads_config())
        results = []
        gw.register_event_handler(GatewayEvent.CONNECTED, lambda d: 1 / 0)
        gw.register_event_handler(GatewayEvent.CONNECTED, lambda d: results.append(True))
        gw.emit_event(GatewayEvent.CONNECTED)
        assert len(results) == 1

    def test_unregister_handler(self):
        """注销处理器后不再被调用"""
        gw = MockGateway(config=_no_threads_config())
        results = []
        handler = lambda d: results.append(True)
        gw.register_event_handler(GatewayEvent.CONNECTED, handler)
        gw.emit_event(GatewayEvent.CONNECTED)
        assert len(results) == 1
        gw.unregister_event_handler(GatewayEvent.CONNECTED, handler)
        gw.emit_event(GatewayEvent.CONNECTED)
        assert len(results) == 1  # 未增加

    def test_emit_no_handlers(self):
        """无处理器时触发事件不应报错"""
        gw = MockGateway(config=_no_threads_config())
        gw.emit_event(GatewayEvent.CONNECTED)  # 不应抛异常


# ══════════════════════════════════════════════════════════════════
# 7. ReconnectStrategy 测试
# ══════════════════════════════════════════════════════════════════


class TestReconnectStrategy:
    """断线重连策略测试"""

    def test_default_initial_delay(self):
        """初始延迟应为 initial_delay"""
        strategy = ReconnectStrategy(initial_delay=1.0, backoff_factor=2.0)
        assert strategy.next_delay() == 1.0

    def test_exponential_backoff(self):
        """延迟应指数增长"""
        strategy = ReconnectStrategy(initial_delay=1.0, backoff_factor=2.0, max_delay=1000.0)
        assert strategy.next_delay() == 1.0  # attempt=0: 1.0 * 2^0
        strategy.record_failure()
        assert strategy.next_delay() == 2.0  # attempt=1: 1.0 * 2^1
        strategy.record_failure()
        assert strategy.next_delay() == 4.0  # attempt=2: 1.0 * 2^2
        strategy.record_failure()
        assert strategy.next_delay() == 8.0  # attempt=3: 1.0 * 2^3

    def test_max_delay_cap(self):
        """延迟不应超过 max_delay"""
        strategy = ReconnectStrategy(
            initial_delay=1.0,
            backoff_factor=10.0,
            max_delay=30.0,
        )
        strategy.record_failure()
        strategy.record_failure()
        # 1.0 * 10^2 = 100, 但 cap 在 30
        assert strategy.next_delay() == 30.0

    def test_custom_backoff_factor(self):
        """自定义退避因子"""
        strategy = ReconnectStrategy(initial_delay=1.0, backoff_factor=3.0, max_delay=1000.0)
        strategy.record_failure()
        assert strategy.next_delay() == 3.0  # 1.0 * 3^1

    def test_record_success_resets(self):
        """成功后应重置延迟"""
        strategy = ReconnectStrategy(initial_delay=1.0, backoff_factor=2.0, max_delay=1000.0)
        strategy.record_failure()
        strategy.record_failure()
        assert strategy.attempt == 2
        strategy.record_success()
        assert strategy.attempt == 0
        assert strategy.next_delay() == 1.0  # 回到初始值

    def test_should_retry_with_limit(self):
        """有限重试次数"""
        strategy = ReconnectStrategy(max_retries=3)
        assert strategy.should_retry() is True
        strategy.record_failure()
        assert strategy.should_retry() is True
        strategy.record_failure()
        assert strategy.should_retry() is True
        strategy.record_failure()
        assert strategy.should_retry() is False  # 已达上限

    def test_should_retry_unlimited(self):
        """无限重试（max_retries=0）"""
        strategy = ReconnectStrategy(max_retries=0)
        for _ in range(100):
            strategy.record_failure()
            assert strategy.should_retry() is True

    def test_reset(self):
        """reset 应完全重置状态"""
        strategy = ReconnectStrategy(max_retries=3)
        strategy.record_failure()
        strategy.record_failure()
        strategy.reset()
        assert strategy.attempt == 0
        assert strategy.consecutive_failures == 0
        assert strategy.should_retry() is True

    def test_exhausted_property(self):
        """exhausted 属性应正确反映状态"""
        strategy = ReconnectStrategy(max_retries=2)
        assert strategy.exhausted is False
        strategy.record_failure()
        assert strategy.exhausted is False
        strategy.record_failure()
        assert strategy.exhausted is True

    def test_consecutive_failures(self):
        """连续失败计数"""
        strategy = ReconnectStrategy()
        assert strategy.consecutive_failures == 0
        strategy.record_failure()
        assert strategy.consecutive_failures == 1
        strategy.record_failure()
        assert strategy.consecutive_failures == 2
        strategy.record_success()
        assert strategy.consecutive_failures == 0

    def test_repr(self):
        """repr 应包含有用信息"""
        strategy = ReconnectStrategy(max_retries=10)
        r = repr(strategy)
        assert "ReconnectStrategy" in r
        assert "attempt=0" in r

    def test_default_no_max_retries(self):
        """默认配置应有最大重试限制"""
        strategy = ReconnectStrategy()
        assert strategy.max_retries == 10


# ══════════════════════════════════════════════════════════════════
# 8. ConnectionStats 测试
# ══════════════════════════════════════════════════════════════════


class TestConnectionStats:
    """连接统计测试"""

    def test_default_stats(self):
        """初始统计应为零"""
        gw = MockGateway(config=_no_threads_config())
        stats = gw.stats
        assert stats.connect_count == 0
        assert stats.disconnect_count == 0
        assert stats.reconnect_count == 0
        assert stats.last_connect_time is None
        assert stats.last_disconnect_time is None
        assert stats.last_error is None
        gw.disconnect()

    def test_connect_increments_stats(self):
        """连接成功应增加 connect_count"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        assert gw.stats.connect_count == 1
        assert gw.stats.last_connect_time is not None
        gw.disconnect()
        assert gw.stats.disconnect_count == 1

    def test_multiple_connects(self):
        """多次连接应累加统计"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        gw.disconnect()
        # reconnect() 内部先 disconnect()（已 DISCONNECTED，转换被拒绝不计入）
        # 再 connect() → CONNECTED（connect_count +1）
        gw.reconnect()
        assert gw.stats.connect_count == 2
        assert gw.stats.disconnect_count == 1  # 只有手动 disconnect() 成功转换
        gw.disconnect()
        assert gw.stats.disconnect_count == 2

    def test_reconnect_increments_reconnect_count(self):
        """ERROR → RECONNECTING 应增加 reconnect_count"""
        gw = MockGateway(config=_no_threads_config())
        gw._transition(GatewayState.CONNECTING)
        gw._transition(GatewayState.ERROR)
        gw._transition(GatewayState.RECONNECTING)
        assert gw.stats.reconnect_count == 1
        gw.disconnect()


# ══════════════════════════════════════════════════════════════════
# 9. 交易日志审计测试
# ══════════════════════════════════════════════════════════════════


class TestAuditLog:
    """交易日志审计测试"""

    def test_empty_log_initially(self):
        """初始审计日志应为空"""
        gw = MockGateway(config=_no_threads_config())
        assert gw.order_audit_log == []
        gw.disconnect()

    def test_place_order_creates_log(self):
        """下单应创建审计日志"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        order = make_order()
        gw.place_order(order)
        logs = gw.order_audit_log
        assert len(logs) >= 1
        log = logs[-1]
        assert log.order_id == order.order_id
        assert log.symbol == order.symbol
        assert log.side == OrderSide.BUY.value
        assert log.price == order.price
        assert log.quantity == order.quantity
        gw.disconnect()

    def test_cancel_order_creates_log(self):
        """撤单应创建审计日志"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        order = make_order()
        gw.place_order(order)
        gw.cancel_order(order)
        logs = gw.order_audit_log
        cancel_logs = [l for l in logs if l.status == "CANCELLED"]
        assert len(cancel_logs) >= 1
        assert cancel_logs[0].reason == "user cancel"
        gw.disconnect()

    def test_rejected_order_creates_log(self):
        """被拒绝的订单应创建审计日志"""
        gw = MockGateway(config=_no_threads_config())
        order = make_order()
        gw.place_order(order)  # 未连接，会被拒绝
        logs = gw.order_audit_log
        rejected = [l for l in logs if l.status == "REJECTED"]
        assert len(rejected) >= 1

    def test_audit_log_is_copy(self):
        """order_audit_log 应返回副本，不暴露内部列表"""
        gw = MockGateway(config=_no_threads_config())
        log1 = gw.order_audit_log
        log2 = gw.order_audit_log
        assert log1 is not log2
        assert log1 == log2


# ══════════════════════════════════════════════════════════════════
# 10. Mock Gateway 完整集成测试
# ══════════════════════════════════════════════════════════════════


class TestMockGatewayIntegration:
    """Mock Gateway 完整生命周期集成测试"""

    def test_full_lifecycle(self):
        """完整生命周期：连接 → 登录 → 下单 → 撤单 → 断开"""
        gw = MockGateway(config=_no_heartbeat_config())

        # 1. 连接并登录
        assert gw.connect() is True
        assert gw.state == GatewayState.LOGGED_IN

        # 2. 下单
        order1 = make_order(symbol="600000.SH", quantity=100)
        trade1 = gw.place_order(order1)
        assert trade1 is not None
        assert order1.order_id in gw._open_orders

        order2 = make_order(symbol="000001.SZ", quantity=200)
        trade2 = gw.place_order(order2)
        assert trade2 is not None
        assert len(gw._open_orders) == 2

        # 3. 查询持仓和余额
        positions = gw.get_positions()
        assert "600000.SH" in positions
        balance = gw.get_balance()
        assert balance["cash"] == 100000.0

        # 4. 撤单
        assert gw.cancel_order(order1) is True
        assert order1.order_id not in gw._open_orders
        assert len(gw._open_orders) == 1

        # 5. 断开
        gw.disconnect()
        assert gw.state == GatewayState.DISCONNECTED
        assert gw.disconnect_called is True

        # 6. 断开后操作应返回空/False
        assert gw.get_positions() == {}
        assert gw.get_balance() == {}

    def test_place_order_after_disconnect(self):
        """断开后下单应被拒绝"""
        gw = MockGateway(config=_no_heartbeat_config())
        gw.connect()
        gw.disconnect()
        order = make_order()
        trade = gw.place_order(order)
        assert trade is None
        assert order.status == EventType.ORDER_REJECTED.value

    def test_multiple_connect_disconnect_cycles(self):
        """多次连接/断开循环应正常工作"""
        gw = MockGateway(config=_no_heartbeat_config())
        for i in range(3):
            assert gw.connect() is True
            order = make_order()
            gw.place_order(order)
            gw.cancel_order(order)
            gw.disconnect()
        assert gw.stats.connect_count == 3
        assert gw.stats.disconnect_count == 3

    def test_order_sync_updates_status(self):
        """订单同步应更新本地缓存"""
        gw = MockGateway(config=GatewayConfig(
            heartbeat_enabled=False,
            reconnect_enabled=False,
            order_sync_enabled=False,  # 手动调用
        ))
        gw.connect()
        order = make_order()
        order.order_id = "sync_test"
        gw.place_order(order)

        # 模拟远程订单已成交
        gw._do_query_orders = lambda: [
            {"order_id": "sync_test", "status": EventType.ORDER_FILLED.value}
        ]

        events = []
        gw.register_event_handler(GatewayEvent.ORDER_FILLED,
                                  lambda d: events.append(d))
        gw._sync_order_status()

        assert order.status == EventType.ORDER_FILLED.value
        assert "sync_test" not in gw._open_orders
        assert len(events) == 1
        gw.disconnect()

    def test_repr(self):
        """repr 应包含状态信息"""
        gw = MockGateway(config=_no_threads_config())
        r = repr(gw)
        assert "BaseGateway" in r
        assert "disconnected" in r

    def test_inherits_from_broker(self):
        """BaseGateway 应继承 Broker"""
        from stockquant.engine.broker import Broker
        assert issubclass(BaseGateway, Broker)
        assert isinstance(MockGateway(), Broker)
