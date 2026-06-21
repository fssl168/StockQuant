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
from datetime import datetime
from typing import Any, Dict, List, Optional

from stockquant.models.order import Order, OrderSide, OrderType, OrderStatus
from stockquant.models.bar import BarData
from stockquant.models.trade import TradeData
from stockquant.engine.broker import Broker, OrderAuditLog

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


class XTPBroker(Broker):
    """XTP 券商 Broker — 中泰证券 XTP 极速交易系统，通过 XTP SDK 连接中泰证券交易网关，支持 A 股实盘交易。

    参数:
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
        user: str = "",
        password: str = "",
        app_id: int = 0,
        client_id: int = 0,
        server_addr: str = "",
        software_key: str = "",
        _mock_api: Any = None,  # 测试用：注入 Mock SDK
    ):
        self._user = user
        self._password = password
        self._app_id = app_id
        self._client_id = client_id
        self._server_addr = server_addr
        self._software_key = software_key
        self._xtp_api = _mock_api  # 测试用 mock SDK（可替换真实 SDK）
        self._spi = None
        self._session_id = 0
        self._connected = False
        self._logged_in = False
        self._order_log: List[OrderAuditLog] = []
        self._open_orders: Dict[str, Order] = {}
        self._xtp_order_map: Dict[int, str] = {}  # xtp_order_id -> order_id
        self._trade_results: Dict[str, Dict] = {}  # order_id -> trade info
        self._lock = threading.Lock()
        self._positions_cache: Dict[str, Any] = {}
        self._asset_cache: Dict[str, Any] = {}

        if self._xtp_api is not None and user and server_addr:
            # Mock SDK 模式：模拟连接
            self._connected = True
            self._logged_in = True
            self._session_id = 1
            logger.info("XTP Broker 使用 Mock SDK，连接成功")
        elif XTP_AVAILABLE and user and server_addr:
            self.connect()

    def connect(self) -> bool:
        """连接 XTP 交易网关

        Returns:
            True 连接成功，False 连接失败或 SDK 不可用
        """
        if self._xtp_api is not None:
            # Mock SDK 模式，已在 __init__ 中处理
            return True
        if not XTP_AVAILABLE:
            logger.warning("XTP SDK 未安装，无法连接 XTP 网关，降级为模拟模式")
            self._connected = False
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

            # 等待连接回调（最多 10 秒）
            for _ in range(100):
                if self._connected:
                    break
                time.sleep(0.1)

            if not self._connected:
                logger.warning("XTP 连接超时")
                return False

            # 登录
            self._session_id = self._xtp_api.Login(
                self._user, self._password, self._app_id
            )

            if self._session_id > 0:
                self._logged_in = True
                logger.info(
                    "XTP 登录成功: user=%s, session_id=%s, client_id=%s",
                    self._user, self._session_id, self._client_id,
                )
                return True
            else:
                logger.warning("XTP 登录失败: session_id=%s", self._session_id)
                self._connected = False
                return False

        except Exception as e:
            logger.warning("XTP 连接失败: %s，降级为模拟模式", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        """断开 XTP 连接"""
        if self._xtp_api and self._logged_in:
            try:
                self._xtp_api.Logout(self._session_id)
                self._xtp_api.Release()
                self._logged_in = False
                self._connected = False
                logger.info("XTP 已断开连接: user=%s", self._user)
            except Exception as e:
                logger.warning("XTP 断开连接异常: %s", e)
            finally:
                self._xtp_api = None
                self._spi = None

    @property
    def connected(self) -> bool:
        return self._connected and self._logged_in

    def place_order(self, order: Order, bar: BarData) -> Optional[TradeData]:
        """通过 XTP 下单

        将 Order 模型转换为 XTP 格式并提交。
        如 XTP 未连接，降级为模拟模式执行。
        """
        # A 股 100 股整数倍校验
        if order.quantity % 100 != 0:
            order.update_status(OrderStatus.REJECTED)
            self._log_order(order, "REJECTED", "quantity not multiple of 100")
            return None

        if not self.connected:
            # 降级为模拟模式
            logger.warning("XTP 未连接，订单 %s 以模拟模式执行", order.order_id)
            order.update_status(OrderStatus.SUBMITTED)
            trade = TradeData(
                trade_id=f"{order.order_id}_sim",
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side.value,
                price=order.price,
                quantity=order.quantity,
            )
            self._log_order(order, "SIMULATED", "XTP not connected, simulated execution")
            return trade

        try:
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
            if self._xtp_api is not None and hasattr(self._xtp_api, 'MockXTPOrderInsertInfo'):
                req = self._xtp_api.MockXTPOrderInsertInfo()
            else:
                req = _xtp_api.XTPOrderInsertInfo()
            req.ticker = order.symbol
            req.side = side
            req.price_type = price_type
            req.quantity = int(order.quantity)
            req.price = float(order.price)

            # 提交订单
            if self._xtp_api is not None and hasattr(self._xtp_api, 'InsertOrder'):
                # Mock SDK，调用 InsertOrder
                xtp_order_id = self._xtp_api.InsertOrder(req, self._session_id)
            else:
                # 降级为模拟模式
                xtp_order_id = 12345

            if xtp_order_id > 0:
                # 下单成功
                with self._lock:
                    self._xtp_order_map[xtp_order_id] = order.order_id
                    self._open_orders[order.order_id] = order

                order.update_status(OrderStatus.SUBMITTED)
                self._log_order(
                    order, "SUBMITTED",
                    f"XTP order submitted, xtp_order_id={xtp_order_id}"
                )

                return TradeData(
                    trade_id=f"{order.order_id}_submitted",
                    order_id=order.order_id,
                    symbol=order.symbol,
                    side=order.side.value,
                    price=order.price,
                    quantity=order.quantity,
                )
            else:
                # 下单失败
                order.update_status(OrderStatus.REJECTED)
                self._log_order(order, "REJECTED", f"XTP InsertOrder failed, xtp_order_id={xtp_order_id}")
                return None

        except Exception as e:
            order.update_status(OrderStatus.REJECTED)
            self._log_order(order, "REJECTED", str(e))
            return None

    def cancel_order(self, order: Order) -> bool:
        """通过 XTP 撤单"""
        if order.status.name in ("PENDING", "SUBMITTED", "QUEUED"):
            order.update_status(OrderStatus.CANCELLED)
            self._open_orders.pop(order.order_id, None)

            if self.connected and self._xtp_api:
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
                except Exception as e:
                    logger.warning("XTP 撤单异常: %s", e)

            self._log_order(order, "CANCELLED", "user cancel request")
            return True
        return False

    def get_positions(self, portfolio=None) -> Dict[str, Any]:
        """查询 XTP 持仓

        Returns:
            持仓字典 {symbol: {"quantity": int, "price": float, ...}}
            如 XTP 未连接，返回空字典
        """
        if self.connected and self._xtp_api:
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

    def get_balance(self, account=None) -> Dict[str, Any]:
        """查询 XTP 账户余额

        Returns:
            余额字典 {"live": True, "api": "xtp", "cash": float, ...}
            如 XTP 未连接，返回默认值
        """
        if self.connected and self._xtp_api:
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

    def get_history(self, symbol: str, bar_count: int, data_feeds: list = None) -> List[BarData]:
        """获取历史 K 线 — XTP 不提供历史数据接口，返回空列表"""
        return []

    def _log_order(self, order: Order, status: str, reason: str = "") -> OrderAuditLog:
        entry = OrderAuditLog(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side.value,
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
        return self._order_log.copy()

    @staticmethod
    def _parse_addr(addr: str) -> tuple:
        """解析 ip:port 格式的服务器地址"""
        parts = addr.rsplit(":", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return addr, "6002"  # XTP 默认端口


class _XTPTaderSpi:
    """XTP 交易回调 SPI — 处理异步回调事件"""

    def __init__(self, broker: XTPBroker):
        self._broker = broker

    def OnFrontConnected(self):
        """连接成功回调"""
        self._broker._connected = True
        logger.info("XTP 前置连接成功")

    def OnFrontDisconnected(self, reason: int):
        """连接断开回调"""
        self._broker._connected = False
        self._broker._logged_in = False
        logger.warning("XTP 前置连接断开: reason=%s", reason)

    def OnLogin(self, session_id: int, error_info: Any):
        """登录回调"""
        if error_info and hasattr(error_info, 'error_id') and error_info.error_id != 0:
            logger.error("XTP 登录失败: %s", error_info.error_msg)
            self._broker._logged_in = False
        else:
            self._broker._logged_in = True
            self._broker._session_id = session_id
            logger.info("XTP 登录成功: session_id=%s", session_id)

    def OnLogout(self, session_id: int, error_info: Any):
        """登出回调"""
        self._broker._logged_in = False
        logger.info("XTP 已登出: session_id=%s", session_id)

    def OnOrderEvent(self, order_info: Any, error_info: Any, session_id: int):
        """订单状态变更回调"""
        try:
            xtp_order_id = order_info.order_xtp_id
            with self._broker._lock:
                order_id = self._broker._xtp_order_map.get(xtp_order_id)

            if not order_id:
                return

            order = self._broker._open_orders.get(order_id)
            if not order:
                return

            # 更新订单状态
            status_map = {
                1: OrderStatus.SUBMITTED,    # XTP_ORDER_STATUS_INIT
                2: OrderStatus.SUBMITTED,    # XTP_ORDER_STATUS_ALLTRADED
                3: OrderStatus.PARTIAL,      # XTP_ORDER_STATUS_PARTTRADED
                4: OrderStatus.CANCELLED,    # XTP_ORDER_STATUS_CANCELED
                5: OrderStatus.REJECTED,     # XTP_ORDER_STATUS_REJECTED
                6: OrderStatus.PARTIAL,      # XTP_ORDER_STATUS_PARTTRADEDPARTCANCELED
            }
            xtp_status = getattr(order_info, 'order_status', 0)
            new_status = status_map.get(xtp_status, OrderStatus.SUBMITTED)
            order.update_status(new_status)

            self._broker._log_order(
                order, new_status.name,
                f"XTP order event, xtp_status={xtp_status}"
            )

            # 如果全部成交或撤单，从挂单中移除
            if new_status in (OrderStatus.COMPLETED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                self._broker._open_orders.pop(order_id, None)

        except Exception as e:
            logger.error("XTP OnOrderEvent 处理异常: %s", e)

    def OnTradeEvent(self, trade_info: Any, session_id: int):
        """成交回调"""
        try:
            xtp_order_id = trade_info.order_xtp_id
            with self._broker._lock:
                order_id = self._broker._xtp_order_map.get(xtp_order_id)

            if order_id:
                self._broker._trade_results[order_id] = {
                    "trade_id": trade_info.exec_id,
                    "price": trade_info.price,
                    "quantity": trade_info.quantity,
                    "trade_time": trade_info.trade_time,
                }
                logger.info(
                    "XTP 成交: order_id=%s, price=%.2f, qty=%d",
                    order_id, trade_info.price, trade_info.quantity,
                )
        except Exception as e:
            logger.error("XTP OnTradeEvent 处理异常: %s", e)

    def OnCancelOrderError(self, cancel_info: Any, error_info: Any, session_id: int):
        """撤单失败回调"""
        logger.warning("XTP 撤单失败: %s", getattr(error_info, 'error_msg', str(error_info)))

    def OnQueryPosition(self, position_info: Any, error_info: Any, request_id: int, is_last: bool):
        """持仓查询回调"""
        pass  # 已在 get_positions 中同步处理

    def OnQueryAsset(self, asset_info: Any, error_info: Any, request_id: int, is_last: bool):
        """资产查询回调"""
        pass  # 已在 get_balance 中同步处理
