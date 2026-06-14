# -*- coding: utf-8 -*-
"""震荡指标 — RSI / KDJ / CCI / ROC / STOCHRSI"""

from __future__ import annotations

import numpy as np
from typing import List

from stockquant.indicators.base import Indicator, IndicatorProxy


class RSI(Indicator):
    """相对强弱指标"""

    def __init__(self, data: List[float], timeperiod: int = 14):
        self._data = np.array(data, dtype=float)
        self._period = timeperiod

    @property
    def name(self) -> str:
        return "RSI"

    def calculate(self) -> IndicatorProxy:
        n = len(self._data)
        if n < self._period + 1:
            return IndicatorProxy([np.nan] * n)

        result = np.full(n, np.nan)
        deltas = np.diff(self._data)

        # 第一个 RSI
        gains = np.array([max(deltas[i], 0) for i in range(self._period)])
        losses = np.array([max(-deltas[i], 0) for i in range(self._period)])
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            result[self._period] = 100
        else:
            rs = avg_gain / avg_loss
            result[self._period] = 100 - (100 / (1 + rs))

        # Wilder 平滑
        for i in range(self._period + 1, n):
            delta = deltas[i - 1]
            avg_gain = (avg_gain * (self._period - 1) + max(delta, 0)) / self._period
            avg_loss = (avg_loss * (self._period - 1) + max(-delta, 0)) / self._period

            if avg_loss == 0:
                result[i] = 100
            else:
                rs = avg_gain / avg_loss
                result[i] = 100 - (100 / (1 + rs))

        return IndicatorProxy(list(result))


class KDJ(Indicator):
    """随机指标 KDJ (Stochastic)"""

    def __init__(
        self,
        high: List[float],
        low: List[float],
        close: List[float],
        fastk_period: int = 9,
        slowk_period: int = 3,
        slowd_period: int = 3,
    ):
        self._high = np.array(high, dtype=float)
        self._low = np.array(low, dtype=float)
        self._close = np.array(close, dtype=float)
        self._fastk = fastk_period
        self._slowk = slowk_period
        self._slowd = slowd_period

    @property
    def name(self) -> str:
        return "KDJ"

    def calculate(self) -> dict:
        n = len(self._close)
        k_values = np.full(n, np.nan)
        d_values = np.full(n, np.nan)

        for i in range(self._fastk - 1, n):
            hh = np.max(self._high[i - self._fastk + 1:i + 1])
            ll = np.min(self._low[i - self._fastk + 1:i + 1])
            diff = hh - ll
            k_values[i] = ((self._close[i] - ll) / diff * 100) if diff > 0 else 50.0

        # Smooth K
        k_smooth = np.full(n, np.nan)
        for i in range(self._slowk - 1, n):
            k_smooth[i] = np.mean(k_values[i - self._slowk + 1:i + 1])

        # Smooth D
        for i in range(self._slowd - 1, n):
            d_values[i] = np.mean(k_smooth[i - self._slowd + 1:i + 1])

        return {
            "k": IndicatorProxy(list(k_smooth)),
            "d": IndicatorProxy(list(d_values)),
        }


class CCI(Indicator):
    """顺势指标"""

    def __init__(self, high: List[float], low: List[float], close: List[float], timeperiod: int = 20):
        self._high = np.array(high, dtype=float)
        self._low = np.array(low, dtype=float)
        self._close = np.array(close, dtype=float)
        self._period = timeperiod

    @property
    def name(self) -> str:
        return "CCI"

    def calculate(self) -> IndicatorProxy:
        n = len(self._close)
        final_result = np.full(n, np.nan)

        for i in range(self._period - 1, n):
            tp = (self._high[i - self._period + 1:i + 1] +
                  self._low[i - self._period + 1:i + 1] +
                  self._close[i - self._period + 1:i + 1]) / 3
            mean_tp = np.mean(tp)
            md = np.mean(np.abs(tp - mean_tp))
            if md == 0:
                final_result[i] = 0
            else:
                final_result[i] = np.mean(tp) / (0.015 * md)
        return IndicatorProxy(list(final_result))


class ROC(Indicator):
    """变动率指标"""

    def __init__(self, data: List[float], timeperiod: int = 12):
        self._data = np.array(data, dtype=float)
        self._period = timeperiod

    @property
    def name(self) -> str:
        return "ROC"

    def calculate(self) -> IndicatorProxy:
        n = len(self._data)
        result = np.full(n, np.nan)
        for i in range(self._period, n):
            if self._data[i - self._period] != 0:
                result[i] = (self._data[i] - self._data[i - self._period]) / self._data[i - self._period] * 100
        return IndicatorProxy(list(result))


class STOCHRSI(Indicator):
    """随机 RSI"""

    def __init__(
        self,
        data: List[float],
        timeperiod: int = 14,
        fastk_period: int = 5,
        fastd_period: int = 3,
    ):
        self._data = np.array(data, dtype=float)
        self._timeperiod = timeperiod
        self._fastk = fastk_period
        self._fastd = fastd_period

    @property
    def name(self) -> str:
        return "STOCHRSI"

    def calculate(self) -> dict:
        # 先计算 RSI
        rsi_proxy = RSI(self._data, self._timeperiod).calculate()
        rsi_values = list(rsi_proxy)

        n = len(rsi_values)
        stochrsi = np.full(n, np.nan)
        fastk = np.full(n, np.nan)

        for i in range(self._timeperiod + self._fastk - 1, n):
            window = rsi_values[i - self._fastk + 1:i + 1]
            hh = np.max(window)
            ll = np.min(window)
            diff = hh - ll
            stochrsi[i] = ((rsi_values[i] - ll) / diff * 100) if diff > 0 else 50.0

        # Smooth fastK
        for i in range(self._fastd - 1, n):
            fastk[i] = np.mean(stochrsi[i - self._fastd + 1:i + 1])

        return {
            "stochrsi": IndicatorProxy(list(stochrsi)),
            "fastk": IndicatorProxy(list(fastk)),
        }
