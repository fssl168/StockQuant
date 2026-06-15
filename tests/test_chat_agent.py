# -*- coding: utf-8 -*-
"""F028 ChatAgent 单元测试"""

import json
from unittest.mock import MagicMock, patch

import pytest

from stockquant.ai.chat_agent import ChatAgent, Conversation, ChatMemory


class TestChatMemory:
    """测试对话持久化 — 由于 get_chat_messages/delete_chat_messages 可能不存在，
    所有操作应静默失败（try/except 捕获异常）"""

    def test_save_message_noop(self):
        """save_message 静默处理异常"""
        mem = ChatMemory()
        mem.save_message("c1", "user", "hello")  # should not raise

    def test_load_messages_noop(self):
        """load_messages 静默处理异常"""
        mem = ChatMemory()
        msgs = mem.load_messages("c1")
        assert isinstance(msgs, list)

    def test_delete_messages_noop(self):
        """delete_messages 静默处理异常"""
        mem = ChatMemory()
        mem.delete_messages("c1")  # should not raise


class TestConversation:
    """测试对话会话"""

    def test_add_message(self):
        conv = Conversation("c1")
        conv.add_message("user", "hello")
        assert len(conv.messages) == 1
        assert conv.messages[0]["role"] == "user"

    def test_get_history(self):
        conv = Conversation("c1")
        for i in range(10):
            conv.add_message("user", f"msg {i}")
            conv.add_message("assistant", f"reply {i}")
        history = conv.get_history(5)
        assert len(history) == 5

    def test_persistence(self):
        with patch.object(ChatMemory, 'load_messages', return_value=[{"role": "system", "content": "hi"}]):
            with patch.object(ChatMemory, 'save_message'):
                mem = ChatMemory()
                conv = Conversation("c1", memory=mem)
                assert len(conv.messages) == 1  # loaded from memory


class TestChatAgentBasic:
    """测试 ChatAgent 基础功能"""

    def test_init(self):
        agent = ChatAgent()
        assert agent._tool_registry is not None
        assert len(agent._conversations) == 0

    def test_ensure_conversation(self):
        agent = ChatAgent()
        conv = agent._ensure_conversation("c1")
        assert conv.conversation_id == "c1"
        assert "c1" in agent._conversations

    def test_clear_conversation(self):
        agent = ChatAgent()
        agent._ensure_conversation("c1")
        assert agent.clear_conversation("c1") is True
        assert "c1" not in agent._conversations
        assert agent.clear_conversation("nonexistent") is False

    def test_get_all_conversations(self):
        agent = ChatAgent()
        agent._ensure_conversation("c1")
        agent._ensure_conversation("c2")
        ids = agent.get_all_conversations()
        assert set(ids) == {"c1", "c2"}

    def test_get_conversation_empty(self):
        agent = ChatAgent()
        msgs = agent.get_conversation("nonexistent")
        assert msgs == []

    def test_chat_fallback_error(self):
        """LLM 调用失败时返回错误信息"""
        with patch.object(ChatAgent, '_chat_fallback', return_value="AI 调用失败: test"):
            agent = ChatAgent()
            result = agent.chat("hello", conversation_id="c1")
            assert "失败" in result
