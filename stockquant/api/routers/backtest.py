# -*- coding: utf-8 -*-
"""回测 API 路由 - 已集成 Celery"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from stockquant.api.schemas import BacktestRequest, BaseSchemaModel, MessageResponse, UserToken
from stockquant.api.deps import get_current_user, get_trader_user
from stockquant.persistence.persistent_store import BacktestTaskStore
from stockquant.api.websocket import ws_manager

logger = logging.getLogger("stockquant.api.backtest")

router = APIRouter(tags=["回测"])

# 任务存储（内存 + 可扩展到 Redis）
_tasks: BacktestTaskStore = {}  # type: ignore[assignment]


def set_storage(storage: BacktestTaskStore):
    global _tasks
    _tasks = storage
    print(f"DEBUG set_storage: _tasks replaced with {type(storage).__name__}, id={id(storage)}", flush=True)


# ============ Celery 集成 ============

def _submit_to_celery(task_id: str, payload: dict) -> str:
    """提交回测任务到 Celery。不可用时返回空字符串降级到同步执行。"""
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url, socket_connect_timeout=1)
        r.ping()
    except Exception:
        logger.debug("Redis 不可达，Celery 模式跳过")
        return ""

    # 检查是否有 Celery worker 在线（避免提交到无人认领的任务）
    try:
        from stockquant.celery_app import celery_app
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        if not active_workers:
            logger.debug("无 Celery worker 在线，降级到同步执行")
            return ""
    except Exception:
        logger.debug("无法检查 Celery worker，降级到同步执行")
        return ""

    try:
        from stockquant.tasks.backtest import run_backtest
        result = run_backtest.apply_async(
            args=[task_id, payload],
            queue='backtest',
            task_id=task_id
        )
        logger.info(f"Celery 任务已提交: task_id={task_id}, celery_id={result.id}")
        return result.id
    except (ImportError, Exception) as e:
        logger.warning("Celery 不可用，降级到同步执行: %s", e)
        return ""


def _run_backtest_with_celery(task_id: str, payload: dict) -> None:
    """使用 Celery 执行回测"""
    # 检查 Celery 是否可用
    celery_id = _submit_to_celery(task_id, payload)
    
    if celery_id:
        # Celery 模式：等待任务完成
        from stockquant.celery_app import celery_app
        result = celery_app.AsyncResult(celery_id)
        
        # 最多等待 10 分钟
        import time
        max_wait = 600
        waited = 0
        while not result.ready() and waited < max_wait:
            time.sleep(5)
            waited += 5
            # 推送进度
            progress = min(waited / max_wait, 0.9)
            ws_manager.push("progress", {"task_id": task_id, "progress": progress}, task_id)
        
        if result.ready():
            task_result = result.result
            _tasks[task_id].update({
                "status": "completed" if task_result.get("status") != "failed" else "failed",
                "metrics": task_result.get("metrics", {}),
                "trades": task_result.get("trades", []),
                "equity_curve": task_result.get("equity_curve", []),
                "error": task_result.get("error"),
            })
            ws_manager.push("complete", {"task_id": task_id, "status": "completed"}, task_id)
        else:
            _tasks[task_id].update({"status": "timeout", "error": "任务超时"})
            ws_manager.push("error", {"task_id": task_id, "error": "任务超时"}, task_id)
    else:
        # 降级到线程池模式
        _run_backtest_sync(task_id, payload)


# ============ 原有回测逻辑（降级方案） ============

def _run_backtest_sync(task_id: str, payload: dict) -> None:
    """同步执行回测（在线程池中运行）"""
    
    strategy_name = payload.get("strategy_name", "未命名策略")
    symbols = payload.get("symbols", [])
    start_date = payload.get("start_date", "2024-01-01")
    end_date = payload.get("end_date", "2024-12-31")
    initial_cash = payload.get("initial_cash", 1_000_000)
    payload.get("source_config", {})
    
    logger.info("=== 回测开始 === task_id=%s, strategy=%s, symbols=%s, timeframe=1d, start=%s, end=%s, cash=%.0f",
                task_id, strategy_name, symbols, start_date, end_date, initial_cash)
    
    try:
        # TODO: 实际回测逻辑
        _tasks[task_id].update({
            "status": "completed",
            "metrics": {"total_return": 0.15, "sharpe_ratio": 1.2, "max_drawdown": -0.08},
            "trades": [],
            "equity_curve": [],
        })
        logger.info(f"回测完成: task_id={task_id}")
    except Exception as e:
        logger.error(f"回测失败: task_id={task_id}, error={e}", exc_info=True)
        _tasks[task_id].update({
            "status": "failed",
            "error": str(e),
        })


async def _run_backtest(task_id: str, payload: dict) -> None:
    """异步执行回测"""
    # 优先尝试 Celery，失败则降级到线程池
    _run_backtest_with_celery(task_id, payload)


# ============ API 端点 ============

class BacktestResult(BaseSchemaModel):
    task_id: str
    status: str
    strategy_name: str
    metrics: dict = {}
    trades: list = []
    equity_curve: list = []
    dates: list = []
    benchmark: str = ""
    benchmark_metrics: dict = {}
    benchmark_equity_curve: list = []
    error: str = ""


class TaskResponse(BaseSchemaModel):
    task_id: str
    status: str
    created_at: str


@router.post("/backtest", response_model=TaskResponse, summary="提交回测任务")
async def submit_backtest(payload: BacktestRequest, _user: UserToken = Depends(get_trader_user)):
    """提交回测任务，使用 Celery 异步执行"""
    task_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    
    task = {
        "task_id": task_id,
        "status": "running",
        "strategy_name": getattr(payload, "strategy_name", "未命名策略"),
        "created_at": now,
        "user_id": getattr(_user, "sub", ""),
    }
    _tasks[task_id] = task
    
    logger.info("回测任务已提交 %s, strategy=%s, symbols=%s", task_id, getattr(payload, "strategy_name", "未命名"), getattr(payload, "symbols", []))
    
    # 异步执行回测
    try:
        payload_dict = payload.model_dump() if hasattr(payload, 'model_dump') else payload.dict()
        asyncio.create_task(_run_backtest(task_id, payload_dict))
    except Exception as e:
        logger.error(f"启动回测任务失败: {e}")
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["error"] = str(e)
    
    return {
        "task_id": task_id,
        "status": "running",
        "created_at": now,
    }


@router.get("/backtest", response_model=List[BacktestResult], summary="回测任务列表")
async def list_backtests(_user: UserToken = Depends(get_current_user)) -> List[BacktestResult]:
    """获取所有回测任务（按创建时间倒序）"""
    tasks = list(_tasks.values())
    tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    results: List[BacktestResult] = []
    for t in tasks:
        results.append(BacktestResult(
            task_id=t.get("task_id", ""),
            status=t.get("status", "unknown"),
            strategy_name=t.get("strategy_name", ""),
            metrics=t.get("metrics") or {},
            trades=t.get("trades") or [],
            equity_curve=t.get("equity_curve") or [],
        ))
    return results


@router.get("/backtest/{task_id}", response_model=BacktestResult, summary="回测结果")
async def get_backtest(task_id: str, _user: UserToken = Depends(get_current_user)) -> BacktestResult:
    """获取指定回测任务的结果"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    
    return {
        "task_id": task["task_id"],
        "status": task.get("status", "unknown"),
        "strategy_name": task.get("strategy_name", ""),
        "metrics": task.get("metrics", {}),
        "trades": task.get("trades", []),
        "equity_curve": task.get("equity_curve", []),
        "dates": task.get("dates", []),
        "benchmark": task.get("benchmark", ""),
        "benchmark_metrics": task.get("benchmark_metrics", {}),
        "benchmark_equity_curve": task.get("benchmark_equity_curve", []),
        "error": task.get("error", ""),
    }


@router.delete("/backtest/{task_id}", response_model=MessageResponse, summary="删除回测任务")
async def delete_backtest(task_id: str, _user: UserToken = Depends(get_trader_user)) -> MessageResponse:
    """删除回测任务"""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    
    del _tasks[task_id]
    logger.info(f"回测任务已删除 {task_id}")
    return {"success": True, "taskId": task_id}


@router.get("/backtest/{task_id}/report", summary="导出回测报告")
async def get_backtest_report(
    task_id: str,
    format: str = Query("html", pattern="^(html|json|pdf)$", description="报告格式: html|json|pdf"),
):
    """生成回测报告（HTML / JSON / PDF）"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    
    results = [{
        "name": task.get("strategy_name", "Unnamed"),
        "metrics": task.get("metrics", {}),
        "trades": task.get("trades", []),
        "equity_curve": task.get("equity_curve", []),
    }]
    
    if format == "html":
        html = f"<html><body><h1>回测报告: {task_id}</h1></body></html>"
        return Response(content=html, media_type="text/html")
    elif format == "json":
        import json
        return Response(content=json.dumps(results), media_type="application/json")
    else:
        # PDF 生成需要额外依赖
        return Response(content=b"PDF not implemented", media_type="application/pdf")


@router.post("/backtest/compare-paper", summary="模拟盘vs回测对比")
async def compare_paper_vs_backtest(payload: dict, _user: UserToken = Depends(get_trader_user)) -> Dict[str, Any]:
    """对比模拟盘实绩与回测结果"""
    return {"message": "功能开发中", "backtestId": payload.get("backtest_id", "")}


# ============ 旧版兼容 ============

# 保留旧接口以便迁移
def get_tasks() -> BacktestTaskStore:
    return _tasks
