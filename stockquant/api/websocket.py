# -*- coding: utf-8 -*-
"""F029 WebSocket 连接管理器 — 实时推送"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Set

from fastapi import WebSocket
from jose import jwt, JWTError

from stockquant.config import get_config

logger = logging.getLogger("stockquant.api")

# JWT 配置
_SECRET = get_config()
SECRET_KEY = _SECRET.get_jwt_secret()
ALGORITHM = "HS256"


def _verify_token(token: str) -> Optional[dict]:
    """验证 JWT token，返回 payload 或 None"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


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
        # 存储已验证的用户信息
        self._authenticated: Dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket, task_id: Optional[str] = None, token: Optional[str] = None) -> bool:
        """连接 WebSocket
        
        Args:
            websocket: WebSocket 连接
            task_id: 可选的任务 ID，用于任务级别推送
            token: 可选的 JWT token，用于认证
            
        Returns:
            True 表示连接成功并已认证，False 表示认证失败需要关闭
        """
        # 如果提供了 token，验证它
        if token:
            payload = _verify_token(token)
            if payload is None:
                logger.warning(f"WebSocket 认证失败: 无效的 token")
                await websocket.close(code=4001, reason="Invalid token")
                return False
            # 存储认证信息
            self._authenticated[websocket] = payload
            logger.info(f"WebSocket 已认证: user={payload.get('sub')}, task={task_id}")
        else:
            # 无 token 的连接视为匿名连接，仅允许特定操作
            logger.info(f"WebSocket 匿名连接: task={task_id}")
        
        await websocket.accept()
        
        if task_id:
            self._connections.setdefault(task_id, set()).add(websocket)
            logger.info(f"WebSocket 连接: task={task_id}, 当前连接数={len(self._connections[task_id])}")
        else:
            self._global_connections.add(websocket)
            logger.info(f"WebSocket 全局连接, 当前连接数={len(self._global_connections)}")
        
        return True

    async def disconnect(self, websocket: WebSocket, task_id: Optional[str] = None) -> None:
        """断开 WebSocket"""
        if task_id and task_id in self._connections:
            self._connections[task_id].discard(websocket)
            if not self._connections[task_id]:
                del self._connections[task_id]
        else:
            self._global_connections.discard(websocket)
        
        # 清理认证信息
        self._authenticated.pop(websocket, None)
        
        logger.info(f"WebSocket 断开: task={task_id}")

    async def broadcast(self, message: dict, task_id: Optional[str] = None) -> None:
        """广播消息到指定的客户终端"""
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
    
    def get_user(self, websocket: WebSocket) -> Optional[dict]:
        """获取 WebSocket 对应的已认证用户"""
        return self._authenticated.get(websocket)


# 全局单例
ws_manager = WebSocketManager()
