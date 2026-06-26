# -*- coding: utf-8 -*-
"""ReAct Agent — 推理-行动循环"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, List, Optional

from stockquant.agent.llm_adapter import LLMAdapter, LLMResponse
from stockquant.agent.tool_registry import ToolRegistry, tool

logger = logging.getLogger("stockquant.agent")


class ReActState(Enum):
    """ReAct 循环状态"""
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    FINISHED = "finished"
    ERROR = "error"


@dataclass
class Thought:
    """单步推理记录"""
    step: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[dict] = None
    observation: Optional[str] = None
    state: ReActState = ReActState.THINKING


@dataclass
class ReActResult:
    """ReAct Agent 执行结果"""
    final_answer: str
    thoughts: list[Thought] = field(default_factory=list)
    tool_calls_made: int = 0
    total_tokens: int = 0
    model_used: str = ""
    success: bool = True
    error: str = ""

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "final_answer": self.final_answer,
            "thoughts": [
                {
                    "step": t.step,
                    "thought": t.thought,
                    "action": t.action,
                    "action_input": t.action_input,
                    "observation": t.observation,
                    "state": t.state.value,
                }
                for t in self.thoughts
            ],
            "tool_calls_made": self.tool_calls_made,
            "total_tokens": self.total_tokens,
            "model_used": self.model_used,
            "success": self.success,
            "error": self.error,
        }


# ── Built-in tools for ReAct Agent ──


def _make_get_kline(fetcher_manager: Any, calendar: Any) -> Callable:
    """工厂函数：创建带闭包的 get_kline 工具"""

    @tool
    def get_kline(symbol: str, days: int = 100) -> str:
        """获取指定标的的历史 K 线数据（标准化格式）"""
        try:
            df = fetcher_manager.fetch(symbol, timeframe="1d", end=str(datetime.now().date()))
            if df is not None and not df.empty:
                df = df.tail(days)
                return df.tail(days).to_json(orient="records", force_ascii=False, date_format="iso")
            return f"No data for {symbol}"
        except Exception as exc:
            return f"Error fetching kline for {symbol}: {exc}"

    return get_kline


def _make_search_news(news_searcher: Any) -> Callable:
    """工厂函数：创建带闭包的 search_news 工具"""

    @tool
    def search_news(symbol: str, query: str = "") -> str:
        """搜索指定标的的新闻"""
        try:
            items = news_searcher.search(symbol, query=query if query else None)
            return json.dumps(
                [item.to_dict() for item in items],
                ensure_ascii=False,
                default=str,
            )
        except Exception as exc:
            return f"Error searching news for {symbol}: {exc}"

    return search_news


def _make_calculate_indicator() -> Callable:
    """工厂函数：创建带闭包的 calculate_indicator 工具"""

    @tool
    def calculate_indicator(symbol: str, indicator_name: str = "",
                           period: int = 14) -> str:
        """计算技术指标"""
        return f"Indicator {indicator_name} for {symbol} (period={period})"

    return calculate_indicator


class ReActAgent:
    """ReAct (Reasoning + Acting) Agent。

    推理循环：
    1. 思考当前信息，决定下一步动作
    2. 选择工具执行
    3. 观察工具返回结果
    4. 回到步骤 1，直到得出最终答案

    Parameters
    ----------
    model : str
        LLM 模型名称
    api_key : str | None
        API Key
    max_steps : int
        最大推理步数（防止无限循环）
    max_tool_calls_per_step : int
        每步最大工具调用数
    """

    # ── Prompt Templates ──

    SYSTEM_PROMPT = """你是一个专业的 A 股量化分析助手。
你的任务是通过工具调用来获取数据和分析结果，最终给出投资建议。

你的工作流程：
1. **思考 (Thought)**: 分析当前信息，确定下一步需要做什么
2. **行动 (Action)**: 选择最合适的工具获取信息
3. **观察 (Observation)**: 读取工具返回的结果
4. 重复以上步骤，直到你有足够信息给出最终答案

可用工具：
{tool_descriptions}

当你对当前信息有足够判断时，输出：
**Final Answer**: 你的投资建议

请严格按照以下格式回复：
Thought: <你的思考>
Action: <工具名>
Action Input: <工具参数，JSON 格式>

或者当你得出最终结论时：
Final Answer: <你的结论>
"""

    def __init__(
        self,
        model: str = "gpt-4",
        api_key: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        base_url: Optional[str] = None,
        max_steps: int = 10,
        max_tool_calls_per_step: int = 3,
    ) -> None:
        self._adapter = LLMAdapter(
            model=model,
            api_key=api_key,
            fallback_models=fallback_models or [],
            base_url=base_url,
        )
        self._registry = ToolRegistry()
        self._max_steps = max_steps
        self._max_tool_calls = max_tool_calls_per_step
        self._tool_handlers: dict[str, Callable] = {}

    def register_tool(self, name: str, handler: Callable,
                      description: str = "",
                      parameters: Optional[dict] = None) -> None:
        """注册一个自定义工具。

        Parameters
        ----------
        name : str
            工具名称
        handler : Callable
            工具处理函数，接收关键字参数
        description : str
            工具描述（用于 LLM 理解）
        parameters : dict | None
            JSON Schema 格式的参数定义
        """
        self._registry.register(handler)
        self._tool_handlers[name] = handler

    def register_tools(self, *tools: Callable) -> None:
        """注册多个工具（使用 @tool 装饰器装饰的函数）。"""
        for t in tools:
            self._registry.register(t)
            name = getattr(t, "_tool_definition", None)
            if name is not None:
                self._tool_handlers[name.name] = t  # type: ignore[attr-defined]

    def run(self, query: str, max_steps: Optional[int] = None) -> ReActResult:
        """执行 ReAct 推理循环。

        Parameters
        ----------
        query : str
            用户问题/分析请求
        max_steps : int | None
            覆盖默认最大步数

        Returns
        -------
        ReActResult
        """
        max_steps = max_steps or self._max_steps
        thoughts: list[Thought] = []
        messages: list[dict] = [
            {"role": "system", "content": self._build_system_prompt()},
        ]
        tool_defs = self._registry.to_openai_tools()

        result = ReActResult(final_answer="")
        step = 0
        last_response: Optional[LLMResponse] = None

        while step < max_steps:
            step += 1
            thought = Thought(step=step, thought=query, state=ReActState.THINKING)

            # 1. 调用 LLM
            try:
                response = self._call_llm(messages, tool_defs)
            except Exception as exc:
                thought.state = ReActState.ERROR
                thought.thought = f"LLM call failed: {exc}"
                thoughts.append(thought)
                result.thoughts = thoughts
                result.error = str(exc)
                result.success = False
                return result

            last_response = response
            result.total_tokens += response.usage.get("total_tokens", 0)
            result.model_used = response.model

            # 2. 检查是否有最终答案
            if response.content:
                answer = self._extract_final_answer(response.content)
                if answer:
                    thought.thought = response.content
                    thought.state = ReActState.FINISHED
                    thoughts.append(thought)
                    result.final_answer = answer
                    result.thoughts = thoughts
                    return result

                thought.thought = response.content
                thought.state = ReActState.THINKING
                thoughts.append(thought)

            # 3. 检查是否有工具调用
            if response.has_tool_calls:
                for tc in response.tool_calls:
                    func_info = tc.get("function", {})
                    action_name = func_info.get("name", "")
                    try:
                        action_input = json.loads(func_info.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        action_input = {}

                    thought.action = action_name
                    thought.action_input = action_input

                    # 执行工具
                    obs = self._execute_tool(action_name, action_input)
                    thought.observation = obs
                    thought.state = ReActState.OBSERVING
                    result.tool_calls_made += 1

                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": [
                            {
                                "id": tc.get("id", ""),
                                "function": {
                                    "name": action_name,
                                    "arguments": json.dumps(action_input),
                                },
                            }
                        ],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": obs,
                    })
            else:
                # 既没有答案也没有工具调用 → 追加内容作为进一步思考
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                })

        # 超过最大步数
        thought.thought = f"Reached max steps ({max_steps})"
        thought.state = ReActState.FINISHED
        thoughts.append(thought)
        result.final_answer = (
            f"在 {max_steps} 步内无法得出确定结论。"
            f"当前分析摘要: {last_response.content[:200] if last_response and last_response.content else '无'}"
        )
        result.thoughts = thoughts
        return result

    def _build_system_prompt(self) -> str:
        """构建系统提示词。"""
        tool_defs = self._registry.get_all_definitions()
        tool_descs = "\n".join(
            f"- {t.name}: {t.description} (params: {json.dumps(t.parameters, ensure_ascii=False)})"
            for t in tool_defs
        )
        return self.SYSTEM_PROMPT.format(tool_descriptions=tool_descs)

    def _call_llm(
        self, messages: list[dict], tools: list[dict]
    ) -> LLMResponse:
        """调用 LLM。"""
        return self._adapter.call_with_tools(
            messages=messages,
            tools=tools,
        )

    @staticmethod
    def _extract_final_answer(content: str) -> Optional[str]:
        """从 LLM 响应中提取最终答案。"""
        if "Final Answer:" in content:
            parts = content.split("Final Answer:")
            return parts[-1].strip()
        return None

    def _execute_tool(
        self, tool_name: str, arguments: dict
    ) -> str:
        """执行工具调用。"""
        handler = self._tool_handlers.get(tool_name)
        if handler is None:
            return f"Tool not registered: {tool_name}"
        try:
            result = handler(**arguments)
            return str(result)
        except Exception as exc:
            return f"Tool error: {exc}"

    def _build_messages(self, query: str, history: list[dict]) -> list[dict]:
        """构建消息列表。"""
        return [
            {"role": "system", "content": self._build_system_prompt()},
            *history,
            {"role": "user", "content": query},
        ]

    @property
    def registry(self) -> ToolRegistry:
        """暴露 ToolRegistry 供外部注册工具。"""
        return self._registry
