# -*- coding: utf-8 -*-
"""F010 仓位管理模块"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class PositionSizer(ABC):
    """仓位管理器抽象基类"""

    @abstractmethod
    def calculate(self, cash: float, price: float, portfolio_equity: float) -> int:
        """
        计算买入数量。

        Parameters
        ----------
        cash : float
            可用现金
        price : float
            当前价格
        portfolio_equity : float
            总资产权益

        Returns
        -------
        int
            买入数量（100 的整数倍）
        """
        ...


class FixedFractionSizer(PositionSizer):
    """固定比例仓位"""

    def __init__(self, fraction: float = 0.1):
        """
        Parameters
        ----------
        fraction : float
            每次投入总资金的比例（0.1 = 10%）
        """
        self._fraction = fraction

    def calculate(self, cash: float, price: float, portfolio_equity: float) -> int:
        if price <= 0:
            return 0
        target_value = portfolio_equity * self._fraction
        quantity = int(target_value / price)
        return (quantity // 100) * 100  # 100 股整数倍


class KellySizer(PositionSizer):
    """凯利公式仓位"""

    def __init__(self, win_rate: float = 0.55, win_loss_ratio: float = 1.5):
        """
        Parameters
        ----------
        win_rate : float
            历史胜率
        win_loss_ratio : float
            盈亏比
        """
        self._win_rate = win_rate
        self._win_loss_ratio = win_loss_ratio

    def calculate(self, cash: float, price: float, portfolio_equity: float) -> int:
        if price <= 0:
            return 0

        # Kelly % = W - (1-W)/R
        kelly = self._win_rate - (1 - self._win_rate) / self._win_loss_ratio
        kelly = max(0, kelly)  # 不能为负

        # 半凯利（更保守）
        half_kelly = kelly * 0.5
        target_value = portfolio_equity * half_kelly
        quantity = int(target_value / price)
        return (quantity // 100) * 100


class ATRSizer(PositionSizer):
    """基于 ATR 的波动率仓位"""

    def __init__(self, risk_per_unit: float = 0.02):
        """
        Parameters
        ----------
        risk_per_unit : float
            每单位 ATR 的风险比例
        """
        self._risk_per_unit = risk_per_unit

    def calculate(self, cash: float, price: float, portfolio_equity: float,
                  atr: Optional[float] = None) -> int:
        if price <= 0:
            return 0

        # 默认 ATR 为价格的 2%（如果未提供）
        if atr is None:
            atr = price * 0.02

        risk_amount = portfolio_equity * self._risk_per_unit
        quantity = int(risk_amount / atr)
        return (quantity // 100) * 100


class VolatilityTargetSizer(PositionSizer):
    """波动率目标仓位"""

    def __init__(self, target_vol: float = 0.20):
        """
        Parameters
        ----------
        target_vol : float
            目标年化波动率（0.20 = 20%）
        """
        self._target_vol = target_vol

    def calculate(self, cash: float, price: float, portfolio_equity: float,
                  historical_vol: Optional[float] = None) -> int:
        if price <= 0:
            return 0

        # 默认波动率 20%
        if historical_vol is None:
            historical_vol = self._target_vol

        # 目标风险金额 = 权益 * (目标波动率 / 实际波动率)
        risk_pct = self._target_vol / historical_vol if historical_vol > 0 else 0.2
        risk_pct = min(risk_pct, 1.0)  # 不超过 100%
        target_value = portfolio_equity * risk_pct
        quantity = int(target_value / price)
        return (quantity // 100) * 100


class EqualWeightSizer(PositionSizer):
    """等权重分配"""

    def __init__(self, n_assets: int = 10):
        """
        Parameters
        ----------
        n_assets : int
            目标持仓股票数量
        """
        self._n_assets = n_assets

    def calculate(self, cash: float, price: float, portfolio_equity: float) -> int:
        if price <= 0:
            return 0
        target_value = portfolio_equity / self._n_assets
        quantity = int(target_value / price)
        return (quantity // 100) * 100
