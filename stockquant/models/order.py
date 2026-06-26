# -*- coding: utf-8 -*-
"""订单数据模型 — F002 OMS"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(Enum):
    BUY = "Buy"
    SELL = "Sell"
    SHORT = "Short"   # 融券卖出
    COVER = "Cover"   # 融券买入平仓


class OrderType(Enum):
    MARKET = "Market"     # 市价单
    LIMIT = "Limit"       # 限价单
    STOP = "Stop"         # 止损单
    STOP_LIMIT = "StopLimit"  # 止损限价单
    MARKET_ON_CLOSE = "MarketOnClose"  # 收盘市价单


# 从 events 模块导入统一事件类型
# 订单状态统一使用 EventType 中的 ORDER_XXX 值
from stockquant.events import EventType as OrderEventType


@dataclass
class Order:
    """订单数据类 — 状态统一使用 EventType.ORDER_XXX"""
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: float
    quantity: float
    order_id: str = ""
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    status: str = field(default=OrderEventType.ORDER_PENDING.value)
    timestamps: dict = field(default_factory=dict)
    _strategy_name: str = ""
    _exchange_order_id: str = ""

    def __post_init__(self):
        if not self.order_id:
            self.order_id = f"{self.symbol}_{self.side.value}_{id(self)}"
        self.timestamps["created"] = datetime.now()
        if self.status == OrderEventType.ORDER_SUBMITTED.value:
            self.timestamps["submitted"] = datetime.now()
        elif self.status == OrderEventType.ORDER_FILLED.value:
            self.timestamps["filled"] = datetime.now()

    @property
    def remaining(self) -> float:
        return self.quantity - self.filled_quantity

    @property
    def filled_ratio(self) -> float:
        if self.quantity == 0:
            return 0.0
        return self.filled_quantity / self.quantity

    def update_status(self, status: str) -> None:
        """更新订单状态（接受字符串值）"""
        self.status = status
        self.timestamps[str(status).lower().replace(" ", "_")] = datetime.now()

    def add_fill(self, quantity: float, price: float) -> None:
        """添加成交"""
        self.filled_quantity += quantity
        self.filled_price += price * quantity
        if self.filled_quantity >= self.quantity:
            self.filled_price = self.filled_price / self.filled_quantity if self.filled_quantity else 0
            self.update_status(OrderEventType.ORDER_FILLED.value)
        else:
            self.update_status(OrderEventType.ORDER_PARTIAL_FILL.value)

    def __repr__(self) -> str:
        return (f"Order({self.order_id} {self.side.value} {self.quantity}@"
                f"{self.price} [{self.status.value}])")
