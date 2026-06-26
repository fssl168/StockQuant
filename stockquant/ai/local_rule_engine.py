# -*- coding: utf-8 -*-
"""本地规则引擎 — 基于 MA/MACD/RSI/BOLL 的快速信号判断

用于 Tick 级决策（< 1s），无需 LLM 调用，纯数学计算，延迟 < 50ms。
与远程 LLM 形成混合决策架构：Tick 级用规则引擎，分钟级以上用 LLM。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

logger = logging.getLogger("stockquant.ai.local_rule_engine")


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class RuleSignal:
    """规则引擎信号"""
    signal: SignalType = SignalType.HOLD
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)
    indicators: Dict[str, Any] = field(default_factory=dict)


class LocalRuleEngine:
    """本地规则引擎 — 纯数学指标计算，无需 LLM

    适用于 Tick 级（< 1s）的快速决策场景。
    规则优先级：RSI 极值 > MACD 金叉/死叉 > MA 趋势 > 布林带突破
    """

    # ── RSI 参数 ──
    RSI_PERIOD = 14
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30

    # ── MACD 参数 ──
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9

    # ── MA 参数 ──
    MA_SHORT = 5
    MA_LONG = 20

    # ── BOLL 参数 ──
    BOLL_PERIOD = 20
    BOLL_STD = 2.0

    def analyze_signal(self, closes: List[float]) -> RuleSignal:
        """基于收盘价序列生成交易信号

        Args:
            closes: 收盘价序列（至少 30 个数据点）

        Returns:
            RuleSignal 包含信号方向、置信度和原因
        """
        if len(closes) < 30:
            return RuleSignal(signal=SignalType.HOLD, confidence=0.0, reasons=["数据不足"])

        signal = RuleSignal()
        buy_score = 0.0
        sell_score = 0.0

        # 1. RSI 分析
        rsi = self._compute_rsi(closes)
        signal.indicators["rsi"] = round(rsi, 2)
        if rsi < self.RSI_OVERSOLD:
            buy_score += 0.35
            signal.reasons.append(f"RSI 超卖 ({rsi:.1f})")
        elif rsi > self.RSI_OVERBOUGHT:
            sell_score += 0.35
            signal.reasons.append(f"RSI 超买 ({rsi:.1f})")

        # 2. MACD 分析
        macd, macd_signal, hist = self._compute_macd(closes)
        signal.indicators["macd"] = round(macd, 4)
        signal.indicators["macd_signal"] = round(macd_signal, 4)
        signal.indicators["macd_hist"] = round(hist, 4)

        if hist > 0 and len(closes) >= 2:
            # MACD 柱状线翻正（金叉）
            buy_score += 0.25
            signal.reasons.append("MACD 金叉")
        elif hist < 0:
            # MACD 柱状线翻负（死叉）
            sell_score += 0.25
            signal.reasons.append("MACD 死叉")

        # 3. MA 趋势分析
        ma_short = self._compute_ma(closes, self.MA_SHORT)
        ma_long = self._compute_ma(closes, self.MA_LONG)
        signal.indicators["ma5"] = round(ma_short, 2)
        signal.indicators["ma20"] = round(ma_long, 2)

        if ma_short > ma_long * 1.005:
            buy_score += 0.20
            signal.reasons.append("MA5 > MA20 多头排列")
        elif ma_short < ma_long * 0.995:
            sell_score += 0.20
            signal.reasons.append("MA5 < MA20 空头排列")

        # 4. 布林带分析
        upper, middle, lower = self._compute_boll(closes)
        current_price = closes[-1]
        signal.indicators["boll_upper"] = round(upper, 2)
        signal.indicators["boll_middle"] = round(middle, 2)
        signal.indicators["boll_lower"] = round(lower, 2)

        if current_price < lower:
            buy_score += 0.20
            signal.reasons.append("价格跌破布林下轨")
        elif current_price > upper:
            sell_score += 0.20
            signal.reasons.append("价格突破布林上轨")

        # 综合判断
        if buy_score > sell_score and buy_score >= 0.3:
            signal.signal = SignalType.BUY
            signal.confidence = min(buy_score, 1.0)
        elif sell_score > buy_score and sell_score >= 0.3:
            signal.signal = SignalType.SELL
            signal.confidence = min(sell_score, 1.0)
        else:
            signal.signal = SignalType.HOLD
            signal.confidence = max(buy_score, sell_score)

        return signal

    def generate_decision(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成交易决策（供 LLMAdapter 调用）

        Args:
            market_data: 包含 closes (价格序列) 的字典

        Returns:
            决策结果字典
        """
        closes = market_data.get("closes", [])
        symbol = market_data.get("symbol", "unknown")

        signal = self.analyze_signal(closes)

        return {
            "symbol": symbol,
            "action": signal.signal.value,
            "confidence": signal.confidence,
            "reasons": signal.reasons,
            "indicators": signal.indicators,
            "model": "local_rule_engine",
            "latency_ms": 0,  # 纯计算，< 50ms
        }

    # ── 指标计算 ──────────────────────────────────────────────────────

    @staticmethod
    def _compute_rsi(closes: List[float], period: int = 14) -> float:
        """计算 RSI"""
        if len(closes) < period + 1:
            return 50.0

        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def _compute_ma(closes: List[float], period: int) -> float:
        """计算移动平均线"""
        if len(closes) < period:
            return closes[-1] if closes else 0
        return sum(closes[-period:]) / period

    @staticmethod
    def _compute_macd(closes: List[float]) -> tuple[float, float, float]:
        """计算 MACD (DIF, DEA, MACD柱)"""
        def ema(data: List[float], period: int) -> List[float]:
            multiplier = 2 / (period + 1)
            result = [data[0]]
            for price in data[1:]:
                result.append(price * multiplier + result[-1] * (1 - multiplier))
            return result

        if len(closes) < 26:
            return 0.0, 0.0, 0.0

        ema_fast = ema(closes, 12)
        ema_slow = ema(closes, 26)
        dif = [f - s for f, s in zip(ema_fast, ema_slow)]

        dea_list = ema(dif, 9)
        macd_hist = 2 * (dif[-1] - dea_list[-1])

        return dif[-1], dea_list[-1], macd_hist

    @staticmethod
    def _compute_boll(closes: List[float], period: int = 20, std_mult: float = 2.0) -> tuple[float, float, float]:
        """计算布林带 (上轨, 中轨, 下轨)"""
        if len(closes) < period:
            p = closes[-1] if closes else 0
            return p, p, p

        recent = closes[-period:]
        middle = sum(recent) / period
        variance = sum((x - middle) ** 2 for x in recent) / period
        std = variance ** 0.5

        upper = middle + std_mult * std
        lower = middle - std_mult * std
        return upper, middle, lower
