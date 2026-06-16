# -*- coding: utf-8 -*-
"""F029 通知推送路由 — WebSocket 实时通知"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from stockquant.api.websocket import ws_manager

logger = logging.getLogger("stockquant.api.notification")

router = APIRouter()


@router.websocket("/ws/notification")
async def notification_ws(websocket: WebSocket):
    """系统通知实时推送"""
    await ws_manager.connect(websocket, "notification")
    try:
        await websocket.send_json({"type": "connected", "data": {"channel": "notification"}})
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(websocket, "notification")
