# -*- coding: utf-8 -*-
"""F020 Phase D 单元测试 — Decision-making 模块

覆盖：
- D1: InsightsBridge + DecisionContext
- D2: DecisionAgent.evaluate() 扩展（insights/user_profile/decision_context）
- D3: Profiling 注入到决策链路

测试策略：
- 用 patch.object(DecisionAgent, "__init__", ...) 绕过真实 LLM 初始化
- mock _react.run() 返回预设 ReActResult
- 验证新参数是否正确注入查询文本与止损止盈逻辑
"""
from __future__ import annotations

import json
import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# 确保项目根目录在 sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from stockquant.ai.insights_bridge import DecisionContext, InsightsBridge
from stockquant.ai.decision_agent import DecisionAgent
from stockquant.ai.models import DecisionAdvice, DecisionMode
from stockquant.agent.react_agent import ReActResult, ReActState, Thought


# ── 辅助：构建 mock DecisionAgent ──


def _make_react_result(
    action: str = "confirm",
    confidence: float = 0.8,
    stop_loss: float = 1700.0,
    take_profit: float = 2000.0,
    modified_params=None,
) -> ReActResult:
    """构建 mock ReActResult（generate_decision 步骤已成功）"""
    thoughts = [
        Thought(
            step=1,
            thought="综合决策",
            action="generate_decision",
            action_input={},
            observation=json.dumps({
                "action": action,
                "confidence": confidence,
                "reason": "技术面支持",
                "modified_params": modified_params,
                "risk_warnings": [],
                "stop_loss": stop_loss,
                "take_profit": take_profit,
            }),
            state=ReActState.OBSERVING,
        ),
    ]
    return ReActResult(
        final_answer="建议买入",
        thoughts=thoughts,
        tool_calls_made=1,
        success=True,
    )


def _make_agent(stop_loss=None, take_profit=None, modified_params=None):
    """构建一个 mock 化的 DecisionAgent（不调用真实 LLM）"""
    react_result = _make_react_result(
        stop_loss=stop_loss,
        take_profit=take_profit,
        modified_params=modified_params,
    )
    with patch.object(DecisionAgent, "__init__", lambda self, **kwargs: None):
        agent = DecisionAgent.__new__(DecisionAgent)
        agent._react = MagicMock()
        agent._react.run.return_value = react_result
        agent._mode = DecisionMode.SEMI_AUTO
        agent._audit_logs = []
    return agent


# ════════════════════════════════════════════════════════════════════
# D1: InsightsBridge + DecisionContext
# ════════════════════════════════════════════════════════════════════


class TestDecisionContext:
    """DecisionContext 数据类测试"""

    def test_default_values(self):
        ctx = DecisionContext()
        assert ctx.symbol == ""
        assert ctx.insights == []
        assert ctx.memory_retrieval == []
        assert ctx.reflection == ""
        assert ctx.reflection_confidence == "low"
        assert ctx.timestamp  # 自动生成
        assert ctx.metadata == {}

    def test_custom_init(self):
        ctx = DecisionContext(
            symbol="sh600519",
            insights=[{"content": "test"}],
            memory_retrieval=[{"content": "mem"}],
            reflection="反思文本",
            reflection_confidence="high",
            metadata={"count": 1},
        )
        assert ctx.symbol == "sh600519"
        assert len(ctx.insights) == 1
        assert ctx.reflection == "反思文本"
        assert ctx.reflection_confidence == "high"
        assert ctx.metadata["count"] == 1


class TestInsightsBridgeBasic:
    """InsightsBridge 基础测试"""

    def test_build_context_no_memory(self):
        """无 memory_system 时仍能构建上下文"""
        bridge = InsightsBridge()
        ctx = bridge.build_context(
            symbol="sh600519",
            insights=[{"content": "利好消息", "symbol": "sh600519"}],
            memory_system=None,
        )
        assert ctx.symbol == "sh600519"
        assert len(ctx.insights) == 1
        assert ctx.memory_retrieval == []
        assert ctx.reflection == ""

    def test_build_context_empty_insights(self):
        """空 insights 列表"""
        bridge = InsightsBridge()
        ctx = bridge.build_context(symbol="sh600519", insights=[], memory_system=None)
        assert ctx.insights == []
        assert ctx.metadata["insight_count"] == 0

    def test_build_context_filters_by_symbol(self):
        """insights 按 symbol 过滤"""
        bridge = InsightsBridge()
        insights = [
            {"content": "贵州茅台利好", "symbol": "sh600519"},
            {"content": "另一只股票", "symbol": "sz000858"},
            {"content": "市场级洞察", "symbol": ""},  # 市场级保留
            {"content": "无 symbol 字段的洞察"},  # 也保留
        ]
        ctx = bridge.build_context(
            symbol="sh600519",
            insights=insights,
            memory_system=None,
        )
        # 应保留 sh600519 + 空 symbol + 无 symbol 字段（共 3 条）
        assert len(ctx.insights) == 3
        symbols = [i.get("symbol", "") for i in ctx.insights]
        assert "sh600519" in symbols
        assert "sz000858" not in symbols


class TestInsightsBridgeMemoryRetrieval:
    """InsightsBridge 记忆检索测试"""

    def test_retrieve_via_search_by_layer(self):
        """优先使用 search_by_layer（B3 多因子召回）"""
        mock_memory = MagicMock()
        mock_memory.search_by_layer.return_value = [
            {"content": "L3 记忆 1", "symbol": "sh600519", "tier": "intermediate"},
            {"content": "L2 记忆 1", "symbol": "sh600519", "layer": "shallow"},
            {"content": "其他股票", "symbol": "sz000858"},  # 应被过滤
        ]
        bridge = InsightsBridge(top_k_per_layer=3)
        ctx = bridge.build_context(
            symbol="sh600519",
            insights=[],
            memory_system=mock_memory,
        )
        assert mock_memory.search_by_layer.called
        # 过滤后只剩 2 条
        assert len(ctx.memory_retrieval) == 2
        for item in ctx.memory_retrieval:
            assert item.get("symbol") in ("sh600519", "")

    def test_retrieve_fallback_to_long_short_term(self):
        """search_by_layer 不可用时降级到 L3+L2 检索"""
        mock_memory = MagicMock(spec=["search_long_term", "search_short_term", "l1"])
        mock_memory.search_long_term.return_value = [
            {"content": "L3 记忆", "symbol": "sh600519"},
        ]
        mock_memory.search_short_term.return_value = [
            {"content": "L2 记忆", "symbol": "sh600519"},
        ]
        bridge = InsightsBridge()
        ctx = bridge.build_context(
            symbol="sh600519",
            insights=[],
            memory_system=mock_memory,
        )
        # search_long_term + search_short_term 都应被调用
        mock_memory.search_long_term.assert_called_once()
        mock_memory.search_short_term.assert_called_once()
        assert len(ctx.memory_retrieval) == 2

    def test_retrieve_memory_exception_safe(self):
        """记忆检索异常时不抛出"""
        mock_memory = MagicMock()
        mock_memory.search_by_layer.side_effect = RuntimeError("DB down")
        mock_memory.search_long_term.side_effect = RuntimeError("DB down")
        mock_memory.search_short_term.side_effect = RuntimeError("DB down")
        bridge = InsightsBridge()
        # 不应抛出异常
        ctx = bridge.build_context(
            symbol="sh600519",
            insights=[],
            memory_system=mock_memory,
        )
        assert ctx.memory_retrieval == []


class TestInsightsBridgeReflection:
    """InsightsBridge 反思组件测试"""

    def test_reflect_called_with_l3_store(self):
        """reflect() 调用时传入 l3_store 实例"""
        mock_memory = MagicMock()
        mock_l1 = MagicMock()
        mock_l3 = MagicMock()
        mock_memory.l1 = mock_l1
        mock_memory.l3 = mock_l3
        mock_l1.reflect.return_value = "市场出现回调风险"
        mock_l1.reflections = [{"confidence": "medium"}]
        # search_by_layer 返回空，避免干扰
        mock_memory.search_by_layer.return_value = []

        bridge = InsightsBridge()
        ctx = bridge.build_context(
            symbol="sh600519",
            insights=[{"content": "利好", "symbol": "sh600519"}],
            memory_system=mock_memory,
        )
        # reflect 应被调用，且 l3_store 参数为 mock_l3
        mock_l1.reflect.assert_called_once()
        args, kwargs = mock_l1.reflect.call_args
        assert kwargs.get("l3_store") is mock_l3 or (args and args[0] is mock_l3)
        assert ctx.reflection == "市场出现回调风险"
        assert ctx.reflection_confidence == "medium"

    def test_reflect_empty_returns_low_confidence(self):
        """reflect 返回空时置信度为 low"""
        mock_memory = MagicMock()
        mock_l1 = MagicMock()
        mock_memory.l1 = mock_l1
        mock_memory.l3 = MagicMock()
        mock_l1.reflect.return_value = ""
        mock_memory.search_by_layer.return_value = []

        bridge = InsightsBridge()
        ctx = bridge.build_context(
            symbol="sh600519",
            insights=[],
            memory_system=mock_memory,
        )
        assert ctx.reflection == ""
        assert ctx.reflection_confidence == "low"

    def test_reflect_exception_safe(self):
        """reflect 抛异常时不影响上下文构建"""
        mock_memory = MagicMock()
        mock_l1 = MagicMock()
        mock_memory.l1 = mock_l1
        mock_memory.l3 = MagicMock()
        mock_l1.reflect.side_effect = RuntimeError("LLM fail")
        mock_memory.search_by_layer.return_value = []

        bridge = InsightsBridge()
        ctx = bridge.build_context(
            symbol="sh600519",
            insights=[],
            memory_system=mock_memory,
        )
        # 不抛异常，反思为空
        assert ctx.reflection == ""


# ════════════════════════════════════════════════════════════════════
# D2: DecisionAgent.evaluate() 扩展
# ════════════════════════════════════════════════════════════════════


class TestEvaluateBackwardCompat:
    """evaluate() 向后兼容测试（旧调用方式仍可用）"""

    def test_three_args_still_works(self):
        """原有 3 参数调用仍然工作"""
        agent = _make_agent()
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100, "price": 1800.0}
        advice = agent.evaluate(signal, {}, 1000000.0)
        assert isinstance(advice, DecisionAdvice)
        assert advice.action == "confirm"
        # _react.run 应被调用
        agent._react.run.assert_called_once()

    def test_default_kwargs_none(self):
        """新增参数默认为 None，不影响行为"""
        agent = _make_agent()
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100}
        advice = agent.evaluate(signal)
        assert isinstance(advice, DecisionAdvice)


class TestEvaluateWithInsights:
    """evaluate(insights=...) 测试"""

    def test_insights_injected_into_query(self):
        """insights 内容应出现在 LLM 查询文本中"""
        agent = _make_agent()
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100, "price": 1800.0}
        insights = [
            {"content": "茅台业绩超预期", "symbol": "sh600519", "confidence": 0.85},
        ]
        agent.evaluate(signal, insights=insights)
        # 验证 _react.run 收到的查询包含洞察内容
        query_arg = agent._react.run.call_args[0][0]
        assert "茅台业绩超预期" in query_arg
        assert "F020 市场洞察" in query_arg

    def test_insights_truncated_to_5(self):
        """insights 超过 5 条时只取前 5 条"""
        agent = _make_agent()
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100}
        insights = [{"content": f"洞察 {i}", "symbol": "sh600519"} for i in range(10)]
        agent.evaluate(signal, insights=insights)
        query_arg = agent._react.run.call_args[0][0]
        # 前 5 条应出现，后 5 条不应出现
        for i in range(5):
            assert f"洞察 {i}" in query_arg
        assert "洞察 5" not in query_arg
        assert "洞察 9" not in query_arg

    def test_empty_insights_not_injected(self):
        """空 insights 列表不应注入"""
        agent = _make_agent()
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100}
        agent.evaluate(signal, insights=[])
        query_arg = agent._react.run.call_args[0][0]
        assert "F020 市场洞察" not in query_arg


class TestEvaluateWithUserProfile:
    """evaluate(user_profile=...) 测试"""

    def test_profile_string_conservative(self):
        """字符串 'conservative' → 仓位 5%, 止损 3%, 止盈 6%"""
        # mock 的 react_result 不带 stop_loss/take_profit，触发自动设置
        agent = _make_agent(stop_loss=None, take_profit=None)
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100, "price": 1000.0}
        advice = agent.evaluate(signal, user_profile="conservative")
        # 1000 * (1 - 0.03) = 970
        assert advice.stop_loss == 970.0
        # 1000 * (1 + 0.06) = 1060
        assert advice.take_profit == 1060.0

    def test_profile_string_aggressive(self):
        """字符串 'aggressive' → 仓位 20%, 止损 8%, 止盈 20%"""
        agent = _make_agent(stop_loss=None, take_profit=None)
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100, "price": 1000.0}
        advice = agent.evaluate(signal, user_profile="aggressive")
        # 1000 * (1 - 0.08) = 920
        assert advice.stop_loss == 920.0
        # 1000 * (1 + 0.20) = 1200
        assert advice.take_profit == 1200.0

    def test_profile_enum_neutral(self):
        """RiskProfile.NEUTRAL 枚举"""
        from stockquant.ai.profiling import RiskProfile
        agent = _make_agent(stop_loss=None, take_profit=None)
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100, "price": 1000.0}
        advice = agent.evaluate(signal, user_profile=RiskProfile.NEUTRAL)
        # 1000 * (1 - 0.05) = 950
        assert advice.stop_loss == 950.0
        # 1000 * (1 + 0.10) = 1100
        assert advice.take_profit == 1100.0

    def test_profile_does_not_override_llm_set_stop_loss(self):
        """LLM 已设置 stop_loss 时不被 profile 覆盖"""
        agent = _make_agent(stop_loss=1600.0, take_profit=2200.0)
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100, "price": 1800.0}
        advice = agent.evaluate(signal, user_profile="conservative")
        # 保持 LLM 设置，不覆盖
        assert advice.stop_loss == 1600.0
        assert advice.take_profit == 2200.0

    def test_profile_injected_into_query(self):
        """profile 标签应出现在查询中"""
        agent = _make_agent()
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100}
        agent.evaluate(signal, user_profile="aggressive")
        query_arg = agent._react.run.call_args[0][0]
        assert "aggressive" in query_arg
        assert "仓位上限" in query_arg

    def test_profile_none_no_constraint(self):
        """user_profile=None 时止损止盈不强制设置"""
        agent = _make_agent(stop_loss=None, take_profit=None)
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100, "price": 1000.0}
        advice = agent.evaluate(signal, user_profile=None)
        # 不应自动设置
        assert advice.stop_loss is None
        assert advice.take_profit is None

    def test_position_warning_when_qty_exceeds_cap(self):
        """修改后的 qty 超过 profile 仓位上限时记录告警"""
        # 总资金 10000, price=100, conservative 仓位 5% → 最大 5 股
        # LLM 建议修改 qty=100 股 → 超过 5 股，应告警
        agent = _make_agent(modified_params={"qty": 100})
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 50, "price": 100.0}
        advice = agent.evaluate(
            signal, total_cash=10000.0, user_profile="conservative"
        )
        # 应有仓位超限告警
        warnings_text = " ".join(advice.risk_warnings)
        assert "仓位约束" in warnings_text or "档位上限" in warnings_text


class TestEvaluateWithDecisionContext:
    """evaluate(decision_context=...) 测试"""

    def test_context_insights_override_separate_insights(self):
        """decision_context.insights 优先级高于单独传入的 insights"""
        agent = _make_agent()
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100}
        ctx = DecisionContext(
            symbol="sh600519",
            insights=[{"content": "上下文洞察", "symbol": "sh600519"}],
            reflection="市场情绪偏多",
            memory_retrieval=[
                {"content": "历史记忆条目", "symbol": "sh600519", "tier": "intermediate"},
            ],
        )
        agent.evaluate(
            signal,
            insights=[{"content": "应被覆盖的洞察"}],
            decision_context=ctx,
        )
        query_arg = agent._react.run.call_args[0][0]
        # 上下文洞察应出现，被覆盖的洞察不应出现
        assert "上下文洞察" in query_arg
        assert "应被覆盖的洞察" not in query_arg
        # 反思也应出现
        assert "市场情绪偏多" in query_arg
        # 历史记忆也应出现
        assert "历史记忆条目" in query_arg

    def test_context_without_insights_falls_back(self):
        """decision_context.insights 为空时回退到单独传入的 insights"""
        agent = _make_agent()
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100}
        ctx = DecisionContext(symbol="sh600519", insights=[])
        agent.evaluate(
            signal,
            insights=[{"content": "回退洞察", "symbol": "sh600519"}],
            decision_context=ctx,
        )
        query_arg = agent._react.run.call_args[0][0]
        assert "回退洞察" in query_arg

    def test_context_reflection_truncated(self):
        """超长反思文本应被截断到 300 字符"""
        agent = _make_agent()
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100}
        long_reflection = "反思" * 500  # 1000 字符
        ctx = DecisionContext(
            symbol="sh600519",
            insights=[],
            reflection=long_reflection,
        )
        agent.evaluate(signal, decision_context=ctx)
        query_arg = agent._react.run.call_args[0][0]
        # 截断到 300 字符（"WorkingMemory 反思: " + 前 300 字符）
        reflection_part = query_arg.split("WorkingMemory 反思: ")[-1]
        assert len(reflection_part) <= 300


class TestEvaluateReadonlyMode:
    """只读模式 + 新参数的交互测试"""

    def test_readonly_with_all_new_params(self):
        """只读模式下新参数不应导致异常"""
        with patch.object(DecisionAgent, "__init__", lambda self, **kwargs: None):
            agent = DecisionAgent.__new__(DecisionAgent)
            agent._mode = DecisionMode.READ_ONLY
            agent._audit_logs = []

        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100, "price": 1000.0}
        ctx = DecisionContext(
            symbol="sh600519",
            insights=[{"content": "洞察"}],
        )
        advice = agent.evaluate(
            signal,
            insights=[{"content": "test"}],
            user_profile="aggressive",
            decision_context=ctx,
        )
        assert advice.action == "confirm"
        assert advice.confidence == 0.0


# ════════════════════════════════════════════════════════════════════
# D3: Profiling 注入端到端
# ════════════════════════════════════════════════════════════════════


class TestProfilingEndToEnd:
    """Profiling 模块端到端注入测试"""

    def test_profile_params_direct(self):
        """直接传入 ProfileParams 实例"""
        from stockquant.ai.profiling import ProfileParams
        agent = _make_agent(stop_loss=None, take_profit=None)
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100, "price": 1000.0}
        params = ProfileParams(
            max_position_pct=0.15,
            stop_loss_pct=0.04,
            take_profit_pct=0.12,
            max_drawdown_tolerance=0.20,
            confidence_threshold=0.50,
        )
        advice = agent.evaluate(signal, user_profile=params)
        # 1000 * (1 - 0.04) = 960
        assert advice.stop_loss == 960.0
        # 1000 * (1 + 0.12) = 1120
        assert advice.take_profit == 1120.0

    def test_invalid_profile_string_falls_back_to_neutral(self):
        """无效字符串回退到 neutral"""
        agent = _make_agent(stop_loss=None, take_profit=None)
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100, "price": 1000.0}
        # 无效值 → from_str 返回 NEUTRAL
        advice = agent.evaluate(signal, user_profile="invalid_profile")
        # neutral: 5% 止损, 10% 止盈
        assert advice.stop_loss == 950.0  # 1000 * 0.95
        assert advice.take_profit == 1100.0  # 1000 * 1.10

    def test_zero_price_no_stop_loss(self):
        """价格为 0 时不自动设置止损止盈"""
        agent = _make_agent(stop_loss=None, take_profit=None)
        signal = {"symbol": "sh600519", "direction": "BUY", "qty": 100, "price": 0.0}
        advice = agent.evaluate(signal, user_profile="conservative")
        # price=0 不应触发自动设置
        assert advice.stop_loss is None
        assert advice.take_profit is None
