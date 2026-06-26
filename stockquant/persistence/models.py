# -*- coding: utf-8 -*-
"""数据持久化 - SQLAlchemy ORM 模型 (多租户重构)"""


import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    func,
    text as _sqla_text,
)
from sqlalchemy.dialects.postgresql import JSONB as _JSONB
from sqlalchemy.engine import Engine
from sqlalchemy import text as sqlalchemy_text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

logger = logging.getLogger(__name__)


# ─── Base ───────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""
    pass


# ─── Engine helpers ─────────────────────────────────────────────────


_engine_cache: dict[str, Engine] = {}


def _default_db_url() -> str:
    """获取默认数据库 URL，优先从环境变量读取。"""
    return os.environ.get("DATABASE_URL", "sqlite:///./stockquant.db")


def get_engine(db_url: str | None = None) -> Engine:
    """获取 SQLAlchemy 引擎（懒加载，模块级缓存）。"""
    if db_url is None:
        db_url = _default_db_url()
    sync_db_url = db_url.replace('+asyncpg', '') if '+asyncpg' in db_url else db_url
    if sync_db_url not in _engine_cache:
        _engine_cache[sync_db_url] = create_engine(sync_db_url, echo=False)
    return _engine_cache[sync_db_url]


def init_db(engine_url: str | None = None) -> Engine:
    """创建所有表（基于 Base.metadata）。

    生产环境应使用 Alembic 管理迁移，此函数仅作为开发/测试的便捷入口。
    """
    engine = get_engine(engine_url)
    Base.metadata.create_all(engine)
    return engine


def drop_db(engine_url: str | None = None) -> None:
    """初始化所有表（仅测试 / 清理使用）。"""
    engine = get_engine(engine_url)
    Base.metadata.drop_all(engine)


# ─── Models ─────────────────────────────────────────────────────────


class UserModel(Base):
    """用户账户"""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    roles: Mapped[str] = mapped_column(Text, nullable=False, default='["user"]')
    disabled: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )


class BacktestResult(Base):
    """回测结果持久化"""
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    initial_cash: Mapped[float] = mapped_column(Float, nullable=False, default=1_000_000.0)
    final_equity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metrics: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string; PostgreSQL 下可通过 Alembic 转为 JSONB
    equity_curve: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string; PostgreSQL 下可通过 Alembic 转为 JSONB
    trades_summary: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string; PostgreSQL 下可通过 Alembic 转为 JSONB
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_backtest_strategy", "strategy_name"),
        Index("ix_backtest_user_id", "user_id"),
    )


class KlineData(Base):
    """K 线数据持久化"""
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
        UniqueConstraint("symbol", "timeframe", "datetime", name="uq_kline_symbol_tf_dt"),
    )


class AnalysisHistory(Base):
    """AI 分析历史"""
    __tablename__ = "analysis_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    analysis_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    input_data: Mapped[str] = mapped_column(Text, nullable=False)
    output_data: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_analysis_symbol_type", "symbol", "analysis_type"),
        Index("ix_analysis_user_id", "user_id"),
    )


class ChatMessage(Base):
    """对话记录"""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_chat_session_created", "session_id", "created_at"),
        Index("ix_chat_user_id", "user_id"),
    )


class AuditLogModel(Base):
    """AI 决策审计日志"""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    signal_source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    original_signal: Mapped[str] = mapped_column(Text, nullable=False)
    ai_decision: Mapped[str] = mapped_column(Text, nullable=False)
    final_action: Mapped[str] = mapped_column(String(30), nullable=False)
    user_confirmed: Mapped[Optional[bool]] = mapped_column(Integer, nullable=True)
    llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    llm_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_reasoning_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    llm_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_audit_symbol_source", "symbol", "signal_source"),
        Index("ix_audit_timestamp", "timestamp"),
        Index("ix_audit_user_id", "user_id"),
    )


class Notification(Base):
    """通知持久化"""
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    notification_type: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_notification_type_created", "notification_type", "created_at"),
        Index("ix_notification_user_id", "user_id"),
    )


class HallucinationRecord(Base):
    """幻觉记录持久化"""
    __tablename__ = "hallucination_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
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
        Index("ix_hallucination_user_id", "user_id"),
    )


# ─── AI Memory Models (PostgreSQL + pgvector) ──────────────────────

_HAS_PGVECTOR = False
_VectorClass: Any = Text

try:
    from pgvector.sqlalchemy import Vector
    _VectorClass = Vector
    _HAS_PGVECTOR = True
    logger.info("pgvector 已启用，向量存储功能可用")
except ImportError:
    logger.info("pgvector Python 包未安装，L3 向量列将使用 Text 类型降级")


class L2Memory(Base):
    """L2 短期记忆"""
    __tablename__ = "l2_memory"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, default="", index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    timestamp: Mapped[str] = mapped_column(String(30), nullable=False)
    expires_at: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    __table_args__ = (
        Index("ix_l2_expires", "expires_at"),
        Index("ix_l2_user_id", "user_id"),
    )


class L3Memory(Base):
    """L3 长期记忆 — PostgreSQL + pgvector 向量存储"""
    __tablename__ = "l3_memory"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, default="", index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    timestamp: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    embedding = Column(_VectorClass, nullable=True)

    __table_args__ = (
        Index("ix_l3_confidence", "confidence"),
        Index("ix_l3_user_id", "user_id"),
    )


class Watchlist(Base):
    """自选股列表"""
    __tablename__ = "watchlist"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )

    __table_args__ = (
        Index("ix_watchlist_user_symbol", "user_id", "symbol", unique=True),
    )


class EquitySnapshot(Base):
    """权益快照"""
    __tablename__ = "equity_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    equity: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    market_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    positions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )

    __table_args__ = (
        Index("ix_equity_snapshot_user_date", "user_id", "date", unique=True),
    )


class BacktestTask(Base):
    """回测任务"""
    __tablename__ = "backtest_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    result: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_bt_task_user_id", "user_id"),
    )


class StrategyModel(Base):
    """策略模型"""
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_strategy_name", "name"),
        Index("ix_strategy_user_id", "user_id"),
    )


class CollectTask(Base):
    """数据收集任务"""
    __tablename__ = "collect_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    result: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_collect_task_user_id", "user_id"),
    )


class OptimizeTask(Base):
    """参数优化任务"""
    __tablename__ = "optimize_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    result: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_optimize_task_user_id", "user_id"),
    )


class ComparisonHistory(Base):
    """策略对比历史"""
    __tablename__ = "comparison_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    strategy_ids: Mapped[str] = mapped_column(String(500), nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )

    __table_args__ = (
        Index("ix_comparison_user_id", "user_id"),
    )


# ── PendingOrder 已废弃，功能并入 Order 模型 ──
# 保留空类用于兼容旧的 Alembic migration 依赖
# 实际使用请改用 Order 模型（stockquant.persistence.models.Order）


class PendingOrder(Base):
    """[DEPRECATED] 待处理订单 — 已废弃，功能并入 Order 模型"""
    __tablename__ = "pending_orders"
    # 已废弃：所有操作通过 stockquant.persistence.models.Order 进行

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )

    __table_args__ = (
        Index("ix_pending_order_user_id", "user_id"),
    )


class OrderAudit(Base):
    """订单审计"""
    __tablename__ = "orders_audit"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )

    __table_args__ = (
        Index("ix_order_audit_order_id", "order_id"),
        Index("ix_order_audit_user_id", "user_id"),
    )


class MonitorAlert(Base):
    """盯盘告警"""
    __tablename__ = "monitor_alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_portfolio_hold: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), index=True
    )

    __table_args__ = (
        Index("ix_monitor_alert_symbol_time", "symbol", "created_at"),
        Index("ix_monitor_alert_user_id", "user_id"),
    )


class SchedulerTask(Base):
    """定时调度任务"""
    __tablename__ = "scheduler_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    cron_expression: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    args: Mapped[str] = mapped_column(Text, nullable=True)
    kwargs: Mapped[str] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_scheduler_task_user_id", "user_id"),
    )


class PipelineTask(Base):
    """AI 信息管线任务"""
    __tablename__ = "pipeline_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    symbols: Mapped[str] = mapped_column(Text, nullable=True)  # JSON array string
    sources: Mapped[str] = mapped_column(Text, nullable=True)  # JSON array string
    result: Mapped[str] = mapped_column(Text, nullable=True)   # JSON object string
    error: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_pipeline_task_status", "status"),
        Index("ix_pipeline_task_user_id", "user_id"),
    )


# ─── 新增：多租户合规表 ────────────────────────────────────────────

class CashFlow(Base):
    """资金流水 — 记录所有资金变动"""
    __tablename__ = "cash_flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    balance_after: Mapped[float] = mapped_column(Float, nullable=False)
    related_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )

    __table_args__ = (
        Index("ix_cash_flow_user_id", "user_id"),
        Index("ix_cash_flow_created_at", "created_at"),
    )


class PositionSnapshot(Base):
    """持仓快照 — 按日记录持仓状态"""
    __tablename__ = "position_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_price: Mapped[float] = mapped_column(Float, nullable=False)
    market_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    snapshot_date: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "symbol", "snapshot_date", name="uq_pos_snap_user_sym_date"),
        Index("ix_pos_snap_user_id", "user_id"),
    )


class RiskEvent(Base):
    """风控事件 — 记录所有风控触发事件"""
    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="WARNING")
    detail: Mapped[str] = mapped_column(Text, nullable=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )

    __table_args__ = (
        Index("ix_risk_event_user_id", "user_id"),
        Index("ix_risk_event_severity", "severity"),
    )


class TradingAccount(Base):
    """交易账户 — 替代内存 Portfolio"""
    __tablename__ = "trading_accounts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    cash: Mapped[float] = mapped_column(Float, nullable=False, default=1_000_000.0)
    frozen_cash: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    available_cash: Mapped[float] = mapped_column(Float, nullable=False, default=1_000_000.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_trading_account_user_id", "user_id"),
    )


class Position(Base):
    """持仓 — 替代内存 Position 字典"""
    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    frozen_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_position_user_symbol"),
        Index("ix_position_user_id", "user_id"),
    )


class Order(Base):
    """订单完整生命周期"""
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    filled_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_fill_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    broker_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_order_user_id", "user_id"),
        Index("ix_order_status", "status"),
    )


class OpAuditLog(Base):
    """操作审计日志 — 满足等保三级合规"""
    __tablename__ = "op_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )

    __table_args__ = (
        Index("ix_op_audit_user_id", "user_id"),
        Index("ix_op_audit_created_at", "created_at"),
    )
