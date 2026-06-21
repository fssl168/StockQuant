# -*- coding: utf-8 -*-
"""社交媒体采集器 — AlphaFeed 优先 / AkShare 降级"""
from __future__ import annotations

import logging
import os
from typing import Dict, List

from .base import BaseCollector, RawInfoItem

logger = logging.getLogger("stockquant.ai.collectors.social")

# AlphaFeed SDK 可选导入
_ALPHAFEED_AVAILABLE = False
try:
    from alphafeed import AlphaFeed as _AlphaFeedClient
    _ALPHAFEED_AVAILABLE = True
except ImportError:
    pass


class SocialCollector(BaseCollector):
    """社交媒体采集器 — AlphaFeed 优先，AkShare 降级"""

    def __init__(self, api_key: str = "") -> None:
        super().__init__(name="social")
        self._api_key = api_key or os.environ.get("ALPHAFEED_KEY", "")
        self._client = None
        if _ALPHAFEED_AVAILABLE and self._api_key:
            try:
                self._client = _AlphaFeedClient(api_key=self._api_key)
            except Exception as e:
                logger.warning("AlphaFeed 客户端初始化失败: %s", e)

    async def collect(self, symbol: str = "", limit: int = 20) -> List[RawInfoItem]:
        """采集社交媒体情绪数据

        优先使用 AlphaFeed，不可用时降级为 AkShare。
        """
        if self._client:
            items = await self._collect_alphafeed(symbol, limit)
            if items:
                return items
            logger.info("AlphaFeed 无数据，降级为 AkShare")

        return await self._collect_akshare(symbol, limit)

    async def _collect_alphafeed(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """从 AlphaFeed 采集社交情绪数据"""
        try:
            # AlphaFeed 暂无独立 API，保留接口供未来扩展。
            # Returns: [] — AlphaFeed SDK 尚未集成
            return []
        except Exception as exc:
            logger.warning("AlphaFeed 社交情绪采集失败: %s", exc)
            return []

    async def _collect_akshare(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """从 AkShare 采集社交情绪数据（降级路径）"""
        all_items: List[RawInfoItem] = []
        seen_titles: set = set()
        source_status: Dict[str, str] = {}

        # 数据源 1: 东方财富热度排名
        hot_items = await self._collect_hot_rank(symbol, limit)
        if hot_items:
            source_status["stock_hot_rank_em"] = f"ok({len(hot_items)})"
        else:
            source_status["stock_hot_rank_em"] = "empty/failed"
        for item in hot_items:
            if item.title not in seen_titles:
                seen_titles.add(item.title)
                all_items.append(item)

        # 数据源 2: 东方财富股吧评论
        if len(all_items) < limit:
            comment_items = await self._collect_comment(symbol, limit - len(all_items))
            if comment_items:
                source_status["stock_comment_em"] = f"ok({len(comment_items)})"
            else:
                source_status["stock_comment_em"] = "empty/failed"
            for item in comment_items:
                if item.title not in seen_titles:
                    seen_titles.add(item.title)
                    all_items.append(item)

        logger.info("社交情绪采集完成(AkShare): %s, 去重后 %d 条", source_status, len(all_items))
        return all_items[:limit]

    @staticmethod
    def _rank_to_sentiment(rank: int, total: int = 100) -> float:
        """将热度排名转换为情绪分数"""
        if total <= 0:
            return 0.5
        return max(0.0, min(1.0, 1.0 - rank / total))

    async def _collect_hot_rank(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """从东方财富热度排名采集"""
        try:
            import akshare as ak

            df = ak.stock_hot_rank_em()
            total = len(df) if len(df) > 0 else 100
            items = []
            for _, row in df.head(limit).iterrows():
                row_symbol = str(row.get("股票代码", row.get("symbol", "")))
                title = f"热度排名: {row.get('股票简称', row.get('名称', ''))} (代码: {row_symbol})"
                rank_val = row.get("当前排名", row.get("排名", 0))
                try:
                    rank_int = int(rank_val)
                except (ValueError, TypeError):
                    rank_int = 0
                sentiment = self._rank_to_sentiment(rank_int, total)
                content = (
                    f"股票: {row.get('股票简称', row.get('名称', ''))}, "
                    f"代码: {row_symbol}, "
                    f"当前排名: {rank_int}, "
                    f"情绪分数: {sentiment:.2f}"
                )
                if symbol and row_symbol != symbol:
                    continue
                items.append(self._create_item(
                    url="", source="hot_rank_em", title=title,
                    content=content, symbol=row_symbol,
                    sentiment=sentiment,
                ))
            logger.debug("热度排名采集: %d 条", len(items))
            return items
        except ImportError:
            logger.warning("akshare 未安装，跳过热度排名采集")
            return []
        except Exception as exc:
            logger.warning("热度排名采集失败: %s", exc)
            return []

    async def _collect_comment(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """从东方财富股吧评论采集"""
        try:
            import akshare as ak

            if not symbol:
                return []
            df = ak.stock_comment_em()
            items = []
            for _, row in df.head(limit).iterrows():
                row_symbol = str(row.get("股票代码", row.get("symbol", "")))
                if symbol and row_symbol != symbol:
                    continue
                title = str(row.get("标题", row.get("title", f"评论: {row_symbol}")))
                content = str(row.get("内容", row.get("content", "")))
                sentiment_raw = row.get("情绪分数", row.get("sentiment", None))
                try:
                    sentiment = float(sentiment_raw) if sentiment_raw is not None else 0.5
                except (ValueError, TypeError):
                    sentiment = 0.5
                items.append(self._create_item(
                    url="", source="comment_em", title=title,
                    content=content, symbol=row_symbol,
                    sentiment=sentiment,
                ))
            logger.debug("股吧评论采集: %d 条", len(items))
            return items
        except ImportError:
            logger.warning("akshare 未安装，跳过股吧评论采集")
            return []
        except Exception as exc:
            logger.warning("股吧评论采集失败: %s", exc)
            return []
