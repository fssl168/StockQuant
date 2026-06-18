# -*- coding: utf-8 -*-
"""F029 FastAPI 应用入口"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

# 最早加载 .env 文件，使所有配置生效
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)
except ImportError:
    pass

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

USE_RATE_LIMIT = False

from stockquant.api.routers import backtest, strategy, dashboard, monitor, ai_chat, comparison, notification, data, settings, trading, portfolio, optimize
from stockquant.api.routers import auth as auth_router
from stockquant.api.routers import signal as signal_router
from stockquant.api.routers import scheduler as scheduler_router
from stockquant.api.websocket import ws_manager
from stockquant.config import get_config, reload_config

_APP_VERSION = "2.0.0-dev"

logger = logging.getLogger("stockquant.api")

# ------------------------------------------------------------------
# 持久化存储（使用数据库）
# ------------------------------------------------------------------
from stockquant.persistence.persistent_store import (
    BacktestTaskStore,
    StrategyStore,
    CollectTaskStore,
    OptimizeTaskStore,
    ComparisonHistoryStore,
    PendingOrderStore,
    OrderAuditStore,
)

_backtest_tasks: dict = BacktestTaskStore()  # task_id -> task dict
_strategies: dict = StrategyStore()  # strategy_id -> strategy dict
_collect_tasks: dict = CollectTaskStore()  # task_id -> task dict
_optimize_tasks: dict = OptimizeTaskStore()  # task_id -> task dict
_comparison_history: list = ComparisonHistoryStore()  # strategy comparison history
_pending_limit_orders: dict = PendingOrderStore()  # order_id -> Order
_orders_audit: dict = OrderAuditStore()  # order_id -> audit dict
_startup_time: float = time.time()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""

    app = FastAPI(
        title="StockQuant 2.0",
        description="机构级中国 A 股量化交易平台",
        version=_APP_VERSION,
    )

    # CORS 中间件 — 从环境变量 CORS_ORIGINS 读取允许的源（逗号分隔）
    _cors_env = os.environ.get("CORS_ORIGINS", "").strip()
    if _cors_env == "*":
        _cors_origins = ["*"]
        _cors_credentials = False
    elif _cors_env:
        _cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
        _cors_credentials = True
    else:
        _cors_origins = ["http://localhost:5173", "http://localhost:3000", "http://localhost:80"]
        _cors_credentials = True

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=_cors_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 速率限制（已禁用，避免 Windows GBK 编码问题）
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
    app.include_router(auth_router.router, prefix="/api", tags=["认证"])
    app.include_router(signal_router.router, prefix="/api", tags=["信号管线"])
    app.include_router(scheduler_router.router, prefix="/api", tags=["调度器"])

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
        token = websocket.query_params.get("token")
        if token:
            try:
                from jose import jwt
                from stockquant.api.deps import SECRET_KEY, ALGORITHM
                jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            except Exception:
                await websocket.close(code=4001, reason="invalid token")
                return
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
        """实时行情推送 — 连接后定时推送自选股行情"""
        token = websocket.query_params.get("token")
        if token:
            try:
                from jose import jwt
                from stockquant.api.deps import SECRET_KEY, ALGORITHM
                jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            except Exception:
                await websocket.close(code=4001, reason="invalid token")
                return
        await ws_manager.connect(websocket, "monitor")
        push_task = None
        try:
            await websocket.send_json({"type": "connected", "data": {"channel": "monitor"}})

            import asyncio
            from datetime import time as dt_time

            async def _push_quotes():
                """后台任务：每 5 秒推送自选股行情"""
                while True:
                    try:
                        await asyncio.sleep(5)
                        # 获取自选股列表
                        from stockquant.api.routers.monitor import _watchlist
                        symbols = list(_watchlist) if _watchlist else ["sh600519", "sz000858"]
                        quotes = []
                        for sym in symbols[:10]:  # 最多 10 只
                            try:
                                from stockquant.api.routers.trading import _get_latest_bar
                                bar = _get_latest_bar(sym)
                                if bar:
                                    quotes.append({
                                        "symbol": sym,
                                        "price": bar.close,
                                        "open": bar.open,
                                        "high": bar.high,
                                        "low": bar.low,
                                        "volume": bar.volume,
                                        "change_pct": round((bar.close - bar.open) / bar.open * 100, 2) if bar.open > 0 else 0,
                                    })
                            except Exception:
                                pass
                        if quotes:
                            # 转换为对象格式 {symbol: {price, change}} 供前端使用
                            quotes_dict = {}
                            for q in quotes:
                                quotes_dict[q["symbol"]] = {
                                    "price": q["price"],
                                    "change": q["change_pct"],
                                }
                            await websocket.send_json({"type": "quote", "data": quotes_dict})
                    except Exception:
                        break

            push_task = asyncio.create_task(_push_quotes())

            while True:
                await websocket.receive_text()
        except Exception:
            pass
        finally:
            if push_task:
                push_task.cancel()
            await ws_manager.disconnect(websocket, "monitor")

    @app.websocket("/ws/backtest/{task_id}")
    async def backtest_ws(websocket: WebSocket, task_id: str):
        """回测进度实时推送"""
        token = websocket.query_params.get("token")
        if token:
            try:
                from jose import jwt
                from stockquant.api.deps import SECRET_KEY, ALGORITHM
                jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            except Exception:
                await websocket.close(code=4001, reason="invalid token")
                return
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
        token = websocket.query_params.get("token")
        if token:
            try:
                from jose import jwt
                from stockquant.api.deps import SECRET_KEY, ALGORITHM
                jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            except Exception:
                await websocket.close(code=4001, reason="invalid token")
                return
        await ws_manager.connect(websocket, f"chat_{conversation_id}")
        try:
            await websocket.send_json({"type": "connected", "data": {"conversation_id": conversation_id}})
            while True:
                await websocket.receive_text()
        except Exception:
            pass
        finally:
            await ws_manager.disconnect(websocket, f"chat_{conversation_id}")

    @app.websocket("/ws/optimize/{task_id}")
    async def optimize_ws(websocket: WebSocket, task_id: str):
        """参数优化进度实时推送"""
        token = websocket.query_params.get("token")
        if token:
            try:
                from jose import jwt
                from stockquant.api.deps import SECRET_KEY, ALGORITHM
                jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            except Exception:
                await websocket.close(code=4001, reason="invalid token")
                return
        await ws_manager.connect(websocket, task_id)
        try:
            await websocket.send_json({"type": "connected", "data": {"task_id": task_id}})
            while True:
                await websocket.receive_text()
        except Exception:
            pass
        finally:
            await ws_manager.disconnect(websocket, task_id)

    # 共享存储注入到路由模块
    backtest.set_storage(_backtest_tasks)
    strategy.set_storage(_strategies)
    dashboard.set_backtest_storage(_backtest_tasks)
    comparison.set_storage(_backtest_tasks, _comparison_history)
    optimize.set_storage(_optimize_tasks)
    data.set_storage(_collect_tasks)
    trading.set_storage(_pending_limit_orders, _orders_audit)

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

    # 加载 YAML 配置
    config = get_config()
    logger.info("应用配置已加载")

    # 初始化 AI Agent Orchestrator
    try:
        from stockquant.ai.orchestrator import init_orchestrator
        orch = init_orchestrator()
        app.state.orchestrator = orch
        logger.info("AI Agent Orchestrator 已初始化: %s", orch.registered_agents)
    except Exception as e:
        logger.warning("Orchestrator 初始化失败（非致命）: %s", e)

    # 从 Redis 加载自选股列表
    try:
        from stockquant.api.routers.monitor import _load_watchlist_from_redis
        _load_watchlist_from_redis()
        logger.info("自选股列表已从 Redis 加载")
    except Exception as e:
        logger.warning("自选股加载失败（非致命）: %s", e)

    return app


# 模块级 ASGI 实例（供 uvicorn stockquant.api.main:app 使用）
app = create_app()


# 模块级存储访问器（供路由模块写入）
def set_backtest_tasks(storage: dict):
    global _backtest_tasks
    _backtest_tasks = storage


def set_strategy_storage(storage: dict):
    global _strategies
    _strategies = storage
