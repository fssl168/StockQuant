# -*- coding: utf-8 -*-
"""Mock 券商 SDK — 用于在没有真实 SDK 的情况下测试 Broker 代码路径

提供三个 Mock SDK 实现，分别模拟 XTP、CTP、QMT SDK 的接口：

- ``MockXtpApi`` — 模拟 ``vnpy_xtp`` / ``openctp`` 的 ``TraderApi`` 接口
- ``MockCtpApi`` — 模拟 ``openctp_ctp.thosttraderapi`` 的 ``CThostFtdcTraderApi`` 接口
- ``MockXtTrader`` — 模拟 ``xtquant.xttrader.XtQuantTrader`` 接口

所有连接操作始终成功（session_id=1），下单返回固定 order_id=12345，
持仓/余额返回预设模拟数据。适用于单元测试和集成测试。

使用示例::

    from stockquant.execution.brokers.mock_sdk import MockXtpApi
    from stockquant.execution.brokers.xtp_broker import XTPBroker

    broker = XTPBroker(_mock_api=MockXtpApi)
    assert broker.connected is True
    trade = broker.place_order(order, bar)
    assert trade is not None
"""
from __future__ import annotations

import dataclasses
from typing import Any, List, Optional


# ====================================================================
# Mock XTP SDK
# ====================================================================

@dataclasses.dataclass
class MockXTPPosition:
    """模拟 XTP 持仓信息"""
    ticker: str = "sh600519"
    total_qty: int = 1000
    available_qty: int = 800
    avg_price: float = 1800.0
    market_value: float = 1800000.0
    unrealized_pnl: float = 50000.0
    exchange_id: str = "SH"


@dataclasses.dataclass
class MockXTPAsset:
    """模拟 XTP 账户资产"""
    buying_power: float = 950000.0
    frozen_cash: float = 50000.0
    total_asset: float = 1000000.0
    market_value: float = 1800000.0


@dataclasses.dataclass
class MockXTPOrderInfo:
    """模拟 XTP 订单信息"""
    order_xtp_id: int = 12345
    ticker: str = "sh600519"
    side: int = 1  # BUY
    price: float = 1800.0
    quantity: int = 100
    order_status: int = 5  # FILLED


@dataclasses.dataclass
class MockXTPTadeInfo:
    """模拟 XTP 成交信息"""
    order_xtp_id: int = 12345
    exec_id: str = "TRD-001"
    price: float = 1800.0
    quantity: int = 100
    trade_time: int = 20260618


@dataclasses.dataclass
class MockXTPErrorInfo:
    """模拟 XTP 错误信息"""
    error_id: int = 0
    error_msg: str = ""


class MockXtpSpi:
    """模拟 XTP SPI 回调"""

    def __init__(self, broker: Any) -> None:
        self._broker = broker

    def OnFrontConnected(self) -> None:
        self._broker._connected = True

    def OnFrontDisconnected(self, reason: int) -> None:
        self._broker._connected = False
        self._broker._logged_in = False

    def OnLogin(self, session_id: int, error_info: MockXTPErrorInfo) -> None:
        if error_info and error_info.error_id != 0:
            self._broker._logged_in = False
        else:
            self._broker._logged_in = True
            self._broker._session_id = session_id

    def OnLogout(self, session_id: int, error_info: MockXTPErrorInfo) -> None:
        self._broker._logged_in = False

    def OnOrderEvent(self, order_info: Any, error_info: Any, session_id: int) -> None:
        pass

    def OnTradeEvent(self, trade_info: Any, session_id: int) -> None:
        pass

    def OnCancelOrderError(self, cancel_info: Any, error_info: Any, session_id: int) -> None:
        pass

    def OnQueryPosition(self, position_info: Any, error_info: Any, request_id: int, is_last: bool) -> None:
        pass

    def OnQueryAsset(self, asset_info: Any, error_info: Any, request_id: int, is_last: bool) -> None:
        pass


class MockXtpApi:
    """模拟 XTP SDK TraderApi 接口

    用于 XTPBroker 在没有真实 SDK 时进行测试。
    所有操作均成功（session_id=1），下单返回固定 order_id=12345。
    """

    @staticmethod
    def CreateTraderApi(client_id: int, log_path: str) -> "MockXtpApi":
        instance = MockXtpApi()
        instance._client_id = client_id
        instance._log_path = log_path
        return instance

    def __init__(self) -> None:
        self._client_id: int = 0
        self._log_path: str = ""
        self._spi: Optional[MockXtpSpi] = None
        self._session_id: int = 0

    def RegisterSpi(self, spi: MockXtpSpi) -> None:
        self._spi = spi

    def SetSoftwareKey(self, key: str) -> None:
        pass

    def RegisterFront(self, ip: str, port: int) -> None:
        # 模拟连接成功
        if self._spi:
            self._spi.OnFrontConnected()

    def SubscribePublicTopic(self, t: int) -> None:
        pass

    def SubscribePrivateTopic(self, t: int) -> None:
        pass

    def Init(self) -> None:
        pass

    def Login(self, user: str, password: str, app_id: int) -> int:
        if self._spi:
            self._spi.OnLogin(1, MockXTPErrorInfo())
        return 1  # session_id

    def Logout(self, session_id: int) -> None:
        if self._spi:
            self._spi.OnLogout(session_id, MockXTPErrorInfo())
        self._session_id = 0

    def Release(self) -> None:
        self._spi = None

    def InsertOrder(self, req: Any, session_id: int) -> int:
        return 12345  # 固定 order_xtp_id

    def CancelOrder(self, xtp_order_id: int, session_id: int) -> None:
        pass

    def QueryPositions(self, session_id: int) -> List[MockXTPPosition]:
        return [MockXTPPosition()]

    def QueryAsset(self, session_id: int) -> MockXTPAsset:
        return MockXTPAsset()

    @property
    def session_id(self) -> int:
        return self._session_id

    @staticmethod
    def MockXTPOrderInsertInfo():
        """Mock XTP 订单请求对象"""
        info = type('MockXTPOrderInsertInfo', (), {})()
        info.ticker = ""
        info.side = 1
        info.price_type = 1
        info.quantity = 0
        info.price = 0.0
        return info


class MockXTPOrderInsertInfo:
    """Mock XTP 订单请求对象"""
    ticker: str = ""
    side: int = 1
    price_type: int = 1
    quantity: int = 0
    price: float = 0.0


# ====================================================================
# Mock CTP SDK
# ====================================================================

@dataclasses.dataclass
class MockCTPPosition:
    """模拟 CTP 持仓信息"""
    InstrumentID: str = "IF2406"
    PosiDirection: str = "2"  # 多头
    Position: int = 10
    PositionCost: float = 2500000.0
    PositionProfit: float = 50000.0


@dataclasses.dataclass
class MockCTPTradingAccount:
    """模拟 CTP 资金账户"""
    Available: float = 500000.0
    Balance: float = 1000000.0
    CurrMargin: float = 250000.0
    FrozenMargin: float = 0.0
    FrozenCash: float = 250000.0
    PreBalance: float = 980000.0


@dataclasses.dataclass
class MockCTPLoginResponse:
    """模拟 CTP 登录响应"""
    ErrorID: int = 0
    ErrorMsg: str = ""
    TradingDay: str = "20260618"


@dataclasses.dataclass
class MockCTPOrderResponse:
    """模拟 CTP 订单响应"""
    ErrorID: int = 0
    ErrorMsg: str = ""


class MockCtpSpi:
    """模拟 CTP SPI 回调"""

    def __init__(self, broker: Any) -> None:
        self._broker = broker

    def OnFrontConnected(self) -> None:
        self._broker._connected = True
        if hasattr(self._broker, '_front_connected_event'):
            self._broker._front_connected_event.set()

    def OnFrontDisconnected(self, reason: int) -> None:
        self._broker._connected = False
        self._broker._logged_in = False
        if hasattr(self._broker, '_front_connected_event'):
            self._broker._front_connected_event.set()

    def OnRspAuthenticate(self, pRspAuthenticateField: Any, pRspInfo: Any, nRequestID: int, bIsLast: bool) -> None:
        pass

    def OnRspUserLogin(self, pRspUserLogin: Any, pRspInfo: Any, nRequestID: int, bIsLast: bool) -> None:
        if pRspInfo and pRspInfo.ErrorID != 0:
            self._broker._logged_in = False
        else:
            self._broker._logged_in = True
            if hasattr(self._broker, '_login_event'):
                self._broker._login_event.set()

    def OnRspUserLogout(self, pUserLogout: Any, pRspInfo: Any, nRequestID: int, bIsLast: bool) -> None:
        self._broker._logged_in = False

    def OnRspOrderInsert(self, pInputOrder: Any, pRspInfo: Any, nRequestID: int, bIsLast: bool) -> None:
        pass

    def OnRspOrderAction(self, pInputOrderAction: Any, pRspInfo: Any, nRequestID: int, bIsLast: bool) -> None:
        pass

    def OnRtnOrder(self, pOrder: Any) -> None:
        pass

    def OnRtnTrade(self, pTrade: Any) -> None:
        pass

    def OnErrRtnOrderInsert(self, pInputOrder: Any, pRspInfo: Any) -> None:
        pass

    def OnErrRtnOrderAction(self, pInputOrderAction: Any, pRspInfo: Any) -> None:
        pass

    def OnRspQryInvestorPosition(self, pInvestorPosition: Any, pRspInfo: Any, nRequestID: int, bIsLast: bool) -> None:
        if pInvestorPosition:
            symbol = pInvestorPosition.InstrumentID
            direction = pInvestorPosition.PosiDirection
            qty = int(pInvestorPosition.Position)
            price = float(pInvestorPosition.PositionCost / max(qty, 1))
            with self._broker._lock:
                if symbol not in self._broker._positions_cache:
                    self._broker._positions_cache[symbol] = {
                        "long_qty": 0, "short_qty": 0, "price": 0.0,
                        "market_value": 0.0, "unrealized_pnl": 0.0,
                    }
                pos = self._broker._positions_cache[symbol]
                if direction == "2":
                    pos["long_qty"] = qty
                elif direction == "3":
                    pos["short_qty"] = qty
                pos["price"] = price
                pos["unrealized_pnl"] = float(getattr(pInvestorPosition, 'PositionProfit', 0))

    def OnRspQryTradingAccount(self, pTradingAccount: Any, pRspInfo: Any, nRequestID: int, bIsLast: bool) -> None:
        if pTradingAccount:
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


class MockCtpApi:
    """模拟 CTP SDK CThostFtdcTraderApi 接口

    用于 CTPBroker 在没有真实 SDK 时进行测试。
    所有连接操作均成功。
    """

    def __init__(self, flow_path: str = "") -> None:
        self._flow_path = flow_path
        self._spi: Optional[MockCtpSpi] = None
        self._front_connected = False

    @staticmethod
    def CreateFtdcTraderApi(flow_path: str = "") -> "MockCtpApi":
        return MockCtpApi(flow_path)

    def RegisterSpi(self, spi: MockCtpSpi) -> None:
        self._spi = spi
        # 模拟连接成功
        if self._spi:
            self._spi.OnFrontConnected()

    def RegisterFront(self, addr: str) -> None:
        pass

    def SubscribePublicTopic(self, t: int) -> None:
        pass

    def SubscribePrivateTopic(self, t: int) -> None:
        pass

    def Init(self) -> None:
        pass

    def Release(self) -> None:
        self._spi = None

    def ReqUserLogin(self, req: Any, request_id: int) -> int:
        resp = MockCTPLoginResponse()
        if self._spi:
            self._spi.OnRspUserLogin(None, resp, request_id, True)
        return 0 if resp.ErrorID == 0 else -1

    def ReqAuthenticate(self, req: Any, request_id: int) -> int:
        return 0

    def ReqOrderInsert(self, req: Any, request_id: int) -> int:
        return 0

    def ReqOrderAction(self, req: Any, request_id: int) -> int:
        return 0

    def ReqUserLogout(self, req: Any, request_id: int) -> int:
        if self._spi:
            self._spi.OnRspUserLogout(None, None, request_id, True)
        return 0

    def CThostFtdcQryInvestorPositionField(self) -> Any:
        """CTP 持仓查询请求字段"""
        return type('QryPositionField', (), {'BrokerID': '', 'InvestorID': ''})()

    def CThostFtdcQryTradingAccountField(self) -> Any:
        """CTP 资金查询请求字段"""
        return type('QryAccountField', (), {'BrokerID': '', 'InvestorID': ''})()

    @staticmethod
    def CThostFtdcInputOrderField() -> Any:
        """CTP 下单请求字段"""
        return type('InputOrderField', (), {
            'BrokerID': '', 'InvestorID': '', 'InstrumentID': '', 'OrderRef': '',
            'Direction': '', 'CombOffsetFlag': '', 'OrderPriceType': '',
            'LimitPrice': 0.0, 'VolumeTotalOriginal': 0,
            'CombHedgeFlag': '', 'TimeCondition': '', 'VolumeCondition': '',
            'MinVolume': 0, 'ContingentCondition': '',
        })()

    def ReqQryInvestorPosition(self, req: Any, request_id: int) -> int:
        # 模拟返回一个多头持仓 — 直接通过 SPI 回调更新 broker cache
        if self._spi:
            pos = MockCTPPosition()
            self._spi.OnRspQryInvestorPosition(pos, None, request_id, True)
        return 0

    def ReqQryTradingAccount(self, req: Any, request_id: int) -> int:
        # 模拟返回资金账户 — 直接通过 SPI 回调更新 broker cache
        if self._spi:
            acc = MockCTPTradingAccount()
            self._spi.OnRspQryTradingAccount(acc, None, request_id, True)
        return 0


# ====================================================================
# Mock QMT SDK (xtquant)
# ====================================================================

@dataclasses.dataclass
class MockQMTPosition:
    """模拟 QMT 持仓信息"""
    stock_code: str = "600519.SH"
    volume: int = 1000
    can_use_volume: int = 800
    open_price: float = 1800.0
    last_price: float = 1850.0
    market_value: float = 1850000.0


@dataclasses.dataclass
class MockQMTAsset:
    """模拟 QMT 账户资产"""
    total_asset: float = 1000000.0
    cash: float = 950000.0
    frozen_cash: float = 50000.0
    market_value: float = 1850000.0


class MockXtTrader:
    """模拟 xtquant XtQuantTrader 接口

    用于 QMTBroker 在没有真实 SDK 时进行测试。
    所有操作均成功，session_id=1 固定。
    """

    def __init__(self, userdata_path: str = "", session_id: int = 1) -> None:
        self._userdata_path = userdata_path
        self._session_id = session_id
        self._connected = True

    @property
    def connected(self) -> bool:
        return self._connected

    def order_stock(
        self,
        account: str,
        stock_code: str,
        order_type: int,
        order_volume: int,
        price_type: int,
        price: float,
    ) -> int:
        return 12345

    def cancel_order_stock(self, account: str, order_id: int) -> None:
        pass

    def query_stock_positions(self, account: str) -> List[MockQMTPosition]:
        return [MockQMTPosition()]

    def query_stock_asset(self, account: str) -> MockQMTAsset:
        return MockQMTAsset()
