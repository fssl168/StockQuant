# -*- coding: utf-8 -*-
"""F020 FinMem Profiling 模块测试

覆盖：
- RiskProfile 枚举与 from_str 安全解析
- ProfileParams 边界校验
- PROFILE_PARAMS 三档默认参数完备性
- ProfileTransitioner 触发器与冷却期
- ProfilingManager 内存降级全流程
"""
from __future__ import annotations

import sys
import os
from datetime import datetime, timedelta

import pytest

# 确保项目根目录在 sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from stockquant.ai.profiling import (
    RiskProfile,
    ProfileParams,
    PROFILE_PARAMS,
    ProfileTransitioner,
    TransitionContext,
    ProfilingManager,
)
from stockquant.ai.profiling.transition import (
    TRIGGER_MANUAL,
    TRIGGER_MARKET_CRASH,
    TRIGGER_CONSECUTIVE_LOSS,
    TRIGGER_RECOVERY,
)


# ─── RiskProfile 枚举 ────────────────────────────────────────────────


class TestRiskProfile:
    def test_three_profiles_exist(self):
        assert RiskProfile.CONSERVATIVE.value == "conservative"
        assert RiskProfile.NEUTRAL.value == "neutral"
        assert RiskProfile.AGGRESSIVE.value == "aggressive"

    def test_from_str_valid(self):
        assert RiskProfile.from_str("conservative") == RiskProfile.CONSERVATIVE
        assert RiskProfile.from_str("NEUTRAL") == RiskProfile.NEUTRAL
        assert RiskProfile.from_str("Aggressive") == RiskProfile.AGGRESSIVE

    def test_from_str_invalid_returns_neutral(self):
        assert RiskProfile.from_str(None) == RiskProfile.NEUTRAL
        assert RiskProfile.from_str("unknown") == RiskProfile.NEUTRAL
        assert RiskProfile.from_str("") == RiskProfile.NEUTRAL


# ─── ProfileParams 参数 ─────────────────────────────────────────────


class TestProfileParams:
    def test_three_profiles_have_params(self):
        assert len(PROFILE_PARAMS) == 3
        for profile in RiskProfile:
            assert profile in PROFILE_PARAMS

    def test_params_in_range(self):
        for profile, params in PROFILE_PARAMS.items():
            assert 0.0 < params.max_position_pct <= 1.0
            assert 0.0 < params.stop_loss_pct <= 1.0
            assert 0.0 < params.take_profit_pct <= 1.0
            assert 0.0 < params.max_drawdown_tolerance <= 1.0
            assert 0.0 <= params.confidence_threshold <= 1.0

    def test_conservative_more_strict_than_aggressive(self):
        c = PROFILE_PARAMS[RiskProfile.CONSERVATIVE]
        a = PROFILE_PARAMS[RiskProfile.AGGRESSIVE]
        # 保守档仓位更小、止损更紧、置信度阈值更高
        assert c.max_position_pct < a.max_position_pct
        assert c.stop_loss_pct < a.stop_loss_pct
        assert c.confidence_threshold > a.confidence_threshold

    def test_params_boundary_validation(self):
        with pytest.raises(ValueError):
            ProfileParams(
                max_position_pct=1.5,
                stop_loss_pct=0.03,
                take_profit_pct=0.06,
                max_drawdown_tolerance=0.08,
                confidence_threshold=0.8,
            )


# ─── ProfileTransitioner ────────────────────────────────────────────


class TestProfileTransitioner:
    def setup_method(self):
        self.transitioner = ProfileTransitioner()

    def test_manual_override_no_cooldown(self):
        """手动覆盖不受冷却期限制"""
        ctx = TransitionContext(user_target=RiskProfile.AGGRESSIVE)
        trigger = self.transitioner.should_transition(
            RiskProfile.NEUTRAL, ctx, days_since_last=0
        )
        assert trigger == TRIGGER_MANUAL

    def test_market_crash_triggers_downgrade(self):
        ctx = TransitionContext(market_env="crash")
        trigger = self.transitioner.should_transition(
            RiskProfile.AGGRESSIVE, ctx, days_since_last=10
        )
        assert trigger == TRIGGER_MARKET_CRASH

    def test_market_crash_no_change_if_already_conservative(self):
        ctx = TransitionContext(market_env="crash")
        trigger = self.transitioner.should_transition(
            RiskProfile.CONSERVATIVE, ctx, days_since_last=10
        )
        assert trigger is None

    def test_consecutive_loss_triggers_downgrade(self):
        ctx = TransitionContext(consecutive_loss_count=3)
        trigger = self.transitioner.should_transition(
            RiskProfile.AGGRESSIVE, ctx, days_since_last=10
        )
        assert trigger == TRIGGER_CONSECUTIVE_LOSS

    def test_low_hit_rate_triggers_downgrade(self):
        ctx = TransitionContext(recent_hit_rate=0.2)
        trigger = self.transitioner.should_transition(
            RiskProfile.NEUTRAL, ctx, days_since_last=10
        )
        assert trigger == TRIGGER_CONSECUTIVE_LOSS

    def test_high_hit_rate_triggers_upgrade(self):
        ctx = TransitionContext(recent_hit_rate=0.7)
        trigger = self.transitioner.should_transition(
            RiskProfile.CONSERVATIVE, ctx, days_since_last=10
        )
        assert trigger == TRIGGER_RECOVERY

    def test_cooldown_blocks_auto_transition(self):
        """冷却期内不触发自动转换"""
        ctx = TransitionContext(market_env="crash")
        trigger = self.transitioner.should_transition(
            RiskProfile.AGGRESSIVE, ctx, days_since_last=3
        )
        assert trigger is None

    def test_transition_downgrade_path(self):
        ctx = TransitionContext(market_env="crash")
        new_profile = self.transitioner.transition(
            RiskProfile.AGGRESSIVE, TRIGGER_MARKET_CRASH, ctx
        )
        assert new_profile == RiskProfile.NEUTRAL

    def test_transition_upgrade_path(self):
        ctx = TransitionContext(recent_hit_rate=0.7)
        new_profile = self.transitioner.transition(
            RiskProfile.CONSERVATIVE, TRIGGER_RECOVERY, ctx
        )
        assert new_profile == RiskProfile.NEUTRAL

    def test_transition_manual_uses_user_target(self):
        ctx = TransitionContext(user_target=RiskProfile.AGGRESSIVE)
        new_profile = self.transitioner.transition(
            RiskProfile.CONSERVATIVE, TRIGGER_MANUAL, ctx
        )
        assert new_profile == RiskProfile.AGGRESSIVE


# ─── ProfilingManager（内存降级） ──────────────────────────────────


class TestProfilingManagerMemory:
    def setup_method(self):
        # 使用 SQLite 内存数据库以便测试不依赖 PostgreSQL
        # 但 ProfilingManager 当前只支持 PostgreSQL / 内存降级
        # 因此直接用内存降级模式
        mgr = ProfilingManager.__new__(ProfilingManager)
        mgr._db_url = "postgresql+asyncpg://invalid:invalid@invalid:5432/invalid"
        mgr._user_id = "test_user"
        mgr._transitioner = ProfileTransitioner()
        mgr._engine = None
        mgr._session_factory = None
        mgr._backend = "memory"
        mgr._cache = {}
        self.mgr = mgr

    def test_default_profile_is_neutral(self):
        assert self.mgr.get_profile("user1") == RiskProfile.NEUTRAL

    def test_default_params_match_neutral(self):
        params = self.mgr.get_params("user1")
        assert params == PROFILE_PARAMS[RiskProfile.NEUTRAL]

    def test_manual_update_profile(self):
        self.mgr.update_profile(
            RiskProfile.AGGRESSIVE, user_id="user1", trigger=TRIGGER_MANUAL
        )
        assert self.mgr.get_profile("user1") == RiskProfile.AGGRESSIVE
        params = self.mgr.get_params("user1")
        assert params == PROFILE_PARAMS[RiskProfile.AGGRESSIVE]

    def test_history_recorded_on_update(self):
        self.mgr.update_profile(
            RiskProfile.AGGRESSIVE, user_id="user1", trigger=TRIGGER_MANUAL
        )
        history = self.mgr.get_history("user1", limit=10)
        assert len(history) >= 1
        assert history[0]["from_profile"] == "neutral"
        assert history[0]["to_profile"] == "aggressive"
        assert history[0]["trigger"] == TRIGGER_MANUAL

    def test_evaluate_transition_market_crash(self):
        # 先升级到 aggressive
        self.mgr.update_profile(
            RiskProfile.AGGRESSIVE, user_id="user2", trigger=TRIGGER_MANUAL
        )
        # 模拟时间已过冷却期
        self.mgr._cache["user2"]["updated_at"] = (
            datetime.now() - timedelta(days=10)
        ).isoformat()
        # 触发市场暴跌
        ctx = TransitionContext(market_env="crash")
        result = self.mgr.evaluate_transition(ctx, user_id="user2")
        assert result == RiskProfile.NEUTRAL
        assert self.mgr.get_profile("user2") == RiskProfile.NEUTRAL

    def test_evaluate_transition_cooldown_blocks(self):
        """冷却期内不触发自动转换"""
        self.mgr.update_profile(
            RiskProfile.AGGRESSIVE, user_id="user3", trigger=TRIGGER_MANUAL
        )
        # updated_at 是刚刚，冷却期内
        ctx = TransitionContext(market_env="crash")
        result = self.mgr.evaluate_transition(ctx, user_id="user3")
        assert result is None
        assert self.mgr.get_profile("user3") == RiskProfile.AGGRESSIVE
