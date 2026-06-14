# -*- coding: utf-8 -*-
"""F007 佣金与滑点建模 — A 股市场真实费用"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CommissionInfo:
    """
    A 股佣金/印花税/过户费模型。

    买入: 佣金 + 过户费
    卖出: 佣金 + 印花税(0.05%) + 过户费
    """

    commission_rate: float = 0.00025   # 佣金 0.025%
    min_commission: float = 5.0         # 最低佣金 5 元
    stamp_tax_rate: float = 0.0005      # 印花税 0.05%（卖方）
    transfer_fee_rate: float = 0.00001  # 过户费 0.001%

    def calc_buy_cost(self, notional: float) -> float:
        """计算买入费用"""
        commission = max(notional * self.commission_rate, self.min_commission)
        transfer_fee = notional * self.transfer_fee_rate
        return commission + transfer_fee

    def calc_sell_cost(self, notional: float) -> float:
        """计算卖出费用"""
        commission = max(notional * self.commission_rate, self.min_commission)
        stamp_tax = notional * self.stamp_tax_rate
        transfer_fee = notional * self.transfer_fee_rate
        return commission + stamp_tax + transfer_fee

    def calc_total_cost(self, notional: float, side: str) -> float:
        """计算总费用"""
        if side == "buy":
            return self.calc_buy_cost(notional)
        return self.calc_sell_cost(notional)


class SlippageModel(ABC):
    """滑点模型抽象基类"""

    @abstractmethod
    def apply(self, price: float, side: str) -> float:
        """
        应用滑点。

        Parameters
        ----------
        price : float
            原始价格
        side : str
            "buy" 或 "sell"

        Returns
        -------
        float
            滑点后的执行价格
        """
        ...


class FixedSlippage(SlippageModel):
    """固定滑点"""

    def __init__(self, slip: float = 0.01):
        self._slip = slip

    def apply(self, price: float, side: str) -> float:
        if side == "buy":
            return price + self._slip
        return price - self._slip


class PercentSlippage(SlippageModel):
    """百分比滑点"""

    def __init__(self, percent: float = 0.001):
        self._percent = percent

    def apply(self, price: float, side: str) -> float:
        slip = price * self._percent
        if side == "buy":
            return price + slip
        return price - slip


class AdaptiveSlippage(SlippageModel):
    """
    基于成交量自适应滑点。
    成交量占当日成交量的比例越大，滑点越大。
    """

    def __init__(self, base_slip_pct: float = 0.0005, volume_factor: float = 0.01):
        self._base_slip_pct = base_slip_pct
        self._volume_factor = volume_factor

    def apply(self, price: float, side: str, volume_ratio: float = 1.0) -> float:
        slip = price * (self._base_slip_pct + self._volume_factor * volume_ratio)
        if side == "buy":
            return price + slip
        return price - slip
