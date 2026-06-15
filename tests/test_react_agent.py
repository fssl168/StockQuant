# -*- coding: utf-8 -*-
"""Tests for stockquant.agent.react_agent"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from stockquant.agent.llm_adapter import LLMResponse
from stockquant.agent.react_agent import (
    ReActAgent,
    ReActResult,
    ReActState,
    Thought,
    _make_calculate_indicator,
    _make_get_kline,
    _make_search_news,
)
from stockquant.agent.tool_registry import ToolRegistry, tool


# ========================================================================
# Helper — build a minimal agent without hitting LLM
# ========================================================================


def _build_agent(
    max_steps: int = 10,
) -> ReActAgent:
    """Construct a ReActAgent without calling LLMAdapter.__init__."""
    agent = ReActAgent.__new__(ReActAgent)
    agent._adapter = MagicMock()
    agent._registry = ToolRegistry()
    agent._max_steps = max_steps
    agent._max_tool_calls = 3
    agent._tool_handlers = {}
    return agent


def _make_llm_response(
    content: str = "",
    tool_calls: list[dict] | None = None,
    model: str = "gpt-4",
    total_tokens: int = 100,
) -> LLMResponse:
    """Quick test LLMResponse."""
    return LLMResponse(
        content=content,
        tool_calls=tool_calls or [],
        model=model,
        usage={"total_tokens": total_tokens},
    )


def _make_tool_call(
    name: str = "get_kline",
    arguments: dict | str | None = None,
    call_id: str = "call_1",
) -> dict:
    """Quick tool_call dict."""
    if arguments is None:
        arguments = {"symbol": "sh600519", "days": 30}
    if isinstance(arguments, dict):
        args_str = json.dumps(arguments)
    else:
        args_str = arguments
    return {
        "id": call_id,
        "function": {
            "name": name,
            "arguments": args_str,
        },
    }


# ========================================================================
# ReActState
# ========================================================================


class TestReActState:
    def test_enum_values(self):
        assert ReActState.THINKING.value == "thinking"
        assert ReActState.ACTING.value == "acting"
        assert ReActState.OBSERVING.value == "observing"
        assert ReActState.FINISHED.value == "finished"
        assert ReActState.ERROR.value == "error"


# ========================================================================
# Thought / ReActResult
# ========================================================================


class TestThought:
    def test_defaults(self):
        t = Thought(step=1, thought="hello")
        assert t.step == 1
        assert t.thought == "hello"
        assert t.action is None
        assert t.action_input is None
        assert t.observation is None
        assert t.state == ReActState.THINKING


class TestReActResult:
    def test_defaults(self):
        r = ReActResult(final_answer="done")
        assert r.final_answer == "done"
        assert r.thoughts == []
        assert r.tool_calls_made == 0
        assert r.total_tokens == 0
        assert r.model_used == ""
        assert r.success is True
        assert r.error == ""

    def test_to_dict(self):
        r = ReActResult(
            final_answer="buy sh600519",
            thoughts=[
                Thought(step=1, thought="thinking", action="get_kline",
                        action_input={"symbol": "sh600519"},
                        observation="[100,101,102]",
                        state=ReActState.OBSERVING),
            ],
            tool_calls_made=1,
            total_tokens=250,
            model_used="gpt-4",
            success=True,
        )
        d = r.to_dict()
        assert d["final_answer"] == "buy sh600519"
        assert len(d["thoughts"]) == 1
        assert d["thoughts"][0]["action"] == "get_kline"
        assert d["thoughts"][0]["state"] == "observing"
        assert d["tool_calls_made"] == 1
        assert d["total_tokens"] == 250


# ========================================================================
# ReActAgent init
# ========================================================================


class TestReActAgentInit:
    def test_default_config(self):
        agent = ReActAgent.__new__(ReActAgent)
        agent._adapter = MagicMock()
        agent._registry = MagicMock()
        agent._max_steps = 10
        agent._max_tool_calls = 3
        agent._tool_handlers = {}
        assert agent._max_steps == 10
        assert agent._max_tool_calls == 3
        assert agent._tool_handlers == {}

    def test_custom_config(self):
        with MagicMock() as mock_adapter:
            pass  # just check attribute defaults

        agent = ReActAgent()
        # Real init — LLMAdapter is created with defaults
        assert agent._max_steps == 10
        assert agent._max_tool_calls == 3

    def test_registry_property(self):
        agent = _build_agent()
        assert isinstance(agent.registry, ToolRegistry)


# ========================================================================
# register_tool / register_tools
# ========================================================================


class TestToolRegistration:
    def test_register_tool_with_handler(self):
        agent = _build_agent()

        def my_handler(symbol: str) -> str:
            return f"price of {symbol}"

        agent.register_tool("get_price", my_handler, description="Get stock price")
        assert "get_price" in agent._tool_handlers
        assert agent._tool_handlers["get_price"] is my_handler

    def test_register_tool_with_decorator(self):
        agent = _build_agent()

        @tool
        def lookup(symbol: str) -> str:
            """Look up a stock."""
            return symbol

        agent.register_tool("lookup", lookup)
        assert "lookup" in agent._tool_handlers

    def test_register_tools_multiple(self):
        agent = _build_agent()

        @tool
        def tool_a(x: int) -> int:
            """Tool A."""
            return x

        @tool
        def tool_b(y: str) -> str:
            """Tool B."""
            return y

        agent.register_tools(tool_a, tool_b)
        assert "tool_a" in agent._tool_handlers
        assert "tool_b" in agent._tool_handlers


# ========================================================================
# _extract_final_answer
# ========================================================================


class TestExtractFinalAnswer:
    def test_with_final_answer_marker(self):
        content = "Thought: let me check\nFinal Answer: buy sh600519"
        result = ReActAgent._extract_final_answer(content)
        assert result == "buy sh600519"

    def test_without_final_answer_marker(self):
        content = "Thought: I need more data"
        result = ReActAgent._extract_final_answer(content)
        assert result is None

    def test_multiple_markers_returns_last(self):
        content = "Final Answer: step1\nFinal Answer: final conclusion"
        result = ReActAgent._extract_final_answer(content)
        assert result == "final conclusion"

    def test_empty_content(self):
        result = ReActAgent._extract_final_answer("")
        assert result is None

    def test_final_answer_with_newlines(self):
        content = "Final Answer:\n这是一个投资建议"
        result = ReActAgent._extract_final_answer(content)
        assert result == "这是一个投资建议"


# ========================================================================
# _build_system_prompt
# ========================================================================


class TestBuildSystemPrompt:
    def test_prompt_includes_tool_descriptions(self):
        agent = _build_agent()

        @tool
        def get_price(symbol: str) -> str:
            """Get the latest price."""
            return "100"

        agent.register_tool("get_price", get_price)
        prompt = agent._build_system_prompt()

        assert "get_price" in prompt
        assert "Get the latest price" in prompt
        assert "symbol" in prompt

    def test_prompt_without_tools(self):
        agent = _build_agent()
        prompt = agent._build_system_prompt()

        assert "你是一个专业的 A 股量化分析助手" in prompt
        assert "可用工具：" in prompt


# ========================================================================
# _execute_tool
# ========================================================================


class TestExecuteTool:
    def test_execute_known_tool(self):
        agent = _build_agent()
        agent._tool_handlers["add"] = lambda a, b: a + b
        result = agent._execute_tool("add", {"a": 3, "b": 4})
        assert result == "7"

    def test_execute_unknown_tool(self):
        agent = _build_agent()
        result = agent._execute_tool("ghost_tool", {})
        assert "Tool not registered: ghost_tool" in result

    def test_execute_handler_raises(self):
        agent = _build_agent()
        agent._tool_handlers["bad"] = lambda: (_ for _ in ()).throw(ValueError("boom"))
        result = agent._execute_tool("bad", {})
        assert "Tool error" in result
        assert "boom" in result


# ========================================================================
# _call_llm
# ========================================================================


class TestCallLLM:
    def test_forwards_to_adapter(self):
        agent = _build_agent()
        mock = agent._adapter
        mock.call_with_tools = MagicMock(return_value=_make_llm_response(content="ok"))

        agent._call_llm([{"role": "user", "content": "hi"}], [])

        mock.call_with_tools.assert_called_once()
        kwargs = mock.call_with_tools.call_args[1]
        assert kwargs["messages"] == [{"role": "user", "content": "hi"}]
        assert kwargs["tools"] == []


# ========================================================================
# _build_messages
# ========================================================================


class TestBuildMessages:
    def test_includes_system_and_user(self):
        agent = _build_agent()
        msgs = agent._build_messages("what is 600519?", [])
        assert len(msgs) >= 2
        assert msgs[0]["role"] == "system"
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "what is 600519?"

    def test_includes_history(self):
        agent = _build_agent()
        history = [
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "Hi there"},
        ]
        msgs = agent._build_messages("question", history)
        assert msgs[1] == {"role": "assistant", "content": "Hello"}
        assert msgs[2] == {"role": "user", "content": "Hi there"}
        assert msgs[-1]["content"] == "question"


# ========================================================================
# run — Final Answer path (no tools)
# ========================================================================


class TestRunWithFinalAnswer:
    def test_direct_answer(self):
        agent = _build_agent()
        agent._adapter.call_with_tools = MagicMock(
            return_value=_make_llm_response(
                content="I have enough info.\nFinal Answer: 建议买入 sh600519"
            )
        )

        result = agent.run("分析一下 sh600519")

        assert result.success is True
        assert "建议买入 sh600519" in result.final_answer
        assert result.tool_calls_made == 0
        assert result.total_tokens == 100
        assert result.model_used == "gpt-4"
        assert len(result.thoughts) >= 1
        assert result.thoughts[-1].state == ReActState.FINISHED

    def test_answer_in_first_thought(self):
        agent = _build_agent()
        agent._adapter.call_with_tools = MagicMock(
            return_value=_make_llm_response(content="Final Answer: hold")
        )

        result = agent.run("what should i do")

        assert result.final_answer == "hold"


# ========================================================================
# run — tool call path
# ========================================================================


class TestRunWithToolCalls:
    def test_single_tool_call_followed_by_answer(self):
        """LLM 先调工具，第二次调用返回最终答案。"""
        agent = _build_agent()
        call_count = [0]

        def side_effect(messages, tools):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_llm_response(
                    content="Let me get the K-line data first.",
                    tool_calls=[_make_tool_call()],
                )
            return _make_llm_response(
                content="Based on the data.\nFinal Answer: 趋势向上，建议持有"
            )

        agent._adapter.call_with_tools = MagicMock(side_effect=side_effect)

        result = agent.run("sh600519 走势如何")

        assert result.success is True
        assert "趋势向上" in result.final_answer
        assert result.tool_calls_made == 1
        assert len(result.thoughts) >= 2

    def test_multiple_tool_calls_in_one_step(self):
        """单步内多个工具调用。"""
        agent = _build_agent()
        call_count = [0]

        def side_effect(messages, tools):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_llm_response(
                    content="Checking multiple indicators.",
                    tool_calls=[
                        _make_tool_call(name="get_kline", call_id="call_1"),
                        _make_tool_call(name="search_news", call_id="call_2"),
                    ],
                )
            return _make_llm_response(
                content="Done.\nFinal Answer: 综合判断为买入"
            )

        agent._adapter.call_with_tools = MagicMock(side_effect=side_effect)

        result = agent.run("多指标分析")

        assert result.tool_calls_made == 2
        assert "综合判断为买入" in result.final_answer


# ========================================================================
# run — max steps exceeded
# ========================================================================


class TestMaxStepsExceeded:
    def test_runs_out_of_steps(self):
        """LLM 始终返回没有 Final Answer 的内容，也不调工具。"""
        agent = _build_agent(max_steps=3)
        agent._adapter.call_with_tools = MagicMock(
            return_value=_make_llm_response(content="Still analyzing...")
        )

        result = agent.run("keep going")

        assert "在 3 步内无法得出确定结论" in result.final_answer
        assert result.thoughts[-1].state == ReActState.FINISHED
        # 3 iterations (each adds 1 thought) + 1 final = 4
        assert len(result.thoughts) == 4


# ========================================================================
# run — LLM error handling
# ========================================================================


class TestLLMErrorHandling:
    def test_llm_failure_returns_error(self):
        agent = _build_agent()
        agent._adapter.call_with_tools = MagicMock(
            side_effect=RuntimeError("API timeout")
        )

        result = agent.run("something")

        assert result.success is False
        assert "API timeout" in result.error
        assert result.final_answer == ""
        assert len(result.thoughts) == 1
        assert result.thoughts[0].state == ReActState.ERROR


# ========================================================================
# run — content without tool call or answer (retries)
# ========================================================================


class TestRunContentOnlyRetries:
    def test_content_without_tool_triggers_retry(self):
        """LLM 返回纯文本内容（无 Final Answer，无 tool_calls），应追加并继续。"""
        agent = _build_agent()
        call_count = [0]

        def side_effect(messages, tools):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_llm_response(content="I need data first.")
            return _make_llm_response(content="Final Answer: 结论是买入")

        agent._adapter.call_with_tools = MagicMock(side_effect=side_effect)

        result = agent.run("analyze")

        assert "结论是买入" in result.final_answer
        assert result.tool_calls_made == 0


# ========================================================================
# Built-in tool factories
# ========================================================================


class TestToolFactories:
    def test_make_get_kline(self):
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.to_json = MagicMock(return_value='[{"close":100}]')
        mock_df.tail = MagicMock(return_value=mock_df)

        mock_fetcher = MagicMock()
        mock_fetcher.fetch.return_value = mock_df

        handler = _make_get_kline(mock_fetcher, MagicMock())
        result = handler(symbol="sh600519", days=10)
        assert "100" in result

    def test_make_get_kline_error(self):
        mock_fetcher = MagicMock()
        mock_fetcher.fetch.side_effect = RuntimeError("db down")

        handler = _make_get_kline(mock_fetcher, MagicMock())
        result = handler(symbol="sh600519", days=10)
        assert "Error" in result or "db down" in result

    def test_make_search_news(self):
        mock_searcher = MagicMock()
        mock_item = MagicMock()
        mock_item.to_dict = MagicMock(return_value={
            "title": "test", "source": "news", "url": "http://x",
            "summary": "s", "published_at": "2024-01-01", "sentiment": 0.5,
        })
        mock_searcher.search = MagicMock(return_value=[mock_item])

        handler = _make_search_news(mock_searcher)
        result = handler(symbol="sh600519", query="earnings")
        assert "test" in result

    def test_make_search_news_error(self):
        mock_searcher = MagicMock()
        mock_searcher.search.side_effect = RuntimeError("net down")

        handler = _make_search_news(mock_searcher)
        result = handler(symbol="sh600519", query="x")
        assert "Error" in result or "net down" in result

    def test_make_calculate_indicator(self):
        handler = _make_calculate_indicator()
        result = handler(symbol="sh600519", indicator_name="RSI", period=14)
        assert result == "Indicator RSI for sh600519 (period=14)"


# ========================================================================
# Edge cases
# ========================================================================


class TestEdgeCases:
    def test_tool_with_non_json_arguments(self):
        """tool call 参数不是合法 JSON 时，回退为空 dict。"""
        agent = _build_agent(max_steps=1)
        agent._adapter.call_with_tools = MagicMock(
            return_value=_make_llm_response(
                content="Let me check.",
                tool_calls=[_make_tool_call(arguments="not-json")],
            )
        )

        result = agent.run("test")
        assert result.tool_calls_made == 1

    def test_override_max_steps_in_run(self):
        agent = _build_agent(max_steps=100)
        agent._adapter.call_with_tools = MagicMock(
            return_value=_make_llm_response(content="Still thinking...")
        )

        result = agent.run("test", max_steps=2)

        # 2 iterations (each adds 1 thought) + 1 final = 3
        assert len(result.thoughts) == 3
        assert result.thoughts[-1].state == ReActState.FINISHED

    def test_response_with_none_content_and_no_tool_calls(self):
        """content=None 且无 tool_calls 时不会崩溃。"""
        agent = _build_agent()
        agent._adapter.call_with_tools = MagicMock(
            return_value=LLMResponse(content=None, tool_calls=[])
        )

        result = agent.run("test")

        # None content → no Thought per iteration; after 10 loops, max_steps exceeded
        assert result.thoughts[-1].state == ReActState.FINISHED
        assert "在 10 步内无法得出确定结论" in result.final_answer

    def test_run_with_empty_tool_registry(self):
        """没有注册任何工具时，run 不会崩溃。"""
        agent = _build_agent(max_steps=1)
        agent._adapter.call_with_tools = MagicMock(
            return_value=_make_llm_response(content="Final Answer: nothing to do")
        )

        result = agent.run("test")
        assert result.final_answer == "nothing to do"

    def test_max_steps_passed_to_run_overrides_default(self):
        agent = _build_agent(max_steps=10)
        agent._adapter.call_with_tools = MagicMock(
            return_value=_make_llm_response(content="Still thinking...")
        )

        result = agent.run("test", max_steps=2)
        # 2 iterations + 1 final
        assert len(result.thoughts) == 3
        assert "在 2 步内无法得出确定结论" in result.final_answer
