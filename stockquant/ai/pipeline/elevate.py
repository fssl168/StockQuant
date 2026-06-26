# -*- coding: utf-8 -*-
"""F020 信息升华阶段 — 5 步完整化（B5.3）

合并旧版 DEPRECATED `elevator.py` 的 L3 检索 + 推理链验证 + 交叉验证能力：

Step 1: l3_retrieval            — 从 L3 检索历史相似情境（RecallScorer 多因子召回）
Step 2: multi_source_fusion     — 多源融合（4 级置信度，保留）
Step 3: reasoning_chain_verify   — 原子声明分解 + 类型路由（数值/时序/实体/比较/监管/计算）
Step 4: cross_validation        — 多源交叉验证关键声明
Step 5: l3_writeback            — 写入 L3 长期记忆 + 触发 WorkingMemory.reflect()

设计原则：
- 完全向后兼容：`ElevateStage().execute(summary)` 接口不变
- 渐进增强：传入 memory_system 才启用 L3 检索 + 回写
- 不引入新依赖
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..memory.system import MemorySystem

logger = logging.getLogger("stockquant.ai.pipeline.elevate")


# ─── FINGROUND 六类原子声明分类（Phase E 预留接口） ────────────────────
CLAIM_TYPES = ["numeric", "temporal", "entity", "comparative", "regulatory", "computed"]


class ElevateStage:
    """信息升华阶段 — 5 步完整化

    Step 1: l3_retrieval            L3 多因子召回历史相似情境
    Step 2: multi_source_fusion     多源融合（4 级置信度）
    Step 3: reasoning_chain_verify   原子声明分解 + 类型路由验证
    Step 4: cross_validation        多源交叉验证
    Step 5: l3_writeback            写入 L3 + 触发 Reflection

    用法（向后兼容）：
        stage = ElevateStage()
        result = stage.execute(summary)

    用法（启用 L3 + Reflection）：
        stage = ElevateStage(memory=mem)
        result = stage.execute(summary)
    """

    def __init__(
        self,
        memory: Any = None,
        hallucination_pipeline: Any = None,
    ) -> None:
        """
        Args:
            memory: MemorySystem 实例（用于检索 + 回写）
            hallucination_pipeline: 反幻觉管线（保留接口，可选）
        """
        self._memory = memory
        self._hallucination = hallucination_pipeline

    def execute(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """执行 5 步升华"""
        if not summary or summary.get("article_count", 0) == 0:
            return {
                "insights": [],
                "summary": summary.get("summary", ""),
                "elevated": False,
                "overall_confidence": 0.0,
                "source_count": 0,
            }

        # Step 1: L3 多因子检索（新增）
        l3_context = self._l3_retrieval(summary)
        logger.debug("Step 1 l3_retrieval: %d contexts", len(l3_context))

        # Step 2: 多源融合（保留 + 增强）
        fused = self._multi_source_fusion(summary, l3_context)
        logger.debug("Step 2 multi_source_fusion: %d insights", len(fused.get("insights", [])))

        # Step 3: 推理链验证（新增）
        verified = self._reasoning_chain_verify(fused)
        logger.debug("Step 3 reasoning_chain_verify: %d verified", len(verified.get("insights", [])))

        # Step 4: 交叉验证（新增）
        cross_validated = self._cross_validation(verified, l3_context)
        logger.debug("Step 4 cross_validation: %d insights", len(cross_validated.get("insights", [])))

        # Step 5: L3 回写 + Reflection 触发（新增）
        self._l3_writeback(cross_validated, summary)
        logger.debug("Step 5 l3_writeback: done")

        # 计算综合置信度
        insights = cross_validated.get("insights", [])
        overall_confidence = (
            max((i.get("confidence", 0.0) for i in insights), default=0.0)
            if insights else 0.0
        )

        return {
            "insights": insights,
            "summary": summary.get("summary", ""),
            "overall_confidence": round(overall_confidence, 3),
            "source_count": cross_validated.get("source_count", 0),
            "l3_context_count": len(l3_context),
            "elevated": True,
            "reflection_triggered": cross_validated.get("reflection_triggered", False),
        }

    # ─── Step 1: L3 多因子检索 ──────────────────────────────────────────
    def _l3_retrieval(self, summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Step 1 — 从 L3 检索历史相似情境（用 RecallScorer 多因子召回）

        借鉴 FinMem 论文 §3.3 的多因子召回机制：
        - 按 summary 关键词检索 L3
        - 按 facts 中的 symbol 检索 L3
        - 使用 search_by_layer("all") 跨层检索
        """
        if self._memory is None:
            return []

        results: List[Dict[str, Any]] = []

        try:
            # 基于 summary 文本检索（跨层）
            summary_text = summary.get("summary", "")
            if summary_text:
                # B3 已实现 search_by_layer("all")，使用 RecallScorer 跨层排序
                if hasattr(self._memory, "search_by_layer"):
                    l3_items = self._memory.search_by_layer(
                        query=summary_text[:100],
                        layer="all",
                        top_k=10,
                    )
                    results.extend(l3_items)
                else:
                    # 降级：直接 search_long_term
                    l3_items = self._memory.search_long_term(
                        keyword=summary_text[:50], limit=10
                    )
                    results.extend(l3_items)

            # 基于 facts 中的 symbol 检索
            facts = summary.get("facts", [])
            for fact in facts[:3]:
                fact_data = fact.get("data", {})
                if isinstance(fact_data, dict):
                    symbol = fact_data.get("symbol", "")
                    if symbol:
                        items = self._memory.search_long_term(
                            symbol=symbol, limit=5
                        )
                        results.extend(items)
        except Exception as exc:
            logger.warning("L3 检索失败: %s", exc)

        # 去重
        seen_ids = set()
        deduped: List[Dict[str, Any]] = []
        for r in results:
            rid = r.get("id") or r.get("content", "")[:50]
            if rid and rid not in seen_ids:
                seen_ids.add(rid)
                deduped.append(r)
        return deduped[:20]

    # ─── Step 2: 多源融合 ───────────────────────────────────────────────
    def _multi_source_fusion(
        self,
        summary: Dict[str, Any],
        l3_context: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Step 2 — 多源融合 + 4 级置信度（保留 + 增强）

        source_count 0-4:
        - 来源验证（verified=True）
        - 历史事实支撑（len(facts) > 3）
        - 信息量充足（article_count > 2）
        - 总结置信度高（summary.confidence > 0.5）
        """
        insights: List[Dict[str, Any]] = []

        verified = summary.get("verified", False)
        article_count = summary.get("article_count", 0)
        facts = summary.get("facts", [])
        summary_confidence = summary.get("confidence", 0.0)
        trend = summary.get("trend", "unknown")

        # 多源 4 级置信度
        source_count = sum([
            bool(verified),
            len(facts) > 3,
            article_count > 2,
            summary_confidence > 0.5,
        ])

        # 趋势确认洞察（多源 ≥2）
        if verified and article_count > 2 and source_count >= 2:
            confidence = min(0.95, 0.5 + source_count * 0.125)
            insights.append({
                "type": "confirmed_trend",
                "confidence": round(confidence, 3),
                "description": (
                    f"基于 {article_count} 条信息的多源融合确认"
                    f"（{source_count}/4 个来源一致，趋势：{trend}）"
                ),
                "source_count": source_count,
                "trend": trend,
                "reasoning_chain": [
                    f"信息来源验证: {'通过' if verified else '未通过'}",
                    f"事实支撑: {len(facts)} 条",
                    f"信息量: {article_count} 条",
                    f"总结置信度: {summary_confidence:.2f}",
                ],
            })

        # 高置信度洞察（多源 ≥3）
        if source_count >= 3:
            insights.append({
                "type": "high_confidence_insight",
                "confidence": round(min(0.9, 0.7 + source_count * 0.05), 3),
                "description": f"高置信度洞察：{source_count} 个独立来源一致，建议重点关注",
                "source_count": source_count,
                "trend": trend,
            })

        # 历史上下文洞察
        if l3_context:
            avg_l3_conf = sum(
                float(it.get("confidence", 0.5) or 0.5)
                for it in l3_context
            ) / len(l3_context)
            insights.append({
                "type": "historical_context",
                "confidence": round(min(avg_l3_conf * 0.8, 0.85), 3),
                "description": f"L3 长期记忆提供 {len(l3_context)} 条相关历史上下文",
                "count": len(l3_context),
                "source_count": source_count,
            })

        # 矛盾检测
        contradiction = self._detect_contradiction(summary, l3_context)
        if contradiction:
            insights.append({
                "type": "contradiction_alert",
                "confidence": 0.9,
                "description": contradiction,
                "sources": "current+L3",
            })

        # 新发现
        if not l3_context and article_count > 0:
            insights.append({
                "type": "new_finding",
                "confidence": round(summary_confidence * 0.7, 3),
                "description": "无历史记录的新发现",
                "sources": "current",
            })

        return {
            "insights": insights,
            "confidence": summary_confidence,
            "l3_count": len(l3_context),
            "source_count": source_count,
        }

    # ─── Step 3: 推理链验证 ────────────────────────────────────────────
    def _reasoning_chain_verify(self, fused: Dict[str, Any]) -> Dict[str, Any]:
        """Step 3 — 推理链验证 + 原子声明分解（借鉴 FINGROUND）

        - 检查每条 insight 的推理链完整性（type/confidence/description）
        - 对 description 做原子声明分解，按类型路由标记
        - 推理链不完整 → 降权
        """
        insights = fused.get("insights", [])

        verified_insights: List[Dict[str, Any]] = []
        for insight in insights:
            # 检查推理链完整性
            has_type = bool(insight.get("type"))
            has_confidence = "confidence" in insight
            has_description = bool(insight.get("description"))
            has_chain = bool(insight.get("reasoning_chain"))

            if has_type and has_confidence and has_description:
                # 推理链完整，标记为 verified
                insight["reasoning_verified"] = True
                if not has_chain:
                    # 补充基础推理链
                    insight["reasoning_chain"] = [
                        f"type: {insight['type']}",
                        f"confidence: {insight.get('confidence', 0.5)}",
                        f"description: {insight.get('description', '')[:50]}",
                    ]
            else:
                # 推理链不完整，降权
                insight["confidence"] = insight.get("confidence", 0.5) * 0.5
                insight["reasoning_verified"] = False

            # 原子声明分解 + 类型路由
            description = insight.get("description", "")
            if description:
                claims = self._decompose_claims(description)
                insight["claims"] = claims
                # 标记声明类型
                insight["claim_types"] = list(set(c["type"] for c in claims))

            verified_insights.append(insight)

        fused["insights"] = verified_insights
        return fused

    def _decompose_claims(self, text: str) -> List[Dict[str, str]]:
        """原子声明分解 — 简化版（完整实现在 Phase E）

        将文本按句号/分号/逗号切分为原子声明，按类型路由：
        - numeric: 包含数字/百分比
        - temporal: 包含日期/时间
        - entity: 包含公司名/股票代码
        - comparative: 包含比较词（高于/低于/超过）
        - regulatory: 包含监管/政策词
        - computed: 包含计算词（同比/环比/增长率）
        """
        if not text:
            return []

        # 按句号、分号、问号切分
        import re
        sentences = re.split(r'[。.;；?？!！]', text)
        sentences = [s.strip() for s in sentences if s and len(s.strip()) > 3]

        claims: List[Dict[str, str]] = []
        for sent in sentences:
            claim_type = self._classify_claim(sent)
            claims.append({
                "text": sent,
                "type": claim_type,
            })
        return claims[:10]  # 限制最多 10 条

    @staticmethod
    def _classify_claim(text: str) -> str:
        """声明类型路由（Phase E 完整实现预留接口）

        优先级顺序（前序类型不能被后序覆盖）：
        - temporal: 含日期 → 时间性声明
        - computed: 含「同比/环比/增长率/增速」+ 数字 → 计算类声明
        - comparative: 比较词（高于/低于/超过/不及） → 比较类
        - numeric: 含数字 + 百分比/亿/万 → 数值类
        - regulatory: 监管/政策类
        - entity: 公司名/股票代码
        - 默认: entity
        """
        import re
        # temporal: 含日期（优先于其他含数字类型）
        if re.search(r'\d{4}年|\d{1,2}月|\d{1,2}日|季度|年度|Q[1-4]', text):
            return "temporal"
        # computed: 同比/环比等增长类（含数字时优先于 numeric）
        if any(w in text for w in ["同比", "环比", "增长率", "增速"]):
            if any(c.isdigit() for c in text):
                return "computed"
        # comparative: 比较词
        if any(w in text for w in ["高于", "低于", "超过", "不及", "对比"]):
            return "comparative"
        # numeric: 含数字/百分比
        if any(c.isdigit() for c in text) and ("%" in text or "亿" in text or "万" in text):
            return "numeric"
        # regulatory: 监管/政策
        if any(w in text for w in ["监管", "证监会", "政策", "处罚", "公告", "披露"]):
            return "regulatory"
        # entity: 公司名/股票代码
        if re.search(r'[A-Za-z]\d{6}|sh\d{6}|sz\d{6}|公司|集团', text):
            return "entity"
        # 默认
        return "entity"

    # ─── Step 4: 交叉验证 ───────────────────────────────────────────────
    def _cross_validation(
        self,
        fused: Dict[str, Any],
        l3_context: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Step 4 — 多源交叉验证关键声明

        - confirmed_trend: 需要 L3 支撑才能 cross_validated=True
        - contradiction_alert: 天然 cross_validated=True
        - new_finding: 无法交叉验证，降低置信度
        - historical_context: 与 L3 交叉
        """
        insights = fused.get("insights", [])

        for insight in insights:
            insight_type = insight.get("type", "")

            if insight_type == "confirmed_trend":
                # 趋势确认需要 L3 支撑
                if l3_context:
                    insight["cross_validated"] = True
                    insight["confidence"] = min(
                        float(insight.get("confidence", 0.5)) + 0.1, 1.0
                    )
                else:
                    insight["cross_validated"] = False
                    insight["confidence"] = float(insight.get("confidence", 0.5)) * 0.8

            elif insight_type == "contradiction_alert":
                # 矛盾检测天然需要交叉验证
                insight["cross_validated"] = True

            elif insight_type == "new_finding":
                # 新发现无法交叉验证，降低置信度
                insight["cross_validated"] = False
                insight["confidence"] = float(insight.get("confidence", 0.5)) * 0.6

            elif insight_type == "historical_context":
                # 历史上下文与 L3 交叉
                insight["cross_validated"] = bool(l3_context)

            elif insight_type == "high_confidence_insight":
                # 高置信度洞察需要多源
                insight["cross_validated"] = insight.get("source_count", 0) >= 3

            else:
                insight["cross_validated"] = False

        # 过滤掉推理链不通过且低置信度的洞察
        filtered = [
            i for i in insights
            if i.get("reasoning_verified", False)
            or float(i.get("confidence", 0.0)) >= 0.5
        ]
        fused["insights"] = filtered

        # 计算综合置信度
        if filtered:
            avg_conf = sum(
                float(i.get("confidence", 0.0)) for i in filtered
            ) / len(filtered)
            fused["confidence"] = round(avg_conf, 3)

        return fused

    # ─── Step 5: L3 回写 + Reflection 触发 ─────────────────────────────
    def _l3_writeback(
        self,
        result: Dict[str, Any],
        summary: Dict[str, Any],
    ) -> None:
        """Step 5 — 写入 L3 长期记忆 + 触发 WorkingMemory.reflect() 写入 L3-Deep

        - 仅写入 cross_validated=True 且 confidence≥0.5 的洞察
        - 触发 WorkingMemory.reflect() 生成阶段反思，写入 L3-Deep
        """
        if self._memory is None:
            return

        insights = result.get("insights", [])
        written_count = 0
        for insight in insights:
            confidence = float(insight.get("confidence", 0.0))
            cross_validated = insight.get("cross_validated", False)
            if confidence >= 0.5 and cross_validated:
                try:
                    self._memory.add_long_term({
                        "user_id": getattr(self._memory.l3, "_user_id", "test_user"),
                        "content": insight.get("description", ""),
                        "summary": insight.get("description", "")[:200],
                        "metadata": {
                            "type": insight.get("type", "insight"),
                            "claims": insight.get("claims", []),
                            "claim_types": insight.get("claim_types", []),
                            "source_count": insight.get("source_count", 0),
                            "trend": insight.get("trend", "unknown"),
                            "cross_validated": cross_validated,
                            "reasoning_verified": insight.get("reasoning_verified", False),
                        },
                        "tier": "intermediate",  # 洞察存入中层
                        "period_type": "ad_hoc",
                        "importance_score": confidence,  # 重要性 = 置信度
                        "timestamp": datetime.now().isoformat(),
                        "confidence": confidence,
                    })
                    written_count += 1
                except Exception as exc:
                    logger.warning("L3 存储失败: %s", exc)

        # 触发 WorkingMemory.reflect() 写入 L3-Deep
        # WorkingMemory.reflect(l3_store=None, symbol=None) 会生成反思并写入 L3-Deep
        reflection_triggered = False
        if written_count > 0 and hasattr(self._memory, "l1"):
            try:
                wm = self._memory.l1
                if hasattr(wm, "reflect"):
                    # 从 summary 提取 symbol
                    symbol = None
                    facts = summary.get("facts", [])
                    for fact in facts[:1]:
                        fact_data = fact.get("data", {}) if isinstance(fact, dict) else {}
                        if isinstance(fact_data, dict):
                            symbol = fact_data.get("symbol")
                            if symbol:
                                break
                    # 触发反思
                    wm.reflect(
                        l3_store=getattr(self._memory, "l3", None),
                        symbol=symbol,
                    )
                    reflection_triggered = True
            except Exception as exc:
                logger.warning("WorkingMemory.reflect() 触发失败: %s", exc)

        result["reflection_triggered"] = reflection_triggered
        result["l3_written_count"] = written_count

    # ─── 矛盾检测 ──────────────────────────────────────────────────────
    @staticmethod
    def _detect_contradiction(
        summary: Dict[str, Any],
        l3_context: List[Dict[str, Any]],
    ) -> Optional[str]:
        """检测当前信息与 L3 历史是否矛盾"""
        summary_text = (summary.get("summary", "") or "").lower()
        if not summary_text:
            return None

        positive_words = {"利好", "上涨", "增长", "盈利", "增持"}
        negative_words = {"利空", "下跌", "亏损", "减持", "风险"}

        for item in l3_context:
            content = (item.get("content", "") or "").lower()
            if not content:
                continue

            has_positive = any(w in summary_text for w in positive_words)
            has_negative_l3 = any(w in content for w in negative_words)
            has_negative = any(w in summary_text for w in negative_words)
            has_positive_l3 = any(w in content for w in positive_words)

            if (has_positive and has_negative_l3) or (has_negative and has_positive_l3):
                return "当前信息与历史记录存在方向矛盾"

        return None


# ─── 工厂函数 ─────────────────────────────────────────────────────────
def make_elevate_stage(
    memory: Any = None,
    hallucination_pipeline: Any = None,
) -> ElevateStage:
    """构造 ElevateStage — 便捷工厂"""
    return ElevateStage(
        memory=memory,
        hallucination_pipeline=hallucination_pipeline,
    )
