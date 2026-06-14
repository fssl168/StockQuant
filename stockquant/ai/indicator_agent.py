# -*- coding: utf-8 -*-
"""F021 AI 指标发现 Agent — 自动推荐最优技术指标和参数组合"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np


class MarketState(Enum):
    """市场状态"""
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


@dataclass
class IndicatorScore:
    """指标评分结果"""
    name: str
    win_rate: float = 0.0
    signal_count: int = 0
    snr: float = 0.0           # 信噪比
    profit_factor: float = 0.0  # 盈亏比
    score: float = 0.0          # 综合评分


class MarketStateDetector:
    """
    从历史价格/成交量数据检测当前市场状态。

    判断逻辑：
    - 高波动: ATR(14)/close > 0.03
    - 低波动: ATR(14)/close < 0.01
    - 趋势: MA(20) 线性回归斜率显著（> 0.5%）
    - 震荡: 价格区间窄且趋势斜率不显著
    """

    def __init__(
        self,
        atr_period: int = 14,
        ma_period: int = 20,
        trend_threshold: float = 0.005,
        range_threshold: float = 0.05,
    ):
        self.atr_period = atr_period
        self.ma_period = ma_period
        self.trend_threshold = trend_threshold
        self.range_threshold = range_threshold

    def _atr(self, close: np.ndarray, period: int) -> np.ndarray:
        """计算 ATR"""
        if len(close) < period + 1:
            return np.array([0.0])
        high = np.convolve(close, np.ones(period), mode='valid') / period
        low = np.convolve(close, np.ones(period), mode='valid') / period
        return close[-1] - close[-period]

    def _ma_slope(self, close: np.ndarray, period: int) -> float:
        """计算 MA 线性回归斜率（标准化）"""
        if len(close) < period:
            return 0.0
        data = close[-period:]
        x = np.arange(len(data))
        # 简单线性回归斜率
        x_mean = np.mean(x)
        y_mean = np.mean(data)
        numerator = np.sum((x - x_mean) * (data - y_mean))
        denominator = np.sum((x - x_mean) ** 2)
        if denominator == 0:
            return 0.0
        return numerator / denominator

    def detect(self, close: np.ndarray, volumes: Optional[np.ndarray] = None) -> MarketState:
        """
        检测市场状态。

        Parameters
        ----------
        close : np.ndarray
            收盘价序列
        volumes : np.ndarray, optional
            成交量序列

        Returns
        -------
        MarketState
        """
        if len(close) < 20:
            return MarketState.LOW_VOLATILITY

        # 计算真实 ATR（用日振幅近似）
        true_range = np.max(np.abs(np.diff(close)), axis=0) if len(close) > 1 else 0.0
        avg_close = np.mean(close[-self.atr_period:])
        # 用最近几日的平均振幅代替 ATR
        recent_returns = np.abs(np.diff(close)[-min(20, len(close)):] / close[-min(20, len(close)) - 1:-1])
        atr_ratio = np.mean(recent_returns) if len(recent_returns) > 0 else 0.0

        # 波动率判断（优先）
        if atr_ratio > 0.03:
            return MarketState.HIGH_VOLATILITY
        if atr_ratio < 0.005:
            return MarketState.LOW_VOLATILITY

        # 趋势判断
        slope = self._ma_slope(close, self.ma_period)
        normalized_slope = slope / avg_close if avg_close > 0 else 0.0

        if normalized_slope > self.trend_threshold:
            return MarketState.TREND_UP
        if normalized_slope < -self.trend_threshold:
            return MarketState.TREND_DOWN

        return MarketState.RANGE_BOUND


class IndicatorRecommender:
    """
    根据市场状态推荐适用的技术指标。
    """

    RECOMMENDATIONS = {
        MarketState.TREND_UP: [
            {"name": "EMA", "params": {"period": 20}, "reason": "趋势跟踪"},
            {"name": "MACD", "params": {}, "reason": "趋势动量确认"},
            {"name": "OBV", "params": {}, "reason": "成交量趋势验证"},
        ],
        MarketState.TREND_DOWN: [
            {"name": "EMA", "params": {"period": 20}, "reason": "趋势跟踪"},
            {"name": "RSI", "params": {"period": 14}, "reason": "超卖检测"},
            {"name": "MACD", "params": {}, "reason": "反弹信号"},
        ],
        MarketState.RANGE_BOUND: [
            {"name": "BOLL", "params": {}, "reason": "区间边界"},
            {"name": "RSI", "params": {"period": 14}, "reason": "超买超卖"},
            {"name": "KDJ", "params": {}, "reason": "震荡指标"},
        ],
        MarketState.HIGH_VOLATILITY: [
            {"name": "ATR", "params": {"period": 14}, "reason": "波动率测量"},
            {"name": "BOLL", "params": {}, "reason": "波动带"},
            {"name": "STDDEV", "params": {"period": 20}, "reason": "波动率"},
        ],
        MarketState.LOW_VOLATILITY: [
            {"name": "ROC", "params": {"period": 12}, "reason": "微弱趋势检测"},
            {"name": "CCI", "params": {"period": 20}, "reason": "价格区间"},
            {"name": "TRIX", "params": {"period": 15}, "reason": "平滑趋势"},
        ],
    }

    def recommend(self, state: MarketState, top_k: int = 3) -> list[dict]:
        """
        根据市场状态推荐指标。

        Parameters
        ----------
        state : MarketState
            市场状态
        top_k : int
            返回前 K 个推荐

        Returns
        -------
        list[dict] — 每个推荐包含 name, params, reason
        """
        recs = self.RECOMMENDATIONS.get(state, self.RECOMMENDATIONS[MarketState.RANGE_BOUND])
        return recs[:top_k]


class IndicatorScorer:
    """
    基于历史数据对指标进行有效性评分。

    评分维度：
    - Win Rate: 信号胜率（买入后价格上涨的概率）
    - Signal Count: 信号数量
    - SNR: 信噪比（有效信号 / 总信号）
    - Profit Factor: 平均盈利 / 平均亏损
    """

    def score(self, close: np.ndarray, indicator_values: np.ndarray,
              indicator_name: str, threshold: float = 0.0) -> IndicatorScore:
        """
        计算指标信号质量。

        简化实现：用指标值的动量变化作为信号生成器。
        - 买入信号：指标值从负转正
        - 卖出信号：指标值从正转负

        Parameters
        ----------
        close : np.ndarray
            收盘价
        indicator_values : np.ndarray
            指标值序列
        indicator_name : str
            指标名称
        threshold : float
            信号判定阈值

        Returns
        -------
        IndicatorScore
        """
        if len(close) < 10 or len(indicator_values) < 10:
            return IndicatorScore(name=indicator_name)

        # 生成交易信号（简化：指标上穿/下穿均值）
        mean_val = np.mean(indicator_values)
        diff = indicator_values - mean_val

        # 买入信号：diff 从 <=0 变 >0
        # 卖出信号：diff 从 >=0 变 <0
        buy_signals = []
        sell_signals = []

        for i in range(1, len(diff)):
            if diff[i] > threshold and diff[i - 1] <= threshold:
                buy_signals.append(i)
            elif diff[i] < -threshold and diff[i - 1] >= -threshold:
                sell_signals.append(i)

        # 计算胜率（买入后 N 日价格上涨的概率）
        buy_wins = 0
        for idx in buy_signals:
            if idx + 5 < len(close):
                if close[idx + 5] > close[idx]:
                    buy_wins += 1

        win_rate = buy_wins / len(buy_signals) if buy_signals else 0.0
        sell_wins = 0
        for idx in sell_signals:
            if idx + 5 < len(close):
                if close[idx + 5] < close[idx]:
                    sell_wins += 1

        sell_win_rate = sell_wins / len(sell_signals) if sell_signals else 0.0

        # 信噪比
        snr = float(np.std(indicator_values[indicator_values != np.nan])) / (
            float(np.std(indicator_values[np.isnan(indicator_values)])) + 1e-10
        )

        # 盈亏比
        total_buy_pnl = 0.0
        for idx in buy_signals:
            if idx + 5 < len(close):
                total_buy_pnl += (close[idx + 5] - close[idx]) / close[idx]
        avg_buy_pnl = total_buy_pnl / len(buy_signals) if buy_signals else 0.0

        total_sell_pnl = 0.0
        for idx in sell_signals:
            if idx + 5 < len(close):
                total_sell_pnl += (close[idx] - close[idx + 5]) / close[idx]
        avg_sell_pnl = total_sell_pnl / len(sell_signals) if sell_signals else 0.0

        profit_factor = abs(avg_buy_pnl) + abs(avg_sell_pnl) if (abs(avg_buy_pnl) + abs(avg_sell_pnl)) > 0 else 0.0

        # 综合评分（加权）
        score = (
            win_rate * 0.3 +
            sell_win_rate * 0.2 +
            min(snr, 5.0) / 5.0 * 0.2 +
            min(profit_factor, 2.0) / 2.0 * 0.3
        )

        return IndicatorScore(
            name=indicator_name,
            win_rate=round(win_rate, 4),
            signal_count=len(buy_signals) + len(sell_signals),
            snr=round(float(snr), 4),
            profit_factor=round(profit_factor, 4),
            score=round(score, 4),
        )


class IndicatorAgent:
    """
    AI 指标发现 Agent — 主入口。

    完整分析流程：
    1. 检测市场状态
    2. 推荐指标
    3. 计算指标值并评分
    4. 生成合成指标建议
    """

    def __init__(self):
        self._detector = MarketStateDetector()
        self._recommender = IndicatorRecommender()
        self._scorer = IndicatorScorer()

    def analyze(self, close: np.ndarray,
                volumes: Optional[np.ndarray] = None) -> dict:
        """
        完整分析流程。

        Parameters
        ----------
        close : np.ndarray
            收盘价序列
        volumes : np.ndarray, optional
            成交量序列

        Returns
        -------
        dict — 包含 market_state, recommendations, scores, synthetic_indicators
        """
        if len(close) < 20:
            return {
                "market_state": "low_data",
                "recommendations": [],
                "scores": [],
                "synthetic_indicators": [],
            }

        # 1. 检测市场状态
        state = self._detector.detect(close, volumes)

        # 2. 推荐指标
        recommendations = self._recommender.recommend(state)

        # 3. 计算每个指标的评分（简化：用指标值近似）
        scores = self._score_recommended(close, recommendations)

        # 4. 合成指标建议
        synthetic = self.get_synthetic_indicators(state)

        return {
            "market_state": state.value,
            "recommendations": recommendations,
            "scores": scores,
            "synthetic_indicators": synthetic,
        }

    def _score_recommended(self, close: np.ndarray,
                           recommendations: list[dict]) -> list[dict]:
        """
        对推荐指标进行评分（使用近似值）。
        """
        scores = []
        for rec in recommendations:
            name = rec["name"]
            values = self._approximate_indicator(close, name)
            score = self._scorer.score(close, values, name)
            scores.append({
                "name": score.name,
                "win_rate": score.win_rate,
                "signal_count": score.signal_count,
                "snr": score.snr,
                "profit_factor": score.profit_factor,
                "score": score.score,
            })

        # 按综合评分排序
        scores.sort(key=lambda s: s["score"], reverse=True)
        return scores

    def _approximate_indicator(self, close: np.ndarray, name: str) -> np.ndarray:
        """
        用简单数学方法近似计算指标值（避免依赖外部库）。
        """
        n = len(close)
        if name == "EMA":
            period = 10
            alpha = 2.0 / (period + 1)
            result = np.full(n, np.nan)
            result[0] = close[0]
            for i in range(1, n):
                result[i] = alpha * close[i] + (1 - alpha) * result[i - 1]
            return result
        elif name == "RSI":
            period = 14
            gains = np.maximum(close[1:] - close[:-1], 0)
            losses = np.maximum(close[:-1] - close[1:], 0)
            avg_gain = np.mean(gains[:period]) if period < len(gains) else 0
            avg_loss = np.mean(losses[:period]) if period < len(losses) else 0
            result = np.full(n, np.nan)
            if avg_loss == 0:
                result[period:] = 100.0
            else:
                rs = avg_gain / avg_loss
                result[period:] = 100.0 - 100.0 / (1.0 + rs)
            return result
        elif name == "MACD":
            # 用两个 EMA 的差近似
            ema12 = self._ema(close, 12)
            ema26 = self._ema(close, 26)
            return ema12 - ema26
        elif name == "BOLL":
            period = 20
            upper = np.full(n, np.nan)
            for i in range(period - 1, n):
                window = close[i - period + 1:i + 1]
                mean = np.mean(window)
                std = np.std(window)
                upper[i] = (close[i] - mean) / std if std > 0 else 0
            return upper
        elif name == "ATR":
            returns = np.abs(np.diff(close) / close[:-1])
            return np.concatenate([[0], returns])
        elif name == "OBV":
            obv = np.zeros(n)
            for i in range(1, n):
                if close[i] > close[i - 1]:
                    obv[i] = obv[i - 1] + 1
                elif close[i] < close[i - 1]:
                    obv[i] = obv[i - 1] - 1
                else:
                    obv[i] = obv[i - 1]
            return obv
        elif name == "ROC":
            period = 12
            result = np.full(n, np.nan)
            for i in range(period, n):
                result[i] = (close[i] - close[i - period]) / close[i - period]
            return result
        elif name == "CCI":
            period = 20
            result = np.full(n, np.nan)
            for i in range(period - 1, n):
                window = close[i - period + 1:i + 1]
                mean = np.mean(window)
                mad = np.mean(np.abs(window - mean))
                result[i] = (close[i] - mean) / (0.015 * mad) if mad > 0 else 0
            return result
        elif name == "TRIX":
            period = 15
            result = self._ema(self._ema(self._ema(close, period), period), period)
            diff = np.diff(result)
            return np.concatenate([[np.nan], diff / result[:-1] if result[0] != 0 else diff])
        elif name == "KDJ":
            period = 9
            result = np.full(n, np.nan)
            for i in range(period - 1, n):
                window = close[i - period + 1:i + 1]
                low = np.min(window)
                high = np.max(window)
                if high == low:
                    result[i] = 50
                else:
                    result[i] = (close[i] - low) / (high - low) * 100
            return result
        elif name == "STDDEV":
            period = 20
            result = np.full(n, np.nan)
            for i in range(period - 1, n):
                window = close[i - period + 1:i + 1]
                result[i] = np.std(window)
            return result
        else:
            # 默认：返回价格差分
            return np.concatenate([[np.nan], np.diff(close)])

    @staticmethod
    def _ema(data: np.ndarray, period: int) -> np.ndarray:
        """计算 EMA"""
        result = np.full(len(data), np.nan)
        if len(data) < period:
            return result
        result[0] = data[0]
        alpha = 2.0 / (period + 1)
        for i in range(1, len(data)):
            if not np.isnan(data[i]):
                result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
            else:
                result[i] = result[i - 1]
        return result

    def get_synthetic_indicators(self, state: MarketState) -> list[dict]:
        """
        生成合成指标建议。

        Returns
        -------
        list[dict] — 合成指标列表
        """
        synthetic_map = {
            MarketState.TREND_UP: [
                {
                    "name": "MACD_ATR",
                    "description": "波动率归一化 MACD",
                    "formula": "MACD / ATR(14)",
                    "reason": "高波动市场中归一化 MACD 信号",
                },
                {
                    "name": "EMA_OBV",
                    "description": "EMA 均线 + OBV 成交量确认",
                    "formula": "EMA(20) + OBV 动量",
                    "reason": "趋势中成交量确认增强信号可靠性",
                },
            ],
            MarketState.TREND_DOWN: [
                {
                    "name": "RSI_BOLL",
                    "description": "RSI + 布林带超卖检测",
                    "formula": "RSI < 30 AND price < BOLL_lower",
                    "reason": "双重超卖信号确认底部",
                },
                {
                    "name": "MACD_SAR",
                    "description": "MACD + SAR 趋势确认",
                    "formula": "MACD 金叉 AND price < SAR",
                    "reason": "反转信号双重验证",
                },
            ],
            MarketState.RANGE_BOUND: [
                {
                    "name": "BOLL_RSI",
                    "description": "布林RSI强度指标",
                    "formula": "RSI * (price - BOLL_mid) / BOLL_width",
                    "reason": "结合价格位置与 RSI 强度的震荡指标",
                },
                {
                    "name": "KDJ_CCI",
                    "description": "KDJ-CCI 复合震荡指标",
                    "formula": "(KDJ - CCI) / 2",
                    "reason": "两种震荡指标综合",
                },
            ],
            MarketState.HIGH_VOLATILITY: [
                {
                    "name": "ATR_BOLL",
                    "description": "ATR 自适应布林带",
                    "formula": "BOLL_mid ± ATR(14) * multiplier",
                    "reason": "波动率自适应的动态支撑阻力",
                },
                {
                    "name": "VOLUME_ATR",
                    "description": "放量波动率指标",
                    "formula": "VOLUME * ATR / MA(VOLUME)",
                    "reason": "结合成交量和波动率的极端信号",
                },
            ],
            MarketState.LOW_VOLATILITY: [
                {
                    "name": "ROC_CCI",
                    "description": "ROC-CCI 动量确认",
                    "formula": "ROC(12) + CCI(20)",
                    "reason": "低波动环境中的微弱趋势放大",
                },
                {
                    "name": "TRIX_MOMENTUM",
                    "description": "TRIX 动量指标",
                    "formula": "TRIX(15) * 100",
                    "reason": "平滑后的趋势动量",
                },
            ],
        }
        return synthetic_map.get(state, synthetic_map[MarketState.RANGE_BOUND])
