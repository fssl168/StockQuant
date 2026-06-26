# -*- coding: utf-8 -*-
"""
AIService - unified AI / LLM call entry point.

Wraps LLMAdapter with config-driven provider selection,
cost tracking, and structured response handling.
"""

from __future__ import annotations

import json
import logging
import re
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

    def generate_strategy(self, description: str, **kwargs) -> str:
        """AI 生成策略代码（统一入口）。

        根据自然语言描述生成 StockQuant 兼容的 BaseStrategy 子类代码。

        Parameters
        ----------
        description : str
            自然语言策略描述，例如 "当MACD金叉且RSI<30时买入"
        **kwargs
            额外参数: symbol, start_date, end_date, cash

        Returns
        -------
        str
            生成的策略代码（Python 源文本）
        """
        if not self._adapter or not self._config.enabled:
            return "# Error: AI not configured"
        try:
            system_prompt = (
                "你是一个专业的 A 股量化策略工程师。请根据用户的自然语言描述，"
                "生成可在 StockQuant 框架中运行的 BaseStrategy 子类代码。\n\n"
                "策略代码规范：\n"
                "- 必须继承 BaseStrategy\n"
                "- 必须实现 on_start() 和 on_bar() 方法\n"
                "- 使用 self.SMA/EMA/RSI/MACD/BOLL/ATR/KDJ 等指标方法\n"
                "- 使用 self.order_market() / self.order_sell() 下单\n"
                "- 使用 self.log() 记录交易日志\n"
                "- A 股规则：买入数量必须为 100 的整数倍，T+1 卖出限制\n"
                "- 代码必须完整可执行，包含必要的导入语句\n"
                "- 只在代码块中返回策略代码，不要包含其他解释文字\n"
            )
            message = (
                f"请根据以下策略描述生成可执行的策略代码：\n\n"
                f"策略描述：{description}\n"
            )
            symbol = kwargs.get("symbol", "sh600519")
            start_date = kwargs.get("start_date", "2023-01-01")
            end_date = kwargs.get("end_date", "2024-12-31")
            cash = kwargs.get("cash", 1000000.0)
            message += (
                f"回测参数：标的={symbol}, 起始={start_date}, 结束={end_date}, "
                f"资金={cash:,.0f}"
            )

            resp = self._adapter.call(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                temperature=max(0.7, self._config.temperature),  # 代码生成需要更高创造性
                max_tokens=self._config.max_tokens,
            )
            self._total_calls += 1
            self._record_cost(resp)
            content = resp.content or ""
            # 尝试提取代码块
            code_match = re.search(r'```(?:python)?\s*\n(.*?)```', content, re.DOTALL)
            if code_match:
                return code_match.group(1).strip()
            return content
        except Exception as e:
            logger.error("AIService.generate_strategy failed: %s", e, exc_info=True)
            return f"# Error: {e}"

    def check_hallucination(self, content: str, **kwargs) -> Dict[str, Any]:
        """幻觉检测（统一入口）。

        检测 AI 生成的内容是否存在事实性错误、数据捏造或逻辑不一致。

        Parameters
        ----------
        content : str
            待检测的文本内容
        **kwargs
            额外参数: symbol (相关股票代码), threshold (置信度阈值)

        Returns
        -------
        Dict[str, Any]
            {
                "passed": bool,
                "score": float,           # 可信度评分 (0-1)
                "issues": List[str],      # 发现的问题
                "category": str,          # 问题分类 (none/fabrication/inconsistency/outdated)
            }
        """
        if not self._adapter or not self._config.enabled:
            return {"passed": True, "score": 1.0, "issues": [], "category": "none", "error": "AI not configured"}
        try:
            system_prompt = (
                "你是一个金融内容可信度检测器。请仔细分析以下内容的真实性，"
                "检查是否存在以下问题：\n"
                "1. **数据捏造**：虚构的价格、成交量、财务数据\n"
                "2. **事实错误**：与公开事实不符的描述\n"
                "3. **逻辑不一致**：自相矛盾的分析\n"
                "4. **过时信息**：引用了不再有效的事件或数据\n"
                "\n"
                "请以 JSON 格式返回检测结果，格式：\n"
                '{"passed": true/false, "score": 0.0-1.0, "issues": ["问题1", ...], "category": "none|fabrication|inconsistency|outdated"}'
            )
            message = (
                f"请检测以下内容的可信度：\n\n{content}\n\n"
                f"相关股票：{kwargs.get('symbol', 'N/A')}\n"
            )
            threshold = kwargs.get("threshold", 0.3)

            resp = self._adapter.call(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                temperature=0.0,  # 检测需要确定性输出
                max_tokens=1024,
            )
            self._total_calls += 1
            self._record_cost(resp)

            # 尝试解析 JSON 结果
            json_match = re.search(r'\{[^{}]*"passed"[^{}]*\}', resp.content or "{}", re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    result.setdefault("category", "none")
                    result.setdefault("issues", [])
                    result.setdefault("score", 1.0)
                    result.setdefault("passed", True)
                    # 根据 threshold 判断是否通过
                    result["passed"] = result["score"] >= threshold
                    return result
                except (json.JSONDecodeError, AttributeError):
                    pass

            # 解析失败，fallback 为简单判断
            content_lower = (resp.content or "").lower()
            issues = []
            if "fabrication" in content_lower or "虚构" in content_lower or "捏造" in content_lower:
                issues.append("可能发现数据捏造")
            if "inconsistency" in content_lower or "矛盾" in content_lower:
                issues.append("可能发现逻辑矛盾")
            if "outdated" in content_lower or "过时" in content_lower:
                issues.append("可能引用过时信息")

            return {
                "passed": len(issues) == 0,
                "score": 0.0 if issues else 1.0,
                "issues": issues,
                "category": "fabrication" if issues else "none",
            }
        except Exception as e:
            logger.error("AIService.check_hallucination failed: %s", e, exc_info=True)
            return {"passed": True, "score": 1.0, "issues": [], "category": "none", "error": str(e)}

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
