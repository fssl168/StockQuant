# -*- coding: utf-8 -*-
"""F020 FinMem 多因子召回评分器测试

覆盖：
- RecallWeights 边界校验
- 三因子计算（相关性 / 新鲜度 / 重要性）
- 分层半衰期
- RecallScorer 评分 / 排序 / 自适应权重 / 可观测性
- 跨层评分一致性
"""
from __future__ import annotations

import sys
import os
from datetime import datetime, timedelta

import pytest

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from stockquant.ai.memory.recall_scorer import (
    RecallWeights,
    RecallScorer,
    ScoreBreakdown,
    TIER_HALF_LIFE_DAYS,
    SOURCE_WEIGHTS,
    SCENE_WEIGHTS,
    relevance_score,
    recency_score,
    importance_score,
    rank_items,
    get_source_weight,
)


# ─── RecallWeights 边界 ─────────────────────────────────────────────


class TestRecallWeights:
    def test_default_weights(self):
        w = RecallWeights()
        assert w.relevance == 0.5
        assert w.recency == 0.3
        assert w.importance == 0.2

    def test_weights_must_sum_to_one(self):
        with pytest.raises(ValueError):
            RecallWeights(relevance=0.5, recency=0.3, importance=0.3)  # sum=1.1

    def test_weights_in_range(self):
        with pytest.raises(ValueError):
            RecallWeights(relevance=1.5, recency=-0.5, importance=0.0)

    def test_weights_immutable(self):
        w = RecallWeights()
        with pytest.raises(Exception):
            w.relevance = 0.9  # frozen=True


# ─── 因子 1: 相关性 ────────────────────────────────────────────────


class TestRelevanceScore:
    def test_keyword_overlap(self):
        item = {"content": "贵州茅台 2024 年营收同比增长 15%", "source": "official_news"}
        # 完全匹配关键词
        score = relevance_score(item, "贵州茅台 营收", tier="shallow")
        assert 0.0 < score <= 1.0

    def test_no_overlap(self):
        item = {"content": "完全无关的内容", "source": "official_news"}
        score = relevance_score(item, "贵州茅台 营收", tier="shallow")
        # 关键词重叠为 0，仅有来源权重贡献
        assert score > 0.0  # source_weight 贡献

    def test_semantic_score_overrides(self):
        """如果提供 semantic_score，直接使用"""
        item = {"content": "任意内容"}
        score = relevance_score(item, "query", tier="shallow", semantic_score=0.2)
        # 1.0 - 0.2 = 0.8
        assert score == pytest.approx(0.8)

    def test_source_weight_modulation(self):
        """高权重来源比低权重来源分数更高"""
        item_high = {"content": "茅台", "source": "exchange_announcement"}
        item_low = {"content": "茅台", "source": "social_media"}
        score_high = relevance_score(item_high, "茅台", tier="shallow")
        score_low = relevance_score(item_low, "茅台", tier="shallow")
        assert score_high > score_low


# ─── 因子 2: 新鲜度（分层半衰期） ─────────────────────────────────


class TestRecencyScore:
    def test_zero_age_max_score(self):
        """刚刚写入的记忆，recency=1.0"""
        now = datetime.now()
        ts = now.isoformat()
        score = recency_score(ts, tier="shallow", now=now)
        assert score == pytest.approx(1.0)

    def test_shallow_half_life_3_days(self):
        """shallow 层 3 天半衰期"""
        now = datetime.now()
        ts = (now - timedelta(days=3)).isoformat()
        score = recency_score(ts, tier="shallow", now=now)
        # 3 天后正好衰减一半
        assert score == pytest.approx(0.5, abs=0.01)

    def test_intermediate_half_life_90_days(self):
        """intermediate 层 90 天半衰期"""
        now = datetime.now()
        ts = (now - timedelta(days=90)).isoformat()
        score = recency_score(ts, tier="intermediate", now=now)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_deep_half_life_365_days(self):
        """deep 层 365 天半衰期"""
        now = datetime.now()
        ts = (now - timedelta(days=365)).isoformat()
        score = recency_score(ts, tier="deep", now=now)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_working_half_life_1_day(self):
        """working 层 1 天半衰期"""
        now = datetime.now()
        ts = (now - timedelta(days=1)).isoformat()
        score = recency_score(ts, tier="working", now=now)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_last_accessed_refreshes_memory(self):
        """last_accessed_at 比较新时，按较新时间衰减"""
        now = datetime.now()
        ts_old = (now - timedelta(days=10)).isoformat()
        last_accessed = (now - timedelta(hours=1)).isoformat()
        score = recency_score(ts_old, tier="shallow", last_accessed_at=last_accessed, now=now)
        # 按 last_accessed 计算，约 1 小时前
        expected = 0.5 ** ((1/24) / 3)
        assert score == pytest.approx(expected, abs=0.01)

    def test_invalid_timestamp_returns_zero(self):
        assert recency_score(None, tier="shallow") == 0.0
        assert recency_score("invalid", tier="shallow") == 0.0

    def test_different_tiers_different_decay(self):
        """同一时间戳在不同 tier 上衰减速度不同"""
        now = datetime.now()
        ts = (now - timedelta(days=5)).isoformat()
        working_score = recency_score(ts, "working", now=now)
        shallow_score = recency_score(ts, "shallow", now=now)
        deep_score = recency_score(ts, "deep", now=now)
        # deep 衰减最慢，working 衰减最快
        assert deep_score > shallow_score > working_score


# ─── 因子 3: 重要性（分层多维加权） ────────────────────────────────


class TestImportanceScore:
    def test_shallow_uses_source_sentiment_scope(self):
        item = {
            "source": "exchange_announcement",
            "sentiment_score": 0.8,
            "scope": "market",
        }
        score = importance_score(item, tier="shallow")
        # 0.4*1.0 + 0.3*0.8 + 0.3*1.0 = 0.4 + 0.24 + 0.3 = 0.94
        assert score == pytest.approx(0.94, abs=0.01)

    def test_intermediate_uses_event_metric(self):
        item = {
            "event_type": "profit_warning_up",
            "metric_change_pct": 0.5,
        }
        score = importance_score(item, tier="intermediate")
        # 0.5*1.0 + 0.5*0.5 = 0.75
        assert score == pytest.approx(0.75, abs=0.01)

    def test_deep_uses_event_count_core_holding(self):
        item = {
            "key_event_count": 5,
            "is_core_holding": True,
        }
        score = importance_score(item, tier="deep")
        # 0.6*0.5 + 0.4*1.0 = 0.3 + 0.4 = 0.7
        assert score == pytest.approx(0.7, abs=0.01)

    def test_working_uses_item_importance(self):
        item = {"importance_score": 0.8}
        score = importance_score(item, tier="working")
        assert score == pytest.approx(0.8, abs=0.01)

    def test_unknown_tier_fallback(self):
        item = {"importance_score": 0.6}
        score = importance_score(item, tier="unknown_tier")
        assert score == pytest.approx(0.6, abs=0.01)


# ─── RecallScorer 主类 ──────────────────────────────────────────────


class TestRecallScorer:
    def setup_method(self):
        self.scorer = RecallScorer()
        self.now = datetime(2026, 6, 27, 12, 0, 0)

        # 构造测试数据
        self.items = [
            {
                "id": "shallow_recent_high_imp",
                "content": "茅台财报 营收增长",
                "timestamp": (self.now - timedelta(hours=1)).isoformat(),
                "source": "exchange_announcement",
                "sentiment_score": 0.7,
                "scope": "individual",
            },
            {
                "id": "shallow_old_low_imp",
                "content": "茅台财报 营收",
                "timestamp": (self.now - timedelta(days=10)).isoformat(),
                "source": "social_media",
                "sentiment_score": 0.1,
                "scope": "individual",
            },
        ]

    def test_score_returns_breakdown(self):
        item = self.items[0]
        breakdown = self.scorer.score(
            item, query_text="茅台财报", tier="shallow", now=self.now
        )
        assert isinstance(breakdown, ScoreBreakdown)
        assert breakdown.item_id == "shallow_recent_high_imp"
        assert 0.0 <= breakdown.relevance <= 1.0
        assert 0.0 <= breakdown.recency <= 1.0
        assert 0.0 <= breakdown.importance <= 1.0
        assert 0.0 <= breakdown.final_score <= 1.0
        assert breakdown.tier == "shallow"

    def test_rank_orders_by_final_score(self):
        scored = self.scorer.rank(
            self.items, query="茅台财报", tier="shallow", top_k=10, now=self.now
        )
        assert len(scored) == 2
        # 新鲜高重要性条目应排第一
        assert scored[0][1].item_id == "shallow_recent_high_imp"
        assert scored[0][1].final_score > scored[1][1].final_score

    def test_rank_top_k_limit(self):
        scored = self.scorer.rank(
            self.items, query="茅台财报", tier="shallow", top_k=1, now=self.now
        )
        assert len(scored) == 1

    def test_explain_returns_dict(self):
        item = self.items[0]
        result = self.scorer.explain(item, "茅台财报", tier="shallow", now=self.now)
        assert isinstance(result, dict)
        assert "score_breakdown" in result
        assert "final_score" in result
        assert result["tier"] == "shallow"

    def test_adaptive_weights_realtime(self):
        w = self.scorer.adaptive_weights("realtime")
        assert w.relevance == 0.7  # 实时场景侧重相关性
        assert w.relevance > w.importance

    def test_adaptive_weights_review(self):
        w = self.scorer.adaptive_weights("review")
        assert w.importance == 0.5  # 复盘场景侧重重要性
        assert w.importance > w.relevance

    def test_adaptive_weights_unknown_scene_uses_default(self):
        w = self.scorer.adaptive_weights("unknown_scene")
        assert w == SCENE_WEIGHTS["default"]

    def test_with_weights_returns_new_instance(self):
        new_w = RecallWeights(relevance=0.6, recency=0.3, importance=0.1)
        new_scorer = self.scorer.with_weights(new_w)
        assert new_scorer is not self.scorer
        assert new_scorer.weights.relevance == 0.6

    def test_with_scene_returns_new_instance(self):
        new_scorer = self.scorer.with_scene("realtime")
        assert new_scorer.weights.relevance == 0.7


# ─── 跨层评分 ──────────────────────────────────────────────────────


class TestCrossLayerScoring:
    def test_cross_layer_consistent_scoring(self):
        """同一查询在不同层评分时，final_score 可比较"""
        now = datetime(2026, 6, 27, 12, 0, 0)
        scorer = RecallScorer()

        l1_item = {
            "id": "l1_x",
            "content": "茅台市场异动",
            "timestamp": (now - timedelta(hours=2)).isoformat(),
            "importance_score": 0.8,
        }
        l2_item = {
            "id": "l2_x",
            "content": "茅台市场异动",
            "timestamp": (now - timedelta(days=2)).isoformat(),
            "source": "official_news",
            "sentiment_score": 0.5,
            "scope": "individual",
        }
        l3_item = {
            "id": "l3_x",
            "content": "茅台 2024 年报披露",
            "timestamp": (now - timedelta(days=200)).isoformat(),
            "key_event_count": 8,
            "is_core_holding": True,
        }

        l1_b = scorer.score(l1_item, query_text="茅台", tier="working", now=now)
        l2_b = scorer.score(l2_item, query_text="茅台", tier="shallow", now=now)
        l3_b = scorer.score(l3_item, query_text="茅台", tier="deep", now=now)

        # 三层 final_score 都在 [0,1]
        for b in [l1_b, l2_b, l3_b]:
            assert 0.0 <= b.final_score <= 1.0

        # L1 working 2小时前 recency 接近 1
        assert l1_b.recency > 0.9
        # L3 deep 200天前 recency 仍较高（半衰期 365 天）
        assert l3_b.recency > 0.5


# ─── 便利函数 ──────────────────────────────────────────────────────


class TestRankItemsFunction:
    def test_returns_enriched_items(self):
        now = datetime(2026, 6, 27)
        items = [
            {
                "id": "x1",
                "content": "茅台 营收",
                "timestamp": (now - timedelta(hours=1)).isoformat(),
                "source": "official_news",
                "sentiment_score": 0.5,
                "scope": "individual",
            },
            {
                "id": "x2",
                "content": "茅台 营收",
                "timestamp": (now - timedelta(days=10)).isoformat(),
                "source": "social_media",
                "sentiment_score": 0.1,
                "scope": "individual",
            },
        ]
        result = rank_items(items, query="茅台 营收", tier="shallow", top_k=10, scene="default")
        assert len(result) == 2
        assert result[0]["_final_score"] > result[1]["_final_score"]
        assert "_score_breakdown" in result[0]

    def test_empty_input(self):
        assert rank_items([], query="x", tier="shallow") == []


# ─── 数据源权重 ────────────────────────────────────────────────────


class TestSourceWeights:
    def test_known_source(self):
        assert get_source_weight("exchange_announcement") == 1.0
        assert get_source_weight("social_media") == 0.5

    def test_unknown_source(self):
        assert get_source_weight("unknown") == 0.3
        assert get_source_weight(None) == 0.3
        assert get_source_weight("not_in_table") == 0.3
