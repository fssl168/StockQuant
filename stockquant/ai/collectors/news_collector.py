# -*- coding: utf-8 -*-
"""新闻采集器 — AlphaFeed 优先 / AkShare 降级"""
from __future__ import annotations

import logging
import os
from typing import Dict, List

from .base import BaseCollector, RawInfoItem

logger = logging.getLogger("stockquant.ai.collectors.news")

# AlphaFeed SDK 可选导入
_ALPHAFEED_AVAILABLE = False
try:
    from alphafeed import AlphaFeed as _AlphaFeedClient
    _ALPHAFEED_AVAILABLE = True
except ImportError:
    pass


class NewsCollector(BaseCollector):
    """新闻采集器 — AlphaFeed 优先，AkShare 降级"""

    def __init__(self, api_key: str = "") -> None:
        super().__init__(name="news")
        self._api_key = api_key or os.environ.get("ALPHAFEED_KEY", "")
        self._client = None
        if _ALPHAFEED_AVAILABLE and self._api_key:
            try:
                self._client = _AlphaFeedClient(api_key=self._api_key)
            except Exception as e:
                logger.warning("AlphaFeed 客户端初始化失败: %s", e)

    async def collect(self, symbol: str = "", limit: int = 20) -> List[RawInfoItem]:
        """采集新闻信息

        优先使用 AlphaFeed，不可用时降级为 AkShare。
        """
        if self._client:
            items = await self._collect_alphafeed(symbol, limit)
            if items:
                return items
            logger.info("AlphaFeed 无数据，降级为 AkShare")

        return await self._collect_akshare(symbol, limit)

    async def _collect_alphafeed(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """从 AlphaFeed 采集新闻"""
        try:
            # AlphaFeed 暂无独立新闻 API，使用 instruments 获取基本信息
            # 未来版本可扩展为 AlphaFeed 新闻端点
            return []
        except Exception as exc:
            logger.warning("AlphaFeed 新闻采集失败: %s", exc)
            return []

    async def _collect_akshare(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """从 AkShare 采集新闻（降级路径）"""
        all_items: List[RawInfoItem] = []
        seen_titles: set = set()
        source_status: Dict[str, str] = {}

        # 数据源 1: 东方财富个股新闻
        em_items = await self._collect_eastmoney(symbol, limit)
        if em_items:
            source_status["stock_news_em"] = f"ok({len(em_items)})"
        else:
            source_status["stock_news_em"] = "empty/failed"
        for item in em_items:
            if item.title not in seen_titles:
                seen_titles.add(item.title)
                all_items.append(item)

        # 数据源 2: CCTV 新闻
        if len(all_items) < limit:
            cctv_items = await self._collect_cctv(limit - len(all_items))
            if cctv_items:
                source_status["news_cctv"] = f"ok({len(cctv_items)})"
            else:
                source_status["news_cctv"] = "empty/failed"
            for item in cctv_items:
                if item.title not in seen_titles:
                    seen_titles.add(item.title)
                    all_items.append(item)

        # 数据源 3: 全球财经快讯
        if len(all_items) < limit:
            global_items = await self._collect_global(limit - len(all_items))
            if global_items:
                source_status["stock_info_global_em"] = f"ok({len(global_items)})"
            else:
                source_status["stock_info_global_em"] = "empty/failed"
            for item in global_items:
                if item.title not in seen_titles:
                    seen_titles.add(item.title)
                    all_items.append(item)

        logger.info("新闻采集完成(AkShare): %s, 去重后 %d 条", source_status, len(all_items))
        return all_items[:limit]

    async def _collect_eastmoney(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """从东方财富采集个股新闻"""
        try:
            import akshare as ak

            df = ak.stock_news_em(symbol=symbol) if symbol else ak.stock_news_em(symbol="sh600519")
            items = []
            for _, row in df.head(limit).iterrows():
                title = str(row.get("新闻标题", row.get("title", "")))
                content = str(row.get("新闻内容", row.get("content", "")))
                url = str(row.get("新闻链接", row.get("url", "")))
                items.append(self._create_item(
                    url=url, source="eastmoney", title=title,
                    content=content, symbol=symbol,
                ))
            logger.debug("东方财富新闻采集: %d 条", len(items))
            return items
        except ImportError:
            logger.warning("akshare 未安装，跳过东方财富新闻采集")
            return []
        except Exception as exc:
            logger.warning("东方财富新闻采集失败: %s", exc)
            return []

    async def _collect_cctv(self, limit: int) -> List[RawInfoItem]:
        """从 CCTV 采集新闻"""
        try:
            import akshare as ak

            df = ak.news_cctv(date="")
            items = []
            for _, row in df.head(limit).iterrows():
                title = str(row.get("标题", row.get("title", "")))
                content = str(row.get("内容", row.get("content", "")))
                url = str(row.get("链接", row.get("url", "")))
                items.append(self._create_item(
                    url=url, source="cctv", title=title,
                    content=content,
                ))
            logger.debug("CCTV 新闻采集: %d 条", len(items))
            return items
        except ImportError:
            logger.warning("akshare 未安装，跳过 CCTV 新闻采集")
            return []
        except Exception as exc:
            logger.warning("CCTV 新闻采集失败: %s", exc)
            return []

    async def _collect_global(self, limit: int) -> List[RawInfoItem]:
        """从全球财经快讯采集新闻"""
        try:
            import akshare as ak

            df = ak.stock_info_global_em()
            items = []
            for _, row in df.head(limit).iterrows():
                title = str(row.get("标题", row.get("新闻标题", "")))
                content = str(row.get("内容", row.get("新闻内容", "")))
                url = str(row.get("链接", row.get("新闻链接", "")))
                items.append(self._create_item(
                    url=url, source="global_em", title=title,
                    content=content,
                ))
            logger.debug("全球财经快讯采集: %d 条", len(items))
            return items
        except ImportError:
            logger.warning("akshare 未安装，跳过全球财经快讯采集")
            return []
        except Exception as exc:
            logger.warning("全球财经快讯采集失败: %s", exc)
            return []
