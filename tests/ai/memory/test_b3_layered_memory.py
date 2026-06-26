# -*- coding: utf-8 -*-
"""F020 Phase B3 — 分层记忆接口测试

覆盖：
1. L3Store 的 tier 过滤（search_by_tier）+ RecallScorer 集成
2. L3Store 写入时携带 tier/period_type/importance_score/last_accessed_at
3. L2Store 集成 RecallScorer（tier=shallow）+ metadata 字段提取
4. MemorySystem 新分层接口：add_intermediate / add_deep / search_by_layer
5. last_accessed_at 刷新机制（访问即更新）
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta

import pytest

# 强制内存模式（避免依赖 PostgreSQL）
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")


# ========================================================================
# L3Store 分层测试
# ========================================================================

class TestL3StoreTierFilter:
    """L3Store 的 tier 过滤与 RecallScorer 集成"""

    def test_write_with_tier_intermediate(self):
        """写入 tier=intermediate 后能用 search_by_tier 检索到"""
        from stockquant.ai.memory.l3_store import L3Store
        store = L3Store(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        store.clear_all()

        store.write({
            "id": "test_int_1",
            "symbol": "sh600519",
            "content": "贵州茅台 2024Q3 季报披露，营收同比增长 15%",
            "summary": "茅台 Q3 营收增 15%",
            "tier": "intermediate",
            "period_type": "quarterly",
            "importance_score": 0.8,
        })

        # 按 intermediate 层检索
        results = store.search_by_tier("茅台", tier="intermediate", top_k=10)
        assert len(results) == 1
        assert results[0]["tier"] == "intermediate"
        assert results[0]["period_type"] == "quarterly"
        assert results[0]["importance_score"] == 0.8

    def test_write_with_tier_deep(self):
        """写入 tier=deep 后能被 search_by_tier('deep') 命中"""
        from stockquant.ai.memory.l3_store import L3Store
        store = L3Store(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        store.clear_all()

        store.write({
            "id": "test_deep_1",
            "symbol": "sh600519",
            "content": "贵州茅台 2024 年报：全年营收 1560 亿",
            "summary": "茅台 2024 年报",
            "tier": "deep",
            "period_type": "annual",
            "importance_score": 0.9,
        })

        results = store.search_by_tier("茅台", tier="deep", top_k=10)
        assert len(results) == 1
        assert results[0]["tier"] == "deep"

    def test_tier_filter_excludes_other_tiers(self):
        """按 tier=intermediate 检索时不应返回 shallow 条目"""
        from stockquant.ai.memory.l3_store import L3Store
        store = L3Store(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        store.clear_all()

        store.write({
            "id": "shallow_1",
            "symbol": "sh600519",
            "content": "茅台最新市场新闻",
            "tier": "shallow",
        })
        store.write({
            "id": "inter_1",
            "symbol": "sh600519",
            "content": "茅台季报披露",
            "tier": "intermediate",
        })

        # intermediate 检索不应返回 shallow
        inter_results = store.search_by_tier("茅台", tier="intermediate", top_k=10)
        assert all(r.get("tier") == "intermediate" for r in inter_results)
        assert len(inter_results) == 1

        # shallow 检索不应返回 intermediate
        shallow_results = store.search_by_tier("茅台", tier="shallow", top_k=10)
        assert all(r.get("tier") == "shallow" for r in shallow_results)
        assert len(shallow_results) == 1

    def test_default_tier_is_shallow(self):
        """未指定 tier 时默认为 shallow"""
        from stockquant.ai.memory.l3_store import L3Store
        store = L3Store(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        store.clear_all()

        # 旧式调用（不传 tier）
        store.write({
            "id": "legacy_1",
            "symbol": "sh600519",
            "content": "无 tier 字段的旧式写入",
        })

        results = store.search_by_tier("", tier="shallow", top_k=10)
        assert len(results) == 1
        assert results[0]["tier"] == "shallow"

    def test_last_accessed_at_refreshed_on_search(self):
        """search_by_tier 命中后应刷新 last_accessed_at"""
        from stockquant.ai.memory.l3_store import L3Store
        store = L3Store(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        store.clear_all()

        store.write({
            "id": "access_test_1",
            "symbol": "sh600519",
            "content": "测试访问刷新",
            "tier": "shallow",
        })

        # 第一次检索后 last_accessed_at 应被更新
        results = store.search_by_tier("测试", tier="shallow", top_k=10)
        assert len(results) == 1
        first_access = results[0].get("last_accessed_at")
        assert first_access is not None

    def test_recall_scorer_orders_by_relevance(self):
        """search_by_tier 应按 RecallScorer 综合评分排序"""
        from stockquant.ai.memory.l3_store import L3Store
        store = L3Store(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        store.clear_all()

        # 三条条目：高相关 + 低相关 + 无关
        store.write({
            "id": "high_rel",
            "symbol": "sh600519",
            "content": "茅台年报披露营收大增",
            "tier": "deep",
            "importance_score": 0.9,
        })
        store.write({
            "id": "low_rel",
            "symbol": "sh600519",
            "content": "其他公司年报",
            "tier": "deep",
            "importance_score": 0.3,
        })

        results = store.search_by_tier("茅台", tier="deep", top_k=10)
        assert len(results) >= 1
        # 高相关性条目应排在前
        assert results[0]["id"] == "high_rel"


# ========================================================================
# L2Store RecallScorer 集成测试
# ========================================================================

class TestL2StoreRecallScorer:
    """L2Store 集成 RecallScorer 后的检索行为"""

    def test_write_records_source_field(self):
        """写入时 source 字段应被记录到 metadata"""
        from stockquant.ai.memory.l2_store import L2Store
        store = L2Store(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        store.clear_all()

        store.write({
            "id": "l2_src_1",
            "symbol": "sh600519",
            "content": "茅台市场新闻",
            "source": "exchange_announcement",
            "sentiment_score": 0.8,
            "scope": "individual",
        })

        # 验证 source 在内存模式下保留在 entry 顶层
        assert len(store._entries) == 1
        entry = store._entries[0]
        assert entry.get("source") == "exchange_announcement"
        assert entry.get("sentiment_score") == 0.8
        assert entry.get("scope") == "individual"

    def test_search_uses_recall_scorer(self):
        """L2 检索应使用 RecallScorer 评分排序"""
        from stockquant.ai.memory.l2_store import L2Store
        store = L2Store(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        store.clear_all()

        store.write({
            "id": "high_imp",
            "symbol": "sh600519",
            "content": "茅台交易所公告重大事项",
            "source": "exchange_announcement",
            "sentiment_score": 0.9,
            "scope": "individual",
            "timestamp": datetime.now().isoformat(),
        })
        store.write({
            "id": "low_imp",
            "symbol": "sh600519",
            "content": "茅台社交媒体传闻",
            "source": "social_media",
            "sentiment_score": 0.1,
            "scope": "individual",
            "timestamp": datetime.now().isoformat(),
        })

        results = store.search("茅台", top_k=10)
        assert len(results) >= 1
        # 交易所公告（source_weight=1.0）应排在社交媒体（0.5）之前
        assert results[0]["id"] == "high_imp"

    def test_search_preserves_backward_compatibility(self):
        """不传 source 字段时仍可正常检索"""
        from stockquant.ai.memory.l2_store import L2Store
        store = L2Store(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        store.clear_all()

        store.write({
            "id": "legacy_l2",
            "symbol": "sh600519",
            "content": "旧式写入无 source",
        })

        results = store.search("旧式", top_k=10)
        assert len(results) == 1


# ========================================================================
# MemorySystem 分层接口测试
# ========================================================================

class TestMemorySystemLayered:
    """MemorySystem 新增分层接口测试"""

    def test_add_intermediate_writes_l3_with_tier(self):
        """add_intermediate 应写入 L3 并标记 tier=intermediate"""
        from stockquant.ai.memory.system import MemorySystem
        ms = MemorySystem(working_max_size=10, db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        ms.clear_all()

        item_id = ms.add_intermediate(
            symbol="sh600519",
            content="茅台 2024Q3 季报",
            period_type="quarterly",
            importance=0.7,
            summary="茅台 Q3 季报摘要",
        )

        # 应能从 L3 通过 search_by_tier('intermediate') 检索到
        results = ms.l3.search_by_tier("茅台", tier="intermediate", top_k=10)
        assert len(results) == 1
        assert results[0]["id"] == item_id
        assert results[0]["tier"] == "intermediate"
        assert results[0]["period_type"] == "quarterly"
        assert results[0]["importance_score"] == 0.7

    def test_add_deep_writes_l3_with_tier(self):
        """add_deep 应写入 L3 并标记 tier=deep"""
        from stockquant.ai.memory.system import MemorySystem
        ms = MemorySystem(working_max_size=10, db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        ms.clear_all()

        item_id = ms.add_deep(
            symbol="sh600519",
            content="茅台 2024 年报全文",
            period_type="annual",
            importance=0.9,
            summary="茅台 2024 年报摘要",
        )

        results = ms.l3.search_by_tier("茅台", tier="deep", top_k=10)
        assert len(results) == 1
        assert results[0]["id"] == item_id
        assert results[0]["tier"] == "deep"
        assert results[0]["importance_score"] == 0.9

    def test_search_by_layer_intermediate(self):
        """search_by_layer('intermediate') 应只返回 intermediate 条目"""
        from stockquant.ai.memory.system import MemorySystem
        ms = MemorySystem(working_max_size=10, db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        ms.clear_all()

        ms.add_intermediate(symbol="sh600519", content="茅台季报")
        ms.add_deep(symbol="sh600519", content="茅台年报")

        results = ms.search_by_layer("茅台", layer="intermediate", top_k=10)
        assert len(results) == 1
        assert results[0]["layer"] == "intermediate"

    def test_search_by_layer_deep(self):
        """search_by_layer('deep') 应只返回 deep 条目"""
        from stockquant.ai.memory.system import MemorySystem
        ms = MemorySystem(working_max_size=10, db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        ms.clear_all()

        ms.add_intermediate(symbol="sh600519", content="茅台季报")
        ms.add_deep(symbol="sh600519", content="茅台年报")

        results = ms.search_by_layer("茅台", layer="deep", top_k=10)
        assert len(results) == 1
        assert results[0]["layer"] == "deep"

    def test_search_by_layer_all_returns_cross_layer(self):
        """search_by_layer('all') 应跨层返回结果并按 RecallScorer 排序"""
        from stockquant.ai.memory.system import MemorySystem
        ms = MemorySystem(working_max_size=10, db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        ms.clear_all()

        ms.add_working({"content": "茅台工作记忆", "symbol": "sh600519"})
        ms.add_short_term("sh600519", "茅台 L2 短期记忆")
        ms.add_intermediate(symbol="sh600519", content="茅台季报")
        ms.add_deep(symbol="sh600519", content="茅台年报")

        results = ms.search_by_layer("茅台", layer="all", top_k=10)
        # 至少返回部分结果
        assert len(results) >= 1
        # 含 _final_score 字段（RecallScorer 排序结果）
        assert "_final_score" in results[0]

    def test_search_by_layer_working(self):
        """search_by_layer('working') 应只返回 L1 工作记忆"""
        from stockquant.ai.memory.system import MemorySystem
        ms = MemorySystem(working_max_size=10, db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        ms.clear_all()

        ms.add_working({"content": "茅台工作记忆测试", "symbol": "sh600519"})
        ms.add_intermediate(symbol="sh600519", content="茅台季报")

        results = ms.search_by_layer("茅台", layer="working", top_k=10)
        assert len(results) == 1
        assert results[0]["layer"] == "working"

    def test_search_by_layer_unknown_returns_empty(self):
        """未知 layer 应返回空列表"""
        from stockquant.ai.memory.system import MemorySystem
        ms = MemorySystem(working_max_size=10, db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        ms.clear_all()

        results = ms.search_by_layer("茅台", layer="unknown_layer", top_k=10)
        assert results == []


# ========================================================================
# 回归测试：现有接口不受 B3 修改影响
# ========================================================================

class TestBackwardCompatibility:
    """B3 修改后的向后兼容性测试"""

    def test_l3_legacy_write_still_works(self):
        """L3Store 旧式 write（不传 tier）仍可用"""
        from stockquant.ai.memory.l3_store import L3Store
        store = L3Store(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        store.clear_all()

        item_id = store.write({
            "symbol": "sh600519",
            "content": "旧式写入测试",
        })
        assert item_id is not None

        # 旧式 search 仍可用
        results = store.search("旧式", top_k=10)
        assert len(results) == 1

    def test_l2_legacy_search_still_works(self):
        """L2Store 旧式 search 仍可用"""
        from stockquant.ai.memory.l2_store import L2Store
        store = L2Store(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        store.clear_all()

        store.write({
            "symbol": "sh600519",
            "content": "茅台新闻",
        })

        results = store.search("茅台", top_k=10)
        assert len(results) == 1

    def test_memory_system_legacy_add_long_term(self):
        """MemorySystem 旧式 add_long_term 仍可用"""
        from stockquant.ai.memory.system import MemorySystem
        ms = MemorySystem(working_max_size=10, db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        ms.clear_all()

        item_id = ms.add_long_term({
            "symbol": "sh600519",
            "content": "旧式长期记忆",
        })
        assert item_id is not None

        results = ms.search_long_term(symbol="sh600519")
        assert len(results) == 1
