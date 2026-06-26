# -*- coding: utf-8 -*-
"""F020 交易所披露采集器（C3）

数据源：
- 上交所披露（akshare.stock_sse_summary）
- 深交所披露（akshare.stock_szse_summary）
- 东方财富龙虎榜（akshare.stock_lhb_detail_em）
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseCollector, RawInfoItem

logger = logging.getLogger("stockquant.ai.collectors.exchange")


class ExchangeCollector(BaseCollector):
    """交易所披露采集器

    采集上交所/深交所的官方披露信息，包括：
    - 上市公司公告摘要
    - 龙虎榜数据（资金动向）
    - 停复牌信息
    """

    def __init__(self, akshare_adapter: Any = None) -> None:
        super().__init__(name="exchange")
        self._akshare = akshare_adapter

    def _get_akshare(self):
        """懒加载 akshare"""
        if self._akshare is not None:
            return self._akshare
        try:
            import akshare as ak
            return ak
        except ImportError:
            logger.warning("akshare 未安装，ExchangeCollector 无法采集")
            return None

    async def collect(self, symbol: str = "", limit: int = 20) -> List[RawInfoItem]:
        """采集交易所披露

        Args:
            symbol: 标的代码（如 sh600519）。为空时返回市场总览。
            limit: 返回最大条目数

        Returns:
            交易所披露条目列表
        """
        items: List[RawInfoItem] = []

        # 数据源 1: 龙虎榜（按 symbol 过滤）
        if symbol:
            lhb_items = self._collect_lhb(symbol, limit)
            items.extend(lhb_items)

        # 数据源 2: 上交所披露
        if len(items) < limit:
            sse_items = self._collect_sse(limit - len(items))
            items.extend(sse_items)

        # 数据源 3: 深交所披露
        if len(items) < limit:
            szse_items = self._collect_szse(limit - len(items))
            items.extend(szse_items)

        logger.info("交易所披露采集完成: symbol=%s, %d 条", symbol, len(items))
        return items[:limit]

    def _collect_lhb(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """龙虎榜数据采集"""
        ak = self._get_akshare()
        if ak is None:
            return []
        try:
            code = self._normalize_symbol(symbol)
            df = ak.stock_lhb_detail_em(symbol=code)
            if df is None or len(df) == 0:
                return []
            items: List[RawInfoItem] = []
            for _, row in df.head(limit).iterrows():
                date = str(row.get("上榜日", ""))
                reason = str(row.get("解读", ""))
                net_buy = str(row.get("龙虎榜净买额", ""))
                content_parts = [
                    f"上榜日: {date}" if date else "",
                    f"净买额: {net_buy}" if net_buy else "",
                    f"解读: {reason}" if reason else "",
                ]
                content = "\n".join(p for p in content_parts if p)
                title = f"{symbol} 龙虎榜 - {date}"
                items.append(self._create_item(
                    url="",
                    source="exchange_lhb",
                    title=title,
                    content=content,
                    symbol=symbol,
                ))
            logger.debug("龙虎榜采集: %d 条", len(items))
            return items
        except Exception as exc:
            logger.warning("龙虎榜采集失败: %s", exc)
            return []

    def _collect_sse(self, limit: int) -> List[RawInfoItem]:
        """上交所披露采集"""
        ak = self._get_akshare()
        if ak is None:
            return []
        try:
            df = ak.stock_sse_summary()
            if df is None or len(df) == 0:
                return []
            items: List[RawInfoItem] = []
            for _, row in df.head(limit).iterrows():
                # stock_sse_summary 返回的是市场总览（成交概况/指标）
                category = str(row.get("成交概况", row.get("类型", "")))
                value = str(row.get("数值", ""))
                content = f"{category}: {value}"
                title = f"上交所披露 - {category}"
                items.append(self._create_item(
                    url="",
                    source="sse_disclosure",
                    title=title,
                    content=content,
                ))
            logger.debug("上交所披露采集: %d 条", len(items))
            return items
        except Exception as exc:
            logger.warning("上交所披露采集失败: %s", exc)
            return []

    def _collect_szse(self, limit: int) -> List[RawInfoItem]:
        """深交所披露采集"""
        ak = self._get_akshare()
        if ak is None:
            return []
        try:
            df = ak.stock_szse_summary(date=datetime.now().strftime("%Y%m%d"))
            if df is None or len(df) == 0:
                return []
            items: List[RawInfoItem] = []
            for _, row in df.head(limit).iterrows():
                category = str(row.get("证券类别", row.get("类别", "")))
                value = str(row.get("成交金额", ""))
                content = f"{category}: {value}"
                title = f"深交所披露 - {category}"
                items.append(self._create_item(
                    url="",
                    source="szse_disclosure",
                    title=title,
                    content=content,
                ))
            logger.debug("深交所披露采集: %d 条", len(items))
            return items
        except Exception as exc:
            logger.warning("深交所披露采集失败: %s", exc)
            return []

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """规范化股票代码：sh600519 → 600519"""
        if not symbol:
            return ""
        s = symbol.strip().lower()
        for prefix in ("sh", "sz", "bj"):
            if s.startswith(prefix):
                return s[len(prefix):]
        return s
