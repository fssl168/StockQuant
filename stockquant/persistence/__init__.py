# -*- coding: utf-8 -*-
"""数据持久化包 — SQLAlchemy ORM 模型与 CRUD 仓库操作"""

from stockquant.persistence.models import (
    Base,
    BacktestResult,
    KlineData,
    AnalysisHistory,
    ChatMessage,
    get_engine,
)
from stockquant.persistence.repository import (
    save_backtest,
    get_backtest,
    list_backtests,
    delete_backtest,
    save_kline,
    get_kline,
    save_analysis,
    list_analyses,
)

__all__ = [
    "Base",
    "BacktestResult",
    "KlineData",
    "AnalysisHistory",
    "ChatMessage",
    "get_engine",
    "save_backtest",
    "get_backtest",
    "list_backtests",
    "delete_backtest",
    "save_kline",
    "get_kline",
    "save_analysis",
    "list_analyses",
]
