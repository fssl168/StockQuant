# -*- coding: utf-8 -*-
"""数据持久化 — CRUD 仓库操作"""


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
    BacktestTask,
    CashFlow,
    ChatMessage,
    CollectTask,
    ComparisonHistory,
    KlineData,
    MonitorAlert,
    Notification,
    OptimizeTask,
    OpAuditLog,
    Order,
    OrderAudit,
    PendingOrder,
    PipelineTask,
    Position,
    RiskEvent,
    SchedulerTask,
    StrategyModel,
    TradingAccount,
    UserModel,
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
    user_id: Optional[str] = None,
    strategy_name: str = "",
    symbol: str = "",
    start_date: str = "",
    end_date: str = "",
    initial_cash: float = 0.0,
    final_equity: float = 0.0,
    metrics: Optional[Dict[str, Any]] = None,
    equity_curve: Optional[List[tuple]] = None,
    trades_summary: Optional[List[Dict]] = None,
) -> int:
    """保存回测结果，返回记录 ID。"""
    session_factory = _session_factory(engine_url)
    if metrics is None:
        metrics = {}
    if equity_curve is None:
        equity_curve = []
    if trades_summary is None:
        trades_summary = []

    with session_factory() as session:
        row = BacktestResult(
            user_id=user_id or "",
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
        logger.info("Saved backtest result id=%d user=%s strategy=%s symbol=%s", row.id, user_id, strategy_name, symbol)
        return row.id


def get_backtest(engine_url: str, user_id: Optional[str] = None, result_id: int = 0) -> Optional[Dict]:
    """获取单个回测结果（需 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = session.get(BacktestResult, result_id)
        if row is None or (user_id is not None and row.user_id != user_id):
            return None
        return _result_to_dict(row)


def list_backtests(engine_url: str, user_id: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict]:
    """列出回测结果（按 user_id 过滤，按 created_at 倒序）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(BacktestResult).order_by(BacktestResult.created_at.desc(), BacktestResult.id.desc()).limit(limit).offset(offset)
        if user_id is not None:
            stmt = stmt.where(BacktestResult.user_id == user_id)
        rows = session.execute(stmt).scalars().all()
        return [_result_to_dict(r) for r in rows]


def delete_backtest(engine_url: str, user_id: Optional[str] = None, result_id: int = 0) -> bool:
    """删除回测结果（需 user_id 验证）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = session.get(BacktestResult, result_id)
        if row is None or (user_id is not None and row.user_id != user_id):
            return False
        session.delete(row)
        session.commit()
        logger.info("Deleted backtest result id=%d user=%s", result_id, user_id)
        return True


# ── KlineData helpers ────────────────────────────────────────────────────


def save_kline(
    engine_url: str,
    symbol: str = "",
    timeframe: str = "1d",
    bars: Optional[List[Dict]] = None,
) -> int:
    """批量保存 K 线数据。返回插入的行数。"""
    session_factory = _session_factory(engine_url)
    if bars is None:
        bars = []

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
    symbol: str = "",
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
    user_id: Optional[str] = None,
    symbol: str = "",
    analysis_type: str = "",
    input_data: Optional[Dict] = None,
    output_data: Optional[Dict] = None,
) -> int:
    """保存 AI 分析结果，返回记录 ID。"""
    session_factory = _session_factory(engine_url)
    if input_data is None:
        input_data = {}
    if output_data is None:
        output_data = {}

    with session_factory() as session:
        row = AnalysisHistory(
            user_id=user_id or "",
            symbol=symbol,
            analysis_type=analysis_type,
            input_data=json.dumps(input_data),
            output_data=json.dumps(output_data),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        logger.info("Saved analysis id=%d user=%s symbol=%s type=%s", row.id, user_id, symbol, analysis_type)
        return row.id


def list_analyses(
    engine_url: str,
    user_id: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """列出分析历史（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(AnalysisHistory).order_by(
            AnalysisHistory.created_at.desc(), AnalysisHistory.id.desc()
        ).limit(limit)
        if user_id is not None:
            stmt = stmt.where(AnalysisHistory.user_id == user_id)
        if symbol:
            stmt = stmt.where(AnalysisHistory.symbol == symbol)

        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
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
    user_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    signal_source: str = "",
    symbol: str = "",
    direction: str = "",
    original_signal: Optional[Dict] = None,
    ai_decision: Optional[Dict] = None,
    final_action: str = "",
    user_confirmed: Optional[bool] = None,
    llm_model: Optional[str] = None,
    llm_prompt: Optional[str] = None,
    llm_response: Optional[str] = None,
    llm_reasoning_content: Optional[str] = None,
    llm_tokens_used: Optional[int] = None,
    llm_cost: Optional[float] = None,
) -> int:
    """保存 AI 决策审计日志，返回记录 ID。"""
    session_factory = _session_factory(engine_url)
    if original_signal is None:
        original_signal = {}
    if ai_decision is None:
        ai_decision = {}
    if timestamp is None:
        timestamp = datetime.now()

    with session_factory() as session:
        row = AuditLogModel(
            user_id=user_id or "",
            timestamp=timestamp,
            signal_source=signal_source,
            symbol=symbol,
            direction=direction,
            original_signal=json.dumps(original_signal, default=str),
            ai_decision=json.dumps(ai_decision, default=str),
            final_action=final_action,
            user_confirmed=int(user_confirmed) if user_confirmed is not None else None,
            llm_model=llm_model,
            llm_prompt=llm_prompt,
            llm_response=llm_response,
            llm_reasoning_content=llm_reasoning_content,
            llm_tokens_used=llm_tokens_used,
            llm_cost=llm_cost,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        logger.info("Saved audit log id=%d user=%s symbol=%s action=%s", row.id, user_id, symbol, final_action)
        return row.id


def list_audit_logs(
    engine_url: str,
    user_id: Optional[str] = None,
    symbol: Optional[str] = None,
    signal_source: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """列出审计日志（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(AuditLogModel).order_by(
            AuditLogModel.timestamp.desc(), AuditLogModel.id.desc()
        ).limit(limit)
        if user_id is not None:
            stmt = stmt.where(AuditLogModel.user_id == user_id)
        if symbol:
            stmt = stmt.where(AuditLogModel.symbol == symbol)
        if signal_source:
            stmt = stmt.where(AuditLogModel.signal_source == signal_source)

        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "signal_source": r.signal_source,
                "symbol": r.symbol,
                "direction": r.direction,
                "original_signal": json.loads(r.original_signal) if isinstance(r.original_signal, str) else r.original_signal,
                "ai_decision": json.loads(r.ai_decision) if isinstance(r.ai_decision, str) else r.ai_decision,
                "final_action": r.final_action,
                "user_confirmed": bool(r.user_confirmed) if r.user_confirmed is not None else None,
                "llm_model": r.llm_model,
                "llm_prompt": r.llm_prompt,
                "llm_response": r.llm_response,
                "llm_reasoning_content": r.llm_reasoning_content,
                "llm_tokens_used": r.llm_tokens_used,
                "llm_cost": r.llm_cost,
                "created_at": r.created_at,
            }
            for r in rows
        ]


def get_audit_log(engine_url: str, user_id: Optional[str] = None, log_id: int = 0) -> Optional[Dict]:
    """获取单条审计日志（需 user_id 验证）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = session.get(AuditLogModel, log_id)
        if row is None or (user_id is not None and row.user_id != user_id):
            return None
        return {
            "id": row.id,
            "user_id": row.user_id,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "signal_source": row.signal_source,
            "symbol": row.symbol,
            "direction": row.direction,
            "original_signal": json.loads(row.original_signal) if isinstance(row.original_signal, str) else row.original_signal,
            "ai_decision": json.loads(row.ai_decision) if isinstance(row.ai_decision, str) else row.ai_decision,
            "final_action": row.final_action,
            "user_confirmed": bool(row.user_confirmed) if row.user_confirmed is not None else None,
            "llm_model": row.llm_model,
            "llm_prompt": row.llm_prompt,
            "llm_response": row.llm_response,
            "llm_reasoning_content": row.llm_reasoning_content,
            "llm_tokens_used": row.llm_tokens_used,
            "llm_cost": row.llm_cost,
            "created_at": row.created_at,
        }


def save_chat_message(
    engine_url: str,
    user_id: Optional[str] = None,
    conversation_id: str = "",
    role: str = "",
    content: str = "",
    metadata: Optional[Dict] = None,
) -> int:
    """保存对话消息。

    Parameters
    ----------
    engine_url : str
        SQLAlchemy 引擎 URL
    user_id : str | None
        用户 ID
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
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = ChatMessage(
            user_id=user_id or "",
            session_id=conversation_id,
            role=role,
            content=content,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        logger.info("Saved chat message id=%d user=%s session=%s role=%s", row.id, user_id, conversation_id, role)
        return row.id


def get_chat_messages(
    engine_url: str,
    user_id: Optional[str] = None,
    session_id: str = "",
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """从数据库加载会话消息（按 user_id 过滤）。

    Parameters
    ----------
    engine_url : str
        SQLAlchemy 引擎 URL
    user_id : str | None
        用户 ID
    session_id : str
        会话 ID
    limit : int
        最大返回条数

    Returns
    -------
    list[dict]
        消息列表，按 created_at 升序
    """
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(ChatMessage).where(ChatMessage.session_id == session_id)
        if user_id is not None:
            stmt = stmt.where(ChatMessage.user_id == user_id)
        stmt = stmt.order_by(ChatMessage.created_at.asc()).limit(limit)

        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "role": row.role,
                "content": row.content,
                "timestamp": row.created_at.isoformat(),
            }
            for row in rows
        ]


def delete_chat_messages(engine_url: str, user_id: Optional[str] = None, session_id: str = "") -> None:
    """删除会话的所有消息（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(ChatMessage).where(ChatMessage.session_id == session_id)
        if user_id is not None:
            stmt = stmt.where(ChatMessage.user_id == user_id)
        session.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete(synchronize_session=False)
        if user_id is not None:
            session.query(ChatMessage).filter(
                ChatMessage.user_id == user_id, ChatMessage.session_id == session_id
            ).delete(synchronize_session=False)
        session.commit()
        logger.info("Deleted chat messages user=%s session=%s", user_id, session_id)


def list_chat_sessions(
    engine_url: str,
    user_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """列出所有会话（按 user_id 过滤，按最新消息时间排序）。"""
    from sqlalchemy import func, desc

    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        # 获取会话列表
        stmt = (
            select(
                ChatMessage.session_id,
                func.max(ChatMessage.created_at).label("latest_at"),
                func.min(ChatMessage.id).label("first_msg_id"),
                func.count(ChatMessage.id).label("message_count"),
            )
            .group_by(ChatMessage.session_id)
            .order_by(desc("latest_at"))
            .limit(limit)
        )
        if user_id is not None:
            stmt = stmt.where(ChatMessage.user_id == user_id)

        rows = session.execute(stmt).scalars().all()

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
                "user_id": user_id or "",
                "created_at": row.latest_at.isoformat() if row.latest_at else None,
                "message_count": row.message_count,
                "title": title,
            })
        return result


def get_watchlist(engine_url: str, user_id: Optional[str] = None) -> List[str]:
    """获取自选股列表（按 user_id 过滤）"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(Watchlist).order_by(Watchlist.created_at)
        if user_id is not None:
            stmt = stmt.where(Watchlist.user_id == user_id)
        rows = session.execute(stmt).scalars().all()
        return [row.symbol for row in rows]


def add_to_watchlist(engine_url: str, user_id: Optional[str] = None, symbols: Optional[List[str]] = None) -> None:
    """添加股票到自选股（按 user_id 存储）"""
    import uuid
    session_factory = _session_factory(engine_url)
    if symbols is None:
        symbols = []

    with session_factory() as session:
        for symbol in symbols:
            # 检查是否已存在（按 user_id + symbol 唯一约束）
            existing = session.query(Watchlist).filter(
                Watchlist.user_id == (user_id or ""), Watchlist.symbol == symbol
            ).first()
            if not existing:
                watchlist_item = Watchlist(
                    id=str(uuid.uuid4()),
                    user_id=user_id or "",
                    symbol=symbol,
                    created_at=datetime.now(),
                )
                session.add(watchlist_item)
        session.commit()
    logger.info("Added %d symbols to watchlist user=%s", len(symbols), user_id)


def remove_from_watchlist(engine_url: str, user_id: Optional[str] = None, symbols: Optional[List[str]] = None) -> None:
    """从自选股移除股票（按 user_id 过滤）"""
    session_factory = _session_factory(engine_url)
    if symbols is None:
        symbols = []

    with session_factory() as session:
        stmt = select(Watchlist).where(Watchlist.symbol.in_(symbols))
        if user_id is not None:
            stmt = stmt.where(Watchlist.user_id == user_id)
        session.query(Watchlist).filter(Watchlist.symbol.in_(symbols)).delete(synchronize_session=False)
        if user_id is not None:
            session.query(Watchlist).filter(
                Watchlist.user_id == user_id, Watchlist.symbol.in_(symbols)
            ).delete(synchronize_session=False)
        session.commit()
    logger.info("Removed %d symbols from watchlist user=%s", len(symbols), user_id)


# ── 回测任务持久化 ──

def get_backtest_task(engine_url: str, user_id: Optional[str] = None, task_id: str = "") -> Optional[Dict[str, Any]]:
    """获取回测任务（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(BacktestTask).where(BacktestTask.id == task_id)
        if user_id is not None:
            stmt = stmt.where(BacktestTask.user_id == user_id)
        task = session.execute(stmt).scalars().first()
        if task:
            return {
                "id": task.id,
                "user_id": task.user_id,
                "status": task.status,
                "result": task.result,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }
        return None


def save_backtest_task(engine_url: str, user_id: Optional[str] = None, task_id: str = "", status: str = "", result: Optional[str] = None) -> None:
    """保存或更新回测任务（按 user_id 存储）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(BacktestTask).where(BacktestTask.id == task_id, BacktestTask.user_id == effective_uid)
        task = session.execute(stmt).scalars().first()
        if task:
            task.status = status
            if result is not None:
                task.result = result
            task.updated_at = datetime.now()
        else:
            task = BacktestTask(
                id=task_id,
                user_id=effective_uid,
                status=status,
                result=result,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(task)
        session.commit()
    logger.info("Saved backtest task id=%s user=%s status=%s", task_id, user_id, status)


def list_backtest_tasks(engine_url: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取回测任务列表（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(BacktestTask).order_by(BacktestTask.created_at.desc())
        if user_id is not None:
            stmt = stmt.where(BacktestTask.user_id == user_id)
        tasks = session.execute(stmt).scalars().all()
        return [
            {
                "id": task.id,
                "user_id": task.user_id,
                "status": task.status,
                "result": task.result,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }
            for task in tasks
        ]


def delete_backtest_task(engine_url: str, user_id: Optional[str] = None, task_id: str = "") -> bool:
    """删除回测任务（需 user_id 验证）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(BacktestTask).where(BacktestTask.id == task_id, BacktestTask.user_id == effective_uid)
        task = session.execute(stmt).scalars().first()
        if task is None:
            return False
        session.delete(task)
        session.commit()
        logger.info("Deleted backtest task id=%s user=%s", task_id, user_id)
        return True


# ── 策略持久化 ──

def get_strategy(engine_url: str, user_id: Optional[str] = None, strategy_id: str = "") -> Optional[Dict[str, Any]]:
    """获取策略（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(StrategyModel).where(StrategyModel.id == strategy_id, StrategyModel.user_id == effective_uid)
        strategy = session.execute(stmt).scalars().first()
        if strategy:
            return {
                "id": strategy.id,
                "user_id": strategy.user_id,
                "name": strategy.name,
                "description": strategy.description,
                "code": strategy.code,
                "parameters": strategy.parameters,
                "created_at": strategy.created_at.isoformat() if strategy.created_at else None,
                "updated_at": strategy.updated_at.isoformat() if strategy.updated_at else None,
            }
        return None


def save_strategy(engine_url: str, user_id: Optional[str] = None, strategy_id: str = "", name: str = "", code: str = "", description: Optional[str] = None, parameters: Optional[str] = None) -> None:
    """保存或更新策略（按 user_id 存储）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(StrategyModel).where(StrategyModel.id == strategy_id, StrategyModel.user_id == effective_uid)
        strategy = session.execute(stmt).scalars().first()
        if strategy:
            strategy.name = name
            strategy.code = code
            if description is not None:
                strategy.description = description
            if parameters is not None:
                strategy.parameters = parameters
            strategy.updated_at = datetime.now()
        else:
            strategy = StrategyModel(
                id=strategy_id,
                user_id=effective_uid,
                name=name,
                code=code,
                description=description,
                parameters=parameters,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(strategy)
        session.commit()
    logger.info("Saved strategy id=%s user=%s name=%s", strategy_id, user_id, name)


def _ensure_user_exists(engine_url: str, user_id: str) -> None:
    """确保 users 表中存在指定用户（用于外键约束）。"""
    if not user_id:
        return
    try:
        save_user(engine_url, user_id, user_id, "", '["admin"]')
    except Exception:
        pass


def list_strategies(engine_url: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取策略列表（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(StrategyModel).order_by(StrategyModel.created_at.desc())
        if user_id is not None:
            stmt = stmt.where(StrategyModel.user_id == user_id)
        strategies = session.execute(stmt).scalars().all()
        return [
            {
                "id": s.id,
                "user_id": s.user_id,
                "name": s.name,
                "description": s.description,
                "code": s.code,
                "parameters": s.parameters,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in strategies
        ]


def delete_strategy(engine_url: str, user_id: Optional[str] = None, strategy_id: str = "") -> bool:
    """删除策略（需 user_id 验证）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(StrategyModel).where(StrategyModel.id == strategy_id, StrategyModel.user_id == effective_uid)
        strategy = session.execute(stmt).scalars().first()
        if strategy is None:
            return False
        session.delete(strategy)
        session.commit()
        logger.info("Deleted strategy id=%s user=%s", strategy_id, user_id)
        return True


# ── 数据收集任务持久化 ──

def save_collect_task(engine_url: str, user_id: Optional[str] = None, task_id: str = "", status: str = "", progress: float = 0.0, result: Optional[str] = None) -> None:
    """保存或更新数据收集任务（按 user_id 存储）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(CollectTask).where(CollectTask.id == task_id, CollectTask.user_id == effective_uid)
        task = session.execute(stmt).scalars().first()
        if task:
            task.status = status
            task.progress = progress
            if result is not None:
                task.result = result
            task.updated_at = datetime.now()
        else:
            task = CollectTask(
                id=task_id,
                user_id=effective_uid,
                status=status,
                progress=progress,
                result=result,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(task)
        session.commit()
    logger.info("Saved collect task id=%s user=%s status=%s", task_id, user_id, status)


def get_collect_task(engine_url: str, user_id: Optional[str] = None, task_id: str = "") -> Optional[Dict[str, Any]]:
    """获取数据收集任务（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(CollectTask).where(CollectTask.id == task_id, CollectTask.user_id == effective_uid)
        task = session.execute(stmt).scalars().first()
        if task:
            return {
                "id": task.id,
                "user_id": task.user_id,
                "status": task.status,
                "progress": task.progress,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }
        return None


def list_collect_tasks(engine_url: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取数据收集任务列表（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(CollectTask).order_by(CollectTask.created_at.desc())
        if user_id is not None:
            stmt = stmt.where(CollectTask.user_id == user_id)
        tasks = session.execute(stmt).scalars().all()
        return [
            {
                "id": task.id,
                "user_id": task.user_id,
                "status": task.status,
                "progress": task.progress,
                "result": task.result,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }
            for task in tasks
        ]


def delete_collect_task(engine_url: str, user_id: Optional[str] = None, task_id: str = "") -> bool:
    """删除数据收集任务（需 user_id 验证）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(CollectTask).where(CollectTask.id == task_id, CollectTask.user_id == effective_uid)
        task = session.execute(stmt).scalars().first()
        if task is None:
            return False
        session.delete(task)
        session.commit()
        logger.info("Deleted collect task id=%s user=%s", task_id, user_id)
        return True


# ── 参数优化任务持久化 ──

def save_optimize_task(engine_url: str, user_id: Optional[str] = None, task_id: str = "", status: str = "", result: Optional[str] = None) -> None:
    """保存或更新参数优化任务（按 user_id 存储）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(OptimizeTask).where(OptimizeTask.id == task_id, OptimizeTask.user_id == effective_uid)
        task = session.execute(stmt).scalars().first()
        if task:
            task.status = status
            if result is not None:
                task.result = result
            task.updated_at = datetime.now()
        else:
            task = OptimizeTask(
                id=task_id,
                user_id=effective_uid,
                status=status,
                result=result,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(task)
        session.commit()
    logger.info("Saved optimize task id=%s user=%s status=%s", task_id, user_id, status)


def get_optimize_task(engine_url: str, user_id: Optional[str] = None, task_id: str = "") -> Optional[Dict[str, Any]]:
    """获取参数优化任务（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(OptimizeTask).where(OptimizeTask.id == task_id, OptimizeTask.user_id == effective_uid)
        task = session.execute(stmt).scalars().first()
        if task:
            return {
                "id": task.id,
                "user_id": task.user_id,
                "status": task.status,
                "result": task.result,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }
        return None


def list_optimize_tasks(engine_url: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取参数优化任务列表（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(OptimizeTask).order_by(OptimizeTask.created_at.desc())
        if user_id is not None:
            stmt = stmt.where(OptimizeTask.user_id == user_id)
        tasks = session.execute(stmt).scalars().all()
        return [
            {
                "id": task.id,
                "user_id": task.user_id,
                "status": task.status,
                "result": task.result,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }
            for task in tasks
        ]


def delete_optimize_task(engine_url: str, user_id: Optional[str] = None, task_id: str = "") -> bool:
    """删除参数优化任务（需 user_id 验证）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(OptimizeTask).where(OptimizeTask.id == task_id, OptimizeTask.user_id == effective_uid)
        task = session.execute(stmt).scalars().first()
        if task is None:
            return False
        session.delete(task)
        session.commit()
        logger.info("Deleted optimize task id=%s user=%s", task_id, user_id)
        return True


# ── 策略对比历史持久化 ──

def save_comparison_history(engine_url: str, user_id: Optional[str] = None, history_id: str = "", strategy_ids: str = "", result: Optional[str] = None) -> None:
    """保存策略对比历史（按 user_id 存储）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        history = ComparisonHistory(
            id=history_id,
            user_id=(user_id or ""),
            strategy_ids=strategy_ids,
            result=result,
            created_at=datetime.now(),
        )
        session.add(history)
        session.commit()
    logger.info("Saved comparison history id=%s user=%s", history_id, user_id)


def list_comparison_history(engine_url: str, user_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """获取策略对比历史列表（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(ComparisonHistory).order_by(ComparisonHistory.created_at.desc()).limit(limit)
        if user_id is not None:
            stmt = stmt.where(ComparisonHistory.user_id == user_id)
        histories = session.execute(stmt).scalars().all()
        return [
            {
                "id": h.id,
                "user_id": h.user_id,
                "strategy_ids": h.strategy_ids,
                "result": h.result,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in histories
        ]


def get_comparison_history(engine_url: str, user_id: Optional[str] = None, history_id: str = "") -> Optional[Dict[str, Any]]:
    """获取单条策略对比历史（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = session.get(ComparisonHistory, history_id)
        if row is None or (user_id is not None and row.user_id != user_id):
            return None
        return {
            "id": row.id,
            "user_id": row.user_id,
            "strategy_ids": row.strategy_ids,
            "result": row.result,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


def delete_comparison_history(engine_url: str, user_id: Optional[str] = None, history_id: str = "") -> bool:
    """删除策略对比历史（按 user_id 验证）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = session.get(ComparisonHistory, history_id)
        if row is None or (user_id is not None and row.user_id != user_id):
            return False
        session.delete(row)
        session.commit()
        logger.info("Deleted comparison history id=%s user=%s", history_id, user_id)
        return True


# ── 待处理订单持久化 ──

def save_pending_order(engine_url: str, user_id: Optional[str] = None, order_id: str = "", symbol: str = "", type: str = "", price: float = 0.0, quantity: int = 0, status: str = "pending") -> None:
    """保存或更新待处理订单（按 user_id 存储）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(PendingOrder).where(PendingOrder.id == order_id, PendingOrder.user_id == effective_uid)
        order = session.execute(stmt).scalars().first()
        if order:
            order.symbol = symbol
            order.type = type
            order.price = price
            order.quantity = quantity
            order.status = status
        else:
            order = PendingOrder(
                id=order_id,
                user_id=effective_uid,
                symbol=symbol,
                type=type,
                price=price,
                quantity=quantity,
                status=status,
                created_at=datetime.now(),
            )
            session.add(order)
        session.commit()
    logger.info("Saved pending order id=%s user=%s symbol=%s", order_id, user_id, symbol)


def get_pending_order(engine_url: str, user_id: Optional[str] = None, order_id: str = "") -> Optional[Dict[str, Any]]:
    """获取待处理订单（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(PendingOrder).where(PendingOrder.id == order_id, PendingOrder.user_id == effective_uid)
        order = session.execute(stmt).scalars().first()
        if order:
            return {
                "id": order.id,
                "user_id": order.user_id,
                "symbol": order.symbol,
                "type": order.type,
                "price": order.price,
                "quantity": order.quantity,
                "status": order.status,
                "created_at": order.created_at.isoformat() if order.created_at else None,
            }
        return None


def list_pending_orders(engine_url: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取待处理订单列表（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(PendingOrder).order_by(PendingOrder.created_at.desc())
        if user_id is not None:
            stmt = stmt.where(PendingOrder.user_id == user_id)
        orders = session.execute(stmt).scalars().all()
        return [
            {
                "id": o.id,
                "user_id": o.user_id,
                "symbol": o.symbol,
                "type": o.type,
                "price": o.price,
                "quantity": o.quantity,
                "status": o.status,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ]


def delete_pending_order(engine_url: str, user_id: Optional[str] = None, order_id: str = "") -> bool:
    """删除待处理订单（需 user_id 验证）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(PendingOrder).where(PendingOrder.id == order_id, PendingOrder.user_id == effective_uid)
        order = session.execute(stmt).scalars().first()
        if order is None:
            return False
        session.delete(order)
        session.commit()
        logger.info("Deleted pending order id=%s user=%s", order_id, user_id)
        return True


# ── 订单审计持久化 ──

def save_order_audit(engine_url: str, user_id: Optional[str] = None, audit_id: str = "", order_id: str = "", action: str = "", details: Optional[str] = None) -> None:
    """保存订单审计记录（按 user_id 存储）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        audit = OrderAudit(
            id=audit_id,
            user_id=(user_id or ""),
            order_id=order_id,
            action=action,
            details=details,
            created_at=datetime.now(),
        )
        session.add(audit)
        session.commit()
    logger.info("Saved order audit id=%s user=%s order=%s action=%s", audit_id, user_id, order_id, action)


def list_order_audits(engine_url: str, user_id: Optional[str] = None, order_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取订单审计记录列表（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(OrderAudit).order_by(OrderAudit.created_at.desc())
        if user_id is not None:
            stmt = stmt.where(OrderAudit.user_id == user_id)
        if order_id:
            stmt = stmt.where(OrderAudit.order_id == order_id)
        audits = session.execute(stmt).scalars().all()
        return [
            {
                "id": a.id,
                "user_id": a.user_id,
                "order_id": a.order_id,
                "action": a.action,
                "details": a.details,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in audits
        ]


def get_order_audit(engine_url: str, user_id: Optional[str] = None, audit_id: str = "") -> Optional[Dict[str, Any]]:
    """获取单条订单审计记录（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = session.get(OrderAudit, audit_id)
        if row is None or (user_id is not None and row.user_id != user_id):
            return None
        return {
            "id": row.id,
            "user_id": row.user_id,
            "order_id": row.order_id,
            "action": row.action,
            "details": row.details,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


def delete_order_audit(engine_url: str, user_id: Optional[str] = None, audit_id: str = "") -> bool:
    """删除订单审计记录（按 user_id 验证）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = session.get(OrderAudit, audit_id)
        if row is None or (user_id is not None and row.user_id != user_id):
            return False
        session.delete(row)
        session.commit()
        logger.info("Deleted order audit id=%s user=%s", audit_id, user_id)
        return True


# ── User CRUD ─────────────────────────────────────────────────────────

def save_user(engine_url: str, user_id: str, username: str, hashed_password: str,
              roles: str = '["user"]', disabled: bool = False) -> Dict[str, Any]:
    """保存或更新用户（upsert）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(UserModel).where(UserModel.id == effective_uid)
        user = session.execute(stmt).scalars().first()
        if user:
            user.username = username
            user.hashed_password = hashed_password
            user.roles = roles
            user.disabled = int(disabled)
            user.updated_at = datetime.now()
        else:
            user = UserModel(
                id=effective_uid,
                username=username,
                hashed_password=hashed_password,
                roles=roles,
                disabled=int(disabled),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(user)
        session.commit()
        return {
            "id": user.id,
            "username": user.username,
            "roles": user.roles,
            "disabled": bool(user.disabled),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }


def get_user(engine_url: str, user_id: str) -> Optional[Dict[str, Any]]:
    """获取单个用户。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        user = session.get(UserModel, user_id)
        if user:
            return {
                "id": user.id,
                "username": user.username,
                "roles": user.roles,
                "disabled": bool(user.disabled),
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            }
        return None


def list_users(engine_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出所有用户（不返回密码哈希）。"""
    if engine_url is None:
        from stockquant.api.routers.auth import _get_db_url
        engine_url = _get_db_url()
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        users = session.query(UserModel).order_by(UserModel.created_at.desc()).all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "roles": u.roles,
                "disabled": bool(u.disabled),
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "updated_at": u.updated_at.isoformat() if u.updated_at else None,
            }
            for u in users
        ]


def delete_user(engine_url: str, user_id: str) -> bool:
    """删除用户。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        user = session.get(UserModel, user_id)
        if user is None:
            return False
        session.delete(user)
        session.commit()
        logger.info("Deleted user id=%s", user_id)
        return True


# ── TradingAccount CRUD ────────────────────────────────────────────────

def save_trading_account(engine_url: str, account_id: str, user_id: str,
                         cash: float = 1_000_000.0, frozen_cash: float = 0.0,
                         available_cash: float = 1_000_000.0) -> Dict[str, Any]:
    """保存或更新交易账户（upsert）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(TradingAccount).where(TradingAccount.id == account_id)
        account = session.execute(stmt).scalars().first()
        if account:
            account.cash = cash
            account.frozen_cash = frozen_cash
            account.available_cash = available_cash
            account.updated_at = datetime.now()
        else:
            account = TradingAccount(
                id=account_id,
                user_id=user_id,
                cash=cash,
                frozen_cash=frozen_cash,
                available_cash=available_cash,
                updated_at=datetime.now(),
            )
            session.add(account)
        session.commit()
        return {
            "id": account.id,
            "user_id": account.user_id,
            "cash": account.cash,
            "frozen_cash": account.frozen_cash,
            "available_cash": account.available_cash,
            "updated_at": account.updated_at.isoformat() if account.updated_at else None,
        }


def get_trading_account(engine_url: str, account_id: str) -> Optional[Dict[str, Any]]:
    """获取交易账户。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        account = session.get(TradingAccount, account_id)
        if account:
            return {
                "id": account.id,
                "user_id": account.user_id,
                "cash": account.cash,
                "frozen_cash": account.frozen_cash,
                "available_cash": account.available_cash,
                "updated_at": account.updated_at.isoformat() if account.updated_at else None,
            }
        return None


def list_trading_accounts(engine_url: str, user_id: str) -> List[Dict[str, Any]]:
    """列出用户交易账户。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(TradingAccount).where(
            TradingAccount.user_id == user_id
        ).order_by(TradingAccount.updated_at.desc())
        accounts = session.execute(stmt).scalars().all()
        return [
            {
                "id": a.id,
                "user_id": a.user_id,
                "cash": a.cash,
                "frozen_cash": a.frozen_cash,
                "available_cash": a.available_cash,
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            }
            for a in accounts
        ]


# ── Position CRUD ──────────────────────────────────────────────────────

def save_position(engine_url: str, position_id: str, user_id: str, symbol: str,
                  quantity: int = 0, available_quantity: int = 0,
                  cost_price: float = 0.0, frozen_quantity: int = 0) -> Dict[str, Any]:
    """保存或更新持仓（upsert）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(Position).where(
            Position.user_id == effective_uid, Position.symbol == symbol
        )
        pos = session.execute(stmt).scalars().first()
        if pos:
            pos.quantity = quantity
            pos.available_quantity = available_quantity
            pos.cost_price = cost_price
            pos.frozen_quantity = frozen_quantity
            pos.updated_at = datetime.now()
        else:
            pos = Position(
                id=position_id,
                user_id=effective_uid,
                symbol=symbol,
                quantity=quantity,
                available_quantity=available_quantity,
                cost_price=cost_price,
                frozen_quantity=frozen_quantity,
                updated_at=datetime.now(),
            )
            session.add(pos)
        session.commit()
        return {
            "id": pos.id,
            "user_id": pos.user_id,
            "symbol": pos.symbol,
            "quantity": pos.quantity,
            "available_quantity": pos.available_quantity,
            "cost_price": pos.cost_price,
            "frozen_quantity": pos.frozen_quantity,
            "updated_at": pos.updated_at.isoformat() if pos.updated_at else None,
        }


def get_position(engine_url: str, user_id: str, symbol: str) -> Optional[Dict[str, Any]]:
    """获取单个持仓（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(Position).where(
            Position.user_id == effective_uid, Position.symbol == symbol
        )
        pos = session.execute(stmt).scalars().first()
        if pos:
            return {
                "id": pos.id,
                "user_id": pos.user_id,
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "available_quantity": pos.available_quantity,
                "cost_price": pos.cost_price,
                "frozen_quantity": pos.frozen_quantity,
                "updated_at": pos.updated_at.isoformat() if pos.updated_at else None,
            }
        return None


def list_positions(engine_url: str, user_id: str) -> List[Dict[str, Any]]:
    """列出用户持仓（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(Position).where(
            Position.user_id == user_id
        ).order_by(Position.updated_at.desc())
        positions = session.execute(stmt).scalars().all()
        return [
            {
                "id": p.id,
                "user_id": p.user_id,
                "symbol": p.symbol,
                "quantity": p.quantity,
                "available_quantity": p.available_quantity,
                "cost_price": p.cost_price,
                "frozen_quantity": p.frozen_quantity,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in positions
        ]


# ── Order (DB) CRUD ────────────────────────────────────────────────────

def save_order(engine_url: str, order_id: str, user_id: str, symbol: str,
               side: str, order_type: str, price: float, quantity: int,
               filled_quantity: int = 0, avg_fill_price: float = 0.0,
               status: str = "PENDING", broker_order_id: Optional[str] = None) -> Dict[str, Any]:
    """保存或更新订单（upsert）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(Order).where(Order.id == order_id, Order.user_id == effective_uid)
        order = session.execute(stmt).scalars().first()
        if order:
            order.side = side
            order.order_type = order_type
            order.price = price
            order.quantity = quantity
            order.filled_quantity = filled_quantity
            order.avg_fill_price = avg_fill_price
            order.status = status
            order.broker_order_id = broker_order_id
            order.updated_at = datetime.now()
        else:
            order = Order(
                id=order_id,
                user_id=effective_uid,
                symbol=symbol,
                side=side,
                order_type=order_type,
                price=price,
                quantity=quantity,
                filled_quantity=filled_quantity,
                avg_fill_price=avg_fill_price,
                status=status,
                broker_order_id=broker_order_id,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(order)
        session.commit()
        return {
            "id": order.id,
            "user_id": order.user_id,
            "symbol": order.symbol,
            "side": order.side,
            "order_type": order.order_type,
            "price": order.price,
            "quantity": order.quantity,
            "filled_quantity": order.filled_quantity,
            "avg_fill_price": order.avg_fill_price,
            "status": order.status,
            "broker_order_id": order.broker_order_id,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        }


def get_order(engine_url: str, user_id: str, order_id: str) -> Optional[Dict[str, Any]]:
    """获取单个订单（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(Order).where(Order.id == order_id, Order.user_id == effective_uid)
        order = session.execute(stmt).scalars().first()
        if order:
            return {
                "id": order.id,
                "user_id": order.user_id,
                "symbol": order.symbol,
                "side": order.side,
                "order_type": order.order_type,
                "price": order.price,
                "quantity": order.quantity,
                "filled_quantity": order.filled_quantity,
                "avg_fill_price": order.avg_fill_price,
                "status": order.status,
                "broker_order_id": order.broker_order_id,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            }
        return None


def list_orders(engine_url: str, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出用户订单（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(Order).where(Order.user_id == user_id).order_by(
            Order.created_at.desc()
        )
        if status:
            stmt = stmt.where(Order.status == status)
        orders = session.execute(stmt).scalars().all()
        return [
            {
                "id": o.id,
                "user_id": o.user_id,
                "symbol": o.symbol,
                "side": o.side,
                "order_type": o.order_type,
                "price": o.price,
                "quantity": o.quantity,
                "filled_quantity": o.filled_quantity,
                "avg_fill_price": o.avg_fill_price,
                "status": o.status,
                "broker_order_id": o.broker_order_id,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "updated_at": o.updated_at.isoformat() if o.updated_at else None,
            }
            for o in orders
        ]


def delete_order(engine_url: str, user_id: str, order_id: str) -> bool:
    """删除订单（需 user_id 验证）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(Order).where(Order.id == order_id, Order.user_id == effective_uid)
        order = session.execute(stmt).scalars().first()
        if order is None:
            return False
        session.delete(order)
        session.commit()
        logger.info("Deleted order id=%s user=%s", order_id, user_id)
        return True


# ── CashFlow CRUD ──────────────────────────────────────────────────────

def save_cash_flow(engine_url: str, user_id: str, cf_type: str, amount: float,
                   balance_after: float, related_order_id: Optional[str] = None,
                   remark: Optional[str] = None) -> Dict[str, Any]:
    """保存资金流水记录。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = CashFlow(
            user_id=user_id,
            type=cf_type,
            amount=amount,
            balance_after=balance_after,
            related_order_id=related_order_id,
            remark=remark,
            created_at=datetime.now(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "user_id": row.user_id,
            "type": row.type,
            "amount": row.amount,
            "balance_after": row.balance_after,
            "related_order_id": row.related_order_id,
            "remark": row.remark,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


def list_cash_flows(engine_url: str, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """列出用户资金流水（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(CashFlow).where(
            CashFlow.user_id == user_id
        ).order_by(CashFlow.created_at.desc()).limit(limit)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "type": r.type,
                "amount": r.amount,
                "balance_after": r.balance_after,
                "related_order_id": r.related_order_id,
                "remark": r.remark,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


# ── RiskEvent CRUD ─────────────────────────────────────────────────────

def save_risk_event(engine_url: str, user_id: str, event_type: str,
                    severity: str = "WARNING", detail: Optional[str] = None,
                    order_id: Optional[str] = None) -> Dict[str, Any]:
    """保存风控事件记录。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = RiskEvent(
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            detail=detail,
            order_id=order_id,
            created_at=datetime.now(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "user_id": row.user_id,
            "event_type": row.event_type,
            "severity": row.severity,
            "detail": row.detail,
            "order_id": row.order_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


def list_risk_events(engine_url: str, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """列出用户风控事件（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(RiskEvent).where(
            RiskEvent.user_id == user_id
        ).order_by(RiskEvent.created_at.desc()).limit(limit)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "event_type": r.event_type,
                "severity": r.severity,
                "detail": r.detail,
                "order_id": r.order_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


# ── OpAuditLog CRUD ────────────────────────────────────────────────────

def save_op_audit_log(engine_url: str, user_id: str, action: str,
                      resource_type: str, resource_id: Optional[str] = None,
                      detail: Optional[str] = None, ip_address: Optional[str] = None,
                      user_agent: Optional[str] = None, status_code: Optional[int] = None) -> int:
    """保存操作审计日志。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = OpAuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
            ip_address=ip_address,
            user_agent=user_agent,
            status_code=status_code,
            created_at=datetime.now(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        logger.info("Saved op_audit_log id=%d user=%s action=%s resource=%s", row.id, user_id, action, resource_type)
        return row.id


def list_op_audit_logs(engine_url: str, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """列出用户操作审计日志（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(OpAuditLog).where(
            OpAuditLog.user_id == user_id
        ).order_by(OpAuditLog.created_at.desc()).limit(limit)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "detail": r.detail,
                "ip_address": r.ip_address,
                "user_agent": r.user_agent,
                "status_code": r.status_code,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


# ── Notification CRUD ────────────────────────────────────────────────

def list_notifications(
    engine_url: str,
    user_id: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """列出通知（按 user_id 过滤，按 created_at 倒序）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(Notification).order_by(
            Notification.created_at.desc()
        ).limit(limit)
        if user_id is not None:
            stmt = stmt.where(Notification.user_id == user_id)

        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "type": r.notification_type,
                "title": r.title,
                "message": r.message,
                "time": r.created_at.isoformat() if r.created_at else None,
                "read": bool(r.is_read),
            }
            for r in rows
        ]


def delete_notification(engine_url: str, user_id: Optional[str] = None, notification_id: str = "") -> bool:
    """删除通知（按 user_id 验证）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        row = session.get(Notification, notification_id)
        if row is None or (user_id is not None and row.user_id != user_id):
            return False
        session.delete(row)
        session.commit()
        logger.info("Deleted notification id=%s user=%s", notification_id, user_id)
        return True


# ── MonitorAlert CRUD ────────────────────────────────────────────────

def list_monitor_alerts(
    engine_url: str,
    user_id: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """列出盯盘告警（按 user_id 过滤，按 created_at 倒序）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(MonitorAlert).order_by(
            MonitorAlert.created_at.desc()
        ).limit(limit)
        if user_id is not None:
            stmt = stmt.where(MonitorAlert.user_id == user_id)
        if symbol:
            stmt = stmt.where(MonitorAlert.symbol == symbol)

        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "symbol": r.symbol,
                "direction": r.direction,
                "reason": r.reason,
                "confidence": r.confidence,
                "signal_type": r.signal_type,
                "is_portfolio_hold": bool(r.is_portfolio_hold),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


def save_monitor_alert(
    engine_url: str,
    alert_id: str,
    user_id: str,
    symbol: str,
    direction: str,
    reason: str,
    confidence: float,
    signal_type: str,
    is_portfolio_hold: bool = False,
) -> None:
    """保存盯盘告警（upsert）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        existing = session.get(MonitorAlert, alert_id)
        if existing:
            existing.symbol = symbol
            existing.direction = direction
            existing.reason = reason
            existing.confidence = confidence
            existing.signal_type = signal_type
            existing.is_portfolio_hold = int(is_portfolio_hold)
        else:
            alert = MonitorAlert(
                id=alert_id,
                user_id=user_id,
                symbol=symbol,
                direction=direction,
                reason=reason,
                confidence=confidence,
                signal_type=signal_type,
                is_portfolio_hold=int(is_portfolio_hold),
            )
            session.add(alert)
        session.commit()
    logger.info("Saved monitor alert id=%s user=%s symbol=%s", alert_id, user_id, symbol)


# ── Scheduler CRUD ───────────────────────────────────────────────────

def save_scheduler_task(
    engine_url: str,
    user_id: Optional[str] = None,
    task_id: str = "",
    name: str = "",
    cron_expression: str = "",
    action: str = "",
    args: Optional[str] = None,
    kwargs: Optional[str] = None,
    enabled: bool = True,
) -> None:
    """保存或更新定时调度任务（upsert）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(SchedulerTask).where(SchedulerTask.id == task_id)
        task = session.execute(stmt).scalars().first()
        if task:
            task.name = name
            task.cron_expression = cron_expression
            task.action = action
            if args is not None:
                task.args = args
            if kwargs is not None:
                task.kwargs = kwargs
            task.enabled = int(enabled)
            task.updated_at = datetime.now()
        else:
            task = SchedulerTask(
                id=task_id,
                user_id=effective_uid,
                name=name,
                cron_expression=cron_expression,
                action=action,
                args=args,
                kwargs=kwargs,
                enabled=int(enabled),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(task)
        session.commit()
    logger.info("Saved scheduler task id=%s user=%s name=%s", task_id, user_id, name)


def list_scheduler_tasks(
    engine_url: str,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """列出定时调度任务（按 user_id 过滤）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(SchedulerTask).order_by(SchedulerTask.created_at.desc())
        if user_id is not None:
            stmt = stmt.where(SchedulerTask.user_id == user_id)

        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "name": r.name,
                "cron_expression": r.cron_expression,
                "action": r.action,
                "args": r.args,
                "kwargs": r.kwargs,
                "enabled": bool(r.enabled),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]


def delete_scheduler_task(engine_url: str, user_id: Optional[str] = None, task_id: str = "") -> bool:
    """删除定时调度任务（需 user_id 验证）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(SchedulerTask).where(SchedulerTask.id == task_id)
        if user_id is not None:
            stmt = stmt.where(SchedulerTask.user_id == user_id)
        task = session.execute(stmt).scalars().first()
        if task is None:
            return False
        session.delete(task)
        session.commit()
        logger.info("Deleted scheduler task id=%s user=%s", task_id, user_id)
        return True


# ── AI 管线任务持久化 ──

def save_pipeline_task(
    engine_url: str,
    user_id: Optional[str] = None,
    task_id: str = "",
    status: str = "queued",
    symbols: Optional[List[str]] = None,
    sources: Optional[List[str]] = None,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    """保存或更新管线任务（按 user_id 存储）。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(PipelineTask).where(
            PipelineTask.task_id == task_id, PipelineTask.user_id == effective_uid
        )
        task = session.execute(stmt).scalars().first()
        if task:
            task.status = status
            if result is not None:
                task.result = json.dumps(result, ensure_ascii=False)
            if error is not None:
                task.error = error
            if status in ("completed", "failed"):
                task.completed_at = datetime.now()
        else:
            task = PipelineTask(
                task_id=task_id,
                user_id=effective_uid,
                status=status,
                symbols=json.dumps(symbols or [], ensure_ascii=False),
                sources=json.dumps(sources or [], ensure_ascii=False),
                result=json.dumps(result or {}, ensure_ascii=False) if result else None,
                error=error,
                created_at=datetime.now(),
                completed_at=datetime.now() if status in ("completed", "failed") else None,
            )
            session.add(task)
        session.commit()
    logger.info("Saved pipeline task %s user=%s status=%s", task_id, user_id, status)


def get_pipeline_task(engine_url: str, user_id: Optional[str] = None, task_id: str = "") -> Optional[Dict[str, Any]]:
    """获取单个管线任务。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(PipelineTask).where(PipelineTask.task_id == task_id)
        if user_id is not None:
            stmt = stmt.where(PipelineTask.user_id == user_id)
        task = session.execute(stmt).scalars().first()
        if task is None:
            return None
        return _pipeline_task_to_dict(task)


def list_pipeline_tasks(engine_url: str, user_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """获取管线任务列表（按 created_at 倒序）。"""
    session_factory = _session_factory(engine_url)

    with session_factory() as session:
        stmt = select(PipelineTask).order_by(PipelineTask.created_at.desc()).limit(limit)
        if user_id is not None:
            stmt = stmt.where(PipelineTask.user_id == user_id)
        tasks = session.execute(stmt).scalars().all()
        return [_pipeline_task_to_dict(t) for t in tasks]


def delete_pipeline_task(engine_url: str, user_id: Optional[str] = None, task_id: str = "") -> bool:
    """删除管线任务。"""
    session_factory = _session_factory(engine_url)
    effective_uid = user_id or ""

    with session_factory() as session:
        stmt = select(PipelineTask).where(
            PipelineTask.task_id == task_id, PipelineTask.user_id == effective_uid
        )
        task = session.execute(stmt).scalars().first()
        if task is None:
            return False
        session.delete(task)
        session.commit()
        logger.info("Deleted pipeline task %s user=%s", task_id, user_id)
        return True


def _pipeline_task_to_dict(task: PipelineTask) -> Dict[str, Any]:
    """ORM 行转字典"""
    d = {
        "task_id": task.task_id,
        "user_id": task.user_id,
        "status": task.status,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }
    if task.symbols:
        try:
            d["symbols"] = json.loads(task.symbols)
        except (json.JSONDecodeError, TypeError):
            d["symbols"] = []
    if task.sources:
        try:
            d["sources"] = json.loads(task.sources)
        except (json.JSONDecodeError, TypeError):
            d["sources"] = []
    if task.result:
        try:
            d["result"] = json.loads(task.result)
        except (json.JSONDecodeError, TypeError):
            d["result"] = {}
    if task.error:
        d["error"] = task.error
    return d
