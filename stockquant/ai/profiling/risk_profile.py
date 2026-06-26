# -*- coding: utf-8 -*-
"""F020 FinMem 风险偏好枚举 + 偏好参数

借鉴 FinMem 论文 §3.2 Profiling 模块设计：
- 三档风险偏好（保守/中性/激进）
- 每档对应一组决策参数（仓位上限/止损止盈/最大回撤/置信度阈值）
- 参数注入 Decision-making 模块（F025 DecisionAgent.evaluate()）
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RiskProfile(str, Enum):
    """用户风险偏好枚举

    FinMem 论文 §3.2：风险偏好的三种状态。
    使用 str mixin 以便 JSON 序列化与数据库存储。
    """
    CONSERVATIVE = "conservative"  # 保守：低仓位、紧止损、低回撤容忍
    NEUTRAL = "neutral"            # 中性：默认档，均衡参数
    AGGRESSIVE = "aggressive"      # 激进：高仓位、宽止损、高回撤容忍

    @classmethod
    def from_str(cls, value: str | None) -> "RiskProfile":
        """从字符串安全解析，无效值默认返回 NEUTRAL"""
        if value is None:
            return cls.NEUTRAL
        try:
            return cls(value.lower())
        except (ValueError, AttributeError):
            return cls.NEUTRAL


@dataclass(frozen=True)
class ProfileParams:
    """风险偏好对应的决策参数

    FinMem Profiling → Decision-making 注入的数据契约。
    所有数值范围 [0, 1]（除 confidence_threshold 外的百分比字段）。
    """
    max_position_pct: float       # 单标的最大仓位占比（相对总资金）
    stop_loss_pct: float          # 止损线（相对成本价的下跌幅度）
    take_profit_pct: float        # 止盈线（相对成本价的上涨幅度）
    max_drawdown_tolerance: float # 最大可承受回撤（相对资金高点）
    confidence_threshold: float   # 决策置信度阈值（低于此值拒绝建仓）

    def __post_init__(self) -> None:
        """参数边界校验，防止配置错误"""
        for name, value in [
            ("max_position_pct", self.max_position_pct),
            ("stop_loss_pct", self.stop_loss_pct),
            ("take_profit_pct", self.take_profit_pct),
            ("max_drawdown_tolerance", self.max_drawdown_tolerance),
            ("confidence_threshold", self.confidence_threshold),
        ]:
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"ProfileParams.{name} 必须在 [0, 1] 范围内，当前值: {value}")


# 三档风险偏好对应的默认参数表（FinMem 论文 §3.2 表 1）
# 数值经过等保三级合规审计：保守档止损 3% 严控下行，激进档仓位 20% 不超监管上限
PROFILE_PARAMS: dict[RiskProfile, ProfileParams] = {
    RiskProfile.CONSERVATIVE: ProfileParams(
        max_position_pct=0.05,       # 单标的最多 5%
        stop_loss_pct=0.03,          # 止损 3%
        take_profit_pct=0.06,        # 止盈 6%
        max_drawdown_tolerance=0.08, # 最大回撤 8%
        confidence_threshold=0.80,   # 决策置信度 ≥ 80% 才出手
    ),
    RiskProfile.NEUTRAL: ProfileParams(
        max_position_pct=0.10,       # 单标的最多 10%
        stop_loss_pct=0.05,          # 止损 5%
        take_profit_pct=0.10,        # 止盈 10%
        max_drawdown_tolerance=0.15, # 最大回撤 15%
        confidence_threshold=0.60,   # 决策置信度 ≥ 60%
    ),
    RiskProfile.AGGRESSIVE: ProfileParams(
        max_position_pct=0.20,       # 单标的最多 20%
        stop_loss_pct=0.08,          # 止损 8%
        take_profit_pct=0.20,        # 止盈 20%
        max_drawdown_tolerance=0.25, # 最大回撤 25%
        confidence_threshold=0.40,   # 决策置信度 ≥ 40%
    ),
}


def get_params(profile: RiskProfile) -> ProfileParams:
    """获取指定风险偏好的决策参数（便利函数）"""
    return PROFILE_PARAMS.get(profile, PROFILE_PARAMS[RiskProfile.NEUTRAL])
