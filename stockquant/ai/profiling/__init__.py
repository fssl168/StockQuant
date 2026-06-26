# -*- coding: utf-8 -*-
"""F020 FinMem Profiling 模块 — 用户风险偏好画像 + 动态转换

FinMem 论文 §3.2 三大模块之一：
- RiskProfile 枚举（conservative/neutral/aggressive）
- ProfileParams 决策参数（仓位上限/止损止盈/最大回撤/置信度阈值）
- ProfileTransitioner 动态转换规则（市场暴跌/连续亏损/手动覆盖 + 7 天冷却期）
- ProfilingManager 统一接口（读取/更新/触发转换/获取参数）
"""
from .risk_profile import RiskProfile, ProfileParams, PROFILE_PARAMS, get_params
from .transition import ProfileTransitioner, TransitionContext
from .manager import ProfilingManager

__all__ = [
    "RiskProfile",
    "ProfileParams",
    "PROFILE_PARAMS",
    "get_params",
    "ProfileTransitioner",
    "TransitionContext",
    "ProfilingManager",
]
