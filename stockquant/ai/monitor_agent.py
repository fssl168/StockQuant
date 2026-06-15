# -*- coding: utf-8 -*-
"""F024 AI 实时盯盘 Agent — 技术信号 + 新闻情绪 + 异动检测"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from stockquant.ai.news_searcher import NewsSearcher

logger = logging.getLogger("stockquant.ai")


@dataclass
class MonitorSignal:
    """盯盘监控信号"""

    symbol: str = ""
    direction: str = ""  # "BUY" / "SELL" / "WATCH"
    reason: str = ""
    confidence: float = 0.0  # 0.0-1.0
    signal_type: str = ""  # "technical" / "news" / "anomaly" / "fused"
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: List[dict] = field(default_factory=list)
    reasoning: str = ""
    acting: str = ""

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class MonitorAgent:
    """F024 AI 实时盯盘 Agent。

    盘中实时分析行情 + 消息面，自动识别交易机会和风险。

    Features:
    - 技术信号检测: MACD 金叉/死叉, RSI 超买超卖, 布林带突破, 放量
    - 消息面联动: 新闻搜索 + 情绪分析
    - 异动检测: 放量突破, 涨停/跌停, 异常成交量
    - AI 信号融合: 技术指标 + 情绪 + 基本面综合
    - 告警推送: 9 通知渠道

    Parameters
    ----------
    fetcher_manager : Any | None
        DataFetcherManager for real-time data
    news_searcher : NewsSearcher | None
        NewsSearcher for news sentiment
    max_steps : int
        最大推理步数
    threshold : float
        告警阈值
    """

    def __init__(
        self,
        fetcher_manager: Any = None,
        news_searcher: NewsSearcher = None,
        max_steps: int = 10,
        threshold: float = 0.6,
    ) -> None:
        self._fetcher_manager = fetcher_manager
        self._news_searcher = news_searcher
        self._threshold = threshold
        self._alerts: List[MonitorSignal] = []
        self._watchlist: List[str] = []

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float) -> None:
        self._threshold = value

    def add_watchlist(self, symbols: List[str]) -> None:
        """添加自选股列表"""
        for s in symbols:
            if s not in self._watchlist:
                self._watchlist.append(s)

    def remove_watchlist(self, symbols: List[str]) -> None:
        """从自选股列表移除"""
        for s in symbols:
            if s in self._watchlist:
                self._watchlist.remove(s)

    def set_watchlist(self, symbols: List[str]) -> None:
        """设置自选股列表（替换）"""
        self._watchlist = list(symbols)

    def scan(self, symbols: Optional[List[str]] = None) -> List[MonitorSignal]:
        """扫描指定股票的技术信号 + 消息面 + 异动。

        Parameters
        ----------
        symbols : list[str] | None
            要扫描的股票代码，默认使用自选股

        Returns
        -------
        list[MonitorSignal]
        """
        targets = symbols or self._watchlist
        signals: List[MonitorSignal] = []

        for symbol in targets:
            tech_signals = self._detect_technical_signals(symbol)
            signals.extend(tech_signals)

            news_signals = self._check_news_sentiment(symbol)
            signals.extend(news_signals)

            anomaly_signals = self._detect_anomalies(symbol)
            signals.extend(anomaly_signals)

        if signals:
            # 按 symbol 分组融合
            by_symbol: Dict[str, List[MonitorSignal]] = {}
            for sig in signals:
                by_symbol.setdefault(sig.symbol, []).append(sig)

            for symbol, group in by_symbol.items():
                fused = self._fuse_signals(group)
                if fused.confidence >= self._threshold:
                    signals.append(fused)

        # 记录告警
        for sig in signals:
            if sig.confidence >= self._threshold:
                self._alerts.append(sig)

        return signals

    def _detect_technical_signals(self, symbol: str) -> List[MonitorSignal]:
        """检测技术指标信号"""
        signals: List[MonitorSignal] = []

        if not self._fetcher_manager:
            return signals

        try:
            df = self._fetcher_manager.fetch(symbol, days=60)
            if df is None or len(df) < 20:
                return signals

            closes = df["close"].values

            # MACD 金叉/死叉
            macd_fast = self._ema(closes, 12)
            macd_slow = self._ema(closes, 26)
            if len(macd_fast) >= 2 and len(macd_slow) >= 2:
                if macd_fast[-2] <= macd_slow[-2] and macd_fast[-1] > macd_slow[-1]:
                    signals.append(MonitorSignal(
                        symbol=symbol, direction="BUY", reason="MACD 金叉",
                        confidence=0.7, signal_type="technical",
                    ))
                elif macd_fast[-2] >= macd_slow[-2] and macd_fast[-1] < macd_slow[-1]:
                    signals.append(MonitorSignal(
                        symbol=symbol, direction="SELL", reason="MACD 死叉",
                        confidence=0.7, signal_type="technical",
                    ))

            # RSI 超买/超卖
            rsi = self._rsi(closes, 14)
            if rsi < 30:
                signals.append(MonitorSignal(
                    symbol=symbol, direction="BUY", reason="RSI 超卖",
                    confidence=0.6, signal_type="technical",
                ))
            elif rsi > 70:
                signals.append(MonitorSignal(
                    symbol=symbol, direction="SELL", reason="RSI 超买",
                    confidence=0.6, signal_type="technical",
                ))

            # 布林带突破
            boll = self._bollinger(closes, 20)
            if boll and len(closes) > 0:
                if closes[-1] > boll[2]:
                    signals.append(MonitorSignal(
                        symbol=symbol, direction="BUY", reason="布林带上轨突破",
                        confidence=0.65, signal_type="technical",
                    ))
                elif closes[-1] < boll[0]:
                    signals.append(MonitorSignal(
                        symbol=symbol, direction="SELL", reason="布林带下轨跌破",
                        confidence=0.65, signal_type="technical",
                    ))

            # 均线排列
            if len(closes) >= 60:
                ma5 = float(np.mean(closes[-5:]))
                ma20 = float(np.mean(closes[-20:]))
                ma60 = float(np.mean(closes[-60:]))
                if ma5 > ma20 > ma60:
                    signals.append(MonitorSignal(
                        symbol=symbol, direction="BUY", reason="均线多头排列",
                        confidence=0.75, signal_type="technical",
                    ))
                elif ma5 < ma20 < ma60:
                    signals.append(MonitorSignal(
                        symbol=symbol, direction="SELL", reason="均线空头排列",
                        confidence=0.75, signal_type="technical",
                    ))

        except Exception as exc:
            logger.warning("Technical signal detection failed for %s: %s", symbol, exc)

        return signals

    def _check_news_sentiment(self, symbol: str) -> List[MonitorSignal]:
        """检查新闻情绪"""
        signals: List[MonitorSignal] = []

        if not self._news_searcher:
            return signals

        try:
            news_items = self._news_searcher.search(symbol, days=1)
            if news_items:
                avg_score = np.mean([n.sentiment for n in news_items])
                if avg_score > 0.5:
                    signals.append(MonitorSignal(
                        symbol=symbol, direction="BUY",
                        reason=f"新闻情绪积极 (score={avg_score:.2f})",
                        confidence=float(avg_score), signal_type="news",
                    ))
                elif avg_score < -0.3:
                    signals.append(MonitorSignal(
                        symbol=symbol, direction="SELL",
                        reason=f"新闻情绪消极 (score={avg_score:.2f})",
                        confidence=float(abs(avg_score)), signal_type="news",
                    ))
        except Exception as exc:
            logger.warning("News sentiment check failed for %s: %s", symbol, exc)

        return signals

    def _detect_anomalies(self, symbol: str) -> List[MonitorSignal]:
        """检测异动"""
        signals: List[MonitorSignal] = []

        if not self._fetcher_manager:
            return signals

        try:
            df = self._fetcher_manager.fetch(symbol, days=30)
            if df is None or len(df) < 5:
                return signals

            closes = df["close"].values
            volumes = df["volume"].values

            # 异常放量 (>3x 均值)
            if len(volumes) > 1:
                avg_vol = float(np.mean(volumes[:-1]))
                if avg_vol > 0 and volumes[-1] > avg_vol * 3:
                    signals.append(MonitorSignal(
                        symbol=symbol, direction="WATCH",
                        reason=f"异常放量 (vol={volumes[-1]:.0f} vs avg={avg_vol:.0f})",
                        confidence=0.6, signal_type="anomaly",
                    ))

            # 涨停/跌停
            if len(closes) >= 2:
                pct_change = (closes[-1] - closes[-2]) / closes[-2]
                if pct_change >= 0.095:
                    signals.append(MonitorSignal(
                        symbol=symbol, direction="WATCH",
                        reason="涨停板", confidence=0.8, signal_type="anomaly",
                    ))
                elif pct_change <= -0.095:
                    signals.append(MonitorSignal(
                        symbol=symbol, direction="WATCH",
                        reason="跌停板", confidence=0.8, signal_type="anomaly",
                    ))

        except Exception as exc:
            logger.warning("Anomaly detection failed for %s: %s", symbol, exc)

        return signals

    def _fuse_signals(self, signals: List[MonitorSignal]) -> MonitorSignal:
        """AI 信号融合 — 综合技术面+消息面+异动检测"""
        if not signals:
            return MonitorSignal(
                symbol="", direction="WATCH", reason="无信号", confidence=0.0,
            )

        weights = {"technical": 0.5, "news": 0.3, "anomaly": 0.2}
        total_weight = sum(weights.get(s.signal_type, 0.2) for s in signals)
        total_confidence = sum(
            s.confidence * weights.get(s.signal_type, 0.2) for s in signals
        )
        avg_confidence = total_confidence / total_weight if total_weight > 0 else 0.0

        buy_count = sum(1 for s in signals if s.direction == "BUY")
        sell_count = sum(1 for s in signals if s.direction == "SELL")

        if buy_count > sell_count:
            direction = "BUY"
        elif sell_count > buy_count:
            direction = "SELL"
        else:
            direction = "WATCH"

        reasons = [s.reason for s in signals]
        return MonitorSignal(
            symbol=signals[0].symbol if len(signals) == 1 else "MULTI",
            direction=direction,
            reason="; ".join(reasons),
            confidence=avg_confidence,
            signal_type="fused",
        )

    def get_alerts(self, limit: int = 50) -> List[MonitorSignal]:
        """获取告警记录"""
        return self._alerts[-limit:]

    def get_watchlist(self) -> List[str]:
        """获取自选股列表"""
        return self._watchlist

    # ── 辅助方法 ──

    @staticmethod
    def _ema(data: np.ndarray, period: int) -> np.ndarray:
        """计算指数移动平均"""
        result = np.zeros_like(data, dtype=float)
        if len(data) == 0:
            return result
        result[0] = float(data[0])
        multiplier = 2.0 / (period + 1)
        for i in range(1, len(data)):
            result[i] = (float(data[i]) - result[i - 1]) * multiplier + result[i - 1]
        return result

    @staticmethod
    def _rsi(data: np.ndarray, period: int = 14) -> float:
        """计算 RSI"""
        if len(data) < period + 1:
            return 50.0
        deltas = np.diff(data.astype(float))
        gains = np.maximum(deltas, 0)
        losses = np.maximum(-deltas, 0)
        avg_gain = float(np.mean(gains[:period]))
        avg_loss = float(np.mean(losses[:period]))
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100.0 - (100.0 / (1.0 + rs)))

    @staticmethod
    def _bollinger(
        data: np.ndarray, period: int = 20, std_mult: float = 2.0
    ) -> Optional[np.ndarray]:
        """计算布林带 [下轨, 中轨, 上轨]"""
        if len(data) < period:
            return None
        closes = data[-period:].astype(float)
        mid = float(np.mean(closes))
        std = float(np.std(closes))
        return np.array([mid - std_mult * std, mid, mid + std_mult * std])
