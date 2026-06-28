# -*- coding: utf-8 -*-
"""F029 FastAPI 应用入口"""

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

# 最早加载 .env 文件，使所有配置生效
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)
except ImportError:
    pass

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from stockquant.api.routers import backtest, strategy, dashboard, monitor, ai_chat, comparison, notification, data, settings, trading, portfolio, optimize
from stockquant.data.service import DataService
from stockquant.ai.service import AIService
from stockquant.api.routers import auth as auth_router
from stockquant.api.routers import signal as signal_router
from stockquant.api.routers import scheduler as scheduler_router
from stockquant.api.routers import audit as audit_router
from stockquant.api.routers import monitoring as monitoring_router
from stockquant.api.routers import memory as memory_router
from stockquant.api.routers import hallucination as hallucination_router
from stockquant.api.routers import pipeline as pipeline_router
# F020 GAP-M5/M6/M7/L2：4 个新 API 路由（管线调度器/采集审计/反幻觉验证/用户风险偏好）
from stockquant.api.routers import pipeline_scheduler as pipeline_scheduler_router
from stockquant.api.routers import pipeline_audit as pipeline_audit_router
from stockquant.api.routers import hallucination_verify as hallucination_verify_router
from stockquant.api.routers import profiling as profiling_router
# 三角色前端重构：用户管理 API
from stockquant.api.routers import user_admin as user_admin_router
from stockquant.api.websocket import ws_manager
from stockquant.config import get_config

# ------------------------------------------------------------------
# 持久化存储（使用数据库）
# ------------------------------------------------------------------
from stockquant.persistence.persistent_store import (
    BacktestTaskStore,
    StrategyStore,
    CollectTaskStore,
    OptimizeTaskStore,
    ComparisonHistoryStore,
    OrderAuditStore,
)

USE_RATE_LIMIT = False
_APP_VERSION = "2.0.0-dev"
logger = logging.getLogger("stockquant.api")

_backtest_tasks: dict = BacktestTaskStore()  # task_id -> task dict
_strategies: dict = StrategyStore()  # strategy_id -> strategy dict
_collect_tasks: dict = CollectTaskStore()  # task_id -> task dict
_optimize_tasks: dict = OptimizeTaskStore()  # task_id -> task dict
_comparison_history: list = ComparisonHistoryStore()  # strategy comparison history
_pending_limit_orders: dict = {}  # order_id -> Order (in-memory only)
_orders_audit: dict = OrderAuditStore()  # order_id -> audit dict
_startup_time: float = time.time()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""

    # lifespan: 启动/停止 PipelineScheduler（F020 GAP-H3 修复）
    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        try:
            from stockquant.ai.scheduler import get_scheduler
            scheduler = get_scheduler()
            try:
                await scheduler.start()
                logger.info("PipelineScheduler 已启动")
            except Exception as exc:
                logger.warning("PipelineScheduler 启动失败（不阻塞主应用）: %s", exc)
            yield
            try:
                await scheduler.stop()
                logger.info("PipelineScheduler 已停止")
            except Exception as exc:
                logger.warning("PipelineScheduler 停止失败: %s", exc)
        except ImportError:
            logger.debug("PipelineScheduler 模块未安装，跳过启动")
            yield

    app = FastAPI(
        title="StockQuant 2.0",
        description="机构级中国 A 股量化交易平台",
        version=_APP_VERSION,
        lifespan=_lifespan,
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
    app.include_router(auth_router.router, prefix="/api")
    app.include_router(signal_router.router, prefix="/api", tags=["信号管线"])
    app.include_router(scheduler_router.router, prefix="/api", tags=["调度器"])

    # 注册审计日志和监控端点
    app.include_router(audit_router.router, prefix="/api", tags=["审计日志"])
    app.include_router(monitoring_router.router, prefix="", tags=["监控"])

    # 注册 AI 基础设施端点
    app.include_router(memory_router.router, prefix="/api", tags=["记忆系统"])
    app.include_router(hallucination_router.router, prefix="/api", tags=["反幻觉系统"])
    app.include_router(pipeline_router.router, prefix="/api", tags=["AI 信息管线"])

    # F020 GAP-M5/M6/M7/L2：注册 4 个新 API 路由
    app.include_router(pipeline_scheduler_router.router, prefix="/api", tags=["管线调度器"])
    app.include_router(pipeline_audit_router.router, prefix="/api", tags=["采集审计日志"])
    app.include_router(hallucination_verify_router.router, prefix="/api", tags=["反幻觉验证"])
    app.include_router(profiling_router.router, prefix="/api", tags=["用户风险偏好"])
    # 三角色前端重构：用户管理
    app.include_router(user_admin_router.router, prefix="/api", tags=["用户管理 (ADMIN)"])

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

    def _now_iso() -> str:
        """返回当前 UTC 时间的 ISO8601 字符串"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    async def _handle_rejoin(websocket: WebSocket, since: str | None, subscriptions: dict[str, str]):
        """补全断线期间数据：根据 since 时间戳查询历史行情并推送

        策略：
        1. 若有订阅 symbol，查询每个 symbol 自 since 以来的 K 线数据
        2. 推送一条 {type: "rejoin_data", data: {...}} 消息
        3. 若无 since 或查询失败，推送空数据 + ack
        """
        try:
            from datetime import datetime, timezone
            from stockquant.api.routers.trading import _get_latest_bar

            # 确定要补全的 symbol 列表
            rejoin_symbols = list(subscriptions.keys())
            if not rejoin_symbols:
                # 无订阅时使用默认自选股
                from stockquant.api.routers.monitor import _watchlist
                rejoin_symbols = list(_watchlist) if _watchlist else ["sh600519", "sz000858"]

            rejoin_data = {}
            for sym in rejoin_symbols[:10]:
                try:
                    bar = _get_latest_bar(sym)
                    if bar:
                        rejoin_data[sym] = {
                            "price": bar.close,
                            "change": round((bar.close - bar.open) / bar.open * 100, 2) if bar.open > 0 else 0,
                            "timestamp": _now_iso(),
                        }
                except Exception:
                    pass

            await websocket.send_json({
                "type": "rejoin_data",
                "data": rejoin_data,
                "since": since,
                "completed_at": _now_iso(),
            })
        except Exception as e:
            await websocket.send_json({
                "type": "rejoin_error",
                "error": str(e),
            })

    @app.websocket("/ws/monitor")
    async def monitor_ws(websocket: WebSocket):
        """实时行情推送 — 连接后定时推送自选股行情

        支持的客户端消息：
        - {"type":"subscribe","symbol":"sh600519","mode":"tick"}  切换逐笔模式
        - {"type":"unsubscribe","symbol":"sh600519"}              取消逐笔
        - {"type":"rejoin","since":"<ISO8601>"}                   补全断线期间数据
        """
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
        tick_task = None
        # 客户端订阅状态：symbol -> mode ('tick' | 'bar')
        subscriptions: dict[str, str] = {}
        try:
            await websocket.send_json({"type": "connected", "data": {"channel": "monitor"}})

            import asyncio

            async def _push_quotes():
                """后台任务：每 5 秒推送自选股行情（Bar 模式，默认）"""
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

            async def _push_ticks():
                """后台任务：逐笔级推送（Tick 模式），每 1 秒推送订阅的 symbol

                仅推送 subscriptions 中 mode='tick' 的 symbol，避免高频推送全量股票。
                """
                while True:
                    try:
                        await asyncio.sleep(1)
                        tick_subs = [s for s, m in subscriptions.items() if m == "tick"]
                        if not tick_subs:
                            continue
                        from stockquant.api.routers.trading import _get_latest_bar
                        quotes_dict = {}
                        for sym in tick_subs[:10]:  # 限制 10 只
                            try:
                                bar = _get_latest_bar(sym)
                                if bar:
                                    quotes_dict[sym] = {
                                        "price": bar.close,
                                        "change": round((bar.close - bar.open) / bar.open * 100, 2) if bar.open > 0 else 0,
                                        "timestamp": _now_iso(),
                                    }
                            except Exception:
                                pass
                        if quotes_dict:
                            await websocket.send_json({"type": "tick", "data": quotes_dict})
                    except Exception:
                        break

            push_task = asyncio.create_task(_push_quotes())
            tick_task = asyncio.create_task(_push_ticks())

            # 主循环：解析客户端消息
            while True:
                raw = await websocket.receive_text()
                try:
                    import json
                    msg = json.loads(raw)
                    msg_type = msg.get("type")

                    if msg_type == "subscribe":
                        # {"type":"subscribe","symbol":"sh600519","mode":"tick"}
                        sym = msg.get("symbol")
                        mode = msg.get("mode", "bar")
                        if sym:
                            subscriptions[sym] = mode
                            await websocket.send_json({
                                "type": "subscribe_ack",
                                "data": {"symbol": sym, "mode": mode},
                            })

                    elif msg_type == "unsubscribe":
                        # {"type":"unsubscribe","symbol":"sh600519"}
                        sym = msg.get("symbol")
                        if sym and sym in subscriptions:
                            del subscriptions[sym]
                            await websocket.send_json({
                                "type": "unsubscribe_ack",
                                "data": {"symbol": sym},
                            })

                    elif msg_type == "rejoin":
                        # {"type":"rejoin","since":"2026-06-28T10:00:00Z"}
                        since = msg.get("since")
                        await _handle_rejoin(websocket, since, subscriptions)

                except json.JSONDecodeError:
                    # 非 JSON 消息，忽略
                    continue
                except Exception:
                    # 其他错误，继续循环
                    continue
        except Exception:
            pass
        finally:
            if push_task:
                push_task.cancel()
            if tick_task:
                tick_task.cancel()
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
    get_config()
    logger.info("应用配置已加载")

    # --- Unified Data Service ---
    try:
        data_svc = DataService()
        app.state.data_service = data_svc
        logger.info("DataService 已初始化")
        data.set_data_service(data_svc)
        from stockquant.api.routers import settings as _settings_router
        _settings_router.set_data_service(data_svc)
        monitor.set_data_service(data_svc)
        trading.set_data_service(data_svc)
    except Exception as e:
        logger.warning("DataService 初始化失败（非致命）: %s", e)
        app.state.data_service = None

    # --- Unified AI Service ---
    try:
        ai_svc = AIService()
        app.state.ai_service = ai_svc
        logger.info("AIService 已初始化: enabled=%s", ai_svc.is_configured)
    except Exception as e:
        logger.warning("AIService 初始化失败（非致命）: %s", e)
        app.state.ai_service = None

    # 初始化 AI Agent Orchestrator
    try:
        from stockquant.ai.orchestrator import init_orchestrator
        orch = init_orchestrator()
        app.state.orchestrator = orch
        logger.info("AI Agent Orchestrator 已初始化: %s", orch.registered_agents)
    except Exception as e:
        logger.warning("Orchestrator 初始化失败（非致命）: %s", e)

    # 初始化记忆系统（如果 PostgreSQL 不可用则降级）
    _memory_system = None
    try:
        from stockquant.ai.memory.system import MemorySystem
        _memory_system = MemorySystem()
        memory_router.init_memory(_memory_system)
        logger.info("记忆系统已初始化 (L1=in-memory, L2/L3=%s)", "PostgreSQL" if "pgvector" in str(_memory_system.l2.__class__.__module__) else "fallback")
    except ImportError as e:
        logger.warning("记忆系统未安装（非致命）: %s", e)
    except Exception as e:
        logger.warning("记忆系统初始化失败（降级为 SQLite）: %s", e)

    # 初始化反幻觉数据库
    try:
        from stockquant.ai.hallucination.database import HallucinationDatabase
        hallucination_db = HallucinationDatabase()
        hallucination_router.init_database(hallucination_db)
        logger.info("反幻觉数据库已初始化")
    except Exception as e:
        logger.warning("反幻觉数据库初始化失败（非致命）: %s", e)

    # 初始化 AI 信息管线
    try:
        from stockquant.ai.pipeline_orchestrator import InformationProcessingPipeline
        if _memory_system is not None:
            pipeline = InformationProcessingPipeline(memory=_memory_system)
        else:
            pipeline = InformationProcessingPipeline()
        pipeline_router.init_pipeline(pipeline)
        logger.info("AI 信息管线已初始化")

        # F020 GAP-H3：将 pipeline 绑定到 PipelineScheduler，实现自动调度
        try:
            from stockquant.ai.scheduler import get_scheduler, ScheduleSpec
            scheduler = get_scheduler()
            # pipeline.run 是同步方法，包装为协程以适配 scheduler.bind_pipeline
            async def _pipeline_runner(symbols):
                return pipeline.run(symbols)
            scheduler.bind_pipeline(_pipeline_runner)
            # 注入默认调度任务（首次启动时）
            if not scheduler.list_tasks():
                scheduler.add_task(ScheduleSpec(
                    name="realtime_news",
                    level="realtime",
                    interval_seconds=300,  # 5 分钟（避免过频）
                    symbols=["sh600519", "sz000858"],
                ))
            logger.info("PipelineScheduler 已绑定 AI 信息管线")
        except Exception as exc:
            logger.warning("PipelineScheduler 绑定 pipeline 失败（非致命）: %s", exc)
    except Exception as e:
        logger.warning("AI 信息管线初始化失败（非致命）: %s", e)

    # 从 Redis 加载自选股列表
    try:
        from stockquant.api.routers.monitor import _load_watchlist_from_redis
        _load_watchlist_from_redis()
        logger.info("自选股列表已从 Redis 加载")
    except Exception as e:
        logger.warning("自选股加载失败（非致命）: %s", e)

    return app


# 模块级 app 实例（供 uvicorn stockquant.api.main:app 加载）
app = create_app()


# 模块级存储访问器（供路由模块写入）
def set_backtest_tasks(storage: dict):
    global _backtest_tasks
    _backtest_tasks = storage


def set_strategy_storage(storage: dict):
    global _strategies
    _strategies = storage
