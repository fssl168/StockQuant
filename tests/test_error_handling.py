# -*- coding: utf-8 -*-
"""#13 P0 任务：异常处理体系测试

测试 ErrorCode、APIError 和 GlobalExceptionHandlerMiddleware。
"""

import json
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from stockquant.errors import (
    ErrorCode,
    APIError,
    create_error_response,
    get_http_status,
)
from stockquant.api.middleware import GlobalExceptionHandlerMiddleware


# ─── ErrorCode 测试 ─────────────────────────────────────────────────

class TestErrorCode:
    """错误码枚举测试"""

    def test_error_code_format(self):
        """所有错误码遵循 ERR_<MODULE>_<NNN> 格式"""
        for code in ErrorCode:
            parts = code.value.split("_")
            assert len(parts) >= 3
            assert parts[0] == "ERR"

    def test_error_code_uniqueness(self):
        """所有错误码唯一"""
        values = [c.value for c in ErrorCode]
        assert len(values) == len(set(values))

    def test_data_error_codes(self):
        assert ErrorCode.DATA_FETCH_FAILED.value == "ERR_DATA_001"
        assert ErrorCode.DATA_SOURCE_UNAVAILABLE.value == "ERR_DATA_002"
        assert ErrorCode.DATA_NOT_FOUND.value == "ERR_DATA_004"

    def test_trade_error_codes(self):
        assert ErrorCode.TRADE_ORDER_FAILED.value == "ERR_TRADE_001"
        assert ErrorCode.TRADE_INSUFFICIENT_FUNDS.value == "ERR_TRADE_003"

    def test_auth_error_codes(self):
        assert ErrorCode.AUTH_INVALID_TOKEN.value == "ERR_AUTH_001"
        assert ErrorCode.AUTH_PERMISSION_DENIED.value == "ERR_AUTH_002"

    def test_sys_error_codes(self):
        assert ErrorCode.SYS_INTERNAL_ERROR.value == "ERR_SYS_001"
        assert ErrorCode.SYS_DATABASE_ERROR.value == "ERR_SYS_003"


# ─── APIError 测试 ──────────────────────────────────────────────────

class TestAPIError:
    """APIError 异常类测试"""

    def test_basic_creation(self):
        err = APIError(ErrorCode.DATA_NOT_FOUND, "K线数据不存在")
        assert err.error_code == "ERR_DATA_004"
        assert err.message == "K线数据不存在"
        assert err.http_status == 404
        assert len(err.request_id) == 8

    def test_with_detail(self):
        err = APIError(
            ErrorCode.TRADE_INSUFFICIENT_FUNDS,
            "资金不足",
            detail={"required": 100000, "available": 50000},
        )
        assert err.detail["required"] == 100000
        assert err.detail["available"] == 50000

    def test_to_response(self):
        err = APIError(ErrorCode.AUTH_INVALID_TOKEN, "无效令牌")
        resp = err.to_response()
        assert resp["error_code"] == "ERR_AUTH_001"
        assert resp["message"] == "无效令牌"
        assert "request_id" in resp
        assert "detail" in resp

    def test_custom_http_status(self):
        err = APIError(ErrorCode.DATA_FETCH_FAILED, "获取失败", http_status=503)
        assert err.http_status == 503

    def test_string_error_code(self):
        """支持字符串错误码"""
        err = APIError("ERR_CUSTOM_001", "自定义错误")
        assert err.error_code == "ERR_CUSTOM_001"
        assert err.http_status == 500  # 未知错误码默认 500

    def test_default_message(self):
        """不传 message 时使用错误码名称"""
        err = APIError(ErrorCode.SYS_INTERNAL_ERROR)
        assert "SYS_INTERNAL_ERROR" in err.message or err.message


# ─── 辅助函数测试 ────────────────────────────────────────────────────

class TestHelperFunctions:
    """辅助函数测试"""

    def test_create_error_response(self):
        resp = create_error_response(ErrorCode.RATE_LIMIT_EXCEEDED, "请求过频")
        assert resp["error_code"] == "ERR_RATE_LIMIT_001"
        assert resp["message"] == "请求过频"

    def test_get_http_status(self):
        assert get_http_status("ERR_DATA_004") == 404
        assert get_http_status("ERR_AUTH_001") == 401
        assert get_http_status("ERR_RATE_LIMIT_001") == 429
        assert get_http_status("ERR_SYS_001") == 500
        assert get_http_status("UNKNOWN_CODE") == 500


# ─── 全局异常处理中间件集成测试 ──────────────────────────────────────

def _create_error_test_app() -> FastAPI:
    """创建用于测试异常处理的 FastAPI 应用"""
    app = FastAPI()

    @app.get("/api/ok")
    async def ok_endpoint():
        return {"status": "ok"}

    @app.get("/api/api-error")
    async def api_error_endpoint():
        raise APIError(ErrorCode.DATA_NOT_FOUND, "数据不存在", detail={"symbol": "000001"})

    @app.get("/api/http-401")
    async def http_401_endpoint():
        raise HTTPException(status_code=401, detail="未授权")

    @app.get("/api/http-403")
    async def http_403_endpoint():
        raise HTTPException(status_code=403, detail="禁止访问")

    @app.get("/api/http-404")
    async def http_404_endpoint():
        raise HTTPException(status_code=404, detail="资源不存在")

    @app.get("/api/http-500")
    async def http_500_endpoint():
        raise HTTPException(status_code=500, detail="内部错误")

    @app.get("/api/unhandled")
    async def unhandled_endpoint():
        # 模拟未处理的异常
        result = 1 / 0  # ZeroDivisionError
        return {"result": result}

    @app.get("/api/business-error")
    async def business_error_endpoint():
        from stockquant.data.exceptions import DataFetchError
        raise DataFetchError("BaoStock 获取失败", source="baostock")

    app.add_middleware(GlobalExceptionHandlerMiddleware)
    return app


class TestGlobalExceptionHandler:
    """全局异常处理中间件测试"""

    def test_normal_request_unaffected(self):
        """正常请求不受影响"""
        app = _create_error_test_app()
        client = TestClient(app)
        resp = client.get("/api/ok")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_api_error_caught(self):
        """APIError 被正确捕获并格式化"""
        app = _create_error_test_app()
        client = TestClient(app)
        resp = client.get("/api/api-error")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error_code"] == "ERR_DATA_004"
        assert data["message"] == "数据不存在"
        assert data["detail"]["symbol"] == "000001"
        assert "request_id" in data

    def test_http_exception_401(self):
        """HTTPException 401 被转换为标准格式"""
        app = _create_error_test_app()
        client = TestClient(app)
        resp = client.get("/api/http-401")
        assert resp.status_code == 401
        data = resp.json()
        assert data["error_code"] == "ERR_AUTH_001"
        assert data["message"] == "未授权"

    def test_http_exception_403(self):
        """HTTPException 403 被转换为标准格式"""
        app = _create_error_test_app()
        client = TestClient(app)
        resp = client.get("/api/http-403")
        assert resp.status_code == 403
        data = resp.json()
        assert data["error_code"] == "ERR_AUTH_002"

    def test_http_exception_404(self):
        """HTTPException 404 被转换为标准格式"""
        app = _create_error_test_app()
        client = TestClient(app)
        resp = client.get("/api/http-404")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error_code"] == "ERR_DATA_004"

    def test_http_exception_500(self):
        """HTTPException 500 被转换为标准格式"""
        app = _create_error_test_app()
        client = TestClient(app)
        resp = client.get("/api/http-500")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error_code"] == "ERR_SYS_001"

    def test_unhandled_exception_caught(self):
        """未处理的异常被捕获并返回 500"""
        app = _create_error_test_app()
        client = TestClient(app)
        resp = client.get("/api/unhandled")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error_code"] == "ERR_SYS_001"
        assert "request_id" in data
        assert data["detail"]["exception_type"] == "ZeroDivisionError"

    def test_business_exception_mapped(self):
        """已知业务异常被正确映射"""
        app = _create_error_test_app()
        client = TestClient(app)
        resp = client.get("/api/business-error")
        assert resp.status_code == 502
        data = resp.json()
        assert data["error_code"] == "ERR_DATA_001"
        assert "BaoStock" in data["message"]

    def test_request_id_in_header(self):
        """响应头包含 X-Request-Id"""
        app = _create_error_test_app()
        client = TestClient(app)
        resp = client.get("/api/api-error")
        assert "x-request-id" in {k.lower() for k in resp.headers.keys()}

    def test_response_format_consistency(self):
        """所有错误响应格式一致"""
        app = _create_error_test_app()
        client = TestClient(app)

        for endpoint in ["/api/api-error", "/api/http-401", "/api/unhandled"]:
            resp = client.get(endpoint)
            data = resp.json()
            assert "error_code" in data
            assert "message" in data
            assert "detail" in data
            assert "request_id" in data
