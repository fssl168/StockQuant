# -*- coding: utf-8 -*-
"""F020 GAP-M5 — PipelineScheduler API 路由

提供对 PipelineScheduler 单例的 HTTP 控制能力：
- 查询调度器状态
- 启动/停止调度器
- 列出/添加/移除调度任务（ScheduleSpec）

路径前缀：/api/pipeline/scheduler/*
"""

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from stockquant.api.deps import get_admin_user, get_current_user
from stockquant.api.schemas import UserToken

router = APIRouter(tags=["管线调度器"])
logger = logging.getLogger("stockquant.api.pipeline_scheduler")


def _get_scheduler_safe():
    """安全获取 PipelineScheduler 单例（导入失败时抛 503）"""
    try:
        from stockquant.ai.scheduler import get_scheduler
        return get_scheduler()
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"PipelineScheduler 模块未安装: {exc}",
        )


def _serialize_spec(spec) -> Dict[str, Any]:
    """将 ScheduleSpec 序列化为字典（含枚举值安全转换）"""
    try:
        return asdict(spec)
    except TypeError:
        # fallback：手动转换
        return {
            "name": spec.name,
            "level": spec.level,
            "interval_seconds": spec.interval_seconds,
            "daily_hour": spec.daily_hour,
            "daily_minute": spec.daily_minute,
            "symbols": list(spec.symbols) if spec.symbols else [],
            "enabled": spec.enabled,
            "last_run_at": spec.last_run_at,
            "last_result": spec.last_result,
            "run_count": spec.run_count,
            "error_count": spec.error_count,
        }


@router.get("/pipeline/scheduler/status", summary="获取调度器状态")
async def get_status(
    _user: UserToken = Depends(get_current_user),
):
    try:
        scheduler = _get_scheduler_safe()
        status = scheduler.status()
        # 补充任务详情
        tasks = [_serialize_spec(s) for s in scheduler.list_tasks()]
        status["task_count"] = len(tasks)
        status["tasks"] = tasks
        return status
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("获取调度器状态失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/pipeline/scheduler/start", summary="启动调度器")
async def start_scheduler(
    _user: UserToken = Depends(get_admin_user),
):
    try:
        scheduler = _get_scheduler_safe()
        if scheduler.is_running:
            return {
                "already_running": True,
                "message": "调度器已在运行中",
                "status": scheduler.status(),
            }
        await scheduler.start()
        logger.info("调度器已通过 API 启动（操作者: %s）", _user.sub)
        return {"success": True, "is_running": scheduler.is_running}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("启动调度器失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/pipeline/scheduler/stop", summary="停止调度器")
async def stop_scheduler(
    _user: UserToken = Depends(get_admin_user),
):
    try:
        scheduler = _get_scheduler_safe()
        if not scheduler.is_running:
            return {
                "already_stopped": True,
                "message": "调度器未在运行",
            }
        await scheduler.stop()
        logger.info("调度器已通过 API 停止（操作者: %s）", _user.sub)
        return {"success": True, "is_running": scheduler.is_running}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("停止调度器失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/pipeline/scheduler/tasks", summary="列出所有调度任务")
async def list_tasks(
    _user: UserToken = Depends(get_current_user),
):
    try:
        scheduler = _get_scheduler_safe()
        tasks = scheduler.list_tasks()
        return {
            "count": len(tasks),
            "tasks": [_serialize_spec(s) for s in tasks],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("列出调度任务失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/pipeline/scheduler/tasks", summary="添加调度任务")
async def add_task(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
):
    try:
        from stockquant.ai.scheduler import ScheduleSpec
        scheduler = _get_scheduler_safe()

        name = payload.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="name 字段必填")

        # 构造 ScheduleSpec，过滤未知字段
        allowed_fields = {
            "name", "level", "interval_seconds",
            "daily_hour", "daily_minute", "symbols", "enabled",
        }
        spec_kwargs = {k: v for k, v in payload.items() if k in allowed_fields}
        spec = ScheduleSpec(**spec_kwargs)
        scheduler.add_task(spec)
        logger.info(
            "调度任务已添加（操作者: %s）: %s level=%s interval=%ss",
            _user.sub, spec.name, spec.level, spec.interval_seconds,
        )
        return {"success": True, "task": _serialize_spec(spec)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("添加调度任务失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/pipeline/scheduler/tasks/{name}", summary="移除调度任务")
async def remove_task(
    name: str,
    _user: UserToken = Depends(get_admin_user),
):
    try:
        scheduler = _get_scheduler_safe()
        removed = scheduler.remove_task(name)
        if not removed:
            raise HTTPException(status_code=404, detail=f"任务 {name} 不存在")
        logger.info("调度任务已移除（操作者: %s）: %s", _user.sub, name)
        return {"success": True, "removed": name}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("移除调度任务失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
