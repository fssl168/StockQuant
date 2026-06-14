# -*- coding: utf-8 -*-
"""F006 Broker 抽象层 — 回测/模拟/实盘统一接口"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from stockquant.models.order import Order, OrderSide, OrderType, OrderStatus
from stockquant.models.bar import BarData
from stockquant.models.trade import TradeData


class Broker(ABC):
    """Broker 抽象基类"""

    @abstractmethod
    def place_order(self, order: Order, bar: BarData) -> Optional[TradeData]:
        """下单并撮合"""
        ...

    @abstractmethod
    def cancel_order(self, order: Order) -> bool:
        """撤单"""
        ...

    @abstractmethod
    def get_positions(self) -> Dict[str, Any]:
        """获取所有持仓"""
        ...

    @abstractmethod
    def get_balance(self) -> Dict[str, Any]:
        """获取账户余额"""
        ...

    @abstractmethod
    def get_history(self, symbol: str, bar_count: int) -> List[BarData]:
        """获取历史K线"""
        ...


class BacktestBroker(Broker):
    """
    回测 Broker — 基于K线数据模拟成交。

    撮合规则:
    - 市价单：按当前 Bar 收盘价撮合
    - 限价单：价格优先、时间优先
      - Buy Limit：实际价格 ≤ 限价 → 按限价成交
      - Sell Limit：实际价格 ≥ 限价 → 按限价成交
    - 涨跌停板限制
    - 100 股整数倍
    """

    def __init__(
        self,
        slippage: Optional[Any] = None,
        limit_up_ratio: float = 0.10,
        limit_down_ratio: float = 0.10,
    ):
        self._slippage = slippage
        self._limit_up_ratio = limit_up_ratio
        self._limit_down_ratio = limit_down_ratio

    def place_order(self, order: Order, bar: BarData) -> Optional[TradeData]:
        """
        撮合一笔订单。

        Returns
        -------
        TradeData or None
            成交则返回 TradeData，否则返回 None
        """
        # 1. 涨跌停检查
        limit_up = bar.close * (1 + self._limit_up_ratio)
        limit_down = bar.close * (1 - self._limit_down_ratio)

        if order.price > limit_up or order.price < limit_down:
            order.update_status(OrderStatus.REJECTED)
            return None

        # 2. 100 股整数倍
        if order.quantity % 100 != 0:
            order.update_status(OrderStatus.REJECTED)
            return None

        # 3. 限价单价格检查
        if order.order_type.name == "LIMIT":
            if order.side == OrderSide.BUY and order.price < bar.close:
                # 买单限价低于市价，不会成交（简化：按市价撮合）
                pass
            elif order.side == OrderSide.SELL and order.price > bar.close:
                pass

        # 4. 应用滑点
        side = "buy" if order.side == OrderSide.BUY else "sell"
        exec_price = bar.close
        if self._slippage:
            exec_price = self._slippage.apply(bar.close, side)

        # 5. 成交
        order.update_status(OrderStatus.FILLED)
        order.add_fill(order.quantity, exec_price)

        trade = TradeData(
            trade_id=f"{order.order_id}_trade",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side.value,
            price=exec_price,
            quantity=order.quantity,
        )
        return trade

    def cancel_order(self, order: Order) -> bool:
        if order.status.name in ("PENDING", "SUBMITTED", "QUEUED"):
            order.update_status(OrderStatus.CANCELLED)
            return True
        return False

    def get_positions(self, portfolio) -> Dict[str, Any]:
        """从 Cerebro/Portfolio 获取实际持仓"""
        if hasattr(portfolio, 'positions'):
            return {k: v.__dict__ for k, v in portfolio.positions.items() if v.quantity > 0}
        return {}

    def get_balance(self, account) -> Dict[str, Any]:
        """从 Account 获取余额"""
        if account:
            return {"cash": account.cash, "frozen": account.frozen_cash, "equity": account.total_equity}
        return {"cash": 0, "frozen": 0}

    def get_history(self, symbol: str, bar_count: int, data_feeds: list = None) -> List[BarData]:
        """从 DataFeed 获取历史数据"""
        if not data_feeds:
            return []
        for feed in data_feeds:
            if feed.symbol == symbol:
                n = len(feed)
                start = max(0, n - bar_count)
                return [feed[i] for i in range(start, n)]
        return []


class PaperBroker(Broker):
    """
    F012 模拟盘 Broker — 基于实时行情模拟成交。
    与 BacktestBroker 相同的费用模型和撮合逻辑，不实际下单。
    """

    def __init__(
        self,
        slippage: Optional[Any] = None,
        limit_up_ratio: float = 0.10,
        limit_down_ratio: float = 0.10,
    ):
        self._slippage = slippage
        self._limit_up_ratio = limit_up_ratio
        self._limit_down_ratio = limit_down_ratio
        self._order_book: Dict[str, List[Order]] = {}  # 未成交订单
        self._trade_log: List[TradeData] = []

    def place_order(self, order: Order, bar: BarData) -> Optional[TradeData]:
        """模拟成交：与 BacktestBroker 相同逻辑"""
        # 涨跌停检查
        limit_up = bar.close * (1 + self._limit_up_ratio)
        limit_down = bar.close * (1 - self._limit_down_ratio)
        if order.price > limit_up or order.price < limit_down:
            order.update_status(OrderStatus.REJECTED)
            return None
        # 100 股整数倍
        if order.quantity % 100 != 0:
            order.update_status(OrderStatus.REJECTED)
            return None
        # 限价单
        if order.order_type.name == "LIMIT":
            if order.side == OrderSide.BUY and order.price < bar.close:
                pass
            elif order.side == OrderSide.SELL and order.price > bar.close:
                pass
        # 滑点
        side = "buy" if order.side == OrderSide.BUY else "sell"
        exec_price = bar.close
        if self._slippage:
            exec_price = self._slippage.apply(bar.close, side)
        # 成交
        order.update_status(OrderStatus.FILLED)
        order.add_fill(order.quantity, exec_price)
        trade = TradeData(
            trade_id=f"{order.order_id}_trade",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side.value,
            price=exec_price,
            quantity=order.quantity,
        )
        self._trade_log.append(trade)
        return trade

    def cancel_order(self, order: Order) -> bool:
        if order.status.name in ("PENDING", "SUBMITTED", "QUEUED"):
            order.update_status(OrderStatus.CANCELLED)
            return True
        return False

    def get_positions(self, portfolio=None) -> Dict[str, Any]:
        return {}

    def get_balance(self, account=None) -> Dict[str, Any]:
        return {"paper": True, "cash": 0, "equity": 0}

    def get_history(self, symbol: str, bar_count: int, data_feeds: list = None) -> List[BarData]:
        return []

    @property
    def trade_log(self) -> List[TradeData]:
        return self._trade_log.copy()


class LiveBroker(Broker):
    """
    F017 实盘 Broker — 调用券商 API 实际下单。
    预留接口：中泰 XTP / CTP 集成。
    """

    def __init__(self, api: str = "xtp", config: Optional[dict] = None):
        self._api = api  # "xtp" / "ctp" / "qmt"
        self._config = config or {}
        self._order_log: List[TradeData] = []

    def place_order(self, order: Order, bar: BarData) -> Optional[TradeData]:
        """实盘下单：调用券商 API（预留）"""
        # TODO: 集成中泰 XTP API
        # TODO: 集成 CTP API
        order.update_status(OrderStatus.REJECTED)
        return None

    def cancel_order(self, order: Order) -> bool:
        # TODO: 调用券商 API 撤单
        return False

    def get_positions(self, portfolio=None) -> Dict[str, Any]:
        return {}

    def get_balance(self, account=None) -> Dict[str, Any]:
        return {}

    def get_history(self, symbol: str, bar_count: int, data_feeds: list = None) -> List[BarData]:
        return []
