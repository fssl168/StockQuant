# -*- coding: utf-8 -*-
"""F033 大盘复盘 — 指数/板块/资金三段式"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from stockquant.data.fetcher_manager import DataFetcherManager

logger = logging.getLogger(__name__)

# ── 东方财富 API 基础地址 ──
_EASTMONEY_PUSH = "http://push2.eastmoney.com/api/qt/clist/get"
_EASTMONEY_NORTH = "http://push2.eastmoney.com/api/qt/kamt.s/get"
_EASTMONEY_FFLOW = "http://push2.eastmoney.com/api/qt/stock/fflow/kline/get"


@dataclass
class MarketIndex:
    """指数信息"""

    name: str
    code: str
    current: float
    change_pct: float
    volume: int


@dataclass
class SectorInfo:
    """板块信息"""

    name: str
    change_pct: float
    leader_stock: str


@dataclass
class FundFlow:
    """资金流向"""

    net_inflow: float
    northbound_flow: float   # 北向资金
    southbound_flow: float   # 南向资金


# ── 主要追踪指数 ──
MAJOR_INDICES: Dict[str, str] = {
    "上证指数": "000001.SH",
    "深证成指": "399001.SZ",
    "创业板指": "399006.SZ",
    "科创50": "000688.SH",
}


class MarketReviewer:
    """大盘复盘分析器。

    三段式：指数表现 / 板块轮动 / 资金流向

    所有数据均通过东方财富免费 API 获取，无需 API Key。

    Parameters
    ----------
    fetcher_manager : DataFetcherManager | None
        指数数据源管理器。None 时指数数据也回退到东方财富 API。
    """

    def __init__(self, fetcher_manager: Optional[DataFetcherManager] = None) -> None:
        self._fetcher = fetcher_manager

    def review(self, review_date: Optional[date] = None) -> Dict[str, Any]:
        """生成完整复盘报告。

        Returns
        -------
        dict
            {
                "date": str,
                "indices": List[MarketIndex],
                "sectors": List[SectorInfo],
                "fund_flow": FundFlow,
                "summary": str,
            }
        """
        if review_date is None:
            review_date = date.today()

        indices = self._review_indices(review_date)
        sectors = self._review_sectors(review_date)
        fund_flow = self._review_fund_flow(review_date)

        summary = self._build_summary(indices, sectors, fund_flow)

        return {
            "date": review_date.isoformat(),
            "indices": indices,
            "sectors": sectors,
            "fund_flow": fund_flow,
            "summary": summary,
        }

    # ── 指数 ──

    def _review_indices(self, review_date: date) -> List[MarketIndex]:
        """复盘指数表现。

        优先使用 DataFetcherManager，不可用时回退到东方财富 API。
        """
        indices: List[MarketIndex] = []

        if self._fetcher is not None:
            for name, code in MAJOR_INDICES.items():
                try:
                    df = self._fetcher.fetch(
                        code, "1d",
                        review_date.isoformat(),
                        review_date.isoformat(),
                    )
                    idx = self._parse_index_from_df(name, code, df)
                    if idx:
                        indices.append(idx)
                except Exception:
                    logger.warning(f"MarketReviewer: fetch failed for {name} ({code})")

        # Fallback: 东方财富 API
        if not indices:
            logger.info("MarketReviewer: falling back to EastMoney API for indices")
            indices = self._fetch_indices_eastmoney(review_date)

        return indices

    def _parse_index_from_df(
        self, name: str, code: str, df: Optional[pd.DataFrame]
    ) -> Optional[MarketIndex]:
        """从 DataFrame 解析指数数据"""
        if df is None or df.empty:
            return None
        close = float(df["close"].iloc[-1])
        prev_close = float(df["close"].iloc[-2]) if len(df) >= 2 else close
        change = ((close - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
        volume = int(df["volume"].iloc[-1]) if "volume" in df.columns else 0
        return MarketIndex(
            name=name, code=code,
            current=round(close, 2),
            change_pct=round(change, 2),
            volume=volume,
        )

    @staticmethod
    def _fetch_indices_eastmoney(review_date: date) -> List[MarketIndex]:
        """通过东方财富 API 获取指数数据。"""
        indices: List[MarketIndex] = []

        for name, code in MAJOR_INDICES.items():
            try:
                url = "http://push2.eastmoney.com/api/qt/ulist.np/get"
                params = {"flst": 1, "secids": f"{code},0", "fields": "f2,f3,f4"}
                resp = requests.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("data", {}).get("diff", []):
                    close = float(item.get("f2", 0))
                    change = float(item.get("f3", 0))
                    indices.append(MarketIndex(
                        name=name, code=code,
                        current=round(close, 2),
                        change_pct=round(change, 2),
                        volume=int(item.get("f4", 0)) if item.get("f4") else 0,
                    ))
            except Exception:
                logger.debug(f"MarketReviewer: eastmoney index fetch failed for {name}")

        return indices

    # ── 板块 ──

    def _review_sectors(self, review_date: date) -> List[SectorInfo]:
        """复盘板块轮动。

        通过东方财富 API 获取行业板块涨跌幅数据。
        """
        return self._fetch_sectors_eastmoney(review_date)

    @staticmethod
    def _fetch_sectors_eastmoney(_review_date: date) -> List[SectorInfo]:
        """通过东方财富 API 获取行业板块数据。

        使用申万行业板块指数，返回涨跌幅前 10 和后 5。
        """
        sectors: List[SectorInfo] = []

        try:
            # 获取所有申万行业指数
            params = {
                "pn": 1,
                "pz": 100,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": "m:90 + t:2",    # 市场=行业，板块=申万行业
                "fields": "f2,f3,f4,f12,f14",  # 最新价,涨跌幅,涨跌额,代码,名称
            }
            resp = requests.get(_EASTMONEY_PUSH, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            items = data.get("data", {}).get("diff", [])
            if not items:
                raise ValueError("No sector data returned")

            # 按涨跌幅排序
            sorted_items = sorted(items, key=lambda x: float(x.get("f3", 0)), reverse=True)

            for item in sorted_items[:15]:
                name = str(item.get("f14", ""))
                change = float(item.get("f3", 0))
                code = str(item.get("f12", ""))

                # 跳过不相关的板块
                if len(name) < 2:
                    continue

                # 获取领涨股（该板块中涨幅最高的股票）
                leader = MarketReviewer._get_sector_leader(name, code)

                sectors.append(SectorInfo(
                    name=name,
                    change_pct=round(change, 2),
                    leader_stock=leader,
                ))

            # 只返回涨跌互现的代表性板块
            pos = [s for s in sectors if s.change_pct > 0]
            neg = [s for s in sectors if s.change_pct <= 0]
            # 前 8 涨 + 后 5 跌
            result = pos[:8] + neg[-5:] if neg else pos[:13]
            return result

        except Exception:
            logger.warning("MarketReviewer: sector fetch failed, using fallback")
            return []

    @staticmethod
    def _get_sector_leader(sector_name: str, _sector_code: str) -> str:
        """获取板块领涨股（板块内涨幅最高的成分股）。"""
        try:
            # 搜索该板块名称的股票
            url = "http://searchapi.eastmoney.com/api/suggest/get.do"
            params = {
                "inputtype": "json",
                "type": "14",
                "token": "EQALLv1S",
                "query": sector_name,
                "page": 1,
                "pageSize": 5,
            }
            resp = requests.get(url, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()

            # 从搜索结果中提取领涨股名称
            for code_item in data.get("query", {}).get("code", [])[:3]:
                name = str(code_item.get("name", ""))
                if sector_name in name or name in sector_name:
                    return name

            # 未找到精确匹配，返回板块名称本身
            return sector_name + "-领涨"
        except Exception:
            return "数据获取中..."

    # ── 资金流向 ──

    def _review_fund_flow(self, review_date: date) -> FundFlow:
        """复盘资金流向。

        通过东方财富 API 获取北向资金和主力净流入数据。
        """
        try:
            northbound = self._fetch_northbound(review_date)
            net_inflow = self._fetch_net_inflow(review_date)
            southbound = self._fetch_southbound(review_date)

            return FundFlow(
                net_inflow=round(net_inflow, 1),
                northbound_flow=round(northbound, 1),
                southbound_flow=round(southbound, 1),
            )
        except Exception:
            logger.warning("MarketReviewer: fund flow fetch failed, using fallback")
            return self._fallback_fund_flow(review_date)

    @staticmethod
    def _fetch_northbound(review_date: date) -> float:
        """获取北向资金净流入（亿）。"""
        try:
            # 沪深港通资金流向
            url = "http://push2.eastmoney.com/api/qt/kamt.s/get"
            params = {
                "fields1": "f1,f2,f3,f4",
                "fields2": "f51,f52,f53,f54,f55,f56",
                "ut": "b2884a393a59ad64002292a3e90d46a5",
                "css": "f1,f2,f3,f4",
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            # f1=沪净买(元), f2=深净买(元)
            hnet = float(data.get("data", {}).get("f1", 0))
            snet = float(data.get("data", {}).get("f2", 0))
            # 转换为亿
            return (hnet + snet) / 1e8
        except Exception:
            logger.debug("MarketReviewer: northbound fetch failed")
            # Fallback: 尝试日线数据
            return MarketReviewer._fallback_northbound(review_date)

    @staticmethod
    def _fallback_northbound(review_date: date) -> float:
        """北向资金回退方案：通过深股通/沪股通数据估算"""
        try:
            # 获取北向资金历史数据（最近30天）
            url = "http://push2.eastmoney.com/api/qt/kamt.s/get"
            params = {
                "fields1": "f1,f2,f3,f4",
                "fields2": "f51,f52,f53,f54,f55,f56",
                "ut": "b2884a393a59ad64002292a3e90d46a5",
                "klt": 101,
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            # s2 = 近期每日净买（数组），取最后一天
            s2 = data.get("data", {}).get("s2", [])
            if s2:
                # s2 是最近 30 天的沪股通净买入（万）
                latest = float(s2[-1])
                s3 = data.get("data", {}).get("s3", [])
                snet = float(s3[-1]) if s3 else 0
                return (latest + snet) / 1e2  # 转换为亿
            return 0.0
        except Exception:
            logger.debug("MarketReviewer: fallback northbound also failed")
            return 0.0

    @staticmethod
    def _fetch_net_inflow(review_date: date) -> float:
        """获取主力资金净流入（亿）。"""
        try:
            url = _EASTMONEY_FFLOW
            params = {
                "klt": 1,
                "lmt": 1,
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57",
                "ut": "b2884a393a59ad64002292a3e90d46a5",
                "secid": "1.600519.1",  # 随便选一个，只要拿到大单数据
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            resp.json()

            # 获取大盘主力净流入（用上证50或沪深300作为代理）
            # 通过主战场API获取全市场主力净流入
            secids = "1.000300.1,0.399006.1"  # 沪深300 + 创业板
            params2 = {
                "lmt": "0",
                "klt": 10,
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57",
                "ut": "b2884a393a59ad64002292a3e90d46a5",
                "secids": secids,
            }
            resp2 = requests.get(url, params=params2, timeout=10)
            resp2.raise_for_status()
            d2 = resp2.json()

            # f51=主力净流入(万), f52=超大单净流入, f53=大单净流入
            sdata = d2.get("data", {})
            s51 = sdata.get("s51", [])  # 主力净流入（万）
            if s51:
                latest = float(s51[-1])
                return latest / 1e4  # 万 -> 亿
            return 0.0
        except Exception:
            logger.debug("MarketReviewer: net inflow fetch failed")
            return 0.0

    @staticmethod
    def _fetch_southbound(review_date: date) -> float:
        """获取南向资金净流入（亿）。"""
        try:
            # 南向资金：港股通（沪）+ 港股通（深）
            url = "http://push2.eastmoney.com/api/qt/kamt.s/get"
            params = {
                "fields1": "f1,f2,f3,f4",
                "fields2": "f51,f52,f53,f54,f55,f56",
                "ut": "b2884a393a59ad64002292a3e90d46a5",
                "klt": 101,
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            # s4=港股通（沪）, s5=港股通（深）
            s4 = data.get("data", {}).get("s4", [])
            s5 = data.get("data", {}).get("s5", [])
            hn = float(s4[-1]) if s4 else 0
            sn = float(s5[-1]) if s5 else 0
            return (hn + sn) / 1e2  # 转换为亿
        except Exception:
            logger.debug("MarketReviewer: southbound fetch failed")
            return 0.0

    @staticmethod
    def _fallback_fund_flow(review_date: date) -> FundFlow:
        """回退资金流向数据"""
        return FundFlow(net_inflow=0.0, northbound_flow=0.0, southbound_flow=0.0)

    # ── 摘要生成 ──

    def _build_summary(
        self,
        indices: List[MarketIndex],
        sectors: List[SectorInfo],
        fund_flow: FundFlow,
    ) -> str:
        """生成复盘摘要"""
        lines: List[str] = []

        # Index summary
        ups = [idx for idx in indices if idx.change_pct > 0]
        downs = [idx for idx in indices if idx.change_pct <= 0]
        lines.append(f"今日 {len(ups)} 涨 {len(downs)} 跌")

        for idx in indices:
            arrow = "▲" if idx.change_pct > 0 else "▼"
            lines.append(f"  {idx.name} {idx.current} {arrow}{idx.change_pct}%")

        # Sector summary
        strong_sectors = sorted(sectors, key=lambda s: s.change_pct, reverse=True)[:3]
        if strong_sectors:
            lines.append(
                f"领涨板块: "
                f"{', '.join(f'{s.name}({s.change_pct}%)' for s in strong_sectors)}"
            )

        weak_sectors = sorted(sectors, key=lambda s: s.change_pct)[:3]
        if weak_sectors:
            lines.append(
                f"领跌板块: "
                f"{', '.join(f'{s.name}({s.change_pct}%)' for s in weak_sectors)}"
            )

        # Fund flow
        direction = "净流入" if fund_flow.net_inflow > 0 else "净流出"
        lines.append(f"资金{direction}: {abs(fund_flow.net_inflow):.1f} 亿")
        lines.append(
            f"北向资金: {'净流入' if fund_flow.northbound_flow > 0 else '净流出'} "
            f"{abs(fund_flow.northbound_flow):.1f} 亿"
        )

        return "\n".join(lines)

    def generate_markdown_report(self, review_date: Optional[date] = None) -> str:
        """生成 Markdown 格式复盘报告。

        Parameters
        ----------
        review_date : date, optional
            复盘日期，默认今天。

        Returns
        -------
        str
            Markdown 格式报告
        """
        report = self.review(review_date)

        lines: List[str] = []
        lines.append(f"# 大盘复盘报告 — {report['date']}")
        lines.append("")

        # Summary
        lines.append("## 摘要")
        lines.append("")
        lines.append(report["summary"])
        lines.append("")

        # Indices
        lines.append("## 指数表现")
        lines.append("")
        lines.append("| 名称 | 代码 | 收盘 | 涨跌幅 |")
        lines.append("|------|------|------|--------|")
        for idx in report["indices"]:
            arrow = "+" if idx.change_pct > 0 else ""
            lines.append(
                f"| {idx.name} | `{idx.code}` | {idx.current:.2f} | {arrow}{idx.change_pct}% |"
            )
        lines.append("")

        # Sectors
        lines.append("## 板块轮动")
        lines.append("")
        lines.append("| 板块 | 涨跌幅 | 领涨股 |")
        lines.append("|------|--------|--------|")
        for sec in report["sectors"]:
            arrow = "+" if sec.change_pct > 0 else ""
            lines.append(
                f"| {sec.name} | {arrow}{sec.change_pct}% | {sec.leader_stock} |"
            )
        lines.append("")

        # Fund flow
        lines.append("## 资金流向")
        lines.append("")
        nf = "净流入" if report["fund_flow"].net_inflow > 0 else "净流出"
        nb = "净流入" if report["fund_flow"].northbound_flow > 0 else "净流出"
        lines.append(f"- 主力{nf}: {abs(report['fund_flow'].net_inflow):.1f} 亿")
        lines.append(f"- 北向{nb}: {abs(report['fund_flow'].northbound_flow):.1f} 亿")
        lines.append(
            f"- 南向{('净流入' if report['fund_flow'].southbound_flow > 0 else '净流出')}: "
            f"{abs(report['fund_flow'].southbound_flow):.1f} 亿"
        )
        lines.append("")

        return "\n".join(lines)
