# -*- coding: utf-8 -*-
"""事件驱动引擎 — F001

核心职责：
1. EventEngine — 事件调度器，支持同步/异步派发
2. Cerebro — 主引擎，流畅API: add_data / add_strategy / run
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Type, TYPE_CHECKING

from stockquant.models.base import Event, EventType
from stockquant.models.bar import BarData
from stockquant.models.order import Order, OrderSide, OrderType, OrderStatus
from stockquant.models.account import Account
from stockquant.models.position import Position
from stockquant.models.trade import TradeData
from stockquant.models.portfolio import Portfolio

if TYPE_CHECKING:
    from stockquant.engine.commission import CommissionInfo
    from stockquant.engine.broker import Broker
    from stockquant.strategy.base import BaseStrategy
    from stockquant.data.feed import DataFeed

logger = logging.getLogger("stockquant.engine")


# ============================================================================
# EventEngine — 事件调度器
# ============================================================================

class EventEngine:
    """
    事件调度器核心类。

    支持：
    - 同步/异步事件派发
    - 按事件类型注册/注销处理器
    - 多线程安全
    """

    def __init__(self, async_mode: bool = False):
        self._handlers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._active = False
        self._queue: list[Event] = []
        self._async_mode = async_mode
        self._executor: Optional[ThreadPoolExecutor] = None

        if async_mode:
            self._executor = ThreadPoolExecutor(max_workers=4)

    def start(self):
        """启动引擎"""
        self._active = True
        logger.info("EventEngine started")

    def stop(self):
        """停止引擎"""
        self._active = False
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
        logger.info("EventEngine stopped")

    def register(self, event_type: EventType, handler: Callable):
        """注册事件处理器"""
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug(f"Registered handler for {event_type.value}")

    def unregister(self, event_type: EventType, handler: Callable):
        """注销事件处理器"""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    def put(self, event: Event):
        """放入事件到队列（同步派发）"""
        self._queue.append(event)
        self._process(event)

    def _process(self, event: Event):
        """处理单个事件"""
        handlers = self._handlers.get(event.type, [])
        if not handlers:
            return
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Handler error for {event.type}: {e}", exc_info=True)

    def run_next(self):
        """从队列取出并处理一个事件"""
        if not self._queue:
            return None
        event = self._queue.pop(0)
        self._process(event)
        return event

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    @property
    def active(self) -> bool:
        return self._active


# ============================================================================
# Cerebro — 主引擎
# ============================================================================

class Cerebro:
    """
    回测主引擎。

    使用示例:
        cerebro = Cerebro(cash=1_000_000)
        cerebro.add_data(DataFeed.baostock(symbols=["sh600519"], ...))
        cerebro.add_strategy(MyStrategy, fast=5, slow=20)
        results = cerebro.run()
        cerebro.show_report(results)
    """

    def __init__(
        self,
        cash: float = 1_000_000.0,
        broker: Optional["Broker"] = None,
        commission: Optional["CommissionInfo"] = None,
        risk_manager: Optional["RiskManager"] = None,
    ):
        self._event_engine = EventEngine()

        self._cash = cash
        self._portfolio = Portfolio(initial_cash=cash, leverage=1.0)

        # 数据源
        self._data_feeds: List["DataFeed"] = []

        # 策略
        self._strategies: List[BaseStrategy] = []

        # Broker
        self._broker = broker

        # 佣金
        self._commission = commission

        # 风控
        self._risk_manager = risk_manager

        # 成交记录
        self._trades: List[TradeData] = []

        # 权益曲线: [(equity, bar_index)]
        self._equity_curve: List[tuple] = []

        # 回测进度
        self._total_bars = 0
        self._processed_bars = 0

        # 兼容旧接口：持仓字典（已迁移到 _portfolio）
        self._positions: Dict[str, "Position"] = {}

    # ------------------------------------------------------------------
    # 流畅API
    # ------------------------------------------------------------------

    def add_data(self, data_feed: "DataFeed") -> "Cerebro":
        """添加数据源"""
        self._data_feeds.append(data_feed)
        return self

    def add_strategy(self, strategy_cls: Type[BaseStrategy], **kwargs) -> "Cerebro":
        """添加策略"""
        self._strategies.append(strategy_cls(cerebro=self, **kwargs))
        return self

    def add_analyzer(self, analyzer: Any) -> "Cerebro":
        """添加分析器（预留）"""
        return self

    @property
    def broker(self) -> Optional["Broker"]:
        return self._broker

    @broker.setter
    def broker(self, broker: "Broker") -> None:
        self._broker = broker

    @property
    def commission(self) -> Optional["CommissionInfo"]:
        return self._commission

    @commission.setter
    def commission(self, commission: "CommissionInfo") -> None:
        self._commission = commission

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------

    @property
    def cash(self) -> float:
        return self._portfolio.cash

    @property
    def account(self):
        return self._portfolio.account

    @property
    def positions(self) -> Dict[str, Position]:
        return self._portfolio.positions

    @property
    def portfolio(self):
        return self._portfolio

    @property
    def trades(self) -> List[TradeData]:
        return self._trades

    @property
    def equity_curve(self) -> List[tuple]:
        return self._equity_curve

    # ------------------------------------------------------------------
    # run()
    # ------------------------------------------------------------------

    def run(self) -> List[dict]:
        """
        运行回测。

        Returns
        -------
        List[dict]
            每个策略一个结果字典，包含 metrics/trades/equity_curve
        """
        self._event_engine.start()

        # 1. 初始化数据源
        for data_feed in self._data_feeds:
            data_feed.start()

        # 2. 初始化策略
        for strategy in self._strategies:
            strategy.initialize(self)
            strategy.on_start()

        # 3. 逐 Bar 驱动
        self._total_bars = sum(len(df) for df in self._data_feeds)
        self._processed_bars = 0
        progress_bar = ProgressBar(self._total_bars)

        max_len = max((len(df) for df in self._data_feeds), default=0)

        for i in range(max_len):
            # 收集当前Bar数据
            bars = {}
            has_data = False
            for data_feed in self._data_feeds:
                if i < len(data_feed):
                    bars[data_feed.symbol] = data_feed[i]
                    has_data = True

            if not has_data:
                break

            # 派发 Bar 事件给策略（通过 on_bar_with_data 设置 _current_bars）
            for strategy in self._strategies:
                strategy.on_bar_with_data(bars)

                # 如果策略有事件引擎注册，也派发 Event
                event = Event(EventType.BAR, data=bars)
                self._event_engine._process(event)

            # 更新权益曲线
            self._portfolio.record_equity()
            self._equity_curve.append((self._portfolio.equity, self._processed_bars))
            self._processed_bars += len(self._data_feeds)
            progress_bar.update(len(self._data_feeds))

            # 每 5 根 Bar 释放一次 T+1 冻结
            if i % 5 == 4:
                self._portfolio.unlock_all_frozen()

        progress_bar.finish()

        # 4. 结束
        for strategy in self._strategies:
            strategy.on_finish()

        for data_feed in self._data_feeds:
            data_feed.stop()

        self._event_engine.stop()

        # 5. 生成结果
        results = []
        for strategy in self._strategies:
            results.append({
                "name": strategy.name,
                "metrics": self._calculate_metrics(strategy),
                "trades": self._trades,
                "equity_curve": self._equity_curve,
            })

        return results

    # ------------------------------------------------------------------
    # 参数优化 (F008)
    # ------------------------------------------------------------------

    def optstrategy(
        self,
        strategy_cls: Type[BaseStrategy],
        param_grid: Dict[str, Any],
        optimizer: str = "grid",
        max_iters: int = 100,
        target: str = "Sharpe Ratio",
        n_jobs: Optional[int] = None,
    ) -> List[dict]:
        """
        参数优化 — 网格搜索或随机搜索。

        Parameters
        ----------
        strategy_cls : Type[BaseStrategy]
            策略类
        param_grid : dict
            {"param_name": [val1, val2, ...], ...}
        optimizer : str
            "grid" | "random"
        max_iters : int
            最大迭代次数（随机搜索时有效）
        target : str
            优化目标指标名（如 "Sharpe Ratio", "Total Return", "Max Drawdown"）
        n_jobs : int or None
            并行线程数，None 则用 CPU 核心数

        Returns
        -------
        List[dict]
            按目标指标排序的参数组合结果（Top 20）
        """
        import itertools
        import random

        if n_jobs is None:
            try:
                from os import cpu_count
                n_jobs = max(1, (cpu_count() or 1) - 1)
            except ImportError:
                n_jobs = 2

        # 生成参数组合
        if optimizer == "grid":
            keys = list(param_grid.keys())
            values = list(param_grid.values())
            param_combos = [dict(zip(keys, combo)) for combo in itertools.product(*values)]
        elif optimizer == "random":
            param_combos = []
            for _ in range(max_iters):
                combo = {}
                for k, v in param_grid.items():
                    if isinstance(v, (list, tuple)):
                        combo[k] = random.choice(v)
                    else:
                        combo[k] = v
                param_combos.append(combo)
        else:
            raise ValueError(f"Unknown optimizer: {optimizer}. Use 'grid' or 'random'.")

        logger.info(f"Parameter optimization: {len(param_combos)} combinations, {n_jobs} workers, target={target}")

        # 并行运行
        results = []
        with ThreadPoolExecutor(max_workers=n_jobs) as executor:
            futures = {}
            for i, params in enumerate(param_combos):
                future = executor.submit(
                    self._run_single_optimization, strategy_cls, params, target, i
                )
                futures[future] = i

            completed = 0
            for future in as_completed(futures):
                completed += 1
                result = future.result()
                if result:
                    results.append(result)
                if completed % 10 == 0 or completed == len(param_combos):
                    logger.info(f"Optimization progress: {completed}/{len(param_combos)}")

        # 按目标指标排序
        def sort_key(r):
            val = r.get("metrics", {}).get(target, 0)
            if isinstance(val, str):
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    val = 0
            return float(val)

        # 如果是回撤类指标，取反（希望回撤越小越好）
        if "Drawdown" in target or "drawdown" in target:
            results.sort(key=sort_key)
        else:
            results.sort(key=sort_key, reverse=True)

        top_n = min(20, len(results))
        logger.info(f"Optimization complete. Top {top_n}/{len(results)} results:")
        for i, r in enumerate(results[:top_n]):
            metrics = r.get("metrics", {})
            target_val = metrics.get(target, "N/A")
            logger.info(f"  #{i+1}: {r['params']} → {target} = {target_val}")

        return results

    def _run_single_optimization(
        self,
        strategy_cls: Type[BaseStrategy],
        params: dict,
        _target: str,
        _index: int,
    ) -> Optional[dict]:
        """运行单组参数回测（用于并行优化）"""
        try:
            # 创建独立引擎实例
            from copy import deepcopy

            temp_cerebro = Cerebro(
                cash=self._cash,
                broker=self._broker,
                commission=self._commission,
                risk_manager=self._risk_manager,
            )
            temp_cerebro._data_feeds = [
                self._clone_feed(feed) for feed in self._data_feeds
            ]
            temp_cerebro.add_strategy(strategy_cls, **params)

            raw_results = temp_cerebro.run()

            if raw_results:
                return {
                    "index": _index,
                    "params": params,
                    "metrics": raw_results[0]["metrics"],
                    "trades": raw_results[0]["trades"],
                    "equity_curve": raw_results[0]["equity_curve"],
                }
        except Exception as e:
            logger.error(f"Optimization run #{_index} failed: {e}", exc_info=True)
        return None

    def _clone_feed(self, feed: "DataFeed") -> "DataFeed":
        """克隆数据源（简化版：直接返回原引用，优化时共享只读数据）"""
        # 注：对于纯只读数据源，共享引用是安全的
        return feed

    # ------------------------------------------------------------------
    # 持仓管理
    # ------------------------------------------------------------------

    def get_position(self, symbol: str) -> Optional[Position]:
        return self._positions.get(symbol)

    def add_position(self, position: Position):
        self._positions[position.symbol] = position

    def update_position_fill(self, symbol: str, quantity: float, price: float, is_today: bool = True):
        """兼容旧接口：委托给 Portfolio"""
        self._portfolio.add_fill(symbol, quantity, price, is_today)

    def unlock_today_frozen(self):
        """兼容旧接口"""
        self._portfolio.unlock_all_frozen()

    @property
    def risk_manager(self):
        return self._risk_manager

    def _calculate_metrics(self, strategy: BaseStrategy) -> dict:
        """计算回测指标（F005）"""
        from stockquant.engine.metrics import BacktestMetrics
        return BacktestMetrics.calculate(
            equity_curve=self._equity_curve,
            trades=self._trades,
            initial_cash=self._cash,
        )

    def show_report(self, results: List[dict]):
        """打印回测报告"""
        for r in results:
            print("\n" + "=" * 70)
            print(f"  Strategy: {r['name']}  |  Equity: {self._portfolio.equity:.2f}")
            print("=" * 70)
            metrics = r["metrics"]
            for k, v in metrics.items():
                if isinstance(v, float):
                    print(f"  {k:35s}: {v:>12.4f}")
                else:
                    print(f"  {k:35s}: {str(v):>12}")
            print(f"  {'Total Trades':35s}: {len(r['trades']):>12}")
            print("=" * 70)


# ============================================================================
# ProgressBar — 进度条
# ============================================================================

class ProgressBar:
    """命令行进度条"""

    def __init__(self, total: int, width: int = 40):
        self.total = total
        self.width = width
        self.current = 0

    def update(self, n: int = 1):
        self.current += n
        if self.total == 0:
            return
        percent = min(1.0, self.current / self.total)
        filled = int(self.width * percent)
        bar = "=" * filled + "-" * (self.width - filled)
        print(f"\rProgress: |{bar}| {percent*100:5.1f}% ({self.current}/{self.total})", end="", flush=True)

    def finish(self):
        print()  # 换行
