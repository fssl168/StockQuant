# -*- coding: utf-8 -*-
"""信号级回测评价 — 评估信号管线准确度"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class SignalAccuracy:
    """信号准确度指标"""
    total_signals: int = 0
    correct_signals: int = 0
    win_rate: float = 0.0
    avg_confidence: float = 0.0
    confidence_correlation: float = 0.0  # 置信度与准确性的相关性
    hit_rate_by_bucket: Dict[str, float] = field(default_factory=dict)


@dataclass
class SignalDecay:
    """信号衰减分析"""
    signal_time: datetime
    price_at_signal: float
    price_after_n_days: float
    decay_pct: float
    n_days: int


class SignalEvaluator:
    """信号级回测评价器。

    评估信号管线产生的信号的准确度：
    - 方向胜率（买入后 N 日价格上涨的概率）
    - 置信度与准确性的相关性
    - 信号衰减（信号发出后的价格变化）
    - 分桶分析（按信号来源类型分组评估）

    Usage:
        evaluator = SignalEvaluator(close_prices=close_series, window=5)
        evaluator.record_signal(signal, actual_return)
        accuracy = evaluator.evaluate()
    """

    # 默认回看窗口（日）
    DEFAULT_WINDOWS = [3, 5, 10, 20]

    def __init__(self, close_prices: Optional[pd.Series] = None,
                 windows: Optional[List[int]] = None) -> None:
        """
        Parameters
        ----------
        close_prices : pd.Series | None
            收盘价序列（用于自动计算实际收益率）
        windows : list[int] | None
            回看窗口（日），默认 [3, 5, 10, 20]
        """
        self._close_prices = close_prices
        self._windows = windows or self.DEFAULT_WINDOWS
        self._signals: list[Dict[str, Any]] = []
        self._actual_returns: list[float] = []

    def record_signal(self, signal: Any, actual_return: Optional[float] = None,
                      symbol: str = "", window: Optional[int] = None) -> None:
        """
        记录一个信号及其实际收益。

        Parameters
        ----------
        signal : Signal or dict
            信号对象或字典
        actual_return : float | None
            实际收益率（如果为 None，尝试从 close_prices 计算）
        symbol : str
            标的代码
        window : int | None
            回看窗口（日），默认用第一个默认窗口
        """
        record: Dict[str, Any] = {}

        # 提取信号字段（兼容 Signal 对象和 dict）
        if hasattr(signal, "to_dict"):
            record["signal_dict"] = signal.to_dict()  # type: ignore[attr-defined]
        elif isinstance(signal, dict):
            record["signal_dict"] = signal
        else:
            # 尝试从对象属性提取
            record["signal_dict"] = {
                "symbol": getattr(signal, "symbol", symbol),
                "side": getattr(signal, "side", "HOLD"),
                "confidence": getattr(signal, "confidence", 0.0),
                "source": getattr(signal, "source", "traditional"),
                "entry_price": getattr(signal, "target_price", None),
            }

        # 如果提供了 close_prices 且没有显式 actual_return，尝试自动计算
        if actual_return is None and self._close_prices is not None:
            w = window or self._windows[0]
            entry_idx = len(self._signals)
            if entry_idx + w < len(self._close_prices):
                entry_price = record["signal_dict"].get("entry_price") or self._close_prices.iloc[entry_idx]
                exit_price = self._close_prices.iloc[entry_idx + w]
                actual_return = (exit_price - entry_price) / entry_price if entry_price else 0.0

        record["actual_return"] = actual_return or 0.0
        record["window"] = window or self._windows[0]
        record["timestamp"] = datetime.now()

        self._signals.append(record)
        self._actual_returns.append(record["actual_return"])

    def evaluate(self) -> SignalAccuracy:
        """
        评估所有已记录信号的准确度。

        Returns
        -------
        SignalAccuracy
        """
        if not self._signals:
            return SignalAccuracy()

        returns = np.array(self._actual_returns, dtype=np.float64)
        confidences = np.array(
            [s["signal_dict"].get("confidence", 0.0) for s in self._signals],
            dtype=np.float64,
        )

        # 胜率为正收益的信号数 / 总数
        correct = np.sum(returns > 0)
        total = len(returns)
        win_rate = float(correct / total) if total > 0 else 0.0

        # 平均置信度
        avg_confidence = float(np.mean(confidences)) if total > 0 else 0.0

        # 置信度与准确性（是否盈利）的相关性
        binary_accuracy = (returns > 0).astype(np.float64)
        if len(binary_accuracy) > 1 and np.std(confidences) > 0 and np.std(binary_accuracy) > 0:
            confidence_correlation = float(np.corrcoef(confidences, binary_accuracy)[0, 1])
            if np.isnan(confidence_correlation):
                confidence_correlation = 0.0
        else:
            confidence_correlation = 0.0

        return SignalAccuracy(
            total_signals=total,
            correct_signals=int(correct),
            win_rate=win_rate,
            avg_confidence=avg_confidence,
            confidence_correlation=confidence_correlation,
        )

    def evaluate_by_window(self) -> Dict[int, SignalAccuracy]:
        """按不同回看窗口评估。"""
        result: Dict[int, SignalAccuracy] = {}
        for w in self._windows:
            window_signals = [s for s in self._signals if s.get("window") == w]
            if not window_signals:
                result[w] = SignalAccuracy()
                continue

            returns = np.array([s["actual_return"] for s in window_signals], dtype=np.float64)
            confidences = np.array(
                [s["signal_dict"].get("confidence", 0.0) for s in window_signals],
                dtype=np.float64,
            )

            correct = np.sum(returns > 0)
            total = len(returns)
            win_rate = float(correct / total) if total > 0 else 0.0
            avg_confidence = float(np.mean(confidences)) if total > 0 else 0.0

            binary_accuracy = (returns > 0).astype(np.float64)
            if total > 1 and np.std(confidences) > 0 and np.std(binary_accuracy) > 0:
                correlation = float(np.corrcoef(confidences, binary_accuracy)[0, 1])
                if np.isnan(correlation):
                    correlation = 0.0
            else:
                correlation = 0.0

            result[w] = SignalAccuracy(
                total_signals=total,
                correct_signals=int(correct),
                win_rate=win_rate,
                avg_confidence=avg_confidence,
                confidence_correlation=correlation,
            )

        return result

    def evaluate_by_source(self) -> Dict[str, SignalAccuracy]:
        """按信号来源类型分组评估。"""
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for s in self._signals:
            source = s["signal_dict"].get("source", "unknown")
            if hasattr(source, "value"):
                source = source.value
            groups.setdefault(source, []).append(s)

        result: Dict[str, SignalAccuracy] = {}
        for source_name, signals in groups.items():
            returns = np.array([s["actual_return"] for s in signals], dtype=np.float64)
            confidences = np.array(
                [s["signal_dict"].get("confidence", 0.0) for s in signals],
                dtype=np.float64,
            )

            correct = np.sum(returns > 0)
            total = len(returns)
            win_rate = float(correct / total) if total > 0 else 0.0
            avg_confidence = float(np.mean(confidences)) if total > 0 else 0.0

            binary_accuracy = (returns > 0).astype(np.float64)
            if total > 1 and np.std(confidences) > 0 and np.std(binary_accuracy) > 0:
                correlation = float(np.corrcoef(confidences, binary_accuracy)[0, 1])
                if np.isnan(correlation):
                    correlation = 0.0
            else:
                correlation = 0.0

            result[source_name] = SignalAccuracy(
                total_signals=total,
                correct_signals=int(correct),
                win_rate=win_rate,
                avg_confidence=avg_confidence,
                confidence_correlation=correlation,
            )

        return result

    def analyze_decay(self, signal_idx: int, days: int = 5) -> SignalDecay:
        """分析单个信号的衰减。"""
        if signal_idx < 0 or signal_idx >= len(self._signals):
            raise IndexError(f"signal_idx {signal_idx} out of range [0, {len(self._signals)})")

        signal = self._signals[signal_idx]
        price_at_signal = signal["signal_dict"].get("entry_price") or 0.0

        if self._close_prices is not None and signal_idx + days < len(self._close_prices):
            price_after = self._close_prices.iloc[signal_idx + days]
        else:
            # 退回到用 actual_return 反推
            actual_ret = signal.get("actual_return", 0.0)
            price_after = price_at_signal * (1 + actual_ret) if price_at_signal else 0.0

        decay_pct = (price_after - price_at_signal) / price_at_signal if price_at_signal else 0.0

        return SignalDecay(
            signal_time=signal["timestamp"],
            price_at_signal=price_at_signal,
            price_after_n_days=price_after,
            decay_pct=decay_pct,
            n_days=days,
        )

    def get_decay_curve(self, signal_idx: int) -> List[SignalDecay]:
        """获取单个信号的衰减曲线（多个窗口）。"""
        return [self.analyze_decay(signal_idx, days=w) for w in self._windows]

    def generate_report(self) -> str:
        """生成信号评价报告（Markdown 格式）。"""
        accuracy = self.evaluate()
        by_source = self.evaluate_by_source()
        by_window = self.evaluate_by_window()

        lines: List[str] = []
        lines.append("# 信号评价报告")
        lines.append("")
        lines.append(f"- 信号总数: {accuracy.total_signals}")
        lines.append(f"- 正确信号: {accuracy.correct_signals}")
        lines.append(f"- 胜率: {accuracy.win_rate:.2%}")
        lines.append(f"- 平均置信度: {accuracy.avg_confidence:.4f}")
        lines.append(f"- 置信度-准确性相关: {accuracy.confidence_correlation:.4f}")
        lines.append("")

        # 分窗口
        lines.append("## 按回看窗口评估")
        lines.append("")
        lines.append("| 窗口(日) | 信号数 | 胜率 | 平均置信度 | 相关系数 |")
        lines.append("|----------|--------|------|------------|----------|")
        for w, acc in sorted(by_window.items()):
            lines.append(
                f"| {w} | {acc.total_signals} | {acc.win_rate:.2%} "
                f"| {acc.avg_confidence:.4f} | {acc.confidence_correlation:.4f} |"
            )
        lines.append("")

        # 按来源
        lines.append("## 按信号来源评估")
        lines.append("")
        lines.append("| 来源 | 信号数 | 胜率 | 平均置信度 | 相关系数 |")
        lines.append("|------|--------|------|------------|----------|")
        for src, acc in sorted(by_source.items()):
            lines.append(
                f"| {src} | {acc.total_signals} | {acc.win_rate:.2%} "
                f"| {acc.avg_confidence:.4f} | {acc.confidence_correlation:.4f} |"
            )
        lines.append("")

        return "\n".join(lines)

    @property
    def signal_count(self) -> int:
        return len(self._signals)
