# -*- coding: utf-8 -*-
"""事件驱动引擎 — F001

核心职责：
1. EventEngine — 事件调度器，支持同步/异步派发
2. Cerebro — 主引擎，流畅API: add_data / add_strategy / run
"""


import logging
import itertools
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Type, TYPE_CHECKING

from stockquant.models.base import Event, EventType
from stockquant.models.position import Position
from stockquant.models.trade import TradeData
from stockquant.models.portfolio import Portfolio

if TYPE_CHECKING:
    from stockquant.engine.commission import CommissionInfo
    from stockquant.engine.broker import Broker
    from stockquant.engine.risk import RiskManager
    from stockquant.data.feed import DataFeed

from stockquant.strategy.base import BaseStrategy

logger = logging.getLogger("stockquant.engine")


# ============================================================================
# EventEngine — 事件调度器
# ============================================================================

class _StrategyDataWrapper:
    """策略 self.data 包装器 — 从 DataFrame 提供 close 等序列供指标计算使用。

    设计约定：
    - 直接迭代/索引 self.data → 返回 close 价序列（兼容 EMA(self.data, ...) 等指标调用）
    - self.data.close / self.data['close'] → 返回指定列的列表
    """

    def __init__(self, df):
        import pandas as pd
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Expected DataFrame, got {type(df)}")
        self._df = df
        # 预取 close 列为列表（最常用路径）
        self._close = df["close"].tolist()

    @property
    def close(self):
        """收盘价列表"""
        return self._close

    @property
    def open(self):
        """开盘价列表"""
        col = "open" if "open" in self._df.columns else "Open"
        return self._df[col].tolist()

    @property
    def high(self):
        """最高价列表"""
        return self._df["high"].tolist()

    @property
    def low(self):
        """最低价列表"""
        return self._df["low"].tolist()

    @property
    def volume(self):
        """成交量列表"""
        return self._df["volume"].tolist()

    def __len__(self):
        return len(self._close)

    def __iter__(self):
        """迭代返回 close 价（使 np.array(self.data) 得到一维 float 数组）"""
        return iter(self._close)

    def __getitem__(self, key):
        """整数索引 → close 价；字符串键 → 对应列列表"""
        if isinstance(key, int):
            return self._close[key]
        if isinstance(key, str) and key in self._df.columns:
            return self._df[key].tolist()
        raise KeyError(f"Key '{key}' not found. Columns: {list(self._df.columns)}")


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
            # 注入 self.data 供策略模板在 on_start() 中使用（如 EMA(self.data, ...)）
            if self._data_feeds:
                feed = self._data_feeds[0]
                df = feed.get_dataframe()
                if df is not None and not df.empty:
                    strategy.data = _StrategyDataWrapper(df)
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
            # 从 broker 获取成交记录（如果可用）
            trades = self._trades.copy() if self._trades else []
            if self._broker and hasattr(self._broker, 'trade_log'):
                trades = self._broker.trade_log
            
            results.append({
                "name": strategy.name,
                "metrics": self._calculate_metrics(strategy),
                "trades": trades,
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
        train_window: Optional[int] = None,
        test_window: Optional[int] = None,
        step: Optional[int] = None,
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
        elif optimizer == "walkforward":
            param_combos = []  # walkforward generates its own combos via _run_walkforward()
        else:
            raise ValueError(f"Unknown optimizer: {optimizer}. Use 'grid', 'random', or 'walkforward'.")

        # Walk-Forward: 需要特殊处理（不并行，需滚动窗口）
        if optimizer == "walkforward":
            return self._run_walkforward(strategy_cls, param_grid, target, n_jobs,
                                         train_window, test_window, step)

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

    def _run_walkforward(
        self,
        strategy_cls: Type[BaseStrategy],
        param_grid: Dict[str, Any],
        target: str,
        n_jobs: int,
        train_window: Optional[int],
        test_window: Optional[int],
        step: Optional[int],
    ) -> List[dict]:
        """
        Walk-Forward 滚动窗口优化。

        流程：
        1. 用第一个数据窗口（训练集）网格搜索最优参数
        2. 在下一个数据窗口（测试集）验证
        3. 窗口滚动，重复步骤 1-2
        4. 汇总所有窗口的结果，取测试集表现最优的参数
        """

        # 获取数据长度
        if not self._data_feeds:
            raise ValueError("No data feeds for Walk-Forward optimization")

        total_bars = len(self._data_feeds[0])

        # 默认窗口大小
        if train_window is None:
            train_window = min(252, total_bars // 3)  # 至少 1 年日线
        if test_window is None:
            test_window = min(63, total_bars // 10)  # 约 1 季度
        if step is None:
            step = max(1, test_window // 2)

        if total_bars < train_window + test_window:
            raise ValueError(
                f"Data too short: {total_bars} bars < "
                f"{train_window} (train) + {test_window} (test)"
            )

        logger.info(
            f"Walk-Forward: train={train_window}, test={test_window}, "
            f"step={step}, total={total_bars} bars"
        )

        all_results = []
        window_idx = 0

        # 滚动窗口
        train_start = 0
        while train_start + train_window + test_window <= total_bars:
            train_end = train_start + train_window
            test_end = train_end + test_window

            # 1. 在训练集上网格搜索
            train_param_combos = self._generate_combos(param_grid)
            best_params = None
            best_score = float("-inf")
            best_train_metrics = None

            for params in train_param_combos:
                result = self._run_single_optimization(
                    strategy_cls, params, target, window_idx
                )
                if result:
                    score = self._extract_target(result["metrics"], target)
                    if score > best_score:
                        best_score = score
                        best_params = params
                        best_train_metrics = result["metrics"]

            if best_params is None:
                train_start += step
                window_idx += 1
                continue

            # 2. 在测试集上验证
            test_cerebro = Cerebro(
                cash=self._cash,
                broker=self._broker,
                commission=self._commission,
                risk_manager=self._risk_manager,
            )
            for feed in self._data_feeds:
                test_feed = self._slice_feed(feed, train_end, test_end)
                test_cerebro.add_data(test_feed)
            test_cerebro.add_strategy(strategy_cls, **best_params)

            test_results = test_cerebro.run()
            test_metrics = test_results[0]["metrics"] if test_results else {}

            # 3. 汇总结果
            all_results.append({
                "window": window_idx + 1,
                "params": best_params,
                "train_metrics": best_train_metrics,
                "test_metrics": test_metrics,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": train_end,
                "test_end": test_end,
            })

            logger.info(
                f"  Window {window_idx+1}: best params={best_params}, "
                f"train_{target}={self._extract_target(best_train_metrics, target):.4f}, "
                f"test_{target}={self._extract_target(test_metrics, target):.4f}"
            )

            train_start += step
            window_idx += 1

        # 4. 汇总：取测试集表现最好的参数
        if all_results:
            for r in all_results:
                r["test_score"] = self._extract_target(r["test_metrics"], target)

            # 按测试集得分排序，取 Top 1
            all_results.sort(key=lambda x: x["test_score"], reverse=True)
            logger.info(
                f"Walk-Forward complete. {len(all_results)} windows. "
                f"Best: window={all_results[0]['window']}, "
                f"params={all_results[0]['params']}"
            )

        return all_results

    def _generate_combos(self, param_grid: Dict[str, Any]) -> List[dict]:
        """生成参数组合列表"""
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        return [dict(zip(keys, combo)) for combo in itertools.product(*values)]

    def _extract_target(self, metrics: dict, target: str) -> float:
        """提取目标指标值"""
        val = metrics.get(target, 0)
        if isinstance(val, str):
            try:
                val = float(val)
            except (ValueError, TypeError):
                val = 0
        return float(val)

    def _slice_feed(self, feed: "DataFeed", start: int, end: int) -> "DataFeed":
        """切片数据源（仅取 start:end 范围）"""
        import tempfile
        from stockquant.data.providers.csv_feed import CSVFeed

        # 获取完整 DataFrame，切片后写入临时文件
        df = feed.get_dataframe()
        sliced = df.iloc[start:end].copy()

        if sliced.empty:
            raise ValueError(f"Sliced feed is empty: [{start}:{end}]")

        # 写入临时 CSV 文件
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        )
        tmp.close()
        sliced.to_csv(tmp.name, index=True)

        return CSVFeed(
            filepath=tmp.name,
            symbol=feed.symbol,
            timeframe=feed.timeframe,
        )

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
        """
        克隆数据源用于并行优化。

        对于只读 DataFeed，共享引用是安全的（数据不可变）。
        但若 feed 有状态（如内部缓存），则创建浅拷贝隔离状态。
        """
        import copy
        try:
            # 优先尝试 deepcopy
            cloned = copy.deepcopy(feed)
            return cloned
        except Exception:
            # deepcopy 失败（某些对象不可序列化），返回原引用
            # 对于只读数据源，共享引用是安全的
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
        # 使用 broker 的实际成交记录
        trades = self._trades.copy() if self._trades else []
        if self._broker and hasattr(self._broker, 'trade_log'):
            trades = self._broker.trade_log
        return BacktestMetrics.calculate(
            equity_curve=self._equity_curve,
            trades=trades,
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
