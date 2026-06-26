# -*- coding: utf-8 -*-
"""重试工具 — 基于 tenacity 的数据拉取重试装饰器"""

from __future__ import annotations

import logging
import random
import time
from functools import wraps
from typing import Any, Callable

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_combine,
    wait_exponential,
    wait_random,
)

from stockquant.data.exceptions import DataFetchError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 预置配置
# ---------------------------------------------------------------------------

#: 内部数据源（baostock）重试策略 — 较少重试，等待较长
BAOSTOCK_RETRY: dict[str, Any] = {
    'max_retries': 3,
    'base_wait': 2.0,
    'max_wait': 30.0,
    'jitter': 1.0,
}

#: 公共 API（akshare 等）重试策略 — 适中
PUBLIC_API_RETRY: dict[str, Any] = {
    'max_retries': 5,
    'base_wait': 1.0,
    'max_wait': 20.0,
    'jitter': 1.0,
}

#: 敏感 API（需要鉴权、限流严格）重试策略 — 保守
SENSITIVE_API_RETRY: dict[str, Any] = {
    'max_retries': 2,
    'base_wait': 3.0,
    'max_wait': 60.0,
    'jitter': 2.0,
}

# ---------------------------------------------------------------------------
# 核心装饰器
# ---------------------------------------------------------------------------

def data_fetch_retry(
    max_retries: int = 3,
    base_wait: float = 2.0,
    max_wait: float = 30.0,
    jitter: float = 1.0,
) -> Callable[[Callable], Callable]:
    """数据拉取重试装饰器工厂。

    使用 ``tenacity`` 实现指数退避 + 随机抖动，自动捕获 ``DataFetchError``
    及常见网络异常并重试；耗尽后重新抛出原始异常。

    Parameters
    ----------
    max_retries : int
        最大重试次数。实际调用次数为 ``max_retries + 1``（含首次）。
    base_wait : float
        指数退避的基础秒数。
    max_wait : float
        单次等待的最大秒数。
    jitter : float
        随机抖动的上界（秒），范围 ``[0, jitter)``。

    Returns
    -------
    Callable[[Callable], Callable]
        装饰器。
    """

    def decorator(func: Callable) -> Callable:
        wrapped = retry(
            retry=retry_if_exception_type((
                DataFetchError,
                ConnectionError,
                TimeoutError,
                OSError,
            )),
            wait=wait_combine(
                wait_exponential(multiplier=base_wait, max=max_wait),
                wait_random(0, jitter),
            ),
            stop=stop_after_attempt(max_retries + 1),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )(func)

        return wrapped

    return decorator


def random_sleep(
    min_delay: float = 1.0,
    max_delay: float = 3.0,
) -> Callable[[Callable], Callable]:
    """在调用函数前随机休眠一段时间（用于规避限流）。

    Parameters
    ----------
    min_delay : float
        最小延迟秒数。
    max_delay : float
        最大延迟秒数。
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = random.uniform(min_delay, max_delay)
            time.sleep(delay)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def no_retry(func: Callable) -> Callable:
    """标记为不可重试的装饰器（空操作）。

    用于文档化目的：声明某个数据源不应被自动重试。
    调用方遇到该来源的异常时应直接向上抛出。
    """
    return func
