# -*- coding: utf-8 -*-
"""XTP 券商 Broker 实现 — 中泰证券 XTP 极速交易系统

XTP (eXtreme Transaction Platform) 是中泰证券提供的极速交易系统，
支持 A 股、基金、债券等品种的极速交易。

SDK 安装:
    pip install vnpy_xtp          # VeighNa 框架封装（推荐）
    或 pip install openctp         # openctp XTP 兼容接口

如未安装，将降级为模拟模式。
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.events import EventType as OrderStatus, EventType
from stockquant.models.trade import TradeData
from stockquant.execution.gateway_base import (
    BaseGateway,
    GatewayConfig,
    GatewayEvent,
    GatewayState,
)

logger = logging.getLogger("stockquant.execution.xtp")

# XTP SDK 可选导入
_xtp_api = None
XTP_AVAILABLE = False

# vnpy_xtp (pip install vnpy_xtp，推荐)
try:
    from vnpy_xtp import XtpGateway as _XtpGateway  # noqa: F401 — 可选依赖
    _xtp_api = _XtpGateway
    XTP_AVAILABLE = True
    logger.info("XTP SDK (vnpy_xtp) 已加载")
except ImportError:
    logger.info("XTP SDK 未安装，XTP Broker 将以模拟模式运行")


class XTPBroker(BaseGateway):
    """XTP 券商 Broker — 中泰证券 XTP 极速交易系统

    通过 BaseGateway 统一生命周期管理，使用 XTP SDK 连接中泰证券交易网关，
    支持 A 股实盘交易。

    参数:
        config: GatewayConfig 配置
        user: XTP 资金账号
        password: XTP 交易密码
        app_id: XTP 应用 ID（由中泰证券分配）
        client_id: XTP 客户端 ID（0-99，同一 app_id 下唯一）
        server_addr: XTP 交易服务器地址 (ip:port)
        software_key: XTP 软件密钥
        _mock_api: 测试用 mock SDK

    如 XTP SDK 未安装，所有操作将降级为模拟模式并输出警告日志。
    """

    api = "xtp"

    # XTP 常量
    XTP_SIDE_BUY = 1
    XTP_SIDE_SELL = 2
    XTP_PRICE_LIMIT = 1
    XTP_PRICE_MARKET = 5
    XTP_PRICE_BEST5_OR_CANCEL = 6  # 最优五档即时成交剩余撤销

    def __init__(
        self,
        config: GatewayConfig = None,
        user: str = "",
        password: str = "",
        app_id: int = 0,
        client_id: int = 0,
        server_addr: str = "",
        software_key: str = "",
        _mock_api: Any = None,
    ):
        super().__init__(config=config)

        self._user = user
        self._password = password
        self._app_id = app_id
        self._client_id = client_id
        self._server_addr = server_addr
        self._software_key = software_key
        self._xtp_api = _mock_api  # 测试用 mock SDK（可替换真实 SDK）
        self._spi = None
        self._session_id = 0
        self._xtp_order_map: Dict[int, str] = {}  # xtp_order_id -> order_id
        self._positions_cache: Dict[str, Any] = {}
        self._asset_cache: Dict[str, Any] = {}

        # Mock SDK 模式：注入 _mock_api 时直接设为 LOGGED_IN 状态
        if self._xtp_api is not None and user and server_addr:
            self._state = GatewayState.LOGGED_IN
            self._session_id = 1
            logger.info("XTP Broker 使用 Mock SDK，连接成功")
        elif XTP_AVAILABLE and user and server_addr:
            self.connect()

    # ── 抽象方法实现 ─────────────────────────────────────────────────

    def _do_connect(self) -> bool:
        """执行 XTP 连接

        创建 TraderApi 实例，注册 SPI 回调，设置前置机地址，
        启动连接并等待回调完成。

        Returns:
            True 连接成功，False 连接失败或 SDK 不可用
        """
        if self._xtp_api is not None:
            # Mock SDK 模式，已在 __init__ 中处理
            return True
        if not XTP_AVAILABLE:
            logger.warning("XTP SDK 未安装，无法连接 XTP 网关，降级为模拟模式")
            return False

        try:
            # 创建 TraderApi 实例
            self._xtp_api = _xtp_api.TraderApi.CreateTraderApi(
                self._client_id, os.path.join(os.getcwd(), "xtp_log")
            )

            # 注册回调 SPI
            self._spi = _XTPTaderSpi(self)
            self._xtp_api.RegisterSpi(self._spi)

            # 设置软件密钥
            if self._software_key:
                self._xtp_api.SetSoftwareKey(self._software_key)

            # 注册前置机地址
            if self._server_addr:
                ip, port = self._parse_addr(self._server_addr)
                self._xtp_api.RegisterFront(ip, int(port))

            # 订阅公有/私有流
            try:
                self._xtp_api.SubscribePublicTopic(0)  # XTP_TERT_RESTART
                self._xtp_api.SubscribePrivateTopic(0)
            except Exception:
                pass

            # 启动连接
            self._xtp_api.Init()

            # 等待 SPI OnFrontConnected 回调（最多 10 秒）
            deadline = time.time() + self._config.connect_timeout
            while time.time() < deadline:
                if self._state in (GatewayState.CONNECTED, GatewayState.LOGGED_IN):
                    return True
                time.sleep(0.1)

            logger.warning("XTP 连接超时")
            return False

        except Exception as e:
            logger.warning("XTP 连接失败: %s，降级为模拟模式", e)
            return False

    def _do_disconnect(self) -> None:
        """执行 XTP 断开连接

        释放 SDK 资源并清理内部状态。
        """
        if self._xtp_api:
            try:
                self._xtp_api.Release()
            except Exception as e:
                logger.warning("XTP Release 异常: %s", e)
            finally:
                self._xtp_api = None
                self._spi = None

    def _do_login(self) -> bool:
        """执行 XTP 登录认证

        Returns:
            True 登录成功（session_id > 0），False 登录失败
        """
        if self._xtp_api is not None and not hasattr(self._xtp_api, 'Login'):
            # Mock SDK 模式，已在 __init__ 中设为 LOGGED_IN
            return True
        if not self._xtp_api:
            return False

        try:
            self._session_id = self._xtp_api.Login(
                self._user, self._password, self._app_id
            )

            if self._session_id > 0:
                logger.info(
                    "XTP 登录成功: user=%s, session_id=%s, client_id=%s",
                    self._user, self._session_id, self._client_id,
                )
                return True
            else:
                logger.warning("XTP 登录失败: session_id=%s", self._session_id)
                return False

        except Exception as e:
            logger.warning("XTP 登录异常: %s", e)
            return False

    def _do_heartbeat(self) -> None:
        """XTP 心跳保活

        XTP 没有独立的心跳接口，通过查询资产（QueryAsset）实现心跳。
        """
        if self._xtp_api and hasattr(self._xtp_api, 'QueryAsset'):
            try:
                self._xtp_api.QueryAsset(self._session_id)
            except Exception as e:
                logger.warning("XTP 心跳（QueryAsset）异常: %s", e)

    # ── 可选方法覆盖 ─────────────────────────────────────────────────

    def _do_place_order(self, order: Order) -> Optional[tuple]:
        """通过 XTP 下单

        将 Order 模型转换为 XTP 格式并提交。
        包含 A 股 100 股整数倍校验。

        Args:
            order: 订单对象

        Returns:
            (xtp_order_id_str: str, True) 成功
            (xtp_order_id_str: str, False) 失败
        """
        # A 股 100 股整数倍校验
        if order.quantity % 100 != 0:
            return (f"0", False)

        # XTP 侧单方向映射
        side = self.XTP_SIDE_BUY if order.side == OrderSide.BUY else self.XTP_SIDE_SELL

        # XTP 订单类型映射
        if order.order_type == OrderType.LIMIT:
            price_type = self.XTP_PRICE_LIMIT
        elif order.order_type == OrderType.MARKET:
            price_type = self.XTP_PRICE_MARKET
        else:
            price_type = self.XTP_PRICE_BEST5_OR_CANCEL

        # 构建 XTP 订单请求
        try:
            if self._xtp_api is not None and hasattr(self._xtp_api, 'MockXTPOrderInsertInfo'):
                req = self._xtp_api.MockXTPOrderInsertInfo()
            else:
                req = _xtp_api.XTPOrderInsertInfo()
            req.ticker = order.symbol
            req.side = side
            req.price_type = price_type
            req.quantity = int(order.quantity)
            req.price = float(order.price)
        except Exception as e:
            logger.warning("构建 XTP 订单请求失败: %s", e)
            return (str(0), False)

        # 提交订单
        try:
            if self._xtp_api is not None and hasattr(self._xtp_api, 'InsertOrder'):
                # Mock SDK，调用 InsertOrder
                xtp_order_id = self._xtp_api.InsertOrder(req, self._session_id)
            else:
                # 降级：返回失败
                xtp_order_id = -1

            if xtp_order_id > 0:
                # 下单成功，记录 xtp_order_id -> order_id 映射
                with self._lock:
                    self._xtp_order_map[xtp_order_id] = order.order_id
                return (str(xtp_order_id), True)
            else:
                return (str(xtp_order_id), False)

        except Exception as e:
            logger.warning("XTP InsertOrder 异常: %s", e)
            return (str(0), False)

    def _do_cancel_order(self, order: Order) -> bool:
        """通过 XTP 撤单

        Args:
            order: 要撤销的订单

        Returns:
            True 撤单请求已发送，False 撤单失败
        """
        if not self._xtp_api:
            return False

        try:
            # 查找 XTP 订单 ID
            xtp_order_id = None
            with self._lock:
                for xid, oid in self._xtp_order_map.items():
                    if oid == order.order_id:
                        xtp_order_id = xid
                        break

            if xtp_order_id is not None:
                self._xtp_api.CancelOrder(xtp_order_id, self._session_id)
                return True
            else:
                logger.warning("未找到订单 %s 对应的 XTP 订单 ID", order.order_id)
                return False

        except Exception as e:
            logger.warning("XTP 撤单异常: %s", e)
            return False

    def _do_query_positions(self) -> dict:
        """查询 XTP 持仓

        Returns:
            持仓字典 {symbol: {"quantity": int, "price": float, ...}}
        """
        if self._xtp_api and hasattr(self._xtp_api, 'QueryPositions'):
            try:
                positions = self._xtp_api.QueryPositions(self._session_id)
                result = {}
                for p in positions:
                    result[p.ticker] = {
                        "quantity": p.total_qty,
                        "price": p.avg_price,
                        "market_value": p.market_value,
                        "unrealized_pnl": p.unrealized_pnl,
                        "exchange": p.exchange_id,
                    }
                with self._lock:
                    self._positions_cache = result
                return result
            except Exception as e:
                logger.warning("XTP 查询持仓失败: %s", e)
                return self._positions_cache
        return {}

    def _do_query_balance(self) -> dict:
        """查询 XTP 账户余额

        Returns:
            余额字典 {"live": True, "api": "xtp", "cash": float, ...}
        """
        if self._xtp_api and hasattr(self._xtp_api, 'QueryAsset'):
            try:
                asset = self._xtp_api.QueryAsset(self._session_id)
                result = {
                    "live": True,
                    "api": "xtp",
                    "cash": asset.buying_power,
                    "frozen": asset.frozen_cash,
                    "equity": asset.total_asset,
                    "available": asset.buying_power,
                    "market_value": asset.market_value,
                }
                with self._lock:
                    self._asset_cache = result
                return result
            except Exception as e:
                logger.warning("XTP 查询余额失败: %s", e)
                return self._asset_cache
        return {"live": True, "api": "xtp", "cash": 0, "frozen": 0, "equity": 0}

    def _do_query_orders(self) -> list:
        """通过 XTP SDK 查询挂单

        Returns:
            订单状态列表，每项包含 order_id 和 status 字段
        """
        if not self._xtp_api or not hasattr(self._xtp_api, 'QueryOrders'):
            return []

        try:
            orders = self._xtp_api.QueryOrders(self._session_id)
            result = []
            for o in orders:
                # 将 XTP 订单 ID 映射回内部 order_id
                xtp_id = o.order_xtp_id
                with self._lock:
                    internal_id = self._xtp_order_map.get(xtp_id)

                if internal_id:
                    # XTP 订单状态映射
                    status_map = {
                        1: OrderStatus.ORDER_SUBMITTED.value,   # XTP_ORDER_STATUS_INIT
                        2: OrderStatus.ORDER_FILLED.value,      # XTP_ORDER_STATUS_ALLTRADED
                        3: OrderStatus.ORDER_PARTIAL_FILL.value,  # XTP_ORDER_STATUS_PARTTRADED
                        4: OrderStatus.ORDER_CANCELLED.value,    # XTP_ORDER_STATUS_CANCELED
                        5: OrderStatus.ORDER_REJECTED.value,     # XTP_ORDER_STATUS_REJECTED
                        6: OrderStatus.ORDER_PARTIAL_FILL.value,  # XTP_ORDER_STATUS_PARTTRADEDPARTCANCELED
                    }
                    xtp_status = getattr(o, 'order_status', 0)
                    result.append({
                        "order_id": internal_id,
                        "status": status_map.get(xtp_status, OrderStatus.ORDER_SUBMITTED.value),
                        "xtp_status": xtp_status,
                    })
            return result
        except Exception as e:
            logger.warning("XTP 查询挂单失败: %s", e)
            return []

    def _do_logout(self) -> None:
        """执行 XTP 登出"""
        if self._xtp_api and hasattr(self._xtp_api, 'Logout'):
            try:
                self._xtp_api.Logout(self._session_id)
                logger.info("XTP 已登出: user=%s", self._user)
            except Exception as e:
                logger.warning("XTP 登出异常: %s", e)

    # ── 工具方法 ────────────────────────────────────────────────────

    @staticmethod
    def _parse_addr(addr: str) -> tuple:
        """解析 ip:port 格式的服务器地址

        Args:
            addr: 服务器地址字符串

        Returns:
            (ip: str, port: str) 元组
        """
        parts = addr.rsplit(":", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return addr, "6002"  # XTP 默认端口

    def __repr__(self) -> str:
        return (
            f"XTPBroker(state={self._state.value}, "
            f"user={self._user}, "
            f"session={self._session_id}, "
            f"orders={len(self._open_orders)})"
        )


class _XTPTaderSpi:
    """XTP 交易回调 SPI — 处理异步回调事件

    通过 BaseGateway 的事件系统（emit_event）将 XTP 异步回调
    转换为统一的 GatewayEvent 事件，交由上层处理。
    """

    def __init__(self, broker: XTPBroker):
        self._broker = broker

    def OnFrontConnected(self):
        """连接成功回调 — 转换状态为 CONNECTED"""
        # _do_connect 中通过轮询 self._state 判断连接成功，
        # 此处由 BaseGateway 的 connect() 方法负责状态转换。
        logger.info("XTP 前置连接成功")

    def OnFrontDisconnected(self, reason: int):
        """连接断开回调 — 触发 BaseGateway 错误状态"""
        logger.warning("XTP 前置连接断开: reason=%s", reason)
        self._broker.emit_event(GatewayEvent.DISCONNECTED, {"reason": reason})

    def OnLogin(self, session_id: int, error_info: Any):
        """登录回调"""
        if error_info and hasattr(error_info, 'error_id') and error_info.error_id != 0:
            logger.error("XTP 登录失败: %s", error_info.error_msg)
            self._broker.emit_event(
                GatewayEvent.LOGIN_FAILED,
                {"reason": error_info.error_msg},
            )
        else:
            self._broker._session_id = session_id
            logger.info("XTP 登录成功: session_id=%s", session_id)

    def OnLogout(self, session_id: int, error_info: Any):
        """登出回调"""
        logger.info("XTP 已登出: session_id=%s", session_id)
        self._broker.emit_event(GatewayEvent.DISCONNECTED, {"reason": "logout"})

    def OnOrderEvent(self, order_info: Any, error_info: Any, session_id: int):
        """订单状态变更回调 — 通过 BaseGateway 事件系统分发"""
        try:
            xtp_order_id = order_info.order_xtp_id
            with self._broker._lock:
                order_id = self._broker._xtp_order_map.get(xtp_order_id)

            if not order_id:
                return

            # XTP 订单状态映射
            status_map = {
                1: (OrderStatus.ORDER_SUBMITTED.value, GatewayEvent.ORDER_SUBMITTED),
                2: (OrderStatus.ORDER_FILLED.value, GatewayEvent.ORDER_FILLED),
                3: (OrderStatus.ORDER_PARTIAL_FILL.value, GatewayEvent.ORDER_PARTIAL_FILL),
                4: (OrderStatus.ORDER_CANCELLED.value, GatewayEvent.ORDER_CANCELLED),
                5: (OrderStatus.ORDER_REJECTED.value, GatewayEvent.ORDER_REJECTED),
                6: (OrderStatus.ORDER_PARTIAL_FILL.value, GatewayEvent.ORDER_PARTIAL_FILL),
            }
            xtp_status = getattr(order_info, 'order_status', 0)
            mapped = status_map.get(xtp_status)
            if not mapped:
                logger.warning("未知 XTP 订单状态: %s", xtp_status)
                return

            new_status, event_type = mapped

            # 更新本地缓存中的订单状态
            local_order = self._broker._open_orders.get(order_id)
            if local_order:
                local_order.update_status(new_status)

                # 终态事件：从挂单列表移除
                if event_type in (
                    GatewayEvent.ORDER_FILLED,
                    GatewayEvent.ORDER_CANCELLED,
                    GatewayEvent.ORDER_REJECTED,
                ):
                    self._broker._open_orders.pop(order_id, None)

            # 通过 BaseGateway 事件系统通知上层
            self._broker.emit_event(event_type, {
                "order_id": order_id,
                "xtp_order_id": xtp_order_id,
                "xtp_status": xtp_status,
            })

        except Exception as e:
            logger.error("XTP OnOrderEvent 处理异常: %s", e)

    def OnTradeEvent(self, trade_info: Any, session_id: int):
        """成交回调 — 通过 BaseGateway TRADE 事件通知"""
        try:
            xtp_order_id = trade_info.order_xtp_id
            with self._broker._lock:
                order_id = self._broker._xtp_order_map.get(xtp_order_id)

            if not order_id:
                return

            trade_data = {
                "trade_id": trade_info.exec_id,
                "order_id": order_id,
                "price": trade_info.price,
                "quantity": trade_info.quantity,
                "trade_time": trade_info.trade_time,
            }

            self._broker.emit_event(GatewayEvent.TRADE, trade_data)
            logger.info(
                "XTP 成交: order_id=%s, price=%.2f, qty=%d",
                order_id, trade_info.price, trade_info.quantity,
            )

        except Exception as e:
            logger.error("XTP OnTradeEvent 处理异常: %s", e)

    def OnCancelOrderError(self, cancel_info: Any, error_info: Any, session_id: int):
        """撤单失败回调"""
        logger.warning("XTP 撤单失败: %s", getattr(error_info, 'error_msg', str(error_info)))
        self._broker.emit_event(GatewayEvent.ERROR, {
            "reason": f"cancel failed: {getattr(error_info, 'error_msg', str(error_info))}",
        })

    def OnQueryPosition(self, position_info: Any, error_info: Any, request_id: int, is_last: bool):
        """持仓查询回调（同步模式，忽略异步回调）"""
        pass

    def OnQueryAsset(self, asset_info: Any, error_info: Any, request_id: int, is_last: bool):
        """资产查询回调（同步模式，忽略异步回调）"""
        pass
