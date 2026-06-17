# -*- coding: utf-8 -*-
"""F024 AI 信号融合 — 技术面+情绪面+基本面三源融合"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class SignalDirection(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class SourceSignal:
    """单源信号"""
    source: str  # "technical", "sentiment", "fundamental"
    symbol: str = ""
    direction: SignalDirection = SignalDirection.HOLD
    confidence: float = 0.0  # 0-1
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp),
        }


@dataclass
class FusedSignal:
    """融合信号"""
    symbol: str = ""
    direction: SignalDirection = SignalDirection.HOLD
    confidence: float = 0.0
    sources: Dict[str, SourceSignal] = field(default_factory=dict)
    reason: str = ""
    conflict: bool = False  # 是否存在方向冲突
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "sources": {k: v.to_dict() for k, v in self.sources.items()},
            "reason": self.reason,
            "conflict": self.conflict,
            "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp),
        }


class SignalFusion:
    """三源信号融合器"""

    # 默认权重：技术面 0.4 + 情绪面 0.3 + 基本面 0.3
    DEFAULT_WEIGHTS = {
        "technical": 0.4,
        "sentiment": 0.3,
        "fundamental": 0.3,
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()

    def fuse(self, signals: List[SourceSignal]) -> FusedSignal:
        """融合多个来源的信号"""
        if not signals:
            return FusedSignal()

        symbol = signals[0].symbol
        source_signals = {s.source: s for s in signals}

        # 加权投票
        direction_scores = {d: 0.0 for d in SignalDirection}
        for signal in signals:
            weight = self.weights.get(signal.source, 0.2)
            direction_scores[signal.direction] += weight * signal.confidence

        # 选择得分最高的方向
        best_direction = max(direction_scores, key=direction_scores.get)
        best_score = direction_scores[best_direction]

        # 检测方向冲突
        active_directions = [d for d, s in direction_scores.items() if s > 0]
        conflict = len(active_directions) > 1

        # 冲突时降级
        if conflict:
            # 如果三个方向都有信号且不一致，降级为 HOLD
            directions_set = set(active_directions)
            if SignalDirection.BUY in directions_set and SignalDirection.SELL in directions_set:
                best_direction = SignalDirection.HOLD
                best_score *= 0.5  # 置信度减半

        # 构建融合原因
        reasons = [f"{s.source}({s.direction.value}:{s.confidence:.1f})" for s in signals]

        return FusedSignal(
            symbol=symbol,
            direction=best_direction,
            confidence=round(min(best_score, 1.0), 3),
            sources=source_signals,
            reason=" | ".join(reasons),
            conflict=conflict,
        )
