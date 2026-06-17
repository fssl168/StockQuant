# -*- coding: utf-8 -*-
"""F030 调度器路由 — 定时任务管理"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from stockquant.api.deps import get_current_user, get_required_user

logger = logging.getLogger("stockquant.api.scheduler")

router = APIRouter()

# 全局调度器实例（懒初始化）
_scheduler = None


def _get_scheduler():
    """延迟初始化 StockScheduler"""
    global _scheduler
    if _scheduler is None:
        from stockquant.scheduler import StockScheduler
        _scheduler = StockScheduler()
    return _scheduler


# ====================================================================
# 请求模型
# ====================================================================

class TaskCreate(BaseModel):
    name: str
    cron_expr: str
    action: str
    enabled: bool = True


# ====================================================================
# 端点
# ====================================================================

@router.get("/scheduler/tasks", summary="列出所有定时任务")
async def list_tasks(user: dict = get_current_user):
    """获取所有已注册的定时任务"""
    sched = _get_scheduler()
    tasks = []
    for name in sched.task_names:
        task = sched._tasks.get(name)
        tasks.append({
            "name": name,
            "cron_expr": task.cron_expression if task else "",
            "is_running": task.is_running if task else False,
        })
    return tasks


@router.post("/scheduler/tasks", summary="添加定时任务")
async def add_task(body: TaskCreate, user: dict = get_required_user):
    """添加新的定时任务"""
    sched = _get_scheduler()

    # 将 action 映射为可调用函数
    def _action_fn():
        logger.info(f"执行定时任务: {body.name}, action={body.action}")

    if not body.enabled:
        return {"success": True, "name": body.name, "message": "任务已创建但未启用"}

    sched.add_task(
        name=body.name,
        cron=body.cron_expr,
        fn=_action_fn,
    )
    return {"success": True, "name": body.name}


@router.delete("/scheduler/tasks/{task_id}", summary="删除定时任务")
async def remove_task(task_id: str, user: dict = get_required_user):
    """删除指定定时任务"""
    sched = _get_scheduler()
    removed = sched.remove_task(task_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return {"success": True, "name": task_id}


@router.post("/scheduler/start", summary="启动调度器")
async def start_scheduler(user: dict = get_required_user):
    """启动调度器"""
    sched = _get_scheduler()
    sched.start()
    return {"success": True, "status": "running"}


@router.post("/scheduler/stop", summary="停止调度器")
async def stop_scheduler(user: dict = get_required_user):
    """停止调度器"""
    sched = _get_scheduler()
    sched.stop()
    return {"success": True, "status": "stopped"}


@router.get("/scheduler/status", summary="调度器状态")
async def scheduler_status(user: dict = get_current_user):
    """获取调度器运行状态"""
    sched = _get_scheduler()
    return {
        "running": sched._running,
        "task_count": sched.task_count,
        "task_names": sched.task_names,
    }
