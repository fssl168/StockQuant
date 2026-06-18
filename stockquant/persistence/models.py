# -*- coding: utf-8 -*-
"""数据持久化 — SQLAlchemy ORM 模型"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Any

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


def _default_db_url() -> str:
    """获取默认数据库 URL，优先从环境变量读取。"""
    return os.environ.get("DATABASE_URL", "sqlite:///./stockquant.db")


def get_engine(db_url: str | None = None) -> Engine:
    """获取 SQLAlchemy 引擎（懒加载，模块级缓存）。

    注意：asyncpg 是异步驱动，同步 SQLAlchemy 需要使用 psycopg2 或标准 postgresql:// 前缀。
    自动将 postgresql+asyncpg 转换为 postgresql:// 以支持同步访问。
    """
    if db_url is None:
        db_url = _default_db_url()
    # asyncpg 异步驱动无法用于同步 SQLAlchemy，转换为标准 postgresql://
    sync_db_url = db_url.replace('+asyncpg', '') if '+asyncpg' in db_url else db_url
    if sync_db_url not in _engine_cache:
        _engine_cache[sync_db_url] = create_engine(sync_db_url, echo=False)
    return _engine_cache[sync_db_url]


def init_db(engine_url: str | None = None) -> Engine:
    """创建所有表（基于 Base.metadata）。"""
    engine = get_engine(engine_url)
    Base.metadata.create_all(engine)
    return engine


def drop_db(engine_url: str | None = None) -> None:
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


class Notification(Base):
    """通知持久化。"""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    notification_type: Mapped[str] = mapped_column(String(20), nullable=False, default="info")  # signal / alert / info
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)  # 0/1
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_notification_type_created", "notification_type", "created_at"),
    )


class HallucinationRecord(Base):
    """幻觉记录持久化。"""

    __tablename__ = "hallucination_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True, default=func.now()
    )
    agent: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    input_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hallucination_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    detection_method: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    original_output: Mapped[str] = mapped_column(Text, nullable=False, default="")
    corrected_output: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    user_feedback: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    __table_args__ = (
        Index("ix_hallucination_agent_type", "agent", "hallucination_type"),
        Index("ix_hallucination_timestamp", "timestamp"),
    )


# ── AI Memory Models (PostgreSQL + pgvector) ──────────────────────────────

# pgvector 扩展在 PostgreSQL 端通过 CREATE EXTENSION 启用
# 此处使用 RAW 类型映射，避免硬依赖 pgvector Python 包

_HAS_PGVECTOR = False
_VectorClass: Any = Text  # 默认使用 Text 类型

try:
    # pgvector 0.4+ 使用方式
    from pgvector.sqlalchemy import Vector
    _VectorClass = Vector
    _HAS_PGVECTOR = True
    logger.info("pgvector 已启用，向量存储功能可用")
except ImportError:
    logger.info("pgvector Python 包未安装，L3 向量列将使用 Text 类型降级")


class L2Memory(Base):
    """L2 短期记忆 — PostgreSQL 持久化存储"""

    __tablename__ = "l2_memory"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, default="", index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    timestamp: Mapped[str] = mapped_column(String(30), nullable=False)
    expires_at: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    __table_args__ = (
        Index("ix_l2_expires", "expires_at"),
    )


class L3Memory(Base):
    """L3 长期记忆 — PostgreSQL + pgvector 向量存储"""

    __tablename__ = "l3_memory"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, default="", index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    timestamp: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # 向量列: pgvector 安装时使用 Vector(1536)，否则降级为 Text
    embedding = Column(_VectorClass, nullable=True)

    __table_args__ = (
        Index("ix_l3_confidence", "confidence"),
    )


class Watchlist(Base):
    """自选股列表 — 持久化存储用户自选股票"""

    __tablename__ = "watchlist"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )

    __table_args__ = (
        Index("ix_watchlist_symbol", "symbol", unique=True),
    )


class EquitySnapshot(Base):
    """权益快照 — 每日收盘后自动保存，用于历史权益曲线"""

    __tablename__ = "equity_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    equity: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    market_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    positions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )

    __table_args__ = (
        Index("ix_equity_snapshot_date", "date", unique=True),
    )


class BacktestTask(Base):
    """回测任务 — 持久化存储回测任务状态"""

    __tablename__ = "backtest_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")  # "running", "completed", "failed"
    result: Mapped[str] = mapped_column(Text, nullable=True)  # JSON 格式的回测结果
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )


class StrategyModel(Base):
    """策略模型 — 持久化存储策略定义"""

    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)  # 策略代码
    parameters: Mapped[str] = mapped_column(Text, nullable=True)  # JSON 格式的参数配置
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_strategy_name", "name"),
    )
