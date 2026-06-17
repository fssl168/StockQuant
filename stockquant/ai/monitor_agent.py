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
from stockquant.ai.json_utils import robust_json_parse

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
        """高置信度信号回调：通知推送 + WS 广播"""
        # 0. 通过 WebSocket 广播到 monitor 频道（前端实时推送）
        self._try_push_ws_signal(signal)

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

    def _try_push_ws_signal(self, signal: MonitorSignal) -> None:
        """通过 WebSocket 广播监控信号到前端 monitor 频道"""
        try:
            ws_mgr = getattr(self, "_ws_manager", None)
            if ws_mgr is not None:
                from stockquant.api.websocket import ws_manager as global_ws
                mgr = ws_mgr if ws_mgr is not global_ws else ws_mgr
                signal_dict = {
                    "symbol": signal.symbol,
                    "direction": signal.direction,
                    "reason": signal.reason,
                    "confidence": signal.confidence,
                    "signal_type": signal.signal_type,
                    "is_portfolio_hold": signal.is_portfolio_hold,
                    "timestamp": signal.timestamp.isoformat() if hasattr(signal.timestamp, "isoformat") else str(signal.timestamp),
                }
                # 调用 push 方法广播到 monitor 频道
                if hasattr(mgr, 'push'):
                    mgr.push("alert", signal_dict, "monitor")
                    logger.info("WS alert pushed for %s (%s)", signal.symbol, signal.direction)
                elif hasattr(mgr, 'broadcast'):
                    mgr.broadcast("alert", signal_dict, "monitor")
        except Exception:
            pass  # 非致命：WS 管理器未配置或推送失败

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

    def generate_premarket_briefing(self, watchlist: list[str]) -> dict:
        """生成盘前简报（结构化 dict）。

        包含：隔夜全球市场概览、自选股关键新闻、技术关键位、建议关注标的。

        Parameters
        ----------
        watchlist : list[str]
            自选股代码列表

        Returns
        -------
        dict
            {
                "global_markets": {...},
                "key_news": [...],
                "technical_levels": [...],
                "focus_stocks": [...],
                "timestamp": "..."
            }
        """
        now_str = datetime.now().isoformat()
        result: dict = {
            "global_markets": {},
            "key_news": [],
            "technical_levels": [],
            "focus_stocks": [],
            "timestamp": now_str,
        }

        # 1. 隔夜全球市场概览
        result["global_markets"] = self._build_global_market_summary()

        # 2. 自选股关键新闻
        for symbol in watchlist:
            news_items = self._fetch_news_items(symbol, days=1)
            for item in news_items:
                result["key_news"].append({
                    "symbol": symbol,
                    "title": item.get("title", ""),
                    "sentiment": item.get("sentiment", 0.0),
                    "source": item.get("source", ""),
                })

        # 3. 技术关键位（支撑/阻力）
        for symbol in watchlist:
            levels = self._compute_technical_levels(symbol)
            if levels:
                result["technical_levels"].append({
                    "symbol": symbol,
                    "support": levels.get("support"),
                    "resistance": levels.get("resistance"),
                    "current": levels.get("current"),
                    "trend": levels.get("trend"),
                })

        # 4. 建议关注标的
        result["focus_stocks"] = self._suggest_focus_stocks(watchlist)

        # 尝试 LLM 增强
        llm_result = self._try_llm_premarket_briefing(watchlist, result)
        if llm_result is not None:
            return llm_result

        return result

    def _build_global_market_summary(self) -> dict:
        """构建隔夜全球市场概览（基于新闻搜索降级）。"""
        summary: dict = {
            "us_markets": "数据暂不可用",
            "europe_markets": "数据暂不可用",
            "asia_markets": "数据暂不可用",
            "commentary": "",
        }
        if not self._news_searcher:
            return summary

        try:
            # 通过新闻搜索获取全球市场信息
            for keyword, key in [("美股", "us_markets"), ("欧洲股市", "europe_markets"), ("亚太股市", "asia_markets")]:
                items = self._news_searcher.search(keyword, days=1)
                if items:
                    top = items[0]
                    summary[key] = top.title if hasattr(top, "title") else str(top)
                    if hasattr(top, "sentiment"):
                        summary[key] += f" (情绪: {top.sentiment:.2f})"
        except Exception:
            logger.debug("Global market summary via news search failed")
        return summary

    def _fetch_news_items(self, symbol: str, days: int = 1) -> list[dict]:
        """获取标的新闻条目（返回 list[dict]）。"""
        if not self._news_searcher:
            return []
        try:
            raw = self._news_searcher.search(symbol, days=days)
            items = []
            for n in raw:
                if hasattr(n, "to_dict"):
                    items.append(n.to_dict())
                elif hasattr(n, "__dict__"):
                    items.append(vars(n))
                else:
                    items.append({"title": str(n), "sentiment": 0.0})
            return items
        except Exception:
            return []

    def _compute_technical_levels(self, symbol: str) -> Optional[dict]:
        """计算技术关键位（支撑/阻力/趋势）。"""
        if not self._fetcher_manager:
            return None
        try:
            df = self._fetcher_manager.fetch(symbol, days=60)
            if df is None or len(df) < 20:
                return None

            close_arr = df["close"]
            closes = close_arr.values if hasattr(close_arr, "values") else np.asarray(close_arr)
            current = float(closes[-1])

            # 布林带作为支撑/阻力
            boll = self._bollinger(closes, 20)
            if boll is not None:
                support = float(boll[0])
                resistance = float(boll[2])
            else:
                support = float(np.min(closes[-20:]))
                resistance = float(np.max(closes[-20:]))

            # 趋势判断
            if len(closes) >= 60:
                ma5 = float(np.mean(closes[-5:]))
                ma20 = float(np.mean(closes[-20:]))
                ma60 = float(np.mean(closes[-60:]))
                if ma5 > ma20 > ma60:
                    trend = "uptrend"
                elif ma5 < ma20 < ma60:
                    trend = "downtrend"
                else:
                    trend = "sideways"
            else:
                trend = "unknown"

            return {
                "support": round(support, 2),
                "resistance": round(resistance, 2),
                "current": round(current, 2),
                "trend": trend,
            }
        except Exception:
            return None

    def _suggest_focus_stocks(self, watchlist: list[str]) -> list[dict]:
        """建议关注标的（基于信号强度排序）。"""
        scored: list[dict] = []
        for symbol in watchlist:
            try:
                signals = self._detect_technical_signals(symbol)
                news_signals = self._check_news_sentiment(symbol)
                all_signals = signals + news_signals
                if all_signals:
                    best = max(all_signals, key=lambda s: s.confidence)
                    scored.append({
                        "symbol": symbol,
                        "direction": best.direction,
                        "confidence": round(best.confidence, 2),
                        "reason": best.reason,
                    })
            except Exception:
                continue
        scored.sort(key=lambda x: x["confidence"], reverse=True)
        return scored[:5]

    def _try_llm_premarket_briefing(self, watchlist: list[str], data: dict) -> Optional[dict]:
        """尝试通过 LLM 增强盘前简报，失败则返回 None。"""
        try:
            from stockquant.agent.llm_adapter import LLMAdapter
            from stockquant.config import get_config
            ai_cfg = get_config().get("ai", {})
            adapter = LLMAdapter(
                model=ai_cfg.get("model", "gpt-4o"),
                api_key=ai_cfg.get("api_key") or None,
                base_url=ai_cfg.get("api_base") or None,
            )
            prompt = (
                "你是一位专业的A股市场分析师。请基于以下数据，生成一份结构化的盘前简报分析。\n"
                "要求：对每个板块给出简明分析，重点标注风险和机会。返回 JSON 格式，"
                "包含 global_markets_analysis, key_news_analysis, technical_analysis, focus_recommendation 字段。\n\n"
                f"数据：{data}"
            )
            resp = adapter.call(
                messages=[
                    {"role": "system", "content": "你是专业A股分析师，只返回JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            )
            if resp.content:
                parsed = robust_json_parse(resp.content)
                if isinstance(parsed, dict):
                    # 合并 LLM 增强结果
                    data["llm_analysis"] = parsed
                    return data
        except Exception:
            logger.debug("LLM premarket briefing enhancement failed, using structured fallback")
        return None

    def generate_postmarket_summary(self, watchlist: list[str]) -> dict:
        """生成收盘总结（结构化 dict）。

        包含：大盘指数表现、自选股表现、异动与成交量、当日关键信号、次日催化剂预览。

        Parameters
        ----------
        watchlist : list[str]
            自选股代码列表

        Returns
        -------
        dict
            {
                "market_indices": {...},
                "watchlist_performance": [...],
                "notable_events": [...],
                "key_signals": [...],
                "next_day_catalysts": [...],
                "timestamp": "..."
            }
        """
        now_str = datetime.now().isoformat()
        result: dict = {
            "market_indices": {},
            "watchlist_performance": [],
            "notable_events": [],
            "key_signals": [],
            "next_day_catalysts": [],
            "timestamp": now_str,
        }

        # 1. 大盘指数表现
        result["market_indices"] = self._build_market_indices_summary()

        # 2. 自选股表现
        for symbol in watchlist:
            perf = self._compute_stock_performance(symbol)
            if perf:
                result["watchlist_performance"].append(perf)

        # 3. 异动与成交量
        for symbol in watchlist:
            events = self._detect_anomalies(symbol)
            for e in events:
                result["notable_events"].append({
                    "symbol": symbol,
                    "reason": e.reason,
                    "confidence": round(e.confidence, 2),
                    "signal_type": e.signal_type,
                })

        # 4. 当日关键信号
        today_alerts = [s for s in self._alerts if s.timestamp.date() == datetime.now().date()]
        for sig in today_alerts[-20:]:
            result["key_signals"].append({
                "symbol": sig.symbol,
                "direction": sig.direction,
                "reason": sig.reason,
                "confidence": round(sig.confidence, 2),
                "signal_type": sig.signal_type,
                "timestamp": sig.timestamp.isoformat(),
            })

        # 5. 次日催化剂预览
        result["next_day_catalysts"] = self._preview_next_day_catalysts(watchlist)

        # 尝试 LLM 增强
        llm_result = self._try_llm_postmarket_summary(watchlist, result)
        if llm_result is not None:
            return llm_result

        return result

    def _build_market_indices_summary(self) -> dict:
        """构建大盘指数表现（上证/深证/创业板）。"""
        indices: dict = {
            "SSE": {"name": "上证指数", "change_pct": None, "commentary": "数据暂不可用"},
            "SZSE": {"name": "深证成指", "change_pct": None, "commentary": "数据暂不可用"},
            "ChiNext": {"name": "创业板指", "change_pct": None, "commentary": "数据暂不可用"},
        }
        if not self._fetcher_manager:
            return indices

        index_map = {
            "SSE": "sh000001",
            "SZSE": "sz399001",
            "ChiNext": "sz399006",
        }
        for key, code in index_map.items():
            try:
                df = self._fetcher_manager.fetch(code, days=5)
                if df is not None and len(df) >= 2:
                    close_arr = df["close"]
                    closes = close_arr.values if hasattr(close_arr, "values") else np.asarray(close_arr)
                    pct = (closes[-1] - closes[-2]) / closes[-2] * 100
                    indices[key]["change_pct"] = round(float(pct), 2)
                    if pct > 1.0:
                        indices[key]["commentary"] = "强势上涨"
                    elif pct > 0:
                        indices[key]["commentary"] = "小幅上涨"
                    elif pct > -1.0:
                        indices[key]["commentary"] = "小幅下跌"
                    else:
                        indices[key]["commentary"] = "明显下跌"
            except Exception:
                continue
        return indices

    def _compute_stock_performance(self, symbol: str) -> Optional[dict]:
        """计算个股表现。"""
        if not self._fetcher_manager:
            return None
        try:
            df = self._fetcher_manager.fetch(symbol, days=5)
            if df is None or len(df) < 2:
                return None

            close_arr = df["close"]
            closes = close_arr.values if hasattr(close_arr, "values") else np.asarray(close_arr)
            vol_arr = df["volume"]
            volumes = vol_arr.values if hasattr(vol_arr, "values") else np.asarray(vol_arr)

            pct_change = (closes[-1] - closes[-2]) / closes[-2] * 100
            vol_change = 0.0
            if len(volumes) >= 2 and volumes[-2] > 0:
                vol_change = (volumes[-1] - volumes[-2]) / volumes[-2] * 100

            return {
                "symbol": symbol,
                "close": round(float(closes[-1]), 2),
                "change_pct": round(float(pct_change), 2),
                "volume_change_pct": round(float(vol_change), 2),
            }
        except Exception:
            return None

    def _preview_next_day_catalysts(self, watchlist: list[str]) -> list[dict]:
        """预览次日催化剂（基于新闻和公告）。"""
        catalysts: list[dict] = []
        for symbol in watchlist:
            news_items = self._fetch_news_items(symbol, days=2)
            for item in news_items[:3]:
                sentiment = item.get("sentiment", 0.0)
                if abs(sentiment) > 0.3:
                    catalysts.append({
                        "symbol": symbol,
                        "title": item.get("title", ""),
                        "sentiment": round(sentiment, 2),
                        "potential_impact": "high" if abs(sentiment) > 0.6 else "medium",
                    })
        return catalysts

    def _try_llm_postmarket_summary(self, watchlist: list[str], data: dict) -> Optional[dict]:
        """尝试通过 LLM 增强收盘总结，失败则返回 None。"""
        try:
            from stockquant.agent.llm_adapter import LLMAdapter
            from stockquant.config import get_config
            ai_cfg = get_config().get("ai", {})
            adapter = LLMAdapter(
                model=ai_cfg.get("model", "gpt-4o"),
                api_key=ai_cfg.get("api_key") or None,
                base_url=ai_cfg.get("api_base") or None,
            )
            prompt = (
                "你是一位专业的A股市场分析师。请基于以下收盘数据，生成一份结构化的收盘总结分析。\n"
                "要求：总结市场走势、标注异动标的、预判次日方向。返回 JSON 格式，"
                "包含 market_analysis, notable_analysis, signal_summary, next_day_outlook 字段。\n\n"
                f"数据：{data}"
            )
            resp = adapter.call(
                messages=[
                    {"role": "system", "content": "你是专业A股分析师，只返回JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            )
            if resp.content:
                parsed = robust_json_parse(resp.content)
                if isinstance(parsed, dict):
                    data["llm_analysis"] = parsed
                    return data
        except Exception:
            logger.debug("LLM postmarket summary enhancement failed, using structured fallback")
        return None

    def _analyze_social_sentiment(self, texts: list[str]) -> dict:
        """社交媒体情绪分析 — 优先使用增强版 SentimentAnalyzer，降级为关键词匹配。

        Parameters
        ----------
        texts : list[str]
            待分析的文本列表

        Returns
        -------
        dict
            {
                "score": float,        # -1.0 ~ 1.0
                "confidence": float,   # 0.0 ~ 1.0
                "key_phrases": list[str],
                "distribution": {"positive": int, "negative": int, "neutral": int}
            }
        """
        # 优先使用增强版 SentimentAnalyzer
        try:
            from stockquant.ai.sentiment import SentimentAnalyzer
            analyzer = SentimentAnalyzer(method="auto")
            result = analyzer.analyze(texts)
            return {
                "score": result.score,
                "confidence": result.confidence,
                "key_phrases": result.key_phrases,
                "distribution": result.distribution,
            }
        except Exception as exc:
            logger.debug("SentimentAnalyzer 不可用: %s，降级为关键词匹配", exc)

        # 降级：基础关键词匹配
        positive_keywords = {
            "利好", "上涨", "突破", "新高", "强势", "反弹", "涨停", "大涨",
            "买入", "加仓", "看好", "机会", "增长", "盈利", "超预期", "龙头",
            "主力", "资金流入", "底部", "反转", "放量上涨", "金叉",
        }
        negative_keywords = {
            "利空", "下跌", "跌破", "新低", "弱势", "回调", "跌停", "大跌",
            "卖出", "减仓", "看空", "风险", "亏损", "不及预期", "暴雷",
            "资金流出", "破位", "死叉", "恐慌", "缩量下跌", "腰斩",
        }

        distribution = {"positive": 0, "negative": 0, "neutral": 0}
        all_key_phrases: list[str] = []
        scores: list[float] = []

        for text in texts:
            text_lower = text.lower()
            pos_hits = [kw for kw in positive_keywords if kw in text_lower]
            neg_hits = [kw for kw in negative_keywords if kw in text_lower]

            pos_count = len(pos_hits)
            neg_count = len(neg_hits)
            total = pos_count + neg_count

            if total == 0:
                distribution["neutral"] += 1
                scores.append(0.0)
            else:
                score = (pos_count - neg_count) / total  # -1.0 ~ 1.0
                scores.append(score)
                if score > 0:
                    distribution["positive"] += 1
                    all_key_phrases.extend(pos_hits)
                elif score < 0:
                    distribution["negative"] += 1
                    all_key_phrases.extend(neg_hits)
                else:
                    distribution["neutral"] += 1

        # 综合情绪分
        if scores:
            avg_score = float(np.mean(scores))
            # 置信度：基于非中性文本比例
            non_neutral = distribution["positive"] + distribution["negative"]
            confidence = min(1.0, non_neutral / max(len(texts), 1))
        else:
            avg_score = 0.0
            confidence = 0.0

        # 去重关键短语
        unique_phrases = list(dict.fromkeys(all_key_phrases))

        return {
            "score": round(avg_score, 3),
            "confidence": round(confidence, 3),
            "key_phrases": unique_phrases[:20],
            "distribution": distribution,
        }

    def _detect_sentiment_anomaly(self, history: list[float]) -> bool:
        """检测情绪突变（z-score > 2.0）。

        Parameters
        ----------
        history : list[float]
            历史情绪分数序列（最近值在末尾）

        Returns
        -------
        bool
            True 表示检测到情绪突变
        """
        if len(history) < 3:
            return False

        arr = np.array(history, dtype=float)
        mean = float(np.mean(arr))
        std = float(np.std(arr))

        if std < 1e-9:
            return False

        latest = arr[-1]
        z_score = abs(latest - mean) / std

        return z_score > 2.0

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

    def analyze_news_correlation(self, symbols: list[str] = None) -> dict:
        """F024 消息面联动 — 新闻-持仓联动分析。

        对指定标的（或持仓标的）搜索相关新闻，分析新闻对持仓的影响。

        Parameters
        ----------
        symbols : list[str] | None
            要分析的股票代码列表，默认从持仓获取

        Returns
        -------
        dict
            {
                "correlations": [
                    {
                        "symbol": "sh600519",
                        "position_value": 1000000,
                        "news_count": 3,
                        "sentiment": "positive",
                        "impact_score": 0.7,
                        "summary": "Recent news suggests...",
                        "news_items": [...]
                    }
                ],
                "timestamp": "2024-01-01T12:00:00"
            }
        """
        # 如果没有提供 symbols，尝试从交易路由获取持仓
        if not symbols:
            symbols = self._get_portfolio_symbols()

        if not symbols:
            return {
                "correlations": [],
                "timestamp": datetime.now().isoformat(),
            }

        correlations = []
        for symbol in symbols:
            try:
                correlation = self._analyze_symbol_news(symbol)
                correlations.append(correlation)
            except Exception as exc:
                logger.warning("News correlation analysis failed for %s: %s", symbol, exc)

        return {
            "correlations": correlations,
            "timestamp": datetime.now().isoformat(),
        }

    def _get_portfolio_symbols(self) -> list[str]:
        """从交易路由获取持仓标的列表"""
        try:
            from stockquant.api.routers.trading import _portfolio
            return [s for s, p in _portfolio.positions.items() if p.quantity > 0]
        except Exception:
            return []

    def _get_position_value(self, symbol: str) -> float:
        """获取标的持仓市值"""
        try:
            from stockquant.api.routers.trading import _portfolio
            pos = _portfolio.positions.get(symbol)
            if pos and pos.quantity > 0:
                return float(pos.market_value)
        except Exception:
            pass
        return 0.0

    def _analyze_symbol_news(self, symbol: str) -> dict:
        """分析单个标的的新闻关联"""
        news_items = []
        avg_sentiment = 0.0

        if self._news_searcher:
            try:
                news_results = self._news_searcher.search(symbol, days=3)
                news_items = [n.to_dict() for n in news_results]

                if news_results:
                    sentiments = [n.sentiment for n in news_results]
                    avg_sentiment = float(np.mean(sentiments))
            except Exception as exc:
                logger.warning("News search failed for %s: %s", symbol, exc)

        # 确定情绪方向
        if avg_sentiment > 0.2:
            sentiment = "positive"
        elif avg_sentiment < -0.2:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        # 计算影响分数 (0-1)
        impact_score = min(1.0, abs(avg_sentiment) * (1 + len(news_items) * 0.1))
        impact_score = round(impact_score, 3)

        # 生成摘要
        summary = self._generate_news_summary(symbol, sentiment, avg_sentiment, news_items)

        # 写入工作记忆
        self._memory.append({
            "symbol": symbol,
            "timestamp": datetime.now(),
            "type": "news_correlation",
            "sentiment": avg_sentiment,
            "news_count": len(news_items),
            "impact_score": impact_score,
        })

        return {
            "symbol": symbol,
            "position_value": self._get_position_value(symbol),
            "news_count": len(news_items),
            "sentiment": sentiment,
            "impact_score": impact_score,
            "summary": summary,
            "news_items": news_items,
        }

    def _generate_news_summary(self, symbol: str, sentiment: str,
                               avg_sentiment: float, news_items: list) -> str:
        """生成新闻影响摘要"""
        if not news_items:
            return f"{symbol}: 暂无近期相关新闻。"

        count = len(news_items)
        if sentiment == "positive":
            return (f"{symbol}: 近期有 {count} 条相关新闻，整体情绪偏积极"
                    f"（均值={avg_sentiment:.2f}），可能对股价形成支撑。")
        elif sentiment == "negative":
            return (f"{symbol}: 近期有 {count} 条相关新闻，整体情绪偏消极"
                    f"（均值={avg_sentiment:.2f}），需关注潜在风险。")
        else:
            return (f"{symbol}: 近期有 {count} 条相关新闻，情绪整体中性"
                    f"（均值={avg_sentiment:.2f}），暂无明显方向性影响。")

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

    def set_websocket_manager(self, ws_manager: Any) -> None:
        """设置 WebSocket 管理器（用于 WS 实时监控推送）。"""
        self._ws_manager = ws_manager

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
