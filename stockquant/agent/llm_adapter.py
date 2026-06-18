# -*- coding: utf-8 -*-
"""LLM Adapter — 统一的 LLM 调用适配层，支持 tool calling + 本地推理"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 模型定价参考 (USD per 1K tokens) — 粗略估算
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
    "claude-haiku-3-20250307": {"input": 0.00025, "output": 0.00125},
}

_DEFAULT_PRICING = {"input": 0.001, "output": 0.003}


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


class LocalLLMAdapter:
    """本地 LLM 推理适配器 — 满足 NFR008 Tick 级 <200ms 延迟要求

    支持两种后端:
    1. HuggingFace transformers 本地推理（模型名以 ``local/`` 前缀标识）
    2. Ollama 本地服务（通过 HTTP API，模型名以 ``ollama/`` 前缀标识）

    使用方式::

        # HuggingFace transformers
        adapter = LocalLLMAdapter(model="qwen2.5-7b-instruct", backend="transformers")

        # Ollama
        adapter = LocalLLMAdapter(model="qwen2.5-7b-instruct", backend="ollama")

        response = adapter.call(messages)
    """

    def __init__(
        self,
        model: str,
        backend: str = "transformers",
        base_url: Optional[str] = None,
    ) -> None:
        self._model = model
        self._backend = backend  # "transformers" / "ollama"
        self._base_url = base_url or "http://localhost:11434"
        self._pipeline: Any = None

    def _ensure_loaded(self) -> None:
        """懒加载模型（仅 transformers 后端需要预加载）。"""
        if self._backend == "ollama":
            return  # ollama 通过 HTTP 调用，无需预加载
        if self._pipeline is not None:
            return
        try:
            from transformers import pipeline
            self._pipeline = pipeline(
                "text-generation",
                model=self._model,
                device=-1,  # CPU
            )
            logger.info("本地 HuggingFace 模型加载成功: %s", self._model)
        except ImportError as exc:
            raise ImportError(
                "transformers 未安装，无法使用本地推理。"
                "Install with: pip install transformers torch"
            ) from exc

    def call(self, messages: list[dict], **kwargs: Any) -> LLMResponse:
        """本地模型调用。

        Parameters
        ----------
        messages : list[dict]
            消息列表（OpenAI format）
        **kwargs
            max_tokens, temperature, timeout 等

        Returns
        -------
        LLMResponse
        """
        self._ensure_loaded()

        if self._backend == "transformers":
            return self._call_transformers(messages, **kwargs)
        elif self._backend == "ollama":
            return self._call_ollama(messages, **kwargs)
        else:
            raise ValueError(f"不支持的 backend: {self._backend}")

    def _call_transformers(self, messages: list[dict], **kwargs: Any) -> LLMResponse:
        """HuggingFace transformers 本地推理。"""
        prompt = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
        max_new_tokens = kwargs.get("max_tokens", 512)
        result = self._pipeline(prompt, max_new_tokens=max_new_tokens, return_full_text=False)
        content = ""
        if result:
            first = result[0]
            content = first.get("generated_text", "") if isinstance(first, dict) else str(first)
        return LLMResponse(
            content=content,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            model=f"local/{self._model}",
            finish_reason="stop",
        )

    def _call_ollama(self, messages: list[dict], **kwargs: Any) -> LLMResponse:
        """Ollama 本地服务调用。"""
        import httpx
        timeout = kwargs.get("timeout", 30)
        response = httpx.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", 0.0),
                    "num_predict": kwargs.get("max_tokens", 512),
                },
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        msg = data.get("message", {})
        return LLMResponse(
            content=msg.get("content", ""),
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            },
            model=f"ollama/{self._model}",
            finish_reason="stop",
        )


class LLMAdapter:
    """统一 LLM 适配器，支持 tool calling。

    使用 ``litellm`` 实现 provider-agnostic 调用。
    litellm 采用懒加载（lazy import），避免硬依赖。
    """

    # 类级别成本追踪器
    _cost_tracker: dict = {
        "total_tokens": 0,
        "total_calls": 0,
        "estimated_cost_usd": 0.0,
    }

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
        logger.info("LLMAdapter 初始化: model=%s, base_url=%s, api_key=%s",
                     model, base_url, ("****" if self._api_key else "None"))

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

    @classmethod
    def get_cost_stats(cls) -> dict:
        """获取 LLM 调用成本统计。

        Returns
        -------
        dict
            包含 total_tokens, total_calls, estimated_cost_usd
        """
        return dict(cls._cost_tracker)

    @classmethod
    def _update_cost_tracker(cls, usage: dict, model: str) -> None:
        """根据 LLM 响应的 usage 信息更新成本追踪器。

        Parameters
        ----------
        usage : dict
            litellm 返回的 usage 字段，含 prompt_tokens / completion_tokens
        model : str
            使用的模型名称
        """
        if not usage:
            return

        prompt_tokens = usage.get("prompt_tokens", 0) or 0
        completion_tokens = usage.get("completion_tokens", 0) or 0
        total = prompt_tokens + completion_tokens

        # 查找模型定价（支持 provider/ 前缀格式）
        model_key = model.split("/")[-1] if "/" in model else model
        pricing = _MODEL_PRICING.get(model_key, _DEFAULT_PRICING)

        cost = (prompt_tokens / 1000.0) * pricing["input"] + (completion_tokens / 1000.0) * pricing["output"]

        cls._cost_tracker["total_tokens"] += total
        cls._cost_tracker["total_calls"] += 1
        cls._cost_tracker["estimated_cost_usd"] += cost

        logger.debug(
            "LLM 成本更新: model=%s, tokens=%d+%d, cost=$%.6f, 累计=$%.4f",
            model, prompt_tokens, completion_tokens, cost,
            cls._cost_tracker["estimated_cost_usd"],
        )

    def _normalize_model(self, model: str) -> str:
        """规范化模型名称。

        当使用自定义 base_url（OpenAI 兼容端点）时，
        为没有 provider 前缀的模型名自动补全 ``openai/`` 前缀，
        以满足 LiteLLM 的路由要求。
        """
        # 已有 provider 前缀 或 是特殊本地模型 → 直接返回
        if (
            "/" in model
            or model.startswith("local/")
            or model.startswith("ollama/")
            or model == "local_rule_engine"
        ):
            return model

        # 自定义 base_url + 无前缀模型名 → 补全 openai/ 前缀
        if self._base_url:
            logger.info("检测到自定义 base_url，自动为模型 %s 补全 openai/ 前缀", model)
            return f"openai/{model}"

        return model

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
        raw_model = model or self._model
        candidates = [self._normalize_model(raw_model)] + [
            self._normalize_model(m) for m in self._fallback_models
        ]
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

                usage_info = response.get("usage", {})
                result = LLMResponse(
                    content=message.content or "",
                    reasoning_content=getattr(message, "reasoning_content", "") or "",
                    tool_calls=tool_calls,
                    usage=usage_info,
                    model=candidate,
                    finish_reason=choice.finish_reason,
                )
                self._update_cost_tracker(usage_info, candidate)
                return result

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
        """简单 LLM 调用（无工具）。

        路由规则:
        1. ``local_rule_engine`` → 本地规则引擎（<50ms）
        2. ``local/*`` 或 ``ollama/*`` 前缀 → 本地 LLM 推理（<200ms，NFR008）
        3. 其他 → 远程 LLM（litellm）
        """
        used_model = model or self._model

        # 本地规则引擎路径
        if used_model == "local_rule_engine":
            return self._call_local_rule_engine(messages)

        # 本地 LLM 路径（HuggingFace transformers / Ollama）
        if used_model.startswith("local/") or used_model.startswith("ollama/"):
            return self._call_local_llm(messages, used_model, **kwargs)

        # 远程 LLM 路径 — 规范化模型名称（补全 provider 前缀）
        normalized = self._normalize_model(used_model)
        self._ensure_litellm()
        response = self._litellm.completion(
            model=normalized,
            messages=messages,
            api_key=self._api_key,
            base_url=self._base_url,
            **kwargs,
        )

        choice = response.choices[0]
        message = choice.message
        usage_info = response.get("usage", {})

        result = LLMResponse(
            content=message.content or "",
            reasoning_content=getattr(message, "reasoning_content", "") or "",
            usage=usage_info,
            model=used_model,
            finish_reason=choice.finish_reason,
        )
        self._update_cost_tracker(usage_info, used_model)
        return result

    def _call_local_llm(self, messages: list[dict], model: str, **kwargs: Any) -> LLMResponse:
        """调用本地 LLM 适配器（HuggingFace / Ollama）。

        Parameters
        ----------
        messages : list[dict]
            消息列表
        model : str
            模型名，格式为 ``local/<model_name>`` 或 ``ollama/<model_name>``
        """
        backend = "ollama" if model.startswith("ollama/") else "transformers"
        model_name = model.split("/", 1)[1]
        adapter = LocalLLMAdapter(
            model=model_name,
            backend=backend,
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        return adapter.call(messages, **kwargs)

    def _call_local_rule_engine(self, messages: list[dict]) -> LLMResponse:
        """本地规则引擎调用 — 基于 MA/MACD/RSI/BOLL 的快速信号判断

        从 messages 中提取市场数据，调用 LocalRuleEngine 生成决策。
        """
        try:
            from stockquant.ai.local_rule_engine import LocalRuleEngine, SignalType

            engine = LocalRuleEngine()

            # 从 messages 中提取价格数据
            market_data = self._extract_market_data(messages)
            closes = market_data.get("closes", [])

            if closes:
                signal = engine.analyze_signal(closes)
                action = signal.signal.value
                content = (
                    f"规则引擎分析结果: {action}\n"
                    f"置信度: {signal.confidence:.2f}\n"
                    f"原因: {', '.join(signal.reasons)}\n"
                    f"指标: RSI={signal.indicators.get('rsi', 'N/A')}, "
                    f"MACD={signal.indicators.get('macd_hist', 'N/A')}, "
                    f"MA5={signal.indicators.get('ma5', 'N/A')}, "
                    f"MA20={signal.indicators.get('ma20', 'N/A')}"
                )
            else:
                content = "规则引擎: 数据不足，建议持有观望"
                action = "hold"

            return LLMResponse(
                content=content,
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                model="local_rule_engine",
                finish_reason="stop",
            )
        except Exception as exc:
            logger.warning("本地规则引擎调用失败: %s", exc)
            return LLMResponse(
                content=f"规则引擎异常: {exc}",
                model="local_rule_engine",
                finish_reason="stop",
            )

    @staticmethod
    def _extract_market_data(messages: list[dict]) -> dict:
        """从消息列表中提取市场数据"""
        import json as _json

        market_data: dict = {"closes": []}

        for msg in messages:
            content = msg.get("content", "")
            if not content:
                continue

            # 尝试解析 JSON 格式的市场数据
            try:
                data = _json.loads(content)
                if isinstance(data, dict):
                    if "closes" in data:
                        market_data["closes"] = data["closes"]
                    elif "price" in data:
                        market_data["closes"].append(float(data["price"]))
                    elif "close" in data:
                        market_data["closes"].append(float(data["close"]))
            except (ValueError, TypeError):
                pass

        return market_data
