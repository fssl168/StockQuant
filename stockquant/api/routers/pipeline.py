# -*- coding: utf-8 -*-
"""F020 AI 信息管线 API — /api/pipeline"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Query

from stockquant.api.deps import get_current_user, get_admin_user
from stockquant.api.schemas import UserToken
from stockquant.ai.pipeline_orchestrator import InformationProcessingPipeline
from stockquant.ai.memory.system import MemorySystem

router = APIRouter(tags=["AI 信息管线"])
logger = logging.getLogger("stockquant.api.pipeline")

# 模块级单例
_pipeline: Optional[InformationProcessingPipeline] = None
_running_tasks: Dict[str, Dict[str, Any]] = {}

_default_config: Dict[str, Any] = {
    "collect_interval_sec": 300,
    "denoise_source_credit_threshold": 0.6,
    "denoise_timeliness_hours": 24,
    "summarize_period": "daily",
    "elevate_min_articles": 5,
    "strict_mode": False,
}


def init_pipeline(pipeline: InformationProcessingPipeline) -> None:
    """由 main.py 注入"""
    global _pipeline
    _pipeline = pipeline


@router.get("/pipeline/config", summary="获取管线配置")
async def get_config(
    _user: UserToken = Depends(get_current_user),
):
    return _default_config


@router.put("/pipeline/config", summary="更新管线配置")
async def update_config(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
):
    for key, value in payload.items():
        if key in _default_config:
            _default_config[key] = value
    return {"success": True, "config": _default_config}


@router.post("/pipeline/run", summary="运行完整信息处理管线")
async def run_pipeline(
    payload: Dict[str, Any],
    bg: BackgroundTasks,
    _user: UserToken = Depends(get_admin_user),
):
    symbols = payload.get("symbols", [])
    if not symbols:
        raise HTTPException(status_code=400, detail="symbols 不能为空")
    sources = payload.get("sources", ["news_searcher"])
    task_id = f"PIPE-{uuid.uuid4().hex[:8].upper()}"
    _running_tasks[task_id] = {
        "status": "queued",
        "created_at": datetime.now().isoformat(),
        "symbols": symbols,
        "sources": sources,
    }

    def _execute():
        _running_tasks[task_id]["status"] = "running"
        try:
            result = _pipeline.run(symbols=symbols, sources=sources)
            _running_tasks[task_id].update({
                "status": "completed",
                "result": result,
                "completed_at": datetime.now().isoformat(),
            })
            logger.info("Pipeline task %s completed: %d articles", task_id, result.get("articles_processed", 0))
        except Exception as e:
            logger.error("Pipeline task %s failed: %s", task_id, e)
            _running_tasks[task_id].update({
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now().isoformat(),
            })

    bg.add_task(_execute)
    return {"task_id": task_id, "status": "queued", "message": "管线任务已排队"}


@router.post("/pipeline/collect", summary="仅执行采集阶段")
async def run_collect(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
):
    symbols = payload.get("symbols", [])
    if not symbols:
        raise HTTPException(status_code=400, detail="symbols 不能为空")
    sources = payload.get("sources", ["news_searcher"])
    task_id = f"COL-{uuid.uuid4().hex[:8].upper()}"
    _running_tasks[task_id] = {
        "status": "queued",
        "created_at": datetime.now().isoformat(),
        "symbols": symbols,
    }

    def _execute():
        _running_tasks[task_id]["status"] = "running"
        try:
            from stockquant.ai.pipeline.collection import CollectionStage
            stage = CollectionStage()
            from stockquant.ai.pipeline.collection import CollectionEvent
            event = CollectionEvent(symbols=symbols, sources=sources)
            articles = stage.execute(event)
            _running_tasks[task_id].update({
                "status": "completed",
                "articles_count": len(articles),
                "completed_at": datetime.now().isoformat(),
            })
        except Exception as e:
            logger.error("Collect task %s failed: %s", task_id, e)
            _running_tasks[task_id].update({
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now().isoformat(),
            })

    import asyncio

    asyncio.create_task(_execute())
    return {"task_id": task_id, "status": "running"}


@router.get("/pipeline/status/{task_id}", summary="获取管线运行状态")
async def get_task_status(
    task_id: str,
    _user: UserToken = Depends(get_current_user),
):
    task = _running_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return task


@router.get("/pipeline/status", summary="获取管线所有运行任务")
async def list_tasks(
    _user: UserToken = Depends(get_current_user),
):
    return list(_running_tasks.values())
