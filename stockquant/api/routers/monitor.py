# -*- coding: utf-8 -*-
"""F024 盯盘 API 路由 — 自选股管理 + 告警查询 + WebSocket 实时推送"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from stockquant.ai.monitor_agent import MonitorAgent, MonitorSignal
from stockquant.ai.news_searcher import NewsSearcher
from stockquant.ai.signal_fusion import SignalFusion, SourceSignal, SignalDirection
from stockquant.api.deps import get_current_user, get_required_user
from stockquant.api.schemas import UserToken
from stockquant.api.websocket import ws_manager
from stockquant.persistence.redis_client import get_watchlist as get_watchlist_redis, add_to_watchlist as add_to_watchlist_redis, remove_from_watchlist as remove_from_watchlist_redis
from stockquant.persistence.persistent_store import MonitorAlertStore

router = APIRouter(prefix="/monitor", tags=["monitor"])

logger = logging.getLogger("stockquant.ai")


# ── 全局监控状态（使用 Redis 持久化） ──

_watchlist: list[str] = []
_alerts: MonitorAlertStore = MonitorAlertStore()
_agent: Optional[MonitorAgent] = None
_agent_lock = threading.Lock()
_signal_fusion = SignalFusion()

def set_alert_storage(alert_store: MonitorAlertStore | None):
    """告警存储注入（由 main.py 调用）"""
    global _alerts
    if alert_store is not None:
        _alerts = alert_store


# Unified data service reference (set by main.py)
_data_service = None


def set_data_service(ds):
    _data_service = ds


class _DataServiceFetcher:
    def __init__(self, data_service):
        self._ds = data_service

    def fetch(self, symbol, days=60):
        return self._ds.fetch(symbol, days=days)


def _load_watchlist_from_redis():
    """从 Redis 加载自选股列表"""
    global _watchlist
    try:
        _watchlist = get_watchlist_redis()
    except Exception as e:
        logger.exception("Failed to load watchlist from Redis")
        _watchlist = []


def _get_agent() -> MonitorAgent:
    """获取或创建全局 MonitorAgent 实例（单例）。"""
    global _agent
    if _agent is None:
        with _agent_lock:
            if _agent is None:
                # 通过统一 DataService 获取行情（替代旧版 DataFetcherManager）
                if _data_service is None:
                    from stockquant.data.service import DataService
                    fetcher = _DataServiceFetcher(DataService())
                else:
                    fetcher = _DataServiceFetcher(_data_service)

                _agent = MonitorAgent(
                    fetcher_manager=fetcher,
                    news_searcher=NewsSearcher(),
                    threshold=0.5,
                )
                # 注入 WebSocket 管理器用于实时监控推送
                _agent.set_websocket_manager(ws_manager)
                # 注入数据库 URL 用于告警持久化
                _agent.set_db_url(os.environ.get("DATABASE_URL", "sqlite:///./stockquant.db"))
    return _agent


def _signal_to_dict(signal: "MonitorSignal") -> Dict[str, Any]:
    return {
        "symbol": signal.symbol,
        "direction": signal.direction,
        "reason": signal.reason,
        "confidence": signal.confidence,
        "signal_type": signal.signal_type,
        "timestamp": signal.timestamp.isoformat() if hasattr(signal.timestamp, "isoformat") else str(signal.timestamp),
        "is_portfolio_hold": signal.is_portfolio_hold,
    }


# ── API 端点 ──

@router.get("/watchlist", response_model=List[str])
def get_watchlist() -> List[str]:
    """获取自选股列表"""
    return _watchlist


@router.post("/watchlist")
def add_to_watchlist(symbols: list[str]) -> list[str]:
    """添加到自选股"""
    agent = _get_agent()
    agent.add_watchlist(symbols)
    for s in symbols:
        if s not in _watchlist:
            _watchlist.append(s)
    # 持久化到 Redis
    try:
        add_to_watchlist_redis(symbols)
    except Exception as e:
        logger.exception("Failed to save watchlist to Redis")
    return _watchlist


@router.delete("/watchlist")
def remove_from_watchlist(symbols: list[str]) -> list[str]:
    """从自选股移除"""
    agent = _get_agent()
    agent.remove_watchlist(symbols)
    for s in symbols:
        if s in _watchlist:
            _watchlist.remove(s)
    # 持久化到 Redis
    try:
        remove_from_watchlist_redis(symbols)
    except Exception as e:
        logger.exception("Failed to remove from watchlist in Redis")
    return _watchlist


@router.get("/alerts", response_model=List[Dict[str, Any]])
def get_alerts(limit: int = 50, _user: UserToken = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """获取告警记录"""
    agent = _get_agent()
    return [_signal_to_dict(a) for a in agent.get_alerts(limit)]


@router.get("/scan/{symbol}")
def scan_symbol(symbol: str) -> List[Dict[str, Any]]:
    """扫描指定股票信号"""
    try:
        agent = _get_agent()
        signals = agent.scan([symbol])
        return [_signal_to_dict(s) for s in signals]
    except Exception as exc:
        logger.error("Scan failed for %s: %s", symbol, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/brief")
def pre_market_brief(symbols: Optional[List[str]] = None) -> str:
    """获取盘前简报"""
    try:
        agent = _get_agent()
        targets = symbols or _watchlist
        return agent.generate_pre_market_brief(targets)
    except Exception as exc:
        logger.error("Pre-market brief failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/summary")
def post_market_summary() -> str:
    """获取收盘总结"""
    try:
        agent = _get_agent()
        recent = agent.get_alerts(200)
        if recent:
            today = recent[0].timestamp.date()
            recent = [s for s in recent if s.timestamp.date() == today]
        return agent.generate_post_market_summary(recent if recent else None)
    except Exception as exc:
        logger.error("Post-market summary failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status")
def get_status(_user: UserToken = Depends(get_current_user)) -> Dict[str, Any]:
    """获取监控状态"""
    try:
        agent = _get_agent()
        return {
            "watchlist": _watchlist,
            "alerts_count": len(agent.get_alerts()),
            "scan_count": agent.get_scan_count(),
            "connections_count": ws_manager.get_connection_count("monitor"),
            "running": agent._running,
        }
    except Exception as exc:
        logger.error("Status check failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/start-monitoring")
def start_monitoring(body: Optional[Dict[str, Any]] = None, _user: UserToken = Depends(get_required_user)) -> Dict[str, str]:
    """启动实时扫描"""
    try:
        agent = _get_agent()
        targets = (body or {}).get("symbols") or _watchlist
        if not targets:
            raise HTTPException(status_code=400, detail="No watchlist or symbols provided")
        agent.start_monitoring(targets)
        return {"status": "monitoring_started"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Start monitoring failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/news-correlation")
def get_news_correlation(symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """F024 消息面联动 — 新闻-持仓联动分析"""
    try:
        agent = _get_agent()
        return agent.analyze_news_correlation(symbols)
    except Exception as exc:
        logger.error("News correlation analysis failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/fused-signals")
def get_fused_signals(symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """F024 AI 信号融合 — 技术面+情绪面+基本面三源融合"""
    try:
        agent = _get_agent()
        targets = symbols or _watchlist
        if not targets:
            return {"fused_signals": [], "timestamp": ""}

        fused_results = []
        for symbol in targets:
            source_signals: List[SourceSignal] = []

            # Technical: 从 MonitorAgent 获取技术指标信号
            tech_signals = agent._detect_technical_signals(symbol)
            if tech_signals:
                best_tech = max(tech_signals, key=lambda s: s.confidence)
                direction_map = {"BUY": SignalDirection.BUY, "SELL": SignalDirection.SELL, "WATCH": SignalDirection.HOLD}
                source_signals.append(SourceSignal(
                    source="technical",
                    symbol=symbol,
                    direction=direction_map.get(best_tech.direction, SignalDirection.HOLD),
                    confidence=best_tech.confidence,
                    reason=best_tech.reason,
                ))

            # Sentiment: 从新闻情绪获取
            news_signals = agent._check_news_sentiment(symbol)
            if news_signals:
                best_news = max(news_signals, key=lambda s: s.confidence)
                direction_map = {"BUY": SignalDirection.BUY, "SELL": SignalDirection.SELL, "WATCH": SignalDirection.HOLD}
                source_signals.append(SourceSignal(
                    source="sentiment",
                    symbol=symbol,
                    direction=direction_map.get(best_news.direction, SignalDirection.HOLD),
                    confidence=best_news.confidence,
                    reason=best_news.reason,
                ))

            # Fundamental: 从新闻/公告获取基本面信号
            fundamental_signal = _get_fundamental_signal(symbol, agent)
            if fundamental_signal:
                source_signals.append(fundamental_signal)

            # 融合信号
            fused = _signal_fusion.fuse(source_signals)
            fused_results.append(fused.to_dict())

        from datetime import datetime
        return {
            "fused_signals": fused_results,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        logger.error("Fused signals failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


def _get_fundamental_signal(symbol: str, agent: MonitorAgent) -> Optional[SourceSignal]:
    """从新闻/公告获取基本面信号"""
    try:
        if not agent._news_searcher:
            return None
        news_items = agent._news_searcher.search(symbol, days=7, max_results=10)
        if not news_items:
            return None

        import numpy as np
        sentiments = [n.sentiment for n in news_items]
        avg_sentiment = float(np.mean(sentiments))

        if avg_sentiment > 0.3:
            direction = SignalDirection.BUY
        elif avg_sentiment < -0.3:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD

        return SourceSignal(
            source="fundamental",
            symbol=symbol,
            direction=direction,
            confidence=min(1.0, abs(avg_sentiment)),
            reason=f"基本面: {len(news_items)}条新闻, 均值={avg_sentiment:.2f}",
        )
    except Exception:
        return None


@router.post("/stop-monitoring")
def stop_monitoring(_user=Depends(get_required_user)) -> Dict[str, str]:
    """停止实时扫描"""
    try:
        agent = _get_agent()
        agent.stop_monitoring()
        return {"status": "monitoring_stopped"}
    except Exception as exc:
        logger.error("Stop monitoring failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/premarket-briefing")
def get_premarket_briefing(
    symbols: Optional[List[str]] = None,
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """获取盘前简报（结构化）。

    包含隔夜全球市场概览、自选股关键新闻、技术关键位、建议关注标的。
    """
    try:
        agent = _get_agent()
        targets = symbols or _watchlist
        if not targets:
            raise HTTPException(status_code=400, detail="No watchlist or symbols provided")
        return agent.generate_premarket_briefing(targets)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Premarket briefing failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/postmarket-summary")
def get_postmarket_summary(
    symbols: Optional[List[str]] = None,
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """获取收盘总结（结构化）。

    包含大盘指数表现、自选股表现、异动与成交量、当日关键信号、次日催化剂预览。
    """
    try:
        agent = _get_agent()
        targets = symbols or _watchlist
        if not targets:
            raise HTTPException(status_code=400, detail="No watchlist or symbols provided")
        return agent.generate_postmarket_summary(targets)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Postmarket summary failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sentiment/{symbol}")
def get_sentiment_analysis(
    symbol: str,
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """获取指定股票的情绪分析。

    基于新闻文本进行关键词情绪评分，并检测情绪突变。
    """
    try:
        agent = _get_agent()

        # 获取新闻文本
        texts: list[str] = []
        if agent._news_searcher:
            try:
                news_items = agent._news_searcher.search(symbol, days=3)
                for n in news_items:
                    title = getattr(n, "title", "") or ""
                    content = getattr(n, "content", "") or ""
                    if title:
                        texts.append(title)
                    if content:
                        texts.append(content)
            except Exception:
                logger.debug("News search failed for sentiment analysis: %s", symbol)

        # 如果没有新闻，尝试从工作记忆获取
        if not texts:
            memory_entries = agent._memory.query(symbol=symbol)
            for entry in memory_entries:
                reason = entry.get("reason", "")
                if reason:
                    texts.append(reason)

        # 情绪分析
        sentiment_result = agent._analyze_social_sentiment(texts) if texts else {
            "score": 0.0,
            "confidence": 0.0,
            "key_phrases": [],
            "distribution": {"positive": 0, "negative": 0, "neutral": 0},
        }

        # 情绪突变检测
        sentiment_history = [
            e["sentiment"] for e in agent._memory.query(symbol=symbol)
            if "sentiment" in e
        ]
        anomaly_detected = agent._detect_sentiment_anomaly(sentiment_history)

        return {
            "symbol": symbol,
            "sentiment": sentiment_result,
            "anomaly_detected": anomaly_detected,
            "sentiment_history_length": len(sentiment_history),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        logger.error("Sentiment analysis failed for %s: %s", symbol, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/risk-control")
def get_risk_control(_user=Depends(get_current_user)) -> Dict[str, Any]:
    """获取动态风控参数。

    基于沪深300近20日波动率判断市场环境，动态调整风控参数。
    """
    try:
        # 计算市场波动率
        sigma = _compute_market_volatility()

        if sigma < 0.01:
            environment = "calm"
            risk_level = "low"
            max_position_pct = 0.30
            max_daily_loss_pct = 0.05
        elif sigma < 0.02:
            environment = "volatile"
            risk_level = "medium"
            max_position_pct = 0.20
            max_daily_loss_pct = 0.03
        else:
            environment = "extreme"
            risk_level = "high"
            max_position_pct = 0.10
            max_daily_loss_pct = 0.02

        return {
            "environment": environment,
            "risk_level": risk_level,
            "max_position_pct": max_position_pct,
            "max_daily_loss_pct": max_daily_loss_pct,
            "max_drawdown_pct": 0.15,
            "volatility": round(sigma, 6),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        logger.error("Risk control computation failed: %s", exc)
        # 降级返回默认值
        return {
            "environment": "volatile",
            "risk_level": "medium",
            "max_position_pct": 0.20,
            "max_daily_loss_pct": 0.03,
            "max_drawdown_pct": 0.15,
            "volatility": 0.0,
            "timestamp": datetime.now().isoformat(),
        }


def _compute_market_volatility() -> float:
    """计算沪深300近20日收益率标准差作为市场波动率指标。

    优先从 BaoStock 获取真实数据，失败时返回默认值 0.015。
    """
    try:
        import baostock as bs
        import numpy as np

        lg = bs.login()
        if lg.error_code != "0":
            return 0.015

        try:
            from datetime import timedelta
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")

            rs = bs.query_history_k_data_plus(
                "sh.000300",
                "date,close",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
            )

            closes = []
            while rs.error_code == "0" and rs.next():
                row = rs.get_row_data()
                if len(row) >= 2 and row[1]:
                    try:
                        closes.append(float(row[1]))
                    except (ValueError, TypeError):
                        continue

            if len(closes) < 5:
                return 0.015

            # 计算近20日日收益率标准差
            recent = closes[-21:]  # 21 个收盘价 → 20 个收益率
            returns = np.diff(recent) / recent[:-1]
            sigma = float(np.std(returns))
            return sigma
        finally:
            bs.logout()
    except ImportError:
        logger.debug("baostock/numpy 未安装，使用默认波动率")
        return 0.015
    except Exception as exc:
        logger.debug("市场波动率计算失败: %s，使用默认值", exc)
        return 0.015
