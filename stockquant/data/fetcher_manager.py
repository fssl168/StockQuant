# -*- coding: utf-8 -*-
"""F011 数据源故障切换管理器"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from stockquant.data.feed import DataFeed

logger = logging.getLogger("stockquant.data")


@dataclass
class FetcherStatus:
    """数据源状态"""
    name: str
    is_healthy: bool = True
    last_check: float = 0.0
    failure_count: int = 0
    last_error: str = ""
    priority: int = 0


class DataFetcherManager:
    """数据源故障切换管理器。

    维护多个数据源的优先级队列，自动故障切换。

    Usage:
        mgr = DataFetcherManager()
        mgr.register_fetcher(fetcher, priority=1)
        df = mgr.fetch("sh600519", "1d", "2024-01-01", "2024-12-31")
        # If primary fails, automatically tries next healthy source
    """

    def __init__(self, failover_threshold: int = 2,
                 health_check_interval: float = 300.0,
                 health_check_fn: Optional[Callable] = None):
        """
        Parameters
        ----------
        failover_threshold : int
            连续失败 N 次后标记为不健康
        health_check_interval : float
            健康检查间隔（秒）
        health_check_fn : callable | None
            自定义健康检查函数
        """
        self._failover_threshold = failover_threshold
        self._health_check_interval = health_check_interval
        self._health_check_fn = health_check_fn
        self._fetchers: Dict[str, DataFeed] = {}
        self._statuses: Dict[str, FetcherStatus] = {}

    def register_fetcher(self, fetcher: "DataFeed", priority: int = 0,
                         health_check: Optional[Callable[[], bool]] = None) -> None:
        """注册数据源。

        Parameters
        ----------
        fetcher : DataFeed
            数据源实例
        priority : int
            优先级，数值越高优先级越高（先尝试）
        health_check : callable | None
            自定义健康检查函数，返回 True 表示健康
        """
        name = getattr(fetcher, "symbol", None) or getattr(fetcher, "name", None) or f"{fetcher.__class__.__name__}_{id(fetcher)}"
        self._fetchers[name] = fetcher
        self._statuses[name] = FetcherStatus(
            name=name,
            priority=priority,
            last_check=time.time(),
        )
        if health_check is not None:
            self._statuses[name].health_check_fn = health_check  # type: ignore[attr-defined]
        logger.debug(f"DataFetcherManager: registered fetcher '{name}' (priority={priority})")

    def fetch(self, symbol: str, timeframe: str = "1d",
              start: str = "", end: str = "", days: int = 0) -> pd.DataFrame:
        """自动选择健康数据源并拉取数据。

        按优先级排序，从最高优先级开始尝试，失败后自动切换到下一个。

        Parameters
        ----------
        symbol : str
            标的代码
        timeframe : str
            时间框架
        start : str
            开始日期
        end : str
            结束日期
        days : int
            获取最近 N 天的数据（如果指定，会覆盖 start 参数）

        Returns
        -------
        pd.DataFrame

        Raises
        ------
        ValueError
            如果没有可用的数据源
        """
        healthy = self.get_healthy_fetchers()
        if not healthy:
            raise ValueError("No healthy fetchers available")

        last_error = ""
        for feed in healthy:
            name = getattr(feed, "symbol", id(feed))
            # 尝试调用 feed 的 fetch 方法按需加载数据（如果 feed 支持）
            try:
                if hasattr(feed, 'fetch') and callable(getattr(feed, 'fetch')):
                    feed.fetch(symbol, timeframe, start, end, days)
                result = feed.get_dataframe(symbol) if hasattr(feed, 'get_dataframe') else feed.get_dataframe()
                if result is not None and not result.empty:
                    logger.debug(f"DataFetcherManager: fetched {len(result)} rows from '{name}' for {symbol}")
                    self.mark_healthy(name)
                    return result
                logger.warning(f"DataFetcherManager: '{name}' returned empty data for {symbol}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"DataFetcherManager: fetcher '{name}' failed for {symbol}: {e}")
                self.mark_unhealthy(name, error=last_error)

        raise ValueError(f"All fetchers failed. Last error: {last_error}")

    def mark_unhealthy(self, name: str, error: str = "") -> None:
        """标记数据源不健康"""
        if name not in self._statuses:
            logger.warning(f"DataFetcherManager: unknown fetcher '{name}'")
            return
        status = self._statuses[name]
        status.failure_count += 1
        status.is_healthy = status.failure_count < self._failover_threshold
        status.last_error = error
        status.last_check = time.time()
        if not status.is_healthy:
            logger.warning(f"DataFetcherManager: '{name}' marked unhealthy "
                           f"(failures={status.failure_count})")

    def mark_healthy(self, name: str) -> None:
        """标记数据源恢复健康"""
        if name not in self._statuses:
            return
        status = self._statuses[name]
        status.is_healthy = True
        status.failure_count = 0
        status.last_error = ""
        status.last_check = time.time()

    def _health_check(self, status: FetcherStatus) -> bool:
        """执行健康检查"""
        now = time.time()
        if now - status.last_check < self._health_check_interval:
            return status.is_healthy

        status.last_check = now

        # 自定义检查函数
        if hasattr(status, "health_check_fn") and status.health_check_fn is not None:  # type: ignore[attr-defined]
            try:
                result = status.health_check_fn()  # type: ignore[attr-defined]
                status.is_healthy = bool(result)
                return status.is_healthy
            except Exception as e:
                status.is_healthy = False
                status.last_error = str(e)
                return False

        # 默认：检查关联的 fetcher 是否存在
        fetcher = self._fetchers.get(status.name)
        if fetcher is None:
            status.is_healthy = False
            return False

        return status.is_healthy

    def get_healthy_fetchers(self) -> List["DataFeed"]:
        """获取所有健康的数据源，按优先级降序排列"""
        for status in self._statuses.values():
            self._health_check(status)

        healthy = [
            (self._fetchers[name], name)
            for name, status in self._statuses.items()
            if status.is_healthy
        ]
        healthy.sort(key=lambda x: self._statuses[x[1]].priority, reverse=True)
        return [f for f, _ in healthy]

    @property
    def status(self) -> Dict[str, dict]:
        """获取所有数据源状态"""
        result = {}
        for name, st in self._statuses.items():
            result[name] = {
                "name": st.name,
                "is_healthy": st.is_healthy,
                "last_check": st.last_check,
                "failure_count": st.failure_count,
                "last_error": st.last_error,
                "priority": st.priority,
            }
        return result

    def reset(self) -> None:
        """重置所有数据源为健康"""
        for status in self._statuses.values():
            status.is_healthy = True
            status.failure_count = 0
            status.last_error = ""
            status.last_check = time.time()
        logger.info("DataFetcherManager: all fetchers reset to healthy")
