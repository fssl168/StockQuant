# -*- coding: utf-8 -*-
"""F026 AI 动态风控 Agent 测试"""

import numpy as np
import pytest
from datetime import datetime, timedelta

from stockquant.ai.risk_agent import (
    MarketEnvironment,
    DynamicRiskParams,
    MarketEnvDetector,
    DynamicRiskAdjuster,
    AnomalyDetector,
    CorrelationEntry,
    CorrelationMonitor,
    RiskAgent,
)


class TestMarketEnvDetector:
    def test_bull_market(self):
        """牛市"""
        np.random.seed(42)
        x = np.arange(300, dtype=float)
        close = 100 + 0.5 * x + np.abs(np.random.randn(300)) * 1.5
        detector = MarketEnvDetector()
        state = detector.detect(close)
        assert state in (MarketEnvironment.BULL, MarketEnvironment.SIDEWAYS, MarketEnvironment.CRASH)

    def test_bear_market(self):
        """熊市"""
        np.random.seed(42)
        x = np.arange(300, dtype=float)
        close = 100 - 0.3 * x + np.abs(np.random.randn(300)) * 1.5  # 控制噪声避免触发暴跌
        detector = MarketEnvDetector()
        state = detector.detect(close)
        assert state in (MarketEnvironment.BEAR, MarketEnvironment.SIDEWAYS, MarketEnvironment.CRASH)

    def test_crash(self):
        """暴跌"""
        close = np.full(100, 100.0)
        close[50] = 90.0  # -10% 日跌幅
        detector = MarketEnvDetector()
        state = detector.detect(close)
        assert state == MarketEnvironment.CRASH

    def test_sideways(self):
        """震荡"""
        np.random.seed(42)
        close = np.full(100, 100.0) + np.random.randn(100) * 0.5
        detector = MarketEnvDetector()
        state = detector.detect(close)
        assert state in (MarketEnvironment.SIDEWAYS, MarketEnvironment.BULL, MarketEnvironment.BEAR)

    def test_short_data(self):
        """短数据"""
        close = np.array([100.0, 101.0])
        detector = MarketEnvDetector()
        state = detector.detect(close)
        assert state == MarketEnvironment.SIDEWAYS


class TestDynamicRiskAdjuster:
    def test_bull_adjustment(self):
        """牛市：放宽"""
        base = DynamicRiskParams()
        adj = DynamicRiskAdjuster()
        adjusted, record = adj.adjust(base, MarketEnvironment.BULL)
        assert adjusted.max_position_pct > base.max_position_pct
        assert adjusted.order_rate_limit > base.order_rate_limit

    def test_bear_adjustment(self):
        """熊市：收紧"""
        base = DynamicRiskParams()
        adj = DynamicRiskAdjuster()
        adjusted, record = adj.adjust(base, MarketEnvironment.BEAR)
        assert adjusted.max_position_pct < base.max_position_pct
        assert adjusted.order_rate_limit < base.order_rate_limit

    def test_crash_adjustment(self):
        """暴跌：极端收紧"""
        base = DynamicRiskParams()
        adj = DynamicRiskAdjuster()
        adjusted, record = adj.adjust(base, MarketEnvironment.CRASH)
        assert adjusted.order_rate_limit >= 1  # 至少 1
        assert adjusted.max_position_pct <= base.max_position_pct

    def test_sideways_no_change(self):
        """震荡：无调整"""
        base = DynamicRiskParams()
        adj = DynamicRiskAdjuster()
        adjusted, record = adj.adjust(base, MarketEnvironment.SIDEWAYS)
        assert adjusted.max_position_pct == base.max_position_pct

    def test_apply_to_risk_manager(self):
        """应用到 RiskManager"""
        from stockquant.engine.risk import RiskManager

        base = DynamicRiskParams(max_position_pct=0.30)
        adj = DynamicRiskAdjuster()
        adjusted, _ = adj.adjust(base, MarketEnvironment.BULL)

        rm = RiskManager(max_position_pct=0.30, max_daily_loss_pct=0.02)
        adj.apply_to_risk_manager(rm, adjusted)
        assert rm._max_position_pct > 0.30


class TestAnomalyDetector:
    def test_order_flood_detected(self):
        """频繁下单检测"""
        orders = []
        base_time = datetime.now()
        for i in range(6):
            orders.append({"side": "BUY", "timestamp": base_time + timedelta(seconds=i * 5)})
        detector = AnomalyDetector()
        assert detector.detect_order_flood(orders)

    def test_no_flood(self):
        """正常下单频率"""
        orders = []
        base_time = datetime.now()
        for i in range(3):
            orders.append({"side": "BUY", "timestamp": base_time + timedelta(minutes=i * 10)})
        detector = AnomalyDetector()
        assert not detector.detect_order_flood(orders)

    def test_large_order(self):
        """大额下单检测"""
        detector = AnomalyDetector()
        assert detector.detect_large_order(1000000, 100000)  # 10x

    def test_no_large_order(self):
        """正常大额"""
        detector = AnomalyDetector()
        assert not detector.detect_large_order(120000, 100000)  # 1.2x

    def test_same_direction_streak(self):
        """同向连续下单"""
        orders = [{"side": "BUY"} for _ in range(6)]
        detector = AnomalyDetector()
        assert detector.detect_same_direction_streak(orders)

    def test_no_streak(self):
        """交替方向"""
        orders = [{"side": "BUY" if i % 2 == 0 else "SELL"} for i in range(10)]
        detector = AnomalyDetector()
        assert not detector.detect_same_direction_streak(orders)


class TestCorrelationMonitor:
    def test_high_correlation(self):
        """高相关性"""
        np.random.seed(42)
        common = np.random.randn(100)
        e1 = CorrelationEntry("sh600519", common)
        e2 = CorrelationEntry("sh601318", common)
        monitor = CorrelationMonitor()
        result = monitor.get_concentration_risk([e1, e2])
        assert result == "high"

    def test_low_correlation(self):
        """低相关性"""
        np.random.seed(42)
        e1 = CorrelationEntry("sh600519", np.random.randn(100))
        e2 = CorrelationEntry("sh601318", np.random.randn(100))
        monitor = CorrelationMonitor()
        result = monitor.get_concentration_risk([e1, e2])
        assert result in ("low", "medium")

    def test_single_holding(self):
        """单只标的"""
        e1 = CorrelationEntry("sh600519", np.random.randn(100))
        monitor = CorrelationMonitor()
        result = monitor.get_concentration_risk([e1])
        assert result == "low"


class TestRiskAgent:
    def test_assess_and_adjust(self):
        """完整风控评估"""
        np.random.seed(42)
        x = np.arange(300, dtype=float)
        close = 100 + 0.5 * x + np.random.randn(300) * 2.0
        agent = RiskAgent()
        base = DynamicRiskParams()
        adjusted, reason = agent.assess_and_adjust(close, base)
        assert adjusted.max_position_pct > 0
        assert reason

    def test_risk_report(self):
        """风控报告"""
        np.random.seed(42)
        x = np.arange(300, dtype=float)
        close = 100 + 0.5 * x + np.random.randn(300) * 2.0
        agent = RiskAgent()
        agent.assess_and_adjust(close, DynamicRiskParams())
        report = agent.get_risk_report()
        assert report["total_adjustments"] == 1
        assert len(report["recent_adjustments"]) == 1

    def test_check_anomalies(self):
        """异常检测"""
        agent = RiskAgent()
        orders = [{"side": "BUY"} for _ in range(20)]
        warnings = agent.check_anomalies(orders)
        assert len(warnings) >= 1  # 至少同向连续下单
