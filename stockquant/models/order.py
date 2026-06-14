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


class OrderStatus(Enum):
    PENDING = "Pending"
    SUBMITTED = "Submitted"
    QUEUED = "Queued"
    PARTIAL = "Partial"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"


@dataclass
class Order:
    """订单数据类"""
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: float
    quantity: float
    order_id: str = ""
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    status: OrderStatus = field(default=OrderStatus.PENDING)
    timestamps: dict = field(default_factory=dict)
    _strategy_name: str = ""
    _exchange_order_id: str = ""

    def __post_init__(self):
        if not self.order_id:
            self.order_id = f"{self.symbol}_{self.side.value}_{id(self)}"
        self.timestamps["created"] = datetime.now()
        if self.status == OrderStatus.SUBMITTED:
            self.timestamps["submitted"] = datetime.now()
        elif self.status == OrderStatus.FILLED:
            self.timestamps["filled"] = datetime.now()

    @property
    def remaining(self) -> float:
        return self.quantity - self.filled_quantity

    @property
    def filled_ratio(self) -> float:
        if self.quantity == 0:
            return 0.0
        return self.filled_quantity / self.quantity

    def update_status(self, status: OrderStatus):
        """更新订单状态"""
        self.status = status
        self.timestamps[str(status.value).lower()] = datetime.now()

    def add_fill(self, quantity: float, price: float):
        """添加成交"""
        self.filled_quantity += quantity
        self.filled_price += price * quantity
        if self.filled_quantity >= self.quantity:
            self.filled_price = self.filled_price / self.filled_quantity if self.filled_quantity else 0
            self.update_status(OrderStatus.FILLED)
        else:
            self.update_status(OrderStatus.PARTIAL)

    def __repr__(self) -> str:
        return (f"Order({self.order_id} {self.side.value} {self.quantity}@"
                f"{self.price} [{self.status.value}])")
