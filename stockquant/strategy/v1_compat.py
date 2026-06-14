# -*- coding: utf-8 -*-
"""v1 兼容层 — 包装 v1 风格策略在 v2 引擎中运行（有限支持）"""

from stockquant.backtest_v1_compat import BackTestCompat, run_backtest_v1

__all__ = ["BackTestCompat", "run_backtest_v1"]
