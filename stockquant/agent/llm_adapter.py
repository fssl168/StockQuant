# -*- coding: utf-8 -*-
"""LLM Adapter — 统一的 LLM 调用适配层，支持 tool calling"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _resolve_api_key(api_key: Optional[str]) -> Optional[str]:
    """解析 API Key：优先使用显式值，否则从环境变量读取。"""
    if api_key:
        return api_key
    # 常见的 LLM API Key 环境变量名
    for env_name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "LLM_API_KEY"):
        val = os.environ.get(env_name)
        if val:
            return val
    return None


@dataclass
class LLMResponse:
    """LLM 调用返回的标准化响应。"""

    content: str = ""
    reasoning_content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    model: str = ""
    finish_reason: str = ""

    @property
    def has_tool_calls(self) -> bool:
        """是否有工具调用。"""
        return len(self.tool_calls) > 0


class LLMAdapter:
    """统一 LLM 适配器，支持 tool calling。

    使用 ``litellm`` 实现 provider-agnostic 调用。
    litellm 采用懒加载（lazy import），避免硬依赖。
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        fallback_models: Optional[list[str]] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._model = model
        self._api_key = _resolve_api_key(api_key)
        self._fallback_models = fallback_models or []
        self._base_url = base_url
        self._litellm: Any = None

    def _ensure_litellm(self) -> None:
        """懒加载 litellm 模块。"""
        if self._litellm is None:
            try:
                import litellm
                self._litellm = litellm
            except ImportError:
                raise ImportError(
                    "litellm is required for LLM tool calling. "
                    "Install with: pip install litellm"
                )

    def call_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """带工具调用的 LLM 请求，支持模型回退链。

        Parameters
        ----------
        messages : list[dict]
            消息列表（OpenAI format）
        tools : list[dict]
            工具定义列表（OpenAI format）
        model : str, optional
            优先使用的模型名称
        temperature : float
            采样温度
        max_tokens : int
            最大输出 token 数

        Returns
        -------
        LLMResponse

        Raises
        ------
        RuntimeError
            所有候选模型均调用失败时抛出
        """
        self._ensure_litellm()
        candidates = [model or self._model] + self._fallback_models
        last_exception: Optional[Exception] = None

        for candidate in candidates:
            try:
                response = self._litellm.completion(
                    model=candidate,
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=self._api_key,
                    base_url=self._base_url,
                )

                choice = response.choices[0]
                message = choice.message

                # 解析 tool_calls
                tool_calls: list[dict] = []
                if hasattr(message, "tool_calls") and message.tool_calls:
                    for tc in message.tool_calls:
                        tool_calls.append({
                            "id": tc.id,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        })

                return LLMResponse(
                    content=message.content or "",
                    reasoning_content=getattr(message, "reasoning_content", "") or "",
                    tool_calls=tool_calls,
                    usage=response.get("usage", {}),
                    model=candidate,
                    finish_reason=choice.finish_reason,
                )

            except Exception as exc:
                logger.warning(
                    "Model %s failed: %s — trying fallback", candidate, exc
                )
                last_exception = exc

        raise RuntimeError(
            f"All {len(candidates)} model candidates failed. "
            f"Last error: {last_exception}"
        )

    def call(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """简单 LLM 调用（无工具）。"""
        self._ensure_litellm()
        response = self._litellm.completion(
            model=model or self._model,
            messages=messages,
            api_key=self._api_key,
            base_url=self._base_url,
            **kwargs,
        )

        choice = response.choices[0]
        message = choice.message

        return LLMResponse(
            content=message.content or "",
            reasoning_content=getattr(message, "reasoning_content", "") or "",
            usage=response.get("usage", {}),
            model=model or self._model,
            finish_reason=choice.finish_reason,
        )
