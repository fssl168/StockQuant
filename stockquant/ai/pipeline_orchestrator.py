# -*- coding: utf-8 -*-
"""F020 信息处理流程编排器"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .pipeline.collection import CollectionEvent, CollectionStage
from .pipeline.denoise import DenoiseStage
from .pipeline.summarize import SummarizeStage
from .pipeline.elevate import ElevateStage
from .memory.system import MemorySystem
from .hallucination.pipeline import HallucinationPipeline

logger = logging.getLogger("stockquant.ai.pipeline")


class InformationProcessingPipeline:
    """信息处理全流程编排器

    CollectionStage → DenoiseStage → SummarizeStage → ElevateStage
    全程注入反幻觉检查和记忆系统
    """

    def __init__(
        self,
        memory: Optional[MemorySystem] = None,
        strict_mode: bool = False,
    ) -> None:
        self._collection = CollectionStage()
        self._denoise = DenoiseStage()
        self._summarize = SummarizeStage(memory=memory)
        self._elevate = ElevateStage(memory=memory)
        self._hallucination = HallucinationPipeline(strict_mode=strict_mode)
        self._memory = memory

    def run(
        self,
        symbols: List[str],
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """运行完整信息处理流程"""
        event = CollectionEvent(symbols=symbols, sources=sources or ["news_searcher"])

        # Phase 1: 采集
        raw_articles = self._collection.execute(event)
        logger.info("Collected %d raw articles", len(raw_articles))

        # 反幻觉检查
        h_results = self._hallucination.execute(raw_articles)
        if not h_results["passed"]:
            logger.warning("Hallucination check failed: %s", h_results["issues"])

        # Phase 2: 降噪
        filtered = self._denoise.execute(raw_articles)
        logger.info("After denoise: %d articles", len(filtered))

        # 写入 L2 记忆
        if self._memory:
            for a in filtered[:50]:
                self._memory.add_short_term(
                    symbol=symbols[0] if symbols else "unknown",
                    content=f"{a.title}: {a.content[:100]}",
                    metadata={"source": a.source, "url": a.url},
                )

        # Phase 3: 总结
        summary = self._summarize.execute(filtered)
        logger.info("Summary generated, verified=%s", summary.get("verified"))

        # Phase 4: 升华
        elevated = self._elevate.execute(summary)

        # 写入 L3 记忆
        if self._memory:
            for insight in elevated.get("insights", []):
                self._memory.add_long_term({
                    "symbol": symbols[0] if symbols else "unknown",
                    "insight": insight,
                    "timestamp": datetime.now().isoformat(),
                })

        return {
            "articles_processed": len(raw_articles),
            "filtered_count": len(filtered),
            "summary": summary,
            "insights": elevated.get("insights", []),
            "hallucination_check": h_results,
        }

    def run_single_symbol(self, symbol: str, sources: Optional[List[str]] = None) -> Dict[str, Any]:
        """处理单个标的"""
        return self.run([symbol], sources)
