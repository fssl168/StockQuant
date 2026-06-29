# -*- coding: utf-8 -*-
"""#3 P0 任务：速率限制中间件测试

测试 RateLimitMiddleware 和 _SlidingWindowCounter 的正确性。
"""

import json
import time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stockquant.api.middleware import (
    RateLimitMiddleware,
    _SlidingWindowCounter,
    _RATE_LIMIT_ROUTES,
    _RATE_LIMIT_WHITELIST,
    get_rate_limit_stats,
)


# ─── 滑动窗口计数器单元测试 ──────────────────────────────────────────

class TestSlidingWindowCounter:
    """滑动窗口计数器单元测试"""

    def test_init(self):
        counter = _SlidingWindowCounter(window_seconds=60)
        assert counter._window == 60
        assert len(counter._buckets) == 0

    def test_check_and_record_allows_within_limit(self):
        counter = _SlidingWindowCounter(window_seconds=60)
        for i in range(5):
            allowed, remaining, retry_after = counter.check_and_record("key1", 5)
            assert allowed is True
            assert remaining == 5 - i - 1
            assert retry_after == 0.0

    def test_check_and_record_blocks_over_limit(self):
        counter = _SlidingWindowCounter(window_seconds=60)
        # 先消耗 3 次配额
        for _ in range(3):
            counter.check_and_record("key1", 3)

        # 第 4 次应被拒绝
        allowed, remaining, retry_after = counter.check_and_record("key1", 3)
        assert allowed is False
        assert remaining == 0
        assert retry_after > 0

    def test_different_keys_independent(self):
        counter = _SlidingWindowCounter(window_seconds=60)
        # key1 消耗 2 次
        counter.check_and_record("key1", 2)
        counter.check_and_record("key1", 2)

        # key1 已满
        allowed1, _, _ = counter.check_and_record("key1", 2)
        assert allowed1 is False

        # key2 仍可用
        allowed2, remaining2, _ = counter.check_and_record("key2", 2)
        assert allowed2 is True
        assert remaining2 == 1

    def test_window_expiry(self):
        """测试窗口过期后计数器重置"""
        counter = _SlidingWindowCounter(window_seconds=1)  # 1 秒窗口
        counter.check_and_record("key1", 1)
        
        # 立即再请求应被拒绝
        allowed, _, _ = counter.check_and_record("key1", 1)
        assert allowed is False

        # 等待窗口过期
        time.sleep(1.1)
        allowed, remaining, _ = counter.check_and_record("key1", 1)
        assert allowed is True
        assert remaining == 0

    def test_get_stats(self):
        counter = _SlidingWindowCounter(window_seconds=60)
        counter.check_and_record("key1", 10)
        counter.check_and_record("key1", 10)
        stats = counter.get_stats("key1")
        assert stats["current_requests"] == 2
        assert stats["window_seconds"] == 60


# ─── 路由配置测试 ──────────────────────────────────────────────────

class TestRateLimitRouteConfig:
    """路由限速配置测试"""

    def test_auth_routes_have_strict_limit(self):
        for route in ["/api/auth/login", "/api/auth/register", "/api/auth/refresh"]:
            assert route in _RATE_LIMIT_ROUTES
            category, limit = _RATE_LIMIT_ROUTES[route]
            assert category == "auth"
            assert limit == 5  # 认证接口 5 req/min

    def test_backtest_routes_have_low_limit(self):
        assert "/api/backtest" in _RATE_LIMIT_ROUTES
        _, limit = _RATE_LIMIT_ROUTES["/api/backtest"]
        assert limit == 10

    def test_ai_chat_route(self):
        assert "/api/ai/chat" in _RATE_LIMIT_ROUTES
        _, limit = _RATE_LIMIT_ROUTES["/api/ai/chat"]
        assert limit == 20

    def test_trading_route(self):
        assert "/api/trading" in _RATE_LIMIT_ROUTES
        _, limit = _RATE_LIMIT_ROUTES["/api/trading"]
        assert limit == 30

    def test_data_route(self):
        assert "/api/data" in _RATE_LIMIT_ROUTES
        _, limit = _RATE_LIMIT_ROUTES["/api/data"]
        assert limit == 60

    def test_health_is_whitelisted(self):
        assert "/api/health" in _RATE_LIMIT_WHITELIST
        assert "/docs" in _RATE_LIMIT_WHITELIST


# ─── 中间件集成测试 ──────────────────────────────────────────────────

def _create_test_app(limit: int = 3, window: int = 60) -> FastAPI:
    """创建测试用 FastAPI 应用"""
    app = FastAPI()

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/auth/login")
    async def login():
        return {"token": "test"}

    @app.get("/api/backtest/run")
    async def run_backtest():
        return {"task_id": "test"}

    @app.get("/api/data/kline")
    async def get_kline():
        return {"data": []}

    @app.get("/api/dashboard")
    async def dashboard():
        return {"data": "ok"}

    app.add_middleware(
        RateLimitMiddleware,
        enabled=True,
        global_limit=limit,
        window_seconds=window,
    )
    return app


class TestRateLimitMiddlewareIntegration:
    """速率限制中间件集成测试"""

    def test_health_endpoint_not_rate_limited(self):
        """健康检查端点不受速率限制"""
        app = _create_test_app(limit=1, window=60)
        client = TestClient(app)

        # 连续请求 /api/health 不应被限速
        for _ in range(10):
            resp = client.get("/api/health")
            assert resp.status_code == 200

    def test_global_limit_triggers_429(self):
        """全局限制触发 429"""
        app = _create_test_app(limit=3, window=60)
        client = TestClient(app)

        # 3 次请求应成功
        for i in range(3):
            resp = client.get("/api/dashboard")
            assert resp.status_code == 200

        # 第 4 次应返回 429
        resp = client.get("/api/dashboard")
        assert resp.status_code == 429
        data = resp.json()
        assert "error_code" in data
        assert data["error_code"] == "ERR_RATE_LIMIT_001"
        assert "retry_after" in data

    def test_429_has_retry_after_header(self):
        """429 响应包含 Retry-After 头"""
        app = _create_test_app(limit=1, window=60)
        client = TestClient(app)

        client.get("/api/dashboard")  # 消耗配额
        resp = client.get("/api/dashboard")
        assert resp.status_code == 429
        assert "retry-after" in {k.lower() for k in resp.headers.keys()}

    def test_429_has_ratelimit_headers(self):
        """429 响应包含 X-RateLimit-* 头"""
        app = _create_test_app(limit=1, window=60)
        client = TestClient(app)

        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        assert "x-ratelimit-limit" in {k.lower() for k in resp.headers.keys()}
        assert "x-ratelimit-remaining" in {k.lower() for k in resp.headers.keys()}

    def test_auth_route_has_stricter_limit(self):
        """认证路由有更严格的限制"""
        app = _create_test_app(limit=100, window=60)
        client = TestClient(app)

        # 认证接口限制 5 req/min（由 _RATE_LIMIT_ROUTES 配置）
        for i in range(5):
            resp = client.get("/api/auth/login")
            assert resp.status_code == 200

        # 第 6 次应被限速
        resp = client.get("/api/auth/login")
        assert resp.status_code == 429

    def test_disabled_middleware_allows_all(self):
        """禁用的中间件允许所有请求"""
        app = FastAPI()

        @app.get("/api/test")
        async def test_endpoint():
            return {"ok": True}

        app.add_middleware(
            RateLimitMiddleware,
            enabled=False,
            global_limit=1,
            window_seconds=60,
        )
        client = TestClient(app)

        for _ in range(20):
            resp = client.get("/api/test")
            assert resp.status_code == 200


# ─── 监控统计测试 ──────────────────────────────────────────────────

class TestRateLimitStats:
    """速率限制统计测试"""

    def test_get_rate_limit_stats(self):
        stats = get_rate_limit_stats()
        assert "enabled" in stats
        assert "window_seconds" in stats
        assert "tracked_keys" in stats
        assert isinstance(stats["tracked_keys"], int)
