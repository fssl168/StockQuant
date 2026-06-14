# -*- coding: utf-8 -*-
"""F029 WebSocket 连接管理器 — 实时推送"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger("stockquant.api")


class WebSocketManager:
    """WebSocket 连接管理器。

    支持广播到所有客户端、向特定任务推送消息。
    消息格式: {"type": "progress|metrics|trade|alert", "data": {...}, "task_id": "..."}
    """

    def __init__(self):
        # task_id -> Set[WebSocket]
        self._connections: Dict[str, Set[WebSocket]] = {}
        # 全局广播连接
        self._global_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, task_id: Optional[str] = None) -> None:
        """连接 WebSocket"""
        await websocket.accept()
        if task_id:
            self._connections.setdefault(task_id, set()).add(websocket)
            logger.info(f"WebSocket 连接: task={task_id}, 当前连接数={len(self._connections[task_id])}")
        else:
            self._global_connections.add(websocket)
            logger.info(f"WebSocket 全局连接, 当前连接数={len(self._global_connections)}")

    async def disconnect(self, websocket: WebSocket, task_id: Optional[str] = None) -> None:
        """断开 WebSocket"""
        if task_id and task_id in self._connections:
            self._connections[task_id].discard(websocket)
            if not self._connections[task_id]:
                del self._connections[task_id]
        else:
            self._global_connections.discard(websocket)
        logger.info(f"WebSocket 断开: task={task_id}")

    async def broadcast(self, message: dict, task_id: Optional[str] = None) -> None:
        """广播消息到指定任务的客户端"""
        if task_id:
            targets = list(self._connections.get(task_id, set()))
        else:
            targets = list(self._global_connections)

        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                # 连接已断开时清理
                await self.disconnect(ws, task_id)

    async def push(self, msg_type: str, data: dict, task_id: Optional[str] = None) -> None:
        """推送一条格式化的 WebSocket 消息"""
        message = {
            "type": msg_type,
            "data": data,
            "task_id": task_id,
        }
        await self.broadcast(message, task_id)

    def get_connection_count(self, task_id: Optional[str] = None) -> int:
        """获取连接数"""
        if task_id:
            return len(self._connections.get(task_id, set()))
        return len(self._global_connections)


# 全局单例
ws_manager = WebSocketManager()
