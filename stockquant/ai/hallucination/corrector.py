# -*- coding: utf-8 -*-
"""F020 五步纠正器 — 逐步纠正幻觉问题"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from .checkpoints import (
    CheckpointResult,
    source_verify,
    fact_screen,
    consistency_filter,
    cross_validation,
    confidence_score,
)

logger = logging.getLogger("stockquant.ai.hallucination.corrector")


class FiveStepCorrector:
    """五步纠正器

    按顺序执行 5 个纠正步骤，每步失败则尝试下一步:
    1. fact_check    — 事实核查
    2. source_check  — 来源核查
    3. consistency   — 一致性检查
    4. cross_validation — 交叉验证
    5. confidence    — 置信度评估

    如果所有步骤都失败，标记为低置信度。
    """

    def correct(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """执行五步纠正

        Args:
            data: 包含待验证信息的字典

        Returns:
            纠正结果，包含 passed/score/steps/correction 等字段
        """
        result: Dict[str, Any] = {
            "passed": False,
            "score": 0.0,
            "steps": [],
            "correction": None,
        }

        steps = [
            ("fact_check", fact_screen),
            ("source_check", source_verify),
            ("consistency", consistency_filter),
            ("cross_validation", cross_validation),
            ("confidence", confidence_score),
        ]

        scores: List[float] = []
        for step_name, check_fn in steps:
            try:
                passed, score, reason = check_fn(data)
            except Exception as exc:
                logger.warning("纠正步骤 %s 异常: %s", step_name, exc)
                passed, score, reason = False, 0.0, f"步骤异常: {exc}"

            result["steps"].append({
                "name": step_name,
                "passed": passed,
                "score": score,
                "reason": reason,
            })
            scores.append(score)

            if passed:
                result["passed"] = True
                result["score"] = score
                result["correction"] = f"步骤 {step_name} 通过: {reason}"
                break

        # 所有步骤都失败
        if not result["passed"]:
            avg_score = sum(scores) / len(scores) if scores else 0.0
            result["score"] = avg_score
            result["correction"] = "所有纠正步骤均未通过，标记为低置信度"
            logger.warning("五步纠正全部失败: avg_score=%.2f", avg_score)

        return result
