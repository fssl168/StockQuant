# -*- coding: utf-8 -*-
"""StockQuant 2.0 公共 API 导出"""

from __future__ import annotations

# API 网关（FastAPI）— 延迟导入，避免循环引用
# 使用时: from stockquant.api import create_app

# 模型
from stockquant.models.bar import BarData
from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.events import EventType as OrderStatus
from stockquant.models.position import Position
from stockquant.models.account import Account
from stockquant.models.trade import TradeData
from stockquant.models.portfolio import Portfolio

# 持久化
from stockquant.persistence import (
    BacktestResult,
    KlineData,
    AnalysisHistory,
    ChatMessage,
)

# 引擎
from stockquant.engine import (
    Cerebro, EventEngine, ProgressBar, EventType,
    CommissionInfo, FixedSlippage, PercentSlippage, AdaptiveSlippage,
    BacktestBroker, PaperBroker, LiveBroker, Broker,
    RiskManager, BacktestMetrics,
    FixedFractionSizer, KellySizer, ATRSizer, VolatilityTargetSizer, EqualWeightSizer,
)

# 策略
from stockquant.strategy.base import BaseStrategy
from stockquant.strategy.yaml_loader import YamlStrategyLoader
from stockquant.strategy.signal import (
    Signal, SignalSide, SignalSource, SignalManager,
    SignalAuditLog, convert_ai_to_strategy,
)
from stockquant.strategy.signal_evaluator import (
    SignalEvaluator, SignalAccuracy, SignalDecay,
)
from stockquant.strategy.templates import (
    DualMACrossoverStrategy,
    RSIReversalStrategy,
    BollingerBounceStrategy,
    MACDDivergenceStrategy,
    DualThrustStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
)

# 指标
from stockquant.indicators import (
    MA, EMA, KAMA, TRIX,
    RSI, KDJ, CCI, ROC, STOCHRSI,
    BOLL, ATR, STDDEV, SAR,
    MACD, OBV, HIGHEST, LOWEST, VOLUME,
    indicator, apply_indicators,
)

# 数据
from stockquant.data import DataFeed, DataCache, CSVFeed
from stockquant.data.providers import BaoStockFeed, AkShareFeed
from stockquant.data.standardize import (
    STANDARD_COLUMNS,
    normalize_columns,
    clean_dataframe,
    calculate_standard_indicators,
)
from stockquant.data.exceptions import (
    StockQuantError,
    DataError,
    DataFetchError,
    RateLimitError,
    DataSourceUnavailableError,
    DataValidationError,
)
from stockquant.data.calendar import TradingCalendar as DataTradingCalendar
from stockquant.data.fetcher_manager import DataFetcherManager, FetcherStatus

# Agent 基础设施
from stockquant.agent import (
    LLMResponse,
    LLMAdapter,
    ToolRegistry,
    ToolDefinition,
    tool,
    ReActAgent,
    ReActState,
    Thought,
    ReActResult,
)

# AI
from stockquant.ai import (
    BacktestAgent, IndicatorAgent, RiskAgent,
    MarketState, DynamicRiskParams, MarketEnvironment,
    robust_json_parse,
    NewsSearcher, NewsItem,
)

# 报表
from stockquant.analytics import ReportGenerator, MarketReviewer, MarketIndex, SectorInfo, FundFlow

# 通知器
from stockquant.execution import (
    DingTalkNotifier, EmailNotifier, WeChatNotifier, TelegramNotifier,
    DiscordNotifier, PushPlusNotifier, ServerChanNotifier, WebhookNotifier, FeishuNotifier,
    render_md_to_image,
    MessageRouter, Message, Priority,
)

# 调度器
from stockquant.scheduler import StockScheduler, ScheduledTask, TradingCalendar

__version__ = "2.0.0-dev"

__all__ = [
    "__version__",
    # 模型
    "BarData", "Order", "OrderSide", "OrderType", "OrderStatus",
    "Position", "Account", "TradeData", "Portfolio",
    # 持久化
    "BacktestResult", "KlineData", "AnalysisHistory", "ChatMessage",
    # 引擎
    "Cerebro", "EventEngine", "ProgressBar", "EventType",
    "CommissionInfo", "FixedSlippage", "PercentSlippage", "AdaptiveSlippage",
    "BacktestBroker", "PaperBroker", "LiveBroker", "Broker",
    "RiskManager", "BacktestMetrics",
    "FixedFractionSizer", "KellySizer", "ATRSizer", "VolatilityTargetSizer", "EqualWeightSizer",
    # 策略
    "BaseStrategy", "YamlStrategyLoader",
    "Signal", "SignalSide", "SignalSource", "SignalManager",
    "SignalAccuracy", "SignalDecay", "SignalEvaluator",
    "DualMACrossoverStrategy", "RSIReversalStrategy", "BollingerBounceStrategy",
    "MACDDivergenceStrategy", "DualThrustStrategy", "MeanReversionStrategy", "MomentumStrategy",
    # 指标
    "MA", "EMA", "KAMA", "TRIX",
    "RSI", "KDJ", "CCI", "ROC", "STOCHRSI",
    "BOLL", "ATR", "STDDEV", "SAR",
    "MACD", "OBV", "HIGHEST", "LOWEST", "VOLUME",
    "indicator", "apply_indicators",
    # 数据
    "DataFeed", "DataCache", "CSVFeed", "BaoStockFeed", "AkShareFeed",
    "DataTradingCalendar", "DataFetcherManager", "FetcherStatus",
    "STANDARD_COLUMNS", "normalize_columns", "clean_dataframe", "calculate_standard_indicators",
    "StockQuantError", "DataError", "DataFetchError", "RateLimitError",
    "DataSourceUnavailableError", "DataValidationError",
    # Agent
    "LLMResponse", "LLMAdapter", "ToolRegistry", "ToolDefinition", "tool",
    "ReActAgent", "ReActState", "Thought", "ReActResult",
    # AI
    "BacktestAgent", "IndicatorAgent", "RiskAgent",
    "MarketState", "DynamicRiskParams", "MarketEnvironment",
    "robust_json_parse", "NewsSearcher", "NewsItem",
    # 报表
    "ReportGenerator", "MarketReviewer", "MarketIndex", "SectorInfo", "FundFlow",
    # 通知器
    "DingTalkNotifier", "EmailNotifier", "WeChatNotifier", "TelegramNotifier",
    "DiscordNotifier", "PushPlusNotifier", "ServerChanNotifier", "WebhookNotifier", "FeishuNotifier",
    "render_md_to_image",
    "MessageRouter", "Message", "Priority",
    # 调度器
    "StockScheduler", "ScheduledTask", "TradingCalendar",
]
