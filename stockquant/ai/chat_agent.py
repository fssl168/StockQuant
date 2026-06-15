# -*- coding: utf-8 -*-
"""F028 AI 自然语言交互界面 — 对话式策略/数据/盯盘 + 工具调用 + 持久化"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Generator, List, Optional

from stockquant.agent.llm_adapter import LLMAdapter
from stockquant.agent.tool_registry import ToolRegistry
from stockquant.agent.react_agent import ReActAgent

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


class ChatMemory:
    """对话持久化 — SQLite 存储"""

    def __init__(self, db_url: str = "sqlite:///./stockquant.db") -> None:
        self._db_url = db_url

    def save_message(self, conversation_id: str, role: str, content: str) -> None:
        """保存单条消息。"""
        try:
            from stockquant.persistence.repository import save_chat_message
            from datetime import datetime
            save_chat_message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                timestamp=datetime.now(),
            )
        except Exception:
            logger.exception("Failed to persist chat message")

    def load_messages(self, conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """加载会话消息历史。"""
        try:
            from stockquant.persistence.repository import get_chat_messages
            return get_chat_messages(conversation_id, limit=limit)
        except Exception:
            logger.exception("Failed to load chat messages")
            return []

    def delete_messages(self, conversation_id: str) -> None:
        """删除会话消息。"""
        try:
            from stockquant.persistence.repository import delete_chat_messages
            delete_chat_messages(conversation_id)
        except Exception:
            logger.exception("Failed to delete chat messages")


class Conversation:
    """对话会话"""

    def __init__(self, conversation_id: str, memory: Optional[ChatMemory] = None) -> None:
        self.conversation_id = conversation_id
        self.messages: List[Dict[str, Any]] = []
        self.created_at: Any = None
        self.updated_at: Any = None
        self._memory = memory

        from datetime import datetime
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

        # 加载历史
        if memory:
            self.messages = memory.load_messages(conversation_id)

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        self.messages.append({"role": role, "content": content, **kwargs})
        self.updated_at = __import__("datetime").datetime.now()
        # 持久化
        if self._memory:
            self._memory.save_message(self.conversation_id, role, content)

    def get_history(self, limit: int = 20) -> List[Dict]:
        return self.messages[-limit:]


class ChatAgent:
    """F028 AI 自然语言交互界面。

    对话式策略开发、数据分析、回测报告解读、盯盘配置。
    使用 ReActAgent + ToolRegistry 实现工具调用。

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
    db_url : str | None
        SQLite 数据库 URL
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        base_url: Optional[str] = None,
        db_url: Optional[str] = None,
    ) -> None:
        self._adapter = LLMAdapter(
            model=model,
            api_key=api_key,
            fallback_models=fallback_models or [],
            base_url=base_url,
        )
        self._conversations: Dict[str, Conversation] = {}
        self._tool_registry = ToolRegistry()
        self._memory = ChatMemory(db_url=db_url) if db_url else None

    def _ensure_conversation(self, conversation_id: str) -> Conversation:
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = Conversation(
                conversation_id=conversation_id,
                memory=self._memory,
            )
        return self._conversations[conversation_id]

    def register_tool(self, tool_fn: Any) -> None:
        """注册对话工具。"""
        self._tool_registry.register(tool_fn)

    def chat(
        self,
        message: str,
        conversation_id: str = "default",
        model: Optional[str] = None,
    ) -> str:
        """发送消息并获取 AI 回复（通过 ReActAgent + 工具调用）。"""
        conv = self._ensure_conversation(conversation_id)
        conv.add_message("user", message)

        history = conv.get_history(limit=15)
        history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

        # 通过 ReActAgent 执行工具调用
        try:
            from stockquant.agent.react_agent import ReActAgent

            react = ReActAgent(
                llm_adapter=self._adapter,
                tool_registry=self._tool_registry,
                max_steps=5,
            )

            result = react.run(message)
            reply = result.final_response if result.final_response else result.content or "抱歉，我没有收到有效回复。"
            conv.add_message("assistant", reply)
            return reply

        except ImportError:
            # 降级：直接调用 LLM（无工具）
            logger.warning("ReActAgent not available, falling back to direct LLM call")
            return self._chat_fallback(message, conversation_id, model)
        except Exception as exc:
            error_msg = f"AI 调用失败: {exc}"
            conv.add_message("assistant", error_msg)
            logger.error("Chat failed for conversation %s: %s", conversation_id, exc)
            return error_msg

    def _chat_fallback(
        self,
        message: str,
        conversation_id: str,
        model: Optional[str] = None,
    ) -> str:
        """降级模式：直接调用 LLM，不通过 ReActAgent。"""
        conv = self._conversations.get(conversation_id)
        if conv is None:
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
            if self._memory:
                self._memory.delete_messages(conversation_id)
            return True
        return False
