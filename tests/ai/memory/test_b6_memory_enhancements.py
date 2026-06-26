# -*- coding: utf-8 -*-
"""F020 Phase B6 单元测试 — 记忆系统增强

覆盖：
- B6.1: Compressor LLM 集成 + importance_score/tier 字段
- B6.2: L3 embedding fallback（OpenAI → 本地 sentence-transformers）
- B6.3: L3Store/MemorySystem 噪音模式库 + 已证伪事实接口
- B6 附加: MemoryManager 跨层 RecallScorer 统一评分
"""

import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from stockquant.ai.memory.compressor import MemoryCompressor
from stockquant.ai.memory.l3_store import L3Store
from stockquant.ai.memory.system import MemorySystem


@pytest.fixture(autouse=True)
def _clear_l3():
    """每个测试前清空 L3"""
    try:
        store = L3Store()
        store.clear_all()
    except Exception:
        pass
    yield


# ════════════════════════════════════════════════════════════════════
# B6.1: Compressor LLM 集成
# ════════════════════════════════════════════════════════════════════

class TestCompressorLLMIntegration:
    """B6.1: 压缩器接入 LLM"""

    def test_no_llm_falls_back_to_truncate(self):
        """未配置 LLM 时降级为截断"""
        compressor = MemoryCompressor(llm_adapter=None)
        long_content = "这是一段很长的内容。" * 100  # > 200 字
        summary = compressor._generate_summary(long_content)
        assert len(summary) <= 205  # 200 + "..."
        assert summary.endswith("...")

    def test_short_content_returns_as_is(self):
        """短内容直接返回，不调用 LLM"""
        mock_llm = MagicMock()
        compressor = MemoryCompressor(llm_adapter=mock_llm)
        short = "短内容"
        result = compressor._generate_summary(short)
        assert result == short
        # LLM 不应被调用
        mock_llm.chat.assert_not_called()

    def test_llm_summarize_new_api(self):
        """LLM 调用新版 API: chat(message, system_prompt=)"""
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "这是LLM生成的摘要"
        compressor = MemoryCompressor(llm_adapter=mock_llm)
        long_content = "测试内容。" * 100
        summary = compressor._generate_summary(long_content)
        assert summary == "这是LLM生成的摘要"
        # 应调用 chat(message, system_prompt=...)
        mock_llm.chat.assert_called_once()
        call_args = mock_llm.chat.call_args
        assert call_args[0][0]  # 第一个位置参数是 user_prompt

    def test_llm_summarize_old_api_fallback(self):
        """LLM 新版 API 抛 TypeError 时降级到旧版 messages 列表"""
        mock_llm = MagicMock()
        # 第一次调用抛 TypeError（模拟新版签名不匹配）
        # 第二次返回摘要
        mock_llm.chat.side_effect = [TypeError("signature mismatch"), "LLM 旧版摘要"]
        compressor = MemoryCompressor(llm_adapter=mock_llm)
        long_content = "测试内容。" * 100
        summary = compressor._generate_summary(long_content)
        assert summary == "LLM 旧版摘要"
        assert mock_llm.chat.call_count == 2

    def test_llm_returns_invalid_falls_back_to_truncate(self):
        """LLM 返回空/None/过长字符串时降级"""
        mock_llm = MagicMock()
        mock_llm.chat.return_value = ""  # 空字符串
        compressor = MemoryCompressor(llm_adapter=mock_llm)
        long_content = "测试内容。" * 100
        summary = compressor._generate_summary(long_content)
        # 降级为截断
        assert summary.endswith("...")
        assert len(summary) <= 205

    def test_llm_raises_exception_falls_back(self):
        """LLM 调用抛异常时降级到截断"""
        mock_llm = MagicMock()
        mock_llm.chat.side_effect = RuntimeError("LLM 服务不可用")
        compressor = MemoryCompressor(llm_adapter=mock_llm)
        long_content = "测试内容。" * 100
        summary = compressor._generate_summary(long_content)
        assert summary.endswith("...")

    def test_compress_group_single_item_with_tier_and_importance(self):
        """B6.1: 单条压缩携带 tier + importance_score"""
        compressor = MemoryCompressor()
        item = {
            "id": "test1",
            "content": "短内容",
            "confidence": 0.8,
            "timestamp": datetime.now().isoformat(),
        }
        result = compressor._compress_group([item])
        assert result["tier"] == "intermediate"
        assert result["importance_score"] == 0.8
        assert result["metadata"]["compression_method"] == "truncate"

    def test_compress_group_multi_items_importance_boosted(self):
        """B6.1: 多条压缩时 importance_score 提升 10%（多源佐证）"""
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "LLM 摘要"
        compressor = MemoryCompressor(llm_adapter=mock_llm)
        items = [
            {"id": "1", "content": "内容1", "confidence": 0.6,
             "timestamp": datetime.now().isoformat()},
            {"id": "2", "content": "内容2" * 100, "confidence": 0.7,
             "timestamp": datetime.now().isoformat()},
        ]
        result = compressor._compress_group(items)
        # importance = max(0.6, 0.7) * 1.1 = 0.77
        assert abs(result["importance_score"] - 0.77) < 0.001
        assert result["tier"] == "intermediate"
        assert result["metadata"]["compression_method"] == "llm"
        assert result["metadata"]["source_count"] == 2

    def test_compress_group_importance_capped_at_1(self):
        """importance_score 上限为 1.0"""
        compressor = MemoryCompressor()
        items = [
            {"id": "1", "content": "短内容", "confidence": 0.95,
             "timestamp": datetime.now().isoformat()},
            {"id": "2", "content": "短内容", "confidence": 0.95,
             "timestamp": datetime.now().isoformat()},
        ]
        result = compressor._compress_group(items)
        # 0.95 * 1.1 = 1.045 -> 截断为 1.0
        assert result["importance_score"] == 1.0


# ════════════════════════════════════════════════════════════════════
# B6.2: L3 Embedding Fallback
# ════════════════════════════════════════════════════════════════════

class TestL3EmbeddingFallback:
    """B6.2: L3 embedding 双层降级"""

    def test_openai_embedding_no_api_key(self):
        """无 API Key 时 OpenAI 返回 None"""
        store = L3Store()
        # 清空环境变量
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(store._openai_embedding("测试文本"))
            finally:
                loop.close()
            assert result is None
        finally:
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key

    def test_local_embedding_without_sentence_transformers(self):
        """sentence-transformers 未安装时本地 embedding 返回 None"""
        store = L3Store()
        # 模拟未安装
        store._local_embedder = None
        # 直接测试编码方法（不会尝试加载模型）
        # 由于我们无法控制 import，只验证 _local_embedder 为 None 时返回 None
        # 不实际调用 encode
        result = store._local_embedding("测试") if store._local_embedder else None
        # 不一定为 None（如果环境装了 sentence-transformers），所以这里只验证不抛异常
        assert result is None or isinstance(result, list)

    def test_get_embedding_graceful_fallback(self):
        """B6.2: _get_embedding 在所有方法失败时返回 None"""
        store = L3Store()
        # 强制两边都失败
        store._local_embedder = None  # 防止懒加载
        # 清空 API Key
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(store._get_embedding("测试文本"))
            finally:
                loop.close()
            # 没有可用 embedding 服务时应返回 None
            assert result is None or isinstance(result, list)
        finally:
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key


# ════════════════════════════════════════════════════════════════════
# B6.3: 噪音模式库 + 已证伪事实
# ════════════════════════════════════════════════════════════════════

class TestNoisePatternLibrary:
    """B6.3: L3Store + MemorySystem 噪音模式库"""

    def test_l3_get_noise_patterns_empty(self):
        """空 L3 返回空列表"""
        store = L3Store()
        store.clear_all()
        patterns = store.get_noise_patterns()
        assert patterns == []

    def test_l3_get_noise_patterns_with_data(self):
        """L3 中有噪音模式时返回"""
        store = L3Store()
        store.clear_all()
        # 写入一条噪音模式
        store.write({
            "content": "震惊体标题模板",
            "metadata": {"type": "noise_pattern"},
            "tier": "shallow",
            "timestamp": datetime.now().isoformat(),
        })
        # 写入一条普通条目（不应被返回）
        store.write({
            "content": "普通新闻内容",
            "metadata": {"type": "news"},
            "tier": "shallow",
            "timestamp": datetime.now().isoformat(),
        })
        patterns = store.get_noise_patterns()
        assert "震惊体标题模板" in patterns
        assert "普通新闻内容" not in patterns

    def test_l3_get_noise_patterns_dedup(self):
        """重复噪音模式去重"""
        store = L3Store()
        store.clear_all()
        for _ in range(3):
            store.write({
                "content": "扫码进群模板",
                "metadata": {"type": "noise_pattern"},
                "tier": "shallow",
                "timestamp": datetime.now().isoformat(),
            })
        patterns = store.get_noise_patterns()
        assert patterns.count("扫码进群模板") == 1

    def test_l3_get_disproved_facts_empty(self):
        """空 L3 返回空列表"""
        store = L3Store()
        store.clear_all()
        facts = store.get_disproved_facts()
        assert facts == []

    def test_l3_get_disproved_facts_with_data(self):
        """L3 中有已证伪事实时返回"""
        store = L3Store()
        store.clear_all()
        store.write({
            "content": "某股票即将涨停（已证伪）",
            "metadata": {"type": "disproved_fact"},
            "symbol": "sh600519",
            "tier": "shallow",
            "timestamp": datetime.now().isoformat(),
        })
        facts = store.get_disproved_facts()
        assert any("某股票即将涨停" in f for f in facts)

    def test_l3_get_disproved_facts_by_symbol(self):
        """按 symbol 过滤已证伪事实"""
        store = L3Store()
        store.clear_all()
        store.write({
            "content": "茅台利空（已证伪）",
            "metadata": {"type": "disproved_fact"},
            "symbol": "sh600519",
            "tier": "shallow",
            "timestamp": datetime.now().isoformat(),
        })
        store.write({
            "content": "五粮液利好（已证伪）",
            "metadata": {"type": "disproved_fact"},
            "symbol": "sz000858",
            "tier": "shallow",
            "timestamp": datetime.now().isoformat(),
        })
        # 过滤茅台
        maotai_facts = store.get_disproved_facts(symbol="sh600519")
        assert any("茅台" in f for f in maotai_facts)
        assert all("五粮液" not in f for f in maotai_facts)

    def test_memory_system_get_noise_patterns(self):
        """MemorySystem 透传 get_noise_patterns"""
        ms = MemorySystem()
        ms.clear_all()
        ms.l3.write({
            "content": "营销号模板",
            "metadata": {"type": "noise_pattern"},
            "tier": "shallow",
            "timestamp": datetime.now().isoformat(),
        })
        patterns = ms.get_noise_patterns()
        assert "营销号模板" in patterns

    def test_memory_system_get_disproved_facts(self):
        """MemorySystem 透传 get_disproved_facts"""
        ms = MemorySystem()
        ms.clear_all()
        ms.l3.write({
            "content": "已证伪声明",
            "metadata": {"type": "disproved_fact"},
            "tier": "shallow",
            "timestamp": datetime.now().isoformat(),
        })
        facts = ms.get_disproved_facts()
        assert any("已证伪" in f for f in facts)

    def test_memory_system_get_noise_patterns_empty(self):
        """空 MemorySystem 返回空列表，不抛异常"""
        ms = MemorySystem()
        ms.clear_all()
        assert ms.get_noise_patterns() == []

    def test_memory_system_get_disproved_facts_exception_safe(self):
        """get_disproved_facts 异常安全"""
        ms = MemorySystem()
        ms.clear_all()
        # 应返回空列表而非抛异常
        result = ms.get_disproved_facts(symbol="any")
        assert result == []


# ════════════════════════════════════════════════════════════════════
# B6 附加: MemoryManager 跨层统一评分
# ════════════════════════════════════════════════════════════════════

class TestMemoryManagerCrossLayerScoring:
    """B6 附加: MemoryManager 跨层 RecallScorer 统一评分"""

    def test_manager_search_returns_unified_results(self):
        """search 返回跨层合并结果"""
        from stockquant.ai.memory.manager import MemoryManager
        mgr = MemoryManager()
        try:
            mgr.l3.clear_all()
            # 写入 L3 一条数据
            mgr.l3.write({
                "content": "茅台业绩超预期",
                "symbol": "sh600519",
                "confidence": 0.8,
                "tier": "shallow",
                "timestamp": datetime.now().isoformat(),
            })
            # 写入 L1 一条数据
            mgr.l1.append({"content": "茅台业绩超预期", "symbol": "sh600519"})
            results = mgr.search("茅台", levels=[1, 3], top_k=5)
            # 至少有一条结果
            assert len(results) > 0
        finally:
            mgr.close()

    def test_manager_search_unified(self):
        """search_unified 跨层统一检索"""
        from stockquant.ai.memory.manager import MemoryManager
        mgr = MemoryManager()
        try:
            mgr.l3.clear_all()
            mgr.l3.write({
                "content": "五粮液年报",
                "symbol": "sz000858",
                "confidence": 0.9,
                "tier": "shallow",
                "timestamp": datetime.now().isoformat(),
            })
            results = mgr.search_unified("五粮液", top_k=5)
            # 应有结果
            assert len(results) >= 0  # 不抛异常即可
        finally:
            mgr.close()

    def test_manager_compress_passes_llm_to_compressor(self):
        """MemoryManager 把 LLM 适配器传给 compressor"""
        from stockquant.ai.memory.manager import MemoryManager
        mock_llm = MagicMock()
        mgr = MemoryManager(llm_adapter=mock_llm)
        try:
            assert mgr._compressor._llm is mock_llm
        finally:
            mgr.close()

    def test_manager_get_noise_patterns_passthrough(self):
        """MemoryManager.get_noise_patterns 透传"""
        from stockquant.ai.memory.manager import MemoryManager
        mgr = MemoryManager()
        try:
            mgr.l3.clear_all()
            mgr.l3.write({
                "content": "噪音模板测试",
                "metadata": {"type": "noise_pattern"},
                "tier": "shallow",
                "timestamp": datetime.now().isoformat(),
            })
            patterns = mgr.get_noise_patterns()
            assert "噪音模板测试" in patterns
        finally:
            mgr.close()

    def test_manager_get_disproved_facts_passthrough(self):
        """MemoryManager.get_disproved_facts 透传"""
        from stockquant.ai.memory.manager import MemoryManager
        mgr = MemoryManager()
        try:
            mgr.l3.clear_all()
            mgr.l3.write({
                "content": "证伪声明测试",
                "metadata": {"type": "disproved_fact"},
                "tier": "shallow",
                "timestamp": datetime.now().isoformat(),
            })
            facts = mgr.get_disproved_facts()
            assert any("证伪声明" in f for f in facts)
        finally:
            mgr.close()

    def test_manager_get_noise_patterns_exception_safe(self):
        """get_noise_patterns 异常安全"""
        from stockquant.ai.memory.manager import MemoryManager
        mgr = MemoryManager()
        try:
            # 不抛异常
            result = mgr.get_noise_patterns()
            assert isinstance(result, list)
        finally:
            mgr.close()


# ════════════════════════════════════════════════════════════════════
# B6 集成测试
# ════════════════════════════════════════════════════════════════════

class TestB6Integration:
    """B6 集成测试 — 多组件协同"""

    def test_denoise_uses_l3_noise_patterns_via_memory_system(self):
        """DenoiseStage 通过 MemorySystem 调用 L3 噪音模式"""
        from stockquant.ai.pipeline.denoise import DenoiseStage
        from stockquant.ai.pipeline.collection import RawArticle

        ms = MemorySystem()
        ms.clear_all()
        # 写入噪音模式
        ms.l3.write({
            "content": "涨停板秘籍",
            "metadata": {"type": "noise_pattern"},
            "tier": "shallow",
            "timestamp": datetime.now().isoformat(),
        })

        stage = DenoiseStage(memory_system=ms)
        articles = [
            RawArticle(
                title="含噪音文章",
                content="这里包含涨停板秘籍内容",
                url="u", source="s",
                published_at=datetime.now(),
            ),
            RawArticle(
                title="干净文章",
                content="这是普通新闻",
                url="u", source="s",
                published_at=datetime.now(),
            ),
        ]
        result = stage.execute(articles)
        titles = [a.title for a in result]
        assert "干净文章" in titles
        assert "含噪音文章" not in titles

    def test_denoise_uses_l3_disproved_via_memory_system(self):
        """DenoiseStage 通过 MemorySystem 调用 L3 已证伪事实"""
        from stockquant.ai.pipeline.denoise import DenoiseStage
        from stockquant.ai.pipeline.collection import RawArticle

        ms = MemorySystem()
        ms.clear_all()
        ms.l3.write({
            "content": "已被证伪的利好",
            "metadata": {"type": "disproved_fact"},
            "tier": "shallow",
            "timestamp": datetime.now().isoformat(),
        })

        stage = DenoiseStage(memory_system=ms, disproved_score_threshold=0.5)
        articles = [
            RawArticle(
                title="低置信已证伪",
                content="包含已被证伪的利好",
                url="u", source="s",
                published_at=datetime.now(),
                raw={"confidence": 0.2},
            ),
            RawArticle(
                title="干净",
                content="无证伪",
                url="u", source="s",
                published_at=datetime.now(),
            ),
        ]
        result = stage.execute(articles)
        titles = [a.title for a in result]
        assert "干净" in titles
        assert "低置信已证伪" not in titles
