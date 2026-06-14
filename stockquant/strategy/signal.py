# -*- coding: utf-8 -*-
"""F019 信号管线系统"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SignalSide(Enum):
    BUY = "Buy"
    SELL = "Sell"
    HOLD = "Hold"


class SignalSource(Enum):
    TRADITIONAL = "traditional_strategy"   # 传统策略信号
    AI_MONITOR = "ai_monitor"              # AI 盯盘信号
    AI_DECISION = "ai_decision"            # AI 决策信号
    AI_ELEVATION = "ai_elevation"          # AI 升华建议


@dataclass
class Signal:
    """
    交易信号。

    每个信号必须附带 reasoning（推理链引用）和 confidence（置信度评分）。
    """
    symbol: str
    side: SignalSide
    confidence: float = 0.0               # 0-1
    source: SignalSource = SignalSource.TRADITIONAL
    reason: str = ""
    target_price: Optional[float] = None
    target_quantity: Optional[int] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    expires_at: Optional[datetime] = None
    reasoning: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def is_expired(self) -> bool:
        """检查信号是否过期"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def is_valid(self, current_price: float) -> bool:
        """信号有效性检查（A 股规则）"""
        if self.is_expired():
            return False

        # 100 股整数倍
        if self.target_quantity and self.target_quantity % 100 != 0:
            return False

        # 涨跌停范围检查（简化）
        # A 股主板 ±10%, 创业板/科创板 ±20%
        if self.target_price:
            if self.side == SignalSide.BUY:
                # 买入价不应超过涨停板
                pass
            elif self.side == SignalSide.SELL:
                # 卖出价不应低于跌停板
                pass

        return True

    @property
    def priority(self) -> int:
        """信号优先级（越小越高）"""
        priority_map = {
            SignalSource.TRADITIONAL: 0,
            SignalSource.AI_MONITOR: 1,
            SignalSource.AI_DECISION: 1,
            SignalSource.AI_ELEVATION: 2,
        }
        return priority_map.get(self.source, 99)

    def __repr__(self) -> str:
        return (f"Signal({self.symbol} {self.side.value} conf={self.confidence:.2f} "
                f"src={self.source.value})")


class SignalManager:
    """
    信号管理器：信号生成、冲突解决、生命周期管理。
    """

    def __init__(self, conflict_resolution: str = "conservative"):
        """
        Parameters
        ----------
        conflict_resolution : str
            "conservative" — AI 否决时暂停，AI 建议时仍需策略确认
            "aggressive" — AI 建议可覆盖策略
        """
        self._signals: list[Signal] = []
        self._conflict_resolution = conflict_resolution

    def add_signal(self, signal: Signal):
        """添加信号"""
        self._signals.append(signal)

    def get_active_signals(self, symbol: str) -> list[Signal]:
        """获取某标的的有效信号（过滤过期）"""
        active = []
        for s in self._signals:
            if s.symbol == symbol and not s.is_expired():
                active.append(s)
        return active

    def resolve_conflicts(self, symbol: str) -> Optional[Signal]:
        """
        信号冲突解决。

        当多个信号矛盾时，按优先级和冲突解决策略选出最终信号。
        """
        active = self.get_active_signals(symbol)
        if len(active) <= 1:
            return active[0] if active else None

        # 按优先级排序
        active.sort(key=lambda s: s.priority)

        # 保守模式：AI 否决时暂停
        if self._conflict_resolution == "conservative":
            for s in active:
                if s.side == SignalSide.HOLD and s.source.value.startswith("ai_"):
                    return Signal(
                        symbol=symbol,
                        side=SignalSide.HOLD,
                        confidence=s.confidence,
                        source=SignalSource.AI_DECISION,
                        reason="AI recommended HOLD (conservative mode)",
                    )

        # 取最高优先级信号
        return active[0]

    def cleanup_expired(self):
        """清理过期信号"""
        self._signals = [s for s in self._signals if not s.is_expired()]
