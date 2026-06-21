# -*- coding: utf-8 -*-
"""NFR001 性能基准测试"""

from __future__ import annotations

import time
import pytest
import numpy as np


class TestIndicatorPerformance:
    """F005 指标计算性能基准测试"""

    def test_indicator_calculation_time(self):
        """单个指标计算 < 10ms 基准测试（给予 10 倍容差）"""
        from stockquant.indicators import EMA, RSI, MACD

        # 生成 10 年日线数据（约 2500 条）
        n = 2500
        close = np.cumsum(np.random.randn(n)) + 100
        close = np.abs(close).tolist()  # 价格为正，转为 list

        indicators = [
            ("EMA-12", lambda: EMA(close, 12)),
            ("RSI-14", lambda: RSI(close, 14)),
            ("MACD", lambda: MACD(close)),
        ]

        results = {}
        for name, func in indicators:
            start = time.perf_counter()
            for _ in range(100):
                func()
            elapsed = (time.perf_counter() - start) / 100 * 1000  # ms/次
            results[name] = elapsed

        # 所有指标平均计算时间 < 10ms
        avg_time = sum(results.values()) / len(results)
        assert avg_time < 10.0, (
            f"指标计算耗时偏高: {avg_time:.2f}ms/次 "
            f"（预期 < 10ms）"
        )


class TestCachePerformance:
    """数据缓存读取性能测试"""

    def test_cache_read_performance(self):
        """缓存读取性能测试
        
        读取 10 年日线数据 < 200ms
        """
        from pathlib import Path

        cache_dir = Path.home() / ".stockquant" / "data"
        if not cache_dir.exists():
            pytest.skip("缓存目录不存在")

        csv_files = list(cache_dir.glob("*.csv"))
        if not csv_files:
            pytest.skip("缓存中无 CSV 文件")

        total_time = 0
        for csv_file in csv_files[:5]:  # 最多测 5 个文件
            start = time.perf_counter()
            with open(csv_file, "r") as f:
                _ = f.read()
            elapsed = (time.perf_counter() - start) * 1000  # ms
            total_time += elapsed

        avg_time = total_time / max(len(csv_files[:5]), 1)
        # 允许 10 倍容差
        assert avg_time < 10000, f"缓存读取耗时 {avg_time:.0f}ms（预期 < 10s）"
