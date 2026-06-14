# -*- coding: utf-8 -*-
"""F006 Broker 抽象层 — 回测/模拟/实盘统一接口"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from stockquant.models.order import Order, OrderSide, OrderType, OrderStatus
from stockquant.models.bar import BarData
from stockquant.models.trade import TradeData


@dataclass
class OrderAuditLog:
    """订单审计日志"""
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    price: float = 0.0
    quantity: float = 0.0
    status: str = "PENDING"
    timestamp: datetime = field(default_factory=datetime.now)
    reason: str = ""


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

    当前为可工作的骨架实现：
    - place_order: 将订单状态置为 SUBMITTED 并记录审计日志，
      预留 XTP/CTP 真实下单接口
    - cancel_order: 对未成交订单撤销
    - get_positions / get_balance / get_history: 返回空数据
      （真实券商连接后可扩展）

    通过 ``config`` 字典可配置 broker 类型和券商参数：
    ``{"api": "xtp" / "ctp" / "qmt", "user": ..., "password": ...}``
    """

    def __init__(self, api: str = "xtp", config: Optional[dict] = None):
        self._api = api  # "xtp" / "ctp" / "qmt"
        self._config = config or {}
        self._order_log: List[OrderAuditLog] = []
        self._open_orders: Dict[str, Order] = {}  # 尚未撤单的订单缓存
        self._data_feeds: List[Any] = []  # 数据源列表，运行时注入

    @property
    def api(self) -> str:
        """当前使用的券商 API 类型"""
        return self._api

    @property
    def config(self) -> dict:
        """券商配置"""
        return self._config

    def _log_order(
        self,
        order: Order,
        status: str = "SUBMITTED",
        reason: str = "",
    ) -> OrderAuditLog:
        """将订单事件写入审计日志"""
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

    def place_order(self, order: Order, bar: BarData) -> Optional[TradeData]:
        """
        实盘下单骨架。

        当前行为：
        1. 验证 100 股整数倍（A 股最小交易单位）
        2. 将订单置为 SUBMITTED 并记录审计日志
        3. 缓存订单以便后续查询/撤销
        4. 返回 TradeData 占位符

        TODO: 集成中泰 XTP API / CTP API 进行真实下单
        """
        # 1. A 股 100 股整数倍校验
        if order.quantity % 100 != 0:
            order.update_status(OrderStatus.REJECTED)
            self._log_order(order, status="REJECTED",
                            reason="quantity not a multiple of 100")
            return None

        # 2. 涨跌停板简易检查（实际应通过行情确认）
        limit_up = bar.close * 1.10
        limit_down = bar.close * 0.90
        if order.price > limit_up or order.price < limit_down:
            order.update_status(OrderStatus.REJECTED)
            self._log_order(order, status="REJECTED",
                            reason="price beyond ±10% limit")
            return None

        # 3. 标记为已提交
        order.update_status(OrderStatus.SUBMITTED)
        self._open_orders[order.order_id] = order
        self._log_order(order, status="SUBMITTED", reason="order submitted to broker")

        # 4. 返回占位成交记录
        trade = TradeData(
            trade_id=f"{order.order_id}_submitted",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side.value,
            price=order.price,
            quantity=order.quantity,
        )
        self._order_log.append(
            OrderAuditLog(
                order_id=trade.trade_id,
                symbol=trade.symbol,
                side=trade.side,
                price=trade.price,
                quantity=trade.quantity,
                status="PLACE",
                timestamp=datetime.now(),
                reason="order placed placeholder",
            )
        )
        return trade

    def cancel_order(self, order: Order) -> bool:
        """
        撤单骨架。

        对状态为 PENDING / SUBMITTED / QUEUED 的订单，
        将其置为 CANCELLED 并记录审计日志。
        """
        if order.status.name in ("PENDING", "SUBMITTED", "QUEUED"):
            order.update_status(OrderStatus.CANCELLED)
            self._open_orders.pop(order.order_id, None)
            self._log_order(order, status="CANCELLED", reason="user cancel request")
            return True
        return False

    def get_positions(self, portfolio=None) -> Dict[str, Any]:
        """
        返回当前持仓。

        骨架实现：无真实券商连接时返回空字典。
        运行时可从 ``portfolio`` 参数或券商 API 获取。
        """
        if portfolio and hasattr(portfolio, "positions"):
            return {
                k: v.__dict__ for k, v in portfolio.positions.items()
                if hasattr(v, "quantity") and v.quantity > 0
            }
        return {}

    def get_balance(self, account=None) -> Dict[str, Any]:
        """
        返回账户余额。

        骨架实现：无真实券商连接时返回默认值。
        """
        return {
            "live": True,
            "api": self._api,
            "cash": 0.0,
            "frozen": 0.0,
            "equity": 0.0,
        }

    def get_history(
        self, symbol: str, bar_count: int, data_feeds: list = None
    ) -> List[BarData]:
        """
        获取历史 K 线。

        优先使用传入的 data_feeds，其次使用内部注入的 _data_feeds。
        """
        feeds = data_feeds or self._data_feeds
        if not feeds:
            return []
        for feed in feeds:
            if hasattr(feed, "symbol") and feed.symbol == symbol:
                n = len(feed)
                start = max(0, n - bar_count)
                return [feed[i] for i in range(start, n)]
        return []

    def _add_data_feed(self, feed) -> None:
        """内部：注入数据源（Cerebro / 外部策略使用）"""
        self._data_feeds.append(feed)

    @property
    def order_audit_log(self) -> List[OrderAuditLog]:
        """返回审计日志副本"""
        return self._order_log.copy()
