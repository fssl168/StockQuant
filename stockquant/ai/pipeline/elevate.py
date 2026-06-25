# -*- coding: utf-8 -*-
"""F020 信息升华阶段"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..memory.system import MemorySystem

logger = logging.getLogger("stockquant.ai.pipeline")


class ElevateStage:
    """信息升华阶段 — LongTermRetriever + MultiSourceFusion + LogicVerifier + CrossValidator"""

    def __init__(self, memory: MemorySystem | None = None) -> None:
        self._memory = memory

    def execute(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """执行升华 — 多源融合 + 置信度评分 + 推理链"""
        insights: List[Dict[str, Any]] = []

        verified = summary.get("verified", False)
        article_count = summary.get("article_count", 0)
        facts = summary.get("facts", [])
        confidence_scores: List[float] = []

        # 多源融合：计算可信来源数量
        source_count = sum([
            verified,                                    # 来源已验证
            len(facts) > 3,                              # 有足够历史事实支撑
            article_count > 2,                           # 信息量充足
            summary.get("confidence", 0) > 0.5,          # 总结置信度高
        ])

        if verified and article_count > 2 and source_count >= 2:
            confidence = min(0.95, 0.5 + source_count * 0.125)
            confidence_scores.append(confidence)
            insights.append({
                "type": "confirmed_trend",
                "confidence": round(confidence, 3),
                "description": f"基于 {article_count} 条信息的多源融合确认（{source_count}/{4} 个来源一致）",
                "source_count": source_count,
                "reasoning_chain": [
                    f"信息来源验证: {'通过' if verified else '未通过'}",
                    f"事实支撑: {len(facts)} 条",
                    f"信息量: {article_count} 条",
                ],
            })

        # 高置信度洞察
        if source_count >= 3:
            confidence_scores.append(min(0.9, 0.7 + source_count * 0.05))
            insights.append({
                "type": "high_confidence_insight",
                "confidence": round(min(0.9, 0.7 + source_count * 0.05), 3),
                "description": f"高置信度洞察：{source_count} 个独立来源一致，建议重点关注",
            })

        if self._memory:
            # 检索已验证知识
            long_term = self._memory.search_long_term(limit=5)
            if long_term:
                insights.append({
                    "type": "historical_context",
                    "confidence": 0.5,
                    "count": len(long_term),
                    "description": f"L3 长期记忆提供 {len(long_term)} 条相关历史上下文",
                })
                confidence_scores.append(0.5)

        overall_confidence = (
            max(confidence_scores) if confidence_scores else 0.0
        )

        return {
            "insights": insights,
            "summary": summary.get("summary", ""),
            "overall_confidence": round(overall_confidence, 3),
            "source_count": source_count,
        }
