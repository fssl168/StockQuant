# -*- coding: utf-8 -*-
"""F030 调度器路由 — 定时任务管理"""

import logging
import os
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from stockquant.api.deps import get_current_user, get_required_user
from stockquant.api.schemas import (
    MessageResponse,
    SchedulerStatusResponse,
    UserToken,
)
from stockquant.persistence.persistent_store import SchedulerStore

logger = logging.getLogger("stockquant.api.scheduler")

router = APIRouter()

# 全局调度器实例（懒初始化）
_scheduler: Any = None
_scheduler_store: SchedulerStore | None = None


def set_storage(storage: SchedulerStore):
    """存储引用注入（由 main.py 调用）"""
    global _scheduler_store
    if storage is not None:
        _scheduler_store = storage


def _get_scheduler():
    """延迟初始化 StockScheduler"""
    global _scheduler
    if _scheduler is None:
        from stockquant.scheduler import StockScheduler
        _scheduler = StockScheduler()
        _scheduler.set_db_url(os.environ.get("DATABASE_URL", "sqlite:///./stockquant.db"))

        # 注册内置定时任务：每日收盘后保存权益快照（15:30）
        try:
            from stockquant.api.routers.portfolio import save_daily_snapshot
            _scheduler.add_task(
                name="daily_equity_snapshot",
                cron="30 15 * * 1-5",
                fn=save_daily_snapshot,
                action="save_equity_snapshot",
            )
            logger.info("已注册每日权益快照定时任务 (15:30)")
        except Exception as e:
            logger.warning(f"注册权益快照任务失败: {e}")

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

@router.get("/scheduler/tasks", summary="列出所有定时任务", response_model=List[Dict[str, Any]])
async def list_tasks(_user: UserToken = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """获取所有已注册的定时任务"""
    sched = _get_scheduler()
    tasks = []
    for name in sched.task_names:
        task = sched._tasks.get(name)
        tasks.append({
            "name": name,
            "cronExpr": task.cron_expression if task else "",
            "isRunning": task.is_running if task else False,
        })
    # 合并数据库中的任务（可能已删除但 DB 未清理）
    if _scheduler_store is not None:
        db_task_ids = set()
        for t in _scheduler_store.values():
            if t and t.get("name") not in [x["name"] for x in tasks]:
                tasks.append({
                    "name": t.get("name", ""),
                    "cronExpr": t.get("cron_expression", ""),
                    "isRunning": False,
                    "fromDb": True,
                })
            db_task_ids.add(t.get("id", ""))
    return tasks


@router.post("/scheduler/tasks", summary="添加定时任务")
async def add_task(body: TaskCreate, _user: UserToken = Depends(get_required_user)) -> Dict[str, Any]:
    """添加新的定时任务"""
    sched = _get_scheduler()

    # 将 action 映射为可调用函数
    def _action_fn():
        logger.info(f"执行定时任务: {body.name}, action={body.action}")

    if not body.enabled:
        # 仍然持久化到 DB
        if _scheduler_store is not None:
            _scheduler_store[body.name] = {
                "id": body.name,
                "name": body.name,
                "cron_expression": body.cron_expr,
                "action": body.action,
                "enabled": False,
            }
        return {"success": True, "name": body.name, "message": "任务已创建但未启用"}

    sched.add_task(
        name=body.name,
        cron=body.cron_expr,
        fn=_action_fn,
    )
    # 持久化到数据库
    if _scheduler_store is not None:
        _scheduler_store[body.name] = {
            "id": body.name,
            "name": body.name,
            "cron_expression": body.cron_expr,
            "action": body.action,
            "enabled": True,
        }
    return {"success": True, "name": body.name}


@router.delete("/scheduler/tasks/{task_id}", summary="删除定时任务")
async def remove_task(task_id: str, _user: UserToken = Depends(get_required_user)) -> MessageResponse:
    """删除指定定时任务"""
    sched = _get_scheduler()
    removed = sched.remove_task(task_id)
    # 同时从数据库删除
    if _scheduler_store is not None and task_id in _scheduler_store:
        del _scheduler_store[task_id]
    if not removed and task_id not in _scheduler_store:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return {"success": True, "name": task_id}


@router.post("/scheduler/start", summary="启动调度器")
async def start_scheduler(_user: UserToken = Depends(get_required_user)) -> Dict[str, Any]:
    """启动调度器"""
    sched = _get_scheduler()
    sched.start()
    return {"success": True, "status": "running"}


@router.post("/scheduler/stop", summary="停止调度器")
async def stop_scheduler(_user: UserToken = Depends(get_required_user)) -> Dict[str, Any]:
    """停止调度器"""
    sched = _get_scheduler()
    sched.stop()
    return {"success": True, "status": "stopped"}


@router.get("/scheduler/status", summary="调度器状态")
async def scheduler_status(_user: UserToken = Depends(get_current_user)) -> SchedulerStatusResponse:
    """获取调度器运行状态"""
    sched = _get_scheduler()
    return {
        "running": sched._running,
        "task_count": sched.task_count,
        "task_names": sched.task_names,
    }
