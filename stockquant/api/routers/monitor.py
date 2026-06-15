# -*- coding: utf-8 -*-
"""F024 盯盘 API 路由 — 自选股管理 + 告警查询 + WebSocket 实时推送"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from stockquant.ai.monitor_agent import MonitorAgent, MonitorSignal
from stockquant.ai.news_searcher import NewsSearcher
from stockquant.data import DataFetcherManager

router = APIRouter(prefix="/api/monitor", tags=["monitor"])

logger = logging.getLogger("stockquant.ai")


# ── 全局监控状态（生产环境应使用 Redis 等） ──

_watchlist: list[str] = []
_alerts: list[MonitorSignal] = []
_connections: list[WebSocket] = []
_agent: Optional[MonitorAgent] = None
_agent_lock = threading.Lock()


def _get_agent() -> MonitorAgent:
    """获取或创建全局 MonitorAgent 实例（单例）。"""
    global _agent
    if _agent is None:
        with _agent_lock:
            if _agent is None:
                _agent = MonitorAgent(
                    fetcher_manager=DataFetcherManager(),
                    news_searcher=NewsSearcher(),
                    threshold=0.5,
                )
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
    return _watchlist


@router.delete("/watchlist")
def remove_from_watchlist(symbols: list[str]) -> list[str]:
    """从自选股移除"""
    agent = _get_agent()
    agent.remove_watchlist(symbols)
    for s in symbols:
        if s in _watchlist:
            _watchlist.remove(s)
    return _watchlist


@router.get("/alerts", response_model=List[Dict[str, Any]])
def get_alerts(limit: int = 50) -> List[Dict[str, Any]]:
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
def get_status() -> Dict[str, Any]:
    """获取监控状态"""
    try:
        agent = _get_agent()
        return {
            "watchlist": _watchlist,
            "alerts_count": len(agent.get_alerts()),
            "scan_count": agent.get_scan_count(),
            "connections_count": len(_connections),
            "running": agent._running,
        }
    except Exception as exc:
        logger.error("Status check failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.websocket("/ws/alerts")
async def websocket_alerts(ws: WebSocket) -> None:
    """WebSocket 实时告警推送"""
    await ws.accept()
    _connections.append(ws)
    logger.info("Monitor WebSocket connected. Total connections: %d", len(_connections))

    def _on_signal(signal: "MonitorSignal") -> None:
        """将高置信度信号推送到 WebSocket"""
        try:
            import asyncio
            data = json.dumps(_signal_to_dict(signal), ensure_ascii=False)
            loop = asyncio.get_running_loop()
            loop.create_task(ws.send_text(data))
        except Exception:
            pass  # 推送失败不影响主流程

    agent = _get_agent()
    agent.on_alert(_on_signal)

    try:
        while True:
            # 等待客户端心跳
            await ws.receive_text()
    except WebSocketDisconnect:
        _connections.remove(ws)
        logger.info("Monitor WebSocket disconnected. Total connections: %d", len(_connections))


@router.post("/start-monitoring")
def start_monitoring(symbols: Optional[List[str]] = None) -> Dict[str, str]:
    """启动实时扫描"""
    try:
        agent = _get_agent()
        targets = symbols or _watchlist
        if not targets:
            raise HTTPException(status_code=400, detail="No watchlist or symbols provided")
        agent.start_monitoring(targets)
        return {"status": "monitoring_started"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Start monitoring failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/stop-monitoring")
def stop_monitoring() -> Dict[str, str]:
    """停止实时扫描"""
    try:
        agent = _get_agent()
        agent.stop_monitoring()
        return {"status": "monitoring_stopped"}
    except Exception as exc:
        logger.error("Stop monitoring failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
