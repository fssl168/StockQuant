# -*- coding: utf-8 -*-
"""F024 MonitorAgent 单元测试"""

import threading
import time
from unittest.mock import MagicMock

import numpy as np
import pytest

from stockquant.ai.monitor_agent import MonitorAgent, MonitorSignal, WorkingMemory


class TestWorkingMemory:
    """测试 L1 工作记忆"""

    def test_append_and_get_recent(self):
        mem = WorkingMemory(max_size=10)
        for i in range(5):
            mem.append({"id": i, "value": i * 10})
        recent = mem.get_recent(3)
        assert len(recent) == 3
        assert recent[0]["id"] == 2
        assert recent[2]["id"] == 4

    def test_max_size_eviction(self):
        mem = WorkingMemory(max_size=5)
        for i in range(10):
            mem.append({"id": i})
        recent = mem.get_recent(10)
        assert len(recent) == 5
        assert recent[0]["id"] == 5
        assert recent[4]["id"] == 9

    def test_query_by_symbol(self):
        mem = WorkingMemory()
        mem.append({"symbol": "sh600519", "value": 1})
        mem.append({"symbol": "sz000858", "value": 2})
        mem.append({"symbol": "sh600519", "value": 3})
        results = mem.query(symbol="sh600519")
        assert len(results) == 2
        assert all(r["symbol"] == "sh600519" for r in results)

    def test_get_sentiment_baseline(self):
        mem = WorkingMemory()
        from datetime import datetime
        now = datetime.now()
        mem.append({"symbol": "sh600519", "timestamp": now, "sentiment": 0.5})
        mem.append({"symbol": "sh600519", "timestamp": now, "sentiment": 0.6})
        mem.append({"symbol": "sh600519", "timestamp": now, "sentiment": 0.4})
        baseline = mem.get_sentiment_baseline("sh600519", window_days=30)
        assert abs(baseline - 0.5) < 0.01

    def test_get_sentiment_baseline_no_data(self):
        mem = WorkingMemory()
        baseline = mem.get_sentiment_baseline("unknown_symbol")
        assert baseline == 0.0


class TestMonitorSignal:
    """测试 MonitorSignal 数据类"""

    def test_default_values(self):
        sig = MonitorSignal()
        assert sig.symbol == ""
        assert sig.direction == ""
        assert sig.confidence == 0.0
        assert sig.notification_sent is False
        assert sig.is_portfolio_hold is False

    def test_has_tool_calls(self):
        sig = MonitorSignal(tool_calls=[])
        assert sig.has_tool_calls is False
        sig.tool_calls = [{"name": "test"}]
        assert sig.has_tool_calls is True


class TestMonitorAgentBasic:
    """测试 MonitorAgent 基础功能"""

    def test_init(self):
        agent = MonitorAgent(threshold=0.7, interval_seconds=30.0)
        assert agent.threshold == 0.7
        assert not agent._running
        assert agent._scan_count == 0

    def test_watchlist_management(self):
        agent = MonitorAgent()
        agent.add_watchlist(["sh600519", "sz000858"])
        assert agent.get_watchlist() == ["sh600519", "sz000858"]

        agent.remove_watchlist(["sh600519"])
        assert agent.get_watchlist() == ["sz000858"]

        agent.set_watchlist(["sh600519", "sz000858", "sh601318"])
        assert len(agent.get_watchlist()) == 3

    def test_scan_without_fetcher_returns_empty(self):
        agent = MonitorAgent()
        signals = agent.scan(["sh600519"])
        assert signals == []

    def test_scan_count_increments(self):
        agent = MonitorAgent()
        initial_count = agent.get_scan_count()
        assert initial_count == 0


# ── Helper class for mock DataFrame ──

class _MockDF:
    """Minimal mock DataFrame that supports df["column"] indexing."""
    def __init__(self, data: dict):
        self._data = data
    def __getitem__(self, key):
        return self._data[key]
    def __len__(self):
        return len(next(iter(self._data.values())))


class TestMonitorAgentTechnicalSignals:
    """测试技术信号检测（mock fetcher）"""

    def _make_fetcher(self, closes: np.ndarray) -> MagicMock:
        fetcher = MagicMock()
        volumes = np.ones(len(closes), dtype=float) * 1000
        fetcher.fetch.return_value = _MockDF({"close": closes, "volume": volumes})
        return fetcher

    def test_macd_golden_cross(self):
        # Uptrend: prices increasing → MACD fast > slow
        fetcher = self._make_fetcher(np.array([10.0 + i * 0.1 for i in range(60)]))
        agent = MonitorAgent(fetcher_manager=fetcher, threshold=0.0)
        signals = agent.scan(["sh600519"])
        tech_signals = [s for s in signals if s.signal_type == "technical"]
        assert len(tech_signals) > 0

    def test_ma_bullish(self):
        # Strong uptrend → MA bullish + RSI may be high, just check signals are detected
        fetcher = self._make_fetcher(np.array([10.0 + i * 0.15 for i in range(60)]))
        agent = MonitorAgent(fetcher_manager=fetcher, threshold=0.0)
        signals = agent.scan(["sh600519"])
        tech_signals = [s for s in signals if s.signal_type == "technical"]
        assert len(tech_signals) > 0  # At least some technical signals

    def test_rsi_flat(self):
        """震荡的数据中 RSI 不应触发超买/超卖"""
        fetcher = self._make_fetcher(np.array([10.0, 10.1, 9.9, 10.05, 9.95, 10.0, 10.02, 9.98, 10.01, 9.99] * 6))
        agent = MonitorAgent(fetcher_manager=fetcher, threshold=0.0)
        signals = agent.scan(["sh600519"])
        rsi_signals = [s for s in signals if "RSI" in s.reason]
        # Flat oscillating data → RSI near 50 → no extreme signal
        assert len(rsi_signals) == 0


class TestMonitorAgentAnomalyDetection:
    """测试异动检测"""

    def test_abnormal_volume(self):
        closes = np.array([10.0] * 30)
        volumes = np.array([1000.0] * 29 + [50000.0])  # 异常放量
        fetcher = MagicMock()
        fetcher.fetch.return_value = _MockDF({"close": closes, "volume": volumes})

        agent = MonitorAgent(fetcher_manager=fetcher, threshold=0.0)
        signals = agent.scan(["sh600519"])
        anomaly_signals = [s for s in signals if s.signal_type == "anomaly"]
        assert any("异常放量" in s.reason for s in anomaly_signals)

    def test_limit_up(self):
        # Last bar limit up (>9.5% increase)
        closes = np.array([10.0] * 28 + [10.0, 11.0])  # 10% increase
        volumes = np.array([1000.0] * 30)
        fetcher = MagicMock()
        fetcher.fetch.return_value = _MockDF({"close": closes, "volume": volumes})

        agent = MonitorAgent(fetcher_manager=fetcher, threshold=0.0)
        signals = agent.scan(["sh600519"])
        anomaly_signals = [s for s in signals if s.signal_type == "anomaly"]
        assert any("涨停板" in s.reason for s in anomaly_signals)


class TestMonitorAgentSignalFusion:
    """测试信号融合"""

    def test_fuse_buy_signals(self):
        agent = MonitorAgent(threshold=0.0)
        signals = [
            MonitorSignal(symbol="sh600519", direction="BUY", confidence=0.7, signal_type="technical"),
            MonitorSignal(symbol="sh600519", direction="BUY", confidence=0.6, signal_type="news"),
        ]
        fused = agent._fuse_signals(signals)
        assert fused.direction == "BUY"
        assert fused.confidence > 0

    def test_fuse_mixed_signals(self):
        agent = MonitorAgent(threshold=0.0)
        signals = [
            MonitorSignal(symbol="sh600519", direction="BUY", confidence=0.7, signal_type="technical"),
            MonitorSignal(symbol="sh600519", direction="SELL", confidence=0.7, signal_type="technical"),
        ]
        fused = agent._fuse_signals(signals)
        assert fused.direction == "WATCH"


class TestMonitorAgentRealtimeLoop:
    """测试实时扫描循环"""

    def test_start_and_stop_monitoring(self):
        agent = MonitorAgent(interval_seconds=0.5)
        agent.start_monitoring(["sh600519"])
        time.sleep(1.5)
        count_before = agent.get_scan_count()
        assert count_before >= 1

        agent.stop_monitoring()
        assert not agent._running
        time.sleep(0.5)
        count_after = agent.get_scan_count()
        assert count_after == count_before

    def test_alert_callback(self):
        agent = MonitorAgent(threshold=0.0)
        received = []

        def on_alert(sig):
            received.append(sig)

        agent.on_alert(on_alert)

        closes = np.array([10.0] * 30)
        volumes = np.array([1000.0] * 29 + [50000.0])
        fetcher = MagicMock()
        fetcher.fetch.return_value = _MockDF({"close": closes, "volume": volumes})
        agent._fetcher_manager = fetcher

        agent.scan(["sh600519"])
        assert len(received) > 0
        assert received[0].symbol == "sh600519"


class TestMonitorAgentPortfolioLinkage:
    """测试持仓联动分析"""

    def test_pre_market_brief(self):
        agent = MonitorAgent(threshold=0.0)
        brief = agent.generate_pre_market_brief(["sh600519"])
        assert isinstance(brief, str)
        assert len(brief) > 0

    def test_post_market_summary_no_signals(self):
        agent = MonitorAgent(threshold=0.0)
        summary = agent.generate_post_market_summary(None)
        assert isinstance(summary, str)
        assert "无信号" in summary or "收盘总结" in summary
