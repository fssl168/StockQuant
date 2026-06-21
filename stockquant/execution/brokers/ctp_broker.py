# -*- coding: utf-8 -*-
"""CTP 券商 Broker 实现 — 期货交易前置系统

CTP (Comprehensive Transaction Platform) 是上期技术开发的期货交易前置系统，
支持国内所有期货交易所（上期所、大商所、郑商所、中金所、广期所）的期货/期权交易。

SDK 安装:
    pip install openctp-ctp        # openctp 官方 Python 封装（推荐）
    或从上期技术官网获取 CTP API

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
from stockquant.execution.brokers.mock_sdk import MockCtpApi

logger = logging.getLogger("stockquant.execution.ctp")

# CTP SDK 可选导入
_ctp_api = None
CTP_AVAILABLE = False

# openctp-ctp (pip install openctp-ctp，推荐)
try:
    from openctp_ctp.thosttraderapi import CThostFtdcTraderApi as TraderApi
    _ctp_api = TraderApi
    CTP_AVAILABLE = True
    logger.info("CTP SDK (openctp_ctp.thosttraderapi) 已加载")
except ImportError:
    logger.info("CTP SDK 未安装，CTP Broker 将以模拟模式运行")


class CTPBroker(Broker):
    """CTP 券商 Broker — 期货交易前置系统，通过 CTP SDK 连接期货公司交易前置，支持期货/期权实盘交易。

    注意：CTP 面向期货交易，下单数量单位为「手」而非「股」，
    且不同合约的每手数量不同（如 IF 每手 300，rb 每手 10）。

    参数:
        user: CTP 资金账号 (InvestorID)
        password: CTP 交易密码
        broker_id: 期货公司 BrokerID
        front_addr: 交易前置地址 (tcp://ip:port)
        app_id: AppID（部分期货公司需要）
        _mock_api: 测试用 mock SDK

    如 CTP SDK 未安装，所有操作将降级为模拟模式并输出警告日志。
    """

    api = "ctp"

    # CTP 常量
    THOST_FTDC_D_Buy = "2"
    THOST_FTDC_D_Sell = "1"
    THOST_FTDC_OF_Open = "0"
    THOST_FTDC_OF_Close = "1"
    THOST_FTDC_OF_CloseYesterday = "4"
    THOST_FTDC_OPT_LimitPrice = "2"
    THOST_FTDC_OPT_AnyPrice = "1"
    THOST_FTDC_HF_Speculation = "1"

    def __init__(
        self,
        user: str = "",
        password: str = "",
        broker_id: str = "",
        front_addr: str = "",
        app_id: str = "",
        _mock_api: Any = None,  # 测试用：注入 Mock SDK
    ):
        self._user = user
        self._password = password
        self._broker_id = broker_id
        self._front_addr = front_addr
        self._app_id = app_id
        self._ctp_api = _mock_api  # 测试用 mock SDK（可替换真实 SDK）
        self._spi = None
        self._request_id = 0
        self._connected = False
        self._logged_in = False
        self._order_log: List[OrderAuditLog] = []
        self._open_orders: Dict[str, Order] = {}
        self._ctp_order_map: Dict[str, str] = {}  # order_ref -> order_id
        self._trade_results: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._positions_cache: Dict[str, Any] = {}
        self._asset_cache: Dict[str, Any] = {}
        self._front_connected_event = threading.Event()
        self._login_event = threading.Event()

        if self._ctp_api is not None and user and front_addr:
            # Mock SDK 模式：模拟连接
            self._connected = True
            self._logged_in = True
            # 注册 SPI 以支持查询回调
            self._spi = _CTPTraderSpi(self)
            self._ctp_api.RegisterSpi(self._spi)
            logger.info("CTP Broker 使用 Mock SDK，连接成功")
        elif CTP_AVAILABLE and user and front_addr:
            self.connect()

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def connect(self) -> bool:
        """连接 CTP 交易前置

        Returns:
            True 连接成功，False 连接失败或 SDK 不可用
        """
        if self._ctp_api is not None:
            # Mock SDK 模式，已在 __init__ 中处理
            return True
        if not CTP_AVAILABLE:
            logger.warning("CTP SDK 未安装，无法连接 CTP 前置，降级为模拟模式")
            self._connected = False
            return False

        try:
            # 创建 TraderApi 实例
            flow_path = os.path.join(os.getcwd(), "ctp_flow")
            os.makedirs(flow_path, exist_ok=True)

            self._ctp_api = _ctp_api.CreateFtdcTraderApi(flow_path)

            # 注册回调 SPI
            self._spi = _CTPTraderSpi(self)
            self._ctp_api.RegisterSpi(self._spi)

            # 订阅公有/私有流
            try:
                self._ctp_api.SubscribePublicTopic(0)  # THOST_TERT_RESTART
                self._ctp_api.SubscribePrivateTopic(0)
            except Exception:
                pass

            # 注册前置机地址
            self._ctp_api.RegisterFront(self._front_addr)

            # 初始化连接
            self._ctp_api.Init()

            # 等待前置连接成功（最多 10 秒）
            if not self._front_connected_event.wait(timeout=10):
                logger.warning("CTP 前置连接超时")
                return False

            self._connected = True

            # 认证（部分期货公司需要）
            if self._app_id:
                try:
                    req = _ctp_api.CThostFtdcReqAuthenticateField()
                    req.BrokerID = self._broker_id
                    req.UserID = self._user
                    req.AppID = self._app_id
                    self._ctp_api.ReqAuthenticate(req, self._next_request_id())
                except Exception as e:
                    logger.debug("CTP 认证请求失败（可能不需要认证）: %s", e)

            # 登录
            login_req = _ctp_api.CThostFtdcReqUserLoginField()
            login_req.BrokerID = self._broker_id
            login_req.UserID = self._user
            login_req.Password = self._password
            ret = self._ctp_api.ReqUserLogin(login_req, self._next_request_id())

            if ret == 0:
                # 等待登录回调
                if self._login_event.wait(timeout=10) and self._logged_in:
                    logger.info(
                        "CTP 登录成功: user=%s, broker_id=%s",
                        self._user, self._broker_id,
                    )
                    return True
                else:
                    logger.warning("CTP 登录失败")
                    self._connected = False
                    return False
            else:
                logger.warning("CTP ReqUserLogin 返回错误: %d", ret)
                self._connected = False
                return False

        except Exception as e:
            logger.warning("CTP 连接失败: %s，降级为模拟模式", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        """断开 CTP 连接"""
        if self._ctp_api and self._logged_in:
            try:
                logout_req = _ctp_api.CThostFtdcUserLogoutField()
                logout_req.BrokerID = self._broker_id
                logout_req.UserID = self._user
                self._ctp_api.ReqUserLogout(logout_req, self._next_request_id())
                self._logged_in = False
                self._connected = False
                logger.info("CTP 已断开连接: user=%s", self._user)
            except Exception as e:
                logger.warning("CTP 断开连接异常: %s", e)
            finally:
                try:
                    self._ctp_api.Release()
                except Exception:
                    pass
                self._ctp_api = None
                self._spi = None

    @property
    def connected(self) -> bool:
        return self._connected and self._logged_in

    def place_order(self, order: Order, bar: BarData) -> Optional[TradeData]:
        """通过 CTP 下单

        将 Order 模型转换为 CTP 格式并提交。
        注意：期货交易以「手」为单位，不强制 100 整数倍校验。
        如 CTP 未连接，降级为模拟模式执行。
        """
        if not self.connected:
            # 降级为模拟模式
            logger.warning("CTP 未连接，订单 %s 以模拟模式执行", order.order_id)
            order.update_status(OrderStatus.SUBMITTED)
            trade = TradeData(
                trade_id=f"{order.order_id}_sim",
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side.value,
                price=order.price,
                quantity=order.quantity,
            )
            self._log_order(order, "SIMULATED", "CTP not connected, simulated execution")
            return trade

        try:
            # 构建 CTP 报单请求
            if self._connected and self._ctp_api:
                req = self._ctp_api.CThostFtdcInputOrderField()
            else:
                # 降级为模拟模式
                raise RuntimeError("CTP not connected")
            req.BrokerID = self._broker_id
            req.InvestorID = self._user
            req.InstrumentID = order.symbol
            req.OrderRef = order.order_id

            # 买卖方向
            if order.side == OrderSide.BUY:
                req.Direction = self.THOST_FTDC_D_Buy
                req.CombOffsetFlag = self.THOST_FTDC_OF_Open  # 买入开仓
            else:
                req.Direction = self.THOST_FTDC_D_Sell
                req.CombOffsetFlag = self.THOST_FTDC_OF_Close  # 卖出平仓

            # 订单类型
            if order.order_type == OrderType.LIMIT:
                req.OrderPriceType = self.THOST_FTDC_OPT_LimitPrice
                req.LimitPrice = float(order.price)
            else:
                req.OrderPriceType = self.THOST_FTDC_OPT_AnyPrice
                req.LimitPrice = 0.0

            # 数量和投机套保标志
            req.VolumeTotalOriginal = int(order.quantity)
            req.CombHedgeFlag = self.THOST_FTDC_HF_Speculation

            # 有效期类型: GFD (当日有效)
            req.TimeCondition = "3"  # THOST_FTDC_TC_GFD
            req.VolumeCondition = "1"  # THOST_FTDC_VC_AV
            req.MinVolume = 1
            req.ContingentCondition = "1"  # THOST_FTDC_CC_Immediately
            req.ForceCloseReason = "0"  # THOST_FTDC_FCC_NotForceClose

            # 提交报单
            if self._connected and self._ctp_api:
                ret = self._ctp_api.ReqOrderInsert(req, self._next_request_id())

            if ret == 0:
                # 报单请求已发送
                with self._lock:
                    self._ctp_order_map[order.order_id] = order.order_id
                    self._open_orders[order.order_id] = order

                order.update_status(OrderStatus.SUBMITTED)
                self._log_order(order, "SUBMITTED", "CTP order submitted")

                return TradeData(
                    trade_id=f"{order.order_id}_submitted",
                    order_id=order.order_id,
                    symbol=order.symbol,
                    side=order.side.value,
                    price=order.price,
                    quantity=order.quantity,
                )
            else:
                order.update_status(OrderStatus.REJECTED)
                self._log_order(order, "REJECTED", f"CTP ReqOrderInsert returned {ret}")
                return None

        except Exception as e:
            order.update_status(OrderStatus.REJECTED)
            self._log_order(order, "REJECTED", str(e))
            return None

    def cancel_order(self, order: Order) -> bool:
        """通过 CTP 撤单"""
        if order.status.name in ("PENDING", "SUBMITTED", "QUEUED"):
            order.update_status(OrderStatus.CANCELLED)
            self._open_orders.pop(order.order_id, None)

            if self.connected and self._ctp_api:
                try:
                    req = _ctp_api.CThostFtdcInputOrderActionField()
                    req.BrokerID = self._broker_id
                    req.InvestorID = self._user
                    req.OrderRef = order.order_id
                    req.InstrumentID = order.symbol
                    req.ActionFlag = "0"  # THOST_FTDC_AF_Delete

                    self._ctp_api.ReqOrderAction(req, self._next_request_id())
                except Exception as e:
                    logger.warning("CTP 撤单异常: %s", e)

            self._log_order(order, "CANCELLED", "user cancel request")
            return True
        return False

    def get_positions(self, portfolio=None) -> Dict[str, Any]:
        """查询 CTP 持仓

        Returns:
            持仓字典 {symbol: {"long_qty": int, "short_qty": int, "price": float, ...}}
            期货持仓区分多空方向。
            如 CTP 未连接，返回空字典
        """
        if self.connected and self._ctp_api:
            try:
                req = self._ctp_api.CThostFtdcQryInvestorPositionField()
                req.BrokerID = self._broker_id
                req.InvestorID = self._user
                self._ctp_api.ReqQryInvestorPosition(req, self._next_request_id())
                # 结果通过 SPI 回调返回，此处返回缓存
                return self._positions_cache
            except Exception as e:
                logger.warning("CTP 查询持仓失败: %s", e)
                return self._positions_cache
        return {}

    def get_balance(self, account=None) -> Dict[str, Any]:
        """查询 CTP 账户余额

        Returns:
            余额字典 {"live": True, "api": "ctp", "cash": float, ...}
            期货账户包含保证金占用等信息。
            如 CTP 未连接，返回默认值
        """
        if self.connected and self._ctp_api:
            try:
                req = self._ctp_api.CThostFtdcQryTradingAccountField()
                req.BrokerID = self._broker_id
                req.InvestorID = self._user
                self._ctp_api.ReqQryTradingAccount(req, self._next_request_id())
                # 结果通过 SPI 回调返回，此处返回缓存
                return self._asset_cache
            except Exception as e:
                logger.warning("CTP 查询余额失败: %s", e)
                return self._asset_cache
        return {"live": True, "api": "ctp", "cash": 0, "frozen": 0, "equity": 0}

    def get_history(self, symbol: str, bar_count: int, data_feeds: list = None) -> List[BarData]:
        """获取历史 K 线 — CTP 不提供历史数据接口，返回空列表"""
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


# CTP SPI 基类 — 优先继承 SDK 的 CThostFtdcTraderSpi
_CTP_SPI_BASE = object
try:
    from openctp_ctp.thosttraderapi import CThostFtdcTraderSpi as _CtpSpiBase
    _CTP_SPI_BASE = _CtpSpiBase
except ImportError:
    pass


class _CTPTraderSpi(_CTP_SPI_BASE):
    """CTP 交易回调 SPI — 处理异步回调事件

    当 openctp-ctp SDK 可用时，继承 CThostFtdcTraderSpi；
    否则作为普通类使用（模拟模式）。
    """

    def __init__(self, broker: CTPBroker):
        if _CTP_SPI_BASE is not object:
            _CTP_SPI_BASE.__init__(self)
        self._broker = broker

    def OnFrontConnected(self):
        """前置连接成功"""
        self._broker._connected = True
        self._broker._front_connected_event.set()
        logger.info("CTP 前置连接成功")

    def OnFrontDisconnected(self, reason: int):
        """前置连接断开"""
        self._broker._connected = False
        self._broker._logged_in = False
        logger.warning("CTP 前置连接断开: reason=%s", reason)

    def OnRspAuthenticate(self, pRspAuthenticateField, pRspInfo, nRequestID, bIsLast):
        """认证回调"""
        if pRspInfo and pRspInfo.ErrorID != 0:
            logger.warning("CTP 认证失败: %s", pRspInfo.ErrorMsg)
        else:
            logger.info("CTP 认证成功")

    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast):
        """登录回调"""
        if pRspInfo and pRspInfo.ErrorID != 0:
            logger.error("CTP 登录失败: %s", pRspInfo.ErrorMsg)
            self._broker._logged_in = False
        else:
            self._broker._logged_in = True
            trading_day = getattr(pRspUserLogin, 'TradingDay', '')
            logger.info("CTP 登录成功: user=%s, trading_day=%s", self._broker._user, trading_day)
        self._broker._login_event.set()

    def OnRspUserLogout(self, pUserLogout, pRspInfo, nRequestID, bIsLast):
        """登出回调"""
        self._broker._logged_in = False
        logger.info("CTP 已登出: user=%s", self._broker._user)

    def OnRspOrderInsert(self, pInputOrder, pRspInfo, nRequestID, bIsLast):
        """报单响应回调"""
        if pRspInfo and pRspInfo.ErrorID != 0:
            logger.warning("CTP 报单失败: %s", pRspInfo.ErrorMsg)
            # 更新订单状态
            order_ref = getattr(pInputOrder, 'OrderRef', '')
            with self._broker._lock:
                order = self._broker._open_orders.get(order_ref)
            if order:
                order.update_status(OrderStatus.REJECTED)
                self._broker._log_order(order, "REJECTED", f"CTP: {pRspInfo.ErrorMsg}")

    def OnRtnOrder(self, pOrder):
        """报单通知回调"""
        try:
            order_ref = pOrder.OrderRef
            with self._broker._lock:
                order = self._broker._open_orders.get(order_ref)

            if not order:
                return

            # CTP 订单状态映射
            status_map = {
                "0": OrderStatus.SUBMITTED,   # THOST_FTDC_OAS_Submitted
                "1": OrderStatus.SUBMITTED,   # THOST_FTDC_OAS_Accepted
                "2": OrderStatus.REJECTED,    # THOST_FTDC_OAS_Rejected
                "3": OrderStatus.PARTIAL,     # THOST_FTDC_OST_PartTraded
                "4": OrderStatus.CANCELLED,   # THOST_FTDC_OST_NoTradeQueueing -> 撤单
                "5": OrderStatus.COMPLETED,   # THOST_FTDC_OST_AllTraded
                "a": OrderStatus.PARTIAL,     # 部成部撤
            }
            ctp_status = getattr(pOrder, 'OrderStatus', '0')
            new_status = status_map.get(ctp_status, OrderStatus.SUBMITTED)
            order.update_status(new_status)

            self._broker._log_order(
                order, new_status.name,
                f"CTP OnRtnOrder, status={ctp_status}"
            )

            if new_status in (OrderStatus.COMPLETED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                self._broker._open_orders.pop(order_ref, None)

        except Exception as e:
            logger.error("CTP OnRtnOrder 处理异常: %s", e)

    def OnRtnTrade(self, pTrade):
        """成交通知回调"""
        try:
            order_ref = pTrade.OrderRef
            with self._broker._lock:
                order_id = self._broker._ctp_order_map.get(order_ref, order_ref)

            self._broker._trade_results[order_id] = {
                "trade_id": pTrade.TradeID,
                "price": float(pTrade.Price),
                "quantity": int(pTrade.Volume),
                "trade_time": pTrade.TradeTime,
                "direction": pTrade.Direction,
                "offset": pTrade.OffsetFlag,
            }
            logger.info(
                "CTP 成交: order_ref=%s, price=%.2f, qty=%d, direction=%s",
                order_ref, float(pTrade.Price), int(pTrade.Volume), pTrade.Direction,
            )
        except Exception as e:
            logger.error("CTP OnRtnTrade 处理异常: %s", e)

    def OnRspOrderAction(self, pInputOrderAction, pRspInfo, nRequestID, bIsLast):
        """撤单响应回调"""
        if pRspInfo and pRspInfo.ErrorID != 0:
            logger.warning("CTP 撤单失败: %s", pRspInfo.ErrorMsg)

    def OnErrRtnOrderInsert(self, pInputOrder, pRspInfo):
        """报单错误回调"""
        logger.error("CTP 报单错误: %s", getattr(pRspInfo, 'ErrorMsg', str(pRspInfo)))

    def OnErrRtnOrderAction(self, pInputOrderAction, pRspInfo):
        """撤单错误回调"""
        logger.error("CTP 撤单错误: %s", getattr(pRspInfo, 'ErrorMsg', str(pRspInfo)))

    def OnRspQryInvestorPosition(self, pInvestorPosition, pRspInfo, nRequestID, bIsLast):
        """持仓查询回调"""
        if pInvestorPosition:
            try:
                symbol = pInvestorPosition.InstrumentID
                direction = pInvestorPosition.PosiDirection  # '2'=多, '3'=空
                qty = int(pInvestorPosition.Position)
                price = float(pInvestorPosition.PositionCost / max(qty, 1))

                with self._broker._lock:
                    if symbol not in self._broker._positions_cache:
                        self._broker._positions_cache[symbol] = {
                            "long_qty": 0, "short_qty": 0, "price": 0.0,
                            "market_value": 0.0, "unrealized_pnl": 0.0,
                        }
                    pos = self._broker._positions_cache[symbol]
                    if direction == "2":  # 多头
                        pos["long_qty"] = qty
                    elif direction == "3":  # 空头
                        pos["short_qty"] = qty
                    pos["price"] = price
                    pos["unrealized_pnl"] = float(getattr(pInvestorPosition, 'PositionProfit', 0))
            except Exception as e:
                logger.error("CTP 持仓回调处理异常: %s", e)

    def OnRspQryTradingAccount(self, pTradingAccount, pRspInfo, nRequestID, bIsLast):
        """资金账户查询回调"""
        if pTradingAccount:
            try:
                with self._broker._lock:
                    self._broker._asset_cache = {
                        "live": True,
                        "api": "ctp",
                        "cash": float(pTradingAccount.Available),
                        "frozen": float(pTradingAccount.FrozenMargin + pTradingAccount.FrozenCash),
                        "equity": float(pTradingAccount.Balance),
                        "available": float(pTradingAccount.Available),
                        "margin": float(pTradingAccount.CurrMargin),
                        "pre_balance": float(pTradingAccount.PreBalance),
                    }
            except Exception as e:
                logger.error("CTP 资金回调处理异常: %s", e)
