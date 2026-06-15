# -*- coding: utf-8 -*-
"""StockQuant 异常层次 — 统一异常体系"""

from __future__ import annotations


class StockQuantError(Exception):
    """StockQuant 所有异常的基类"""


# ---------------------------------------------------------------------------
# 数据层异常
# ---------------------------------------------------------------------------

class DataError(StockQuantError):
    """数据层异常基类"""


class DataFetchError(DataError):
    """数据拉取失败。

    Parameters
    ----------
    message : str
        错误描述。
    source : str
        数据源名称（如 ``'baostock'``, ``'akshare'``）。
    retryable : bool
        是否可重试。默认 ``True``。
    """

    def __init__(
        self,
        message: str,
        source: str = "",
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.source: str = source
        self.retryable: bool = retryable


class RateLimitError(DataError):
    """数据源返回限流。不重试，触发备选数据源切换。"""

    def __init__(self, message: str = "数据源限流", source: str = "") -> None:
        super().__init__(message)
        self.source: str = source


class DataSourceUnavailableError(DataError):
    """数据源不可用（网络断开、服务宕机等）。不重试，触发备选数据源切换。"""

    def __init__(
        self,
        message: str = "数据源不可用",
        source: str = "",
    ) -> None:
        super().__init__(message)
        self.source: str = source


class DataValidationError(DataError):
    """数据格式校验失败（列缺失、类型错误等）"""

    def __init__(self, message: str, source: str = "") -> None:
        super().__init__(message)
        self.source: str = source


# ---------------------------------------------------------------------------
# 引擎层异常
# ---------------------------------------------------------------------------

class EngineError(StockQuantError):
    """引擎层异常基类"""


class OrderError(EngineError):
    """下单相关异常（拒单、部分成交等）"""


class RiskError(EngineError):
    """风控拦截异常"""


# ---------------------------------------------------------------------------
# AI 层异常
# ---------------------------------------------------------------------------

class AIError(StockQuantError):
    """AI 层异常基类"""


class LLMResponseError(AIError):
    """LLM 响应异常（超时、格式错误等）"""


class ToolExecutionError(AIError):
    """工具执行异常"""
