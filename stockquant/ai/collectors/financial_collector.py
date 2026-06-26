# -*- coding: utf-8 -*-
"""F020 财务报表采集器（C2）

数据源：AkShare 财务数据（akshare.stock_financial_report_sina）、东方财富财务指标
写入层：L3-Deep（period_type=annual）

借鉴 FinMem 分层记忆设计：财务数据作为深层记忆，半衰期 365 天，
importance_score 高于浅层市场新闻（默认 0.7）。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseCollector, RawInfoItem

logger = logging.getLogger("stockquant.ai.collectors.financial")


class FinancialCollector(BaseCollector):
    """财务报表采集器

    采集标的的最新季报关键指标（PE/PB/ROE/营收/净利润），
    封装为结构化 RawInfoItem（type='financial'），
    供反幻觉事实初筛使用。
    """

    def __init__(self, akshare_adapter: Any = None) -> None:
        super().__init__(name="financial")
        self._akshare = akshare_adapter

    def _get_akshare(self):
        """懒加载 akshare（支持测试时注入 mock）"""
        if self._akshare is not None:
            return self._akshare
        try:
            import akshare as ak
            return ak
        except ImportError:
            logger.warning("akshare 未安装，FinancialCollector 无法采集")
            return None

    async def collect(self, symbol: str = "", limit: int = 20) -> List[RawInfoItem]:
        """采集财务数据

        Args:
            symbol: 标的代码（如 sh600519）
            limit: 返回最大条目数（通常 1 个标的最多 4 条：年报+3 季报）

        Returns:
            财务条目列表，content 中包含结构化字段：
            pe, pb, roe, revenue, net_profit, report_period
        """
        if not symbol:
            logger.debug("FinancialCollector 需要指定 symbol")
            return []

        items: List[RawInfoItem] = []

        # 数据源 1: 新浪财务报表
        sina_items = self._collect_sina_financial(symbol, limit)
        items.extend(sina_items)

        # 数据源 2: 东方财富财务指标（如果新浪不足）
        if len(items) < limit:
            em_items = self._collect_eastmoney_financial(symbol, limit - len(items))
            items.extend(em_items)

        logger.info("财务数据采集完成: symbol=%s, %d 条", symbol, len(items))
        return items[:limit]

    def _collect_sina_financial(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """从新浪财务报表接口采集"""
        ak = self._get_akshare()
        if ak is None:
            return []
        try:
            # stock_financial_report_sina 接受股票代码（不带前缀）
            code = self._normalize_symbol(symbol)
            df = ak.stock_financial_report_sina(stock=f"sh{code}" if code.startswith("6") else f"sz{code}")
            if df is None or len(df) == 0:
                return []

            items: List[RawInfoItem] = []
            for _, row in df.head(limit).iterrows():
                # 字段名以 akshare 接口为准
                report_period = str(row.get("报告日", row.get("报告期", "")))
                revenue = str(row.get("主营业务收入", row.get("营业收入", "")))
                net_profit = str(row.get("净利润", ""))
                eps = str(row.get("每股收益", row.get("基本每股收益", "")))
                roe = str(row.get("净资产收益率", row.get("ROE", "")))

                content_parts = [
                    f"报告期: {report_period}" if report_period else "",
                    f"营业收入: {revenue}" if revenue else "",
                    f"净利润: {net_profit}" if net_profit else "",
                    f"每股收益: {eps}" if eps else "",
                    f"ROE: {roe}" if roe else "",
                ]
                content = "\n".join(p for p in content_parts if p)
                title = f"{symbol} 财报 ({report_period})"

                items.append(self._create_item(
                    url="",
                    source="sina_financial",
                    title=title,
                    content=content,
                    symbol=symbol,
                ))
            logger.debug("新浪财务报表采集: %d 条", len(items))
            return items
        except Exception as exc:
            logger.warning("新浪财务报表采集失败: %s", exc)
            return []

    def _collect_eastmoney_financial(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """从东方财富财务指标接口采集"""
        ak = self._get_akshare()
        if ak is None:
            return []
        try:
            code = self._normalize_symbol(symbol)
            # stock_financial_abstract_ths 同花顺财务摘要
            df = ak.stock_financial_abstract(symbol=code)
            if df is None or len(df) == 0:
                return []

            items: List[RawInfoItem] = []
            for _, row in df.head(limit).iterrows():
                indicator = str(row.get("指标", ""))
                value = str(row.get("本期", row.get("数值", "")))
                content = f"{indicator}: {value}"
                title = f"{symbol} 财务指标 - {indicator}"
                items.append(self._create_item(
                    url="",
                    source="eastmoney_financial",
                    title=title,
                    content=content,
                    symbol=symbol,
                ))
            logger.debug("东方财富财务指标采集: %d 条", len(items))
            return items
        except Exception as exc:
            logger.warning("东方财富财务指标采集失败: %s", exc)
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
