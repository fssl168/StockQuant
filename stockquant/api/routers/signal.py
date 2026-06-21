# -*- coding: utf-8 -*-
"""F019 信号管线 API — 暴露 SignalManager 到 REST 端点"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from stockquant.api.deps import get_current_user, get_required_user, get_trader_user
from stockquant.api.schemas import AddSignalRequest, UserToken

from stockquant.strategy.signal import SignalManager, Signal, SignalSide, SignalSource

router = APIRouter(prefix="/signals", tags=["信号管线"])
logger = logging.getLogger("stockquant.api.signals")

# 全局 SignalManager 实例
_signal_manager = SignalManager()


def get_signal_manager() -> SignalManager:
    return _signal_manager


@router.get("", summary="获取活跃信号列表")
async def list_signals(
    symbol: Optional[str] = None,
    side: Optional[str] = None,
    source: Optional[str] = None,
    _user: UserToken = Depends(get_required_user),
) -> Dict[str, Any]:
    """获取当前活跃信号列表，支持按标的/方向/来源过滤"""
    signals = _signal_manager.get_active_signals()
    if symbol:
        signals = [s for s in signals if s.symbol == symbol]
    if side:
        signals = [s for s in signals if s.side.value == side.upper()]
    if source:
        signals = [s for s in signals if s.source.value == source]
    return {"signals": [_signal_to_dict(s) for s in signals], "count": len(signals)}


@router.post("", summary="手动添加信号")
async def add_signal(payload: AddSignalRequest, _user: UserToken = Depends(get_required_user)) -> Dict[str, Any]:
    """手动添加交易信号"""
    try:
        signal = Signal(
            symbol=payload.symbol,
            side=SignalSide(payload.side.upper()),
            source=SignalSource(payload.source),
            confidence=payload.confidence,
            reason=payload.reason,
            price=payload.price,
            quantity=payload.quantity,
        )
        result = _signal_manager.add_signal(signal)
        return {"success": True, "signal": _signal_to_dict(signal), "action": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{signal_id}", summary="移除信号")
async def remove_signal(signal_id: str, _user: UserToken = Depends(get_trader_user)) -> Dict[str, Any]:
    """移除指定信号"""
    signals = _signal_manager.get_active_signals()
    target = None
    for s in signals:
        if str(id(s)) == signal_id:
            target = s
            break
    if not target:
        raise HTTPException(status_code=404, detail="信号不存在")
    _signal_manager.cleanup_expired()
    return {"success": True}


@router.get("/audit", summary="信号审计日志")
async def signal_audit(
    symbol: Optional[str] = None,
    limit: int = 50,
    _user: UserToken = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取信号审计日志"""
    logs = _signal_manager.get_audit_logs()
    if symbol:
        logs = [l for l in logs if l.signal.symbol == symbol]
    return {"logs": [_audit_to_dict(l) for l in logs[-limit:]], "count": len(logs)}


@router.get("/stats", summary="信号统计")
async def signal_stats(_user: UserToken = Depends(get_current_user)) -> Dict[str, Any]:
    """获取信号管线统计信息"""
    signals = _signal_manager.get_active_signals()
    return {
        "active_count": len(signals),
        "by_side": {
            "BUY": len([s for s in signals if s.side == SignalSide.BUY]),
            "SELL": len([s for s in signals if s.side == SignalSide.SELL]),
            "HOLD": len([s for s in signals if s.side == SignalSide.HOLD]),
        },
        "by_source": {
            s.value: len([sig for sig in signals if sig.source == s])
            for s in SignalSource
        },
    }


def _signal_to_dict(signal: Signal) -> Dict[str, Any]:
    return {
        "id": str(id(signal)),
        "symbol": signal.symbol,
        "side": signal.side.value,
        "source": signal.source.value,
        "confidence": signal.confidence,
        "reason": signal.reason,
        "price": signal.price,
        "quantity": signal.quantity,
        "timestamp": signal.timestamp,
        "priority": signal.priority,
    }


def _audit_to_dict(log: Any) -> Dict[str, Any]:
    return {
        "signal": _signal_to_dict(log.signal) if hasattr(log, "signal") else {},
        "action": log.action if hasattr(log, "action") else "",
        "reason": log.reason if hasattr(log, "reason") else "",
        "timestamp": log.timestamp if hasattr(log, "timestamp") else None,
    }
