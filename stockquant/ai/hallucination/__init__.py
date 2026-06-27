# -*- coding: utf-8 -*-
"""F020 反幻觉系统 — FINGROUND 六类声明验证 + 多模型交叉验证

公共接口：
- ClaimVerifier: FINGROUND 六类原子声明验证器（NUMERIC/TEMPORAL/ENTITY_ATTR/COMPARATIVE/REGULATORY/COMPUTATIONAL）
- CrossValidator: 多模型交叉验证器（gpt-4o-mini / claude-haiku-3 / deepseek-chat）
- HallucinationPipeline: 反幻觉编排管线（多阶段验证 + 五步纠正 + 多模型交叉验证）
- VerificationMode: 验证模式枚举（STRICT/STANDARD/RELAXED/EMERGENCY）
"""
from .claim_verifier import ClaimVerifier, ClaimType, ClaimVerification
from .cross_validator import (
    CrossValidator,
    VerifyResult,
    ModelVerifyResult,
    multi_model_verify,
    reset_default_validator,
)
from .pipeline import HallucinationPipeline, FactDatabase, HallucinationDB
from .modes import VerificationMode, get_checkpoints, get_threshold
from .checkpoints import CheckpointResult, fact_screen
from .corrector import FiveStepCorrector
from .database import HallucinationDatabase

__all__ = [
    # ClaimVerifier (Phase E1)
    "ClaimVerifier", "ClaimType", "ClaimVerification",
    # CrossValidator (Phase E2)
    "CrossValidator", "VerifyResult", "ModelVerifyResult",
    "multi_model_verify", "reset_default_validator",
    # Pipeline
    "HallucinationPipeline", "FactDatabase", "HallucinationDB",
    # Modes
    "VerificationMode", "get_checkpoints", "get_threshold",
    # Checkpoints
    "CheckpointResult", "fact_screen",
    # Corrector
    "FiveStepCorrector",
    # Database
    "HallucinationDatabase",
]
