# -*- coding: utf-8 -*-
"""F029/F019 中间件 — RequireAuth + AuditLog"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse

from stockquant.api.deps import decode_token, SECRET_KEY, ALGORITHM

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
