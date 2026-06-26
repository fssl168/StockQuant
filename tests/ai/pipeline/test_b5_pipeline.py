# -*- coding: utf-8 -*-
"""F020 B5 管线四阶段完整化测试

覆盖 Phase B5.1-B5.3 新增能力：
- DenoiseStage Step 4 (l3_noise_filter) + Step 5 (l3_disproved_filter)
- SummarizeStage Step 2-6 (prompt_constraints + LLM + multi_level + 5 步验证 + 回写)
- ElevateStage Step 1-5 (l3_retrieval + reasoning_chain + cross_validation + l3_writeback + reflection)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from stockquant.ai.pipeline.collection import RawArticle
from stockquant.ai.pipeline.denoise import DenoiseStage, DEFAULT_NOISE_PATTERNS
from stockquant.ai.pipeline.summarize import SummarizeStage, PROMPT_CONSTRAINTS
from stockquant.ai.pipeline.elevate import ElevateStage, CLAIM_TYPES


# ─── 测试辅助 ─────────────────────────────────────────────────────────


def _make_articles(n: int = 3, source: str = "eastmoney") -> List[RawArticle]:
    """构造测试文章列表"""
    return [
        RawArticle(
            title=f"标题 {i}",
            content=f"内容 {i} 茅台 利好 上涨",
            url=f"http://x/{i}",
            source=source,
            published_at=datetime.now(),
            raw={"symbol": "sh600519"},
        )
        for i in range(n)
    ]


def _make_noise_articles() -> List[RawArticle]:
    """构造噪音模式文章"""
    return [
        RawArticle(
            title="震惊！这只股票要涨停",
            content="扫码进群免费诊股，稳赚不赔",
            url="http://spam/1",
            source="spam",
            published_at=datetime.now(),
        ),
        RawArticle(
            title="正常新闻标题",
            content="公司发布业绩预告",
            url="http://ok/2",
            source="eastmoney",
            published_at=datetime.now(),
        ),
    ]


class MockLLM:
    """模拟 LLM 适配器"""

    def __init__(self, response: str = ""):
        self.response = response
        self.call_count = 0

    def chat(self, message, system_prompt=""):
        self.call_count += 1
        return self.response


# ─── B5.1 DenoiseStage 5 步测试 ─────────────────────────────────────


class TestDenoiseStage5Steps:
    """测试降噪阶段 5 步完整化"""

    def test_step1_temporal_filter_preserved(self):
        """Step 1 时效过滤（保留）"""
        stage = DenoiseStage(max_age_hours=24)
        old = RawArticle(title="old", content="c", url="u", source="s",
                        published_at=datetime.now() - timedelta(days=2))
        new = RawArticle(title="new", content="c", url="u", source="s",
                        published_at=datetime.now())
        result = stage.execute([old, new])
        assert len(result) == 1
        assert result[0].title == "new"

    def test_step2_deduplicate_preserved(self):
        """Step 2 去重（保留）"""
        stage = DenoiseStage()
        a1 = RawArticle(title="same title words", content="c1", url="u1",
                       source="s", published_at=datetime.now())
        a2 = RawArticle(title="same title words", content="c2", url="u2",
                       source="s", published_at=datetime.now())
        result = stage.execute([a1, a2])
        assert len(result) == 1

    def test_step3_source_rank_preserved(self):
        """Step 3 信源排序（保留）"""
        stage = DenoiseStage()
        low = RawArticle(title="low", content="c", url="u", source="xueqiu",
                        published_at=datetime.now())
        high = RawArticle(title="high", content="c", url="u", source="cninfo",
                        published_at=datetime.now())
        result = stage.execute([low, high])
        assert result[0].source == "cninfo"

    def test_step4_default_noise_patterns_filter(self):
        """Step 4 默认噪音模式过滤（无 L3）"""
        stage = DenoiseStage()
        articles = _make_noise_articles()
        result = stage.execute(articles)
        # 震惊+扫码进群+免费诊股+稳赚不赔 应被过滤
        titles = [a.title for a in result]
        assert "正常新闻标题" in titles
        assert "震惊！这只股票要涨停" not in titles

    def test_step4_l3_noise_patterns_via_search_long_term(self):
        """Step 4 通过 search_long_term 检索 L3 噪音模式"""
        # 用 spec 限制 MagicMock 自动属性，触发 search_long_term 降级路径
        mock_memory = MagicMock(spec=["search_long_term"])
        # 配置 search_long_term 返回噪音模式
        mock_memory.search_long_term.return_value = [
            {"content": "独家秘方", "type": "noise_pattern"},
        ]
        stage = DenoiseStage(memory_system=mock_memory)
        articles = [
            RawArticle(title="正常", content="独家秘方在此", url="u",
                       source="s", published_at=datetime.now()),
            RawArticle(title="其他", content="普通内容", url="u",
                       source="s", published_at=datetime.now()),
        ]
        result = stage.execute(articles)
        # 独家秘方 应被过滤
        titles = [a.title for a in result]
        assert "其他" in titles
        assert "正常" not in titles

    def test_step4_l3_noise_patterns_via_dedicated_method(self):
        """Step 4 通过 B6.3 专用 get_noise_patterns 接口"""
        mock_memory = MagicMock()
        mock_memory.get_noise_patterns.return_value = ["定制噪音词"]
        stage = DenoiseStage(memory_system=mock_memory)
        articles = [
            RawArticle(title="含噪音", content="这里包含定制噪音词", url="u",
                       source="s", published_at=datetime.now()),
            RawArticle(title="干净", content="纯新闻内容", url="u",
                       source="s", published_at=datetime.now()),
        ]
        result = stage.execute(articles)
        titles = [a.title for a in result]
        assert "干净" in titles
        assert "含噪音" not in titles

    def test_step5_disproved_filter_low_confidence(self):
        """Step 5 已证伪事实过滤（低置信度才过滤）"""
        mock_memory = MagicMock()
        mock_memory.get_disproved_facts.return_value = ["已被证伪的声明"]
        stage = DenoiseStage(memory_system=mock_memory, disproved_score_threshold=0.5)
        articles = [
            RawArticle(title="低置信已证伪", content="包含已被证伪的声明", url="u",
                       source="s", published_at=datetime.now(),
                       raw={"confidence": 0.3}),
            RawArticle(title="高置信已证伪", content="也包含已被证伪的声明", url="u",
                       source="s", published_at=datetime.now(),
                       raw={"confidence": 0.9}),
            RawArticle(title="干净", content="无证伪声明", url="u",
                       source="s", published_at=datetime.now()),
        ]
        result = stage.execute(articles)
        titles = [a.title for a in result]
        # 低置信度已证伪 → 过滤
        assert "低置信已证伪" not in titles
        # 高置信度已证伪 → 保留（让上层决定）
        assert "高置信已证伪" in titles
        assert "干净" in titles

    def test_backward_compat_no_memory(self):
        """向后兼容：无 memory_system 时等同旧 3 步 + 默认噪音库"""
        stage = DenoiseStage()
        articles = _make_articles(2)
        result = stage.execute(articles)
        assert len(result) == 2

    def test_factory_make_denoise_stage(self):
        """工厂函数"""
        stage = DenoiseStage()
        from stockquant.ai.pipeline.denoise import make_denoise_stage
        s2 = make_denoise_stage()
        assert isinstance(s2, DenoiseStage)
        assert isinstance(stage, DenoiseStage)


# ─── B5.2 SummarizeStage 6 步测试 ────────────────────────────────────


class TestSummarizeStage6Steps:
    """测试总结阶段 6 步完整化"""

    def test_step1_memory_retrieval_no_memory(self):
        """Step 1 无 memory 时 facts 为空"""
        stage = SummarizeStage()
        articles = _make_articles(2)
        result = stage.execute(articles)
        assert result["facts"] == []

    def test_step1_memory_retrieval_with_memory(self):
        """Step 1 有 memory 时调用三源检索"""
        mock_memory = MagicMock()
        mock_memory.search_working.return_value = [{"content": "L1"}]
        mock_memory.search_short_term.return_value = [{"content": "L2"}]
        mock_memory.search_long_term.return_value = [{"content": "L3"}]
        stage = SummarizeStage(memory=mock_memory)
        articles = _make_articles(2)
        result = stage.execute(articles)
        assert len(result["facts"]) > 0
        sources = [f["source"] for f in result["facts"]]
        assert "L1" in sources or "L2" in sources or "L3" in sources

    def test_step2_prompt_constraint_inject(self):
        """Step 2 返回反幻觉约束"""
        stage = SummarizeStage()
        constraints = stage._prompt_constraint_inject()
        assert len(constraints) == len(PROMPT_CONSTRAINTS)
        assert any("编造" in c for c in constraints)

    def test_step3_llm_summarize_fallback_to_rule(self):
        """Step 3 无 LLM 时降级到规则总结"""
        stage = SummarizeStage()
        articles = _make_articles(2)
        result = stage.execute(articles)
        assert "summary" in result
        assert "共采集" in result["summary"]
        assert result["trend"] in ("unknown", "上涨", "下跌", "震荡", "不确定")

    def test_step3_llm_summarize_with_mock_llm(self):
        """Step 3 有 LLM 时调用 LLM 生成总结"""
        mock_llm = MockLLM(response='{"summary": "LLM 总结", "trend": "上涨", "confidence": 0.8, "facts": ["f1"], "anomalies": [], "reasoning_chain": ["step1"]}')
        stage = SummarizeStage(llm_adapter=mock_llm)
        articles = _make_articles(2)
        result = stage.execute(articles)
        assert mock_llm.call_count == 1
        assert result["summary"] == "LLM 总结"
        assert result["trend"] == "上涨"
        assert result["confidence"] == 0.8

    def test_step3_llm_failure_falls_back_to_rule(self):
        """Step 3 LLM 异常时降级到规则总结"""
        mock_llm = MockLLM()
        mock_llm.chat = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("LLM down"))
        stage = SummarizeStage(llm_adapter=mock_llm)
        articles = _make_articles(2)
        result = stage.execute(articles)
        # 应回退到规则总结
        assert "共采集" in result["summary"]

    def test_step4_multi_level_summary(self):
        """Step 4 多级摘要"""
        stage = SummarizeStage()
        articles = _make_articles(3)
        result = stage.execute(articles)
        assert "multi_level" in result
        assert "level" in result
        assert result["level"] in ("session", "daily", "weekly", "monthly")

    def test_step5_five_step_verify(self):
        """Step 5 五步验证链"""
        stage = SummarizeStage()
        articles = _make_articles(3)
        result = stage.execute(articles)
        assert "verification" in result
        verify = result["verification"]
        assert "passed" in verify
        assert "confidence" in verify
        assert "steps" in verify
        steps = verify["steps"]
        assert "fact_check" in steps
        assert "source_check" in steps
        assert "consistency" in steps
        assert "cross_validation" in steps

    def test_step6_memory_writeback_no_memory(self):
        """Step 6 无 memory 时跳过回写"""
        stage = SummarizeStage()
        articles = _make_articles(2)
        # 不应抛出异常
        result = stage.execute(articles)
        assert result["summary"]

    def test_step6_memory_writeback_with_memory(self):
        """Step 6 有 memory 时回写 L2 + L3"""
        mock_memory = MagicMock()
        # search 返回空，避免 facts 过多触发额外逻辑
        mock_memory.search_working.return_value = []
        mock_memory.search_short_term.return_value = []
        mock_memory.search_long_term.return_value = []
        mock_memory.l3 = MagicMock()
        mock_memory.l3._user_id = "test_user"
        stage = SummarizeStage(memory=mock_memory)
        articles = _make_articles(3)
        result = stage.execute(articles)
        # confidence < 0.6 时不写 L3，但 L2 总是写
        assert mock_memory.add_short_term.called

    def test_factory_make_summarize_stage(self):
        """工厂函数"""
        from stockquant.ai.pipeline.summarize import make_summarize_stage
        s = make_summarize_stage()
        assert isinstance(s, SummarizeStage)


# ─── B5.3 ElevateStage 5 步测试 ──────────────────────────────────────


class TestElevateStage5Steps:
    """测试升华阶段 5 步完整化"""

    def _make_summary(self, **kwargs) -> Dict[str, Any]:
        """构造测试 summary"""
        defaults = {
            "summary": "茅台 利好 上涨",
            "verified": True,
            "article_count": 5,
            "facts": [],
            "confidence": 0.7,
            "level": "session",
            "trend": "上涨",
        }
        defaults.update(kwargs)
        return defaults

    def test_step1_l3_retrieval_no_memory(self):
        """Step 1 无 memory 时无 L3 上下文"""
        stage = ElevateStage()
        summary = self._make_summary()
        result = stage.execute(summary)
        assert result["l3_context_count"] == 0

    def test_step1_l3_retrieval_with_memory(self):
        """Step 1 有 memory 时检索 L3"""
        mock_memory = MagicMock()
        mock_memory.search_by_layer.return_value = [{"content": "L3 历史", "id": "1"}]
        mock_memory.search_long_term.return_value = []
        stage = ElevateStage(memory=mock_memory)
        summary = self._make_summary()
        result = stage.execute(summary)
        assert result["l3_context_count"] > 0

    def test_step2_multi_source_fusion_confirmed_trend(self):
        """Step 2 多源融合 — confirmed_trend 洞察"""
        stage = ElevateStage()
        summary = self._make_summary(verified=True, article_count=5, confidence=0.7)
        result = stage.execute(summary)
        insight_types = [i["type"] for i in result["insights"]]
        assert "confirmed_trend" in insight_types

    def test_step2_high_confidence_insight(self):
        """Step 2 多源融合 — high_confidence_insight 洞察（多源 ≥3）"""
        stage = ElevateStage()
        summary = self._make_summary(
            verified=True, article_count=5, confidence=0.7, facts=[1, 2, 3, 4]
        )
        result = stage.execute(summary)
        insight_types = [i["type"] for i in result["insights"]]
        assert "high_confidence_insight" in insight_types

    def test_step3_reasoning_chain_verify(self):
        """Step 3 推理链验证 + 声明分解"""
        stage = ElevateStage()
        summary = self._make_summary()
        result = stage.execute(summary)
        for insight in result["insights"]:
            assert "reasoning_verified" in insight
            # confirmed_trend 应该 verified=True
            if insight["type"] == "confirmed_trend":
                assert insight["reasoning_verified"] is True
                assert "reasoning_chain" in insight

    def test_step3_claims_decomposition(self):
        """Step 3 原子声明分解"""
        stage = ElevateStage()
        summary = self._make_summary()
        result = stage.execute(summary)
        for insight in result["insights"]:
            if "claims" in insight:
                # 至少有声明类型字段
                assert isinstance(insight.get("claim_types"), list)

    def test_step3_claim_type_classification(self):
        """Step 3 声明类型分类"""
        stage = ElevateStage()
        # numeric
        assert stage._classify_claim("营收增长 50%") == "numeric"
        # temporal
        assert stage._classify_claim("2024年第一季度业绩") == "temporal"
        # computed
        assert stage._classify_claim("同比增长 30%") == "computed"
        # comparative
        assert stage._classify_claim("高于行业平均水平") == "comparative"
        # regulatory
        assert stage._classify_claim("证监会处罚") == "regulatory"
        # entity（默认）
        assert stage._classify_claim("公司发布") == "entity"

    def test_step4_cross_validation_with_l3(self):
        """Step 4 交叉验证（有 L3 支撑）"""
        mock_memory = MagicMock()
        mock_memory.search_by_layer.return_value = [{"content": "L3 历史", "id": "1"}]
        mock_memory.search_long_term.return_value = []
        stage = ElevateStage(memory=mock_memory)
        summary = self._make_summary(verified=True, article_count=5, confidence=0.7)
        result = stage.execute(summary)
        # confirmed_trend 有 L3 支撑 → cross_validated=True
        for insight in result["insights"]:
            if insight["type"] == "confirmed_trend":
                assert insight["cross_validated"] is True

    def test_step4_cross_validation_no_l3(self):
        """Step 4 交叉验证（无 L3 支撑 → 降权）"""
        stage = ElevateStage()
        summary = self._make_summary(verified=True, article_count=5, confidence=0.7)
        result = stage.execute(summary)
        for insight in result["insights"]:
            if insight["type"] == "confirmed_trend":
                assert insight["cross_validated"] is False

    def test_step5_l3_writeback_no_memory(self):
        """Step 5 无 memory 时跳过回写"""
        stage = ElevateStage()
        summary = self._make_summary()
        result = stage.execute(summary)
        assert result.get("reflection_triggered") in (False, None)

    def test_step5_l3_writeback_with_memory(self):
        """Step 5 有 memory 时写入 L3"""
        mock_memory = MagicMock()
        mock_memory.search_by_layer.return_value = [{"content": "L3 历史", "id": "1"}]
        mock_memory.search_long_term.return_value = []
        mock_memory.l1 = MagicMock()
        mock_memory.l1.reflect = MagicMock(return_value="反思内容")
        mock_memory.l3 = MagicMock()
        mock_memory.l3._user_id = "test_user"
        stage = ElevateStage(memory=mock_memory)
        summary = self._make_summary(verified=True, article_count=5, confidence=0.7)
        result = stage.execute(summary)
        # 应该调用了 add_long_term（confirmed_trend cross_validated=True, confidence≥0.5）
        assert mock_memory.add_long_term.called
        assert result.get("reflection_triggered") is True

    def test_contradiction_detection(self):
        """矛盾检测"""
        stage = ElevateStage()
        summary = self._make_summary(summary="利好 上涨", verified=True, article_count=5)
        # L3 中存在相反方向 → 检测到矛盾
        l3_context = [{"content": "利空 下跌 亏损"}]
        contradiction = stage._detect_contradiction(summary, l3_context)
        assert contradiction is not None

    def test_backward_compat_no_memory(self):
        """向后兼容：无 memory 时仍可执行"""
        stage = ElevateStage()
        summary = self._make_summary()
        result = stage.execute(summary)
        assert result["elevated"] is True
        assert "insights" in result

    def test_factory_make_elevate_stage(self):
        """工厂函数"""
        from stockquant.ai.pipeline.elevate import make_elevate_stage
        s = make_elevate_stage()
        assert isinstance(s, ElevateStage)


# ─── 端到端集成测试 ──────────────────────────────────────────────────


class TestPipelineIntegration:
    """端到端：Collection → Denoise → Summarize → Elevate"""

    def test_full_pipeline_no_memory_no_llm(self):
        """无 memory + 无 LLM 全流程（降级模式）"""
        articles = _make_articles(3, source="eastmoney")
        # Denoise
        denoise_stage = DenoiseStage()
        filtered = denoise_stage.execute(articles)
        assert len(filtered) == 3
        # Summarize
        summarize_stage = SummarizeStage()
        summary = summarize_stage.execute(filtered)
        assert "summary" in summary
        assert summary["article_count"] == 3
        # Elevate
        elevate_stage = ElevateStage()
        result = elevate_stage.execute(summary)
        assert result["elevated"] is True
        assert len(result["insights"]) > 0

    def test_full_pipeline_with_memory(self):
        """有 memory 的全流程"""
        mock_memory = MagicMock()
        mock_memory.search_working.return_value = []
        mock_memory.search_short_term.return_value = []
        mock_memory.search_long_term.return_value = []
        mock_memory.search_by_layer.return_value = []
        mock_memory.l1 = MagicMock()
        mock_memory.l1.reflect = MagicMock(return_value="反思")
        mock_memory.l3 = MagicMock()
        mock_memory.l3._user_id = "test_user"

        articles = _make_articles(4, source="eastmoney")
        denoise_stage = DenoiseStage(memory_system=mock_memory)
        filtered = denoise_stage.execute(articles)
        assert len(filtered) == 4

        summarize_stage = SummarizeStage(memory=mock_memory)
        summary = summarize_stage.execute(filtered)
        assert summary["article_count"] == 4

        elevate_stage = ElevateStage(memory=mock_memory)
        result = elevate_stage.execute(summary)
        assert result["elevated"] is True

    def test_claim_types_constant(self):
        """CLAIM_TYPES 常量包含六类"""
        assert "numeric" in CLAIM_TYPES
        assert "temporal" in CLAIM_TYPES
        assert "entity" in CLAIM_TYPES
        assert "comparative" in CLAIM_TYPES
        assert "regulatory" in CLAIM_TYPES
        assert "computed" in CLAIM_TYPES
