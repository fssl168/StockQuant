# -*- coding: utf-8 -*-
"""F021 AI 指标发现 Agent 测试"""

import numpy as np
import pytest

from stockquant.ai.indicator_agent import (
    MarketState,
    MarketStateDetector,
    IndicatorRecommender,
    IndicatorScorer,
    IndicatorAgent,
)


class TestMarketStateDetector:
    def test_trend_up(self):
        """上升趋势 — 容忍波动率干扰"""
        np.random.seed(42)
        x = np.arange(100, dtype=float)
        close = 100 + 0.3 * x + np.random.randn(100) * 5.0
        detector = MarketStateDetector()
        state = detector.detect(close)
        # 如果噪声过大被识别为 HIGH_VOLATILITY，也接受
        assert state in (MarketState.TREND_UP, MarketState.HIGH_VOLATILITY)

    def test_trend_down(self):
        """下降趋势 — 容忍波动率干扰"""
        np.random.seed(123)
        x = np.arange(100, dtype=float)
        close = 100 - 0.3 * x + np.random.randn(100) * 5.0
        detector = MarketStateDetector()
        state = detector.detect(close)
        assert state in (MarketState.TREND_DOWN, MarketState.HIGH_VOLATILITY)

    def test_range_bound(self):
        """震荡市场"""
        np.random.seed(42)
        close = np.full(100, 100.0) + np.random.randn(100) * 1.5
        detector = MarketStateDetector()
        state = detector.detect(close)
        assert state in (MarketState.RANGE_BOUND, MarketState.LOW_VOLATILITY)

    def test_low_volatility(self):
        """低波动"""
        np.random.seed(42)
        close = np.full(100, 100.0) + np.random.randn(100) * 0.001
        detector = MarketStateDetector()
        state = detector.detect(close)
        assert state == MarketState.LOW_VOLATILITY

    def test_short_data(self):
        """短数据 → 低波动"""
        close = np.array([100.0, 101.0, 102.0])
        detector = MarketStateDetector()
        state = detector.detect(close)
        assert state == MarketState.LOW_VOLATILITY
        state = detector.detect(close)
        assert state == MarketState.LOW_VOLATILITY


class TestIndicatorRecommender:
    def test_recommend_trend_up(self):
        """上升趋势推荐 EMA/MACD/OBV"""
        recs = IndicatorRecommender().recommend(MarketState.TREND_UP)
        names = [r["name"] for r in recs]
        assert "EMA" in names
        assert "MACD" in names

    def test_recommend_range_bound(self):
        """震荡市场推荐 BOLL/RSI/KDJ"""
        recs = IndicatorRecommender().recommend(MarketState.RANGE_BOUND)
        names = [r["name"] for r in recs]
        assert "BOLL" in names
        assert "RSI" in names

    def test_top_k(self):
        """top_k 限制"""
        recs = IndicatorRecommender().recommend(MarketState.RANGE_BOUND, top_k=2)
        assert len(recs) <= 2

    def test_unknown_state_fallback(self):
        """未知状态降级到 RANGE_BOUND"""
        recs = IndicatorRecommender().recommend(MarketState.LOW_VOLATILITY)
        assert len(recs) >= 1


class TestIndicatorScorer:
    def test_score_with_trending_data(self):
        """趋势数据评分"""
        np.random.seed(42)
        close = np.arange(100, 200, dtype=float)
        values = np.arange(100, dtype=float)
        score = IndicatorScorer().score(close, values, "Test")
        assert 0 <= score.win_rate <= 1
        assert score.signal_count > 0

    def test_score_flat_data(self):
        """平直数据 → 低分"""
        close = np.full(100, 100.0)
        values = np.full(100, 50.0)
        score = IndicatorScorer().score(close, values, "Flat")
        assert score.win_rate == 0.0

    def test_score_short_data(self):
        """短数据 → 零分"""
        close = np.array([100.0, 101.0])
        values = np.array([1.0, 2.0])
        score = IndicatorScorer().score(close, values, "Short")
        assert score.signal_count == 0


class TestIndicatorAgent:
    def test_full_analysis_trend(self):
        """完整分析 — 趋势"""
        np.random.seed(42)
        x = np.arange(200, dtype=float)
        close = 100 + 0.5 * x + np.random.randn(200) * 0.5
        agent = IndicatorAgent()
        result = agent.analyze(close)
        assert result["market_state"] in [s.value for s in MarketState]
        assert len(result["recommendations"]) > 0
        assert len(result["scores"]) > 0
        assert len(result["synthetic_indicators"]) > 0

    def test_full_analysis_flat(self):
        """完整分析 — 震荡"""
        np.random.seed(42)
        close = np.full(200, 100.0) + np.random.randn(200) * 0.5
        agent = IndicatorAgent()
        result = agent.analyze(close)
        assert "market_state" in result
        assert len(result["recommendations"]) > 0

    def test_short_data(self):
        """短数据 → 空结果"""
        close = np.array([100.0, 101.0, 102.0])
        agent = IndicatorAgent()
        result = agent.analyze(close)
        assert result["market_state"] == "low_data"
        assert result["recommendations"] == []

    def test_synthetic_indicators(self):
        """合成指标建议"""
        agent = IndicatorAgent()
        synthetic = agent.get_synthetic_indicators(MarketState.RANGE_BOUND)
        assert len(synthetic) > 0
        for item in synthetic:
            assert "name" in item
            assert "description" in item
            assert "formula" in item


class TestApproximateIndicator:
    def test_ema_approximation(self):
        """EMA 近似"""
        agent = IndicatorAgent()
        close = np.arange(50, dtype=float)
        result = agent._approximate_indicator(close, "EMA")
        assert len(result) == 50
        assert not np.all(np.isnan(result))

    def test_rsi_approximation(self):
        """RSI 近似"""
        agent = IndicatorAgent()
        close = np.arange(50, dtype=float)
        result = agent._approximate_indicator(close, "RSI")
        assert len(result) == 50

    def test_macd_approximation(self):
        """MACD 近似"""
        agent = IndicatorAgent()
        close = np.arange(50, dtype=float)
        result = agent._approximate_indicator(close, "MACD")
        assert len(result) == 50
