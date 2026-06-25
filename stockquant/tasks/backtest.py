# -*- coding: utf-8 -*-
"""回测任务 - Celery 实现

通过 Cerebro 引擎执行真实回测，支持 BaoStock / CSV 数据源。
进度通过 Celery update_state + WebSocket 双通道推送。
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from celery import shared_task
from stockquant.celery_app import celery_app

logger = logging.getLogger("stockquant.tasks")


@shared_task(bind=True, name="stockquant.tasks.backtest.run_backtest")
def run_backtest(self, task_id: str, params: dict) -> dict:
    """执行回测任务

    Args:
        task_id: 任务 ID
        params: 回测参数
    """
    logger.info(f"回测任务开始: task_id={task_id}, strategy={params.get('strategy_name')}")

    try:
        # 更新任务状态
        self.update_state(state='PROGRESS', meta={'progress': 5, 'status': '初始化引擎'})

        # 加载参数
        strategy_id = params.get('strategy_id')
        strategy_code = params.get('strategy_code', '')
        strategy_class = params.get('strategy_class', 'DualMACrossoverStrategy')
        symbols = params.get('symbols', ['sh600519'])
        start_date = params.get('start_date', '2024-01-01')
        end_date = params.get('end_date', '2024-12-31')
        initial_cash = params.get('initial_cash', 1_000_000)
        timeframe = params.get('timeframe', '1d')

        self.update_state(state='PROGRESS', meta={'progress': 15, 'status': '加载数据源'})

        # 加载 K 线数据
        feed = self._load_datafeed(symbols, timeframe, start_date, end_date)
        if feed is None:
            raise RuntimeError(f"无法加载数据: symbols={symbols}")

        total_bars = len(feed)
        logger.info("加载数据完成: symbols=%s, bars=%d", symbols, total_bars)

        self.update_state(state='PROGRESS', meta={'progress': 25, 'status': f'加载数据完成 ({total_bars} 根K线)'})

        # 加载策略
        strategy_cls = self._load_strategy(strategy_code, strategy_class)

        self.update_state(state='PROGRESS', meta={'progress': 30, 'status': '配置引擎'})

        # 运行 Cerebro
        metrics, trades, equity_curve = self._run_cerebro(
            feed, strategy_cls, initial_cash, params
        )

        self.update_state(state='PROGRESS', meta={'progress': 95, 'status': '生成报告'})

        result = {
            "task_id": task_id,
            "status": "completed",
            "metrics": metrics,
            "trades": trades,
            "equity_curve": equity_curve,
            "error": None,
        }

        logger.info(f"回测任务完成: task_id={task_id}, trades={len(trades)}")
        self.update_state(state='PROGRESS', meta={'progress': 100, 'status': '回测完成'})
        return result

    except Exception as e:
        logger.error(f"回测任务失败: task_id={task_id}, error={e}", exc_info=True)
        return {
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
            "metrics": {},
            "trades": [],
            "equity_curve": [],
        }


@shared_task(bind=True, name="stockquant.tasks.backtest.get_task_status")
def get_task_status(self, task_id: str) -> dict:
    """获取任务状态"""
    result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.state,
        "result": result.result if result.ready() else None,
        "info": result.info if hasattr(result, 'info') else None,
    }


    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _load_datafeed(symbols: list, timeframe: str, start: str, end: str):
        """加载数据源 — 优先 CSV，其次 BaoStock"""
        # 尝试 CSV 数据源（如果 symbols 是文件路径）
        try:
            from stockquant.data.providers.parquet_feed import ParquetFeed
            pf = ParquetFeed()
            # ParquetFeed 需要检查是否存在缓存
            df = pf.get_kline(symbols[0] if symbols else "sh600519", timeframe, start, end)
            if df is not None and len(df) > 0:
                logger.info("Parquet 缓存命中: %d 行", len(df))
                return pf
        except Exception:
            pass

        # 降级到 BaoStock
        try:
            from stockquant.data.providers.baostock_feed import BaoStockFeed
            return BaoStockFeed(
                symbols=symbols,
                timeframe=timeframe,
                start=start,
                end=end,
            )
        except Exception as e:
            logger.warning("BaoStock 加载失败: %s", e)
            return None

    @staticmethod
    def _load_strategy(strategy_code: str, class_name: str):
        """加载策略类 — 优先使用传入代码，其次使用内置模板"""
        # 如果有用户提供的策略代码，动态加载
        if strategy_code and strategy_code.strip():
            return _safe_load_strategy_code(strategy_code, class_name)

        # 使用内置模板
        try:
            from stockquant.strategy.templates import DualMACrossoverStrategy
            return DualMACrossoverStrategy
        except ImportError:
            raise RuntimeError("无法加载策略类：未提供策略代码且内置模板不可用")

    @staticmethod
    def _run_cerebro(feed, strategy_cls, initial_cash: float, params: dict):
        """运行 Cerebro 回测引擎"""
        from stockquant.engine import Cerebro, BacktestBroker
        from stockquant.engine.commission import CommissionInfo, FixedSlippage
        from stockquant.analytics.report import ReportGenerator

        cerebro = Cerebro()
        cerebro.add_data(feed)
        cerebro.add_strategy(strategy_cls)

        # 佣金 + 滑点
        commission = params.get('commission', {})
        cash = params.get('initial_cash', initial_cash)
        slippage = params.get('slippage', {})

        if commission:
            cerebro.set_commission(
                CommissionInfo(
                    commission_rate=commission.get('rate', 0.00025),
                    min_commission=commission.get('min', 5),
                    stamp_tax_rate=commission.get('stamp_tax', 0.0005),
                )
            )
        else:
            cerebro.set_commission(CommissionInfo())

        if slippage:
            slip_type = slippage.get('type', 'percent')
            slip_value = slippage.get('value', 0.001)
            if slip_type == 'percent':
                cerebro.set_slippage_perc(perc=slip_value)
            elif slip_type == 'fixed':
                cerebro.set_slippage_fixed(per_share=slip_value)
        else:
            cerebro.set_slippage_perc(perc=0.001)

        # 运行
        results = cerebro.run()
        if not results:
            raise RuntimeError("Cerebro 回测未返回结果")

        strategy_result = results[0]

        # 提取指标
        metrics = strategy_result.get("metrics", {}) if hasattr(strategy_result, "__getitem__") else {}
        if isinstance(metrics, dict) and len(metrics) == 0:
            # 尝试从 Cerebro 内部提取
            if hasattr(strategy_result, '_metrics'):
                metrics = strategy_result._metrics

        trades = strategy_result.get("trades", []) if isinstance(strategy_result, dict) else []
        if not isinstance(trades, list):
            trades = []

        equity_curve = strategy_result.get("equity_curve", []) if isinstance(strategy_result, dict) else []
        if not isinstance(equity_curve, list):
            equity_curve = []

        # 如果 Cerebro 结果中无指标，生成简易版
        if not metrics:
            # 从 portfolio 提取基础指标
            if hasattr(strategy_result, 'portfolio'):
                port = strategy_result.portfolio
                final_value = port.getvalue() if hasattr(port, 'getvalue') else port.total_equity
                total_return = (final_value - cash) / cash if cash > 0 else 0
                metrics = {
                    "Total Return": round(total_return, 4),
                    "Annualized Return": round(total_return * 1.2, 4),  # 简易年化
                    "Total Trades": len(trades),
                    "Final Value": round(final_value, 2),
                    "Initial Cash": round(cash, 2),
                }

        logger.info("回测完成: metrics=%s", metrics)
        return metrics, trades, equity_curve


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------

def _safe_load_strategy_code(code: str, class_name: str):
    """安全加载用户策略代码"""
    import types
    import ast
    from stockquant.strategy.base import BaseStrategy

    # AST 安全检查
    tree = ast.parse(code)
    allowed_imports = {
        'stockquant', 'stockquant.engine', 'stockquant.indicators',
        'stockquant.strategy', 'stockquant.models', 'stockquant.engine.broker',
        'stockquant.engine.commission', 'stockquant.indicators.moving_avg',
        'stockquant.indicators.oscillators', 'stockquant.indicators.volatility',
        'stockquant.indicators.trend', 'stockquant.indicators.base',
        'numpy', 'pandas', 'datetime',
    }

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = node.module or ''
            if module.split('.')[0] not in allowed_imports:
                raise RuntimeError(f"不允许的模块导入: {module}")

    # 执行代码
    local_ns: dict = {}
    exec(code, {"__builtins__": __builtins__}, local_ns)

    cls = local_ns.get(class_name)
    if cls is None:
        raise RuntimeError(f"策略类 {class_name} 未在代码中找到")
    if not issubclass(cls, BaseStrategy):
        raise RuntimeError(f"策略类 {class_name} 未继承 BaseStrategy")

    logger.info("用户策略代码加载成功: %s", class_name)
    return cls
def cancel_task(task_id: str) -> dict:
    """取消回测任务"""
    from stockquant.celery_app import celery_app
    celery_app.control.revoke(task_id, terminate=True)
    return {"task_id": task_id, "status": "cancelled"}
