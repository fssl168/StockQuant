# -*- coding: utf-8 -*-
"""F019 信号管线系统 — AI 信号 ↔ 策略信号双向转换，含 A 股规则校验"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

# --- A 股规则常量 ---
LOT_SIZE = 100
MAIN_BOARD_LIMIT = 0.10      # 主板 ±10%
CHINEXT_LIMIT = 0.20         # 创业板/科创板 ±20%
COMMISSION_RATE = 0.00025    # 佣金 0.025%（最低 5 元）
STAMP_TAX_RATE = 0.0005       # 印花税 0.05%（卖方）
TRANSFER_FEE_RATE = 0.00001  # 过户费 0.001%


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
class SignalAuditLog:
    """信号操作审计日志"""
    timestamp: datetime
    action: str          # "created", "filtered", "resolved", "expired", "deduped"
    signal_id: str
    reason: str


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
    is_t1_restricted: bool = False        # T+1 标记

    def _is_createch_market(self) -> bool:
        """判断是否为创业板/科创板"""
        return self.symbol.startswith("sz30") or self.symbol.startswith("sh68")

    def _get_limit_pct(self) -> float:
        """获取该标的涨跌停比例"""
        if self._is_createch_market():
            return CHINEXT_LIMIT
        return MAIN_BOARD_LIMIT

    def _calc_price_limits(self, prev_close: float) -> tuple[float, float]:
        """计算涨跌停价格范围 (lower_limit, upper_limit)"""
        if prev_close <= 0:
            return (0.0, float('inf'))
        limit = self._get_limit_pct()
        lower = prev_close * (1 - limit)
        upper = prev_close * (1 + limit)
        return (round(lower, 2), round(upper, 2))

    def _estimate_fee(self, price: float, quantity: int, side: str) -> dict:
        """估算交易费用"""
        if price <= 0 or quantity <= 0:
            return {"commission": 0, "stamp_tax": 0, "transfer_fee": 0, "total": 0}
        amount = price * quantity
        commission = max(amount * COMMISSION_RATE, 5.0)  # 最低 5 元
        stamp_tax = amount * STAMP_TAX_RATE if side.upper() == "SELL" else 0.0
        transfer_fee = amount * TRANSFER_FEE_RATE
        return {
            "amount": amount,
            "commission": round(commission, 2),
            "stamp_tax": round(stamp_tax, 2),
            "transfer_fee": round(transfer_fee, 2),
            "total": round(commission + stamp_tax + transfer_fee, 2),
        }

    def is_expired(self) -> bool:
        """检查信号是否过期"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def is_valid(self, prev_close: float = 0.0) -> bool:
        """信号有效性检查（A 股规则）"""
        if self.is_expired():
            return False

        # 100 股整数倍
        if self.target_quantity and self.target_quantity % LOT_SIZE != 0:
            return False

        # 涨跌停范围检查
        if prev_close > 0 and self.target_price:
            lower, upper = self._calc_price_limits(prev_close)
            if self.side == SignalSide.BUY and self.target_price > upper:
                return False
            if self.side == SignalSide.SELL and self.target_price < lower:
                return False

        return True

    def to_order_params(self, prev_close: float = 0.0) -> dict:
        """
        将信号转换为订单参数。

        返回:
        {
            "symbol": str,
            "side": str,
            "quantity": int,       # 已按 100 股取整
            "price": float,        # 目标价格
            "estimated_fees": dict,
            "is_t1_restricted": bool,
        }
        """
        qty = self.target_quantity or 0
        qty = (qty // LOT_SIZE) * LOT_SIZE if qty > 0 else 0

        fee = self._estimate_fee(self.target_price or 0, qty, self.side.value) if qty > 0 else {}

        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": qty,
            "price": self.target_price,
            "estimated_fees": fee,
            "is_t1_restricted": self.is_t1_restricted,
        }

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


def convert_ai_to_strategy(ai_signal: dict) -> tuple[Signal, list[str]]:
    """
    将 AI 信号（自然语言/结构化）转换为策略可执行的 Signal 对象。

    Parameters
    ----------
    ai_signal : dict
        {
            "symbol": str,
            "side": "Buy"/"Sell"/"Hold",
            "confidence": float,
            "reasoning": list[str],
            "target_price": float | None,
            "target_quantity": int | None,
            "stop_loss": float | None,
            "take_profit": float | None,
            "expires_minutes": int | None,  # 信号过期时间（相对）
        }

    Returns
    -------
    (Signal, warnings) — 转换后的信号和警告列表
    """
    warnings = []

    symbol = ai_signal.get("symbol", "").strip()
    if not symbol:
        raise ValueError("AI signal missing 'symbol'")

    side_str = ai_signal.get("side", "HOLD").upper()
    if side_str not in ("BUY", "SELL", "HOLD"):
        warnings.append(f"Unknown side '{side_str}', defaulting to HOLD")
        side_str = "HOLD"

    side = SignalSide.BUY if side_str == "BUY" else SignalSide.SELL if side_str == "SELL" else SignalSide.HOLD
    confidence = min(max(ai_signal.get("confidence", 0.0), 0.0), 1.0)
    reasoning = ai_signal.get("reasoning", [])
    expires_at = None
    if ai_signal.get("expires_minutes"):
        expires_at = datetime.now() + timedelta(minutes=ai_signal["expires_minutes"])

    signal = Signal(
        symbol=symbol,
        side=side,
        confidence=confidence,
        source=SignalSource.AI_DECISION,
        reason=ai_signal.get("reason", ""),
        target_price=ai_signal.get("target_price"),
        target_quantity=ai_signal.get("target_quantity"),
        stop_loss=ai_signal.get("stop_loss"),
        take_profit=ai_signal.get("take_profit"),
        expires_at=expires_at,
        reasoning=reasoning,
    )

    # 验证 A 股规则
    target_qty = signal.target_quantity
    if target_qty and target_qty % LOT_SIZE != 0:
        rounded = (target_qty // LOT_SIZE) * LOT_SIZE
        warnings.append(f"Quantity {target_qty} not multiple of {LOT_SIZE}, rounded to {rounded}")

    return signal, warnings


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
        self._audit_log: list[SignalAuditLog] = []

    def _log(self, action: str, signal: Signal, reason: str = ""):
        """记录审计日志"""
        self._audit_log.append(SignalAuditLog(
            timestamp=datetime.now(),
            action=action,
            signal_id=signal.symbol,
            reason=reason,
        ))

    def add_signal(self, signal: Signal):
        """添加信号"""
        self._log("created", signal, f"Added signal: {signal}")
        self._signals.append(signal)

    def get_active_signals(self, symbol: str) -> list[Signal]:
        """获取某标的的有效信号（过滤过期）"""
        active = []
        for s in self._signals:
            if s.symbol == symbol and not s.is_expired():
                active.append(s)
        return active

    def deduplicate(self, symbol: str) -> list[Signal]:
        """
        对某标的信号去重。

        如果两个信号 side 相同且 confidence 差值 < 0.1，视为重复。
        保留高置信度。

        Returns
        -------
        list[Signal] — 被去重的信号列表
        """
        active = self.get_active_signals(symbol)
        if len(active) <= 1:
            return []

        removed = []
        remaining = []
        for s in active:
            is_dup = False
            for r in remaining:
                if (s.side == r.side and abs(s.confidence - r.confidence) < 0.1):
                    removed.append(s)
                    self._log("deduped", s, f"Deduplicated: similar to {r.symbol}")
                    is_dup = True
                    break
            if not is_dup:
                remaining.append(s)

        # 更新内部状态
        current = set(id(s) for s in self._signals)
        self._signals = [s for s in self._signals if id(s) in remaining or s not in active]
        self._signals.extend(remaining)

        return removed

    def resolve_conflicts(self, symbol: str) -> Optional[Signal]:
        """
        信号冲突解决。

        当多个信号矛盾时，按优先级和冲突解决策略选出最终信号。

        Returns
        -------
        Optional[Signal] — 选出的最终信号，或 None
        """
        active = self.get_active_signals(symbol)
        if len(active) <= 1:
            return active[0] if active else None

        # 按优先级排序
        active.sort(key=lambda s: s.priority)

        # 检查冲突
        sides = set(s.side for s in active)
        if len(sides) <= 1:
            # 没有冲突，直接返回最高优先级
            self._log("resolved", active[0], f"No conflict, all {sides}")
            return active[0]

        if self._conflict_resolution == "conservative":
            # 保守模式：AI 否决（HOLD）时暂停
            for s in active:
                if s.side == SignalSide.HOLD and s.source.value.startswith("ai_"):
                    result = Signal(
                        symbol=symbol,
                        side=SignalSide.HOLD,
                        confidence=s.confidence,
                        source=SignalSource.AI_DECISION,
                        reason=f"AI recommended HOLD (conservative mode) — source: {s.source.value}",
                    )
                    self._log("resolved", result, f"Conservative: AI HOLD overruled {sides}")
                    return result

        # 激进模式：AI 建议可覆盖
        if self._conflict_resolution == "aggressive":
            for s in reversed(active):
                if s.side != SignalSide.HOLD and s.source.value.startswith("ai_"):
                    self._log("resolved", s, f"Aggressive: AI signal overruled traditional")
                    return s

        # 默认：取最高优先级信号
        result = active[0]
        self._log("resolved", result, f"Default: highest priority from {sides}")
        return result

    def get_highest_confidence(self, symbol: str) -> Optional[Signal]:
        """获取某标的最高置信度信号"""
        active = self.get_active_signals(symbol)
        if not active:
            return None
        return max(active, key=lambda s: s.confidence)

    def get_signals_by_source(self, source: SignalSource) -> list[Signal]:
        """按来源类型过滤信号"""
        return [s for s in self._signals if s.source == source and not s.is_expired()]

    def cleanup_expired(self) -> int:
        """
        清理过期信号。

        Returns
        -------
        int — 被清理的信号数量
        """
        before = len(self._signals)
        self._signals = [s for s in self._signals if not s.is_expired()]
        removed_count = before - len(self._signals)
        for _ in range(removed_count):
            pass  # audit: "removed" for each removed signal
        return removed_count

    def get_audit_log(self) -> list[SignalAuditLog]:
        """获取审计日志"""
        return self._audit_log.copy()

    @property
    def signal_count(self) -> int:
        """当前信号总数（含过期）"""
        return len(self._signals)
