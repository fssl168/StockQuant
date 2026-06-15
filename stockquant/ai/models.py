# -*- coding: utf-8 -*-
"""F022/F025 共享数据模型 — 策略生成与辅助决策"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ── F022 策略生成模型 ──


@dataclass
class StrategyIntent:
    """策略意图解析结果。

    由 parse_strategy_intent 工具从自然语言中提取。
    """

    indicators: List[Dict[str, Any]] = field(default_factory=list)
    # [{"name": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9}}]

    entry_conditions: List[str] = field(default_factory=list)
    # ["MACD 金叉", "RSI < 30"]

    exit_conditions: List[str] = field(default_factory=list)
    # ["MACD 死叉", "止损 5%"]

    position_method: str = "FixedFraction"
    position_params: Dict[str, Any] = field(default_factory=lambda: {"pct": 0.2})

    risk_params: Dict[str, Any] = field(default_factory=dict)
    # {"stop_loss": 0.05, "max_drawdown": 0.15}

    description: str = ""


@dataclass
class ValidationResult:
    """策略代码验证结果。"""

    valid: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class StrategyScore:
    """策略多维度评分。"""

    total: float = 0.0           # 0-100 综合分
    profitability: float = 0.0   # 收益维度 0-100
    risk_control: float = 0.0    # 风险维度 0-100
    trading_quality: float = 0.0 # 交易质量维度 0-100
    stability: float = 0.0       # 稳定性维度 0-100
    overfitting_risk: str = "low"  # "low" / "medium" / "high"


@dataclass
class ImprovementSuggestion:
    """策略优化建议。"""

    category: str       # "indicator" / "condition" / "risk" / "position"
    description: str    # 具体建议内容
    priority: str       # "high" / "medium" / "low"
    code_hint: str = "" # 可选的代码片段提示


@dataclass
class StrategyGenerationResult:
    """F022 策略生成完整结果。"""

    code: str = ""                         # 生成的策略 Python 代码
    validation: ValidationResult = field(default_factory=ValidationResult)
    backtest_result: Optional[Dict[str, Any]] = None
    score: StrategyScore = field(default_factory=StrategyScore)
    suggestions: List[ImprovementSuggestion] = field(default_factory=list)
    intent: Optional[StrategyIntent] = None
    success: bool = False
    error: str = ""


# ── F025 辅助决策模型 ──


class DecisionMode(Enum):
    """人机协同模式。"""

    AUTO = "auto"               # AI 建议自动下单
    SEMI_AUTO = "semi_auto"     # AI 建议 → 用户确认 → 下单
    READ_ONLY = "read_only"     # AI 只推送建议


class SignalSource(Enum):
    """信号来源。"""

    STRATEGY = "strategy"   # 传统策略信号（最高优先级）
    F025 = "f025"           # AI 辅助信号
    F022 = "f022"           # AI 生成策略信号
    F024 = "f024"           # 盯盘 Agent 信号


@dataclass
class Signal:
    """交易信号。"""

    symbol: str
    direction: str          # "BUY" / "SELL"
    source: SignalSource = SignalSource.STRATEGY
    confidence: float = 1.0
    quantity: int = 0
    price: Optional[float] = None
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalVerification:
    """信号技术面验证结果。"""

    confirmed: bool = False
    indicators_summary: Dict[str, Any] = field(default_factory=dict)
    # {"MA": "多头排列", "MACD": "金叉确认", "RSI": "50.2 中性"}

    contradictions: List[str] = field(default_factory=list)
    # ["RSI 超买(78) 与买入信号矛盾"]


@dataclass
class RiskAssessment:
    """风险评估结果。"""

    level: str = "low"  # "low" / "medium" / "high" / "extreme"
    warnings: List[str] = field(default_factory=list)
    adjusted_params: Dict[str, Any] = field(default_factory=dict)
    # {"max_position_pct": 0.15, "stop_loss_pct": 0.03}


@dataclass
class MarketEnvResult:
    """市场环境评估结果。"""

    environment: str = "sideways"  # "bull" / "bear" / "sideways" / "crash"
    suggestion: str = ""           # 建议的仓位/策略调整


@dataclass
class SentimentResult:
    """消息面验证结果。"""

    score: float = 0.5       # 0.0(极度悲观) - 1.0(极度乐观)
    key_events: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class PositionEvaluation:
    """仓位合理性检查结果。"""

    reasonable: bool = True
    suggestion: str = ""
    current_exposure: float = 0.0  # 当前总仓位占比
    proposed_exposure: float = 0.0 # 建议后总仓位占比


@dataclass
class DecisionAdvice:
    """AI 决策建议。"""

    action: str = "reject"          # "confirm" / "reject" / "modify"
    confidence: float = 0.0         # 0.0-1.0
    reason: str = ""
    modified_params: Optional[Dict[str, Any]] = None
    # {"qty": 200, "price": 1850.0}

    risk_warnings: List[str] = field(default_factory=list)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    # 验证详情
    verification: Optional[SignalVerification] = None
    risk: Optional[RiskAssessment] = None
    market_env: Optional[MarketEnvResult] = None
    sentiment: Optional[SentimentResult] = None
    position_eval: Optional[PositionEvaluation] = None


@dataclass
class AuditLog:
    """决策审计日志。"""

    timestamp: datetime = field(default_factory=datetime.now)
    signal_source: str = ""         # "strategy" / "f024" / "f022"
    symbol: str = ""
    direction: str = ""             # "BUY" / "SELL"
    original_signal: Dict[str, Any] = field(default_factory=dict)
    ai_decision: Optional[DecisionAdvice] = None
    final_action: str = ""          # 实际执行的动作
    user_confirmed: Optional[bool] = None  # 半自动模式下用户是否确认
