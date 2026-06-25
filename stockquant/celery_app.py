# -*- coding: utf-8 -*-
"""Celery 任务队列配置

用于：
- 回测任务异步执行
- 参数优化任务
- 数据采集任务
"""

from __future__ import annotations

import os
from celery import Celery
from celery.schedules import crontab

# Redis 配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 创建 Celery 应用
celery_app = Celery(
    "stockquant",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "stockquant.tasks.backtest",
    ]
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化方式
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,
    
    # 任务结果过期时间 (24小时)
    result_expires=86400,
    
    # 任务超时 (10分钟)
    task_soft_time_limit=600,
    task_time_limit=660,
    
    # Worker 配置
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    
    # 路由配置
    task_routes={
        "stockquant.tasks.backtest.*": {"queue": "backtest"},
    },

    # 定时任务
    beat_schedule={},
)

# 自动发现任务
celery_app.autodiscover_tasks(["stockquant.tasks"])


@celery_app.task(bind=True, name="stockquant.health_check")
def health_check(self) -> dict:
    """健康检查任务"""
    return {"status": "ok", "worker": self.request.hostname}


if __name__ == "__main__":
    celery_app.start()
