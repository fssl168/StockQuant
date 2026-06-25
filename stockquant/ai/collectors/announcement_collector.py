# -*- coding: utf-8 -*-
"""公告采集器 — AlphaFeed 优先 / AkShare 降级"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .base import BaseCollector, RawInfoItem

logger = logging.getLogger("stockquant.ai.collectors.announcement")

# AlphaFeed SDK 可选导入
_ALPHAFEED_AVAILABLE = False
try:
    from alphafeed import AlphaFeed as _AlphaFeedClient
    _ALPHAFEED_AVAILABLE = True
except ImportError:
    pass


class AnnouncementCollector(BaseCollector):
    """公告采集器 — AlphaFeed 优先，AkShare 降级"""

    def __init__(self, api_key: str = "") -> None:
        super().__init__(name="announcement")
        self._api_key = api_key or os.environ.get("ALPHAFEED_KEY", "")
        self._client = None
        if _ALPHAFEED_AVAILABLE and self._api_key:
            try:
                self._client = _AlphaFeedClient(api_key=self._api_key)
            except Exception as e:
                logger.warning("AlphaFeed 客户端初始化失败: %s", e)

    async def collect(
        self,
        symbol: str = "",
        limit: int = 20,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
    ) -> List[RawInfoItem]:
        """采集公告信息

        优先使用 AlphaFeed，不可用时降级为 AkShare。
        """
        if not date_end:
            date_end = datetime.now().strftime("%Y%m%d")
        if not date_start:
            date_start = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

        if self._client:
            items = await self._collect_alphafeed(symbol, limit, date_start, date_end)
            if items:
                return items
            logger.info("AlphaFeed 无数据，降级为 AkShare")

        return await self._collect_akshare(symbol, limit, date_start, date_end)

    async def _collect_alphafeed(
        self, symbol: str, limit: int, date_start: str, date_end: str
    ) -> List[RawInfoItem]:
        """从 AlphaFeed 采集公告"""
        try:
            # AlphaFeed 暂无独立 API，保留接口供未来扩展。
            # Returns: [] — AlphaFeed SDK 尚未集成
            return []
        except Exception as exc:
            logger.warning("AlphaFeed 公告采集失败: %s", exc)
            return []

    async def _collect_akshare(
        self, symbol: str, limit: int, date_start: str, date_end: str
    ) -> List[RawInfoItem]:
        """从 AkShare 采集公告（降级路径）"""
        all_items: List[RawInfoItem] = []
        seen_titles: set = set()
        source_status: Dict[str, str] = {}

        # 数据源 1: 巨潮资讯公告
        notice_items = await self._collect_notice_report(symbol, limit, date_start, date_end)
        if notice_items:
            source_status["stock_notice_report"] = f"ok({len(notice_items)})"
        else:
            source_status["stock_notice_report"] = "empty/failed"
        for item in notice_items:
            if item.title not in seen_titles:
                seen_titles.add(item.title)
                all_items.append(item)

        # 数据源 2: 信息披露
        if len(all_items) < limit:
            disclosure_items = await self._collect_disclosure(symbol, limit - len(all_items), date_start, date_end)
            if disclosure_items:
                source_status["stock_disclosure"] = f"ok({len(disclosure_items)})"
            else:
                source_status["stock_disclosure"] = "empty/failed"
            for item in disclosure_items:
                if item.title not in seen_titles:
                    seen_titles.add(item.title)
                    all_items.append(item)

        # 日期范围过滤
        try:
            dt_start = datetime.strptime(date_start, "%Y%m%d")
            dt_end = datetime.strptime(date_end, "%Y%m%d")
            filtered = [
                item for item in all_items
                if dt_start <= item.timestamp <= dt_end
            ]
            if len(filtered) < len(all_items):
                logger.debug("日期过滤: %d → %d 条", len(all_items), len(filtered))
            all_items = filtered
        except ValueError:
            logger.warning("日期格式无效，跳过日期过滤")

        logger.info("公告采集完成(AkShare): %s, 去重后 %d 条", source_status, len(all_items))
        if not all_items:
            failed_sources = [k for k, v in source_status.items() if "failed" in v or "empty" in v]
            if failed_sources:
                logger.warning("所有公告数据源采集失败: %s", failed_sources)
        return all_items[:limit]

    async def _collect_notice_report(
        self, symbol: str, limit: int, date_start: str, date_end: str
    ) -> List[RawInfoItem]:
        """从巨潮资讯采集公告"""
        try:
            import akshare as ak

            if symbol:
                df = ak.stock_notice_report(symbol=symbol)
            else:
                df = ak.stock_gsrl_gsdt_em()
            items = []
            for _, row in df.head(limit).iterrows():
                title = str(row.get("公告标题", row.get("title", "")))
                content = str(row.get("公告内容", row.get("content", "")))
                url = str(row.get("公告链接", row.get("url", "")))
                items.append(self._create_item(
                    url=url, source="cninfo", title=title,
                    content=content, symbol=symbol,
                ))
            logger.debug("巨潮资讯公告采集: %d 条", len(items))
            return items
        except ImportError:
            logger.warning("akshare 未安装，跳过巨潮资讯公告采集")
            return []
        except Exception as exc:
            logger.warning("巨潮资讯公告采集失败: %s", exc)
            return []

    async def _collect_disclosure(
        self, symbol: str, limit: int, date_start: str, date_end: str
    ) -> List[RawInfoItem]:
        """从信息披露采集公告"""
        try:
            import akshare as ak

            df = ak.stock_disclosure(date=date_end)
            items = []
            for _, row in df.head(limit).iterrows():
                title = str(row.get("公告标题", row.get("标题", "")))
                content = str(row.get("公告内容", row.get("内容", "")))
                url = str(row.get("公告链接", row.get("链接", "")))
                row_symbol = str(row.get("股票代码", row.get("symbol", symbol)))
                items.append(self._create_item(
                    url=url, source="disclosure", title=title,
                    content=content, symbol=row_symbol,
                ))
            logger.debug("信息披露公告采集: %d 条", len(items))
            return items
        except ImportError:
            logger.warning("akshare 未安装，跳过信息披露公告采集")
            return []
        except Exception as exc:
            logger.warning("信息披露公告采集失败: %s", exc)
            return []
