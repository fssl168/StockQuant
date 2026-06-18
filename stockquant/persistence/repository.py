# -*- coding: utf-8 -*-
"""数据持久化 — CRUD 仓库操作"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from stockquant.persistence.models import (
    AnalysisHistory,
    AuditLogModel,
    BacktestResult,
    ChatMessage,
    KlineData,
    Watchlist,
    get_engine,
)

logger = logging.getLogger(__name__)


def _session_factory(engine_url: str):
    """Create a sessionmaker bound to the given engine URL."""
    from sqlalchemy.orm import sessionmaker
    return sessionmaker(bind=get_engine(engine_url))


def _result_to_dict(result: BacktestResult) -> Dict[str, Any]:
    """BacktestResult ORM → dict."""
    return {
        "id": result.id,
        "strategy_name": result.strategy_name,
        "symbol": result.symbol,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "initial_cash": result.initial_cash,
        "final_equity": result.final_equity,
        "metrics": result.metrics if isinstance(result.metrics, dict) else json.loads(result.metrics) if result.metrics else {},
        "equity_curve": result.equity_curve if isinstance(result.equity_curve, list) else json.loads(result.equity_curve) if result.equity_curve else [],
        "trades_summary": result.trades_summary if isinstance(result.trades_summary, list) else json.loads(result.trades_summary) if result.trades_summary else [],
        "created_at": result.created_at,
    }


def save_backtest(
    engine_url: str,
    strategy_name: str,
    symbol: str,
    start_date: str,
    end_date: str,
    initial_cash: float,
    final_equity: float,
    metrics: Dict[str, Any],
    equity_curve: List[tuple],
    trades_summary: List[Dict],
) -> int:
    """保存回测结果，返回记录 ID。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = BacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            final_equity=final_equity,
            metrics=json.dumps(metrics),
            equity_curve=json.dumps([list(t) if isinstance(t, (tuple, list)) else t for t in equity_curve]),
            trades_summary=json.dumps(trades_summary),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        logger.info("Saved backtest result id=%d strategy=%s symbol=%s", row.id, strategy_name, symbol)
        return row.id


def get_backtest(engine_url: str, result_id: int) -> Optional[Dict]:
    """获取单个回测结果。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = session.get(BacktestResult, result_id)
        if row is None:
            return None
        return _result_to_dict(row)


def list_backtests(engine_url: str, limit: int = 50, offset: int = 0) -> List[Dict]:
    """列出回测结果（按 created_at 倒序）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = (
            select(BacktestResult)
            .order_by(BacktestResult.created_at.desc(), BacktestResult.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = session.execute(stmt).scalars().all()
        return [_result_to_dict(r) for r in rows]


def delete_backtest(engine_url: str, result_id: int) -> bool:
    """删除回测结果。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = session.get(BacktestResult, result_id)
        if row is None:
            return False
        session.delete(row)
        session.commit()
        logger.info("Deleted backtest result id=%d", result_id)
        return True


# ── KlineData helpers ────────────────────────────────────────────────────


def save_kline(
    engine_url: str,
    symbol: str,
    timeframe: str,
    bars: List[Dict],
) -> int:
    """批量保存 K 线数据。返回插入的行数。"""
    session_factory = _session_factory(engine_url)

    inserted = 0
    with session_factory() as session:
        for bar in bars:
            row = KlineData(
                symbol=symbol,
                timeframe=timeframe,
                datetime=datetime.fromisoformat(bar["datetime"]) if isinstance(bar.get("datetime"), str) else bar["datetime"],
                open=float(bar["open"]),
                high=float(bar["high"]),
                low=float(bar["low"]),
                close=float(bar["close"]),
                volume=int(bar.get("volume", 0)),
                amount=float(bar.get("amount", 0.0)),
            )
            session.add(row)
            inserted += 1
        session.commit()
    logger.info("Saved %d kline bars symbol=%s timeframe=%s", inserted, symbol, timeframe)
    return inserted


def get_kline(
    engine_url: str,
    symbol: str,
    timeframe: str = "1d",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> List[Dict]:
    """获取 K 线数据（可按日期范围过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(KlineData).where(
            KlineData.symbol == symbol,
            KlineData.timeframe == timeframe,
        )
        if start:
            stmt = stmt.where(KlineData.datetime >= datetime.fromisoformat(start))
        if end:
            stmt = stmt.where(KlineData.datetime <= datetime.fromisoformat(end))
        stmt = stmt.order_by(KlineData.datetime.asc())

        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "timeframe": r.timeframe,
                "datetime": r.datetime.isoformat() if r.datetime else None,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
                "amount": r.amount,
            }
            for r in rows
        ]


# ── AnalysisHistory helpers ──────────────────────────────────────────────


def save_analysis(
    engine_url: str,
    symbol: str,
    analysis_type: str,
    input_data: Dict,
    output_data: Dict,
) -> int:
    """保存 AI 分析结果，返回记录 ID。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = AnalysisHistory(
            symbol=symbol,
            analysis_type=analysis_type,
            input_data=json.dumps(input_data),
            output_data=json.dumps(output_data),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        logger.info("Saved analysis id=%d symbol=%s type=%s", row.id, symbol, analysis_type)
        return row.id


def list_analyses(
    engine_url: str,
    symbol: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """列出分析历史。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(AnalysisHistory).order_by(
            AnalysisHistory.created_at.desc(), AnalysisHistory.id.desc()
        ).limit(limit)
        if symbol:
            stmt = stmt.where(AnalysisHistory.symbol == symbol)

        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "analysis_type": r.analysis_type,
                "input_data": json.loads(r.input_data) if isinstance(r.input_data, str) else r.input_data,
                "output_data": json.loads(r.output_data) if isinstance(r.output_data, str) else r.output_data,
                "created_at": r.created_at,
            }
            for r in rows
        ]


# ── AuditLog helpers ────────────────────────────────────────────────────


def save_audit_log(
    engine_url: str,
    timestamp: datetime,
    signal_source: str,
    symbol: str,
    direction: str,
    original_signal: Dict,
    ai_decision: Dict,
    final_action: str,
    user_confirmed: Optional[bool] = None,
) -> int:
    """保存 AI 决策审计日志，返回记录 ID。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = AuditLogModel(
            timestamp=timestamp,
            signal_source=signal_source,
            symbol=symbol,
            direction=direction,
            original_signal=json.dumps(original_signal, default=str),
            ai_decision=json.dumps(ai_decision, default=str),
            final_action=final_action,
            user_confirmed=int(user_confirmed) if user_confirmed is not None else None,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        logger.info("Saved audit log id=%d symbol=%s action=%s", row.id, symbol, final_action)
        return row.id


def list_audit_logs(
    engine_url: str,
    symbol: Optional[str] = None,
    signal_source: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """列出审计日志。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(AuditLogModel).order_by(
            AuditLogModel.timestamp.desc(), AuditLogModel.id.desc()
        ).limit(limit)
        if symbol:
            stmt = stmt.where(AuditLogModel.symbol == symbol)
        if signal_source:
            stmt = stmt.where(AuditLogModel.signal_source == signal_source)

        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "signal_source": r.signal_source,
                "symbol": r.symbol,
                "direction": r.direction,
                "original_signal": json.loads(r.original_signal) if isinstance(r.original_signal, str) else r.original_signal,
                "ai_decision": json.loads(r.ai_decision) if isinstance(r.ai_decision, str) else r.ai_decision,
                "final_action": r.final_action,
                "user_confirmed": bool(r.user_confirmed) if r.user_confirmed is not None else None,
                "created_at": r.created_at,
            }
            for r in rows
        ]


def get_audit_log(engine_url: str, log_id: int) -> Optional[Dict]:
    """获取单条审计日志。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = session.get(AuditLogModel, log_id)
        if row is None:
            return None
        return {
            "id": row.id,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "signal_source": row.signal_source,
            "symbol": row.symbol,
            "direction": row.direction,
            "original_signal": json.loads(row.original_signal) if isinstance(row.original_signal, str) else row.original_signal,
            "ai_decision": json.loads(row.ai_decision) if isinstance(row.ai_decision, str) else row.ai_decision,
            "final_action": row.final_action,
            "user_confirmed": bool(row.user_confirmed) if row.user_confirmed is not None else None,
            "created_at": row.created_at,
        }


def save_chat_message(
    engine_url: str,
    conversation_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict] = None,
) -> int:
    """保存对话消息。

    Parameters
    ----------
    engine_url : str
        SQLAlchemy 引擎 URL
    conversation_id : str
        会话 ID（映射到 session_id）
    role : str
        消息角色 (user/assistant/system)
    content : str
        消息内容
    metadata : dict | None
        附加元数据

    Returns
    -------
    int
        保存的消息 ID
    """
    engine = get_engine(engine_url)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        row = ChatMessage(
            session_id=conversation_id,
            role=role,
            content=content,
        )
        session.add(row)
        session.commit()
        return row.id


def get_chat_messages(
    engine_url: str,
    session_id: str,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """从数据库加载会话消息。

    Parameters
    ----------
    engine_url : str
        SQLAlchemy 引擎 URL
    session_id : str
        会话 ID
    limit : int
        最大返回条数

    Returns
    -------
    list[dict]
        消息列表，按 created_at 升序
    """
    engine = get_engine(engine_url)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        rows = (
            session.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
            .all()
        )
        return [
            {
                "role": row.role,
                "content": row.content,
                "timestamp": row.created_at.isoformat(),
            }
            for row in rows
        ]


def delete_chat_messages(engine_url: str, session_id: str) -> None:
    """删除会话的所有消息。"""
    engine = get_engine(engine_url)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        session.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        session.commit()


def list_chat_sessions(
    engine_url: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """列出所有会话（按最新消息时间排序）。"""
    engine = get_engine(engine_url)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        from sqlalchemy import func, desc
        # 获取会话列表
        rows = (
            session.query(
                ChatMessage.session_id,
                func.max(ChatMessage.created_at).label("latest_at"),
                func.min(ChatMessage.id).label("first_msg_id"),
                func.count(ChatMessage.id).label("message_count"),
            )
            .group_by(ChatMessage.session_id)
            .order_by(desc("latest_at"))
            .limit(limit)
            .all()
        )
        
        result = []
        for row in rows:
            # 获取第一条用户消息作为标题
            title = None
            if row.first_msg_id:
                first_msg = session.query(ChatMessage).filter(
                    ChatMessage.id == row.first_msg_id
                ).first()
                if first_msg and first_msg.role == "user":
                    title = first_msg.content[:30] if len(first_msg.content) > 30 else first_msg.content
            
            result.append({
                "id": row.session_id,
                "created_at": row.latest_at.isoformat() if row.latest_at else None,
                "message_count": row.message_count,
                "title": title,
            })
        return result


def get_watchlist(engine_url: str) -> List[str]:
    """获取自选股列表"""
    engine = get_engine(engine_url)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        rows = session.query(Watchlist).order_by(Watchlist.created_at).all()
        return [row.symbol for row in rows]


def add_to_watchlist(engine_url: str, symbols: List[str]) -> None:
    """添加股票到自选股"""
    import uuid
    engine = get_engine(engine_url)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        for symbol in symbols:
            # 检查是否已存在
            existing = session.query(Watchlist).filter(Watchlist.symbol == symbol).first()
            if not existing:
                watchlist_item = Watchlist(
                    id=str(uuid.uuid4()),
                    symbol=symbol,
                    created_at=datetime.now(),
                )
                session.add(watchlist_item)
        session.commit()


def remove_from_watchlist(engine_url: str, symbols: List[str]) -> None:
    """从自选股移除股票"""
    engine = get_engine(engine_url)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        for symbol in symbols:
            session.query(Watchlist).filter(Watchlist.symbol == symbol).delete()
        session.commit()
