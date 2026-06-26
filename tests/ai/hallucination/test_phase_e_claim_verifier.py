# -*- coding: utf-8 -*-
"""F020 Phase E1 测试 — FINGROUND 六类原子声明验证 (ClaimVerifier)

覆盖：
1. ClaimType 枚举与 from_str 兼容性
2. classify_claim 优先级与对齐 elevate.py
3. 六类 _verify_* 方法
4. verify_claim / verify_claims_batch 异步入口
5. 异常处理与降级
6. memory_system 多接口兼容（search_by_layer / search_long_term+short_term）
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from stockquant.ai.hallucination.claim_verifier import (
    ClaimType,
    ClaimVerification,
    ClaimVerifier,
)


# ── 辅助 ──────────────────────────────────────────────────────────────────


def run_async(coro):
    """同步执行异步协程"""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_memory_with_layer(items: List[Dict[str, Any]]) -> MagicMock:
    """构造仅支持 search_by_layer 的 memory_system"""
    mem = MagicMock(spec=["search_by_layer"])
    mem.search_by_layer.return_value = items
    return mem


def _make_memory_with_l3_l2(l3_items, l2_items=None) -> MagicMock:
    """构造支持 search_long_term + search_short_term 的 memory_system"""
    mem = MagicMock(spec=["search_long_term", "search_short_term"])
    mem.search_long_term.return_value = l3_items
    mem.search_short_term.return_value = l2_items or []
    return mem


# ── 1. ClaimType 枚举 ─────────────────────────────────────────────────────


class TestClaimTypeEnum:
    def test_enum_values(self):
        assert ClaimType.NUMERIC.value == "numeric"
        assert ClaimType.TEMPORAL.value == "temporal"
        assert ClaimType.ENTITY_ATTR.value == "entity_attr"
        assert ClaimType.COMPARATIVE.value == "comparative"
        assert ClaimType.REGULATORY.value == "regulatory"
        assert ClaimType.COMPUTATIONAL.value == "computational"

    def test_from_str_valid(self):
        assert ClaimType.from_str("numeric") == ClaimType.NUMERIC
        assert ClaimType.from_str("temporal") == ClaimType.TEMPORAL
        assert ClaimType.from_str("entity_attr") == ClaimType.ENTITY_ATTR
        assert ClaimType.from_str("comparative") == ClaimType.COMPARATIVE
        assert ClaimType.from_str("regulatory") == ClaimType.REGULATORY
        assert ClaimType.from_str("computational") == ClaimType.COMPUTATIONAL

    def test_from_str_elevate_compat(self):
        """兼容 elevate.py 输出：'computed' → COMPUTATIONAL, 'entity' → ENTITY_ATTR"""
        assert ClaimType.from_str("computed") == ClaimType.COMPUTATIONAL
        assert ClaimType.from_str("entity") == ClaimType.ENTITY_ATTR

    def test_from_str_none_returns_entity_attr(self):
        assert ClaimType.from_str(None) == ClaimType.ENTITY_ATTR

    def test_from_str_invalid_returns_entity_attr(self):
        assert ClaimType.from_str("unknown_type") == ClaimType.ENTITY_ATTR
        assert ClaimType.from_str("") == ClaimType.ENTITY_ATTR

    def test_str_mixin_serializable(self):
        """str mixin 使得枚举可直接 JSON 序列化"""
        import json
        data = {"type": ClaimType.NUMERIC}
        # ClaimType 继承 str，json.dumps 会将其作为字符串
        assert json.dumps(data) == '{"type": "numeric"}'


# ── 2. ClaimVerification 数据类 ────────────────────────────────────────────


class TestClaimVerification:
    def test_default_values(self):
        cv = ClaimVerification()
        assert cv.claim == ""
        assert cv.claim_type == ""
        assert cv.verified is False
        assert cv.confidence == 0.0
        assert cv.reason == ""
        assert cv.evidence == []
        assert cv.source == ""

    def test_custom_init(self):
        cv = ClaimVerification(
            claim="test", claim_type="numeric",
            verified=True, confidence=0.8,
            reason="matched", source="memory",
            evidence=[{"k": "v"}],
        )
        assert cv.claim == "test"
        assert cv.verified is True
        assert cv.confidence == 0.8
        assert len(cv.evidence) == 1


# ── 3. classify_claim 静态方法 ─────────────────────────────────────────────


class TestClassifyClaim:
    def test_temporal_priority(self):
        """日期优先级最高"""
        assert ClaimVerifier.classify_claim("2023年净利润") == ClaimType.TEMPORAL
        assert ClaimVerifier.classify_claim("2024年Q1财报") == ClaimType.TEMPORAL
        assert ClaimVerifier.classify_claim("5月15日股东大会") == ClaimType.TEMPORAL

    def test_computational(self):
        """同比/环比+数字"""
        assert ClaimVerifier.classify_claim("净利润同比增长30%") == ClaimType.COMPUTATIONAL
        assert ClaimVerifier.classify_claim("环比增长15%") == ClaimType.COMPUTATIONAL
        # 同比但无数字不算 computational（落到后面分类）
        # 注：实际"同比"被识别，但因无数字会被其他规则覆盖
        assert ClaimVerifier.classify_claim("同比增速") == ClaimType.ENTITY_ATTR  # 无数字

    def test_comparative(self):
        assert ClaimVerifier.classify_claim("营收高于行业平均") == ClaimType.COMPARATIVE
        assert ClaimVerifier.classify_claim("市盈率低于同行") == ClaimType.COMPARATIVE

    def test_numeric(self):
        assert ClaimVerifier.classify_claim("营收100亿") == ClaimType.NUMERIC
        assert ClaimVerifier.classify_claim("利润50%") == ClaimType.NUMERIC

    def test_regulatory(self):
        assert ClaimVerifier.classify_claim("证监会立案调查") == ClaimType.REGULATORY
        assert ClaimVerifier.classify_claim("披露处罚公告") == ClaimType.REGULATORY

    def test_entity_attr_fallback(self):
        assert ClaimVerifier.classify_claim("贵州茅台公司") == ClaimType.ENTITY_ATTR
        assert ClaimVerifier.classify_claim("sh600519") == ClaimType.ENTITY_ATTR
        assert ClaimVerifier.classify_claim("") == ClaimType.ENTITY_ATTR
        assert ClaimVerifier.classify_claim("随便一段文字") == ClaimType.ENTITY_ATTR


# ── 4. _verify_numeric 数值型 ──────────────────────────────────────────────


class TestVerifyNumeric:
    def test_no_numbers_fails(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("无数字声明", ClaimType.NUMERIC))
        assert result.verified is False
        assert result.confidence < 0.5
        assert "未提取到数字" in result.reason

    def test_format_check_passes(self):
        """无 memory 时格式合理则通过"""
        v = ClaimVerifier()
        result = run_async(v.verify_claim("营收100亿", ClaimType.NUMERIC))
        assert result.verified is True
        assert result.source == "format_check"
        assert result.confidence == 0.6

    def test_over_precise_fails(self):
        """超过3位小数视为虚构"""
        v = ClaimVerifier()
        result = run_async(v.verify_claim("净利率12.3456%", ClaimType.NUMERIC))
        assert result.verified is False
        assert "过于精确" in result.reason

    def test_memory_match_passes(self):
        """memory 中找到匹配数字则通过"""
        mem_items = [{"content": "营收100亿"}]
        mem = _make_memory_with_layer(mem_items)
        v = ClaimVerifier(memory_system=mem)
        result = run_async(v.verify_claim("营收100亿", ClaimType.NUMERIC))
        assert result.verified is True
        assert result.source == "memory"
        assert result.confidence == 0.85
        assert len(result.evidence) >= 1


# ── 5. _verify_temporal 时间型 ──────────────────────────────────────────────


class TestVerifyTemporal:
    def test_no_dates_passes(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("去年事件", ClaimType.TEMPORAL))
        assert result.verified is True
        assert "未提取到完整日期" in result.reason

    def test_valid_date_passes(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("2023年5月15日股东大会", ClaimType.TEMPORAL))
        assert result.verified is True
        assert result.confidence == 0.8

    def test_future_date_fails(self):
        v = ClaimVerifier()
        future_year = datetime.now().year + 5
        result = run_async(
            v.verify_claim(f"{future_year}年6月1日发行", ClaimType.TEMPORAL)
        )
        assert result.verified is False
        assert "未来" in result.reason

    def test_invalid_month_fails(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("2023年13月1日", ClaimType.TEMPORAL))
        assert result.verified is False
        assert "月份超出范围" in result.reason

    def test_invalid_day_fails(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("2023年6月32日", ClaimType.TEMPORAL))
        assert result.verified is False
        assert "日期超出范围" in result.reason


# ── 6. _verify_entity_attr 实体属性 ────────────────────────────────────────


class TestVerifyEntityAttr:
    def test_no_entity_fails(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("这是一段普通文字", ClaimType.ENTITY_ATTR))
        assert result.verified is False
        assert "未识别到实体" in result.reason

    def test_symbol_recognized(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("sh600519", ClaimType.ENTITY_ATTR))
        assert result.verified is True
        assert result.source == "format_check"
        assert result.confidence == 0.5

    def test_company_name_recognized(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("贵州茅台公司", ClaimType.ENTITY_ATTR))
        assert result.verified is True

    def test_memory_match_passes(self):
        mem_items = [{"content": "贵州茅台公司是白酒企业"}]
        mem = _make_memory_with_layer(mem_items)
        v = ClaimVerifier(memory_system=mem)
        result = run_async(v.verify_claim("贵州茅台公司", ClaimType.ENTITY_ATTR))
        assert result.verified is True
        assert result.source == "memory"
        assert result.confidence == 0.85


# ── 7. _verify_comparative 比较型 ──────────────────────────────────────────


class TestVerifyComparative:
    def test_no_direction_passes(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("对比同行", ClaimType.COMPARATIVE))
        assert result.verified is True
        assert "未识别方向" in result.reason

    def test_up_direction_no_conflict(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("营收高于去年", ClaimType.COMPARATIVE))
        assert result.verified is True
        assert result.confidence == 0.7
        assert "up" in result.reason

    def test_down_direction_passes(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("利润低于预期", ClaimType.COMPARATIVE))
        assert result.verified is True

    def test_memory_conflict_fails(self):
        """memory 中提到反向趋势则失败"""
        mem_items = [{"content": "营收下降20%"}]
        mem = _make_memory_with_layer(mem_items)
        v = ClaimVerifier(memory_system=mem)
        result = run_async(v.verify_claim("营收高于预期", ClaimType.COMPARATIVE))
        assert result.verified is False
        assert result.confidence == 0.3
        assert "冲突" in result.reason


# ── 8. _verify_regulatory 监管型 ──────────────────────────────────────────


class TestVerifyRegulatory:
    def test_no_agency_fails(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("监管政策", ClaimType.REGULATORY))
        assert result.verified is False
        assert "未识别到具体监管机构" in result.reason

    def test_agency_recognized_no_memory(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("证监会立案", ClaimType.REGULATORY))
        assert result.verified is True
        assert result.source == "format_check"
        assert result.confidence == 0.6

    def test_memory_match_passes(self):
        mem_items = [{"content": "证监会对某公司立案调查"}]
        mem = _make_memory_with_layer(mem_items)
        v = ClaimVerifier(memory_system=mem)
        result = run_async(v.verify_claim("证监会处罚", ClaimType.REGULATORY))
        assert result.verified is True
        assert result.source == "memory"
        assert result.confidence == 0.8


# ── 9. _verify_computational 计算型 ───────────────────────────────────────


class TestVerifyComputational:
    def test_no_pct_fails(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("同比增加", ClaimType.COMPUTATIONAL))
        assert result.verified is False
        assert "未提取到百分比" in result.reason

    def test_valid_pct_passes(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("同比增长30%", ClaimType.COMPUTATIONAL))
        assert result.verified is True
        assert result.confidence == 0.7

    def test_extreme_pct_fails(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("同比增长1500%", ClaimType.COMPUTATIONAL))
        assert result.verified is False
        assert "超出合理范围" in result.reason

    def test_contradictory_keywords_fails(self):
        v = ClaimVerifier()
        result = run_async(
            v.verify_claim("同比增长30%但下降5%", ClaimType.COMPUTATIONAL)
        )
        assert result.verified is False
        assert "矛盾" in result.reason

    def test_memory_match_boosts_confidence(self):
        mem_items = [{"content": "同比增长25%"}]
        mem = _make_memory_with_layer(mem_items)
        v = ClaimVerifier(memory_system=mem)
        result = run_async(v.verify_claim("同比增长30%", ClaimType.COMPUTATIONAL))
        assert result.verified is True
        assert result.confidence == 0.85
        assert result.source == "memory"


# ── 10. verify_claim 异步入口 ──────────────────────────────────────────────


class TestVerifyClaimEntry:
    def test_empty_claim_returns_failed(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim(""))
        assert result.verified is False
        assert "声明为空" in result.reason

    def test_whitespace_claim_returns_failed(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("   "))
        assert result.verified is False
        assert "声明为空" in result.reason

    def test_auto_classify_when_type_none(self):
        v = ClaimVerifier()
        # "2023年5月15日..." 应被自动分类为 TEMPORAL
        result = run_async(v.verify_claim("2023年5月15日事件"))
        assert result.claim_type == ClaimType.TEMPORAL.value
        assert result.verified is True

    def test_memory_override_in_call(self):
        """verify_claim 接受 memory_system 参数覆盖实例级"""
        mem1 = _make_memory_with_layer([{"content": "营收100亿"}])
        mem2 = _make_memory_with_layer([])  # 空 memory
        v = ClaimVerifier(memory_system=mem1)
        # 用 mem2 覆盖，应该走 format_check 而不是 memory
        result = run_async(
            v.verify_claim("营收100亿", ClaimType.NUMERIC, memory_system=mem2)
        )
        assert result.source == "format_check"
        assert result.verified is True
        assert result.confidence == 0.6

    def test_exception_returns_failed(self):
        """verify_claim 中抛异常应被捕获并返回 failed"""
        v = ClaimVerifier()
        # 用 mock 强制让 _verify_numeric 抛异常
        v._verify_numeric = MagicMock(side_effect=RuntimeError("boom"))
        # asyncio 中 mock 不会 await，会抛 TypeError 或 RuntimeError
        # _verify_numeric 是 async 方法，MagicMock 不是协程
        # 直接调用应该被 try/except 捕获
        result = run_async(v.verify_claim("营收100亿", ClaimType.NUMERIC))
        # 由于 MagicMock 不是协程函数，await 会抛 TypeError
        assert result.verified is False
        assert "异常" in result.reason or result.source == "exception"


# ── 11. verify_claims_batch 批量验证 ────────────────────────────────────────


class TestVerifyClaimsBatch:
    def test_empty_batch(self):
        v = ClaimVerifier()
        results = run_async(v.verify_claims_batch([]))
        assert results == []

    def test_batch_preserves_order(self):
        v = ClaimVerifier()
        claims = [
            ("营收100亿", ClaimType.NUMERIC),
            ("2023年5月15日", ClaimType.TEMPORAL),
            ("贵州茅台公司", ClaimType.ENTITY_ATTR),
        ]
        results = run_async(v.verify_claims_batch(claims))
        assert len(results) == 3
        assert results[0].claim_type == ClaimType.NUMERIC.value
        assert results[1].claim_type == ClaimType.TEMPORAL.value
        assert results[2].claim_type == ClaimType.ENTITY_ATTR.value

    def test_batch_with_none_type_auto_classifies(self):
        v = ClaimVerifier()
        claims = [
            ("2023年5月事件", None),  # TEMPORAL
            ("证监会处罚", None),     # REGULATORY
        ]
        results = run_async(v.verify_claims_batch(claims))
        assert results[0].claim_type == ClaimType.TEMPORAL.value
        assert results[1].claim_type == ClaimType.REGULATORY.value


# ── 12. memory 接口兼容性 ─────────────────────────────────────────────────


class TestMemoryInterfaceCompat:
    def test_search_by_layer_preferred(self):
        """优先调用 search_by_layer"""
        mem = _make_memory_with_layer([{"content": "营收100亿"}])
        v = ClaimVerifier(memory_system=mem)
        run_async(v.verify_claim("营收100亿", ClaimType.NUMERIC))
        mem.search_by_layer.assert_called_once()

    def test_fallback_to_long_short_term(self):
        """无 search_by_layer 时降级到 search_long_term + search_short_term"""
        mem = _make_memory_with_l3_l2(
            l3_items=[{"content": "营收100亿"}],
            l2_items=[{"content": "短期100亿"}],
        )
        v = ClaimVerifier(memory_system=mem)
        result = run_async(v.verify_claim("营收100亿", ClaimType.NUMERIC))
        assert result.verified is True
        assert result.source == "memory"
        mem.search_long_term.assert_called_once()
        mem.search_short_term.assert_called_once()

    def test_search_by_layer_exception_falls_back(self):
        """search_by_layer 抛异常时降级到 long/short_term"""
        mem = MagicMock(spec=["search_by_layer", "search_long_term", "search_short_term"])
        mem.search_by_layer.side_effect = RuntimeError("layer error")
        mem.search_long_term.return_value = [{"content": "营收100亿"}]
        mem.search_short_term.return_value = []
        v = ClaimVerifier(memory_system=mem)
        result = run_async(v.verify_claim("营收100亿", ClaimType.NUMERIC))
        assert result.verified is True
        assert result.source == "memory"
        mem.search_by_layer.assert_called_once()
        mem.search_long_term.assert_called_once()

    def test_no_memory_works(self):
        """无 memory_system 时验证器仍可工作"""
        v = ClaimVerifier()
        result = run_async(v.verify_claim("营收100亿", ClaimType.NUMERIC))
        assert result.verified is True
        assert result.source == "format_check"


# ── 13. 集成：完整声明句子 ────────────────────────────────────────────────


class TestIntegrationRealClaims:
    def test_real_claim_numeric(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("贵州茅台2023年净利润600亿"))
        # 含日期应分类为 TEMPORAL（优先级最高）
        assert result.claim_type == ClaimType.TEMPORAL.value

    def test_real_claim_computational(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("净利润同比增长30%"))
        assert result.claim_type == ClaimType.COMPUTATIONAL.value
        assert result.verified is True

    def test_real_claim_regulatory(self):
        v = ClaimVerifier()
        result = run_async(v.verify_claim("证监会对贵州茅台立案调查"))
        assert result.claim_type == ClaimType.REGULATORY.value
        assert result.verified is True

    def test_real_claim_with_memory(self):
        """完整流程：声明 + memory_system"""
        mem_items = [
            {"content": "贵州茅台2023年净利润600亿，同比增长30%"},
            {"content": "证监会对某公司立案调查"},
        ]
        mem = _make_memory_with_layer(mem_items)
        v = ClaimVerifier(memory_system=mem)
        result = run_async(v.verify_claim("净利润600亿", ClaimType.NUMERIC))
        assert result.verified is True
        assert result.source == "memory"
        assert len(result.evidence) >= 1
