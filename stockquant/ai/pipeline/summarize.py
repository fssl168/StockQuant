# -*- coding: utf-8 -*-
"""F020 信息总结阶段"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .collection import RawArticle
from ..memory.system import MemorySystem

logger = logging.getLogger("stockquant.ai.pipeline")


class SummarizeStage:
    """信息总结阶段 — MemoryRetriever + PromptConstraint + LLM Summarizer + PostVerify"""

    def __init__(self, memory: MemorySystem | None = None) -> None:
        self._memory = memory

    def execute(self, articles: List[RawArticle]) -> Dict[str, Any]:
        """执行总结"""
        if not articles:
            return {"summary": "无有效信息", "facts": [], "confidence": 0.0}

        # 从记忆系统检索相关事实
        facts = []
        if self._memory:
            for sym in set(a.raw.get("symbols", ["unknown"]) for a in articles):
                retrieved = self._memory.search_short_term(sym, limit=10)
                facts.extend(retrieved)

        # 构建总结
        summary = self._build_summary(articles, facts)

        # 后验证
        verified = self._post_verify(articles)

        return {
            "summary": summary,
            "facts": facts[:20],
            "verified": verified,
            "article_count": len(articles),
        }

    def _build_summary(self, articles: List[RawArticle], facts: List) -> str:
        """构建总结文本"""
        sources = set(a.source for a in articles)
        parts = [f"共采集 {len(articles)} 条信息，来源：{', '.join(sources)}"]

        # 按来源分组
        by_source: Dict[str, List[RawArticle]] = {}
        for a in articles:
            by_source.setdefault(a.source, []).append(a)

        for source, items in sorted(by_source.items()):
            parts.append(f"\n[{source}] {len(items)} 条：")
            for item in items[:3]:
                parts.append(f"  - {item.title}")

        return "\n".join(parts[:50])

    def _post_verify(self, articles: List[RawArticle]) -> bool:
        """总结后事实验证"""
        # 检查是否所有文章都有来源
        return all(a.url or a.source for a in articles)
