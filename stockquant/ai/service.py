# -*- coding: utf-8 -*-
"""
AIService - unified AI / LLM call entry point.

Wraps LLMAdapter with config-driven provider selection,
cost tracking, and structured response handling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional, Tuple

from stockquant.config import AISettings, get_config, LLMProvider
from stockquant.agent.llm_adapter import LLMAdapter, LLMResponse

logger = logging.getLogger("stockquant.ai.service")


@dataclass
class AIServiceResponse:
    """Structured AI service response (mirrors LLMResponse + metadata)."""

    content: str = ""
    reasoning_content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=dict)
    model: str = ""
    finish_reason: str = ""
    provider: str = ""
    error: str = ""

    @classmethod
    def from_llm(cls, resp, provider=""):
        return cls(
            content=resp.content or "",
            reasoning_content=resp.reasoning_content or "",
            tool_calls=list(resp.tool_calls or []),
            usage=dict(resp.usage or {}),
            model=resp.model or "",
            finish_reason=resp.finish_reason or "",
            provider=provider,
        )

    @property
    def success(self) -> bool:
        return bool(self.content) and not self.error

    @property
    def cost(self) -> float:
        input_tokens = self.usage.get("prompt_tokens", 0)
        output_tokens = self.usage.get("completion_tokens", 0)
        rates = {
            "gpt-4o": (2.5, 10.0),
            "gpt-4o-mini": (0.15, 0.6),
            "claude-sonnet-4-20250514": (3.0, 15.0),
            "qwen-max": (2.8, 11.2),
            "llama3": (0.0, 0.0),
        }
        in_r, out_r = rates.get(self.model, (0.0, 0.0))
        return round((input_tokens * in_r + output_tokens * out_r) / 1_000_000, 6)


class AIService:
    """Unified LLM call service backed by config.AISettings.

    Reads provider credentials from config, creates the appropriate
    LLMAdapter instance, and provides chat / chat_with_tools / stream
    methods with cost tracking and conversation history.
    """

    def __init__(self, settings=None):
        self._config = settings or get_config().ai
        self._adapter = None
        self._conversation_history = []
        self._total_cost = 0.0
        self._total_calls = 0
        self._initialize()

    def _initialize(self) -> None:
        """Build LLMAdapter from current config."""
        if self._adapter is not None:
            return
        try:
            provider = self._config.default_provider
            if provider == LLMProvider.OPENAI:
                model = self._config.openai_model
                api_key = self._config.openai_api_key or None
                base_url = self._config.openai_base_url or None
            elif provider == LLMProvider.ANTHROPIC:
                model = self._config.anthropic_model
                api_key = self._config.anthropic_api_key or None
                base_url = self._config.anthropic_base_url or None
            elif provider == LLMProvider.OLLAMA:
                model = self._config.ollama_model
                api_key = None
                base_url = self._config.ollama_base_url
            elif provider == LLMProvider.QWEN:
                model = self._config.qwen_model
                api_key = self._config.qwen_api_key or None
                base_url = self._config.qwen_base_url
            else:
                model = "gpt-4o"
                api_key = None
                base_url = None
            self._adapter = LLMAdapter(
                model=model,
                api_key=api_key,
                base_url=base_url,
            )
            logger.info(
                "AIService initialized: provider=%s model=%s",
                provider.value, model,
            )
        except Exception as e:
            logger.warning("AIService init failed (non-fatal): %s", e)
            self._adapter = None

    def chat(self, message, system_prompt=""):
        """Non-streaming single-turn chat. Returns assistant reply text."""
        if not self._adapter or not self._config.enabled:
            return ""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message})
            resp = self._adapter.call(
                messages,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
            )
            self._total_calls += 1
            self._record_cost(resp)
            self._conversation_history.append(("user", message))
            self._conversation_history.append(("assistant", resp.content))
            return resp.content or ""
        except Exception as e:
            logger.error("AIService.chat failed: %s", e, exc_info=True)
            return ""

    def chat_stream(self, message, system_prompt=""):
        """Stream-friendly wrapper - calls once, yields content in chunks."""
        text = self.chat(message, system_prompt)
        for i in range(0, len(text), 20):
            yield text[i:i + 20]

    def chat_with_tools(self, messages, tools):
        """Call LLM with tool definitions. Returns structured response."""
        if not self._adapter or not self._config.enabled:
            return AIServiceResponse(error="AI not configured")
        try:
            resp = self._adapter.call_with_tools(
                messages, tools,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
            )
            result = AIServiceResponse.from_llm(resp, self._config.default_provider.value)
            self._total_calls += 1
            self._record_cost(resp)
            return result
        except Exception as e:
            logger.error("AIService.chat_with_tools failed: %s", e, exc_info=True)
            return AIServiceResponse(error=str(e))

    def structured_chat(self, prompt, system_prompt=""):
        """Chat that returns a structured AIServiceResponse."""
        if not self._adapter or not self._config.enabled:
            return AIServiceResponse(error="AI not configured")
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            resp = self._adapter.call(
                messages,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
            )
            result = AIServiceResponse.from_llm(resp, self._config.default_provider.value)
            self._total_calls += 1
            self._record_cost(resp)
            return result
        except Exception as e:
            logger.error("AIService.structured_chat failed: %s", e, exc_info=True)
            return AIServiceResponse(error=str(e))

    def append_history(self, role, content):
        self._conversation_history.append((role, content))
        if len(self._conversation_history) > 100:
            self._conversation_history = self._conversation_history[-100:]

    def get_history(self, limit=20):
        return [{"role": r, "content": c} for r, c in self._conversation_history[-limit:]]

    @property
    def is_configured(self):
        return self._adapter is not None and self._config.enabled


    def get_ai_model(self) -> str:
        p = self._config.default_provider
        return {
            "openai": self._config.openai_model,
            "anthropic": self._config.anthropic_model,
            "ollama": self._config.ollama_model,
            "qwen": self._config.qwen_model,
        }.get(p.value, "gpt-4o")

    @property
    def stats(self):
        return {
            "enabled": self._config.enabled,
            "provider": self._config.default_provider.value,
            "model": self.get_ai_model(),
            "total_calls": self._total_calls,
            "total_cost": round(self._total_cost, 6),
        }

    def switch_provider(self, provider):
        """Hot-swap the LLM provider from config."""
        if not self._config.has_api_key(provider) and provider != LLMProvider.OLLAMA:
            logger.warning("Cannot switch to %s: no API key", provider.value)
            return False
        self._config.default_provider = provider
        self._initialize()
        return True

    def _record_cost(self, resp):
        cost = 0.0
        if resp.usage:
            in_t = resp.usage.get("prompt_tokens", 0)
            out_t = resp.usage.get("completion_tokens", 0)
            rates = {
                "gpt-4o": (2.5, 10.0),
                "gpt-4o-mini": (0.15, 0.6),
                "claude-sonnet-4-20250514": (3.0, 15.0),
                "qwen-max": (2.8, 11.2),
            }
            in_r, out_r = rates.get(resp.model, (0.0, 0.0))
            cost = (in_t * in_r + out_t * out_r) / 1_000_000
        self._total_cost += cost
