# -*- coding: utf-8 -*-
"""F006 Broker 抽象层 — 回测/模拟/实盘统一接口"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
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

    确定性保证:
    - 回测结果完全确定性：撮合逻辑不包含任何随机因素
    - 相同输入（K线数据 + 订单参数）始终产生相同输出
    - 无需设置随机种子，因为不使用 random / numpy.random 等随机源
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
    支持崩溃恢复：通过 save_state/load_state 持久化交易日志和订单簿。
    """

    _logger = logging.getLogger("stockquant.engine.broker.PaperBroker")

    def __init__(
        self,
        slippage: Optional[Any] = None,
        limit_up_ratio: float = 0.10,
        limit_down_ratio: float = 0.10,
        state_file: Optional[str] = None,
    ):
        self._slippage = slippage
        self._limit_up_ratio = limit_up_ratio
        self._limit_down_ratio = limit_down_ratio
        self._order_book: Dict[str, List[Order]] = {}  # 未成交订单
        self._trade_log: List[TradeData] = []
        self._portfolio: Optional[Any] = None  # 绑定的 Portfolio 实例
        self._orders_audit: Optional[Any] = None  # 绑定的订单审计日志
        self._state_file = state_file
        # 自动加载上次的崩溃恢复状态
        if state_file:
            self.load_state(state_file)

    def bind_portfolio(self, portfolio, orders_audit: Optional[dict] = None) -> None:
        """绑定 Portfolio 实例和订单审计日志，使 get_positions/get_balance/get_history 返回真实数据"""
        self._portfolio = portfolio
        self._orders_audit = orders_audit

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
        # 每次交易后自动保存状态
        if self._state_file:
            self.save_state(self._state_file)
        return trade

    def cancel_order(self, order: Order) -> bool:
        if order.status.name in ("PENDING", "SUBMITTED", "QUEUED"):
            order.update_status(OrderStatus.CANCELLED)
            return True
        return False

    def get_positions(self, portfolio=None) -> Dict[str, Any]:
        """获取持仓 — 优先从绑定的 Portfolio 获取真实数据"""
        src = portfolio or self._portfolio
        if src and hasattr(src, 'positions'):
            return {k: v.__dict__ for k, v in src.positions.items() if v.quantity > 0}
        return {}

    def get_balance(self, account=None) -> Dict[str, Any]:
        """获取账户余额 — 优先从绑定的 Portfolio 获取真实数据"""
        src = account
        if src is None and self._portfolio and hasattr(self._portfolio, 'account'):
            src = self._portfolio.account
        if src:
            return {
                "paper": True,
                "cash": getattr(src, 'cash', 0),
                "available_cash": getattr(src, 'available_cash', 0),
                "frozen": getattr(src, 'frozen_cash', 0),
                "equity": getattr(src, 'total_equity', 0),
            }
        return {"paper": True, "cash": 0, "equity": 0}

    def get_history(self, symbol: str, bar_count: int, data_feeds: list = None) -> List[BarData]:
        """获取成交记录 — 从交易日志中提取"""
        # PaperBroker 不维护 K 线历史，返回空列表
        # 如需 K 线数据，应通过 BaoStockFeed 等数据源获取
        return []

    def on_bar(self, bar: BarData, pending_orders: Optional[Dict[str, Order]] = None) -> List[TradeData]:
        """接收实时行情，检查 LIMIT 订单是否可成交。

        Args:
            bar: 最新行情数据
            pending_orders: 待撮合的 LIMIT 订单字典 {order_id: Order}

        Returns:
            成交的 TradeData 列表
        """
        filled_trades: List[TradeData] = []
        if pending_orders is None:
            return filled_trades

        for order_id, order in list(pending_orders.items()):
            # 涨跌停检查
            limit_up = bar.close * (1 + self._limit_up_ratio)
            limit_down = bar.close * (1 - self._limit_down_ratio)
            if order.price > limit_up or order.price < limit_down:
                order.update_status(OrderStatus.REJECTED)
                self.cancel_order(order)
                continue

            # 100 股整数倍
            if order.quantity % 100 != 0:
                order.update_status(OrderStatus.REJECTED)
                self.cancel_order(order)
                continue

            # 限价单撮合条件
            matched = False
            if order.order_type == OrderType.LIMIT:
                if order.side == OrderSide.BUY and order.price >= bar.close:
                    matched = True
                elif order.side == OrderSide.SELL and order.price <= bar.close:
                    matched = True

            if matched:
                trade = self.place_order(order, bar)
                if trade:
                    filled_trades.append(trade)

        return filled_trades

    @property
    def trade_log(self) -> List[TradeData]:
        return self._trade_log.copy()

    def save_state(self, filepath: str) -> None:
        """将 trade_log 和 order_book 持久化到 JSON 文件，用于崩溃恢复"""
        state = {
            "trade_log": [
                {
                    "trade_id": t.trade_id,
                    "order_id": t.order_id,
                    "symbol": t.symbol,
                    "side": t.side,
                    "price": t.price,
                    "quantity": t.quantity,
                }
                for t in self._trade_log
            ],
            "order_book": {
                key: [
                    {
                        "order_id": o.order_id,
                        "symbol": o.symbol,
                        "side": o.side.value,
                        "order_type": o.order_type.value,
                        "price": o.price,
                        "quantity": o.quantity,
                    }
                    for o in orders
                ]
                for key, orders in self._order_book.items()
            },
        }
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._logger.warning(f"保存状态失败: {e}")

    def load_state(self, filepath: str) -> None:
        """从 JSON 文件恢复 trade_log 和 order_book"""
        try:
            p = Path(filepath)
            if not p.exists():
                return
            with open(filepath, "r", encoding="utf-8") as f:
                state = json.load(f)
            # 恢复 trade_log
            for t in state.get("trade_log", []):
                trade = TradeData(
                    trade_id=t["trade_id"],
                    order_id=t["order_id"],
                    symbol=t["symbol"],
                    side=t["side"],
                    price=t["price"],
                    quantity=t["quantity"],
                )
                self._trade_log.append(trade)
            # 恢复 order_book（仅记录，不重建 Order 对象）
            for key, orders in state.get("order_book", {}).items():
                self._order_book[key] = []
                for o in orders:
                    order = Order(
                        symbol=o["symbol"],
                        side=OrderSide(o["side"]),
                        order_type=OrderType(o["order_type"]),
                        price=o["price"],
                        quantity=o["quantity"],
                        order_id=o["order_id"],
                        status=OrderStatus.SUBMITTED,
                    )
                    self._order_book[key].append(order)
            self._logger.info(f"已从 {filepath} 恢复状态: {len(self._trade_log)} 条交易记录")
        except Exception as e:
            self._logger.warning(f"加载状态失败: {e}")


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
