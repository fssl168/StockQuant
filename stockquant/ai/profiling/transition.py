# -*- coding: utf-8 -*-
"""F020 FinMem 风险偏好动态转换规则

借鉴 FinMem 论文 §3.2 的动态转换机制：
- 市场暴跌（market_env=crash）：aggressive→neutral, neutral→conservative
- 连续亏损（recent_hit_rate < 0.3）：降一级
- 用户手动覆盖：任意切换
- 冷却期 7 天，防止抖动

转换函数返回新 RiskProfile，但不直接持久化，由 ProfilingManager 负责落库。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from .risk_profile import RiskProfile

logger = logging.getLogger("stockquant.ai.profiling.transition")


# 转换触发器类型
TRIGGER_MARKET_CRASH = "market_crash"           # 市场暴跌
TRIGGER_CONSECUTIVE_LOSS = "consecutive_loss"   # 连续亏损
TRIGGER_MANUAL = "manual"                       # 用户手动覆盖
TRIGGER_COOLDOWN_EXPIRED = "cooldown_expired"  # 冷却期到期（暂未使用）
TRIGGER_RECOVERY = "recovery"                   # 命中率恢复（可升档）


# 风险偏好降级顺序：aggressive → neutral → conservative
_DOWNGRADE_PATH: Dict[RiskProfile, RiskProfile] = {
    RiskProfile.AGGRESSIVE: RiskProfile.NEUTRAL,
    RiskProfile.NEUTRAL: RiskProfile.CONSERVATIVE,
    RiskProfile.CONSERVATIVE: RiskProfile.CONSERVATIVE,  # 已最低，不再降
}

# 风险偏好升级顺序（仅在命中率恢复时触发）
_UPGRADE_PATH: Dict[RiskProfile, RiskProfile] = {
    RiskProfile.CONSERVATIVE: RiskProfile.NEUTRAL,
    RiskProfile.NEUTRAL: RiskProfile.AGGRESSIVE,
    RiskProfile.AGGRESSIVE: RiskProfile.AGGRESSIVE,  # 已最高
}


@dataclass
class TransitionContext:
    """转换上下文 — 用于决策是否触发转换以及记录历史

    所有字段可选，便于不同触发器使用部分字段。
    """
    market_env: Optional[str] = None         # crash | volatile | stable | bullish
    recent_hit_rate: Optional[float] = None  # 最近 N 笔交易命中率 [0, 1]
    consecutive_loss_count: int = 0          # 连续亏损笔数
    user_target: Optional[RiskProfile] = None  # 用户手动指定的目标偏好
    extra: Dict[str, Any] = field(default_factory=dict)  # 扩展字段

    def to_json(self) -> str:
        """序列化为 JSON 字符串（写入 UserProfileHistory.context_json）"""
        payload = {
            "market_env": self.market_env,
            "recent_hit_rate": self.recent_hit_rate,
            "consecutive_loss_count": self.consecutive_loss_count,
            "user_target": self.user_target.value if self.user_target else None,
            "extra": self.extra,
        }
        return json.dumps(payload, ensure_ascii=False)


class ProfileTransitioner:
    """风险偏好动态转换器

    转换规则（保守策略，避免频繁切换）：
    1. 手动覆盖优先级最高，立即生效但记录冷却
    2. 市场暴跌（market_env=crash）：降一级
    3. 连续亏损 ≥ 3 笔 或 命中率 < 30%：降一级
    4. 命中率 > 60% 且持续稳定：可升一级（需冷却期已过）
    5. 冷却期 7 天内不再触发自动转换（手动覆盖不受冷却限制）

    用法：
        transitioner = ProfileTransitioner()
        new_profile = transitioner.transition(
            current=RiskProfile.AGGRESSIVE,
            trigger=TRIGGER_MARKET_CRASH,
            context=TransitionContext(market_env="crash"),
        )
    """

    COOLDOWN_DAYS = 7  # 自动转换冷却期（天）

    # 触发自动降级的连续亏损笔数阈值
    CONSECUTIVE_LOSS_THRESHOLD = 3

    # 触发自动降级的命中率阈值
    HIT_RATE_DOWNGRADE_THRESHOLD = 0.30

    # 触发自动升级的命中率阈值
    HIT_RATE_UPGRADE_THRESHOLD = 0.60

    def should_transition(
        self,
        current: RiskProfile,
        context: TransitionContext,
        days_since_last: int = 0,
    ) -> Optional[str]:
        """判断是否应该触发自动转换

        Args:
            current: 当前风险偏好
            context: 转换上下文
            days_since_last: 距离上次转换的天数（冷却期判断）

        Returns:
            触发器名称（如 "market_crash"）或 None（不触发）
        """
        # 手动覆盖不受冷却期限制
        if context.user_target is not None and context.user_target != current:
            return TRIGGER_MANUAL

        # 自动转换受冷却期限制
        if days_since_last < self.COOLDOWN_DAYS:
            return None

        # 市场暴跌触发降级
        if context.market_env == "crash" and current != RiskProfile.CONSERVATIVE:
            return TRIGGER_MARKET_CRASH

        # 连续亏损触发降级
        if context.consecutive_loss_count >= self.CONSECUTIVE_LOSS_THRESHOLD:
            return TRIGGER_CONSECUTIVE_LOSS

        # 命中率低于阈值触发降级
        if (
            context.recent_hit_rate is not None
            and context.recent_hit_rate < self.HIT_RATE_DOWNGRADE_THRESHOLD
            and current != RiskProfile.CONSERVATIVE
        ):
            return TRIGGER_CONSECUTIVE_LOSS

        # 命中率高于阈值触发升级
        if (
            context.recent_hit_rate is not None
            and context.recent_hit_rate > self.HIT_RATE_UPGRADE_THRESHOLD
            and current != RiskProfile.AGGRESSIVE
        ):
            return TRIGGER_RECOVERY

        return None

    def transition(
        self,
        current: RiskProfile,
        trigger: str,
        context: TransitionContext,
    ) -> RiskProfile:
        """执行转换，返回新风险偏好

        Args:
            current: 当前风险偏好
            trigger: 触发器（手动 / 市场暴跌 / 连续亏损 / 恢复）
            context: 转换上下文

        Returns:
            新的风险偏好（如果触发器无法识别，返回原值）
        """
        if trigger == TRIGGER_MANUAL:
            if context.user_target is None:
                logger.warning("手动转换但未提供 user_target，保持原值")
                return current
            logger.info(
                "Profiling 手动转换: %s → %s", current.value, context.user_target.value
            )
            return context.user_target

        if trigger in (TRIGGER_MARKET_CRASH, TRIGGER_CONSECUTIVE_LOSS):
            new_profile = _DOWNGRADE_PATH[current]
            if new_profile != current:
                logger.info(
                    "Profiling 自动降级: %s → %s (trigger=%s)",
                    current.value, new_profile.value, trigger,
                )
            return new_profile

        if trigger == TRIGGER_RECOVERY:
            new_profile = _UPGRADE_PATH[current]
            if new_profile != current:
                logger.info(
                    "Profiling 自动升级: %s → %s (trigger=recovery)",
                    current.value, new_profile.value,
                )
            return new_profile

        logger.warning("未识别的转换触发器: %s，保持原值", trigger)
        return current

    def evaluate(
        self,
        current: RiskProfile,
        context: TransitionContext,
        last_transition_at: Optional[datetime] = None,
    ) -> tuple[Optional[str], RiskProfile]:
        """一站式评估：判断是否应该转换 + 执行转换

        Args:
            current: 当前风险偏好
            context: 转换上下文
            last_transition_at: 上次转换时间（冷却期判断）

        Returns:
            (trigger, new_profile) 元组；trigger 为 None 表示不转换
        """
        days_since_last = 0
        if last_transition_at is not None:
            days_since_last = (datetime.now() - last_transition_at).days

        trigger = self.should_transition(current, context, days_since_last)
        if trigger is None:
            return None, current

        new_profile = self.transition(current, trigger, context)
        return trigger, new_profile
