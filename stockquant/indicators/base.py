# -*- coding: utf-8 -*-
"""指标基类与代理"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional


class Indicator(ABC):
    """指标抽象基类"""

    @abstractmethod
    def calculate(self, data: List[float]) -> List[float]:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class IndicatorProxy:
    """
    指标结果代理，支持 __getitem__ 访问历史值。

    Usage:
        ema = self.EMA(prices, period=12)
        current = ema[0]        # 最新值
        prev = ema[-1]          # 前一根
        series = list(ema)      # 转为列表
    """

    def __init__(self, values: List[float]):
        self._values = values

    def __getitem__(self, key: int) -> float:
        n = len(self._values)
        if n == 0:
            return 0.0
        # 支持负索引
        idx = key if key >= 0 else n + key
        if idx < 0 or idx >= n:
            return 0.0  # NaN 缺失值
        v = self._values[idx]
        if v is None or (isinstance(v, float) and (v != v)):  # NaN check
            return 0.0
        return float(v)

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self):
        return iter(self._values)

    def __repr__(self) -> str:
        n = len(self._values)
        return f"IndicatorProxy([{self._values[0] if n > 0 else 0}... ({n} values)])"

    @property
    def current(self) -> float:
        return self[-1]

    def crossed_above(self, other: "IndicatorProxy") -> bool:
        """当前值上穿 other"""
        return self[-1] > other[-1] and self[-2] <= other[-2]

    def crossed_below(self, other: "IndicatorProxy") -> bool:
        """当前值下穿 other"""
        return self[-1] < other[-1] and self[-2] >= other[-2]
