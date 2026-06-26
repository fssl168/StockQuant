# -*- coding: utf-8 -*-
"""对话记忆管理 — 会话级上下文 + 持久化"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from stockquant.persistence.repository import save_chat_message

logger = logging.getLogger("stockquant.ai")


def _default_db_url() -> str:
    """获取默认数据库 URL，优先从环境变量读取。"""
    return os.environ.get("DATABASE_URL", "sqlite:///:memory:")


class ChatMemory:
    """对话记忆管理。

    管理多个对话会话的上下文，支持内存缓存和持久化存储。

    Parameters
    ----------
    db_url : str | None
        SQLAlchemy 引擎 URL，用于持久化
    max_context : int
        最大上下文消息数（默认 20）
    ttl_hours : int
        会话超时时间（小时，默认 24）
    """

    def __init__(
        self,
        db_url: str | None = None,
        max_context: int = 20,
        ttl_hours: int = 24,
    ) -> None:
        self._db_url = db_url or _default_db_url()
        self._max_context = max_context
        self._ttl_hours = ttl_hours
        # 内存缓存: {conversation_id: list[ChatMessage]}
        self._cache: Dict[str, List[ChatMessage]] = {}

    def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """保存消息到记忆系统。

        Parameters
        ----------
        conversation_id : str
            会话 ID
        role : str
            消息角色 (user/assistant/system)
        content : str
            消息内容
        metadata : dict | None
            附加元数据

        Returns
        -------
        bool
            是否保存成功
        """
        from stockquant.ai.models import ChatMessage as _ChatMessage  # 避免与 ORM 冲突

        msg = _ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )

        # 更新内存缓存
        if conversation_id not in self._cache:
            self._cache[conversation_id] = []
        self._cache[conversation_id].append(msg)

        # 限制缓存大小
        if len(self._cache[conversation_id]) > self._max_context * 2:
            self._cache[conversation_id] = self._cache[conversation_id][-self._max_context:]

        # 持久化
        try:
            save_chat_message(
                engine_url=self._db_url,
                conversation_id=conversation_id,
                role=role,
                content=content,
            )
        except Exception:
            logger.debug("Chat memory persistence failed (non-fatal)")

        return True

    def get_context(
        self,
        conversation_id: str,
        limit: int = 20,
    ) -> List[Dict[str, str]]:
        """获取对话上下文（OpenAI format）。"""
        messages = self._cache.get(conversation_id, [])
        result = messages[-limit:]

        return [
            {"role": m.role, "content": m.content}
            for m in result
        ]

    def get_all_messages(self, conversation_id: str) -> List[Any]:
        """获取会话所有消息。"""
        return self._cache.get(conversation_id, [])

    def clear(self, conversation_id: str) -> bool:
        """清空会话记忆。"""
        if conversation_id in self._cache:
            del self._cache[conversation_id]
        return True

    def cleanup_expired(self) -> int:
        """清理过期会话。"""
        now = datetime.now()
        removed = 0
        for conv_id, msgs in list(self._cache.items()):
            if msgs and (now - msgs[-1].timestamp).total_seconds() > self._ttl_hours * 3600:
                del self._cache[conv_id]
                removed += 1
        return removed


@dataclass
class ChatMessage:
    """对话消息（内存版）"""
    conversation_id: str
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
