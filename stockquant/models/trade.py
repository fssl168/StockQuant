# -*- coding: utf-8 -*-
"""成交数据"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TradeData:
    """成交记录"""
    trade_id: str = ""
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    price: float = 0.0
    quantity: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    timestamp: float = field(default_factory=datetime.now().timestamp)
    strategy_name: str = ""
    exchange_trade_id: str = ""

    @property
    def notional(self) -> float:
        return self.price * self.quantity
