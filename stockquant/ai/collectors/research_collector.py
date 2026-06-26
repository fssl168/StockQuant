# -*- coding: utf-8 -*-
"""F020 券商研报采集器（C1）

数据源：东方财富研报（akshare.stock_research_report_em）、巨潮资讯研报
写入层：L3-Intermediate（period_type=quarterly）
借鉴：TradingAgents 基本面分析师 + FinRobot 数据采集层
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseCollector, RawInfoItem

logger = logging.getLogger("stockquant.ai.collectors.research")


class ResearchCollector(BaseCollector):
    """券商研报采集器

    采集标的对应的研究报告：评级、目标价、核心观点。
    写入 L3-Intermediate 层（季报级，半衰期 90 天）。
    """

    def __init__(self, akshare_adapter: Any = None) -> None:
        super().__init__(name="research")
        self._akshare = akshare_adapter

    def _get_akshare(self):
        """懒加载 akshare（支持测试时注入 mock）"""
        if self._akshare is not None:
            return self._akshare
        try:
            import akshare as ak
            return ak
        except ImportError:
            logger.warning("akshare 未安装，ResearchCollector 无法采集")
            return None

    async def collect(self, symbol: str = "", limit: int = 20) -> List[RawInfoItem]:
        """采集研报

        Args:
            symbol: 标的代码（如 sh600519）。为空时返回热门研报。
            limit: 返回最大条目数

        Returns:
            研报条目列表，content 中结构化字段：
            rating（评级）、target_price（目标价）、researcher（分析师）
        """
        items: List[RawInfoItem] = []

        # 数据源 1: 东方财富研报
        em_items = self._collect_eastmoney(symbol, limit)
        items.extend(em_items)

        # 数据源 2: 巨潮资讯研报（如果东方财富不足）
        if len(items) < limit:
            cn_items = self._collect_cninfo(symbol, limit - len(items))
            items.extend(cn_items)

        # 去重（按标题）
        seen_titles = set()
        deduped: List[RawInfoItem] = []
        for item in items:
            if item.title and item.title not in seen_titles:
                seen_titles.add(item.title)
                deduped.append(item)

        logger.info("研报采集完成: symbol=%s, %d 条", symbol, len(deduped))
        return deduped[:limit]

    def _collect_eastmoney(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """从东方财富研报接口采集"""
        ak = self._get_akshare()
        if ak is None:
            return []
        try:
            # stock_research_report_em 接受股票代码（不带 sh/sz 前缀）
            code = self._normalize_symbol(symbol)
            df = ak.stock_research_report_em(symbol=code)
            if df is None or len(df) == 0:
                return []
            items: List[RawInfoItem] = []
            for _, row in df.head(limit).iterrows():
                title = str(row.get("研究机构", "") + " - " + row.get("评级", "")).strip(" -")
                rating = str(row.get("评级", ""))
                target_price = str(row.get("目标价", ""))
                researcher = str(row.get("研究员", ""))
                content_parts = [
                    f"评级: {rating}" if rating else "",
                    f"目标价: {target_price}" if target_price else "",
                    f"研究员: {researcher}" if researcher else "",
                ]
                content = "\n".join(p for p in content_parts if p)
                items.append(self._create_item(
                    url="",
                    source="eastmoney_research",
                    title=title or "未命名研报",
                    content=content,
                    symbol=symbol,
                ))
            logger.debug("东方财富研报采集: %d 条", len(items))
            return items
        except Exception as exc:
            logger.warning("东方财富研报采集失败: %s", exc)
            return []

    def _collect_cninfo(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """从巨潮资讯研报接口采集（占位，预留接口）"""
        # 巨潮研报接口尚不稳定，预留接口
        return []

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """规范化股票代码：sh600519 → 600519"""
        if not symbol:
            return ""
        # 去掉 sh/sz/SZ/SH 前缀
        s = symbol.strip().lower()
        for prefix in ("sh", "sz", "bj"):
            if s.startswith(prefix):
                return s[len(prefix):]
        return s
