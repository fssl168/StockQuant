# -*- coding: utf-8 -*-
"""F003 投资组合 Portfolio 聚合类"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from stockquant.models.account import Account
from stockquant.models.position import Position

logger = logging.getLogger(__name__)


class Portfolio:
    """
    投资组合聚合类。

    管理全局资金和所有持仓，支持多策略共享。
    """

    def __init__(
        self,
        initial_cash: float = 1_000_000,
        leverage: float = 1.0,
        margin_rate: float = 0.0,
        margin_call_threshold: float = 0.3,
    ):
        self._account = Account(
            account_id="default",
            initial_cash=initial_cash,
            cash=initial_cash,
            available_cash=initial_cash,
        )
        self._positions: Dict[str, Position] = {}
        self._leverage = leverage

        # 权益曲线
        self._equity_curve: List[float] = []
        self._peak_equity: float = initial_cash

        # 保证金相关
        self._margin_rate = margin_rate
        self._margin_call_threshold = margin_call_threshold
        self._borrowed_amount: float = 0.0
        self._margin_called: bool = False
        self._last_margin_interest_time: datetime = datetime.now()

    @property
    def account(self) -> Account:
        return self._account

    @property
    def positions(self) -> Dict[str, Position]:
        return self._positions

    @property
    def equity(self) -> float:
        return self._account.total_equity

    @property
    def cash(self) -> float:
        return self._account.cash

    @property
    def available_cash(self) -> float:
        return self._account.available_cash

    @property
    def market_value(self) -> float:
        return self._account.market_value

    @property
    def leverage(self) -> float:
        return self._leverage

    @property
    def borrowed_amount(self) -> float:
        """当前融券（借入）金额"""
        return self._borrowed_amount

    @property
    def is_margin_called(self) -> bool:
        """是否已触发警戒线"""
        return self._margin_called

    @property
    def margin_rate(self) -> float:
        return self._margin_rate

    @property
    def margin_call_threshold(self) -> float:
        return self._margin_call_threshold

    def calc_margin_interest(self, equity: Optional[float] = None, days: int = 1) -> float:
        """
        计算并扣除保证金利息。

        日利息 = 融券金额 * margin_rate / 252
        利息从 cash 中扣除。
        """
        if self._margin_rate <= 0 or self._borrowed_amount <= 0:
            return 0.0
        interest = self._borrowed_amount * self._margin_rate / 252 * days
        self._account.cash -= interest
        self._account.available_cash -= interest
        self._account.update_equity(sum(p.market_value for p in self._positions.values()))
        self._last_margin_interest_time = datetime.now()
        return interest

    def check_margin_call(self) -> bool:
        """
        检查是否触发警戒线。

        当 equity / initial_cash < (1 - margin_call_threshold) 时触发。
        """
        if self._account.initial_cash <= 0:
            return False
        ratio = self._account.total_equity / self._account.initial_cash
        if ratio < (1 - self._margin_call_threshold):
            self._margin_called = True
            logger.warning(
                "Margin call triggered: equity=%.2f / initial_cash=%.2f = %.4f < %.4f",
                self._account.total_equity,
                self._account.initial_cash,
                ratio,
                1 - self._margin_call_threshold,
            )
            return True
        return False

    def _update_borrowed(self):
        """更新融券金额 = max(0, 持仓市值 - cash)"""
        market_value = sum(p.market_value for p in self._positions.values())
        self._borrowed_amount = max(0.0, market_value - self._account.cash)

    def update_price(self, symbol: str, price: float):
        """更新某标的当前价格"""
        if symbol in self._positions:
            self._positions[symbol].update_price(price)
        self._recompute()

    def add_fill(self, symbol: str, quantity: float, price: float, is_today: bool = True):
        """成交后更新持仓"""
        if symbol not in self._positions:
            self._positions[symbol] = Position(symbol=symbol)
        self._positions[symbol].add_fill(quantity, price, is_today)
        # 保证金: 如果买入后持仓市值 > 现金, 差额为融券金额
        self._update_borrowed()
        self._recompute()

    def remove_position(self, symbol: str, quantity: float, price: float):
        """卖出扣减"""
        if symbol not in self._positions:
            return
        pos = self._positions[symbol]
        if pos.quantity < quantity:
            quantity = pos.quantity
        pos.subtract(quantity)
        # 已实现盈亏
        if pos.quantity == 0:
            self._account.realized_pnl += pos.realized_pnl
            # 释放冻结
            self._positions.pop(symbol, None)
        self._recompute()

    def unlock_all_frozen(self):
        """释放所有持仓的T+1冻结"""
        for pos in self._positions.values():
            pos.unlock_today_frozen()

    def _recompute(self):
        """重新计算权益"""
        # 先计算保证金利息（距上次计算的日数）
        self.calc_margin_interest()
        market_value = sum(p.market_value for p in self._positions.values())
        self._account.update_equity(market_value)
        # 追踪峰值
        if self._account.total_equity > self._peak_equity:
            self._peak_equity = self._account.total_equity

    def record_equity(self):
        """记录权益快照"""
        self._equity_curve.append(self._account.total_equity)

    @property
    def equity_curve(self) -> List[float]:
        return self._equity_curve

    @property
    def peak_equity(self) -> float:
        return self._peak_equity

    @property
    def drawdown(self) -> float:
        if self._peak_equity == 0:
            return 0.0
        return (self._peak_equity - self._account.total_equity) / self._peak_equity

    @property
    def num_positions(self) -> int:
        return len([p for p in self._positions.values() if p.quantity > 0])

    def get_position(self, symbol: str) -> Optional[Position]:
        return self._positions.get(symbol)

    def summary(self) -> dict:
        """投资组合摘要"""
        return {
            "equity": self._account.total_equity,
            "cash": self._account.cash,
            "market_value": self._account.market_value,
            "frozen_cash": self._account.frozen_cash,
            "available_cash": self._account.available_cash,
            "num_positions": self.num_positions,
            "drawdown": self.drawdown,
        }
