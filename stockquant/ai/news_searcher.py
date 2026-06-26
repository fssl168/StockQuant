# -*- coding: utf-8 -*-
"""F032 新闻情报搜索器 — 多源新闻搜索 + 情感分析"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """新闻条目"""

    title: str
    source: str
    url: str
    summary: str
    published_at: datetime
    sentiment: float = 0.0  # -1.0 to 1.0

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "summary": self.summary,
            "published_at": self.published_at.isoformat(),
            "sentiment": round(self.sentiment, 4),
        }


class NewsSearcher:
    """多源新闻情报搜索器。

    支持 5 种搜索源：聚合搜索、Bocha、Tavily、Brave、SerpAPI。
    各搜索源为可选依赖，未安装时跳过对应源。

    Parameters
    ----------
    api_keys : dict, optional
        {"tavily": "key", "serpapi": "key", "brave": "key"}
    """

    def __init__(self, api_keys: Optional[Dict[str, str]] = None) -> None:
        self._api_keys = api_keys or {}

    def search(self, symbol: str, query: Optional[str] = None,
               days: int = 7, max_results: int = 20) -> List[NewsItem]:
        """搜索相关新闻。

        按优先级依次尝试各搜索源，直到获得结果。

        Parameters
        ----------
        symbol : str
            股票代码，如 "600519"
        query : str, optional
            自定义搜索关键词
        days : int
            回溯天数
        max_results : int
            最大返回条数

        Returns
        -------
        List[NewsItem]
        """
        search_query = query or self._build_query(symbol)
        cutoff = datetime.now() - timedelta(days=days)

        all_items: List[NewsItem] = []

        # Try each source in priority order
        sources = [
            ("aggregate", self._search_aggregate),
            ("tavily", self._search_tavily),
            ("brave", self._search_brave),
            ("serpapi", self._search_serpapi),
        ]

        for source_name, search_fn in sources:
            try:
                items = search_fn(search_query, cutoff, max_results)
                if items:
                    logger.info(f"NewsSearcher: got {len(items)} items from {source_name}")
                    all_items.extend(items)
                    if len(all_items) >= max_results:
                        break
            except ImportError:
                logger.debug(f"NewsSearcher: {source_name} not available")
            except Exception:
                logger.exception(f"NewsSearcher: {source_name} search failed")

        # Deduplicate by URL
        seen_urls: set = set()
        unique_items: List[NewsItem] = []
        for item in all_items:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_items.append(item)
                if len(unique_items) >= max_results:
                    break

        return unique_items

    def _build_query(self, symbol: str) -> str:
        """构建搜索关键词"""
        # 简单映射：600519 -> 贵州茅台
        symbol_mapping = {
            "600519": "贵州茅台",
            "000858": "五粮液",
            "600036": "招商银行",
            "000333": "美的集团",
            "601318": "中国平安",
            "300750": "宁德时代",
            "000001": "平安银行",
            "600276": "恒瑞医药",
        }
        cn_name = symbol_mapping.get(symbol, symbol)
        return f"{cn_name} 股票 新闻"

    def _search_aggregate(self, query: str, cutoff: datetime,
                          max_results: int) -> List[NewsItem]:
        """聚合搜索（使用 requests 抓取财经网站 RSS/页面）。

        尝试从主流财经网站获取数据，失败时返回空列表。
        """
        items: List[NewsItem] = []

        # 尝试新浪财经 RSS
        try:
            items = self._fetch_sina_rss(query, cutoff, max_results)
        except Exception:
            pass

        # 尝试东方财富
        if not items:
            try:
                items = self._fetch_eastmoney(query, cutoff, max_results)
            except Exception:
                pass

        # Fallback: no data available
        if not items:
            logger.debug("NewsSearcher: no news data available from any source")

        # Apply sentiment analysis
        for item in items:
            item.sentiment = self.analyze_sentiment(f"{item.title} {item.summary}")

        return items[:max_results]

    def _fetch_sina_rss(self, query: str, cutoff: datetime,
                        max_results: int) -> List[NewsItem]:
        """从新浪财经获取新闻"""
        items: List[NewsItem] = []
        try:
            # 新浪财经新闻搜索
            url = "https://search.sinaapi.com/news.php"
            params = {
                "q": query,
                "page": 1,
                "pageSize": min(max_results, 20),
                "sort": "createtime",
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            for row in data.get("result", {}).get("doc", [])[:max_results]:
                pub_time = self._parse_time(row.get("date", ""))
                if pub_time and pub_time >= cutoff:
                    items.append(NewsItem(
                        title=row.get("title", ""),
                        source="新浪财经",
                        url=row.get("url", ""),
                        summary=row.get("intro", "")[:200],
                        published_at=pub_time,
                    ))
        except Exception:
            logger.debug("NewsSearcher: sina RSS fetch failed")
        return items

    def _fetch_eastmoney(self, query: str, cutoff: datetime,
                         max_results: int) -> List[NewsItem]:
        """从东方财富获取新闻"""
        items: List[NewsItem] = []
        try:
            url = "https://searchapi.eastmoney.com/api/suggest/get.do"
            params = {
                "inputtype": "json",
                "type": "14",
                "token": "EQALLv1S",
                "journalism": "1",
                "query": query,
                "page": 1,
                "pageSize": min(max_results, 20),
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            for row in data.get("query", {}).get("journalism", [])[:max_results]:
                pub_str = row.get("publishTime", "")
                pub_time = self._parse_time(pub_str)
                if pub_time and pub_time >= cutoff:
                    items.append(NewsItem(
                        title=row.get("title", ""),
                        source="东方财富",
                        url=row.get("url", ""),
                        summary=row.get("content", "")[:200],
                        published_at=pub_time,
                    ))
        except Exception:
            logger.debug("NewsSearcher: eastmoney fetch failed")
        return items

    def _search_tavily(self, query: str, cutoff: datetime,
                       max_results: int) -> List[NewsItem]:
        """Tavily 搜索（需要 API key）"""
        api_key = self._api_keys.get("tavily")
        if not api_key:
            raise ImportError("Tavily API key not configured")

        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "days": 7,
                "max_results": max_results,
                "include_answer": True,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        items = []
        for row in data.get("results", [])[:max_results]:
            pub_str = row.get("published_date", "")
            items.append(NewsItem(
                title=row.get("title", ""),
                source="Tavily",
                url=row.get("url", ""),
                summary=row.get("content", "")[:200],
                published_at=self._parse_time(pub_str) or datetime.now(),
            ))
        return items

    def _search_brave(self, query: str, cutoff: datetime,
                      max_results: int) -> List[NewsItem]:
        """Brave 搜索（需要 API key）"""
        api_key = self._api_keys.get("brave")
        if not api_key:
            raise ImportError("Brave API key not configured")

        resp = requests.get(
            "https://api.search.brave.com/res/v1/news/search",
            params={"q": query, "freshness": "pd7", "count": max_results},
            headers={"X-Subscription-Token": api_key},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        items = []
        for row in data.get("results", [])[:max_results]:
            items.append(NewsItem(
                title=row.get("title", ""),
                source="Brave",
                url=row.get("url", ""),
                summary=row.get("description", "")[:200],
                published_at=self._parse_time(row.get("extra_info", {}).get("age", "")) or datetime.now(),
            ))
        return items

    def _search_serpapi(self, query: str, cutoff: datetime,
                        max_results: int) -> List[NewsItem]:
        """SerpAPI 搜索（需要 API key）"""
        api_key = self._api_keys.get("serpapi")
        if not api_key:
            raise ImportError("SerpAPI API key not configured")

        resp = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_news",
                "q": query,
                "api_key": api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        items = []
        for row in data.get("news_results", [])[:max_results]:
            items.append(NewsItem(
                title=row.get("title", ""),
                source=row.get("source", "SerpAPI"),
                url=row.get("link", ""),
                summary=row.get("snippet", "")[:200],
                published_at=self._parse_time(row.get("date", "")) or datetime.now(),
            ))
        return items

    @staticmethod
    def _parse_time(time_str: str) -> Optional[datetime]:
        """解析各种时间格式"""
        if not time_str:
            return None

        # Try multiple formats
        for fmt in [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y年%m月%d日",
            "%Y/%m/%d",
        ]:
            try:
                dt = datetime.strptime(time_str.strip(), fmt)
                if dt.year < 2000:
                    dt = dt.replace(year=2024)
                return dt
            except ValueError:
                continue

        # Handle relative time like "2小时前"
        if "小时前" in time_str:
            match = re.search(r"(\d+)", time_str)
            if match:
                hours = int(match.group(1))
                return datetime.now() - timedelta(hours=hours)

        return None

    def analyze_sentiment(self, text: str) -> float:
        """基于关键词词典的简单情感分析。

        Parameters
        ----------
        text : str
            待分析文本（中文）

        Returns
        -------
        float
            情感分数，范围 [-1.0, 1.0]
        """
        positive_words = ["利好", "上涨", "增长", "突破", "盈利", "扩张",
                          "走强", "反弹", "新高", "放量", "看好", "受益"]
        negative_words = ["利空", "下跌", "亏损", "暴跌", "监管", "调查",
                          "走弱", "回调", "新低", "缩量", "看空", "受损"]

        pos_count = sum(1 for w in positive_words if w in text)
        neg_count = sum(1 for w in negative_words if w in text)

        total = pos_count + neg_count
        if total == 0:
            return 0.0
        return round((pos_count - neg_count) / total, 4)
