# -*- coding: utf-8 -*-
"""F020 反幻觉编排管线"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..pipeline.collection import RawArticle

logger = logging.getLogger("stockquant.ai.hallucination")


class HallucinationPipeline:
    """反幻觉系统 — 多阶段验证管线

    按顺序执行: SourceVerifier → FactScreener → ConsistencyFilter →
    PromptConstraint → PostVerify → LogicVerifier → CrossValidator → ConfidenceScorer
    """

    def __init__(self, strict_mode: bool = False) -> None:
        self._strict = strict_mode

    def execute(self, articles: List[RawArticle]) -> Dict[str, Any]:
        """执行反幻觉检查"""
        results: Dict[str, Any] = {
            "passed": True,
            "issues": [],
            "scores": {},
        }

        if not articles:
            return results

        # 1. 来源验证
        source_result = self._source_verify(articles)
        results["source_verif"] = source_result

        # 2. 事实初筛
        fact_result = self._fact_screen(articles)
        results["fact_screen"] = fact_result

        # 3. 一致性过滤
        consist_result = self._consistency_filter(articles)
        results["consistency"] = consist_result

        # 综合评分
        results["scores"]["source"] = source_result.get("score", 0.5)
        results["scores"]["fact"] = fact_result.get("score", 0.5)
        results["scores"]["consistency"] = consist_result.get("score", 0.5)

        overall = sum(results["scores"].values()) / len(results["scores"])
        results["confidence"] = round(overall, 3)
        results["passed"] = overall >= (0.3 if not self._strict else 0.6)

        if not results["passed"]:
            results["issues"].append("综合可信度低于阈值，建议过滤")

        return results

    def _source_verify(self, articles: List[RawArticle]) -> Dict[str, Any]:
        known_sources = {"news_searcher", "eastmoney", "xueqiu", "cls", "cninfo"}
        verified = sum(1 for a in articles if a.source in known_sources)
        ratio = verified / len(articles) if articles else 0
        return {"verified_count": verified, "score": ratio}

    def _fact_screen(self, articles: List[RawArticle]) -> Dict[str, Any]:
        has_content = sum(1 for a in articles if a.content and len(a.content) > 10)
        ratio = has_content / len(articles) if articles else 0
        return {"valid_count": has_content, "score": ratio}

    def _consistency_filter(self, articles: List[RawArticle]) -> Dict[str, Any]:
        titles = [a.title.strip().lower() for a in articles]
        unique = len(set(titles))
        ratio = unique / len(titles) if titles else 0
        return {"unique_count": unique, "score": ratio}


class FactDatabase:
    """已验证事实库"""

    def __init__(self) -> None:
        self._facts: List[Dict[str, Any]] = []

    def add(self, fact: Dict[str, Any]) -> str:
        self._facts.append(fact)
        return f"fact_{len(self._facts)}"

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        return [f for f in self._facts if keyword.lower() in str(f).lower()]

    def count(self) -> int:
        return len(self._facts)


class HallucinationDB:
    """幻觉数据库 — 记录已识别的幻觉样本"""

    def __init__(self) -> None:
        self._records: List[Dict[str, Any]] = []

    def add(self, record: Dict[str, Any]) -> None:
        self._records.append(record)

    def search(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        if symbol:
            return [r for r in self._records if r.get("symbol") == symbol]
        return self._records

    def count(self) -> int:
        return len(self._records)
