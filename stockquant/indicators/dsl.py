# -*- coding: utf-8 -*-
"""F015 自定义指标 DSL"""

from __future__ import annotations

import numpy as np
from typing import Callable, List

from stockquant.indicators.base import Indicator, IndicatorProxy


def indicator(func: Callable) -> Callable:
    """
    装饰器：将普通函数转换为指标。

    Usage:
        @indicator
        def my_indicator(data, period=14):
            return [sum(data[max(0,i-period+1):i+1]) / min(period, i+1) for i in range(len(data))]

        # 自动注册为 IndicatorProxy
    """
    func._is_indicator = True
    func._name = func.__name__
    return func


def _is_indicator_func(func) -> bool:
    return getattr(func, "_is_indicator", False)


def apply_indicators(input_data: List[float], func: Callable) -> IndicatorProxy:
    """
    将装饰器函数应用到数据上。

    Usage:
        result = apply_indicators(prices, my_indicator)
    """
    values = func(list(np.array(input_data, dtype=float))) if hasattr(func, '__self__') else func(input_data)
    if isinstance(values, (list, np.ndarray)):
        return IndicatorProxy(list(values))
    return IndicatorProxy([values])
