# -*- coding: utf-8 -*-
"""移动平均指标 — MA / EMA / KAMA / TRIX"""

from __future__ import annotations

import numpy as np
from typing import List

from stockquant.indicators.base import Indicator, IndicatorProxy


class MA(Indicator):
    """简单移动平均"""

    def __init__(self, data: List[float], period: int = 20):
        self._data = np.array(data, dtype=float)
        self._period = period

    @property
    def name(self) -> str:
        return "MA"

    def calculate(self) -> IndicatorProxy:
        n = len(self._data)
        result = np.full(n, np.nan)
        for i in range(self._period - 1, n):
            result[i] = np.mean(self._data[i - self._period + 1:i + 1])
        return IndicatorProxy(list(result))


class EMA(Indicator):
    """指数移动平均"""

    def __init__(self, data: List[float], period: int = 12):
        self._data = np.array(data, dtype=float)
        self._period = period

    @property
    def name(self) -> str:
        return "EMA"

    def calculate(self) -> IndicatorProxy:
        n = len(self._data)
        result = np.full(n, np.nan)
        if n == 0:
            return IndicatorProxy([])
        result[0] = self._data[0]
        multiplier = 2.0 / (self._period + 1)
        for i in range(1, n):
            result[i] = (self._data[i] - result[i - 1]) * multiplier + result[i - 1]
        return IndicatorProxy(list(result))


class KAMA(Indicator):
    """适应性移动平均线 (Kaufman Adaptive MA)"""

    def __init__(self, data: List[float], period: int = 30):
        self._data = np.array(data, dtype=float)
        self._period = period

    @property
    def name(self) -> str:
        return "KAMA"

    def calculate(self) -> IndicatorProxy:
        n = len(self._data)
        if n < self._period + 1:
            return IndicatorProxy([np.nan] * n)

        result = np.full(n, np.nan)
        result[0] = self._data[0]

        fast_smoothing = 2.0 / (2 + 1)
        slow_smoothing = 2.0 / (self._period + 1)

        for i in range(self._period, n):
            # 计算变化率
            change = abs(self._data[i] - self._data[i - self._period])
            volatility_sum = sum(abs(self._data[i - j] - self._data[i - j - 1])
                                 for j in range(self._period))

            efficiency_ratio = change / volatility_sum if volatility_sum > 0 else 0

            # 平滑系数
            smoothing = (efficiency_ratio * (fast_smoothing - slow_smoothing) + slow_smoothing) ** 2

            result[i] = smoothing * self._data[i] + (1 - smoothing) * result[i - 1]

        return IndicatorProxy(list(result))


class TRIX(Indicator):
    """三重指数平滑平均线"""

    def __init__(self, data: List[float], period: int = 15):
        self._data = np.array(data, dtype=float)
        self._period = period

    @property
    def name(self) -> str:
        return "TRIX"

    def calculate(self) -> IndicatorProxy:
        result = self._triple_ema(self._data, self._period)
        # TRIX = (result - prev_result) / prev_result * 100
        output = np.full(len(result), np.nan)
        for i in range(1, len(result)):
            if result[i - 1] != 0:
                output[i] = (result[i] - result[i - 1]) / result[i - 1] * 100
        return IndicatorProxy(list(output))

    @staticmethod
    def _triple_ema(data: np.ndarray, period: int) -> np.ndarray:
        """计算三重EMA"""
        ema1 = EMA(data, period).calculate()
        ema2 = EMA(list(ema1), period).calculate()
        ema3 = EMA(list(ema2), period).calculate()
        return np.array(ema3)
