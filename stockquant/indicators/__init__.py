# -*- coding: utf-8 -*-
"""技术指标包 — 18+ 指标，纯 numpy 实现"""

from stockquant.indicators.moving_avg import MA, EMA, KAMA, TRIX
from stockquant.indicators.oscillators import RSI, KDJ, CCI, ROC, STOCHRSI
from stockquant.indicators.volatility import BOLL, ATR, STDDEV, SAR
from stockquant.indicators.trend import MACD, OBV, HIGHEST, LOWEST, VOLUME
from stockquant.indicators.dsl import indicator, apply_indicators

__all__ = [
    # 移动平均
    "MA", "EMA", "KAMA", "TRIX",
    # 震荡指标
    "RSI", "KDJ", "CCI", "ROC", "STOCHRSI",
    # 波动率
    "BOLL", "ATR", "STDDEV", "SAR",
    # 趋势
    "MACD", "OBV", "HIGHEST", "LOWEST", "VOLUME",
    # DSL
    "indicator", "apply_indicators",
]
