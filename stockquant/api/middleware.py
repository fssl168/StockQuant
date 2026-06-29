# -*- coding: utf-8 -*-
"""F029/F019 中间件 — RequireAuth + AuditLog + RateLimit + ExceptionHandler"""

from __future__ import annotations

import json
import logging
import time
import traceback
import uuid
from collections import defaultdict
from threading import Lock
from typing import Optional

from fastapi import Request
from fastapi import HTTPException as FastAPIHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse

from stockquant.api.deps import decode_token

logger = logging.getLogger("stockquant.middleware")

# 不需要认证的白名单路径
AUTH_WHITELIST = frozenset({
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/refresh",
    "/api/health",
    "/docs",
    "/openapi.json",
    "/favicon.ico",
})


def _extract_client_ip(request: Request) -> str:
    """提取客户端 IP 地址"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _safe_json_dump(obj: object) -> str:
    """安全地将对象序列化为 JSON 字符串"""
    try:
        return json.dumps(obj, default=str, ensure_ascii=False)
    except Exception:
        return ""


class RequireAuthMiddleware(BaseHTTPMiddleware):
    """JWT 认证中间件。

    白名单路径外的所有请求必须携带有效的 Bearer token。
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> StarletteResponse:
        path = request.url.path

        # 白名单路径跳过认证
        if path in AUTH_WHITELIST:
            return await call_next(request)

        # 检查 Authorization header
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return StarletteResponse(
                json.dumps({"detail": "需要提供认证令牌"}),
                status_code=401,
                media_type="application/json",
            )

        token = auth_header[7:]  # 去掉 "Bearer " 前缀
        try:
            decode_token(token)  # 验证 token，失败则抛 HTTPException
        except Exception:
            return StarletteResponse(
                json.dumps({"detail": "无效的认证令牌"}),
                status_code=401,
                media_type="application/json",
            )

        # Token 有效，继续处理请求
        return await call_next(request)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """操作审计日志中间件。

    自动记录所有 POST/PUT/DELETE/PATCH 请求到 op_audit_logs 表。
    """

    # 需要记录的 HTTP 方法
    TRACKED_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> StarletteResponse:
        method = request.method.upper()

        # 只记录写操作
        if method not in self.TRACKED_METHODS:
            return await call_next(request)

        path = request.url.path
        start_time = time.time()

        try:
            response = await call_next(request)
        except Exception as e:
            # 请求处理异常时也记录
            self._log_audit(
                request=request,
                path=path,
                method=method,
                status_code=500,
                latency=0,
                error=str(e),
            )
            raise

        # 记录审计日志
        self._log_audit(
            request=request,
            path=path,
            method=method,
            status_code=response.status_code,
            latency=time.time() - start_time,
        )

        return response

    def _log_audit(
        self,
        request: Request,
        path: str,
        method: str,
        status_code: int,
        latency: float,
        error: Optional[str] = None,
    ) -> None:
        """异步写入审计日志（不阻塞响应）。"""
        try:
            from stockquant.persistence.repository import save_op_audit_log

            # 尝试从请求状态中提取当前用户
            user_id = getattr(request.state, "user_id", None) or "anonymous"
            action = f"{method} {path}"
            # 从路径提取资源类型和资源 ID
            parts = path.strip("/").split("/")
            resource_type = parts[-2] if len(parts) >= 3 else parts[-1] if len(parts) == 2 else "unknown"
            resource_id = parts[-1] if len(parts) >= 2 else None

            # 仅记录写操作且非白名单
            if path in AUTH_WHITELIST:
                return

            save_op_audit_log(
                engine_url="",  # 使用默认引擎
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=json.dumps({
                    "method": method,
                    "path": path,
                    "latency_ms": round(latency * 1000, 1),
                    "error": error,
                }, default=str, ensure_ascii=False),
                ip_address=_extract_client_ip(request),
                user_agent=request.headers.get("user-agent", "")[:500],
                status_code=status_code,
            )
        except Exception:
            # 审计日志写入失败不影响主流程
            logger.debug("Audit log write failed", exc_info=True)


async def extract_user_id_middleware(request: Request, call_next: RequestResponseEndpoint) -> StarletteResponse:
    """从 JWT token 提取 user_id 并挂载到 request.state。

    此中间件不阻塞认证（由 RequireAuthMiddleware 负责验证），
    仅用于后续中间件/路由中获取当前用户信息。
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = decode_token(token)
            request.state.user_id = payload.get("sub", "anonymous")
            request.state.user_roles = payload.get("roles", [])
            request.state.user_role = payload.get("role", "VIEWER")
        except Exception:
            pass  # token 无效，user_id 保持默认

    response = await call_next(request)
    return response


# ====================================================================
# 速率限制中间件（#3 P0 任务）
# ====================================================================

# 路由前缀 → 限制配置的映射
_RATE_LIMIT_ROUTES = {
    "/api/auth/login": ("auth", 5),        # 认证：5 req/min
    "/api/auth/register": ("auth", 5),
    "/api/auth/refresh": ("auth", 5),
    "/api/backtest": ("backtest", 10),     # 回测：10 req/min
    "/api/optimize": ("backtest", 10),     # 参数优化归入回测
    "/api/ai/chat": ("ai_chat", 20),       # AI 对话：20 req/min
    "/api/trading": ("trading", 30),       # 交易：30 req/min
    "/api/orders": ("trading", 30),
    "/api/data": ("data", 60),             # 数据：60 req/min
    "/api/kline": ("data", 60),
}

# 白名单路径（不限速）
_RATE_LIMIT_WHITELIST = frozenset({
    "/api/health",
    "/docs",
    "/openapi.json",
    "/favicon.ico",
    "/redoc",
})


class _SlidingWindowCounter:
    """线程安全的滑动窗口计数器"""

    def __init__(self, window_seconds: int = 60):
        self._window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _cleanup(self, key: str, now: float) -> None:
        """清理过期的时间戳"""
        cutoff = now - self._window
        self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]

    def check_and_record(self, key: str, limit: int) -> tuple[bool, int, float]:
        """检查并记录请求

        返回: (allowed, remaining, retry_after_seconds)
        """
        now = time.time()
        with self._lock:
            self._cleanup(key, now)
            current = len(self._buckets[key])

            if current >= limit:
                # 计算最早记录的过期时间
                oldest = self._buckets[key][0] if self._buckets[key] else now
                retry_after = max(1.0, self._window - (now - oldest))
                return (False, 0, retry_after)

            self._buckets[key].append(now)
            remaining = limit - len(self._buckets[key])
            return (True, remaining, 0.0)

    def get_stats(self, key: str) -> dict:
        """获取指定 key 的统计信息"""
        now = time.time()
        with self._lock:
            self._cleanup(key, now)
            count = len(self._buckets[key])
        return {"key": key, "current_requests": count, "window_seconds": self._window}


# 全局计数器单例
_rate_counter = _SlidingWindowCounter(window_seconds=60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """API 速率限制中间件

    基于 IP + 用户 ID 的双重标识，按路由前缀差异化限速。
    使用滑动窗口算法，线程安全，无外部依赖。

    限制策略：
    - 认证接口 (/api/auth/*): 5 req/min（防暴力破解）
    - 回测接口 (/api/backtest/*): 10 req/min（资源密集型）
    - AI 对话 (/api/ai/chat/*): 20 req/min
    - 交易接口 (/api/trading/*): 30 req/min
    - 数据接口 (/api/data/*): 60 req/min
    - 其他接口: 100 req/min（全局默认）
    """

    def __init__(self, app, enabled: bool = True, global_limit: int = 100,
                 window_seconds: int = 60):
        super().__init__(app)
        self._enabled = enabled
        self._global_limit = global_limit
        self._window = window_seconds
        _rate_counter._window = window_seconds
        if enabled:
            logger.info(
                "RateLimitMiddleware 已启用 (global=%d req/%ds)",
                global_limit, window_seconds,
            )
        else:
            logger.info("RateLimitMiddleware 已禁用")

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> StarletteResponse:
        if not self._enabled:
            return await call_next(request)

        path = request.url.path

        # 白名单路径跳过
        if path in _RATE_LIMIT_WHITELIST:
            return await call_next(request)

        # WebSocket 连接不限速
        if path.startswith("/ws"):
            return await call_next(request)

        # 确定限速规则
        route_limit = self._global_limit
        for route_prefix, (_category, limit) in _RATE_LIMIT_ROUTES.items():
            if path.startswith(route_prefix):
                route_limit = limit
                break

        # 构建限速 key: IP + user_id (如果有)
        client_ip = _extract_client_ip(request)
        user_id = "anonymous"

        # 尝试从 token 提取 user_id
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                token = auth_header[7:]
                payload = _safe_decode_token(token)
                if payload:
                    user_id = payload.get("sub", "anonymous")
            except Exception:
                pass

        rate_key = f"{client_ip}:{user_id}:{self._get_route_category(path)}"

        # 检查并记录
        allowed, remaining, retry_after = _rate_counter.check_and_record(
            rate_key, route_limit
        )

        if not allowed:
            logger.warning(
                "速率限制触发: ip=%s user=%s path=%s limit=%d",
                client_ip, user_id, path, route_limit,
            )
            return StarletteResponse(
                json.dumps({
                    "detail": "请求过于频繁，请稍后再试",
                    "error_code": "ERR_RATE_LIMIT_001",
                    "retry_after": int(retry_after) + 1,
                }, ensure_ascii=False),
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": str(int(retry_after) + 1),
                    "X-RateLimit-Limit": str(route_limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # 请求通过，添加限速信息到响应头
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(route_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    def _get_route_category(self, path: str) -> str:
        """从路径提取路由分类"""
        for route_prefix, (category, _limit) in _RATE_LIMIT_ROUTES.items():
            if path.startswith(route_prefix):
                return category
        return "default"


def _safe_decode_token(token: str) -> Optional[dict]:
    """安全解码 JWT token（不抛异常）"""
    try:
        return decode_token.__wrapped__(token) if hasattr(decode_token, "__wrapped__") else None
    except Exception:
        pass
    # 直接用 jose 解码
    try:
        from jose import jwt
        SECRET_KEY = __import__("os").environ.get(
            "JWT_SECRET_KEY", "stockquant-dev-secret-change-in-prod"
        )
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return None


def get_rate_limit_stats() -> dict:
    """获取速率限制统计信息（供监控端点使用）"""
    return {
        "enabled": True,
        "window_seconds": _rate_counter._window,
        "tracked_keys": len(_rate_counter._buckets),
    }


# ====================================================================
# 全局异常处理中间件（#13 P0 任务）
# ====================================================================

# 已知的业务异常类型映射到 ErrorCode
_BUSINESS_EXCEPTION_MAP = {
    "DataFetchError": ("ERR_DATA_001", 502),
    "DataSourceUnavailableError": ("ERR_DATA_002", 503),
    "DataValidationError": ("ERR_DATA_003", 400),
    "RateLimitError": ("ERR_DATA_005", 429),
    "OrderError": ("ERR_TRADE_001", 400),
    "RiskError": ("ERR_TRADE_001", 400),
    "LLMResponseError": ("ERR_AI_001", 502),
    "ToolExecutionError": ("ERR_AI_004", 500),
    "EngineError": ("ERR_ENGINE_001", 500),
}


class GlobalExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """全局异常处理中间件

    统一捕获所有未处理的异常，转换为结构化错误响应：
    1. APIError → 直接使用其 error_code 和 http_status
    2. HTTPException → 转换为标准格式
    3. 已知业务异常 → 映射到对应 ErrorCode
    4. 未知异常 → ERR_SYS_001 (500)

    响应格式：
    {
        "error_code": "ERR_XXX_NNN",
        "message": "错误描述",
        "detail": {...},
        "request_id": "xxxxxxxx"
    }
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> StarletteResponse:
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            return self._handle_exception(exc, request)

    def _handle_exception(self, exc: Exception, request: Request) -> StarletteResponse:
        """将异常转换为结构化错误响应"""
        request_id = str(uuid.uuid4())[:8]
        path = request.url.path
        method = request.method

        # 1. APIError — 直接使用
        try:
            from stockquant.errors import APIError, ErrorCode
        except ImportError:
            APIError = None  # type: ignore
            ErrorCode = None  # type: ignore

        if APIError and isinstance(exc, APIError):
            logger.warning(
                "APIError [%s] %s %s: %s",
                exc.error_code, method, path, exc.message,
            )
            return StarletteResponse(
                json.dumps(exc.to_response(), ensure_ascii=False, default=str),
                status_code=exc.http_status,
                media_type="application/json",
                headers={"X-Request-Id": exc.request_id},
            )

        # 2. FastAPI HTTPException — 转换为标准格式
        if isinstance(exc, FastAPIHTTPException):
            status_code = exc.status_code
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

            # 根据 HTTP 状态码推断 ErrorCode
            if status_code == 401:
                error_code = "ERR_AUTH_001"
            elif status_code == 403:
                error_code = "ERR_AUTH_002"
            elif status_code == 404:
                error_code = "ERR_DATA_004"
            elif status_code == 429:
                error_code = "ERR_RATE_LIMIT_001"
            else:
                error_code = "ERR_SYS_001"

            response_data = {
                "error_code": error_code,
                "message": detail,
                "detail": {"status_code": status_code},
                "request_id": request_id,
            }
            logger.warning(
                "HTTPException [%s] %s %s: %s",
                error_code, method, path, detail,
            )
            return StarletteResponse(
                json.dumps(response_data, ensure_ascii=False, default=str),
                status_code=status_code,
                media_type="application/json",
                headers={"X-Request-Id": request_id},
            )

        # 3. 已知业务异常 — 映射
        exc_type_name = type(exc).__name__
        if exc_type_name in _BUSINESS_EXCEPTION_MAP:
            error_code, http_status = _BUSINESS_EXCEPTION_MAP[exc_type_name]
            response_data = {
                "error_code": error_code,
                "message": str(exc),
                "detail": {"exception_type": exc_type_name},
                "request_id": request_id,
            }
            logger.warning(
                "BusinessException [%s] %s %s: %s",
                error_code, method, path, exc,
            )
            return StarletteResponse(
                json.dumps(response_data, ensure_ascii=False, default=str),
                status_code=http_status,
                media_type="application/json",
                headers={"X-Request-Id": request_id},
            )

        # 4. 未知异常 — ERR_SYS_001
        tb = traceback.format_exc()
        logger.error(
            "UnhandledException [%s] %s %s: %s\n%s",
            request_id, method, path, exc, tb,
        )
        response_data = {
            "error_code": "ERR_SYS_001",
            "message": "服务器内部错误，请稍后重试",
            "detail": {
                "exception_type": exc_type_name,
                "exception_message": str(exc),
            },
            "request_id": request_id,
        }

        # 开发环境返回详细错误信息
        import os
        if os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"):
            response_data["detail"]["traceback"] = tb

        return StarletteResponse(
            json.dumps(response_data, ensure_ascii=False, default=str),
            status_code=500,
            media_type="application/json",
            headers={"X-Request-Id": request_id},
        )
