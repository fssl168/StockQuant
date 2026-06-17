# -*- coding: utf-8 -*-
"""F020 信息总结器 — 三源检索 + 提示约束 + LLM 总结 + 多级摘要 + 记忆压缩"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from stockquant.ai.collectors.base import RawInfoItem

logger = logging.getLogger("stockquant.ai.pipeline.summarizer")


class Summarizer:
    """信息总结器

    五步总结:
    1. 三源检索 — L1/L2/L3 记忆检索相关事实
    2. 提示约束注入 — 注入反幻觉约束到 prompt
    3. LLM 总结 — 调用 LLM 生成总结（降级到规则总结）
    4. 多级摘要 — 会话/日/周/月四级摘要
    5. 记忆压缩 — 总结后压缩工作记忆
    """

    # 提示约束模板
    PROMPT_CONSTRAINTS = [
        "仅基于提供的信息进行总结，不得编造数据",
        "如果信息不足，明确标注'信息不足'而非推测",
        "所有数值必须来自原始信息，不得四舍五入或估算",
        "不得包含任何投资建议，如需提及请附免责声明",
    ]

    def __init__(
        self,
        memory_system: Any = None,
        llm_client: Any = None,
    ) -> None:
        self._memory = memory_system
        self._llm = llm_client

    def summarize(self, items: List[RawInfoItem]) -> Dict[str, Any]:
        """执行五步总结"""
        if not items:
            return {
                "summary": "无有效信息",
                "facts": [],
                "confidence": 0.0,
                "level": "session",
            }

        # Step 1: 三源检索
        facts = self._three_source_retrieval(items)

        # Step 2: 提示约束注入
        constrained_items = self._inject_prompt_constraints(items)

        # Step 3: LLM 总结（降级到规则总结）
        summary_text = self._llm_summarize(constrained_items, facts)

        # Step 4: 多级摘要
        level = self._determine_summary_level(items)
        multi_level = self._build_multi_level_summary(summary_text, items, level)

        # Step 5: 记忆压缩
        self._memory_compression(items, summary_text)

        return {
            "summary": summary_text,
            "facts": facts[:20],
            "confidence": self._calculate_confidence(items, facts),
            "level": level,
            "multi_level": multi_level,
            "article_count": len(items),
        }

    def _three_source_retrieval(self, items: List[RawInfoItem]) -> List[Dict[str, Any]]:
        """三源检索 — L1/L2/L3"""
        facts: List[Dict[str, Any]] = []

        if not self._memory:
            return facts

        # L1: 工作记忆
        try:
            symbols = list(set(it.symbol for it in items if it.symbol))
            for sym in symbols[:3]:
                l1_facts = self._memory.search_working(symbol=sym)
                facts.extend([{"source": "L1", "data": f} for f in l1_facts[:5]])
        except Exception as exc:
            logger.warning("L1 检索失败: %s", exc)

        # L2: 短期记忆
        try:
            for sym in symbols[:3]:
                l2_facts = self._memory.search_short_term(symbol=sym, limit=5)
                facts.extend([{"source": "L2", "data": f} for f in l2_facts[:5]])
        except Exception as exc:
            logger.warning("L2 检索失败: %s", exc)

        # L3: 长期记忆
        try:
            for sym in symbols[:3]:
                l3_facts = self._memory.search_long_term(
                    symbol=sym, min_confidence=0.6, limit=5
                )
                facts.extend([{"source": "L3", "data": f} for f in l3_facts[:5]])
        except Exception as exc:
            logger.warning("L3 检索失败: %s", exc)

        return facts

    def _inject_prompt_constraints(self, items: List[RawInfoItem]) -> List[RawInfoItem]:
        """提示约束注入 — 在 item 的 raw 中附加约束标记"""
        for item in items:
            if not hasattr(item, '_constraints'):
                item._constraints = self.PROMPT_CONSTRAINTS  # type: ignore[attr-defined]
        return items

    def _llm_summarize(
        self,
        items: List[RawInfoItem],
        facts: List[Dict[str, Any]],
    ) -> str:
        """LLM 总结 — 降级到规则总结"""
        if self._llm:
            try:
                return self._call_llm(items, facts)
            except Exception as exc:
                logger.warning("LLM 总结失败，降级到规则总结: %s", exc)

        return self._rule_based_summarize(items, facts)

    def _call_llm(self, items: List[RawInfoItem], facts: List[Dict[str, Any]]) -> str:
        """调用 LLM 生成总结"""
        # 构建提示
        constraints_text = "\n".join(f"- {c}" for c in self.PROMPT_CONSTRAINTS)
        items_text = "\n".join(
            f"[{it.source}] {it.title}: {it.content[:200]}" for it in items[:15]
        )
        facts_text = "\n".join(
            f"[{f['source']}] {json.dumps(f['data'], ensure_ascii=False)[:100]}"
            for f in facts[:10]
        )

        prompt = (
            f"请根据以下信息进行总结。\n\n"
            f"约束条件:\n{constraints_text}\n\n"
            f"原始信息:\n{items_text}\n\n"
            f"历史事实:\n{facts_text}\n\n"
            f"总结:"
        )

        result = self._llm.chat(prompt)
        return result if isinstance(result, str) else str(result)

    def _rule_based_summarize(
        self,
        items: List[RawInfoItem],
        facts: List[Dict[str, Any]],
    ) -> str:
        """规则总结（LLM 不可用时的降级方案）"""
        sources = set(it.source for it in items)
        parts = [f"共采集 {len(items)} 条信息，来源：{', '.join(sources)}"]

        by_source: Dict[str, List[RawInfoItem]] = {}
        for it in items:
            by_source.setdefault(it.source, []).append(it)

        for source, group in sorted(by_source.items()):
            parts.append(f"\n[{source}] {len(group)} 条：")
            for g in group[:3]:
                parts.append(f"  - {g.title}")

        if facts:
            parts.append(f"\n历史参考: {len(facts)} 条相关事实")

        return "\n".join(parts[:50])

    def _determine_summary_level(self, items: List[RawInfoItem]) -> str:
        """确定摘要级别 — session/daily/weekly/monthly"""
        if not items:
            return "session"

        timestamps = [it.timestamp for it in items if it.timestamp]
        if not timestamps:
            return "session"

        span = max(timestamps) - min(timestamps)
        if span <= timedelta(hours=4):
            return "session"
        elif span <= timedelta(days=1):
            return "daily"
        elif span <= timedelta(days=7):
            return "weekly"
        else:
            return "monthly"

    def _build_multi_level_summary(
        self,
        summary_text: str,
        items: List[RawInfoItem],
        current_level: str,
    ) -> Dict[str, str]:
        """构建多级摘要"""
        levels = ["session", "daily", "weekly", "monthly"]
        level_idx = levels.index(current_level) if current_level in levels else 0

        result: Dict[str, str] = {}
        # 当前级别使用完整总结
        result[current_level] = summary_text

        # 更高级别使用压缩版本
        for i in range(level_idx + 1, len(levels)):
            higher_level = levels[i]
            # 逐级压缩：取前 3 条核心信息
            core_items = items[:3]
            compressed = "; ".join(f"{it.source}:{it.title[:20]}" for it in core_items)
            result[higher_level] = f"[{higher_level}摘要] {compressed}"

        return result

    def _memory_compression(self, items: List[RawInfoItem], summary: str) -> None:
        """记忆压缩 — 总结后压缩工作记忆"""
        if not self._memory:
            return

        try:
            # 将总结写入 L2 短期记忆
            symbols = list(set(it.symbol for it in items if it.symbol))
            for sym in symbols[:3]:
                self._memory.add_short_term(
                    symbol=sym,
                    content=summary[:500],
                    metadata={"type": "summarized", "item_count": len(items)},
                )
        except Exception as exc:
            logger.warning("记忆压缩失败: %s", exc)

    @staticmethod
    def _calculate_confidence(
        items: List[RawInfoItem],
        facts: List[Dict[str, Any]],
    ) -> float:
        """计算总结置信度"""
        if not items:
            return 0.0

        # 信号 1: 数据量
        volume_score = min(len(items) / 10, 1.0)

        # 信号 2: 内容完整性
        has_content = sum(1 for it in items if it.content and len(it.content) > 20)
        content_score = has_content / len(items)

        # 信号 3: 历史事实支撑
        fact_score = min(len(facts) / 5, 1.0)

        # 信号 4: 来源验证
        verified = sum(1 for it in items if it.verified)
        verify_score = verified / len(items)

        return round(
            (volume_score * 0.2 + content_score * 0.3 + fact_score * 0.3 + verify_score * 0.2),
            3,
        )
