# -*- coding: utf-8 -*-
"""F020 Phase F4 — 数据源变更检测集成到管线测试

覆盖：
- CollectionStage 变更检测开关
- detect_source_changes 方法
- 首次采集不报变更（无指纹缓存）
- 二次采集相同内容不报变更
- 二次采集不同内容报变更
- 检测到变更时写入审计日志
- 注入自定义 verifier
- 禁用变更检测
- 多源同时检测
- 空文章列表跳过检测
- 向后兼容：旧调用 execute(event) 不受影响
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from stockquant.ai.pipeline.collection import (
    CollectionEvent,
    CollectionStage,
    RawArticle,
)
from stockquant.ai.collectors.audit_log import reset_audit_log, get_audit_log
from stockquant.ai.collectors.verifier import SourceVerifier


# ── 工具 ──────────────────────────────────────────────────────────────────


def _make_articles(source: str, content: str, n: int = 2) -> List[RawArticle]:
    """构造测试文章列表"""
    return [
        RawArticle(
            title=f"标题 {i}",
            content=f"{content} #{i}",
            url=f"http://x/{source}/{i}",
            source=source,
            published_at=datetime.now(),
            raw={"symbol": "sh600519"},
        )
        for i in range(n)
    ]


# ── CollectionStage 变更检测开关 ──────────────────────────────────────────


class TestChangeDetectionToggle:
    def test_default_enabled(self):
        stage = CollectionStage()
        assert stage._enable_change_detection is True

    def test_can_disable(self):
        stage = CollectionStage(enable_change_detection=False)
        assert stage._enable_change_detection is False

    def test_can_inject_verifier(self):
        mock_verifier = MagicMock(spec=["detect_source_change"])
        stage = CollectionStage(verifier=mock_verifier)
        assert stage._verifier is mock_verifier


# ── _get_change_detector ──────────────────────────────────────────────────


class TestGetChangeDetector:
    def test_uses_injected_verifier(self):
        mock_verifier = MagicMock(spec=["detect_source_change"])
        stage = CollectionStage(verifier=mock_verifier)
        detector = stage._get_change_detector()
        assert detector is mock_verifier

    def test_lazy_creates_source_verifier(self):
        """未注入 verifier 时懒加载创建 SourceVerifier"""
        stage = CollectionStage()
        detector = stage._get_change_detector()
        assert isinstance(detector, SourceVerifier)
        # 再次调用返回同一实例
        assert stage._get_change_detector() is detector


# ── detect_source_changes 方法 ─────────────────────────────────────────────


class TestDetectSourceChanges:
    def test_empty_articles_returns_empty(self):
        stage = CollectionStage()
        changes = stage.detect_source_changes([])
        assert changes == []

    def test_first_collection_no_change(self):
        """首次采集无指纹缓存，不报变更"""
        reset_audit_log()
        stage = CollectionStage()
        articles = _make_articles("eastmoney", "茅台 利好 上涨")
        changes = stage.detect_source_changes(articles)
        # 首次无变更
        assert changes == []

    def test_same_content_no_change(self):
        """二次采集相同内容不报变更"""
        reset_audit_log()
        stage = CollectionStage()
        articles = _make_articles("eastmoney", "茅台 利好 上涨")
        # 第一次
        stage.detect_source_changes(articles)
        # 第二次相同内容
        changes = stage.detect_source_changes(articles)
        assert changes == []

    def test_different_content_reports_change(self):
        """二次采集不同内容报变更"""
        reset_audit_log()
        stage = CollectionStage()
        articles1 = _make_articles("eastmoney", "茅台 利好 上涨")
        articles2 = _make_articles("eastmoney", "五粮液 利空 下跌 完全不同的内容")
        # 第一次
        stage.detect_source_changes(articles1)
        # 第二次不同内容
        changes = stage.detect_source_changes(articles2)
        assert len(changes) == 1
        assert changes[0]["source"] == "eastmoney"
        assert changes[0]["changed"] is True

    def test_multiple_sources_detected(self):
        """多源同时变更检测"""
        reset_audit_log()
        stage = CollectionStage()
        # 第一次 eastmoney 和 sina 各有内容
        stage.detect_source_changes(
            _make_articles("eastmoney", "茅台 利好") +
            _make_articles("sina", "茅台 上涨")
        )
        # 第二次两个源都变了
        changes = stage.detect_source_changes(
            _make_articles("eastmoney", "完全不同 内容") +
            _make_articles("sina", "另一个 不同 内容")
        )
        assert len(changes) == 2
        sources = [c["source"] for c in changes]
        assert "eastmoney" in sources
        assert "sina" in sources

    def test_one_source_unchanged_other_changed(self):
        """混合情况：一个源未变，另一个源变了"""
        reset_audit_log()
        stage = CollectionStage()
        # 初始两个源
        stage.detect_source_changes(
            _make_articles("eastmoney", "茅台 利好") +
            _make_articles("sina", "茅台 上涨")
        )
        # 只改 eastmoney
        changes = stage.detect_source_changes(
            _make_articles("eastmoney", "完全不同 内容") +
            _make_articles("sina", "茅台 上涨")  # sina 相同
        )
        assert len(changes) == 1
        assert changes[0]["source"] == "eastmoney"


# ── 注入 verifier ────────────────────────────────────────────────────────


class TestInjectedVerifier:
    def test_injected_verifier_called(self):
        """注入的 verifier 应被调用"""
        reset_audit_log()
        mock_verifier = MagicMock(spec=["detect_source_change"])
        mock_verifier.detect_source_change.return_value = {
            "source": "eastmoney",
            "changed": False,
            "current_fingerprint": "abc",
            "previous_fingerprint": None,
        }
        stage = CollectionStage(verifier=mock_verifier)
        articles = _make_articles("eastmoney", "茅台 利好")
        changes = stage.detect_source_changes(articles)
        assert mock_verifier.detect_source_change.called
        assert changes == []

    def test_injected_verifier_with_change(self):
        """注入的 verifier 报变更时返回"""
        reset_audit_log()
        mock_verifier = MagicMock(spec=["detect_source_change"])
        mock_verifier.detect_source_change.return_value = {
            "source": "eastmoney",
            "changed": True,
            "current_fingerprint": "new_fp",
            "previous_fingerprint": "old_fp",
        }
        stage = CollectionStage(verifier=mock_verifier)
        articles = _make_articles("eastmoney", "茅台 利好")
        changes = stage.detect_source_changes(articles)
        assert len(changes) == 1
        assert changes[0]["changed"] is True


# ── 审计日志集成 ──────────────────────────────────────────────────────────


class TestAuditLogIntegration:
    def test_change_detected_writes_audit_log(self):
        """检测到变更时写入审计日志"""
        reset_audit_log()
        stage = CollectionStage()
        # 第一次
        stage.detect_source_changes(_make_articles("eastmoney", "茅台"))
        # 第二次不同内容
        stage.detect_source_changes(_make_articles("eastmoney", "完全不同"))
        log = get_audit_log()
        # 应有 source_change_detected 记录
        entries = log.query(action="source_change_detected")
        assert len(entries) >= 1
        assert entries[0].source == "eastmoney"
        assert entries[0].result == "partial"
        assert entries[0].metadata.get("previous_fingerprint") is not None
        assert entries[0].metadata.get("current_fingerprint") is not None

    def test_no_change_no_audit_log(self):
        """未检测到变更时不写审计日志"""
        reset_audit_log()
        stage = CollectionStage()
        # 首次采集，无变更
        stage.detect_source_changes(_make_articles("eastmoney", "茅台"))
        log = get_audit_log()
        entries = log.query(action="source_change_detected")
        assert entries == []

    def test_audit_log_includes_count(self):
        """审计日志包含文章数量"""
        reset_audit_log()
        stage = CollectionStage()
        # 第一次
        stage.detect_source_changes(_make_articles("eastmoney", "content1", n=3))
        # 第二次不同内容
        stage.detect_source_changes(_make_articles("eastmoney", "completely different", n=3))
        log = get_audit_log()
        entries = log.query(action="source_change_detected")
        assert entries[0].count == 3


# ── execute 集成 ─────────────────────────────────────────────────────────


class TestExecuteIntegration:
    def test_execute_calls_detect_source_changes(self):
        """execute() 应自动调用变更检测"""
        reset_audit_log()
        stage = CollectionStage()
        # mock _collect_from_news 返回一些文章
        with patch.object(stage, "_collect_from_news", return_value=_make_articles("news_searcher", "茅台")):
            with patch.object(stage, "detect_source_changes", wraps=stage.detect_source_changes) as spy:
                event = CollectionEvent(symbols=["sh600519"], sources=["news_searcher"])
                articles = stage.execute(event)
                # detect_source_changes 应被调用
                assert spy.called
                assert len(articles) > 0

    def test_execute_disabled_does_not_detect(self):
        """禁用变更检测时 execute 不调用"""
        reset_audit_log()
        stage = CollectionStage(enable_change_detection=False)
        with patch.object(stage, "_collect_from_news", return_value=_make_articles("news_searcher", "茅台")):
            with patch.object(stage, "detect_source_changes") as spy:
                event = CollectionEvent(symbols=["sh600519"], sources=["news_searcher"])
                stage.execute(event)
                assert not spy.called

    def test_execute_empty_articles_skips_detection(self):
        """无文章时跳过变更检测"""
        reset_audit_log()
        stage = CollectionStage()
        with patch.object(stage, "_collect_from_news", return_value=[]):
            with patch.object(stage, "detect_source_changes") as spy:
                event = CollectionEvent(symbols=["sh600519"], sources=["news_searcher"])
                stage.execute(event)
                assert not spy.called


# ── 向后兼容 ──────────────────────────────────────────────────────────────


class TestBackwardCompatibility:
    def test_old_constructor_works(self):
        """旧版构造（无新参数）应正常工作"""
        stage = CollectionStage()
        assert stage._max_articles == 20
        # 新参数应有默认值
        assert stage._enable_change_detection is True

    def test_old_max_articles_param(self):
        """max_articles_per_source 参数仍生效"""
        stage = CollectionStage(max_articles_per_source=5)
        assert stage._max_articles == 5

    def test_execute_returns_articles(self):
        """execute() 仍返回文章列表"""
        stage = CollectionStage(enable_change_detection=False)
        with patch.object(stage, "_collect_from_news", return_value=_make_articles("x", "茅台")):
            event = CollectionEvent(symbols=["sh600519"], sources=["news_searcher"])
            articles = stage.execute(event)
        assert isinstance(articles, list)
        assert len(articles) > 0


# ── 边界情况 ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_articles_with_empty_source_skipped(self):
        """source 为空的文章不参与变更检测"""
        reset_audit_log()
        stage = CollectionStage()
        articles = [
            RawArticle(title="t", content="c", url="u", source=""),  # 空 source
            RawArticle(title="t2", content="c2", url="u2", source="eastmoney"),
        ]
        # 不应抛异常
        changes = stage.detect_source_changes(articles)
        assert changes == []  # 首次采集无变更

    def test_articles_with_none_content_treated_as_empty(self):
        """content 为 None 时当作空字符串处理"""
        reset_audit_log()
        stage = CollectionStage()
        articles = [
            RawArticle(title="t", content=None, url="u", source="eastmoney"),
        ]
        # 不应抛异常
        stage.detect_source_changes(articles)
        # 第二次相同空内容
        changes = stage.detect_source_changes([
            RawArticle(title="t", content=None, url="u", source="eastmoney"),
        ])
        # 空内容相同，无变更
        assert changes == []

    def test_verifier_exception_does_not_break(self):
        """verifier 抛异常不应中断检测"""
        reset_audit_log()
        mock_verifier = MagicMock(spec=["detect_source_change"])
        mock_verifier.detect_source_change.side_effect = RuntimeError("verifier error")
        stage = CollectionStage(verifier=mock_verifier)
        # 不应抛异常
        changes = stage.detect_source_changes(_make_articles("eastmoney", "茅台"))
        assert changes == []

    def test_multiple_calls_same_stage_uses_same_verifier(self):
        """多次调用复用同一 verifier 实例"""
        stage = CollectionStage()
        d1 = stage._get_change_detector()
        d2 = stage._get_change_detector()
        assert d1 is d2


# ── 与 SourceVerifier 真实集成 ──────────────────────────────────────────────


class TestIntegrationWithRealVerifier:
    """与真实 SourceVerifier 集成"""

    def test_full_flow_first_run(self):
        """完整流程首次运行无变更"""
        reset_audit_log()
        stage = CollectionStage()
        articles = _make_articles("eastmoney", "茅台 利好 上涨")
        changes = stage.detect_source_changes(articles)
        assert changes == []

    def test_full_flow_change_detected(self):
        """完整流程变更检测"""
        reset_audit_log()
        stage = CollectionStage()
        # 第一次
        stage.detect_source_changes(_make_articles("eastmoney", "茅台 利好"))
        # 第二次完全不同
        changes = stage.detect_source_changes(
            _make_articles("eastmoney", "完全不同的 五粮液 利空 下跌 消息")
        )
        assert len(changes) == 1
        change = changes[0]
        assert change["source"] == "eastmoney"
        assert change["changed"] is True
        assert change["current_fingerprint"] != change["previous_fingerprint"]

    def test_full_flow_audit_log_written(self):
        """完整流程审计日志被写入"""
        reset_audit_log()
        stage = CollectionStage()
        # 第一次
        stage.detect_source_changes(_make_articles("eastmoney", "茅台 利好"))
        # 第二次变更
        stage.detect_source_changes(_make_articles("eastmoney", "完全不同"))

        log = get_audit_log()
        # 查询变更检测审计
        entries = log.query_by_collector("collection_stage")
        assert len(entries) >= 1
        assert all(e.action == "source_change_detected" for e in entries)
        # 应有 fingerprint 元数据
        for e in entries:
            assert "previous_fingerprint" in e.metadata
            assert "current_fingerprint" in e.metadata

    def test_pipeline_run_with_change_detection(self):
        """模拟 pipeline.run 调用 execute 后变更检测被触发"""
        reset_audit_log()
        stage = CollectionStage()
        with patch.object(stage, "_collect_from_news", return_value=_make_articles("news_searcher", "茅台 利好")):
            event = CollectionEvent(symbols=["sh600519"], sources=["news_searcher"])
            # 第一次执行
            stage.execute(event)
        # 第二次执行（内容不同）
        with patch.object(stage, "_collect_from_news", return_value=_make_articles("news_searcher", "完全不同的内容")):
            stage.execute(event)

        # 应检测到变更
        log = get_audit_log()
        entries = log.query(action="source_change_detected")
        assert len(entries) >= 1
