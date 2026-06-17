# -*- coding: utf-8 -*-
"""F029 参数优化路由 — 提交/查询/推送进度

已接入 Cerebro.optstrategy() 真实优化引擎。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException

from stockquant.api.websocket import ws_manager

logger = logging.getLogger("stockquant.api.optimize")

router = APIRouter()

# 存储引用（由 main.py 注入）
_optimize_tasks: dict = {}


def set_storage(storage: dict):
    global _optimize_tasks
    _optimize_tasks = storage


# ====================================================================
# 辅助函数（复用 backtest.py 的逻辑）
# ====================================================================

def _get_strategy_map():
    """延迟导入策略模板"""
    from stockquant.strategy.templates import (
        DualMACrossoverStrategy,
        RSIReversalStrategy,
        BollingerBounceStrategy,
        MACDDivergenceStrategy,
        DualThrustStrategy,
        MeanReversionStrategy,
        MomentumStrategy,
    )
    return {
        "DualMACrossover": DualMACrossoverStrategy,
        "DualMACrossoverStrategy": DualMACrossoverStrategy,
        "RSIReversal": RSIReversalStrategy,
        "RSIReversalStrategy": RSIReversalStrategy,
        "BollingerBounce": BollingerBounceStrategy,
        "BollingerBounceStrategy": BollingerBounceStrategy,
        "MACDDivergence": MACDDivergenceStrategy,
        "MACDDivergenceStrategy": MACDDivergenceStrategy,
        "DualThrust": DualThrustStrategy,
        "DualThrustStrategy": DualThrustStrategy,
        "MeanReversion": MeanReversionStrategy,
        "MeanReversionStrategy": MeanReversionStrategy,
        "Momentum": MomentumStrategy,
        "MomentumStrategy": MomentumStrategy,
    }


def _build_slippage(slippage_type: str, slippage_value: Optional[float] = None):
    """构造滑点模型"""
    from stockquant.engine.commission import FixedSlippage, PercentSlippage, AdaptiveSlippage

    if slippage_type == "fixed":
        return FixedSlippage(slippage_value or 0.01)
    elif slippage_type == "percent":
        return PercentSlippage(slippage_value or 0.001)
    elif slippage_type == "adaptive":
        return AdaptiveSlippage()
    return None


def _serialize_optimize_result(result: dict) -> dict:
    """序列化单条优化结果"""
    metrics = result.get("metrics", {})
    # 确保所有指标值可序列化
    safe_metrics = {}
    for k, v in metrics.items():
        if isinstance(v, (int, float, str, bool)):
            safe_metrics[k] = v
        else:
            safe_metrics[k] = str(v)

    return {
        "params": result.get("params", {}),
        "metrics": safe_metrics,
        "index": result.get("index", 0),
    }


def _run_optimize_sync(task_id: str, payload: dict) -> None:
    """同步执行参数优化（在线程池中运行）"""
    from stockquant.engine.cerebro import Cerebro
    from stockquant.engine.broker import BacktestBroker
    from stockquant.engine.commission import CommissionInfo
    from stockquant.engine.risk import RiskManager
    from stockquant.data.providers.baostock_feed import BaoStockFeed

    try:
        # 1. 提取参数
        strategy_name = payload.get("strategy_name", "DualMACrossover")
        symbols = payload.get("symbols", ["sh600519"])
        timeframe = payload.get("timeframe", "1d")
        start_date = payload.get("start_date", "2023-01-01")
        end_date = payload.get("end_date", "2024-12-31")
        cash = payload.get("cash", 1_000_000)

        # 优化参数
        param_grid = payload.get("param_grid", {})
        method = payload.get("method", "grid")
        target_metric = payload.get("target_metric", "Sharpe Ratio")
        max_iters = payload.get("max_iterations", 50)
        n_jobs = payload.get("n_jobs", None)
        train_window = payload.get("train_window", None)
        test_window = payload.get("test_window", None)
        step = payload.get("step", None)

        # 佣金/滑点/风控
        commission_rate = payload.get("commission_rate", 0.00025)
        slippage_type = payload.get("slippage_type", "none")
        slippage_value = payload.get("slippage_value")
        risk_rules = payload.get("risk_rules", {})

        # 2. 获取策略类
        strategy_map = _get_strategy_map()
        strategy_cls = strategy_map.get(strategy_name)
        if strategy_cls is None:
            raise ValueError(f"未知策略: {strategy_name}")

        # 3. 构造数据源
        feed = BaoStockFeed(
            symbols=symbols,
            timeframe=timeframe,
            start=start_date,
            end=end_date,
        )

        # 4. 构造 Cerebro
        commission = CommissionInfo(commission_rate=commission_rate)
        slippage = _build_slippage(slippage_type, slippage_value)
        broker = BacktestBroker(slippage=slippage)
        risk_manager = RiskManager(
            max_position_pct=risk_rules.get("max_position_pct", 0.3),
            max_daily_loss_pct=risk_rules.get("max_daily_loss_pct", 0.05),
            max_drawdown_pct=risk_rules.get("max_drawdown_pct", 0.15),
        )

        cerebro = Cerebro(
            cash=cash,
            broker=broker,
            commission=commission,
            risk_manager=risk_manager,
        )
        cerebro.add_data(feed)

        # 5. 执行优化
        logger.info(f"参数优化开始: {task_id}, 策略={strategy_name}, 方法={method}, 目标={target_metric}")

        results = cerebro.optstrategy(
            strategy_cls,
            param_grid=param_grid,
            optimizer=method,
            max_iters=max_iters,
            target=target_metric,
            n_jobs=n_jobs,
            train_window=train_window,
            test_window=test_window,
            step=step,
        )

        # 6. 序列化结果
        serialized_results = [_serialize_optimize_result(r) for r in results]

        # 7. 最佳结果
        best_result = serialized_results[0] if serialized_results else None

        # 8. 更新任务
        _optimize_tasks[task_id].update({
            "status": "completed",
            "progress": 100,
            "results": serialized_results,
            "best_result": best_result,
            "updated_at": datetime.now().isoformat(),
        })
        logger.info(f"参数优化完成: {task_id}, 结果数={len(serialized_results)}")

    except Exception as e:
        logger.error(f"参数优化失败: {task_id}, 错误={e}", exc_info=True)
        _optimize_tasks[task_id].update({
            "status": "failed",
            "error": str(e),
            "updated_at": datetime.now().isoformat(),
        })


async def _run_optimize(task_id: str, payload: dict) -> None:
    """异步执行参数优化"""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _run_optimize_sync, task_id, payload)
    except Exception as e:
        logger.error(f"参数优化执行异常: {task_id}, {e}", exc_info=True)
        _optimize_tasks[task_id].update({
            "status": "failed",
            "error": str(e),
            "updated_at": datetime.now().isoformat(),
        })

    # 推送完成通知
    task = _optimize_tasks.get(task_id, {})
    await ws_manager.push("complete", {
        "task_id": task_id,
        "status": task.get("status", "unknown"),
        "progress": 100,
        "results_count": len(task.get("results", [])),
        "best_result": task.get("best_result"),
    }, task_id)


# ====================================================================
# 端点
# ====================================================================

@router.post("/backtest/optimize", summary="提交参数优化任务")
async def submit_optimize(payload: dict):
    """提交参数优化任务，异步执行 Cerebro.optstrategy()"""
    task_id = f"OPT-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now().isoformat()

    task = {
        "task_id": task_id,
        "status": "running",
        "strategy_name": payload.get("strategy_name", "未命名策略"),
        "params": payload.get("params", []),
        "param_grid": payload.get("param_grid", {}),
        "method": payload.get("method", "grid"),
        "target_metric": payload.get("target_metric", "Sharpe Ratio"),
        "max_iterations": payload.get("max_iterations", 50),
        "created_at": now,
        "updated_at": now,
        "results": [],
        "best_result": None,
        "progress": 0,
        "error": None,
    }

    _optimize_tasks[task_id] = task
    logger.info(f"参数优化任务已提交: {task_id}")

    # 异步执行优化
    asyncio.create_task(_run_optimize(task_id, payload))

    return {"task_id": task_id, "status": "running", "created_at": now}


@router.get("/backtest/optimize/{task_id}", summary="查询优化状态/结果")
async def get_optimize_status(task_id: str):
    """查询参数优化任务状态和结果"""
    task = _optimize_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"优化任务 {task_id} 不存在")

    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "progress": task["progress"],
        "results": task["results"],
        "best_result": task["best_result"],
        "error": task.get("error"),
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }
