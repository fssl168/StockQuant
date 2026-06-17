# -*- coding: utf-8 -*-
"""F029 回测路由 — 提交/查询/删除/列表

已接入 Cerebro.run() 真实回测引擎。
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from stockquant.analytics.report import ReportGenerator
from stockquant.api.websocket import ws_manager

logger = logging.getLogger("stockquant.api.backtest")

router = APIRouter()

# 存储引用（由 main.py 注入）
_tasks: dict = {}


def set_storage(storage: dict):
    global _tasks
    _tasks = storage


# ====================================================================
# 策略映射
# ====================================================================

def _get_strategy_map():
    """延迟导入策略模板，避免循环依赖"""
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


# ====================================================================
# 辅助函数
# ====================================================================

def _build_slippage(slippage_type: str, slippage_value: Optional[float] = None):
    """构造滑点模型"""
    from stockquant.engine.commission import FixedSlippage, PercentSlippage, AdaptiveSlippage

    if slippage_type == "fixed":
        return FixedSlippage(slippage_value or 0.01)
    elif slippage_type == "percent":
        return PercentSlippage(slippage_value or 0.001)
    elif slippage_type == "adaptive":
        return AdaptiveSlippage()
    return None  # "none"


def _serialize_trade(trade) -> dict:
    """将 TradeData 序列化为 dict"""
    return {
        "trade_id": trade.trade_id,
        "order_id": trade.order_id,
        "symbol": trade.symbol,
        "side": trade.side,
        "price": trade.price,
        "quantity": trade.quantity,
        "commission": trade.commission,
        "slippage": trade.slippage,
        "notional": trade.notional,
    }


def _run_backtest_sync(task_id: str, payload: dict) -> None:
    """同步执行回测（在线程池中运行）"""
    from stockquant.engine.cerebro import Cerebro
    from stockquant.engine.broker import BacktestBroker
    from stockquant.engine.commission import CommissionInfo
    from stockquant.engine.risk import RiskManager
    from stockquant.data.providers.baostock_feed import BaoStockFeed

    try:
        # 1. 提取参数
        strategy_name = payload.get("strategy_name", "DualMACrossover")
        strategy_params = payload.get("strategy_params", {})
        symbols = payload.get("symbols", ["sh600519"])
        timeframe = payload.get("timeframe", "1d")
        start_date = payload.get("start_date", "2023-01-01")
        end_date = payload.get("end_date", "2024-12-31")
        cash = payload.get("cash", 1_000_000)

        # 佣金参数
        commission_rate = payload.get("commission_rate", 0.00025)
        min_commission = payload.get("min_commission", 5.0)
        stamp_tax_rate = payload.get("stamp_tax_rate", 0.0005)
        transfer_fee_rate = payload.get("transfer_fee_rate", 0.00001)

        # 滑点参数
        slippage_type = payload.get("slippage_type", "none")
        slippage_value = payload.get("slippage_value")

        # 风控参数
        risk_rules = payload.get("risk_rules", {})
        max_position_pct = risk_rules.get("max_position_pct", 0.3)
        max_daily_loss_pct = risk_rules.get("max_daily_loss_pct", 0.05)
        max_drawdown_pct = risk_rules.get("max_drawdown_pct", 0.15)

        # 基准参数
        benchmark = payload.get("benchmark", "")

        # 2. 获取策略类
        strategy_map = _get_strategy_map()
        strategy_cls = strategy_map.get(strategy_name)
        if strategy_cls is None:
            available = list(strategy_map.keys())
            raise ValueError(f"未知策略: {strategy_name}，可用策略: {available}")

        # 3. 构造数据源
        feed = BaoStockFeed(
            symbols=symbols,
            timeframe=timeframe,
            start=start_date,
            end=end_date,
        )

        # 4. 构造佣金模型
        commission = CommissionInfo(
            commission_rate=commission_rate,
            min_commission=min_commission,
            stamp_tax_rate=stamp_tax_rate,
            transfer_fee_rate=transfer_fee_rate,
        )

        # 5. 构造滑点模型
        slippage = _build_slippage(slippage_type, slippage_value)

        # 6. 构造 Broker
        broker = BacktestBroker(slippage=slippage)

        # 7. 构造风控
        risk_manager = RiskManager(
            max_position_pct=max_position_pct,
            max_daily_loss_pct=max_daily_loss_pct,
            max_drawdown_pct=max_drawdown_pct,
        )

        # 8. 构造 Cerebro 并运行
        cerebro = Cerebro(
            cash=cash,
            broker=broker,
            commission=commission,
            risk_manager=risk_manager,
        )
        cerebro.add_data(feed)
        cerebro.add_strategy(strategy_cls, **strategy_params)

        logger.info(f"回测开始: {task_id}, 策略={strategy_name}, 标的={symbols}")
        # 设置固定随机种子，确保相同参数产生相同结果（回测确定性）
        random.seed(42)
        results = cerebro.run()

        # 9. 处理结果
        if results:
            result = results[0]
            metrics = result.get("metrics", {})
            trades = [_serialize_trade(t) for t in result.get("trades", [])]
            equity_curve = [float(eq) for eq, _ in result.get("equity_curve", [])]

            # 10. 基准处理
            benchmark_metrics = {}
            benchmark_equity_curve = []
            if benchmark:
                try:
                    benchmark_symbols = {
                        "hs300": "sh000300",
                        "zz500": "sh000905",
                        "cyb": "sz399006",
                    }
                    bench_symbol = benchmark_symbols.get(benchmark, benchmark)
                    bench_feed = BaoStockFeed(
                        symbols=[bench_symbol],
                        timeframe=timeframe,
                        start=start_date,
                        end=end_date,
                    )
                    bench_cerebro = Cerebro(cash=cash)
                    bench_cerebro.add_data(bench_feed)
                    # 使用买入持有策略
                    from stockquant.strategy.templates import DualMACrossoverStrategy
                    bench_cerebro.add_strategy(DualMACrossoverStrategy, fast_period=1, slow_period=999999)
                    bench_results = bench_cerebro.run()
                    if bench_results:
                        benchmark_metrics = bench_results[0].get("metrics", {})
                        benchmark_equity_curve = [float(eq) for eq, _ in bench_results[0].get("equity_curve", [])]
                except Exception as e:
                    logger.warning(f"基准数据获取失败: {e}")

            # 11. 更新任务
            _tasks[task_id].update({
                "status": "completed",
                "metrics": metrics,
                "trades": trades,
                "equity_curve": equity_curve,
                "benchmark_metrics": benchmark_metrics,
                "benchmark_equity_curve": benchmark_equity_curve,
                "updated_at": datetime.now().isoformat(),
                "error": None,
            })
            logger.info(f"回测完成: {task_id}, 指标数={len(metrics)}, 交易数={len(trades)}")
        else:
            _tasks[task_id].update({
                "status": "completed",
                "metrics": {},
                "trades": [],
                "equity_curve": [],
                "updated_at": datetime.now().isoformat(),
                "error": "回测无结果",
            })

    except Exception as e:
        logger.error(f"回测失败: {task_id}, 错误={e}", exc_info=True)
        _tasks[task_id].update({
            "status": "failed",
            "error": str(e),
            "updated_at": datetime.now().isoformat(),
        })


async def _run_backtest(task_id: str, payload: dict) -> None:
    """异步执行回测（在线程池中运行同步代码）"""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _run_backtest_sync, task_id, payload)
    except Exception as e:
        logger.error(f"回测执行异常: {task_id}, {e}", exc_info=True)
        _tasks[task_id].update({
            "status": "failed",
            "error": str(e),
            "updated_at": datetime.now().isoformat(),
        })

    # 推送完成通知
    task = _tasks.get(task_id, {})
    await ws_manager.push("complete", {
        "task_id": task_id,
        "status": task.get("status", "unknown"),
        "metrics_count": len(task.get("metrics", {})),
        "trades_count": len(task.get("trades", [])),
    }, task_id)


# ====================================================================
# 端点
# ====================================================================

@router.post("/backtest", response_model=dict, summary="提交回测任务")
async def submit_backtest(payload: dict):
    """提交回测任务，异步执行 Cerebro.run()"""
    task_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    task = {
        "task_id": task_id,
        "status": "running",
        "strategy_name": payload.get("strategy_name", "未命名策略"),
        "strategy_code": payload.get("strategy_code", ""),
        "strategy_params": payload.get("strategy_params", {}),
        "symbols": payload.get("symbols", []),
        "start_date": payload.get("start_date", ""),
        "end_date": payload.get("end_date", ""),
        "cash": payload.get("cash", 1_000_000),
        "commission_type": payload.get("commission_type", "ashare"),
        "slippage_type": payload.get("slippage_type", "none"),
        "benchmark": payload.get("benchmark", ""),
        "created_at": now,
        "updated_at": now,
        "metrics": {},
        "trades": [],
        "equity_curve": [],
        "benchmark_metrics": {},
        "benchmark_equity_curve": [],
        "error": None,
    }

    _tasks[task_id] = task
    logger.info(f"回测任务已提交: {task_id}")

    # 异步执行回测
    asyncio.create_task(_run_backtest(task_id, payload))

    return {
        "task_id": task_id,
        "status": "running",
        "created_at": now,
    }


@router.get("/backtest", response_model=list[dict], summary="回测任务列表")
async def list_backtests():
    """获取所有回测任务"""
    return list(_tasks.values())


@router.get("/backtest/{task_id}", response_model=dict, summary="回测结果")
async def get_backtest(task_id: str):
    """获取指定回测任务的结果"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "strategy_name": task["strategy_name"],
        "metrics": task["metrics"],
        "trades": task["trades"],
        "equity_curve": task["equity_curve"],
        "benchmark_metrics": task.get("benchmark_metrics", {}),
        "benchmark_equity_curve": task.get("benchmark_equity_curve", []),
        "error": task["error"],
    }


@router.delete("/backtest/{task_id}", response_model=dict, summary="删除回测任务")
async def delete_backtest(task_id: str):
    """删除回测任务"""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    del _tasks[task_id]
    logger.info(f"回测任务已删除: {task_id}")
    return {"success": True, "task_id": task_id}


@router.get("/backtest/{task_id}/report", summary="导出回测报表")
async def get_backtest_report(
    task_id: str,
    format: str = Query("html", regex="^(html|json|pdf)$", description="报表格式: html|json|pdf"),
):
    """生成回测报表（HTML / JSON / PDF）"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    results = [{
        "name": task.get("strategy_name", "Unnamed"),
        "metrics": task.get("metrics", {}),
        "trades": task.get("trades", []),
        "equity_curve": task.get("equity_curve", []),
    }]

    if format == "json":
        json_str = ReportGenerator.generate_json(results)
        return Response(content=json_str, media_type="application/json")

    if format == "pdf":
        try:
            pdf_bytes = ReportGenerator.generate_pdf(results)
        except ImportError as e:
            raise HTTPException(status_code=501, detail=str(e))
        filename = f"backtest-report-{task_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    html = ReportGenerator.generate_html(results)
    return Response(content=html, media_type="text/html")
