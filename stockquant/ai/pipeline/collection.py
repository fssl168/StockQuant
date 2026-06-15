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

    集成 NewsSearcher + 4 爬虫（东方财富/雪球/财联社/巨潮）
    """

    def __init__(self, max_articles_per_source: int = 20) -> None:
        self._max_articles = max_articles_per_source

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
                        url="",
                        source="news_searcher",
                        published_at=getattr(item, 'published_at', None),
                        raw={"sentiment": item.sentiment, "source": item.source},
                    ))
            return articles
        except ImportError:
            logger.warning("NewsSearcher not available")
            return []

    def _collect_from_source(self, source: str, event: CollectionEvent) -> List[RawArticle]:
        """通过指定爬虫采集"""
        src_map = {
            "eastmoney": EastMoneyScraper,
            "xueqiu": XueQiuScraper,
            "cls": CLSScraper,
            "cninfo": CNInfScraper,
        }
        cls = src_map.get(source)
        if cls is None:
            return []
        try:
            scraper = cls()
            return scraper.scrape(event.symbols)
        except Exception as exc:
            logger.warning("Scraper %s failed: %s", source, exc)
            return []


class EastMoneyScraper:
    """东方财富新闻爬虫"""

    def __init__(self) -> None:
        self.base_url = "https://newsapi.eastmoney.com/kuaixun/"

    def scrape(self, symbols: List[str]) -> List[RawArticle]:
        return []


class XueQiuScraper:
    """雪球社区爬虫"""

    def scrape(self, symbols: List[str]) -> List[RawArticle]:
        return []


class CLSScraper:
    """财联社电报爬虫"""

    def scrape(self, symbols: List[str]) -> List[RawArticle]:
        return []


class CNInfScraper:
    """巨潮资讯爬虫"""

    def scrape(self, symbols: List[str]) -> List[RawArticle]:
        return []
