# -*- coding: utf-8 -*-
"""#1 P0 任务：统一券商 Gateway 基类

提供 QMT/XTP 等券商接口的统一抽象，包括：
- 统一连接状态管理
- 断线重连机制
- 订单状态同步
- 心跳保活
- 交易日志审计

所有券商接口（QMT/XTP/CTP）应继承此基类，实现统一的生命周期管理。
"""

from __future__ import annotations

import logging
import time
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.models.trade import TradeData
from stockquant.engine.broker import Broker, OrderAuditLog
from stockquant.events import EventType

logger = logging.getLogger(__name__)


# ── 枚举与数据类 ──────────────────────────────────────────────────────

class GatewayState(str, Enum):
    """Gateway 连接状态

    状态转换图::

        DISCONNECTED → CONNECTING → CONNECTED → LOGGED_IN
               ↑           │                          │
               └───────────┘  (连接失败)             │
               ↑                                      │
               └──────────────────────────────────────┘  (断开)
               ↑
               └──────  RECONNECTING ←──────────────────┘  (自动重连)
    """
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    LOGGED_IN = "logged_in"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class GatewayEvent(str, Enum):
    """Gateway 事件类型"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_PARTIAL_FILL = "order_partial_fill"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    TRADE = "trade"
    ERROR = "error"


@dataclass
class GatewayConfig:
    """Gateway 配置

    Attributes:
        reconnect_enabled: 是否启用自动重连
        reconnect_max_retries: 最大重连次数（0 = 无限）
        reconnect_initial_delay: 初始重连延迟（秒）
        reconnect_max_delay: 最大重连延迟（秒）
        reconnect_backoff_factor: 指数退避因子
        heartbeat_enabled: 是否启用心跳保活
        heartbeat_interval: 心跳间隔（秒）
        heartbeat_timeout: 心跳超时（秒）
        order_sync_enabled: 是否启用订单状态同步
        order_sync_interval: 订单同步间隔（秒）
        connect_timeout: 连接超时（秒）
    """
    # 重连配置
    reconnect_enabled: bool = True
    reconnect_max_retries: int = 10
    reconnect_initial_delay: float = 1.0
    reconnect_max_delay: float = 60.0
    reconnect_backoff_factor: float = 2.0
    # 心跳配置
    heartbeat_enabled: bool = True
    heartbeat_interval: float = 30.0
    heartbeat_timeout: float = 10.0
    # 订单同步配置
    order_sync_enabled: bool = True
    order_sync_interval: float = 5.0
    # 通用
    connect_timeout: float = 10.0


@dataclass
class ConnectionStats:
    """连接统计

    Attributes:
        connect_count: 累计连接成功次数
        disconnect_count: 累计断开次数
        reconnect_count: 累计重连次数
        last_connect_time: 最近连接成功时间戳
        last_disconnect_time: 最近断开时间戳
        last_error: 最近错误信息
        total_uptime: 累计在线时长（秒）
        total_downtime: 累计离线时长（秒）
    """
    connect_count: int = 0
    disconnect_count: int = 0
    reconnect_count: int = 0
    last_connect_time: Optional[float] = None
    last_disconnect_time: Optional[float] = None
    last_error: Optional[str] = None
    total_uptime: float = 0.0
    total_downtime: float = 0.0


# ── 允许的状态转换表 ─────────────────────────────────────────────────

_VALID_TRANSITIONS: Dict[GatewayState, set] = {
    GatewayState.DISCONNECTED: {GatewayState.CONNECTING, GatewayState.LOGGED_IN},
    GatewayState.CONNECTING: {GatewayState.CONNECTED, GatewayState.ERROR,
                               GatewayState.DISCONNECTED, GatewayState.RECONNECTING},
    GatewayState.CONNECTED: {GatewayState.LOGGED_IN, GatewayState.DISCONNECTED,
                              GatewayState.ERROR},
    GatewayState.LOGGED_IN: {GatewayState.DISCONNECTED, GatewayState.ERROR},
    GatewayState.RECONNECTING: {GatewayState.CONNECTED, GatewayState.ERROR,
                                GatewayState.DISCONNECTED},
    GatewayState.ERROR: {GatewayState.CONNECTING, GatewayState.DISCONNECTED,
                        GatewayState.RECONNECTING},
}


class BaseGateway(Broker):
    """统一券商 Gateway 基类

    所有券商接口（QMT/XTP/CTP）应继承此基类，实现统一的生命周期管理。

    提供的能力：
    - 连接状态机（DISCONNECTED -> CONNECTING -> CONNECTED -> LOGGED_IN）
    - 断线自动重连（指数退避）
    - 心跳保活（可选）
    - 订单状态同步（定时查询更新）
    - 交易日志审计
    - 连接统计

    子类需实现的抽象方法：
    - ``_do_connect() -> bool``：执行实际连接
    - ``_do_disconnect() -> None``：执行实际断开
    - ``_do_login() -> bool``：执行登录
    - ``_do_heartbeat() -> None``：发送心跳

    可选覆盖的方法（有默认行为）：
    - ``_do_logout() -> None``：执行登出
    - ``_do_place_order(order) -> tuple(order_id, success)``：实际下单
    - ``_do_cancel_order(order) -> bool``：实际撤单
    - ``_do_query_positions() -> dict``：查询持仓
    - ``_do_query_balance() -> dict``：查询余额
    - ``_do_query_orders() -> list``：查询挂单
    """

    # ── 构造 ──────────────────────────────────────────────────────

    def __init__(self, config: GatewayConfig = None, **kwargs):
        """
        Args:
            config: Gateway 配置，默认使用 GatewayConfig()
            **kwargs: 可选参数，传递给子类
        """
        self._config = config or GatewayConfig()
        self._state = GatewayState.DISCONNECTED
        self._stats = ConnectionStats()
        self._lock = threading.Lock()
        self._order_log: List[OrderAuditLog] = []
        self._open_orders: Dict[str, Order] = {}
        self._trade_results: Dict[str, Dict] = {}
        self._event_handlers: Dict[GatewayEvent, list] = {}

        # 重连相关
        self._reconnect_thread: Optional[threading.Thread] = None
        self._reconnect_stop_event = threading.Event()
        self._reconnect_attempt = 0

        # 心跳相关
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_stop_event = threading.Event()
        self._last_heartbeat_time: Optional[float] = None

        # 订单同步相关
        self._order_sync_thread: Optional[threading.Thread] = None
        self._order_sync_stop_event = threading.Event()

        # 状态变更回调
        self._on_state_change_callbacks: List[Callable] = []

        # 在线计时起点
        self._connected_at: Optional[float] = None
        self._disconnected_at: Optional[float] = None

    # ── 属性 ──────────────────────────────────────────────────────

    @property
    def state(self) -> GatewayState:
        """当前连接状态"""
        return self._state

    @property
    def connected(self) -> bool:
        """是否已连接（含 LOGGED_IN）"""
        return self._state in (GatewayState.CONNECTED, GatewayState.LOGGED_IN)

    @property
    def logged_in(self) -> bool:
        """是否已登录"""
        return self._state == GatewayState.LOGGED_IN

    @property
    def stats(self) -> ConnectionStats:
        """连接统计（只读副本）"""
        return self._stats

    @property
    def config(self) -> GatewayConfig:
        """Gateway 配置"""
        return self._config

    # ── 状态机 ─────────────────────────────────────────────────────

    def _transition(self, target: GatewayState) -> bool:
        """内部状态转换，线程安全

        Args:
            target: 目标状态

        Returns:
            True 转换成功，False 转换失败（非法转换）
        """
        with self._lock:
            allowed = _VALID_TRANSITIONS.get(self._state, set())
            if target not in allowed:
                logger.warning(
                    "Gateway 状态转换被拒绝: %s → %s",
                    self._state.value, target.value,
                )
                return False
            old = self._state
            self._state = target
            logger.info("Gateway 状态转换: %s → %s", old.value, target.value)

            # 更新统计
            now = time.time()
            if target == GatewayState.CONNECTED:
                self._stats.connect_count += 1
                self._stats.last_connect_time = now
                if self._disconnected_at is not None:
                    self._stats.total_downtime += now - self._disconnected_at
                self._connected_at = now
                self._disconnected_at = None
            elif target == GatewayState.LOGGED_IN:
                self._stats.last_connect_time = now

            elif target == GatewayState.DISCONNECTED:
                self._stats.disconnect_count += 1
                self._stats.last_disconnect_time = now
                if self._connected_at is not None:
                    self._stats.total_uptime += now - self._connected_at
                self._disconnected_at = now
                self._connected_at = None

            elif target == GatewayState.RECONNECTING:
                self._stats.reconnect_count += 1

            # 通知回调
            for cb in self._on_state_change_callbacks:
                try:
                    cb(old, target)
                except Exception as e:
                    logger.warning("状态变更回调异常: %s", e)

            return True

    # ── 生命周期管理 ────────────────────────────────────────────────

    def connect(self) -> bool:
        """连接券商网关

        执行流程：CONNECTING → _do_connect() → CONNECTED → _do_login() → LOGGED_IN

        Returns:
            True 连接并登录成功，False 连接或登录失败
        """
        if not self._transition(GatewayState.CONNECTING):
            logger.warning("Gateway 无法进入 CONNECTING 状态，当前: %s", self._state.value)
            return False

        try:
            ok = self._do_connect()
            if not ok:
                self._transition(GatewayState.ERROR)
                return False

            if not self._transition(GatewayState.CONNECTED):
                return False
            self.emit_event(GatewayEvent.CONNECTED)

            # 尝试登录
            login_ok = self._do_login()
            if login_ok:
                if not self._transition(GatewayState.LOGGED_IN):
                    return False
                self.emit_event(GatewayEvent.LOGIN_SUCCESS)

                # 启动后台线程
                self._start_heartbeat_loop()
                self._start_order_sync_loop()
                return True
            else:
                logger.warning("Gateway 登录失败，连接已建立但未登录")
                self.emit_event(GatewayEvent.LOGIN_FAILED, {"reason": "login failed"})
                return True  # 连接成功但登录失败

        except Exception as e:
            logger.error("Gateway 连接异常: %s", e, exc_info=True)
            self._stats.last_error = str(e)
            self._transition(GatewayState.ERROR)
            self.emit_event(GatewayEvent.ERROR, {"reason": str(e)})

            # 启动自动重连
            if self._config.reconnect_enabled:
                self._start_reconnect_loop()
            return False

    def disconnect(self) -> None:
        """断开券商网关

        停止所有后台线程，执行登出和断开操作。
        """
        # 停止后台线程
        self._stop_reconnect_loop()
        self._stop_heartbeat_loop()
        self._stop_order_sync_loop()

        try:
            self._do_logout()
        except Exception as e:
            logger.warning("Gateway 登出异常: %s", e)

        try:
            self._do_disconnect()
        except Exception as e:
            logger.warning("Gateway 断开异常: %s", e)

        self._transition(GatewayState.DISCONNECTED)
        self.emit_event(GatewayEvent.DISCONNECTED)

    def reconnect(self) -> bool:
        """手动重连

        先断开，再重新连接。

        Returns:
            True 重连成功，False 重连失败
        """
        logger.info("Gateway 手动重连")
        self.disconnect()
        time.sleep(0.5)
        return self.connect()

    # ── Broker 接口实现（子类不应覆盖） ───────────────────────────

    def place_order(self, order: Order, bar=None) -> Optional[TradeData]:
        """统一下单流程

        流程：校验连接 → _do_place_order → 记录日志 → 更新缓存

        Args:
            order: 订单
            bar: K 线数据（可选）

        Returns:
            TradeData 成交记录，失败返回 None
        """
        # 1. 连接状态校验
        if not self.connected:
            logger.error("Gateway 未连接，无法下单")
            self._log_order(order, "REJECTED", reason="gateway not connected")
            order.update_status(EventType.ORDER_REJECTED.value)
            return None

        # 2. 基本校验
        if order.quantity <= 0:
            logger.error("订单数量无效: %s", order.quantity)
            self._log_order(order, "REJECTED", reason="invalid quantity")
            order.update_status(EventType.ORDER_REJECTED.value)
            return None

        # 3. 调用子类实现
        try:
            order.update_status(EventType.ORDER_SUBMITTED.value)
            result = self._do_place_order(order)
            if result is None:
                # 子类返回 None 表示不支持或失败
                self._log_order(order, "REJECTED", reason="broker does not support order")
                order.update_status(EventType.ORDER_REJECTED.value)
                return None

            order_id, success = result
            if success:
                self._open_orders[order.order_id] = order
                self._log_order(order, "SUBMITTED")
                self.emit_event(GatewayEvent.ORDER_SUBMITTED, {
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "price": order.price,
                    "quantity": order.quantity,
                })

                # 返回占位 TradeData（实际成交由回调/同步更新）
                trade = TradeData(
                    trade_id=f"{order.order_id}_submitted",
                    order_id=order.order_id,
                    symbol=order.symbol,
                    side=order.side.value,
                    price=order.price,
                    quantity=order.quantity,
                )
                return trade
            else:
                self._log_order(order, "REJECTED", reason="broker rejected order")
                order.update_status(EventType.ORDER_REJECTED.value)
                self.emit_event(GatewayEvent.ORDER_REJECTED, {
                    "order_id": order.order_id,
                    "reason": "broker rejected",
                })
                return None

        except Exception as e:
            logger.error("下单异常: %s", e, exc_info=True)
            self._stats.last_error = str(e)
            self._log_order(order, "REJECTED", reason=str(e))
            order.update_status(EventType.ORDER_REJECTED.value)
            self.emit_event(GatewayEvent.ERROR, {"reason": str(e)})
            return None

    def cancel_order(self, order: Order) -> bool:
        """统一撤单流程

        流程：校验 → _do_cancel_order → 更新缓存 → 记录日志

        Args:
            order: 要撤销的订单

        Returns:
            True 撤单成功，False 撤单失败
        """
        if not self.connected:
            logger.error("Gateway 未连接，无法撤单")
            return False

        if order.order_id not in self._open_orders:
            logger.warning("订单 %s 不在已提交列表中", order.order_id)
            return False

        try:
            success = self._do_cancel_order(order)
            if success:
                self._open_orders.pop(order.order_id, None)
                order.update_status(EventType.ORDER_CANCELLED.value)
                self._log_order(order, "CANCELLED", reason="user cancel")
                self.emit_event(GatewayEvent.ORDER_CANCELLED, {
                    "order_id": order.order_id,
                })
                return True
            else:
                logger.warning("撤单失败: %s", order.order_id)
                return False
        except Exception as e:
            logger.error("撤单异常: %s", e, exc_info=True)
            self._stats.last_error = str(e)
            return False

    def get_positions(self, portfolio=None) -> Dict[str, Any]:
        """统一持仓查询

        优先调用子类 _do_query_positions()，失败返回空字典。
        """
        if not self.connected:
            return {}
        try:
            return self._do_query_positions()
        except Exception as e:
            logger.error("查询持仓异常: %s", e, exc_info=True)
            return {}

    def get_balance(self, account=None) -> Dict[str, Any]:
        """统一余额查询

        优先调用子类 _do_query_balance()，失败返回空字典。
        """
        if not self.connected:
            return {}
        try:
            return self._do_query_balance()
        except Exception as e:
            logger.error("查询余额异常: %s", e, exc_info=True)
            return {}

    def get_history(self, symbol: str, bar_count: int, data_feeds=None) -> list:
        """获取历史K线

        BaseGateway 不维护K线数据，返回空列表。
        子类可覆盖此方法以提供行情数据。
        """
        return []

    # ── 子类需实现的抽象方法 ─────────────────────────────────────────

    @abstractmethod
    def _do_connect(self) -> bool:
        """执行实际连接（子类必须实现）

        Returns:
            True 连接成功
        """
        ...

    @abstractmethod
    def _do_disconnect(self) -> None:
        """执行实际断开（子类必须实现）"""
        ...

    @abstractmethod
    def _do_login(self) -> bool:
        """执行登录认证（子类必须实现）

        Returns:
            True 登录成功
        """
        ...

    @abstractmethod
    def _do_heartbeat(self) -> None:
        """发送心跳包（子类必须实现）"""
        ...

    # ── 可选覆盖的方法（有默认行为） ───────────────────────────────

    def _do_logout(self) -> None:
        """执行登出（子类可选覆盖）"""
        pass

    def _do_place_order(self, order: Order) -> Optional[tuple]:
        """执行实际下单（子类可选覆盖）

        Returns:
            (order_id: str, success: bool) 元组，或 None 表示不支持
        """
        logger.warning("子类未实现 _do_place_order，下单将被拒绝")
        return None

    def _do_cancel_order(self, order: Order) -> bool:
        """执行实际撤单（子类可选覆盖）

        Returns:
            True 撤单成功
        """
        logger.warning("子类未实现 _do_cancel_order")
        return False

    def _do_query_positions(self) -> dict:
        """查询持仓（子类可选覆盖）

        Returns:
            持仓数据字典
        """
        return {}

    def _do_query_balance(self) -> dict:
        """查询余额（子类可选覆盖）

        Returns:
            余额数据字典
        """
        return {}

    def _do_query_orders(self) -> list:
        """查询挂单状态（子类可选覆盖）

        Returns:
            订单状态列表
        """
        return []

    # ── 事件系统 ───────────────────────────────────────────────────

    def register_event_handler(self, event: GatewayEvent, handler: Callable) -> None:
        """注册事件处理器

        Args:
            event: 事件类型
            handler: 回调函数，签名 handler(data: dict) -> None
        """
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def unregister_event_handler(self, event: GatewayEvent, handler: Callable) -> None:
        """注销事件处理器"""
        if event in self._event_handlers:
            self._event_handlers[event] = [
                h for h in self._event_handlers[event] if h != handler
            ]

    def emit_event(self, event: GatewayEvent, data: dict = None) -> None:
        """触发事件

        Args:
            event: 事件类型
            data: 事件数据
        """
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                handler(data or {})
            except Exception as e:
                logger.warning("事件处理器异常 [%s]: %s", event.value, e)

    def on_state_change(self, callback: Callable) -> None:
        """注册状态变更回调

        Args:
            callback: 回调函数，签名 callback(old_state: GatewayState, new_state: GatewayState)
        """
        self._on_state_change_callbacks.append(callback)

    # ── 心跳保活 ───────────────────────────────────────────────────

    def _start_heartbeat_loop(self) -> None:
        """启动心跳循环线程"""
        if not self._config.heartbeat_enabled:
            return
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return

        self._heartbeat_stop_event.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"{self.__class__.__name__}-heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()
        logger.info("心跳保活线程已启动，间隔 %.1f 秒", self._config.heartbeat_interval)

    def _stop_heartbeat_loop(self) -> None:
        """停止心跳循环线程"""
        self._heartbeat_stop_event.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=5.0)
            logger.info("心跳保活线程已停止")

    def _heartbeat_loop(self) -> None:
        """心跳循环主体"""
        interval = self._config.heartbeat_interval
        timeout = self._config.heartbeat_timeout
        while not self._heartbeat_stop_event.is_set():
            try:
                self._heartbeat_stop_event.wait(interval)
                if self._heartbeat_stop_event.is_set():
                    break

                if not self.connected:
                    continue

                self._do_heartbeat()
                self._last_heartbeat_time = time.time()

                # 检查心跳超时
                if (self._last_heartbeat_time is not None
                        and time.time() - self._last_heartbeat_time > timeout):
                    logger.warning("心跳超时 %.1f 秒，触发重连", timeout)
                    self._stats.last_error = "heartbeat timeout"
                    self._transition(GatewayState.ERROR)
                    if self._config.reconnect_enabled:
                        self._start_reconnect_loop()

            except Exception as e:
                logger.error("心跳异常: %s", e, exc_info=True)
                self._stats.last_error = str(e)
                self._transition(GatewayState.ERROR)
                if self._config.reconnect_enabled:
                    self._start_reconnect_loop()

    # ── 断线重连 ───────────────────────────────────────────────────

    def _start_reconnect_loop(self) -> None:
        """启动重连循环线程"""
        if not self._config.reconnect_enabled:
            return
        if self._reconnect_thread is not None and self._reconnect_thread.is_alive():
            return

        self._reconnect_stop_event.clear()
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop,
            name=f"{self.__class__.__name__}-reconnect",
            daemon=True,
        )
        self._reconnect_thread.start()
        logger.info("自动重连线程已启动")

    def _stop_reconnect_loop(self) -> None:
        """停止重连循环线程"""
        self._reconnect_stop_event.set()
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            self._reconnect_thread.join(timeout=max(self._config.reconnect_max_delay, 5.0) + 2.0)
            logger.info("自动重连线程已停止")
        self._reconnect_attempt = 0

    def _reconnect_loop(self) -> None:
        """重连循环主体 — 指数退避"""
        cfg = self._config
        self._reconnect_attempt = 0

        while not self._reconnect_stop_event.is_set():
            # 检查重试限制
            if cfg.reconnect_max_retries > 0 and self._reconnect_attempt >= cfg.reconnect_max_retries:
                logger.error("重连次数已达上限 %d，停止重连", cfg.reconnect_max_retries)
                self._transition(GatewayState.ERROR)
                self._stats.last_error = f"max retries ({cfg.reconnect_max_retries}) exceeded"
                break

            # 计算退避延迟
            delay = min(
                cfg.reconnect_initial_delay * (cfg.reconnect_backoff_factor ** self._reconnect_attempt),
                cfg.reconnect_max_delay,
            )
            self._reconnect_attempt += 1
            logger.info("第 %d 次重连，等待 %.1f 秒...", self._reconnect_attempt, delay)

            # 等待（可被停止信号中断）
            if self._reconnect_stop_event.wait(delay):
                break

            # 执行重连
            try:
                self._transition(GatewayState.RECONNECTING)

                ok = self._do_connect()
                if ok:
                    login_ok = self._do_login()
                    if login_ok:
                        self._transition(GatewayState.LOGGED_IN)
                        self.emit_event(GatewayEvent.CONNECTED)
                        self.emit_event(GatewayEvent.LOGIN_SUCCESS)
                        self._start_heartbeat_loop()
                        self._start_order_sync_loop()
                        logger.info("重连成功（第 %d 次尝试）", self._reconnect_attempt)
                        break
                    else:
                        logger.warning("重连后登录失败")
                        self._transition(GatewayState.ERROR)
                        self.emit_event(GatewayEvent.LOGIN_FAILED, {"reason": "reconnect login failed"})

                else:
                    logger.warning("第 %d 次重连失败", self._reconnect_attempt)
                    self._transition(GatewayState.ERROR)

            except Exception as e:
                logger.error("重连异常: %s", e, exc_info=True)
                self._stats.last_error = str(e)
                self._transition(GatewayState.ERROR)
                self.emit_event(GatewayEvent.ERROR, {"reason": str(e)})

    # ── 订单状态同步 ───────────────────────────────────────────────

    def _start_order_sync_loop(self) -> None:
        """启动订单同步循环线程"""
        if not self._config.order_sync_enabled:
            return
        if self._order_sync_thread is not None and self._order_sync_thread.is_alive():
            return

        self._order_sync_stop_event.clear()
        self._order_sync_thread = threading.Thread(
            target=self._order_sync_loop,
            name=f"{self.__class__.__name__}-order-sync",
            daemon=True,
        )
        self._order_sync_thread.start()
        logger.info("订单同步线程已启动，间隔 %.1f 秒", self._config.order_sync_interval)

    def _stop_order_sync_loop(self) -> None:
        """停止订单同步循环线程"""
        self._order_sync_stop_event.set()
        if self._order_sync_thread and self._order_sync_thread.is_alive():
            self._order_sync_thread.join(timeout=10.0)
            logger.info("订单同步线程已停止")

    def _order_sync_loop(self) -> None:
        """订单同步循环主体"""
        interval = self._config.order_sync_interval
        while not self._order_sync_stop_event.is_set():
            try:
                self._order_sync_stop_event.wait(interval)
                if self._order_sync_stop_event.is_set():
                    break

                if not self.connected:
                    continue

                self._sync_order_status()

            except Exception as e:
                logger.error("订单同步异常: %s", e, exc_info=True)

    def _sync_order_status(self) -> None:
        """同步订单状态

        查询子类的 _do_query_orders()，更新本地缓存的订单状态。
        """
        try:
            remote_orders = self._do_query_orders()
            if not remote_orders:
                return

            for remote in remote_orders:
                order_id = remote.get("order_id", "")
                status = remote.get("status", "")

                if order_id in self._open_orders:
                    local_order = self._open_orders[order_id]
                    if local_order.status != status:
                        old_status = local_order.status
                        local_order.update_status(status)
                        self._log_order(local_order, status, reason="order sync")

                        # 根据状态触发事件
                        if status == EventType.ORDER_FILLED.value:
                            self.emit_event(GatewayEvent.ORDER_FILLED, {
                                "order_id": order_id,
                                "old_status": old_status,
                            })
                            self._open_orders.pop(order_id, None)
                        elif status == EventType.ORDER_PARTIAL_FILL.value:
                            self.emit_event(GatewayEvent.ORDER_PARTIAL_FILL, {
                                "order_id": order_id,
                                "old_status": old_status,
                            })
                        elif status == EventType.ORDER_CANCELLED.value:
                            self.emit_event(GatewayEvent.ORDER_CANCELLED, {
                                "order_id": order_id,
                            })
                            self._open_orders.pop(order_id, None)
                        elif status == EventType.ORDER_REJECTED.value:
                            self.emit_event(GatewayEvent.ORDER_REJECTED, {
                                "order_id": order_id,
                            })
                            self._open_orders.pop(order_id, None)

        except Exception as e:
            logger.error("订单同步查询异常: %s", e, exc_info=True)

    # ── 日志审计 ───────────────────────────────────────────────────

    def _log_order(self, order, status: str, reason: str = "") -> OrderAuditLog:
        """将订单事件写入审计日志

        Args:
            order: 订单对象
            status: 状态描述
            reason: 原因/备注

        Returns:
            OrderAuditLog 日志条目
        """
        entry = OrderAuditLog(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side.value if hasattr(order.side, "value") else str(order.side),
            price=order.price,
            quantity=order.quantity,
            status=status,
            timestamp=datetime.now(),
            reason=reason,
        )
        self._order_log.append(entry)
        return entry

    @property
    def order_audit_log(self) -> List[OrderAuditLog]:
        """返回审计日志副本"""
        return self._order_log.copy()

    # ── 清理 ──────────────────────────────────────────────────────

    def __del__(self):
        """析构时确保停止所有后台线程"""
        try:
            self.disconnect()
        except Exception:
            pass

    def __repr__(self) -> str:
        return (
            f"BaseGateway(state={self._state.value}, "
            f"orders={len(self._open_orders)}, "
            f"stats={self._stats})"
        )
