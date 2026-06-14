# -*- coding: utf-8 -*-
"""账户数据模型 — F003 Portfolio"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Account:
    """交易账户"""
    account_id: str = "default"

    initial_cash: float = 1_000_000.0
    cash: float = 1_000_000.0
    frozen_cash: float = 0.0      # 冻结资金（下单中）
    available_cash: float = 1_000_000.0

    total_equity: float = 1_000_000.0
    market_value: float = 0.0

    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    def update_equity(self, market_value: float):
        """更新总权益"""
        self.market_value = market_value
        self.total_equity = self.cash + market_value  # frozen_cash 已从 cash 中扣除，不应重复计算
        self.unrealized_pnl = self.total_equity - self.initial_cash - self.realized_pnl

    def freeze_cash(self, amount: float):
        """冻结资金（下单时）"""
        self.cash -= amount
        self.frozen_cash += amount
        self.available_cash = self.cash

    def release_cash(self, amount: float):
        """释放资金（撤单时）"""
        self.cash += amount
        self.frozen_cash -= amount
        self.available_cash = self.cash

    def deduct(self, amount: float):
        """扣减费用"""
        self.cash -= amount
        self.available_cash = self.cash

    def __repr__(self) -> str:
        return (f"Account({self.account_id} equity={self.total_equity:.2f} "
                f"cash={self.cash:.2f} frozen={self.frozen_cash:.2f})")
