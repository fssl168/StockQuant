# -*- coding: utf-8 -*-
"""F020 信息降噪阶段"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List

from .collection import RawArticle

logger = logging.getLogger("stockquant.ai.pipeline")


class DenoiseStage:
    """信息降噪阶段 — SourceRanker + TemporalFilter + ConsistencyFilter + Compressor"""

    def __init__(
        self,
        max_articles: int = 30,
        max_age_hours: int = 24,
    ) -> None:
        self._max = max_articles
        self._max_age = timedelta(hours=max_age_hours)

    def execute(self, articles: List[RawArticle]) -> List[RawArticle]:
        """执行降噪"""
        if not articles:
            return []

        # 1. 时效性降权
        articles = self._temporal_filter(articles)

        # 2. 语义去重
        articles = self._deduplicate(articles)

        # 3. 按来源信用度排序，取 top N
        articles = self._source_rank(articles)

        return articles[:self._max]

    def _temporal_filter(self, articles: List[RawArticle]) -> List[RawArticle]:
        """过滤超过时效的文章"""
        cutoff = datetime.now() - self._max_age
        return [a for a in articles if a.published_at is None or a.published_at >= cutoff]

    def _deduplicate(self, articles: List[RawArticle]) -> List[RawArticle]:
        """语义去重 — 基于 Jaccard 词集合重叠率（≥60% 视为重复）"""
        seen: List[RawArticle] = []
        for a in articles:
            title_words = set(a.title.lower().split())
            if not title_words:
                seen.append(a)
                continue
            is_dup = False
            for existing in seen:
                exist_words = set(existing.title.lower().split())
                if not exist_words:
                    continue
                overlap = len(title_words & exist_words)
                min_len = min(len(title_words), len(exist_words))
                if min_len > 0 and overlap / min_len >= 0.6:
                    is_dup = True
                    break
            if not is_dup:
                seen.append(a)
        return seen

    def _source_rank(self, articles: List[RawArticle]) -> List[RawArticle]:
        """按来源信用度排序"""
        score_map = {
            "cninfo": 1.0,
            "cls": 0.9,
            "eastmoney": 0.8,
            "xueqiu": 0.6,
            "news_searcher": 0.7,
        }
        return sorted(articles, key=lambda a: score_map.get(a.source, 0.5), reverse=True)
