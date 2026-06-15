# -*- coding: utf-8 -*-
"""Tests for stockquant.agent.llm_adapter"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from stockquant.agent.llm_adapter import LLMResponse, LLMAdapter


class TestLLMResponse:
    def test_defaults(self):
        resp = LLMResponse()
        assert resp.content == ""
        assert resp.tool_calls == []
        assert resp.model == ""
        assert resp.has_tool_calls is False

    def test_has_tool_calls_true(self):
        resp = LLMResponse(tool_calls=[{"id": "tc1", "function": {"name": "x", "arguments": "{}"}}])
        assert resp.has_tool_calls is True

    def test_content_only(self):
        resp = LLMResponse(content="hello", model="gpt-4")
        assert resp.content == "hello"
        assert resp.model == "gpt-4"


class TestLLMAdapterInit:
    def test_default_model(self):
        adapter = LLMAdapter()
        assert adapter._model == "gpt-4"
        assert adapter._fallback_models == []

    def test_custom_model_and_fallback(self):
        adapter = LLMAdapter(model="claude-3", fallback_models=["claude-2", "gpt-4"])
        assert adapter._model == "claude-3"
        assert adapter._fallback_models == ["claude-2", "gpt-4"]

    def test_api_key_stored(self):
        adapter = LLMAdapter(api_key="sk-test")
        assert adapter._api_key == "sk-test"


class TestLLMAdapterEnsureLiteLLM:
    def test_import_error_raises(self):
        adapter = LLMAdapter()
        adapter._litellm = None
        with patch.dict("sys.modules", {"litellm": None}):
            with pytest.raises(ImportError, match="litellm is required"):
                adapter._ensure_litellm()

    def test_lazy_load(self):
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"litellm": mock_module}):
            adapter = LLMAdapter()
            adapter._ensure_litellm()
            assert adapter._litellm is mock_module


class TestLLMAdapterCall:
    def test_call_success(self):
        mock_module = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "test response"
        mock_message.reasoning_content = "thinking..."
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_response.get.return_value = {"prompt_tokens": 10, "completion_tokens": 20}
        mock_module.completion.return_value = mock_response

        adapter = LLMAdapter()
        adapter._litellm = mock_module

        result = adapter.call([{"role": "user", "content": "hello"}])

        assert result.content == "test response"
        assert result.reasoning_content == "thinking..."
        assert result.model == "gpt-4"
        assert result.usage == {"prompt_tokens": 10, "completion_tokens": 20}

    def test_call_uses_override_model(self):
        mock_module = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "ok"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_module.completion.return_value = mock_response

        adapter = LLMAdapter()
        adapter._litellm = mock_module

        result = adapter.call([{"role": "user", "content": "hi"}], model="custom-model")
        assert result.model == "custom-model"

    def test_call_with_kwargs(self):
        mock_module = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "ok"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_module.completion.return_value = mock_response

        adapter = LLMAdapter()
        adapter._litellm = mock_module

        result = adapter.call([{"role": "user", "content": "hi"}], temperature=0.7, max_tokens=100)
        mock_module.completion.assert_called_once()
        call_kwargs = mock_module.completion.call_args[1]
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 100


class TestLLMAdapterCallWithTools:
    def test_call_with_tools_success(self):
        mock_module = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "I'll call a tool"
        mock_message.tool_calls = []
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_response.get.return_value = {}
        mock_module.completion.return_value = mock_response

        adapter = LLMAdapter()
        adapter._litellm = mock_module

        tools = [{"type": "function", "function": {"name": "get_price", "parameters": {}}}]
        result = adapter.call_with_tools(
            messages=[{"role": "user", "content": "check price"}],
            tools=tools,
        )
        assert result.content == "I'll call a tool"

    def test_call_with_tools_parse_tool_calls(self):
        mock_module = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "use get_price"

        mock_tc = MagicMock()
        mock_tc.id = "call_123"
        mock_tc.function.name = "get_price"
        mock_tc.function.arguments = '{"symbol": "sh600519"}'
        mock_message.tool_calls = [mock_tc]

        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_module.completion.return_value = mock_response

        adapter = LLMAdapter()
        adapter._litellm = mock_module

        tools = [{"type": "function", "function": {"name": "get_price"}}]
        result = adapter.call_with_tools(
            messages=[{"role": "user", "content": "get price"}],
            tools=tools,
        )
        assert result.has_tool_calls is True
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["id"] == "call_123"
        assert result.tool_calls[0]["function"]["name"] == "get_price"

    def test_fallback_chain(self):
        mock_module = MagicMock()

        # First call fails, second succeeds
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "recovered"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_module.completion.side_effect = [RuntimeError("model 1 down"), mock_response]

        adapter = LLMAdapter(fallback_models=["gpt-3.5"])
        adapter._litellm = mock_module

        tools = []
        result = adapter.call_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            tools=tools,
        )
        assert result.content == "recovered"
        assert mock_module.completion.call_count == 2

    def test_all_models_fail_raises(self):
        mock_module = MagicMock()
        mock_module.completion.side_effect = RuntimeError("all down")

        adapter = LLMAdapter(fallback_models=["fallback1", "fallback2"])
        adapter._litellm = mock_module

        with pytest.raises(RuntimeError, match="All 3 model candidates failed"):
            adapter.call_with_tools(
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
            )

    def test_none_content_handled(self):
        mock_module = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = None
        mock_message.tool_calls = None
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_module.completion.return_value = mock_response

        adapter = LLMAdapter()
        adapter._litellm = mock_module

        result = adapter.call_with_tools(messages=[], tools=[])
        assert result.content == ""
        assert result.tool_calls == []
