# -*- coding: utf-8 -*-
"""F029 FastAPI 应用入口"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from stockquant.api.routers import backtest, strategy, dashboard, monitor, ai_chat, comparison, notification, data, settings, trading, portfolio, optimize
from stockquant.api.websocket import ws_manager

_APP_VERSION = "2.0.0-dev"

logger = logging.getLogger("stockquant.api")

# ------------------------------------------------------------------
# 内存存储（MVP 用，后续换数据库）
# ------------------------------------------------------------------
_backtest_tasks: dict = {}  # task_id -> task dict
_strategies: dict = {}  # strategy_id -> strategy dict
_startup_time: float = time.time()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""

    app = FastAPI(
        title="StockQuant 2.0",
        description="机构级中国 A 股量化交易平台",
        version=_APP_VERSION,
    )

    # CORS 中间件 — MVP 允许全部
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(backtest.router, prefix="/api", tags=["回测"])
    app.include_router(strategy.router, prefix="/api", tags=["策略"])
    app.include_router(dashboard.router, prefix="/api", tags=["仪表盘"])
    app.include_router(monitor.router, prefix="/api", tags=["盯盘"])
    app.include_router(ai_chat.router, prefix="/api", tags=["AI 对话"])
    app.include_router(comparison.router, prefix="/api", tags=["策略对比"])
    app.include_router(notification.router, prefix="/api", tags=["通知"])
    app.include_router(data.router, prefix="/api", tags=["数据管理"])
    app.include_router(settings.router, prefix="/api", tags=["设置"])
    app.include_router(trading.router, prefix="/api", tags=["交易"])
    app.include_router(portfolio.router, prefix="/api", tags=["投资组合"])
    app.include_router(optimize.router, prefix="/api", tags=["参数优化"])

    # WebSocket 端点 — 统一路径 /ws/*
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket 连接入口"""
        await ws_manager.connect(websocket)
        try:
            await websocket.send_json({"type": "connected", "data": {"status": "ok"}})
            while True:
                await websocket.receive_text()
        except Exception:
            pass
        finally:
            await ws_manager.disconnect(websocket)

    @app.websocket("/ws/notification")
    async def notification_ws(websocket: WebSocket):
        """系统通知实时推送"""
        await ws_manager.connect(websocket, "notification")
        try:
            await websocket.send_json({"type": "connected", "data": {"channel": "notification"}})
            while True:
                await websocket.receive_text()
        except Exception:
            pass
        finally:
            await ws_manager.disconnect(websocket, "notification")

    @app.websocket("/ws/monitor")
    async def monitor_ws(websocket: WebSocket):
        """实时告警推送"""
        await ws_manager.connect(websocket, "monitor")
        try:
            await websocket.send_json({"type": "connected", "data": {"channel": "monitor"}})
            while True:
                await websocket.receive_text()
        except Exception:
            pass
        finally:
            await ws_manager.disconnect(websocket, "monitor")

    @app.websocket("/ws/backtest/{task_id}")
    async def backtest_ws(websocket: WebSocket, task_id: str):
        """回测进度实时推送"""
        await ws_manager.connect(websocket, task_id)
        try:
            await websocket.send_json({"type": "connected", "data": {"task_id": task_id}})
            while True:
                await websocket.receive_text()
        except Exception:
            pass
        finally:
            await ws_manager.disconnect(websocket, task_id)

    @app.websocket("/ws/chat/{conversation_id}")
    async def chat_ws(websocket: WebSocket, conversation_id: str):
        """AI 对话实时推送"""
        await ws_manager.connect(websocket, f"chat_{conversation_id}")
        try:
            await websocket.send_json({"type": "connected", "data": {"conversation_id": conversation_id}})
            while True:
                await websocket.receive_text()
        except Exception:
            pass
        finally:
            await ws_manager.disconnect(websocket, f"chat_{conversation_id}")

    # MVP 共享存储注入到路由模块
    backtest.set_storage(_backtest_tasks)
    strategy.set_storage(_strategies)
    dashboard.set_backtest_storage(_backtest_tasks)
    comparison.set_storage(_backtest_tasks)

    # 健康检查
    @app.get("/api/health")
    async def health_check():
        """健康检查"""
        return {
            "status": "ok",
            "version": _APP_VERSION,
            "uptime": round(time.time() - _startup_time, 2),
        }

    logger.info("StockQuant API 网关启动")
    return app


# 模块级存储访问器（供路由模块写入）
def set_backtest_tasks(storage: dict):
    global _backtest_tasks
    _backtest_tasks = storage


def set_strategy_storage(storage: dict):
    global _strategies
    _strategies = storage
