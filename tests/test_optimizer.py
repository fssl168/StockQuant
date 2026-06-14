# -*- coding: utf-8 -*-
"""F008 参数优化器测试"""

import os
import tempfile

import numpy as np
import pytest

from stockquant import Cerebro, BacktestBroker, CSVFeed, CommissionInfo
from stockquant.engine.sizer import FixedFractionSizer
from stockquant.strategy.base import BaseStrategy


class TestParameterOptimizer:
    """参数优化功能测试"""

    @pytest.fixture
    def test_csv(self):
        """创建测试 CSV（有趋势的数据以产生可区分结果）"""
        csv_content = "timestamp,open,high,low,close,volume\n"
        price = 100.0
        for i in range(100):
            dt = f"2024-{(i // 30) + 1:02d}-{(i % 28) + 1:02d}"
            csv_content += f"{dt},{price:.2f},{price+1:.2f},{price-1:.2f},{price:.2f},{1000000}\n"
            price *= 1.001  # 微弱上升趋势
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_content)
            path = f.name
        try:
            yield path
        finally:
            os.unlink(path)

    @pytest.fixture
    def cerebro_with_strategy(self, test_csv):
        """创建带测试策略的 Cerebro"""
        class MAStrategy(BaseStrategy):
            name = "MA Test"
            parameters = {
                "fast_period": 5,
                "slow_period": 20,
            }
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self._price_history = {}

            def on_bar(self, bars):
                for symbol, bar in bars.items():
                    if symbol not in self._price_history:
                        self._price_history[symbol] = []
                    self._price_history[symbol].append(bar.close)
                    closes = self._price_history[symbol]
                    if len(closes) < 20:
                        return

        feed = CSVFeed(test_csv, symbol="test", timeframe="1d")
        cerebro = Cerebro(cash=1_000_000, broker=BacktestBroker(), commission=CommissionInfo())
        cerebro.add_data(feed)
        return cerebro, MAStrategy

    def test_optstrategy_grid_search(self, cerebro_with_strategy):
        """网格搜索优化"""
        cerebro, strategy_cls = cerebro_with_strategy

        results = cerebro.optstrategy(
            strategy_cls,
            param_grid={
                "fast_period": [3, 5],
                "slow_period": [10, 15],
            },
            optimizer="grid",
            target="Sharpe Ratio",
            n_jobs=1,
        )

        # 2x2 = 4 种参数组合
        assert len(results) == 4
        assert all("params" in r and "metrics" in r for r in results)
        assert all("fast_period" in r["params"] for r in results)
        assert all("slow_period" in r["params"] for r in results)

    def test_optstrategy_random_search(self, cerebro_with_strategy):
        """随机搜索优化"""
        cerebro, strategy_cls = cerebro_with_strategy

        results = cerebro.optstrategy(
            strategy_cls,
            param_grid={
                "fast_period": [3, 5, 8],
                "slow_period": [10, 15, 20],
            },
            optimizer="random",
            max_iters=5,
            target="Sharpe Ratio",
            n_jobs=1,
        )

        assert len(results) == 5
        for r in results:
            assert r["params"]["fast_period"] in [3, 5, 8]
            assert r["params"]["slow_period"] in [10, 15, 20]

    def test_optstrategy_sorting(self, cerebro_with_strategy):
        """验证结果按目标指标排序"""
        cerebro, strategy_cls = cerebro_with_strategy

        results = cerebro.optstrategy(
            strategy_cls,
            param_grid={
                "fast_period": [3, 5, 8, 10],
                "slow_period": [10, 15, 20, 30],
            },
            optimizer="grid",
            target="Total Return",
            n_jobs=1,
        )

        assert len(results) > 1
        # 按 Total Return 降序排列
        for i in range(len(results) - 1):
            v1 = results[i]["metrics"].get("Total Return", "0%")
            v2 = results[i + 1]["metrics"].get("Total Return", "0%")
            # 字符串比较（% 格式）
            assert v1 >= v2 or v1 == v2

    def test_optstrategy_top_n(self, cerebro_with_strategy):
        """验证返回结果"""
        cerebro, strategy_cls = cerebro_with_strategy

        results = cerebro.optstrategy(
            strategy_cls,
            param_grid={
                "fast_period": [3, 5],
                "slow_period": [10, 15],
            },
            optimizer="grid",
            n_jobs=1,
        )

        assert len(results) >= 1
        assert len(results) <= 4
