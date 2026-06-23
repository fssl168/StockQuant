# -*- coding: utf-8 -*-
"""波动率指标 — BOLL / ATR / STDDEV / SAR"""

from __future__ import annotations

import numpy as np
from typing import List

from stockquant.indicators.base import Indicator, IndicatorProxy


class BOLL(Indicator):
    """布林带"""

    def __init__(self, data: List[float], timeperiod: int = 20, nbdev: int = 2):
        self._period = timeperiod
        self._nbdev = nbdev
        super().__init__(data)

    @property
    def name(self) -> str:
        return "BOLL"

    def _do_calculate(self, data) -> dict:
        arr = np.array(data, dtype=float)
        n = len(arr)
        upper = np.full(n, np.nan)
        middle = np.full(n, np.nan)
        lower = np.full(n, np.nan)

        for i in range(self._period - 1, n):
            window = arr[i - self._period + 1:i + 1]
            mean = np.mean(window)
            std = np.std(window, ddof=1)
            middle[i] = mean
            upper[i] = mean + self._nbdev * std
            lower[i] = mean - self._nbdev * std

        return {
            "upperband": IndicatorProxy(list(upper)),
            "middleband": IndicatorProxy(list(middle)),
            "lowerband": IndicatorProxy(list(lower)),
        }


class ATR(Indicator):
    """平均真实波幅"""

    def __init__(self, high: List[float], low: List[float], close: List[float], timeperiod: int = 14):
        self._high = np.array(high, dtype=float)
        self._low = np.array(low, dtype=float)
        self._period = timeperiod
        super().__init__(close)

    @property
    def name(self) -> str:
        return "ATR"

    def _do_calculate(self, data) -> IndicatorProxy:
        n = len(data)
        if n < 2:
            return IndicatorProxy([0.0] * n)

        result = np.full(n, np.nan)
        trs = np.zeros(n - 1)

        for i in range(1, n):
            tr = max(
                self._high[i] - self._low[i],
                abs(self._high[i] - data[i - 1]),
                abs(self._low[i] - data[i - 1]),
            )
            trs[i - 1] = tr

        # 第一个 ATR = 平均值
        if len(trs) < self._period:
            result[n - 1] = np.mean(trs) if len(trs) > 0 else 0
            return IndicatorProxy(list(result))

        result[self._period] = np.mean(trs[:self._period])

        # Wilder 平滑
        for i in range(self._period + 1, n):
            result[i] = (result[i - 1] * (self._period - 1) + trs[i - 1]) / self._period

        return IndicatorProxy(list(result))


class STDDEV(Indicator):
    """标准差"""

    def __init__(self, data: List[float], timeperiod: int = 20, nbdev: float = 1):
        self._period = timeperiod
        self._nbdev = nbdev
        super().__init__(data)

    @property
    def name(self) -> str:
        return "STDDEV"

    def _do_calculate(self, data) -> IndicatorProxy:
        arr = np.array(data, dtype=float)
        n = len(arr)
        result = np.full(n, np.nan)
        for i in range(self._period - 1, n):
            window = arr[i - self._period + 1:i + 1]
            std = np.std(window, ddof=1)
            result[i] = std * self._nbdev
        return IndicatorProxy(list(result))


class SAR(Indicator):
    """抛物线指标 (SAR/PAR)"""

    def __init__(self, high: List[float], low: List[float],
                 acceleration: float = 0.02, maximum: float = 0.2):
        self._high = np.array(high, dtype=float)
        self._acceleration = acceleration
        self._max_acceleration = maximum
        super().__init__(low)

    @property
    def name(self) -> str:
        return "SAR"

    def _do_calculate(self, data) -> IndicatorProxy:
        n = len(data)
        if n < 2:
            return IndicatorProxy([0.0] * n)

        result = np.zeros(n)
        # 简化：假设初始做多
        is_accelerating = True
        ep = data[0]  # 极值点
        af = self._acceleration  # 加速因子

        result[0] = data[0] + af * (self._high[0] - data[0])

        for i in range(1, n):
            if is_accelerating:
                # 上升趋势中的 SAR
                sar = result[i - 1]
                if data[i] < sar:
                    # 趋势反转
                    result[i] = ep
                    ep = data[i]
                    af = self._acceleration
                    is_accelerating = False
                else:
                    if self._high[i] > ep:
                        ep = self._high[i]
                        af = min(af + self._acceleration, self._max_acceleration)
                    high_range = ep - sar
                    result[i] = sar + af * high_range
            else:
                # 下降趋势中的 SAR
                sar = result[i - 1]
                if self._high[i] > sar:
                    result[i] = ep
                    ep = self._high[i]
                    af = self._acceleration
                    is_accelerating = True
                else:
                    if data[i] < ep:
                        ep = data[i]
                        af = min(af + self._acceleration, self._max_acceleration)
                    low_range = sar - ep
                    result[i] = sar - af * low_range

        return IndicatorProxy(list(result))
