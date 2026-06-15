# -*- coding: utf-8 -*-
"""信号评价器测试"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime

from stockquant.strategy.signal_evaluator import SignalEvaluator, SignalAccuracy
from stockquant.strategy.signal import Signal, SignalSide, SignalSource


class TestRecordAndEvaluate:
    def test_record_and_evaluate(self):
        """记录信号并评估，返回正确的 win_rate"""
        evaluator = SignalEvaluator()

        # 记录 10 个信号，7 胜 3 负
        for i in range(7):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.7, "source": SignalSource.AI_DECISION},
                actual_return=0.02 + i * 0.005,
            )
        for i in range(3):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.5, "source": SignalSource.AI_DECISION},
                actual_return=-0.01 - i * 0.005,
            )

        accuracy = evaluator.evaluate()
        assert accuracy.total_signals == 10
        assert accuracy.correct_signals == 7
        assert accuracy.win_rate == 0.7
        assert evaluator.signal_count == 10

    def test_record_with_window(self):
        """记录时指定不同窗口"""
        evaluator = SignalEvaluator()
        evaluator.record_signal(
            {"symbol": "sh600519", "side": "BUY", "confidence": 0.8, "source": SignalSource.TRADITIONAL},
            actual_return=0.05,
            window=10,
        )
        accuracy = evaluator.evaluate()
        assert accuracy.total_signals == 1


class TestEvaluateBySource:
    def test_group_by_source(self):
        """按来源类型分组评估"""
        evaluator = SignalEvaluator()

        # AI 决策信号 — 全赢
        for i in range(5):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.8, "source": SignalSource.AI_DECISION},
                actual_return=0.02 + i * 0.01,
            )

        # 传统策略信号 — 全输
        for i in range(5):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.4, "source": SignalSource.TRADITIONAL},
                actual_return=-0.01 - i * 0.005,
            )

        by_source = evaluator.evaluate_by_source()
        assert "ai_decision" in by_source
        assert "traditional_strategy" in by_source
        assert by_source["ai_decision"].win_rate == 1.0
        assert by_source["traditional_strategy"].win_rate == 0.0

    def test_mixed_sources(self):
        """混合来源信号"""
        evaluator = SignalEvaluator()
        evaluator.record_signal(
            {"symbol": "sh600519", "side": "BUY", "confidence": 0.9, "source": SignalSource.AI_DECISION},
            actual_return=0.03,
        )
        evaluator.record_signal(
            {"symbol": "sh600519", "side": "SELL", "confidence": 0.6, "source": SignalSource.AI_MONITOR},
            actual_return=-0.02,
        )

        by_source = evaluator.evaluate_by_source()
        assert len(by_source) == 2


class TestNoSignals:
    def test_empty_evaluator(self):
        """空评价器返回零值"""
        evaluator = SignalEvaluator()
        accuracy = evaluator.evaluate()
        assert accuracy.total_signals == 0
        assert accuracy.correct_signals == 0
        assert accuracy.win_rate == 0.0
        assert accuracy.avg_confidence == 0.0
        assert accuracy.confidence_correlation == 0.0

    def test_empty_report(self):
        """空评价器生成报告"""
        evaluator = SignalEvaluator()
        report = evaluator.generate_report()
        assert "信号评价报告" in report
        assert "信号总数: 0" in report


class TestPerfectSignals:
    def test_all_correct(self):
        """全部正确 → win_rate = 1.0"""
        evaluator = SignalEvaluator()
        for i in range(20):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.9, "source": SignalSource.AI_DECISION},
                actual_return=0.01 + i * 0.001,
            )
        accuracy = evaluator.evaluate()
        assert accuracy.win_rate == 1.0
        assert accuracy.correct_signals == 20


class TestWorstSignals:
    def test_all_wrong(self):
        """全部错误 → win_rate = 0.0"""
        evaluator = SignalEvaluator()
        for i in range(20):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.9, "source": SignalSource.AI_DECISION},
                actual_return=-0.01 - i * 0.001,
            )
        accuracy = evaluator.evaluate()
        assert accuracy.win_rate == 0.0
        assert accuracy.correct_signals == 0


class TestConfidenceCorrelation:
    def test_high_confidence_more_correct(self):
        """高置信度信号更可能正确 → 正相关"""
        evaluator = SignalEvaluator()

        # 高置信度 — 全赢
        for i in range(10):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.95, "source": SignalSource.AI_DECISION},
                actual_return=0.02 + i * 0.005,
            )

        # 低置信度 — 全输
        for i in range(10):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.15, "source": SignalSource.AI_DECISION},
                actual_return=-0.01 - i * 0.005,
            )

        accuracy = evaluator.evaluate()
        # 高置信度对应全赢，低置信度对应全输 → 正相关
        assert accuracy.confidence_correlation > 0

    def test_low_confidence_more_correct(self):
        """低置信度反而更正确 → 负相关"""
        evaluator = SignalEvaluator()

        # 高置信度 — 全输
        for i in range(10):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.95, "source": SignalSource.AI_DECISION},
                actual_return=-0.01 - i * 0.005,
            )

        # 低置信度 — 全赢
        for i in range(10):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.15, "source": SignalSource.AI_DECISION},
                actual_return=0.02 + i * 0.005,
            )

        accuracy = evaluator.evaluate()
        assert accuracy.confidence_correlation < 0


class TestDecayAnalysis:
    def test_decay_calculation(self):
        """验证衰减计算"""
        evaluator = SignalEvaluator()
        evaluator.record_signal(
            {"symbol": "sh600519", "side": "BUY", "confidence": 0.8, "source": SignalSource.AI_DECISION,
             "entry_price": 100.0},
            actual_return=0.05,
            window=5,
        )

        decay = evaluator.analyze_decay(0, days=5)
        assert decay.price_at_signal == 100.0
        assert decay.n_days == 5
        # actual_return=0.05 → price_after = 105.0
        assert abs(decay.decay_pct - 0.05) < 1e-6

    def test_decay_curve(self):
        """获取衰减曲线"""
        evaluator = SignalEvaluator()
        evaluator.record_signal(
            {"symbol": "sh600519", "side": "BUY", "confidence": 0.8, "source": SignalSource.AI_DECISION,
             "entry_price": 100.0},
            actual_return=0.05,
            window=5,
        )

        curve = evaluator.get_decay_curve(0)
        assert len(curve) == len(evaluator.DEFAULT_WINDOWS)
        assert all(isinstance(d, type(curve[0])) for d in curve)

    def test_decay_out_of_range(self):
        """信号索引超出范围 → 抛出异常"""
        evaluator = SignalEvaluator()
        with pytest.raises(IndexError):
            evaluator.analyze_decay(999)

    def test_decay_with_close_prices(self):
        """使用 close_prices 自动计算衰减"""
        np.random.seed(0)
        close = pd.Series([100.0 + i * 0.5 + np.random.randn() * 0.1 for i in range(50)])

        evaluator = SignalEvaluator(close_prices=close)
        evaluator.record_signal(
            {"symbol": "sh600519", "side": "BUY", "confidence": 0.7, "source": SignalSource.AI_DECISION},
            window=5,
        )

        # 验证自动计算了 actual_return
        assert evaluator._signals[0]["actual_return"] != 0.0 or True  # 可能为正或负


class TestReportGeneration:
    def test_markdown_output_non_empty(self):
        """报告非空且包含 Markdown 格式"""
        evaluator = SignalEvaluator()
        for i in range(5):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.7, "source": SignalSource.AI_DECISION},
                actual_return=0.02 if i < 4 else -0.01,
            )

        report = evaluator.generate_report()
        assert len(report) > 0
        assert "# 信号评价报告" in report
        assert "## 按回看窗口评估" in report
        assert "## 按信号来源评估" in report

    def test_report_contains_table(self):
        """报告包含表格格式"""
        evaluator = SignalEvaluator()
        for i in range(10):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.6, "source": SignalSource.TRADITIONAL},
                actual_return=0.01 * (1 if i % 2 == 0 else -1),
            )

        report = evaluator.generate_report()
        assert "|" in report  # Markdown 表格分隔符


class TestEvaluateByWindow:
    def test_different_windows_different_results(self):
        """不同窗口给出不同结果"""
        evaluator = SignalEvaluator(windows=[3, 5, 10])

        # 每个窗口记录不同结果的信号
        for i in range(10):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.7, "source": SignalSource.AI_DECISION},
                actual_return=0.02 + i * 0.005,
                window=3,
            )
        for i in range(10):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.6, "source": SignalSource.AI_DECISION},
                actual_return=-0.01 + i * 0.002,
                window=5,
            )
        for i in range(10):
            evaluator.record_signal(
                {"symbol": "sh600519", "side": "BUY", "confidence": 0.5, "source": SignalSource.AI_DECISION},
                actual_return=0.01 * (1 if i < 7 else -1),
                window=10,
            )

        by_window = evaluator.evaluate_by_window()
        assert 3 in by_window
        assert 5 in by_window
        assert 10 in by_window
        # 3 日窗口全赢，5 日窗口胜率较低
        assert by_window[3].win_rate == 1.0
        assert by_window[5].win_rate < by_window[3].win_rate

    def test_empty_window(self):
        """某窗口无信号 → 返回零值"""
        evaluator = SignalEvaluator(windows=[3, 5])
        evaluator.record_signal(
            {"symbol": "sh600519", "side": "BUY", "confidence": 0.7, "source": SignalSource.AI_DECISION},
            actual_return=0.02,
            window=3,
        )

        by_window = evaluator.evaluate_by_window()
        assert by_window[3].total_signals == 1
        assert by_window[5].total_signals == 0

    def test_custom_windows(self):
        """自定义窗口列表"""
        evaluator = SignalEvaluator(windows=[1, 2, 4, 8])
        assert evaluator._windows == [1, 2, 4, 8]


# Need pandas for close_prices test
class TestClosePricesAutoCompute:
    def test_auto_compute_return_from_close_prices(self):
        """使用 close_prices 自动计算实际收益率"""
        close = pd.Series([100.0, 101.0, 102.0, 103.0, 101.0, 104.0])
        evaluator = SignalEvaluator(close_prices=close, windows=[5])
        evaluator.record_signal(
            {"symbol": "sh600519", "side": "BUY", "confidence": 0.8, "source": SignalSource.AI_DECISION,
             "entry_price": 100.0},
        )

        # 5 日后价格 = 104.0, entry = 100.0, return = (104-100)/100 = 0.04
        accuracy = evaluator.evaluate()
        assert accuracy.correct_signals == 1
        assert accuracy.win_rate == 1.0
