# -*- coding: utf-8 -*-
"""F020 Phase C 单元测试 — 采集端补齐

覆盖：
- C1: ResearchCollector（券商研报）
- C2: FinancialCollector（财务报表）
- C3: ExchangeCollector（交易所披露）
- C4: AlphaFeed SDK 修复
- C5: 注册新采集器到 orchestrator
- C6: FAKE_SOURCES 黑名单 + 变更检测
"""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from stockquant.ai.collectors.base import RawInfoItem
from stockquant.ai.collectors.research_collector import ResearchCollector
from stockquant.ai.collectors.financial_collector import FinancialCollector
from stockquant.ai.collectors.exchange_collector import ExchangeCollector
from stockquant.ai.collectors.news_collector import NewsCollector
from stockquant.ai.collectors.verifier import SourceVerifier


def run_async(coro):
    """同步运行异步函数"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def make_mock_df(rows):
    """构造 mock DataFrame：__len__ 返回非零，head().iterrows() 返回指定行"""
    mock_df = MagicMock()
    mock_df.__len__.return_value = len(rows)  # 避免 len(df) == 0 提前返回
    mock_df.head.return_value.iterrows.return_value = list(enumerate(rows))
    return mock_df


# ════════════════════════════════════════════════════════════════════
# C1: ResearchCollector
# ════════════════════════════════════════════════════════════════════

class TestResearchCollector:
    """C1: 券商研报采集器"""

    def test_no_akshare_returns_empty(self):
        """未安装 akshare 时返回空"""
        collector = ResearchCollector(akshare_adapter=None)
        # patch _get_akshare 直接返回 None，绕过懒加载
        with patch.object(collector, "_get_akshare", return_value=None):
            items = run_async(collector.collect(symbol="sh600519"))
        assert items == []

    def test_mock_akshare_collect(self):
        """mock akshare 接口返回研报"""
        mock_ak = MagicMock()
        rows = [
            {
                "研究机构": "中信证券",
                "评级": "买入",
                "目标价": "2000",
                "研究员": "张三",
            },
            {
                "研究机构": "海通证券",
                "评级": "增持",
                "目标价": "1800",
                "研究员": "李四",
            },
        ]
        mock_ak.stock_research_report_em.return_value = make_mock_df(rows)
        collector = ResearchCollector(akshare_adapter=mock_ak)
        items = run_async(collector.collect(symbol="sh600519", limit=5))
        assert len(items) == 2
        assert "中信证券" in items[0].title
        assert items[0].source == "eastmoney_research"
        assert "评级" in items[0].content

    def test_normalize_symbol(self):
        """规范化股票代码"""
        assert ResearchCollector._normalize_symbol("sh600519") == "600519"
        assert ResearchCollector._normalize_symbol("SZ000858") == "000858"
        assert ResearchCollector._normalize_symbol("bj430047") == "430047"
        assert ResearchCollector._normalize_symbol("") == ""

    def test_dedup_by_title(self):
        """按标题去重"""
        mock_ak = MagicMock()
        rows = [
            {"研究机构": "中信", "评级": "买入", "目标价": "", "研究员": ""},
            {"研究机构": "中信", "评级": "买入", "目标价": "", "研究员": ""},
        ]
        mock_ak.stock_research_report_em.return_value = make_mock_df(rows)
        collector = ResearchCollector(akshare_adapter=mock_ak)
        items = run_async(collector.collect(symbol="sh600519", limit=5))
        # 重复研报去重
        assert len(items) == 1

    def test_akshare_exception_returns_empty(self):
        """akshare 调用异常时返回空"""
        mock_ak = MagicMock()
        mock_ak.stock_research_report_em.side_effect = RuntimeError("网络异常")
        collector = ResearchCollector(akshare_adapter=mock_ak)
        items = run_async(collector.collect(symbol="sh600519"))
        assert items == []


# ════════════════════════════════════════════════════════════════════
# C2: FinancialCollector
# ════════════════════════════════════════════════════════════════════

class TestFinancialCollector:
    """C2: 财务报表采集器"""

    def test_no_symbol_returns_empty(self):
        """无 symbol 时返回空"""
        collector = FinancialCollector()
        items = run_async(collector.collect(symbol=""))
        assert items == []

    def test_no_akshare_returns_empty(self):
        """未安装 akshare 时返回空"""
        collector = FinancialCollector(akshare_adapter=None)
        with patch.object(collector, "_get_akshare", return_value=None):
            items = run_async(collector.collect(symbol="sh600519"))
        assert items == []

    def test_mock_sina_financial(self):
        """mock 新浪财务报表接口"""
        mock_ak = MagicMock()
        rows = [
            {
                "报告日": "2024-12-31",
                "主营业务收入": "100亿",
                "净利润": "50亿",
                "每股收益": "5.0",
                "净资产收益率": "30%",
            },
        ]
        mock_ak.stock_financial_report_sina.return_value = make_mock_df(rows)
        # 让东方财富接口返回空，避免干扰
        mock_ak.stock_financial_abstract.return_value = make_mock_df([])
        collector = FinancialCollector(akshare_adapter=mock_ak)
        items = run_async(collector.collect(symbol="sh600519", limit=5))
        assert len(items) >= 1
        assert "sh600519" in items[0].title or "财报" in items[0].title
        assert items[0].source == "sina_financial"

    def test_normalize_symbol(self):
        assert FinancialCollector._normalize_symbol("sh600519") == "600519"
        assert FinancialCollector._normalize_symbol("sz000858") == "000858"


# ════════════════════════════════════════════════════════════════════
# C3: ExchangeCollector
# ════════════════════════════════════════════════════════════════════

class TestExchangeCollector:
    """C3: 交易所披露采集器"""

    def test_no_akshare_returns_empty(self):
        """未安装 akshare 时返回空"""
        collector = ExchangeCollector(akshare_adapter=None)
        with patch.object(collector, "_get_akshare", return_value=None):
            items = run_async(collector.collect(symbol="sh600519"))
        assert items == []

    def test_lhb_collect(self):
        """龙虎榜采集"""
        mock_ak = MagicMock()
        lhb_rows = [
            {
                "上榜日": "2024-01-15",
                "解读": "日涨幅偏离值达7%",
                "龙虎榜净买额": "1.5亿",
            },
        ]
        mock_ak.stock_lhb_detail_em.return_value = make_mock_df(lhb_rows)
        # 让上交所/深交所接口返回空，避免干扰
        mock_ak.stock_sse_summary.return_value = make_mock_df([])
        mock_ak.stock_szse_summary.return_value = make_mock_df([])
        collector = ExchangeCollector(akshare_adapter=mock_ak)
        items = run_async(collector.collect(symbol="sh600519", limit=5))
        assert len(items) >= 1
        assert items[0].source == "exchange_lhb"
        assert "龙虎榜" in items[0].title

    def test_sse_collect(self):
        """上交所披露采集"""
        mock_ak = MagicMock()
        sse_rows = [
            {"成交概况": "总成交额", "数值": "5000亿"},
        ]
        mock_ak.stock_sse_summary.return_value = make_mock_df(sse_rows)
        collector = ExchangeCollector(akshare_adapter=mock_ak)
        items = run_async(collector.collect(symbol="", limit=5))
        assert len(items) >= 1
        assert items[0].source == "sse_disclosure"

    def test_normalize_symbol(self):
        assert ExchangeCollector._normalize_symbol("sh600519") == "600519"


# ════════════════════════════════════════════════════════════════════
# C4: AlphaFeed SDK 修复
# ════════════════════════════════════════════════════════════════════

class TestAlphaFeedFix:
    """C4: AlphaFeed SDK 修复"""

    def test_alphafeed_no_client_falls_back(self):
        """无 AlphaFeed client 时降级到 AkShare"""
        collector = NewsCollector()
        # 不传 api_key，client 应为 None
        assert collector._client is None
        items = run_async(collector.collect(symbol="sh600519"))
        # 不抛异常即可（AkShare 可能因为环境而失败）
        assert isinstance(items, list)

    def test_alphafeed_client_returns_empty_falls_back(self):
        """AlphaFeed client 返回空时降级"""
        mock_alphafeed = MagicMock()
        # 模拟 SDK 已加载但调用返回空
        collector = NewsCollector(api_key="test_key")
        collector._client = mock_alphafeed
        mock_alphafeed.get_news.return_value = []
        items = run_async(collector._collect_alphafeed("sh600519", 5))
        assert items == []

    def test_alphafeed_client_returns_data(self):
        """AlphaFeed client 返回数据"""
        mock_alphafeed = MagicMock()
        mock_alphafeed.get_news.return_value = {
            "data": [
                {
                    "title": "测试新闻",
                    "content": "测试内容",
                    "url": "http://example.com",
                    "source": "alphafeed",
                    "published_at": "2024-01-15T10:00:00",
                }
            ]
        }
        collector = NewsCollector(api_key="test_key")
        collector._client = mock_alphafeed
        items = run_async(collector._collect_alphafeed("sh600519", 5))
        assert len(items) == 1
        assert items[0].title == "测试新闻"
        assert items[0].source == "alphafeed"

    def test_alphafeed_old_api_fallback(self):
        """新版 API 失败时降级到旧版"""
        mock_alphafeed = MagicMock()
        # get_news 抛 AttributeError（模拟旧版无此方法）
        mock_alphafeed.get_news.side_effect = AttributeError("no get_news method")
        mock_alphafeed.news.return_value = [
            {"title": "旧版新闻", "content": "内容", "url": "http://x.com"}
        ]
        collector = NewsCollector(api_key="test_key")
        collector._client = mock_alphafeed
        items = run_async(collector._collect_alphafeed("sh600519", 5))
        assert len(items) == 1
        assert items[0].title == "旧版新闻"

    def test_alphafeed_exception_returns_empty(self):
        """SDK 抛异常时返回空"""
        mock_alphafeed = MagicMock()
        mock_alphafeed.get_news.side_effect = RuntimeError("服务不可用")
        mock_alphafeed.news.side_effect = RuntimeError("旧版也不可用")
        collector = NewsCollector(api_key="test_key")
        collector._client = mock_alphafeed
        items = run_async(collector._collect_alphafeed("sh600519", 5))
        assert items == []


# ════════════════════════════════════════════════════════════════════
# C5: 注册新采集器到 orchestrator
# ════════════════════════════════════════════════════════════════════

class TestOrchestratorCollectors:
    """C5: orchestrator 注册新采集器"""

    def test_orchestrator_includes_new_collectors(self):
        """orchestrator 应包含 6 个采集器（3 旧 + 3 新）"""
        from stockquant.ai.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator()
        collector_names = [c.name for c in orch._collectors]
        # 旧采集器
        assert "news" in collector_names
        assert "announcement" in collector_names
        assert "social" in collector_names
        # C1-C3 新采集器
        assert "research" in collector_names
        assert "financial" in collector_names
        assert "exchange" in collector_names
        assert len(orch._collectors) == 6


# ════════════════════════════════════════════════════════════════════
# C6: FAKE_SOURCES 黑名单 + 变更检测
# ════════════════════════════════════════════════════════════════════

class TestFakeSourcesBlacklist:
    """C6: 仿冒源黑名单"""

    def test_initial_fake_sources(self):
        """初始黑名单预置"""
        verifier = SourceVerifier()
        # 预置仿冒源
        assert verifier.is_fake_source("fake-eastmoney")
        assert verifier.is_fake_source("spam-news")
        assert verifier.is_fake_source("stock-tip-xxx")

    def test_add_fake_source(self):
        """动态添加单个仿冒源"""
        verifier = SourceVerifier()
        verifier.add_fake_source("new-fake-source")
        assert verifier.is_fake_source("new-fake-source")
        # 大小写不敏感
        verifier.add_fake_source("ANOTHER-FAKE")
        assert verifier.is_fake_source("another-fake")

    def test_register_fake_sources_batch(self):
        """批量添加仿冒源"""
        verifier = SourceVerifier()
        added = verifier.register_fake_sources(["batch1", "batch2", "batch3"])
        assert added == 3
        assert verifier.is_fake_source("batch1")
        assert verifier.is_fake_source("batch2")
        assert verifier.is_fake_source("batch3")

    def test_register_duplicate_sources(self):
        """重复添加不增加计数"""
        verifier = SourceVerifier()
        # 先添加一个
        verifier.add_fake_source("dup-source")
        # 再批量添加，包含重复
        added = verifier.register_fake_sources(["dup-source", "new1"])
        assert added == 1  # 只有 new1 是新增

    def test_is_fake_source_empty(self):
        """空字符串不在黑名单"""
        verifier = SourceVerifier()
        assert not verifier.is_fake_source("")
        assert not verifier.is_fake_source(None)

    def test_get_fake_sources_returns_copy(self):
        """get_fake_sources 返回黑名单副本（修改不影响原黑名单）"""
        verifier = SourceVerifier()
        sources = verifier.get_fake_sources()
        sources.add("temp-source")
        # 原黑名单不应包含 temp-source
        assert not verifier.is_fake_source("temp-source")

    def test_verify_filters_fake_sources(self):
        """verify 过滤黑名单中的来源"""
        verifier = SourceVerifier()
        verifier.add_fake_source("fake-test-source")
        items = [
            RawInfoItem(source="eastmoney", title="可信", content="c"),
            RawInfoItem(source="fake-test-source", title="仿冒", content="c"),
        ]
        result = verifier.verify(items)
        titles = [i.title for i in result]
        assert "可信" in titles
        assert "仿冒" not in titles

    def test_trusted_sources_includes_new(self):
        """TRUSTED_SOURCES 包含新采集器的源"""
        # C6: 新增可信源
        assert "eastmoney_research" in SourceVerifier.TRUSTED_SOURCES
        assert "sina_financial" in SourceVerifier.TRUSTED_SOURCES
        assert "exchange_lhb" in SourceVerifier.TRUSTED_SOURCES
        assert "alphafeed" in SourceVerifier.TRUSTED_SOURCES


class TestSourceChangeDetection:
    """C6: 数据源变更检测"""

    def test_first_call_no_change(self):
        """首次采集不触发变更告警"""
        verifier = SourceVerifier()
        result = verifier.detect_source_change("eastmoney", "first response")
        assert result["source"] == "eastmoney"
        assert result["changed"] is False
        assert result["previous_fingerprint"] is None
        assert result["current_fingerprint"] != ""

    def test_same_response_no_change(self):
        """相同响应不触发变更"""
        verifier = SourceVerifier()
        verifier.detect_source_change("eastmoney", "same response")
        result = verifier.detect_source_change("eastmoney", "same response")
        assert result["changed"] is False
        assert result["current_fingerprint"] == result["previous_fingerprint"]

    def test_different_response_triggers_change(self):
        """响应变化时触发变更告警"""
        verifier = SourceVerifier()
        verifier.detect_source_change("eastmoney", "first response")
        result = verifier.detect_source_change("eastmoney", "changed response")
        assert result["changed"] is True
        assert result["current_fingerprint"] != result["previous_fingerprint"]

    def test_empty_response(self):
        """空响应的指纹为空字符串"""
        verifier = SourceVerifier()
        result = verifier.detect_source_change("source", "")
        assert result["current_fingerprint"] == ""
        assert result["changed"] is False  # 首次仍为 False

    def test_multiple_sources_independent(self):
        """不同源的指纹独立缓存"""
        verifier = SourceVerifier()
        r1 = verifier.detect_source_change("source_a", "content_a")
        r2 = verifier.detect_source_change("source_b", "content_b")
        assert r1["current_fingerprint"] != r2["current_fingerprint"]
        # 各自再次采集相同内容，都不应触发变更
        r1_2 = verifier.detect_source_change("source_a", "content_a")
        r2_2 = verifier.detect_source_change("source_b", "content_b")
        assert r1_2["changed"] is False
        assert r2_2["changed"] is False
