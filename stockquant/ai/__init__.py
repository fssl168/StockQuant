# -*- coding: utf-8 -*-
"""AI 包（F020-F028 系列）"""

from stockquant.ai.backtest_agent import BacktestAgent
from stockquant.ai.indicator_agent import IndicatorAgent, MarketState
from stockquant.ai.risk_agent import RiskAgent, DynamicRiskParams, MarketEnvironment
from stockquant.ai.json_utils import robust_json_parse
from stockquant.ai.news_searcher import NewsSearcher, NewsItem
from stockquant.ai.strategy_agent import StrategyAgent
from stockquant.ai.decision_agent import DecisionAgent
from stockquant.ai.chat_agent import ChatAgent, Conversation
from stockquant.ai.chat_memory import ChatMemory
from stockquant.ai.chat_tools import (
    query_market_data,
    generate_chart_json,
    trigger_backtest,
    search_news,
)
from stockquant.ai.monitor_agent import MonitorAgent, MonitorSignal
from stockquant.ai.comparison_agent import ComparisonAgent, StrategyComparison
from stockquant.ai.models import (
    DecisionAdvice,
    DecisionMode,
    Signal,
    SignalSource,
    StrategyGenerationResult,
    StrategyIntent,
    StrategyScore,
    AuditLog,
)

__all__ = [
    "BacktestAgent",
    "IndicatorAgent",
    "MarketState",
    "RiskAgent",
    "DynamicRiskParams",
    "MarketEnvironment",
    "robust_json_parse",
    "NewsSearcher",
    "NewsItem",
    "StrategyAgent",
    "DecisionAgent",
    "ChatAgent",
    "Conversation",
    "ChatMemory",
    "query_market_data",
    "generate_chart_json",
    "trigger_backtest",
    "search_news",
    "MonitorAgent",
    "MonitorSignal",
    "ComparisonAgent",
    "StrategyComparison",
    "DecisionAdvice",
    "DecisionMode",
    "Signal",
    "SignalSource",
    "StrategyGenerationResult",
    "StrategyIntent",
    "StrategyScore",
    "AuditLog",
]
