# -*- coding: utf-8 -*-
"""v1 兼容层实现"""

from typing import List, Optional

import pandas as pd

from stockquant.engine import Cerebro, BacktestBroker
from stockquant.engine.commission import CommissionInfo, FixedSlippage
from stockquant.models.bar import BarData
from stockquant.strategy.base import BaseStrategy


class BackTestCompat:
    """
    v1 BackTest 类的兼容包装。

    将 v1 的手动逐 Bar 循环模式包装为 v2 的回调模式。
    仅支持单标的日线回测。
    """

    def __init__(self, cash: float = 1_000_000):
        self._cerebro = Cerebro(cash=cash, broker=BacktestBroker(), commission=CommissionInfo())
        self._v1_strategy: Optional[object] = None
        self._symbol: str = ""
        self._kline_history: List[List[float]] = {
            "open": [], "high": [], "low": [], "close": [], "volume": [],
        }

    def initialize(self, kline: list):
        """
        v1 兼容：递增传入 K 线数据。

        内部自动累积 kline，当检测到新 Bar 时触发 on_bar。
        """
        if not kline or len(kline) < 2:
            return

        # 累积数据
        for row in kline:
            if len(row) >= 6:
                self._kline_history["open"].append(float(row[0]))
                self._kline_history["high"].append(float(row[2]))
                self._kline_history["low"].append(float(row[3]))
                self._kline_history["close"].append(float(row[4]))
                self._kline_history["volume"].append(float(row[5]))

    def run(self) -> dict:
        """运行回测，返回结果"""
        closes = self._kline_history["close"]
        if len(closes) < 20:  # 至少需要 20 根 K 线
            return {"error": "Insufficient data"}

        # 创建临时策略包装 v1 对象
        class _V1Wrapper(BaseStrategy):
            def __init__(self, v1_obj, cerebro_inst):
                super().__init__(cerebro_inst)
                self._v1 = v1_obj
                self._closes = []
                self._highs = []
                self._lows = []
                self._volumes = []
                self._bar_count = 0

            def on_start(self):
                if hasattr(self._v1, "on_start"):
                    self._v1.on_start()

            def on_bar(self, bars):
                self._closes.append(bars["close"])
                self._highs.append(bars["high"])
                self._lows.append(bars["low"])
                self._volumes.append(bars["volume"])

                # 构建 v1 兼容的 kline 格式
                kline = list(zip(
                    range(self._bar_count),
                    self._closes,
                    self._highs,
                    self._lows,
                    self._closes,
                    self._volumes,
                ))
                self._bar_count += 1

                # 调用 v1 策略逻辑
                if hasattr(self._v1, "initialize"):
                    self._v1.initialize(kline)
                if hasattr(self._v1, "before_start"):
                    self._v1.before_start()
                if hasattr(self._v1, "after_start"):
                    self._v1.after_start()

            def on_finish(self):
                if hasattr(self._v1, "after_start"):
                    self._v1.after_start()

        # 创建一个空策略对象
        class DummyV1Strategy:
            pass

        v1_obj = DummyV1Strategy()
        wrapper = _V1Wrapper(v1_obj, self._cerebro)

        # 运行
        result = self._cerebro.run()
        return result


def run_backtest_v1(kline: list, symbol: str = "test", cash: float = 1_000_000) -> dict:
    """
    快捷函数：用 v1 风格运行回测。

    Parameters
    ----------
    kline : list
        K 线数据列表
    symbol : str
        标的代码
    cash : float
        初始资金

    Returns
    -------
    dict
        回测结果
    """
    bt = BackTestCompat(cash=cash)
    bt.initialize(kline)
    return bt.run()
