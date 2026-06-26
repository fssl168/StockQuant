# -*- coding: utf-8 -*-
"""F020 验证模式 — 不同严格程度的验证策略"""
from __future__ import annotations

from enum import Enum
from typing import Callable, Dict, List

from .checkpoints import (
    source_verify,
    fact_screen,
    consistency_filter,
    prompt_constraint,
    summary_verify,
    reasoning_verify,
    cross_validation,
    confidence_score,
)


class VerificationMode(Enum):
    """验证模式

    STRICT:    全部 8 个检查点，高阈值
    STANDARD:  4 个核心检查点，中等阈值
    RELAXED:   仅置信度评分，低阈值
    EMERGENCY: 跳过所有验证
    """

    STRICT = "strict"
    STANDARD = "standard"
    RELAXED = "relaxed"
    EMERGENCY = "emergency"


# 各模式对应的检查点列表
MODE_CHECKPOINTS: Dict[VerificationMode, List[Callable]] = {
    VerificationMode.STRICT: [
        source_verify,
        fact_screen,
        consistency_filter,
        prompt_constraint,
        summary_verify,
        reasoning_verify,
        cross_validation,
        confidence_score,
    ],
    VerificationMode.STANDARD: [
        source_verify,
        fact_screen,
        summary_verify,
        confidence_score,
    ],
    VerificationMode.RELAXED: [
        confidence_score,
    ],
    VerificationMode.EMERGENCY: [],
}

# 各模式对应的通过阈值
MODE_THRESHOLDS: Dict[VerificationMode, float] = {
    VerificationMode.STRICT: 0.7,
    VerificationMode.STANDARD: 0.5,
    VerificationMode.RELAXED: 0.3,
    VerificationMode.EMERGENCY: 0.0,
}


def get_checkpoints(mode: VerificationMode) -> List[Callable]:
    """获取指定模式的检查点列表"""
    return MODE_CHECKPOINTS.get(mode, MODE_CHECKPOINTS[VerificationMode.STANDARD])


def get_threshold(mode: VerificationMode) -> float:
    """获取指定模式的通过阈值"""
    return MODE_THRESHOLDS.get(mode, 0.5)
