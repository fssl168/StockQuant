# -*- coding: utf-8 -*-
"""Prometheus 监控指标端点"""

from __future__ import annotations

import time
import logging
from typing import Dict
from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger("stockquant.api")

router = APIRouter(tags=["monitoring"])

# 请求计数器
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# 请求延迟直方图
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

# 回测任务Gauge
backtest_tasks_running = Gauge(
    'backtest_tasks_running',
    'Number of running backtest tasks'
)

# WebSocket 连接数
websocket_connections = Gauge(
    'websocket_connections',
    'Number of active WebSocket connections'
)

# 订单计数器
orders_total = Counter(
    'orders_total',
    'Total orders processed',
    ['side', 'status']
)

# 风控事件计数器
risk_events_total = Counter(
    'risk_events_total',
    'Total risk events',
    ['severity', 'event_type']
)

# 活跃用户数
active_users = Gauge(
    'active_users',
    'Number of active users in last hour'
)


@router.get("/metrics", summary="Prometheus 指标")
async def metrics() -> Response:
    """返回 Prometheus 格式的指标"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@router.get("/health", summary="健康检查")
async def health_check() -> Dict:
    """系统健康检查"""
    return {
        "status": "ok",
        "timestamp": time.time(),
    }
