# -*- coding: utf-8 -*-
"""F024 盯盘 API 路由 — 自选股管理 + 告警查询"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from stockquant.ai.models import MonitorSignal

router = APIRouter(prefix="/api/monitor", tags=["monitor"])

logger = logging.getLogger("stockquant.ai")

# 全局监控状态（生产环境应使用 Redis 等）
_watchlist: list[str] = []
_alerts: list[MonitorSignal] = []
_connections: list[WebSocket] = []


@router.get("/watchlist", response_model=List[str])
def get_watchlist() -> List[str]:
    """获取自选股列表"""
    return _watchlist


@router.post("/watchlist")
def add_to_watchlist(symbols: list[str]) -> list[str]:
    """添加到自选股"""
    for s in symbols:
        if s not in _watchlist:
            _watchlist.append(s)
    return _watchlist


@router.delete("/watchlist")
def remove_from_watchlist(symbols: list[str]) -> list[str]:
    """从自选股移除"""
    for s in symbols:
        if s in _watchlist:
            _watchlist.remove(s)
    return _watchlist


@router.get("/alerts", response_model=List[Dict[str, Any]])
def get_alerts(limit: int = 50) -> List[Dict[str, Any]]:
    """获取告警记录"""
    return [_signal_to_dict(a) for a in _alerts[-limit:]]


@router.get("/scan/{symbol}")
def scan_symbol(symbol: str) -> List[Dict[str, Any]]:
    """扫描指定股票信号"""
    try:
        from stockquant.ai import MonitorAgent
        from stockquant.data import DataFetcherManager
        from stockquant.ai import NewsSearcher

        fetcher = DataFetcherManager()
        searcher = NewsSearcher()
        agent = MonitorAgent(
            fetcher_manager=fetcher,
            news_searcher=searcher,
            threshold=0.5,
        )
        signals = agent.scan([symbol])
        return [_signal_to_dict(s) for s in signals]
    except Exception as exc:
        logger.error("Scan failed for %s: %s", symbol, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.websocket("/ws/alerts")
async def websocket_alerts(ws: WebSocket) -> None:
    """WebSocket 实时告警推送"""
    await ws.accept()
    _connections.append(ws)

    try:
        while True:
            # 等待客户端心跳
            await ws.receive_text()
    except WebSocketDisconnect:
        _connections.remove(ws)


def push_alert(signal: MonitorSignal) -> None:
    """推送告警到所有 WebSocket 连接"""
    import json

    data = json.dumps(_signal_to_dict(signal), ensure_ascii=False)
    for ws in list(_connections):
        try:
            ws.send_text(data)
        except Exception:
            _connections.remove(ws)


def _signal_to_dict(signal: MonitorSignal) -> Dict[str, Any]:
    return {
        "symbol": signal.symbol,
        "direction": signal.direction,
        "reason": signal.reason,
        "confidence": signal.confidence,
        "signal_type": signal.signal_type,
        "timestamp": signal.timestamp.isoformat() if hasattr(signal.timestamp, "isoformat") else str(signal.timestamp),
    }
