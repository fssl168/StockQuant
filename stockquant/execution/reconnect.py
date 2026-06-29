# -*- coding: utf-8 -*-
"""断线重连策略 — 指数退避重连管理器

提供独立的重连策略类，可与 BaseGateway 配合使用，也可独立用于其他场景。

重连延迟计算公式::

    delay = min(initial_delay * backoff_factor ^ attempt, max_delay)

使用示例::

    strategy = ReconnectStrategy(initial_delay=1.0, max_delay=60.0, backoff_factor=2.0, max_retries=10)
    while strategy.should_retry():
        delay = strategy.next_delay()
        time.sleep(delay)
        ok = try_connect()
        if ok:
            strategy.record_success()
            break
        else:
            strategy.record_failure()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReconnectStrategy:
    """断线重连策略 — 指数退避

    管理重连的退避延迟计算、重试计数和成功/失败记录。

    Attributes:
        initial_delay: 初始重连延迟（秒）
        max_delay: 最大重连延迟（秒），退避延迟不会超过此值
        backoff_factor: 指数退避因子，每次失败后延迟乘以该因子
        max_retries: 最大重试次数（0 = 无限重试）
    """

    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    max_retries: int = 10

    # 内部状态（不从 dataclass 构造函数初始化）
    _attempt: int = 0
    _consecutive_failures: int = 0

    def __post_init__(self):
        """初始化内部状态"""
        if not hasattr(self, "_attempt"):
            self._attempt = 0
        if not hasattr(self, "_consecutive_failures"):
            self._consecutive_failures = 0

    def next_delay(self) -> float:
        """计算下次重连延迟

        Returns:
            延迟秒数，范围为 [initial_delay, max_delay]
        """
        delay = self.initial_delay * (self.backoff_factor ** self._attempt)
        delay = min(delay, self.max_delay)
        return delay

    def record_success(self) -> None:
        """记录连接成功，重置计数器"""
        logger.info("重连成功，重置计数器（已尝试 %d 次）", self._attempt)
        self._attempt = 0
        self._consecutive_failures = 0

    def record_failure(self) -> None:
        """记录连接失败，递增计数器"""
        self._attempt += 1
        self._consecutive_failures += 1
        logger.warning(
            "重连失败（第 %d 次），下次延迟 %.1f 秒",
            self._attempt, self.next_delay(),
        )

    def should_retry(self) -> bool:
        """判断是否应该继续重试

        Returns:
            True 可以重试，False 已达上限
        """
        if self.max_retries <= 0:
            # 0 表示无限重试
            return True
        return self._attempt < self.max_retries

    def reset(self) -> None:
        """完全重置策略状态"""
        self._attempt = 0
        self._consecutive_failures = 0
        logger.debug("重连策略已重置")

    @property
    def attempt(self) -> int:
        """当前重试次数"""
        return self._attempt

    @property
    def consecutive_failures(self) -> int:
        """连续失败次数"""
        return self._consecutive_failures

    @property
    def exhausted(self) -> bool:
        """是否已耗尽重试次数"""
        return self.max_retries > 0 and self._attempt >= self.max_retries

    def __repr__(self) -> str:
        return (
            f"ReconnectStrategy(attempt={self._attempt}/{self.max_retries}, "
            f"next_delay={self.next_delay():.1f}s, "
            f"backoff={self.backoff_factor}x)"
        )
