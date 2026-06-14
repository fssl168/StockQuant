# -*- coding: utf-8 -*-
"""StockQuant 2.0 公共 API 导出"""

# API 网关（FastAPI）— 延迟导入，避免循环引用
# 使用时: from stockquant.api import create_app

# 模型
from stockquant.models.bar import BarData
from stockquant.models.order import Order, OrderSide, OrderType, OrderStatus
from stockquant.models.position import Position
from stockquant.models.account import Account
from stockquant.models.trade import TradeData
from stockquant.models.portfolio import Portfolio

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
from stockquant.strategy.signal import (
    Signal, SignalSide, SignalSource, SignalManager,
    SignalAuditLog, convert_ai_to_strategy,
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
from stockquant.data.providers import BaoStockFeed

# AI
from stockquant.ai import (
    BacktestAgent, IndicatorAgent, RiskAgent,
    MarketState, DynamicRiskParams, MarketEnvironment,
)

# 报表
from stockquant.analytics import ReportGenerator

# 通知器
from stockquant.execution import DingTalkNotifier, EmailNotifier, WeChatNotifier, TelegramNotifier

__version__ = "2.0.0-dev"

__all__ = [
    "__version__",
    # 模型
    "BarData", "Order", "OrderSide", "OrderType", "OrderStatus",
    "Position", "Account", "TradeData", "Portfolio",
    # 引擎
    "Cerebro", "EventEngine", "ProgressBar", "EventType",
    "CommissionInfo", "FixedSlippage", "PercentSlippage", "AdaptiveSlippage",
    "BacktestBroker", "PaperBroker", "LiveBroker", "Broker",
    "RiskManager", "BacktestMetrics",
    "FixedFractionSizer", "KellySizer", "ATRSizer", "VolatilityTargetSizer", "EqualWeightSizer",
    # 策略
    "BaseStrategy", "Signal", "SignalSide", "SignalSource", "SignalManager",
    "DualMACrossoverStrategy", "RSIReversalStrategy", "BollingerBounceStrategy",
    "MACDDivergenceStrategy", "DualThrustStrategy", "MeanReversionStrategy", "MomentumStrategy",
    # 指标
    "MA", "EMA", "KAMA", "TRIX",
    "RSI", "KDJ", "CCI", "ROC", "STOCHRSI",
    "BOLL", "ATR", "STDDEV", "SAR",
    "MACD", "OBV", "HIGHEST", "LOWEST", "VOLUME",
    "indicator", "apply_indicators",
    # 数据
    "DataFeed", "DataCache", "CSVFeed", "BaoStockFeed",
    # AI
    "BacktestAgent", "IndicatorAgent", "RiskAgent",
    "MarketState", "DynamicRiskParams", "MarketEnvironment",
    # 报表
    "ReportGenerator",
    # 通知器
    "DingTalkNotifier", "EmailNotifier", "WeChatNotifier", "TelegramNotifier",
]
