# -*- coding: utf-8 -*-
"""#13 P0 任务：统一错误码体系与 API 异常

提供结构化错误码、统一异常响应格式和 APIError 异常类。

错误码命名规范：
    ERR_<MODULE>_<NNN>

模块前缀：
    DATA  — 数据层
    TRADE — 交易层
    AUTH  — 认证/授权
    AI    — AI/LLM
    ENGINE— 回测引擎
    RATE  — 速率限制
    SYS   — 系统级
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    """结构化错误码枚举"""

    # ── 数据层 ──────────────────────────────────────────
    DATA_FETCH_FAILED = "ERR_DATA_001"
    DATA_SOURCE_UNAVAILABLE = "ERR_DATA_002"
    DATA_VALIDATION_FAILED = "ERR_DATA_003"
    DATA_NOT_FOUND = "ERR_DATA_004"
    DATA_RATE_LIMITED = "ERR_DATA_005"

    # ── 交易层 ──────────────────────────────────────────
    TRADE_ORDER_FAILED = "ERR_TRADE_001"
    TRADE_CANCEL_FAILED = "ERR_TRADE_002"
    TRADE_INSUFFICIENT_FUNDS = "ERR_TRADE_003"
    TRADE_INSUFFICIENT_POSITION = "ERR_TRADE_004"
    TRADE_PRICE_LIMIT = "ERR_TRADE_005"
    TRADE_BROKER_DISCONNECTED = "ERR_TRADE_006"

    # ── 认证/授权 ────────────────────────────────────────
    AUTH_INVALID_TOKEN = "ERR_AUTH_001"
    AUTH_PERMISSION_DENIED = "ERR_AUTH_002"
    AUTH_TOKEN_EXPIRED = "ERR_AUTH_003"
    AUTH_USER_NOT_FOUND = "ERR_AUTH_004"

    # ── AI 层 ────────────────────────────────────────────
    AI_LLM_CALL_FAILED = "ERR_AI_001"
    AI_LLM_TIMEOUT = "ERR_AI_002"
    AI_RESPONSE_INVALID = "ERR_AI_003"
    AI_AGENT_ERROR = "ERR_AI_004"

    # ── 回测引擎 ────────────────────────────────────────
    ENGINE_BACKTEST_FAILED = "ERR_ENGINE_001"
    ENGINE_STRATEGY_ERROR = "ERR_ENGINE_002"
    ENGINE_DATA_MISMATCH = "ERR_ENGINE_003"

    # ── 速率限制 ────────────────────────────────────────
    RATE_LIMIT_EXCEEDED = "ERR_RATE_LIMIT_001"

    # ── 系统级 ──────────────────────────────────────────
    SYS_INTERNAL_ERROR = "ERR_SYS_001"
    SYS_CONFIG_ERROR = "ERR_SYS_002"
    SYS_DATABASE_ERROR = "ERR_SYS_003"
    SYS_SERVICE_UNAVAILABLE = "ERR_SYS_004"


# HTTP 状态码映射
_ERROR_HTTP_STATUS: Dict[str, int] = {
    # 数据层
    ErrorCode.DATA_FETCH_FAILED: 502,
    ErrorCode.DATA_SOURCE_UNAVAILABLE: 503,
    ErrorCode.DATA_VALIDATION_FAILED: 400,
    ErrorCode.DATA_NOT_FOUND: 404,
    ErrorCode.DATA_RATE_LIMITED: 429,
    # 交易层
    ErrorCode.TRADE_ORDER_FAILED: 400,
    ErrorCode.TRADE_CANCEL_FAILED: 400,
    ErrorCode.TRADE_INSUFFICIENT_FUNDS: 400,
    ErrorCode.TRADE_INSUFFICIENT_POSITION: 400,
    ErrorCode.TRADE_PRICE_LIMIT: 400,
    ErrorCode.TRADE_BROKER_DISCONNECTED: 503,
    # 认证
    ErrorCode.AUTH_INVALID_TOKEN: 401,
    ErrorCode.AUTH_PERMISSION_DENIED: 403,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    ErrorCode.AUTH_USER_NOT_FOUND: 404,
    # AI
    ErrorCode.AI_LLM_CALL_FAILED: 502,
    ErrorCode.AI_LLM_TIMEOUT: 504,
    ErrorCode.AI_RESPONSE_INVALID: 502,
    ErrorCode.AI_AGENT_ERROR: 500,
    # 引擎
    ErrorCode.ENGINE_BACKTEST_FAILED: 500,
    ErrorCode.ENGINE_STRATEGY_ERROR: 400,
    ErrorCode.ENGINE_DATA_MISMATCH: 400,
    # 速率限制
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    # 系统
    ErrorCode.SYS_INTERNAL_ERROR: 500,
    ErrorCode.SYS_CONFIG_ERROR: 500,
    ErrorCode.SYS_DATABASE_ERROR: 503,
    ErrorCode.SYS_SERVICE_UNAVAILABLE: 503,
}


class APIError(Exception):
    """统一 API 异常类

    所有 API 路由应抛出 APIError 或其子类，由全局异常处理中间件统一捕获。

    Parameters
    ----------
    error_code : ErrorCode | str
        结构化错误码
    message : str
        人类可读的错误描述
    detail : dict, optional
        附加详情（如 symbol、order_id 等）
    http_status : int, optional
        覆盖默认的 HTTP 状态码
    """

    def __init__(
        self,
        error_code: ErrorCode | str,
        message: str = "",
        detail: Optional[Dict[str, Any]] = None,
        http_status: Optional[int] = None,
    ) -> None:
        self.error_code = error_code.value if isinstance(error_code, ErrorCode) else str(error_code)
        self.message = message or error_code.name if isinstance(error_code, ErrorCode) else str(error_code)
        self.detail = detail or {}
        self.http_status = http_status or _ERROR_HTTP_STATUS.get(self.error_code, 500)
        self.request_id = str(uuid.uuid4())[:8]
        super().__init__(self.message)

    def to_response(self) -> Dict[str, Any]:
        """转换为 API 响应 JSON"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "detail": self.detail,
            "request_id": self.request_id,
        }


def create_error_response(
    error_code: ErrorCode | str,
    message: str = "",
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """快捷创建错误响应"""
    err = APIError(error_code, message, detail)
    return err.to_response()


def get_http_status(error_code: str) -> int:
    """获取错误码对应的 HTTP 状态码"""
    return _ERROR_HTTP_STATUS.get(error_code, 500)
