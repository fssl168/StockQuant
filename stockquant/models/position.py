# -*- coding: utf-8 -*-
"""持仓数据模型 — F003 Portfolio"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Position:
    """单标的持仓"""
    symbol: str
    direction: str = ""  # ""=long, "short"

    quantity: float = 0.0
    available: float = 0.0       # 可用数量（T+1约束后）
    cost_price: float = 0.0
    current_price: float = 0.0
    pnl: float = 0.0             # 未实现盈亏
    realized_pnl: float = 0.0    # 已实现盈亏

    # T+1 追踪
    today_frozen: float = 0.0    # 今日买入不可卖出数量

    def update_price(self, price: float):
        """更新当前价格"""
        self.current_price = price
        if self.quantity > 0:
            self.pnl = (price - self.cost_price) * self.quantity

    def add_fill(self, quantity: float, price: float, is_today: bool = True):
        """成交后更新持仓"""
        total_cost = self.cost_price * self.quantity + price * quantity
        self.quantity += quantity
        self.cost_price = total_cost / self.quantity if self.quantity else 0
        if is_today:
            self.today_frozen += quantity
        self.available = self.quantity - self.today_frozen

    def subtract(self, quantity: float):
        """卖出扣减（需T+1检查）"""
        self.quantity -= quantity
        self.available = self.quantity - self.today_frozen
        if self.today_frozen > 0:
            self.today_frozen = max(0, self.today_frozen - quantity)
        self.available = self.quantity  # T+1次日自动释放

    def unlock_today_frozen(self):
        """解除T+1冻结（次日调用）"""
        self.available = self.quantity
        self.today_frozen = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    def __repr__(self) -> str:
        return (f"Position({self.symbol} qty={self.quantity} "
                f"cost={self.cost_price:.2f} pnl={self.pnl:.2f})")
