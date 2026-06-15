# -*- coding: utf-8 -*-
"""F020 Pipeline + Memory + Hallucination 单元测试"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from stockquant.ai.pipeline.collection import (
    CollectionEvent,
    CollectionStage,
    RawArticle,
)
from stockquant.ai.pipeline.denoise import DenoiseStage
from stockquant.ai.pipeline.summarize import SummarizeStage
from stockquant.ai.pipeline.elevate import ElevateStage
from stockquant.ai.pipeline_orchestrator import InformationProcessingPipeline
from stockquant.ai.memory.working import WorkingMemory
from stockquant.ai.memory.short_term import ShortTermMemory
from stockquant.ai.memory.long_term import LongTermMemory
from stockquant.ai.memory.system import MemorySystem
from stockquant.ai.hallucination.pipeline import HallucinationPipeline, FactDatabase, HallucinationDB


class TestCollectionStage:
    """测试采集阶段"""

    def test_execute_empty_event(self):
        stage = CollectionStage()
        event = CollectionEvent(symbols=["sh600519"], sources=[])
        articles = stage.execute(event)
        assert isinstance(articles, list)

    def test_execute_with_news_searcher_noop(self):
        """news_searcher 不存在时静默处理，返回空列表"""
        stage = CollectionStage()
        event = CollectionEvent(symbols=["sh600519"], sources=["news_searcher"])
        articles = stage.execute(event)
        assert isinstance(articles, list)

    def test_event_creation(self):
        event = CollectionEvent(symbols=["sh600519", "sz000858"])
        assert event.symbols == ["sh600519", "sz000858"]
        assert event.sources == []


class TestRawArticle:
    """测试 RawArticle 数据类"""

    def test_defaults(self):
        a = RawArticle(title="t", content="c", url="u", source="s")
        assert a.published_at is None
        assert a.raw == {}


class TestDenoiseStage:
    """测试降噪阶段"""

    def test_empty_input(self):
        stage = DenoiseStage()
        assert stage.execute([]) == []

    def test_temporal_filter(self):
        stage = DenoiseStage(max_age_hours=1)
        old_time = datetime(2020, 1, 1)
        articles = [
            RawArticle(title="past", content="c", url="u", source="s", published_at=old_time),
            RawArticle(title="recent", content="c", url="u", source="s", published_at=datetime.now()),
        ]
        result = stage.execute(articles)
        assert len(result) == 1
        assert result[0].title == "recent"

    def test_deduplication(self):
        stage = DenoiseStage()
        articles = [
            RawArticle(title="A", content="c1", url="u1", source="s"),
            RawArticle(title="A", content="c2", url="u2", source="s"),
            RawArticle(title="B", content="d", url="u3", source="s"),
        ]
        result = stage.execute(articles)
        assert len(result) == 2

    def test_source_ranking(self):
        stage = DenoiseStage()
        articles = [
            RawArticle(title="A", content="c", url="u", source="xueqiu"),
            RawArticle(title="B", content="c", url="u", source="cninfo"),
        ]
        result = stage.execute(articles)
        assert result[0].source == "cninfo"


class TestSummarizeStage:
    """测试总结阶段"""

    def test_empty_input(self):
        stage = SummarizeStage()
        result = stage.execute([])
        assert result["summary"] == "无有效信息"

    def test_summary_generation(self):
        stage = SummarizeStage()
        articles = [
            RawArticle(title="T1", content="content1", url="u1", source="news_searcher"),
            RawArticle(title="T2", content="content2", url="u2", source="news_searcher"),
        ]
        result = stage.execute(articles)
        assert "共采集 2 条信息" in result["summary"]
        assert result["article_count"] == 2


class TestElevateStage:
    """测试升华阶段"""

    def test_with_verified_summary(self):
        stage = ElevateStage()
        summary = {"verified": True, "article_count": 5, "summary": "test"}
        result = stage.execute(summary)
        assert len(result["insights"]) > 0
        assert result["insights"][0]["type"] == "confirmed_trend"

    def test_with_no_articles(self):
        stage = ElevateStage()
        result = stage.execute({"verified": False, "article_count": 0})
        assert len(result["insights"]) == 0


class TestPipelineOrchestrator:
    """测试流程编排器"""

    def test_run(self):
        pipeline = InformationProcessingPipeline()
        result = pipeline.run(["sh600519"], sources=[])
        assert "articles_processed" in result
        assert "filtered_count" in result
        assert "summary" in result
        assert "insights" in result
        assert "hallucination_check" in result

    def test_run_single_symbol(self):
        pipeline = InformationProcessingPipeline()
        result = pipeline.run_single_symbol("sh600519")
        assert isinstance(result, dict)


class TestWorkingMemory:
    """测试 L1 工作记忆（memory 模块）"""

    def test_append_and_get_recent(self):
        mem = WorkingMemory(max_size=10)
        for i in range(5):
            mem.append({"id": i})
        assert len(mem.get_recent(3)) == 3

    def test_max_size_eviction(self):
        mem = WorkingMemory(max_size=5)
        for i in range(20):
            mem.append({"id": i})
        assert len(mem.get_recent(10)) <= 5

    def test_query_by_symbol(self):
        mem = WorkingMemory()
        mem.append({"symbol": "sh600519"})
        mem.append({"symbol": "sz000858"})
        results = mem.query(symbol="sh600519")
        assert len(results) == 1

    def test_get_sentiment_baseline(self):
        mem = WorkingMemory()
        for _ in range(10):
            mem.append({"symbol": "sh600519", "sentiment": 0.5})
        baseline = mem.get_sentiment_baseline("sh600519")
        assert abs(baseline - 0.5) < 0.01

    def test_sentiment_baseline_no_data(self):
        mem = WorkingMemory()
        assert mem.get_sentiment_baseline("unknown") == 0.0

    def test_clear(self):
        mem = WorkingMemory()
        mem.append({"id": 1})
        mem.clear()
        assert mem.get_recent(10) == []


class TestShortTermMemory:
    """测试 L2 短期记忆"""

    def test_add_and_search(self):
        mem = ShortTermMemory()
        mem.add("sh600519", "贵州茅台利好消息")
        results = mem.search(symbol="sh600519")
        assert len(results) == 1
        assert "贵州茅台" in results[0]["content"]

    def test_keyword_search(self):
        mem = ShortTermMemory()
        mem.add("sh600519", "贵州茅台")
        mem.add("sz000858", "五粮液")
        results = mem.search(keyword="茅台")
        assert len(results) == 1

    def test_delete(self):
        mem = ShortTermMemory()
        id_ = mem.add("sh600519", "test")
        assert mem.delete(id_) is True
        assert mem.count() == 0

    def test_clear(self):
        mem = ShortTermMemory()
        mem.add("sh600519", "test")
        mem.clear()
        assert mem.count() == 0


class TestLongTermMemory:
    """测试 L3 长期记忆"""

    def test_add_and_search(self):
        mem = LongTermMemory()
        mem.add({"symbol": "sh600519", "confidence": 0.9})
        results = mem.search(symbol="sh600519")
        assert len(results) == 1

    def test_min_confidence_filter(self):
        mem = LongTermMemory()
        mem.add({"symbol": "sh600519", "confidence": 0.3})
        mem.add({"symbol": "sh600519", "confidence": 0.9})
        results = mem.search(symbol="sh600519", min_confidence=0.5)
        assert len(results) == 1
        assert results[0]["confidence"] == 0.9


class TestMemorySystem:
    """测试记忆系统编排"""

    def test_add_and_retrieve_all_layers(self):
        ms = MemorySystem()
        ms.add_working({"symbol": "sh600519"})
        ms.add_short_term("sh600519", "test content")
        ms.add_long_term({"symbol": "sh600519", "confidence": 0.8, "insight": "test insight"})

        assert len(ms.get_recent(1)) == 1
        assert len(ms.search_short_term(keyword="test")) == 1
        assert len(ms.search_long_term(keyword="test")) == 1

    def test_sentiment_baseline(self):
        ms = MemorySystem()
        for _ in range(5):
            ms.add_working({"symbol": "sh600519", "sentiment": 0.7})
        baseline = ms.get_sentiment_baseline("sh600519")
        assert abs(baseline - 0.7) < 0.01


class TestHallucinationPipeline:
    """测试反幻觉管线"""

    def test_pass_with_valid_articles(self):
        articles = [
            RawArticle(title="A", content="real content here", url="http://example.com", source="cninfo"),
            RawArticle(title="B", content="more content", url="http://example.com", source="eastmoney"),
        ]
        pipeline = HallucinationPipeline()
        result = pipeline.execute(articles)
        assert result["passed"] is True

    def test_fail_with_no_content(self):
        articles = [
            RawArticle(title="X", content="", url="", source="unknown"),
        ]
        pipeline = HallucinationPipeline()
        result = pipeline.execute(articles)
        assert "scores" in result

    def test_strict_mode(self):
        pipeline = HallucinationPipeline(strict_mode=True)
        result = pipeline.execute([])
        assert result["passed"] is True  # Empty articles = no hallucination

    def test_empty_input(self):
        pipeline = HallucinationPipeline()
        result = pipeline.execute([])
        assert result["passed"] is True
        assert result["issues"] == []


class TestFactDatabase:
    """测试事实库"""

    def test_add_and_search(self):
        db = FactDatabase()
        db.add({"symbol": "sh600519", "fact": "贵州茅台股价"})
        results = db.search("茅台")
        assert len(results) >= 1

    def test_count(self):
        db = FactDatabase()
        assert db.count() == 0
        db.add({})
        assert db.count() == 1


class TestHallucinationDB:
    """测试幻觉数据库"""

    def test_add_and_search(self):
        db = HallucinationDB()
        db.add({"symbol": "sh600519", "type": "hallucination"})
        results = db.search(symbol="sh600519")
        assert len(results) == 1
