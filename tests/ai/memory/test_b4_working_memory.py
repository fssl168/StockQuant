# -*- coding: utf-8 -*-
"""F020 Phase B4 — Working Memory 三组件测试

覆盖：
1. Summarization 组件：LLM 摘要 + 缓存 + 降级
2. Observation 组件：LLM 观察 + 规则降级
3. Reflection 组件：LLM 反思 + L3 写入 + 降级
4. 向后兼容性：现有接口不受影响
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

import pytest


# ─── Mock LLM 适配器 ────────────────────────────────────────────────


class MockLLMAdapter:
    """模拟 LLM 适配器，用于测试三组件"""

    def __init__(self, responses: List[str] = None):
        self._responses = responses or []
        self._call_count = 0
        self._calls = []  # 记录所有调用

    def chat(self, message, system_prompt=""):
        self._calls.append({"message": message, "system": system_prompt})
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
            self._call_count += 1
            return resp
        return "默认 LLM 响应"


# ─── 测试数据 ────────────────────────────────────────────────────────


def _make_events(n: int = 5) -> list:
    """生成 N 条测试事件"""
    events = []
    base = datetime.now() - timedelta(hours=n)
    for i in range(n):
        events.append({
            "id": f"ev_{i}",
            "symbol": "sh600519",
            "content": f"茅台事件 {i}：涨幅扩大",
            "timestamp": (base + timedelta(hours=i)).isoformat(),
            "sentiment": 0.5 + i * 0.1,
        })
    return events


# ========================================================================
# 向后兼容性回归测试
# ========================================================================

class TestBackwardCompat:
    """B4 重写后保留现有接口"""

    def test_append_and_get_recent(self):
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory(max_size=10)
        for i in range(5):
            mem.append({"id": i})
        assert len(mem.get_recent(3)) == 3

    def test_max_size_eviction(self):
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory(max_size=5)
        for i in range(20):
            mem.append({"id": i})
        assert len(mem.get_recent(10)) <= 5

    def test_query_by_symbol(self):
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory()
        mem.append({"symbol": "sh600519"})
        mem.append({"symbol": "sz000858"})
        results = mem.query(symbol="sh600519")
        assert len(results) == 1

    def test_get_sentiment_baseline(self):
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory()
        for _ in range(10):
            mem.append({"symbol": "sh600519", "sentiment": 0.5})
        baseline = mem.get_sentiment_baseline("sh600519")
        assert abs(baseline - 0.5) < 0.01

    def test_clear(self):
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory()
        mem.append({"id": 1})
        mem.clear()
        assert mem.get_recent(10) == []


# ========================================================================
# Summarization 组件测试
# ========================================================================

class TestSummarization:
    """Summarization 组件测试"""

    def test_summarize_fallback_without_llm(self):
        """无 LLM 时降级文本拼接"""
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory(max_size=100, llm_adapter=None)
        for ev in _make_events(5):
            mem.append(ev)

        summary = mem.summarize(force=True)
        assert summary
        assert "近期事件" in summary
        assert "茅台事件" in summary

    def test_summarize_uses_llm(self):
        """有 LLM 时调用 LLM 生成摘要"""
        from stockquant.ai.memory.working import WorkingMemory
        mock = MockLLMAdapter(["这是 LLM 生成的市场摘要。"])
        mem = WorkingMemory(max_size=100, llm_adapter=mock)
        for ev in _make_events(5):
            mem.append(ev)

        summary = mem.summarize(force=True)
        assert "LLM 生成" in summary
        assert mock._call_count == 1

    def test_summarize_caches_result(self):
        """摘要结果缓存：未达阈值时返回缓存"""
        from stockquant.ai.memory.working import WorkingMemory
        mock = MockLLMAdapter(["第一次摘要"])
        mem = WorkingMemory(max_size=100, llm_adapter=mock)
        # 调整阈值避免触发重摘要
        mem.SUMMARIZE_BATCH_SIZE = 100
        for ev in _make_events(3):
            mem.append(ev)

        s1 = mem.summarize(force=True)
        assert mock._call_count == 1
        # 添加少量事件，未达阈值
        mem.append({"id": "ev_new", "symbol": "sh600519", "content": "新事件"})
        s2 = mem.summarize()  # 不强制
        assert s2 == s1  # 返回缓存
        assert mock._call_count == 1  # 未调用 LLM

    def test_summarize_force_overrides_cache(self):
        """force=True 强制重新摘要"""
        from stockquant.ai.memory.working import WorkingMemory
        mock = MockLLMAdapter(["第一次", "第二次"])
        mem = WorkingMemory(max_size=100, llm_adapter=mock)
        for ev in _make_events(3):
            mem.append(ev)

        s1 = mem.summarize(force=True)
        s2 = mem.summarize(force=True)
        assert s1 == "第一次"
        assert s2 == "第二次"
        assert mock._call_count == 2

    def test_summarize_empty_returns_empty(self):
        """无事件时摘要返回空字符串"""
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory(max_size=100)
        assert mem.summarize() == ""

    def test_summary_property(self):
        """summary 属性不触发新摘要"""
        from stockquant.ai.memory.working import WorkingMemory
        mock = MockLLMAdapter(["LLM 摘要"])
        mem = WorkingMemory(max_size=100, llm_adapter=mock)
        for ev in _make_events(3):
            mem.append(ev)

        # summary 属性未触发摘要时为 None
        assert mem.summary is None
        # 触发摘要
        mem.summarize(force=True)
        assert mem.summary == "LLM 摘要"
        # 再访问不增加调用
        assert mock._call_count == 1


# ========================================================================
# Observation 组件测试
# ========================================================================

class TestObservation:
    """Observation 组件测试"""

    def test_observe_rule_based_market_anomaly(self):
        """规则降级：识别涨停异动"""
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory(max_size=100, llm_adapter=None)
        mem.append({
            "id": "anomaly_1",
            "symbol": "sh600519",
            "content": "茅台涨停，成交额放大",
        })

        observations = mem.observe(force=True)
        assert len(observations) >= 1
        obs = next(o for o in observations if o["type"] == "market_anomaly")
        assert obs["direction"] == "bullish"
        assert obs["strength"] > 0

    def test_observe_rule_based_capital_flow(self):
        """规则降级：识别资金流向"""
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory(max_size=100, llm_adapter=None)
        mem.append({
            "id": "flow_1",
            "symbol": "sh600519",
            "content": "北向资金净流入 50 亿",
        })

        observations = mem.observe(force=True)
        assert any(o["type"] == "capital_flow" for o in observations)

    def test_observe_rule_based_technical_breakout(self):
        """规则降级：识别技术突破"""
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory(max_size=100, llm_adapter=None)
        mem.append({
            "id": "tech_1",
            "symbol": "sh600519",
            "content": "突破 60 日均线，量价配合",
        })

        observations = mem.observe(force=True)
        assert any(o["type"] == "technical_breakout" for o in observations)

    def test_observe_uses_llm_json_response(self):
        """LLM 返回 JSON 数组时正确解析"""
        from stockquant.ai.memory.working import WorkingMemory
        json_resp = '[{"type": "market_anomaly", "symbol": "sh600519", "direction": "bullish", "strength": 0.8, "description": "涨停", "evidence": "ev_0"}]'
        mock = MockLLMAdapter([json_resp])
        mem = WorkingMemory(max_size=100, llm_adapter=mock)
        for ev in _make_events(3):
            mem.append(ev)

        observations = mem.observe(force=True)
        assert len(observations) == 1
        assert observations[0]["type"] == "market_anomaly"
        assert observations[0]["strength"] == 0.8

    def test_observe_empty_events_returns_empty(self):
        """无事件时观察返回空"""
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory(max_size=100)
        assert mem.observe(force=True) == []

    def test_observe_property_returns_copy(self):
        """observations 属性返回副本"""
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory(max_size=100, llm_adapter=None)
        mem.append({"id": "e1", "symbol": "s", "content": "涨停"})
        mem.observe(force=True)

        obs1 = mem.observations
        obs1.append({"extra": "modified"})
        # 原始数据未被修改
        assert len(mem.observations) == 1


# ========================================================================
# Reflection 组件测试
# ========================================================================

class TestReflection:
    """Reflection 组件测试"""

    def test_reflect_fallback_without_llm(self):
        """无 LLM 时降级反思"""
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory(max_size=100, llm_adapter=None)
        mem.append({"id": "e1", "symbol": "s", "content": "涨停"})
        mem.append({"id": "e2", "symbol": "s", "content": "跌停"})

        reflection = mem.reflect()
        assert "判断" in reflection
        assert "依据" in reflection
        assert "置信度" in reflection

    def test_reflect_uses_llm(self):
        """有 LLM 时调用 LLM 生成反思"""
        from stockquant.ai.memory.working import WorkingMemory
        mock = MockLLMAdapter(["摘要", "[]", "判断：市场情绪转空\n依据：观察显示\n置信度：high"])
        mem = WorkingMemory(max_size=100, llm_adapter=mock)
        for ev in _make_events(3):
            mem.append(ev)

        reflection = mem.reflect()
        assert "市场情绪转空" in reflection
        assert "high" in reflection.lower()

    def test_reflect_writes_to_l3_deep(self):
        """reflect 应将反思写入 L3-Deep"""
        from stockquant.ai.memory.working import WorkingMemory
        from stockquant.ai.memory.l3_store import L3Store

        l3 = L3Store(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        l3.clear_all()

        mem = WorkingMemory(max_size=100, llm_adapter=None)
        mem.append({"id": "e1", "symbol": "sh600519", "content": "涨停"})

        reflection = mem.reflect(l3_store=l3, symbol="sh600519")
        assert reflection

        # L3-Deep 应有反思记录
        deep_items = l3.search_by_tier("", tier="deep", top_k=10)
        assert len(deep_items) >= 1
        assert deep_items[0]["tier"] == "deep"
        assert deep_items[0]["period_type"] == "reflection"

    def test_reflect_stores_in_reflections_list(self):
        """反思应被加入 reflections 列表"""
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory(max_size=100, llm_adapter=None)
        mem.append({"id": "e1", "symbol": "s", "content": "涨停"})

        assert len(mem.reflections) == 0
        mem.reflect()
        assert len(mem.reflections) == 1
        assert "content" in mem.reflections[0]
        assert "confidence" in mem.reflections[0]

    def test_reflect_empty_returns_empty(self):
        """无摘要无观察时返回空"""
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory(max_size=100)
        result = mem.reflect()
        assert result == ""


# ========================================================================
# 三组件集成测试
# ========================================================================

class TestWorkingMemoryIntegration:
    """三组件集成测试"""

    def test_query_merges_three_components(self):
        """query 应合并三组件输出"""
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory(max_size=100, llm_adapter=None)
        # 加入触发观察关键词的事件
        mem.append({"id": "e1", "symbol": "sh600519", "content": "茅台涨停"})
        mem.append({"id": "e2", "symbol": "sh600519", "content": "北向资金流入"})
        mem.append({"id": "e3", "symbol": "sh600519", "content": "突破均线"})

        # 触发三组件
        mem.summarize(force=True)
        mem.observe(force=True)
        mem.reflect()

        # query 应包含原始事件 + summary + observations + reflections
        results = mem.query()
        components = {r.get("component") for r in results}
        assert "summarization" in components
        assert "observation" in components
        assert "reflection" in components

    def test_clear_resets_all_components(self):
        """clear 应重置所有组件缓存"""
        from stockquant.ai.memory.working import WorkingMemory
        mem = WorkingMemory(max_size=100, llm_adapter=None)
        for ev in _make_events(3):
            mem.append(ev)
        mem.summarize(force=True)
        mem.observe(force=True)
        mem.reflect()

        mem.clear()
        assert mem.summary is None
        assert mem.observations == []
        assert mem.reflections == []
        assert mem.get_recent(10) == []

    def test_llm_available_property(self):
        """llm_available 属性正确反映 LLM 状态"""
        from stockquant.ai.memory.working import WorkingMemory
        mem_no_llm = WorkingMemory(llm_adapter=None)
        assert mem_no_llm.llm_available is False

        mem_with_llm = WorkingMemory(llm_adapter=MockLLMAdapter())
        assert mem_with_llm.llm_available is True
