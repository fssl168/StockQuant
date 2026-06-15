# -*- coding: utf-8 -*-
"""F030 定时调度器 — 基于 schedule 库 + 交易日检查"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """定时任务定义"""

    name: str
    cron_expression: str
    task_fn: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    is_running: bool = False


class TradingCalendar:
    """简易交易日日历（内建 fallback，无需外部数据源）。

    MVP 阶段：使用中国 A 股常见休市规则近似判断。
    生产环境应替换为真实节假日数据。
    """

    # 2024-2026 中国 A 股主要节假日（实际日期可能调整）
    HOLIDAYS = frozenset([
        # 2024
        date(2024, 1, 1), date(2024, 2, 10), date(2024, 2, 11),
        date(2024, 2, 12), date(2024, 2, 13), date(2024, 2, 14),
        date(2024, 4, 4), date(2024, 4, 5), date(2024, 4, 6),
        date(2024, 5, 1), date(2024, 5, 2), date(2024, 5, 3),
        date(2024, 5, 4), date(2024, 5, 5),
        date(2024, 6, 10), date(2024, 6, 11), date(2024, 6, 12),
        date(2024, 9, 15), date(2024, 9, 16), date(2024, 9, 17),
        date(2024, 10, 1), date(2024, 10, 2), date(2024, 10, 3),
        date(2024, 10, 4), date(2024, 10, 5), date(2024, 10, 6),
        date(2024, 10, 7),
        # 2025
        date(2025, 1, 1), date(2025, 1, 28), date(2025, 1, 29),
        date(2025, 1, 30), date(2025, 1, 31), date(2025, 2, 1),
        date(2025, 2, 2), date(2025, 2, 3), date(2025, 2, 4),
        date(2025, 4, 4), date(2025, 4, 5), date(2025, 4, 6),
        date(2025, 5, 1), date(2025, 5, 2), date(2025, 5, 3),
        date(2025, 5, 4), date(2025, 5, 5),
        date(2025, 5, 31), date(2025, 6, 1), date(2025, 6, 2),
        date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3),
        date(2025, 10, 4), date(2025, 10, 5), date(2025, 10, 6),
        date(2025, 10, 7),
        # 2026
        date(2026, 1, 1), date(2026, 2, 17), date(2026, 2, 18),
        date(2026, 2, 19), date(2026, 2, 20), date(2026, 2, 21),
        date(2026, 2, 22), date(2026, 2, 23), date(2026, 4, 5),
        date(2026, 4, 6), date(2026, 5, 1), date(2026, 5, 2),
        date(2026, 5, 3), date(2026, 5, 4), date(2026, 5, 5),
        date(2026, 6, 19), date(2026, 6, 20), date(2026, 6, 21),
        date(2026, 9, 15), date(2026, 9, 16), date(2026, 9, 17),
        date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3),
        date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 6),
        date(2026, 10, 7),
    ])

    def __init__(self, market: str = 'CN') -> None:
        self.market = market

    def is_trading_day(self, d: date) -> bool:
        """判断是否为交易日（排除节假日和周末）"""
        # 周六(5) / 周日(6)
        if d.weekday() >= 5:
            return False
        if d in self.HOLIDAYS:
            return False
        return True


class StockScheduler:
    """StockQuant 定时调度器。

    基于 ``schedule`` 库，增加交易日检查。
    只在交易日内执行任务。

    Usage:
        scheduler = StockScheduler()
        scheduler.add_task("daily_backtest", "0 16 * * 1-5", run_daily_backtest, args=(symbol,))
        scheduler.start()
    """

    def __init__(self, market: str = 'CN') -> None:
        self._calendar = TradingCalendar(market=market)
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def add_task(self, name: str, cron: str, fn: Callable,
                 args: tuple = (), kwargs: dict = None) -> None:
        """添加定时任务。

        Parameters
        ----------
        name : str
            任务名称（唯一标识）
        cron : str
            简单 cron 表达式："minute hour day_of_week month day_of_week"
            例如 "0 16 * * 1-5" 表示每周一至周五 16:00
        fn : Callable
            任务函数
        args : tuple
            位置参数
        kwargs : dict, optional
            关键字参数
        """
        import schedule

        if name in self._tasks:
            logger.warning(f"Task '{name}' already exists, replacing")
            old_cron = self._tasks[name].cron_expression
            schedule.clear(old_cron)

        kwargs = kwargs or {}
        self._tasks[name] = ScheduledTask(
            name=name,
            cron_expression=cron,
            task_fn=fn,
            args=args,
            kwargs=kwargs,
        )

        # 注册到 schedule 库
        parts = cron.split()
        if len(parts) == 5:
            minute, hour, _, _, dow = parts
            schedule.every().day.at(f"{hour}:{minute.zfill(2)}").do(
                self._wrap_task, name
            ).tag(dow)
            logger.info(f"Added task '{name}': cron={cron}")
        else:
            # Fallback: use schedule's simpler interface
            schedule.every().day.at(f"{hour.split(':')[0] if len(parts) >= 2 else '0'}:{parts[0].zfill(2)}").do(
                self._wrap_task, name
            )
            logger.info(f"Added task '{name}': cron={cron} (simplified)")

    def remove_task(self, name: str) -> bool:
        """移除定时任务。

        Returns
        -------
        bool — 是否成功移除
        """
        import schedule

        if name not in self._tasks:
            return False

        task = self._tasks.pop(name)
        schedule.clear(name)
        logger.info(f"Removed task '{name}'")
        return True

    def start(self) -> None:
        """启动调度器（后台线程）"""
        if self._running:
            logger.warning("Scheduler already running")
            return

        import schedule

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="stockquant-scheduler")
        self._thread.start()
        logger.info("StockScheduler started")

    def stop(self) -> None:
        """停止调度器"""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("StockScheduler stopped")

    def _wrap_task(self, name: str) -> None:
        """包装任务执行，含交易日检查和异常处理"""
        import schedule

        task = self._tasks.get(name)
        if not task:
            return

        today = date.today()
        if not self._calendar.is_trading_day(today):
            logger.debug(f"{today} is not a trading day, skipping task '{name}'")
            # 清除该调度点的待执行任务，避免 schedule 延迟执行
            schedule.clear(name)
            return

        try:
            task.is_running = True
            logger.info(f"Executing task '{name}'")
            task.task_fn(*task.args, **task.kwargs)
            logger.info(f"Task '{name}' completed")
        except Exception:
            logger.exception(f"Task '{name}' failed")
        finally:
            task.is_running = False

    def _run_loop(self) -> None:
        """调度循环：每秒检查待执行任务"""
        while self._running:
            try:
                import schedule
                schedule.run_pending()
            except Exception:
                logger.exception("Error in scheduler loop")
            time.sleep(1)

    @property
    def task_names(self) -> List[str]:
        """当前已注册的任务名称列表"""
        return list(self._tasks.keys())

    @property
    def task_count(self) -> int:
        """已注册任务数量"""
        return len(self._tasks)

    def is_trading_day(self, d: date) -> bool:
        """代理：判断是否为交易日"""
        return self._calendar.is_trading_day(d)
