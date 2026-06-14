# -*- coding: utf-8 -*-
"""趋势指标 — MACD / OBV + 极值指标 HIGHEST / LOWEST"""

from __future__ import annotations

import numpy as np
from typing import List

from stockquant.indicators.base import Indicator, IndicatorProxy


class MACD(Indicator):
    """MACD 指标"""

    def __init__(self, data: List[float], fastperiod: int = 12,
                 slowperiod: int = 26, signalperiod: int = 9):
        self._data = np.array(data, dtype=float)
        self._fast = fastperiod
        self._slow = slowperiod
        self._signal = signalperiod

    @property
    def name(self) -> str:
        return "MACD"

    def calculate(self) -> dict:
        dif = self._ema(self._data, self._fast) - self._ema(self._data, self._slow)
        dea = self._ema(dif, self._signal)
        macd_hist = (dif - dea) * 2

        return {
            "dif": IndicatorProxy(list(dif)),
            "dea": IndicatorProxy(list(dea)),
            "macd": IndicatorProxy(list(macd_hist)),
        }

    @staticmethod
    def _ema(data: List[float], period: int) -> np.ndarray:
        arr = np.array(data, dtype=float)
        if len(arr) == 0:
            return arr
        result = np.full(len(arr), np.nan)
        result[0] = arr[0]
        mult = 2.0 / (period + 1)
        for i in range(1, len(arr)):
            result[i] = (arr[i] - result[i - 1]) * mult + result[i - 1]
        return result


class OBV(Indicator):
    """能量潮指标 (On-Balance Volume)"""

    def __init__(self, close: List[float], volume: List[float]):
        self._close = np.array(close, dtype=float)
        self._volume = np.array(volume, dtype=float)

    @property
    def name(self) -> str:
        return "OBV"

    def calculate(self) -> IndicatorProxy:
        n = len(self._close)
        result = np.zeros(n)
        for i in range(1, n):
            if self._close[i] > self._close[i - 1]:
                result[i] = result[i - 1] + self._volume[i]
            elif self._close[i] < self._close[i - 1]:
                result[i] = result[i - 1] - self._volume[i]
            else:
                result[i] = result[i - 1]
        return IndicatorProxy(list(result))


class HIGHEST(Indicator):
    """周期最高价"""

    def __init__(self, data: List[float], timeperiod: int = 20):
        self._data = np.array(data, dtype=float)
        self._period = timeperiod

    @property
    def name(self) -> str:
        return "HIGHEST"

    def calculate(self) -> IndicatorProxy:
        n = len(self._data)
        result = np.full(n, np.nan)
        for i in range(self._period - 1, n):
            result[i] = np.max(self._data[i - self._period + 1:i + 1])
        return IndicatorProxy(list(result))


class LOWEST(Indicator):
    """周期最低价"""

    def __init__(self, data: List[float], timeperiod: int = 20):
        self._data = np.array(data, dtype=float)
        self._period = timeperiod

    @property
    def name(self) -> str:
        return "LOWEST"

    def calculate(self) -> IndicatorProxy:
        n = len(self._data)
        result = np.full(n, np.nan)
        for i in range(self._period - 1, n):
            result[i] = np.min(self._data[i - self._period + 1:i + 1])
        return IndicatorProxy(list(result))


def VOLUME(data: List[float]) -> List[float]:
    """
    成交量 — 直接从原始数据提取。
    注意：这不是指标计算，而是数据提取。
    调用者应传入 volume 列数据。
    """
    return list(data)
