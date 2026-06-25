# -*- coding: utf-8 -*-
"""DEPRECATED — 信息升华器（旧版）

请改用 :mod:`stockquant.ai.pipeline.elevate`（新版 ElevateStage）。
此文件保留仅供向后兼容，将在下一大版本移除。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.pipeline.elevator")


class Elevator:
    """信息升华器

    五步升华:
    1. L3 检索 — 从长期记忆检索交叉参考
    2. 多源融合 — 融合多来源信息
    3. 推理链验证 — 验证推理逻辑
    4. 交叉验证 — 与其他来源交叉确认
    5. 存储升华结果 — 写入 L3 长期记忆
    """

    def __init__(
        self,
        memory_system: Any = None,
        hallucination_pipeline: Any = None,
    ) -> None:
        self._memory = memory_system
        self._hallucination = hallucination_pipeline

    def elevate(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """执行五步升华"""
        if not summary or summary.get("article_count", 0) == 0:
            return {
                "insights": [],
                "summary": summary.get("summary", ""),
                "elevated": False,
            }

        # Step 1: L3 检索
        l3_context = self._l3_retrieval(summary)

        # Step 2: 多源融合
        fused = self._multi_source_fusion(summary, l3_context)

        # Step 3: 推理链验证
        reasoning_verified = self._reasoning_chain_verify(fused)

        # Step 4: 交叉验证
        cross_validated = self._cross_validation(reasoning_verified, l3_context)

        # Step 5: 存储升华结果
        self._store_elevated(cross_validated)

        return {
            "insights": cross_validated.get("insights", []),
            "summary": summary.get("summary", ""),
            "l3_context_count": len(l3_context),
            "elevated": True,
            "confidence": cross_validated.get("confidence", 0.0),
        }

    def _l3_retrieval(self, summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """L3 检索 — 从长期记忆检索交叉参考"""
        if not self._memory:
            return []

        results: List[Dict[str, Any]] = []
        try:
            # 基于总结关键词检索
            summary_text = summary.get("summary", "")
            keywords = summary_text[:50] if summary_text else ""

            if keywords:
                l3_items = self._memory.search_long_term(
                    keyword=keywords, min_confidence=0.5, limit=10
                )
                results.extend(l3_items)

            # 基于事实检索
            facts = summary.get("facts", [])
            for fact in facts[:3]:
                fact_data = fact.get("data", {})
                if isinstance(fact_data, dict):
                    symbol = fact_data.get("symbol", "")
                    if symbol:
                        items = self._memory.search_long_term(
                            symbol=symbol, min_confidence=0.5, limit=5
                        )
                        results.extend(items)

        except Exception as exc:
            logger.warning("L3 检索失败: %s", exc)

        return results

    def _multi_source_fusion(
        self,
        summary: Dict[str, Any],
        l3_context: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """多源融合 — 融合当前总结与 L3 历史上下文"""
        insights: List[Dict[str, Any]] = []

        article_count = summary.get("article_count", 0)
        facts = summary.get("facts", [])
        summary_confidence = summary.get("confidence", 0.0)

        # 趋势确认: 多条信息 + 高置信度
        if article_count >= 3 and summary_confidence >= 0.6:
            insights.append({
                "type": "confirmed_trend",
                "confidence": min(summary_confidence + 0.1, 1.0),
                "description": f"基于 {article_count} 条信息的趋势确认",
                "sources": "current",
            })

        # 历史上下文: L3 有相关记录
        if l3_context:
            avg_l3_conf = sum(
                it.get("confidence", 0.5) for it in l3_context
            ) / len(l3_context)
            insights.append({
                "type": "historical_context",
                "confidence": avg_l3_conf * 0.8,
                "description": f"发现 {len(l3_context)} 条历史相关记录",
                "sources": "L3",
                "count": len(l3_context),
            })

        # 矛盾检测: 当前信息与 L3 矛盾
        if l3_context and facts:
            contradiction = self._detect_contradiction(summary, l3_context)
            if contradiction:
                insights.append({
                    "type": "contradiction_alert",
                    "confidence": 0.9,
                    "description": contradiction,
                    "sources": "current+L3",
                })

        # 新发现: L3 无相关记录
        if not l3_context and article_count > 0:
            insights.append({
                "type": "new_finding",
                "confidence": summary_confidence * 0.7,
                "description": "无历史记录的新发现",
                "sources": "current",
            })

        return {
            "insights": insights,
            "confidence": summary_confidence,
            "l3_count": len(l3_context),
        }

    def _reasoning_chain_verify(self, fused: Dict[str, Any]) -> Dict[str, Any]:
        """推理链验证 — 验证推理逻辑"""
        insights = fused.get("insights", [])

        verified_insights: List[Dict[str, Any]] = []
        for insight in insights:
            # 检查推理链完整性
            has_type = bool(insight.get("type"))
            has_confidence = "confidence" in insight
            has_description = bool(insight.get("description"))

            if has_type and has_confidence and has_description:
                # 推理链完整，保留
                insight["reasoning_verified"] = True
                verified_insights.append(insight)
            else:
                # 推理链不完整，降权
                insight["confidence"] = insight.get("confidence", 0.5) * 0.5
                insight["reasoning_verified"] = False
                verified_insights.append(insight)

        fused["insights"] = verified_insights
        return fused

    def _cross_validation(
        self,
        fused: Dict[str, Any],
        l3_context: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """交叉验证 — 与其他来源交叉确认"""
        insights = fused.get("insights", [])

        for insight in insights:
            insight_type = insight.get("type", "")

            if insight_type == "confirmed_trend":
                # 趋势确认需要 L3 支撑
                if l3_context:
                    insight["cross_validated"] = True
                    insight["confidence"] = min(insight.get("confidence", 0.5) + 0.1, 1.0)
                else:
                    insight["cross_validated"] = False
                    insight["confidence"] = insight.get("confidence", 0.5) * 0.8

            elif insight_type == "contradiction_alert":
                # 矛盾检测天然需要交叉验证
                insight["cross_validated"] = True

            elif insight_type == "new_finding":
                # 新发现无法交叉验证，降低置信度
                insight["cross_validated"] = False
                insight["confidence"] = insight.get("confidence", 0.5) * 0.6

            else:
                insight["cross_validated"] = False

        # 计算综合置信度
        if insights:
            avg_conf = sum(it.get("confidence", 0.0) for it in insights) / len(insights)
            fused["confidence"] = round(avg_conf, 3)

        return fused

    def _store_elevated(self, result: Dict[str, Any]) -> None:
        """存储升华结果到 L3"""
        if not self._memory:
            return

        insights = result.get("insights", [])
        for insight in insights:
            if insight.get("confidence", 0) >= 0.5 and insight.get("cross_validated"):
                try:
                    self._memory.add_long_term({
                        "content": insight.get("description", ""),
                        "type": insight.get("type", ""),
                        "confidence": insight.get("confidence", 0.0),
                        "timestamp": __import__("datetime").datetime.now().isoformat(),
                    })
                except Exception as exc:
                    logger.warning("L3 存储失败: %s", exc)

    @staticmethod
    def _detect_contradiction(
        summary: Dict[str, Any],
        l3_context: List[Dict[str, Any]],
    ) -> Optional[str]:
        """检测当前信息与 L3 历史是否矛盾"""
        summary_text = summary.get("summary", "").lower()

        for item in l3_context:
            content = item.get("content", "").lower()
            if not content:
                continue

            # 简单矛盾检测：包含相反方向的关键词
            positive_words = {"利好", "上涨", "增长", "盈利", "增持"}
            negative_words = {"利空", "下跌", "亏损", "减持", "风险"}

            has_positive = any(w in summary_text for w in positive_words)
            has_negative_l3 = any(w in content for w in negative_words)
            has_negative = any(w in summary_text for w in negative_words)
            has_positive_l3 = any(w in content for w in positive_words)

            if (has_positive and has_negative_l3) or (has_negative and has_positive_l3):
                return f"当前信息与历史记录存在方向矛盾"

        return None
