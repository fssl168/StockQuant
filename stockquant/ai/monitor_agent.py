# -*- coding: utf-8 -*-
"""F024 AI 实时盯盘 Agent — 技术信号 + 新闻情绪 + 异动检测 + 实时循环 + 通知推送"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable

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
    notification_sent: bool = False  # 是否已发送通知
    is_portfolio_hold: bool = False  # 是否为持仓标的

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class WorkingMemory:
    """L1 工作记忆 — 内存存储最近 N 条关键信息。

    用于 MonitorAgent 存储/读取近期情绪基线、历史信号等。
    """

    def __init__(self, max_size: int = 200) -> None:
        self._max_size = max_size
        self._entries: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def append(self, entry: Dict[str, Any]) -> None:
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_size:
                self._entries = self._entries[-self._max_size:]

    def get_recent(self, n: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._entries[-n:])

    def query(self, symbol: Optional[str] = None, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """查询记忆条目。"""
        with self._lock:
            results = self._entries
            if symbol:
                results = [e for e in results if e.get("symbol") == symbol]
            if since:
                results = [e for e in results if e.get("timestamp", datetime.min) >= since]
            return list(results)

    def get_sentiment_baseline(self, symbol: str, window_days: int = 5) -> float:
        """获取某标的最近 N 日的平均情绪分，用于突变检测。"""
        cutoff = datetime.now() - timedelta(days=window_days)
        entries = self.query(symbol=symbol, since=cutoff)
        sentiment_entries = [e for e in entries if "sentiment" in e]
        if not sentiment_entries:
            return 0.0
        return float(np.mean([e["sentiment"] for e in sentiment_entries]))


class MonitorAgent:
    """F024 AI 实时盯盘 Agent。

    盘中实时分析行情 + 消息面，自动识别交易机会和风险。

    Features:
    - 技术信号检测: MACD 金叉/死叉, RSI 超买超卖, 布林带突破, 放量
    - 消息面联动: 新闻搜索 + 情绪分析
    - 异动检测: 放量突破, 涨停/跌停, 异常成交量
    - AI 信号融合: 技术指标 + 情绪 + 基本面综合
    - 告警推送: 通过 MessageRouter 发送到 9 通知渠道
    - 情绪突变检测: 对比历史基线，检测情绪异常
    - 持仓联动分析: 关联持仓标的新闻
    - 实时扫描循环: 定时循环扫描
    - 盘前简报 / 收盘总结

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
    interval_seconds : float
        实时扫描循环间隔（秒），默认 60 秒
    """

    def __init__(
        self,
        fetcher_manager: Any = None,
        news_searcher: NewsSearcher = None,
        max_steps: int = 10,
        threshold: float = 0.6,
        interval_seconds: float = 60.0,
    ) -> None:
        self._fetcher_manager = fetcher_manager
        self._news_searcher = news_searcher
        self._max_steps = max_steps
        self._threshold = threshold
        self._interval_seconds = interval_seconds
        self._alerts: List[MonitorSignal] = []
        self._watchlist: List[str] = []
        self._memory = WorkingMemory(max_size=200)
        self._running = False
        self._scan_thread: Optional[threading.Thread] = None
        self._on_alert_callbacks: List[Callable[[MonitorSignal], None]] = []
        self._scan_count = 0  # 已执行扫描次数

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

    def on_alert(self, callback: Callable[[MonitorSignal], None]) -> None:
        """注册告警回调。当高置信度信号产生时调用。"""
        self._on_alert_callbacks.append(callback)

    def start_monitoring(self, symbols: Optional[List[str]] = None) -> None:
        """启动实时扫描循环（后台线程）。

        每隔 interval_seconds 秒自动扫描自选股或指定标的。
        """
        if self._running:
            logger.warning("Monitoring already running")
            return

        targets = symbols or self._watchlist
        if not targets:
            logger.warning("No watchlist or symbols to monitor")
            return

        self._running = True
        self._scan_thread = threading.Thread(
            target=self._scan_loop,
            args=(targets,),
            daemon=True,
            name="stockquant-monitor-agent",
        )
        self._scan_thread.start()
        logger.info("MonitorAgent monitoring started with interval=%ss", self._interval_seconds)

    def stop_monitoring(self) -> None:
        """停止实时扫描循环"""
        self._running = False
        if self._scan_thread is not None:
            self._scan_thread.join(timeout=10)
            self._scan_thread = None
        logger.info("MonitorAgent monitoring stopped")

    def _scan_loop(self, targets: List[str]) -> None:
        """扫描循环：定时执行 scan()"""
        while self._running:
            try:
                self.scan(targets)
                self._scan_count += 1
            except Exception:
                logger.exception("Error in scan loop")
            # 按间隔休眠（可被中断）
            for _ in range(int(self._interval_seconds * 10)):
                if not self._running:
                    break
                time.sleep(0.1)

    def scan(self, symbols: Optional[List[str]] = None, portfolio: Optional[Dict[str, Any]] = None) -> List[MonitorSignal]:
        """扫描指定股票的技术信号 + 消息面 + 异动。

        Parameters
        ----------
        symbols : list[str] | None
            要扫描的股票代码，默认使用自选股
        portfolio : dict | None
            持仓信息 {symbol: {"name": str, "cost": float, "qty": int}}

        Returns
        -------
        list[MonitorSignal]
        """
        targets = symbols or self._watchlist
        signals: List[MonitorSignal] = []

        for symbol in targets:
            is_hold = portfolio is not None and symbol in portfolio

            tech_signals = self._detect_technical_signals(symbol)
            for s in tech_signals:
                s.is_portfolio_hold = is_hold
            signals.extend(tech_signals)

            news_signals = self._check_news_sentiment(symbol, portfolio)
            for s in news_signals:
                s.is_portfolio_hold = is_hold
            signals.extend(news_signals)

            anomaly_signals = self._detect_anomalies(symbol)
            for s in anomaly_signals:
                s.is_portfolio_hold = is_hold
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

        # 记录告警 + 推送通知
        for sig in signals:
            if sig.confidence >= self._threshold:
                self._alerts.append(sig)
                self._on_high_confidence_signal(sig)

        return signals

    def _on_high_confidence_signal(self, signal: MonitorSignal) -> None:
        """高置信度信号回调：通知推送"""
        # 1. 通知回调
        for callback in self._on_alert_callbacks:
            try:
                callback(signal)
            except Exception:
                logger.exception("Error in alert callback")

        # 2. 通过 MessageRouter 推送（如果可用）
        self._try_push_notification(signal)

        # 3. 写入工作记忆
        self._memory.append({
            "symbol": signal.symbol,
            "timestamp": signal.timestamp,
            "type": "signal",
            "direction": signal.direction,
            "confidence": signal.confidence,
            "reason": signal.reason,
        })

    def _try_push_notification(self, signal: MonitorSignal) -> None:
        """尝试通过消息路由器推送通知。"""
        try:
            from stockquant.execution.notifier.router import Message, MessageRouter, Priority
            from stockquant.execution.notifier.base import Notifier

            # 检查是否已配置 MessageRouter
            router = getattr(self, "_router", None)
            if router:
                priority = Priority.CRITICAL if signal.confidence >= 0.8 else Priority.HIGH
                message = Message(
                    title=f"盯盘信号: {signal.symbol} {signal.direction}",
                    content=f"{signal.reason}\n置信度: {signal.confidence:.2f}",
                    priority=priority,
                )
                router.send(message)
                signal.notification_sent = True
                logger.info("Notification pushed via MessageRouter for %s", signal.symbol)
                return
        except Exception:
            pass  # 非致命：路由器未配置

        # 降级：直接通过已注册的 Notifier 发送
        try:
            notifier = getattr(self, "_notifier", None)
            if notifier:
                notifier.send(
                    f"[盯盘告警] {signal.symbol} {signal.direction}\n{signal.reason}",
                    title=f"{signal.symbol} {signal.direction}",
                )
                signal.notification_sent = True
        except Exception:
            pass  # 非致命：通知器未配置

    def generate_pre_market_brief(self, symbols: Optional[List[str]] = None) -> str:
        """生成盘前简报。

        扫描持仓 + 自选股，汇总技术指标 + 新闻情绪，在开盘前推送给用户。
        """
        targets = symbols or self._watchlist
        if not targets:
            return "盘前简报：无监控标的。"

        lines = [f"## 盘前简报 ({datetime.now().strftime('%Y-%m-%d')})\n"]

        for symbol in targets:
            try:
                tech_signals = self._detect_technical_signals(symbol)
                news_signals = self._check_news_sentiment(symbol)
                anomaly_signals = self._detect_anomalies(symbol)

                all_signals = tech_signals + news_signals + anomaly_signals
                if not all_signals:
                    continue

                lines.append(f"### {symbol}\n")
                for s in all_signals:
                    icon = {"BUY": "🟢", "SELL": "🔴", "WATCH": "🟡"}.get(s.direction, "⚪")
                    lines.append(f"- {icon} {s.reason} (置信度: {s.confidence:.2f})")

            except Exception:
                logger.warning("Pre-market brief generation failed for %s", symbol)

        return "\n".join(lines)

    def generate_post_market_summary(self, signals: Optional[List[MonitorSignal]] = None) -> str:
        """生成收盘总结。

        汇总当日成交信号、持仓变化、市场回顾。
        """
        if signals is None:
            signals = [s for s in self._alerts if s.timestamp.date() == datetime.now().date()]

        if not signals:
            return "## 收盘总结 ({}): 当日无信号生成。".format(datetime.now().strftime('%Y-%m-%d'))

        buy_count = sum(1 for s in signals if s.direction == "BUY")
        sell_count = sum(1 for s in signals if s.direction == "SELL")
        watch_count = sum(1 for s in signals if s.direction == "WATCH")

        lines = [
            f"## 收盘总结 ({datetime.now().strftime('%Y-%m-%d')})\n",
            f"- 买入信号: {buy_count} 条",
            f"- 卖出信号: {sell_count} 条",
            f"- 观察信号: {watch_count} 条",
            f"- 总扫描次数: {self._scan_count}",
            "",
        ]

        # 按标的汇总
        by_symbol: Dict[str, List[MonitorSignal]] = {}
        for s in signals:
            by_symbol.setdefault(s.symbol, []).append(s)

        for symbol, group in by_symbol.items():
            lines.append(f"### {symbol}\n")
            for s in sorted(group, key=lambda x: x.timestamp, reverse=True)[:10]:
                icon = {"BUY": "🟢", "SELL": "🔴", "WATCH": "🟡"}.get(s.direction, "⚪")
                lines.append(
                    f"- {icon} {s.timestamp.strftime('%H:%M')} {s.reason} "
                    f"(置信度: {s.confidence:.2f})"
                )

        return "\n".join(lines)

    def _detect_technical_signals(self, symbol: str) -> List[MonitorSignal]:
        """检测技术指标信号"""
        signals: List[MonitorSignal] = []

        if not self._fetcher_manager:
            return signals

        try:
            df = self._fetcher_manager.fetch(symbol, days=60)
            if df is None or len(df) < 20:
                return signals

            close_arr = df["close"]
            closes = close_arr.values if hasattr(close_arr, "values") else np.asarray(close_arr)

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

    def _check_news_sentiment(self, symbol: str, portfolio: Optional[Dict[str, Any]] = None) -> List[MonitorSignal]:
        """检查新闻情绪 + 情绪突变检测"""
        signals: List[MonitorSignal] = []

        if not self._news_searcher:
            return signals

        try:
            news_items = self._news_searcher.search(symbol, days=1)
            if news_items:
                sentiments = [n.sentiment for n in news_items]
                avg_score = float(np.mean(sentiments))

                # 写入工作记忆（供情绪基线计算）
                self._memory.append({
                    "symbol": symbol,
                    "timestamp": datetime.now(),
                    "type": "sentiment",
                    "sentiment": avg_score,
                })

                # 情绪突变检测
                baseline = self._memory.get_sentiment_baseline(symbol, window_days=5)
                deviation = abs(avg_score - baseline)
                if deviation > 0.3:
                    direction = "BUY" if avg_score > baseline else "SELL"
                    signals.append(MonitorSignal(
                        symbol=symbol, direction=direction,
                        reason=f"情绪突变 (当前={avg_score:.2f}, 基线={baseline:.2f}, 偏离={deviation:.2f})",
                        confidence=min(0.8, deviation * 1.5), signal_type="news",
                    ))

                # 常规情绪信号
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

                # 持仓联动分析
                if portfolio and symbol in portfolio:
                    stock_info = portfolio[symbol]
                    is_negative = avg_score < -0.3
                    is_positive = avg_score > 0.5
                    impact = "重大利好" if is_positive else ("重大利空" if is_negative else "中性")
                    for sig in signals:
                        if sig.symbol == symbol and sig.signal_type == "news":
                            sig.reason += f" | 持仓: {stock_info.get('name', symbol)} ({impact})"
                            sig.is_portfolio_hold = True

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

            close_arr = df["close"]
            closes = close_arr.values if hasattr(close_arr, "values") else np.asarray(close_arr)
            vol_arr = df["volume"]
            volumes = vol_arr.values if hasattr(vol_arr, "values") else np.asarray(vol_arr)

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
        # 标记是否为持仓标的
        is_hold = any(s.is_portfolio_hold for s in signals)
        return MonitorSignal(
            symbol=signals[0].symbol if len(signals) == 1 else "MULTI",
            direction=direction,
            reason="; ".join(reasons),
            confidence=avg_confidence,
            signal_type="fused",
            is_portfolio_hold=is_hold,
        )

    def get_alerts(self, limit: int = 50) -> List[MonitorSignal]:
        """获取告警记录"""
        return self._alerts[-limit:]

    def get_watchlist(self) -> List[str]:
        """获取自选股列表"""
        return self._watchlist

    def get_scan_count(self) -> int:
        """获取已执行扫描次数"""
        return self._scan_count

    def set_router(self, router: Any) -> None:
        """设置消息路由器（用于通知推送）。"""
        self._router = router

    def set_notifier(self, notifier: Any) -> None:
        """设置通知器（降级推送通道）。"""
        self._notifier = notifier

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
