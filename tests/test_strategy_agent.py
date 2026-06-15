# -*- coding: utf-8 -*-
"""F022 StrategyAgent 测试 — 策略生成工具和主类"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from stockquant.agent.llm_adapter import LLMResponse
from stockquant.agent.react_agent import ReActResult, ReActState, Thought
from stockquant.agent.strategy_tools import (
    _extract_code_block,
    _make_generate_strategy_code,
    _make_parse_strategy_intent,
    _make_suggest_improvements,
    _parse_pct,
    score_strategy,
    validate_strategy_code,
)
from stockquant.ai.models import (
    ImprovementSuggestion,
    StrategyGenerationResult,
    StrategyIntent,
    StrategyScore,
    ValidationResult,
)
from stockquant.ai.strategy_agent import StrategyAgent


# ── 辅助：构建 mock LLMAdapter ──


def _make_mock_adapter(content: str) -> MagicMock:
    """返回一个 mock LLMAdapter，adapter.call() 返回指定 content。"""
    adapter = MagicMock(spec=["call"])
    adapter.call.return_value = LLMResponse(content=content)
    return adapter


# ── 1. test_parse_intent_basic ──


def test_parse_intent_basic():
    """_make_parse_strategy_intent 工具，mock LLMAdapter.call 返回合法 JSON"""
    intent_json = {
        "indicators": [{"name": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9}}],
        "entry_conditions": ["MACD 金叉"],
        "exit_conditions": ["MACD 死叉"],
        "position_method": "FixedFraction",
        "position_params": {"pct": 0.2},
        "risk_params": {"stop_loss": 0.05},
    }
    adapter = _make_mock_adapter(json.dumps(intent_json, ensure_ascii=False))
    tool_fn = _make_parse_strategy_intent(adapter)
    result_str = tool_fn("当MACD金叉时买入，仓位20%，止损5%")
    result = json.loads(result_str)

    assert "indicators" in result
    assert result["indicators"][0]["name"] == "MACD"
    assert "MACD 金叉" in result["entry_conditions"]
    adapter.call.assert_called_once()


# ── 2. test_generate_code_simple ──


def test_generate_code_simple():
    """_make_generate_strategy_code 工具，mock LLMAdapter.call 返回含 ```python``` 代码块的响应"""
    code = (
        "from stockquant.strategy.base import BaseStrategy\n\n"
        "class AIStrategy(BaseStrategy):\n"
        "    name = 'AIStrategy'\n\n"
        "    def on_start(self):\n"
        "        self.MACD = self.MACD()\n\n"
        "    def on_bar(self, bars):\n"
        "        pass\n"
    )
    llm_response = f"这是生成的策略代码：\n```python\n{code}\n```\n请检查。"
    adapter = _make_mock_adapter(llm_response)
    tool_fn = _make_generate_strategy_code(adapter)
    result = tool_fn('{"indicators": [{"name": "MACD"}]}')

    assert "class AIStrategy" in result
    assert "on_bar" in result
    adapter.call.assert_called_once()


# ── 3. test_validate_code_valid ──


def test_validate_code_valid():
    """validate_strategy_code 工具，传入合法策略代码"""
    valid_code = (
        "from stockquant.strategy.base import BaseStrategy\n\n"
        "class MyStrategy(BaseStrategy):\n"
        "    name = 'MyStrategy'\n\n"
        "    def on_start(self):\n"
        "        pass\n\n"
        "    def on_bar(self, bars):\n"
        "        pass\n"
    )
    result_str = validate_strategy_code(valid_code)
    result = json.loads(result_str)

    assert result["valid"] is True
    assert len(result["errors"]) == 0


# ── 4. test_validate_code_syntax_error ──


def test_validate_code_syntax_error():
    """validate_strategy_code 工具，语法错误检测"""
    bad_code = "def foo(\n  pass\n"
    result_str = validate_strategy_code(bad_code)
    result = json.loads(result_str)

    assert result["valid"] is False
    assert any("语法错误" in e for e in result["errors"])


# ── 5. test_validate_code_missing_method ──


def test_validate_code_missing_method():
    """validate_strategy_code 工具，缺少 on_bar 方法检测"""
    incomplete_code = (
        "from stockquant.strategy.base import BaseStrategy\n\n"
        "class MyStrategy(BaseStrategy):\n"
        "    name = 'MyStrategy'\n\n"
        "    def on_start(self):\n"
        "        pass\n"
    )
    result_str = validate_strategy_code(incomplete_code)
    result = json.loads(result_str)

    assert result["valid"] is False
    assert any("on_bar" in e for e in result["errors"])


# ── 6. test_score_strategy_excellent ──


def test_score_strategy_excellent():
    """score_strategy 工具，传入优秀回测指标"""
    excellent_metrics = json.dumps({
        "Annualized Return": "35%",
        "Max Drawdown": "8%",
        "Sharpe Ratio": 2.5,
        "Win Rate": "65%",
        "SQN (System Quality Number)": 4.0,
        "Total Trades": 120,
    })
    result_str = score_strategy(excellent_metrics)
    result = json.loads(result_str)

    assert result["total"] >= 70
    assert result["profitability"] >= 75
    assert result["risk_control"] >= 75
    assert result["overfitting_risk"] == "low"


# ── 7. test_score_strategy_poor ──


def test_score_strategy_poor():
    """score_strategy 工具，糟糕回测指标评分"""
    poor_metrics = json.dumps({
        "Annualized Return": "-10%",
        "Max Drawdown": "45%",
        "Sharpe Ratio": -0.5,
        "Win Rate": "30%",
        "SQN (System Quality Number)": -1.0,
        "Total Trades": 5,
    })
    result_str = score_strategy(poor_metrics)
    result = json.loads(result_str)

    assert result["total"] < 50
    assert result["profitability"] <= 30
    assert result["overfitting_risk"] == "high"


# ── 8. test_suggest_improvements ──


def test_suggest_improvements():
    """_make_suggest_improvements 工具"""
    suggestions = [
        {
            "category": "risk",
            "description": "建议添加止损逻辑",
            "priority": "high",
            "code_hint": "self.order_sell(bar, qty)",
        },
    ]
    # robust_json_parse 只接受 dict，列表会走 fallback 路径
    # 因此将建议包装在 dict 中，让 robust_json_parse 能解析
    adapter = _make_mock_adapter(json.dumps({"suggestions": suggestions}, ensure_ascii=False))
    tool_fn = _make_suggest_improvements(adapter)
    result_str = tool_fn(
        code="class MyStrategy(BaseStrategy): pass",
        score_json='{"total": 40}',
        backtest_result_json='{"Annualized Return": "5%"}',
    )
    result = json.loads(result_str)

    # robust_json_parse 返回 dict，json.dumps 后再 json.loads 仍是 dict
    assert isinstance(result, dict)
    assert "suggestions" in result
    assert result["suggestions"][0]["category"] == "risk"
    adapter.call.assert_called_once()


# ── 9. test_strategy_agent_generate ──


def test_strategy_agent_generate():
    """StrategyAgent.generate()，mock ReActAgent.run 返回含工具调用的 ReActResult"""
    strategy_code = (
        "from stockquant.strategy.base import BaseStrategy\n\n"
        "class AIStrategy(BaseStrategy):\n"
        "    name = 'AIStrategy'\n"
        "    def on_start(self): pass\n"
        "    def on_bar(self, bars): pass\n"
    )
    thoughts = [
        Thought(
            step=1,
            thought="解析策略意图",
            action="parse_strategy_intent",
            action_input={"description": "MACD金叉买入"},
            observation=json.dumps({
                "indicators": [{"name": "MACD"}],
                "entry_conditions": ["MACD 金叉"],
                "exit_conditions": ["MACD 死叉"],
                "position_method": "FixedFraction",
                "position_params": {"pct": 0.2},
                "risk_params": {},
            }),
            state=ReActState.OBSERVING,
        ),
        Thought(
            step=2,
            thought="生成策略代码",
            action="generate_strategy_code",
            action_input={"intent_json": "{}"},
            observation=strategy_code,
            state=ReActState.OBSERVING,
        ),
        Thought(
            step=3,
            thought="验证策略代码",
            action="validate_strategy_code",
            action_input={"code": strategy_code},
            observation=json.dumps({"valid": True, "errors": [], "warnings": []}),
            state=ReActState.OBSERVING,
        ),
        Thought(
            step=4,
            thought="评分",
            action="score_strategy",
            action_input={"backtest_result_json": "{}"},
            observation=json.dumps({
                "total": 75,
                "profitability": 80,
                "risk_control": 70,
                "trading_quality": 75,
                "stability": 65,
                "overfitting_risk": "low",
            }),
            state=ReActState.OBSERVING,
        ),
    ]

    react_result = ReActResult(
        final_answer="策略生成完成",
        thoughts=thoughts,
        tool_calls_made=4,
        success=True,
    )

    with patch.object(StrategyAgent, "__init__", lambda self, **kwargs: None):
        agent = StrategyAgent.__new__(StrategyAgent)
        agent._react = MagicMock()
        agent._react.run.return_value = react_result

    result = agent.generate("当MACD金叉时买入")

    assert isinstance(result, StrategyGenerationResult)
    assert result.success is True
    assert "AIStrategy" in result.code
    assert result.validation.valid is True
    assert result.score.total == 75
    assert result.intent is not None
    assert "MACD" in result.intent.indicators[0]["name"]


# ── 10. test_strategy_agent_improve ──


def test_strategy_agent_improve():
    """StrategyAgent.improve()"""
    improved_code = (
        "from stockquant.strategy.base import BaseStrategy\n\n"
        "class AIStrategy(BaseStrategy):\n"
        "    name = 'AIStrategy'\n"
        "    def on_start(self): pass\n"
        "    def on_bar(self, bars): pass\n"
    )
    thoughts = [
        Thought(
            step=1,
            thought="改进策略",
            action="generate_strategy_code",
            action_input={"intent_json": "{}"},
            observation=improved_code,
            state=ReActState.OBSERVING,
        ),
    ]

    react_result = ReActResult(
        final_answer="策略改进完成",
        thoughts=thoughts,
        tool_calls_made=1,
        success=True,
    )

    with patch.object(StrategyAgent, "__init__", lambda self, **kwargs: None):
        agent = StrategyAgent.__new__(StrategyAgent)
        agent._react = MagicMock()
        agent._react.run.return_value = react_result

    result = agent.improve(
        strategy_code="class OldStrategy: pass",
        backtest_result={"Annualized Return": "5%"},
    )

    assert isinstance(result, StrategyGenerationResult)
    assert result.success is True
    assert "AIStrategy" in result.code


# ── 11. test_extract_code_block ──


def test_extract_code_block():
    """_extract_code_block 辅助函数"""
    # 带 ```python``` 标记
    content_with_block = "这是代码：\n```python\nclass Foo:\n    pass\n```\n请检查。"
    result = _extract_code_block(content_with_block)
    assert "class Foo" in result

    # 不带标记但有 class + BaseStrategy
    content_no_block = (
        "下面是策略：\nclass MyStrategy(BaseStrategy):\n"
        "    def on_bar(self, bars):\n        pass\n"
    )
    result = _extract_code_block(content_no_block)
    assert "class MyStrategy" in result

    # 纯代码
    pure_code = "x = 1 + 2"
    result = _extract_code_block(pure_code)
    assert result == "x = 1 + 2"


# ── 12. test_parse_pct ──


def test_parse_pct():
    """_parse_pct 辅助函数"""
    # 百分比字符串
    assert _parse_pct("35%") == pytest.approx(0.35)
    assert _parse_pct("8%") == pytest.approx(0.08)

    # 已经是小数的数值
    assert _parse_pct(0.35) == pytest.approx(0.35)
    assert _parse_pct(0.08) == pytest.approx(0.08)

    # 大于1的数值（视为百分比数值）
    assert _parse_pct("35") == pytest.approx(0.35)
    assert _parse_pct("8") == pytest.approx(0.08)

    # 小于1的字符串数值
    assert _parse_pct("0.35") == pytest.approx(0.35)
