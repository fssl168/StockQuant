# -*- coding: utf-8 -*-
"""F028 AI 自然语言交互界面 — 对话式策略/数据/盯盘"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Generator, List, Optional

from stockquant.agent.llm_adapter import LLMAdapter

logger = logging.getLogger("stockquant.ai")


SYSTEM_PROMPT = """你是 StockQuant 量化交易助手，专注于中国 A 股市场。

你的能力包括：
1. 策略开发：根据自然语言描述生成 BaseStrategy 代码
2. 数据分析：查询市场数据、板块表现、个股走势
3. 回测解读：分析回测结果，解释盈亏原因
4. 盯盘配置：帮助用户设置自选股和监控条件
5. 交易建议：基于技术指标和市场面给出参考建议

回答规范：
- 使用中文回答
- 涉及数据时给出具体数值
- 涉及代码时用 markdown code block 包裹
- 涉及风险提示时明确指出
- 简洁专业，避免废话
"""


class Conversation:
    """对话会话"""

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        self.messages: List[Dict[str, Any]] = []
        self.created_at: Any = None
        self.updated_at: Any = None

        from datetime import datetime
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        self.messages.append({"role": role, "content": content, **kwargs})
        self.updated_at = __import__("datetime").datetime.now()

    def get_history(self, limit: int = 20) -> List[Dict]:
        return self.messages[-limit:]


class ChatAgent:
    """F028 AI 自然语言交互界面。

    对话式策略开发、数据分析、回测报告解读、盯盘配置。

    Parameters
    ----------
    model : str
        LLM 模型名称
    api_key : str | None
        API Key
    fallback_models : list[str] | None
        回退模型列表
    base_url : str | None
        API 基础 URL
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._adapter = LLMAdapter(
            model=model,
            api_key=api_key,
            fallback_models=fallback_models or [],
            base_url=base_url,
        )
        self._conversations: Dict[str, Conversation] = {}

    def _ensure_conversation(self, conversation_id: str) -> Conversation:
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = Conversation(
                conversation_id=conversation_id,
            )
        return self._conversations[conversation_id]

    def chat(
        self,
        message: str,
        conversation_id: str = "default",
        model: Optional[str] = None,
    ) -> str:
        """发送消息并获取 AI 回复。

        Parameters
        ----------
        message : str
            用户消息
        conversation_id : str
            会话 ID，用于保持上下文
        model : str | None
            可选的模型覆盖

        Returns
        -------
        str
            AI 回复内容
        """
        conv = self._ensure_conversation(conversation_id)
        conv.add_message("user", message)

        history = conv.get_history(limit=15)
        history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

        try:
            response = self._adapter.call(
                messages=history,
                model=model,
                temperature=0.3,
                max_tokens=2048,
            )
            reply = response.content or "抱歉，我没有收到有效回复。"
            conv.add_message("assistant", reply)
            return reply

        except Exception as exc:
            error_msg = f"AI 调用失败: {exc}"
            conv.add_message("assistant", error_msg)
            logger.error("Chat failed for conversation %s: %s", conversation_id, exc)
            return error_msg

    def chat_stream(
        self,
        message: str,
        conversation_id: str = "default",
    ) -> Generator[str, None, None]:
        """流式对话（SSE 兼容）。"""
        conv = self._ensure_conversation(conversation_id)
        conv.add_message("user", message)

        history = conv.get_history(limit=15)
        history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

        try:
            response = self._adapter.call(
                messages=history,
                temperature=0.3,
                max_tokens=2048,
            )
            reply = response.content or ""
            conv.add_message("assistant", reply)
            yield f"data: {json.dumps({'type': 'message', 'content': reply}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            error_msg = f"AI 调用失败: {exc}"
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    def get_conversation(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        """获取会话消息历史"""
        conv = self._conversations.get(conversation_id)
        if conv is None:
            return []
        return conv.messages[-limit:]

    def get_all_conversations(self) -> List[str]:
        """获取所有会话 ID"""
        return list(self._conversations.keys())

    def clear_conversation(self, conversation_id: str) -> bool:
        """清空会话"""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            return True
        return False
