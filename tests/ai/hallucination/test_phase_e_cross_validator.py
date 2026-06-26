# -*- coding: utf-8 -*-
"""F020 Phase E2 测试 — 多模型交叉验证 (CrossValidator)

覆盖：
1. 数据结构 (ModelVerifyResult, VerifyResult)
2. JSON 解析（纯 JSON / ```json``` 块 / 嵌入文本）
3. 单模型调用（成功/异常/超时）
4. 聚合策略（多数同意/平票/模型不足）
5. 批量验证
6. 便捷函数 multi_model_verify
7. 集成：完整声明 + 多模型
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock

import pytest

from stockquant.ai.hallucination.cross_validator import (
    CrossValidator,
    ModelVerifyResult,
    VerifyResult,
    VERIFICATION_PROMPT_TEMPLATE,
    multi_model_verify,
    reset_default_validator,
)
from stockquant.agent.llm_adapter import LLMResponse


# ── 辅助 ──────────────────────────────────────────────────────────────────


def run_async(coro):
    """同步执行异步协程"""
    return asyncio.new_event_loop().run_until_complete(coro)


def _make_sync_adapter(content: str) -> MagicMock:
    """构造同步 mock adapter（模拟 LLMAdapter.call）"""
    adapter = MagicMock(spec=["call"])
    adapter.call.return_value = LLMResponse(content=content)
    return adapter


def _make_async_adapter(content: str) -> MagicMock:
    """构造异步 mock adapter（call 是协程函数）"""
    async def _call(messages):
        return LLMResponse(content=content)
    adapter = MagicMock(spec=["call"])
    adapter.call = _call
    return adapter


def _make_failing_adapter(error: Exception) -> MagicMock:
    """构造抛异常的 mock adapter"""
    adapter = MagicMock(spec=["call"])
    adapter.call.side_effect = error
    return adapter


def _make_three_adapters(
    contents: Tuple[str, str, str],
) -> List[Tuple[str, Any]]:
    """快速构造三个 (name, adapter)"""
    return [
        ("openai", _make_sync_adapter(contents[0])),
        ("anthropic", _make_sync_adapter(contents[1])),
        ("deepseek", _make_sync_adapter(contents[2])),
    ]


def _json_response(verified: bool, confidence: float = 0.8, reason: str = "OK") -> str:
    """构造标准 JSON 响应字符串"""
    return json.dumps({
        "verified": verified,
        "confidence": confidence,
        "reasoning": reason,
    })


# ── 1. 数据结构 ────────────────────────────────────────────────────────────


class TestModelVerifyResult:
    def test_default_values(self):
        r = ModelVerifyResult()
        assert r.model == ""
        assert r.verified is False
        assert r.confidence == 0.0
        assert r.reasoning == ""
        assert r.error is None
        assert r.duration_ms == 0

    def test_custom_init(self):
        r = ModelVerifyResult(
            model="openai", verified=True, confidence=0.9,
            reasoning="合理", error=None, duration_ms=120,
        )
        assert r.model == "openai"
        assert r.verified is True
        assert r.confidence == 0.9
        assert r.duration_ms == 120


class TestVerifyResult:
    def test_default_values(self):
        r = VerifyResult()
        assert r.claim == ""
        assert r.consensus == "insufficient"
        assert r.verified is False
        assert r.conflict is False
        assert r.needs_human_review is False
        assert r.per_model_results == []
        assert r.decision_rule == ""

    def test_custom_init(self):
        r = VerifyResult(
            claim="x", consensus="agree", verified=True,
            confidence=0.8, conflict=True, needs_human_review=True,
            decision_rule="2/3",
        )
        assert r.consensus == "agree"
        assert r.verified is True
        assert r.conflict is True


# ── 2. JSON 解析 ──────────────────────────────────────────────────────────


class TestParseJsonResponse:
    def test_pure_json(self):
        content = '{"verified": true, "confidence": 0.8, "reasoning": "合理"}'
        result = CrossValidator._parse_json_response(content)
        assert result["verified"] is True
        assert result["confidence"] == 0.8

    def test_code_block_json(self):
        content = '```json\n{"verified": false, "confidence": 0.3}\n```'
        result = CrossValidator._parse_json_response(content)
        assert result["verified"] is False
        assert result["confidence"] == 0.3

    def test_embedded_json(self):
        content = '好的，我的判断如下：{"verified": true, "confidence": 0.7} 希望对你有帮助。'
        result = CrossValidator._parse_json_response(content)
        assert result["verified"] is True
        assert result["confidence"] == 0.7

    def test_invalid_json_returns_none(self):
        assert CrossValidator._parse_json_response("") is None
        assert CrossValidator._parse_json_response("纯文本无 JSON") is None
        assert CrossValidator._parse_json_response("{invalid}") is None


# ── 3. 单模型调用 ──────────────────────────────────────────────────────────


class TestVerifyWithModel:
    def test_successful_call(self):
        adapter = _make_sync_adapter(_json_response(True, 0.9, "合理"))
        v = CrossValidator(model_adapters=[("openai", adapter)])
        results = run_async(v.verify("营收100亿"))
        assert len(results.per_model_results) == 1
        r = results.per_model_results[0]
        assert r.model == "openai"
        assert r.verified is True
        assert r.confidence == 0.9
        assert r.error is None
        assert r.duration_ms >= 0

    def test_async_adapter(self):
        """适配异步 adapter.call（协程函数）"""
        adapter = _make_async_adapter(_json_response(True, 0.85))
        v = CrossValidator(model_adapters=[("anthropic", adapter)])
        results = run_async(v.verify("营收100亿"))
        r = results.per_model_results[0]
        assert r.model == "anthropic"
        assert r.verified is True

    def test_adapter_exception(self):
        """adapter.call 抛异常时应被捕获"""
        adapter = _make_failing_adapter(RuntimeError("API down"))
        v = CrossValidator(model_adapters=[("openai", adapter)])
        results = run_async(v.verify("营收100亿"))
        r = results.per_model_results[0]
        assert r.verified is False
        assert r.error is not None
        assert "API down" in r.error

    def test_invalid_json_response(self):
        """LLM 返回非 JSON 文本"""
        adapter = _make_sync_adapter("这是我的判断：合理但无 JSON")
        v = CrossValidator(model_adapters=[("openai", adapter)])
        results = run_async(v.verify("营收100亿"))
        r = results.per_model_results[0]
        assert r.verified is False
        assert r.error is not None
        assert "无法解析" in r.error

    def test_missing_verified_field(self):
        """JSON 缺少 verified 字段时默认为 False"""
        adapter = _make_sync_adapter('{"confidence": 0.5, "reasoning": "不确定"}')
        v = CrossValidator(model_adapters=[("openai", adapter)])
        results = run_async(v.verify("营收100亿"))
        r = results.per_model_results[0]
        assert r.verified is False
        assert r.confidence == 0.5

    def test_missing_confidence_field(self):
        """JSON 缺少 confidence 字段时默认为 0.0"""
        adapter = _make_sync_adapter('{"verified": true, "reasoning": "OK"}')
        v = CrossValidator(model_adapters=[("openai", adapter)])
        results = run_async(v.verify("营收100亿"))
        r = results.per_model_results[0]
        assert r.verified is True
        assert r.confidence == 0.0


# ── 4. 聚合策略 ──────────────────────────────────────────────────────────


class TestAggregation:
    def test_all_agree_true(self):
        """3/3 同意 True"""
        adapters = _make_three_adapters(
            (_json_response(True, 0.9), _json_response(True, 0.85), _json_response(True, 0.8))
        )
        v = CrossValidator(model_adapters=adapters)
        result = run_async(v.verify("营收100亿"))
        assert result.consensus == "agree"
        assert result.verified is True
        assert result.conflict is False
        assert result.needs_human_review is False
        assert "3/3" in result.decision_rule

    def test_all_agree_false(self):
        """3/3 同意 False"""
        adapters = _make_three_adapters(
            (_json_response(False, 0.9), _json_response(False, 0.85), _json_response(False, 0.8))
        )
        v = CrossValidator(model_adapters=adapters)
        result = run_async(v.verify("虚构声明"))
        assert result.consensus == "agree"
        assert result.verified is False
        assert result.conflict is False
        assert "3/3" in result.decision_rule

    def test_majority_true_with_minority(self):
        """2/3 True + 1/3 False = 通过但有分歧"""
        adapters = _make_three_adapters(
            (_json_response(True, 0.9), _json_response(True, 0.8), _json_response(False, 0.6))
        )
        v = CrossValidator(model_adapters=adapters)
        result = run_async(v.verify("声明"))
        assert result.consensus == "agree"
        assert result.verified is True
        assert result.conflict is True
        assert result.needs_human_review is True
        assert "2/3" in result.decision_rule

    def test_majority_false_with_minority(self):
        """2/3 False + 1/3 True = 失败但有分歧"""
        adapters = _make_three_adapters(
            (_json_response(False, 0.7), _json_response(False, 0.6), _json_response(True, 0.8))
        )
        v = CrossValidator(model_adapters=adapters)
        result = run_async(v.verify("声明"))
        assert result.consensus == "agree"
        assert result.verified is False
        assert result.conflict is True
        assert result.needs_human_review is True

    def test_tie_disagrees(self):
        """1 vs 1 平票 = disagree"""
        adapters = [
            ("openai", _make_sync_adapter(_json_response(True, 0.8))),
            ("anthropic", _make_sync_adapter(_json_response(False, 0.7))),
        ]
        v = CrossValidator(model_adapters=adapters)
        result = run_async(v.verify("声明"))
        assert result.consensus == "disagree"
        assert result.verified is False
        assert result.conflict is True
        assert result.needs_human_review is True
        assert "平票" in result.decision_rule

    def test_insufficient_models(self):
        """有效模型数少于 min_for_consensus"""
        adapters = [
            ("openai", _make_sync_adapter(_json_response(True, 0.8))),
            ("anthropic", _make_failing_adapter(RuntimeError("down"))),
            ("deepseek", _make_failing_adapter(RuntimeError("down"))),
        ]
        v = CrossValidator(model_adapters=adapters, min_models_for_consensus=2)
        result = run_async(v.verify("声明"))
        assert result.consensus == "insufficient"
        assert result.verified is False
        assert result.needs_human_review is True
        assert "1/3" in result.decision_rule

    def test_avg_confidence(self):
        """平均置信度计算"""
        adapters = _make_three_adapters(
            (_json_response(True, 0.9), _json_response(True, 0.7), _json_response(True, 0.5))
        )
        v = CrossValidator(model_adapters=adapters)
        result = run_async(v.verify("声明"))
        # (0.9 + 0.7 + 0.5) / 3 = 0.7
        assert result.confidence == 0.7


# ── 5. 边界情况 ──────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_claim(self):
        adapter = _make_sync_adapter(_json_response(True))
        v = CrossValidator(model_adapters=[("openai", adapter)])
        result = run_async(v.verify(""))
        assert result.consensus == "insufficient"
        assert "声明为空" in result.decision_rule

    def test_whitespace_claim(self):
        adapter = _make_sync_adapter(_json_response(True))
        v = CrossValidator(model_adapters=[("openai", adapter)])
        result = run_async(v.verify("   "))
        assert result.consensus == "insufficient"

    def test_min_models_for_consensus_floor(self):
        """min_models_for_consensus 最小为 2"""
        v = CrossValidator(
            model_adapters=[("openai", _make_sync_adapter(_json_response(True)))],
            min_models_for_consensus=1,
        )
        assert v._min_for_consensus == 2  # 强制 ≥2

    def test_no_adapters_raises_on_init(self):
        """无 adapters 且无 models 时使用 DEFAULT_MODELS"""
        # 不应抛异常（默认会构造 3 个 LLMAdapter，但不实际调用）
        # 这里只验证初始化不抛
        try:
            v = CrossValidator()
            assert len(v._adapters) == 3
        except ImportError:
            # litellm 可能未安装，跳过
            pytest.skip("litellm 未安装")


# ── 6. 批量验证 ──────────────────────────────────────────────────────────


class TestVerifyBatch:
    def test_empty_batch(self):
        adapters = _make_three_adapters(
            (_json_response(True), _json_response(True), _json_response(True))
        )
        v = CrossValidator(model_adapters=adapters)
        results = run_async(v.verify_batch([]))
        assert results == []

    def test_batch_preserves_order(self):
        adapters = _make_three_adapters(
            (_json_response(True), _json_response(True), _json_response(True))
        )
        v = CrossValidator(model_adapters=adapters)
        results = run_async(v.verify_batch(["claim1", "claim2", "claim3"]))
        assert len(results) == 3
        assert results[0].claim == "claim1"
        assert results[1].claim == "claim2"
        assert results[2].claim == "claim3"


# ── 7. 模块级便捷函数 ────────────────────────────────────────────────────


class TestModuleLevelFunction:
    def setup_method(self):
        reset_default_validator()

    def teardown_method(self):
        reset_default_validator()

    def test_multi_model_verify_with_adapters(self):
        """注入 adapters 调用模块级函数"""
        adapters = _make_three_adapters(
            (_json_response(True, 0.8), _json_response(True, 0.85), _json_response(True, 0.9))
        )
        result = run_async(multi_model_verify("声明", model_adapters=adapters))
        assert result.consensus == "agree"
        assert result.verified is True
        assert len(result.per_model_results) == 3

    def test_multi_model_verify_empty_claim(self):
        adapters = _make_three_adapters(
            (_json_response(True), _json_response(True), _json_response(True))
        )
        result = run_async(multi_model_verify("", model_adapters=adapters))
        assert result.consensus == "insufficient"


# ── 8. 集成 ──────────────────────────────────────────────────────────────


class TestIntegration:
    def test_real_claim_with_consensus(self):
        """完整流程：3 模型对真实声明达成共识"""
        adapters = _make_three_adapters(
            (_json_response(True, 0.85, "声明合理"),
             _json_response(True, 0.80, "符合事实"),
             _json_response(True, 0.90, "数据真实"))
        )
        v = CrossValidator(model_adapters=adapters)
        result = run_async(v.verify("贵州茅台 2024 年营收同比增长 15%"))
        assert result.consensus == "agree"
        assert result.verified is True
        assert result.conflict is False
        assert result.needs_human_review is False
        assert "3/3" in result.decision_rule

    def test_disagreement_triggers_human_review(self):
        """模型分歧触发人工复核"""
        adapters = _make_three_adapters(
            (_json_response(True, 0.9, "合理"),
             _json_response(False, 0.6, "数据可疑"),
             _json_response(True, 0.8, "符合趋势"))
        )
        v = CrossValidator(model_adapters=adapters)
        result = run_async(v.verify("某公司净利润增长 500%"))
        assert result.consensus == "agree"
        assert result.verified is True
        assert result.conflict is True
        assert result.needs_human_review is True

    def test_one_model_down_still_works(self):
        """单模型故障不影响整体验证"""
        adapters = [
            ("openai", _make_sync_adapter(_json_response(True, 0.8))),
            ("anthropic", _make_sync_adapter(_json_response(True, 0.85))),
            ("deepseek", _make_failing_adapter(RuntimeError("API 不可用"))),
        ]
        v = CrossValidator(model_adapters=adapters, min_models_for_consensus=2)
        result = run_async(v.verify("营收100亿"))
        # 2/2 有效模型均 True
        assert result.consensus == "agree"
        assert result.verified is True
        # 第三个模型有 error
        assert result.per_model_results[2].error is not None

    def test_prompt_template_contains_claim(self):
        """验证提示词模板包含声明字段"""
        prompt = VERIFICATION_PROMPT_TEMPLATE.format(claim="测试声明 XYZ")
        assert "测试声明 XYZ" in prompt
        assert "verified" in prompt
        assert "confidence" in prompt
        assert "reasoning" in prompt
