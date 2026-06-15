# -*- coding: utf-8 -*-
"""Tests for stockquant.analytics.market_review"""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from stockquant.analytics.market_review import (
    MarketIndex,
    SectorInfo,
    FundFlow,
    MarketReviewer,
    MAJOR_INDICES,
)


class TestConstants:
    def test_major_indices_defined(self):
        assert "上证指数" in MAJOR_INDICES
        assert "深证成指" in MAJOR_INDICES
        assert "创业板指" in MAJOR_INDICES
        assert "科创50" in MAJOR_INDICES


class TestReviewInit:
    def test_default_init_no_fetcher(self):
        reviewer = MarketReviewer()
        assert reviewer._fetcher is None

    def test_init_with_fetcher(self):
        mock_fm = MagicMock()
        reviewer = MarketReviewer(fetcher_manager=mock_fm)
        assert reviewer._fetcher is mock_fm


class TestParseIndexFromDf:
    def test_parses_from_dataframe(self):
        import pandas as pd
        df = pd.DataFrame({"close": [3000.0, 3030.0], "volume": [1000000, 1100000]})
        reviewer = MarketReviewer()
        idx = reviewer._parse_index_from_df("上证指数", "000001.SH", df)
        assert idx is not None
        assert idx.current == 3030.0
        assert abs(idx.change_pct - 1.0) < 0.1

    def test_empty_dataframe_returns_none(self):
        import pandas as pd
        df = pd.DataFrame(columns=["close", "volume"])
        reviewer = MarketReviewer()
        assert reviewer._parse_index_from_df("上证", "000001.SH", df) is None

    def test_none_dataframe_returns_none(self):
        reviewer = MarketReviewer()
        assert reviewer._parse_index_from_df("上证", "000001.SH", None) is None


class TestReviewIndices:
    def test_fetcher_returns_indices(self):
        import pandas as pd
        mock_fm = MagicMock()
        # fetch returns a DataFrame per symbol
        mock_fm.fetch.return_value = pd.DataFrame({
            "close": [3000.0, 3030.0],
            "volume": [1000000, 1100000],
        })
        reviewer = MarketReviewer(fetcher_manager=mock_fm)
        result = reviewer._review_indices(date(2024, 6, 15))
        assert len(result) >= 1
        assert isinstance(result[0], MarketIndex)

    def test_fallback_to_eastmoney(self):
        """当无 fetcher 时，回退到东方财富 API。"""
        # Mock the requests call
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "diff": [
                    {"f2": 3030.0, "f3": 1.0, "f4": 1000000, "f8": "上证指数"},
                    {"f2": 9800.0, "f3": -0.5, "f4": 2000000, "f8": "深证成指"},
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            reviewer = MarketReviewer()
            result = reviewer._review_indices(date(2024, 6, 15))
            assert len(result) >= 1
            assert all(isinstance(idx, MarketIndex) for idx in result)


class TestFetchSectorsEastmoney:
    def test_fetches_real_sectors(self):
        """模拟东方财富 API 返回真实板块数据"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "diff": [
                    {"f12": "801170", "f14": "计算机", "f3": 2.5, "f2": 3500.0, "f4": 500000},
                    {"f12": "801710", "f14": "电力设备", "f3": 1.8, "f2": 2800.0, "f4": 800000},
                    {"f12": "801390", "f14": "电子", "f3": 1.2, "f2": 1500.0, "f4": 600000},
                    {"f12": "801180", "f14": "医药生物", "f3": -0.5, "f2": 2200.0, "f4": 400000},
                    {"f12": "801120", "f14": "银行", "f3": -0.3, "f2": 1800.0, "f4": 300000},
                    {"f12": "801160", "f14": "食品饮料", "f3": -1.2, "f2": 3000.0, "f4": 700000},
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            sectors = MarketReviewer._fetch_sectors_eastmoney(date(2024, 6, 15))
            assert len(sectors) >= 3
            assert isinstance(sectors[0], SectorInfo)
            # 检查排序（从高到低）
            assert sectors[0].change_pct >= sectors[-1].change_pct

    def test_empty_response(self):
        """空响应回退为空列表"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"diff": []}}
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            sectors = MarketReviewer._fetch_sectors_eastmoney(date(2024, 6, 15))
            assert sectors == []

    def test_api_failure_returns_empty(self):
        """API 失败时返回空列表"""
        with patch("requests.get", side_effect=Exception("network error")):
            sectors = MarketReviewer._fetch_sectors_eastmoney(date(2024, 6, 15))
            assert sectors == []


class TestFetchNorthbound:
    def test_fetches_northbound(self):
        """北向资金获取"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {"f1": 5e8, "f2": 3e8}  # 沪5亿, 深3亿
        }
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            flow = MarketReviewer._fetch_northbound(date(2024, 6, 15))
            assert flow == 8.0  # 5+3=8亿

    def test_fallback_northbound(self):
        """回退方案"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {"s2": [500.0], "s3": [300.0]}  # 500万+300万 = 800万
        }
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            flow = MarketReviewer._fallback_northbound(date(2024, 6, 15))
            assert flow >= 0.0  # Just verify it returns a positive float

    def test_northbound_api_failure(self):
        """API 失败"""
        with patch("requests.get", side_effect=Exception("error")):
            flow = MarketReviewer._fetch_northbound(date(2024, 6, 15))
            # 应回退到 fallback
            assert isinstance(flow, float)


class TestReviewFundFlow:
    def test_full_fund_flow(self):
        """完整的资金流向获取"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {"f1": 5e8, "f2": 3e8},  # northbound
        }
        mock_response.raise_for_status = MagicMock()

        mock_flow = MagicMock()
        mock_flow.json.return_value = {
            "data": {"s51": [10000.0]}  # 主力净流入 10000万 = 1亿
        }
        mock_flow.raise_for_status = MagicMock()

        with patch("requests.get", side_effect=[mock_response, mock_flow, mock_response]):
            reviewer = MarketReviewer()
            flow = reviewer._review_fund_flow(date(2024, 6, 15))
            assert isinstance(flow, FundFlow)
            assert flow.northbound_flow == 8.0


class TestReview:
    def test_full_review(self):
        """完整复盘流程"""
        # Build a single mock that dispatches by URL + params
        def mock_requests_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            params = kwargs.get("params", {})
            if "ulist.np" in url:
                # index endpoints
                resp.json.return_value = {
                    "data": {"diff": [
                        {"f2": 3030.0, "f3": 1.0, "f4": 1000000},
                        {"f2": 9800.0, "f3": -0.5, "f4": 2000000},
                        {"f2": 2200.0, "f3": 0.8, "f4": 500000},
                        {"f2": 900.0, "f3": -0.3, "f4": 300000},
                    ]},
                }
            elif "clist/get" in url and isinstance(params.get("fs"), str) and "m:90" in params["fs"]:
                # sector endpoint
                resp.json.return_value = {
                    "data": {"diff": [
                        {"f12": "801170", "f14": "计算机", "f3": 2.5, "f2": 3500, "f4": 500000},
                        {"f12": "801710", "f14": "电力设备", "f3": 1.8, "f2": 2800, "f4": 800000},
                        {"f12": "801390", "f14": "电子", "f3": 1.2, "f2": 1500, "f4": 600000},
                        {"f12": "801180", "f14": "医药生物", "f3": -0.5, "f2": 2200, "f4": 400000},
                        {"f12": "801120", "f14": "银行", "f3": -0.3, "f2": 1800, "f4": 300000},
                        {"f12": "801160", "f14": "食品饮料", "f3": -1.2, "f2": 3000, "f4": 700000},
                    ]},
                }
            elif "kamt.s" in url:
                # northbound/southbound endpoint
                resp.json.return_value = {
                    "data": {"f1": 5e8, "f2": 3e8, "s4": [200.0], "s5": [150.0]},
                }
            elif "stock/fflow" in url:
                # net inflow endpoint
                resp.json.return_value = {
                    "data": {"s51": [10000.0]},
                }
            else:
                # search/searchapi (sector leader)
                sector_query = params.get("query", "板块")
                resp.json.return_value = {
                    "query": {"code": [{"name": f"{sector_query}-龙头", "code": "600001"}]},
                }
            return resp

        with patch("requests.get", side_effect=mock_requests_get):
            reviewer = MarketReviewer()
            result = reviewer.review(date(2024, 6, 15))

        assert result["date"] == "2024-06-15"
        assert len(result["indices"]) >= 1
        assert len(result["sectors"]) >= 1
        assert isinstance(result["fund_flow"], FundFlow)
        assert isinstance(result["summary"], str)
        assert "涨" in result["summary"] or "跌" in result["summary"]


class TestMarkdownReport:
    def test_generate_markdown(self):
        """生成 Markdown 报告"""
        def mock_requests_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            params = kwargs.get("params", {})
            if "ulist.np" in url:
                resp.json.return_value = {
                    "data": {"diff": [
                        {"f2": 3030.0, "f3": 1.0, "f4": 1000000},
                    ]},
                }
            elif "clist/get" in url and isinstance(params.get("fs"), str) and "m:90" in params["fs"]:
                resp.json.return_value = {
                    "data": {"diff": [
                        {"f12": "801170", "f14": "计算机", "f3": 2.5, "f2": 3500, "f4": 500000},
                    ]},
                }
            elif "kamt.s" in url:
                resp.json.return_value = {
                    "data": {"f1": 5e8, "f2": 3e8, "s4": [200.0], "s5": [150.0]},
                }
            elif "stock/fflow" in url:
                resp.json.return_value = {
                    "data": {"s51": [10000.0]},
                }
            else:
                sector_query = params.get("query", "板块")
                resp.json.return_value = {
                    "query": {"code": [{"name": f"{sector_query}-龙头", "code": "600001"}]},
                }
            return resp

        with patch("requests.get", side_effect=mock_requests_get):
            reviewer = MarketReviewer()
            md = reviewer.generate_markdown_report(date(2024, 6, 15))

        assert "# 大盘复盘报告" in md
        assert "## 摘要" in md
        assert "## 指数表现" in md
        assert "## 板块轮动" in md
        assert "## 资金流向" in md
        assert "| 名称 | 代码 | 收盘 | 涨跌幅 |" in md
        assert "| 板块 | 涨跌幅 | 领涨股 |" in md


class TestBuildSummary:
    def test_mixed_market(self):
        """混合涨跌市场摘要"""
        indices = [
            MarketIndex("上证", "000001.SH", 3030.0, 1.5, 1000000),
            MarketIndex("深证", "399001.SZ", 9800.0, -0.5, 2000000),
        ]
        sectors = [
            SectorInfo("计算机", 2.5, "龙头A"),
            SectorInfo("银行", -0.3, "龙头B"),
        ]
        flow = FundFlow(net_inflow=5.0, northbound_flow=3.0, southbound_flow=-1.0)

        reviewer = MarketReviewer()
        summary = reviewer._build_summary(indices, sectors, flow)

        assert "1 涨 1 跌" in summary
        assert "▲+1.5%" in summary or "▲1.5%" in summary
        assert "计算机(2.5%)" in summary
        assert "净流入" in summary


class TestHotSectors:
    def test_major_indices_count(self):
        """指数配置完整性"""
        assert len(MAJOR_INDICES) == 4
        assert "上证指数" in MAJOR_INDICES
