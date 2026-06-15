# -*- coding: utf-8 -*-
"""数据持久化 — SQLAlchemy ORM 模型"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    event,
    func,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

logger = logging.getLogger(__name__)


# ── Base ────────────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""
    pass


# ── Engine helpers ───────────────────────────────────────────────────────


# Module-level lazy engine cache; key is the engine URL.
_engine_cache: dict[str, Engine] = {}


def get_engine(db_url: str = "sqlite:///./stockquant.db") -> Engine:
    """获取 SQLAlchemy 引擎（懒加载，模块级缓存）。"""
    if db_url not in _engine_cache:
        _engine_cache[db_url] = create_engine(db_url, echo=False)
    return _engine_cache[db_url]


def init_db(engine_url: str = "sqlite:///./stockquant.db") -> Engine:
    """创建所有表（基于 Base.metadata）。"""
    engine = get_engine(engine_url)
    Base.metadata.create_all(engine)
    return engine


def drop_db(engine_url: str = "sqlite:///./stockquant.db") -> None:
    """删除所有表（仅测试 / 清理使用）。"""
    engine = get_engine(engine_url)
    Base.metadata.drop_all(engine)


# ── Models ───────────────────────────────────────────────────────────────


class BacktestResult(Base):
    """回测结果持久化。"""

    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    initial_cash: Mapped[float] = mapped_column(Float, nullable=False, default=1_000_000.0)
    final_equity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metrics: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    equity_curve: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    trades_summary: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_backtest_strategy", "strategy_name"),
    )


class KlineData(Base):
    """K 线数据持久化。"""

    __tablename__ = "kline_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False, default="1d")
    datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_kline_symbol_timeframe", "symbol", "timeframe"),
        Index("ix_kline_symbol_datetime", "symbol", "datetime"),
    )


class AnalysisHistory(Base):
    """AI 分析历史。"""

    __tablename__ = "analysis_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    analysis_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # "backtest_interpretation", "indicator_recomm", "risk_assessment"
    input_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    output_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_analysis_symbol_type", "symbol", "analysis_type"),
    )


class ChatMessage(Base):
    """对话记录。"""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # "user", "assistant", "system"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_chat_session_created", "session_id", "created_at"),
    )


class AuditLogModel(Base):
    """AI 决策审计日志。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    signal_source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    original_signal: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    ai_decision: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    final_action: Mapped[str] = mapped_column(String(30), nullable=False)
    user_confirmed: Mapped[Optional[bool]] = mapped_column(Integer, nullable=True)  # 0/1/None
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_audit_symbol_source", "symbol", "signal_source"),
        Index("ix_audit_timestamp", "timestamp"),
    )
