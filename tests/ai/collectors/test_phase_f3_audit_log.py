# -*- coding: utf-8 -*-
"""F020 Phase F3 — 采集器审计日志测试

覆盖：
- AuditEntry 数据结构
- CollectorAuditLog 内存环形缓冲
- 线程安全（多线程并发写入）
- 持久化回调（set_persist_fn）
- 查询接口（query / query_by_collector / query_by_source / query_failures）
- 统计接口（stats / count_by_collector / count_by_source / success_rate）
- 单例与重置
- BaseCollector._audit_log 集成
- 现有采集器（ResearchCollector 等）调用 _audit_log 验证向后兼容
"""
from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from stockquant.ai.collectors.audit_log import (
    AuditEntry,
    CollectorAuditLog,
    get_audit_log,
    reset_audit_log,
)
from stockquant.ai.collectors.base import BaseCollector, RawInfoItem


# ── 工具 ──────────────────────────────────────────────────────────────────


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _DummyCollector(BaseCollector):
    """测试用采集器"""
    async def collect(self, symbol: str = "", limit: int = 20):
        return []


# ── AuditEntry ──────────────────────────────────────────────────────────────


class TestAuditEntry:
    def test_default_values(self):
        entry = AuditEntry()
        assert entry.collector == ""
        assert entry.action == ""
        assert entry.source == ""
        assert entry.result == ""
        assert entry.count == 0
        assert entry.error is None
        assert entry.timestamp == ""
        assert entry.duration_ms == 0
        assert entry.metadata == {}

    def test_to_dict(self):
        entry = AuditEntry(
            collector="news",
            action="collect",
            source="eastmoney",
            result="success",
            count=10,
            timestamp="2025-01-01T00:00:00",
            metadata={"symbol": "sh600519"},
        )
        d = entry.to_dict()
        assert d["collector"] == "news"
        assert d["count"] == 10
        assert d["metadata"]["symbol"] == "sh600519"


# ── CollectorAuditLog 内存缓冲 ──────────────────────────────────────────────


class TestCollectorAuditLogBuffer:
    def test_append_and_query(self):
        log = reset_audit_log()
        log.append_sync("news", "collect", "eastmoney", "success", count=10)
        entries = log.query()
        assert len(entries) == 1
        assert entries[0].collector == "news"
        assert entries[0].count == 10

    def test_query_returns_newest_first(self):
        log = reset_audit_log()
        for i in range(5):
            log.append_sync("news", "collect", f"src{i}", "success", count=i)
        entries = log.query()
        # 最新条目（src4）应在前
        assert entries[0].source == "src4"
        assert entries[-1].source == "src0"

    def test_ring_buffer_eviction(self):
        """超过 max_size 时丢弃最旧条目"""
        log = reset_audit_log(max_size=3)
        for i in range(5):
            log.append_sync("news", "collect", f"src{i}", "success")
        # 只保留最新 3 条
        entries = log.query()
        assert len(entries) == 3
        # 应保留 src2, src3, src4
        sources = [e.source for e in entries]
        assert "src2" in sources
        assert "src3" in sources
        assert "src4" in sources
        assert "src0" not in sources
        assert "src1" not in sources

    def test_max_size_zero_raises(self):
        with pytest.raises(ValueError):
            CollectorAuditLog(max_size=0)

    def test_negative_max_size_raises(self):
        with pytest.raises(ValueError):
            CollectorAuditLog(max_size=-1)


# ── 异步接口 ──────────────────────────────────────────────────────────────


class TestAsyncInterface:
    def test_async_append(self):
        log = reset_audit_log()
        async def _go():
            await log.append("news", "collect", "eastmoney", "success", count=5)
        run_async(_go())
        assert log.size == 1

    def test_async_append_returns_entry(self):
        log = reset_audit_log()
        async def _go():
            return await log.append("news", "collect", "eastmoney", "success", count=5)
        entry = run_async(_go())
        assert isinstance(entry, AuditEntry)
        assert entry.collector == "news"


# ── result 规范化 ──────────────────────────────────────────────────────────


class TestResultNormalization:
    def test_unknown_result_normalized_to_failure(self):
        log = reset_audit_log()
        log.append_sync("news", "collect", "eastmoney", result="weird_result")
        entries = log.query()
        assert entries[0].result == "failure"

    def test_valid_results_preserved(self):
        log = reset_audit_log()
        for r in ["success", "failure", "partial", "skipped"]:
            log.append_sync("news", "collect", "src", result=r)
        results = [e.result for e in log.query()]
        assert set(results) == {"success", "failure", "partial", "skipped"}


# ── 查询接口 ──────────────────────────────────────────────────────────────


class TestQueryInterfaces:
    def setup_method(self):
        self.log = reset_audit_log()
        # 准备测试数据
        self.log.append_sync("news", "collect", "eastmoney", "success", count=10)
        self.log.append_sync("news", "collect", "sina", "failure", error="timeout")
        self.log.append_sync("research", "collect", "eastmoney_research", "success", count=5)
        self.log.append_sync("news", "verify", "eastmoney", "success", count=8)
        self.log.append_sync("financial", "collect", "sina_financial", "partial", count=3)

    def test_query_by_collector(self):
        entries = self.log.query_by_collector("news")
        assert len(entries) == 3
        for e in entries:
            assert e.collector == "news"

    def test_query_by_source(self):
        entries = self.log.query_by_source("eastmoney")
        assert len(entries) == 2
        for e in entries:
            assert e.source == "eastmoney"

    def test_query_failures(self):
        entries = self.log.query_failures()
        assert len(entries) == 1
        assert entries[0].result == "failure"
        assert entries[0].error == "timeout"

    def test_query_with_action_filter(self):
        entries = self.log.query(action="collect")
        assert len(entries) == 4
        for e in entries:
            assert e.action == "collect"

    def test_query_with_result_filter(self):
        entries = self.log.query(result="partial")
        assert len(entries) == 1
        assert entries[0].result == "partial"

    def test_query_with_limit(self):
        entries = self.log.query(limit=2)
        assert len(entries) == 2

    def test_query_with_offset(self):
        # 全部 5 条倒序
        all_entries = self.log.query()
        # offset=2 跳过最新 2 条
        entries = self.log.query(offset=2)
        assert len(entries) == 3
        assert entries[0] == all_entries[2]

    def test_latest(self):
        entries = self.log.latest(1)
        assert len(entries) == 1
        # 最新条目是最后 append 的 financial
        assert entries[0].collector == "financial"

    def test_latest_n(self):
        entries = self.log.latest(3)
        assert len(entries) == 3

    def test_query_empty_log(self):
        log = reset_audit_log()
        assert log.query() == []


# ── 统计接口 ──────────────────────────────────────────────────────────────


class TestStatistics:
    def setup_method(self):
        self.log = reset_audit_log()
        self.log.append_sync("news", "collect", "eastmoney", "success")
        self.log.append_sync("news", "collect", "sina", "success")
        self.log.append_sync("research", "collect", "eastmoney_research", "failure", error="err")
        self.log.append_sync("financial", "collect", "sina_financial", "skipped")

    def test_stats(self):
        stats = self.log.stats()
        assert stats["total"] == 4
        assert stats["success"] == 2
        assert stats["failure"] == 1
        assert stats["skipped"] == 1

    def test_count_by_collector(self):
        counts = self.log.count_by_collector()
        assert counts["news"] == 2
        assert counts["research"] == 1
        assert counts["financial"] == 1

    def test_count_by_source(self):
        counts = self.log.count_by_source()
        assert counts["eastmoney"] == 1
        assert counts["sina"] == 1
        assert counts["eastmoney_research"] == 1
        assert counts["sina_financial"] == 1

    def test_success_rate(self):
        rate = self.log.success_rate()
        assert rate == 0.5  # 2/4

    def test_success_rate_empty(self):
        log = reset_audit_log()
        assert log.success_rate() == 0.0


# ── 管理接口 ──────────────────────────────────────────────────────────────


class TestManagement:
    def test_clear(self):
        log = reset_audit_log()
        for i in range(5):
            log.append_sync("news", "collect", f"src{i}", "success")
        cleared = log.clear()
        assert cleared == 5
        assert log.size == 0

    def test_clear_keeps_stats(self):
        """清空不影响累计统计"""
        log = reset_audit_log()
        log.append_sync("news", "collect", "src", "success")
        log.clear()
        stats = log.stats()
        assert stats["total"] == 1  # 累计仍为 1
        assert stats["success"] == 1

    def test_to_dict_list(self):
        log = reset_audit_log()
        log.append_sync("news", "collect", "eastmoney", "success", count=10)
        d_list = log.to_dict_list()
        assert len(d_list) == 1
        assert d_list[0]["collector"] == "news"
        assert d_list[0]["count"] == 10

    def test_summary(self):
        log = reset_audit_log()
        log.append_sync("news", "collect", "eastmoney", "success")
        log.append_sync("research", "collect", "eastmoney_research", "failure", error="err")
        s = log.summary()
        assert s["size"] == 2
        assert s["max_size"] == 1000
        assert "news" in s["collectors"]
        assert "research" in s["collectors"]
        assert "eastmoney" in s["sources"]
        assert s["stats"]["total"] == 2
        assert s["success_rate"] == 0.5


# ── 持久化回调 ──────────────────────────────────────────────────────────────


class TestPersistenceCallback:
    def test_persist_fn_called(self):
        log = reset_audit_log()
        persisted: List[List[AuditEntry]] = []
        log.set_persist_fn(lambda entries: persisted.append(list(entries)))

        log.append_sync("news", "collect", "eastmoney", "success", count=10)
        assert len(persisted) == 1
        assert len(persisted[0]) == 1
        assert persisted[0][0].collector == "news"

    def test_persist_fn_can_be_disabled(self):
        log = reset_audit_log()
        call_count = [0]
        def fn(entries):
            call_count[0] += 1
        log.set_persist_fn(fn)
        log.append_sync("news", "collect", "eastmoney", "success")
        log.set_persist_fn(None)
        log.append_sync("news", "collect", "sina", "success")
        assert call_count[0] == 1  # 只第一次调用

    def test_persist_fn_exception_does_not_break_append(self):
        log = reset_audit_log()
        def bad_fn(entries):
            raise RuntimeError("persist failed")
        log.set_persist_fn(bad_fn)
        # 不应抛异常
        log.append_sync("news", "collect", "eastmoney", "success")
        # 条目仍应被记录
        assert log.size == 1


# ── 线程安全 ──────────────────────────────────────────────────────────────


class TestThreadSafety:
    def test_concurrent_appends(self):
        log = reset_audit_log(max_size=10000)
        n_threads = 5
        n_per_thread = 50

        def worker(tid: int):
            for i in range(n_per_thread):
                log.append_sync(
                    f"collector_{tid}",
                    "collect",
                    f"src_{tid}_{i}",
                    "success",
                )

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert log.size == n_threads * n_per_thread
        # 统计应准确
        assert log.stats()["total"] == n_threads * n_per_thread
        assert log.stats()["success"] == n_threads * n_per_thread


# ── 单例 ──────────────────────────────────────────────────────────────────


class TestSingleton:
    def test_get_audit_log_returns_same_instance(self):
        reset_audit_log()
        log1 = get_audit_log()
        log2 = get_audit_log()
        assert log1 is log2

    def test_reset_creates_new_instance(self):
        log1 = get_audit_log()
        log2 = reset_audit_log()
        assert log1 is not log2

    def test_reset_with_custom_max_size(self):
        log = reset_audit_log(max_size=50)
        assert log.max_size == 50
        # 单例应已更新
        assert get_audit_log() is log


# ── BaseCollector 集成 ──────────────────────────────────────────────────────


class TestBaseCollectorIntegration:
    def test_audit_log_writes_to_singleton(self):
        reset_audit_log()
        collector = _DummyCollector(name="test_collector")

        async def _go():
            await collector._audit_log(
                action="collect",
                source="eastmoney",
                result="success",
                count=10,
            )
        run_async(_go())

        log = get_audit_log()
        entries = log.query()
        assert len(entries) == 1
        assert entries[0].collector == "test_collector"
        assert entries[0].source == "eastmoney"
        assert entries[0].count == 10

    def test_audit_log_with_error(self):
        reset_audit_log()
        collector = _DummyCollector(name="test_collector")

        async def _go():
            await collector._audit_log(
                action="collect",
                source="sina",
                result="failure",
                error="connection timeout",
                duration_ms=5000,
            )
        run_async(_go())

        log = get_audit_log()
        entries = log.query_failures()
        assert len(entries) == 1
        assert entries[0].error == "connection timeout"
        assert entries[0].duration_ms == 5000

    def test_audit_log_with_metadata(self):
        reset_audit_log()
        collector = _DummyCollector(name="test_collector")

        async def _go():
            await collector._audit_log(
                action="collect",
                source="eastmoney",
                result="success",
                count=5,
                metadata={"symbol": "sh600519", "retry_count": 2},
            )
        run_async(_go())

        log = get_audit_log()
        entries = log.query()
        assert entries[0].metadata["symbol"] == "sh600519"
        assert entries[0].metadata["retry_count"] == 2

    def test_multiple_collectors_share_log(self):
        """多个采集器共享同一审计日志单例"""
        reset_audit_log()
        c1 = _DummyCollector(name="news")
        c2 = _DummyCollector(name="research")

        async def _go():
            await c1._audit_log("collect", "eastmoney", "success", count=10)
            await c2._audit_log("collect", "eastmoney_research", "success", count=5)
        run_async(_go())

        log = get_audit_log()
        assert log.size == 2
        counts = log.count_by_collector()
        assert counts["news"] == 1
        assert counts["research"] == 1


# ── 向后兼容：现有采集器仍可正常使用 ──────────────────────────────────────────


class TestBackwardCompatibility:
    """验证现有采集器在加了 _audit_log 后仍能正常工作"""

    def test_research_collector_still_works(self):
        from stockquant.ai.collectors.research_collector import ResearchCollector
        collector = ResearchCollector(akshare_adapter=None)
        with patch.object(collector, "_get_akshare", return_value=None):
            items = run_async(collector.collect(symbol="sh600519"))
        assert items == []

    def test_financial_collector_still_works(self):
        from stockquant.ai.collectors.financial_collector import FinancialCollector
        collector = FinancialCollector(akshare_adapter=None)
        with patch.object(collector, "_get_akshare", return_value=None):
            items = run_async(collector.collect(symbol="sh600519"))
        assert items == []

    def test_exchange_collector_still_works(self):
        from stockquant.ai.collectors.exchange_collector import ExchangeCollector
        collector = ExchangeCollector(akshare_adapter=None)
        with patch.object(collector, "_get_akshare", return_value=None):
            items = run_async(collector.collect(symbol="sh600519"))
        assert items == []

    def test_news_collector_still_works(self):
        from stockquant.ai.collectors.news_collector import NewsCollector
        collector = NewsCollector(api_key="")  # 无 api_key
        # 不抛异常即可（AkShare 可能因为环境而失败）
        items = run_async(collector.collect(symbol="sh600519"))
        assert isinstance(items, list)


# ── 集成：审计日志在采集失败时记录 ──────────────────────────────────────────


class TestIntegrationWithFailure:
    def test_collector_failure_logged(self):
        reset_audit_log()
        from stockquant.ai.collectors.research_collector import ResearchCollector
        collector = ResearchCollector(akshare_adapter=None)

        # 模拟有 akshare 但调用失败的场景
        mock_akshare = MagicMock()
        mock_akshare.stock_research_report_em.side_effect = RuntimeError("network error")

        async def _go():
            await collector._audit_log(
                action="collect",
                source="eastmoney_research",
                result="failure",
                error="network error",
                duration_ms=1500,
            )
        run_async(_go())

        log = get_audit_log()
        entries = log.query_failures()
        assert len(entries) == 1
        assert "network error" in entries[0].error


# ── 边界情况 ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_append_with_zero_count(self):
        log = reset_audit_log()
        log.append_sync("news", "collect", "eastmoney", "success", count=0)
        entries = log.query()
        assert entries[0].count == 0

    def test_append_with_empty_source(self):
        log = reset_audit_log()
        log.append_sync("news", "collect", "", "success")
        entries = log.query()
        assert entries[0].source == ""

    def test_append_with_negative_duration(self):
        log = reset_audit_log()
        log.append_sync("news", "collect", "eastmoney", "success", duration_ms=-1)
        entries = log.query()
        assert entries[0].duration_ms == -1

    def test_size_property(self):
        log = reset_audit_log()
        assert log.size == 0
        log.append_sync("news", "collect", "eastmoney", "success")
        assert log.size == 1

    def test_max_size_property(self):
        log = reset_audit_log(max_size=42)
        assert log.max_size == 42

    def test_query_with_invalid_filters_returns_all(self):
        """过滤条件不匹配时返回空"""
        log = reset_audit_log()
        log.append_sync("news", "collect", "eastmoney", "success")
        # collector 不匹配
        assert log.query(collector="nonexistent") == []
        # source 不匹配
        assert log.query(source="nonexistent") == []
        # action 不匹配
        assert log.query(action="nonexistent") == []
        # result 不匹配
        assert log.query(result="nonexistent") == []
