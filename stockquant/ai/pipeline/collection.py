# -*- coding: utf-8 -*-
"""F020 信息采集阶段"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.pipeline")


@dataclass
class RawArticle:
    """原始采集文章"""
    title: str
    content: str
    url: str
    source: str
    published_at: Optional[datetime] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectionEvent:
    """采集事件"""
    symbols: List[str]
    sources: List[str] = field(default_factory=list)
    since: Optional[datetime] = None


class CollectionStage:
    """信息采集阶段 — 多渠道采集新闻和市场信息

    集成 NewsCollector (AlphaFeed/AkShare/直连API) + NewsSearcher
    """

    def __init__(self, max_articles_per_source: int = 20) -> None:
        self._max_articles = max_articles_per_source
        self._news_collector = None

    def _get_news_collector(self):
        """获取新闻采集器单例"""
        if self._news_collector is None:
            try:
                from stockquant.ai.collectors.news_collector import NewsCollector
                self._news_collector = NewsCollector()
            except ImportError as e:
                logger.warning("NewsCollector not available: %s", e)
        return self._news_collector

    def execute(self, event: CollectionEvent) -> List[RawArticle]:
        """执行采集"""
        articles: List[RawArticle] = []
        for src in event.sources or ["news_searcher"]:
            try:
                if src == "news_searcher":
                    articles.extend(self._collect_from_news(event.symbols))
                else:
                    articles.extend(self._collect_from_source(src, event))
            except Exception as exc:
                logger.warning("Collection failed for source %s: %s", src, exc)
        return articles[:self._max_articles * 10]

    def _collect_from_news(self, symbols: List[str]) -> List[RawArticle]:
        """通过 NewsSearcher 采集"""
        try:
            from stockquant.ai.news_searcher import NewsSearcher
            searcher = NewsSearcher()
            articles = []
            for sym in symbols:
                items = searcher.search(sym, days=3)
                for item in items[:5]:
                    articles.append(RawArticle(
                        title=item.title,
                        content=item.summary,
                        url=item.url,
                        source=item.source,
                        published_at=item.published_at,
                        raw={"sentiment": item.sentiment},
                    ))
            return articles
        except ImportError:
            logger.warning("NewsSearcher not available")
            return []

    def _collect_from_source(self, source: str, event: CollectionEvent) -> List[RawArticle]:
        """通过 NewsCollector 采集多源新闻"""
        collector = self._get_news_collector()
        if collector is None:
            logger.warning("NewsCollector not available, falling back to NewsSearcher")
            return self._collect_from_news(event.symbols)
        
        articles: List[RawArticle] = []
        for symbol in event.symbols:
            try:
                # 同步调用异步采集器
                import asyncio
                items = asyncio.run(collector.collect(symbol, self._max_articles))
                for item in items:
                    articles.append(RawArticle(
                        title=item.title,
                        content=item.content or "",
                        url=item.url or "",
                        source=item.source,
                        published_at=item.timestamp if hasattr(item, 'timestamp') else None,
                        raw={"sentiment": item.sentiment_score, "symbol": item.symbol},
                    ))
            except Exception as exc:
                logger.warning("Collection failed for source %s, symbol %s: %s", source, symbol, exc)
        
        return articles
