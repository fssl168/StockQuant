# -*- coding: utf-8 -*-
"""F020 GAP-M7 — ClaimVerifier / CrossValidator 验证 API 路由

提供对反幻觉系统的验证调用能力：
- 声明分类（同步）：classify_claim
- 单条声明验证（异步）：verify_claim
- 批量声明验证（异步）：verify_claims_batch
- 多模型交叉验证（异步）：CrossValidator.verify

路径前缀：/api/hallucination/verify/*

注意：与现有 hallucination.py 路由（管理配置/记录）共存，本路由专注验证调用。
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from stockquant.api.deps import get_current_user
from stockquant.api.schemas import UserToken

router = APIRouter(tags=["反幻觉验证"])
logger = logging.getLogger("stockquant.api.hallucination_verify")


@router.post("/hallucination/verify/classify", summary="声明类型分类（同步）")
async def classify_claim(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_current_user),
):
    """对输入文本做六类原子声明分类

    Body:
        {"text": "茅台2023年净利润同比增长30%"}

    Returns:
        {"claim_type": "numeric", "text": "..."}
    """
    text = payload.get("text")
    if not text or not isinstance(text, str):
        raise HTTPException(status_code=400, detail="text 字段必填且为字符串")

    try:
        from stockquant.ai.hallucination import ClaimVerifier
        claim_type = ClaimVerifier.classify_claim(text)
        return {
            "text": text,
            "claim_type": claim_type.value if hasattr(claim_type, "value") else str(claim_type),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("声明分类失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/hallucination/verify/claim", summary="验证单条声明（异步）")
async def verify_claim(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_current_user),
):
    """异步验证单条声明

    Body:
        {"text": "茅台2023年净利润同比增长30%", "claim_type": null}

    Returns:
        ClaimVerification 字典
    """
    text = payload.get("text")
    if not text or not isinstance(text, str):
        raise HTTPException(status_code=400, detail="text 字段必填且为字符串")

    try:
        from stockquant.ai.hallucination import ClaimVerifier, ClaimType
        verifier = ClaimVerifier()
        claim_type_str = payload.get("claim_type")
        claim_type = None
        if claim_type_str:
            try:
                claim_type = ClaimType(claim_type_str)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"无效 claim_type: {claim_type_str}",
                )
        result = await verifier.verify_claim(text, claim_type=claim_type)
        return _safe_asdict(result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("声明验证失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/hallucination/verify/claims-batch", summary="批量验证声明（异步）")
async def verify_claims_batch(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_current_user),
):
    """异步批量验证声明

    Body:
        {"claims": ["声明1", "声明2", ...]}

    Returns:
        {"count": N, "results": [ClaimVerification, ...]}
    """
    claims = payload.get("claims")
    if not claims or not isinstance(claims, list):
        raise HTTPException(status_code=400, detail="claims 字段必填且为列表")
    if not all(isinstance(c, str) for c in claims):
        raise HTTPException(status_code=400, detail="claims 列表中所有元素必须为字符串")

    try:
        from stockquant.ai.hallucination import ClaimVerifier
        verifier = ClaimVerifier()
        results = await verifier.verify_claims_batch(claims)
        return {
            "count": len(results),
            "results": [_safe_asdict(r) for r in results],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("批量声明验证失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/hallucination/verify/cross-validate", summary="多模型交叉验证（异步）")
async def cross_validate(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_current_user),
):
    """多模型交叉验证单条声明

    Body:
        {"text": "茅台2024年营收同比增长15%"}

    Returns:
        VerifyResult 字典（含 consensus/verdict/confidence/models/agreement_score）
    """
    text = payload.get("text")
    if not text or not isinstance(text, str):
        raise HTTPException(status_code=400, detail="text 字段必填且为字符串")

    try:
        from stockquant.ai.hallucination import CrossValidator
        validator = CrossValidator()
        result = await validator.verify(text)
        return _safe_asdict(result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("多模型交叉验证失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


def _safe_asdict(obj: Any) -> Dict[str, Any]:
    """安全将 dataclass 转字典，处理枚举值不可序列化问题"""
    try:
        return asdict(obj)
    except TypeError:
        # 非 dataclass 或含不可序列化字段，手动转换
        if hasattr(obj, "__dict__"):
            result = {}
            for k, v in obj.__dict__.items():
                if hasattr(v, "value"):
                    result[k] = v.value
                elif isinstance(v, list):
                    result[k] = [
                        item.value if hasattr(item, "value") else item
                        for item in v
                    ]
                else:
                    result[k] = v
            return result
        return {"raw": str(obj)}
