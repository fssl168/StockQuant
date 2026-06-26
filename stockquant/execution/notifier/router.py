# -*- coding: utf-8 -*-
"""消息路由与批量发送"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List

from stockquant.execution.notifier.base import Notifier

logger = logging.getLogger(__name__)


class Priority(Enum):
    """消息优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Priority):
            return NotImplemented
        return self.value >= other.value

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Priority):
            return NotImplemented
        return self.value <= other.value

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Priority):
            return NotImplemented
        return self.value > other.value

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Priority):
            return NotImplemented
        return self.value < other.value


@dataclass
class Message:
    """待发送消息"""
    title: str
    content: str
    priority: Priority = Priority.NORMAL
    channels: List[str] = field(default_factory=lambda: ["all"])
    created_at: float = field(default_factory=time.time)
    sender: str = "system"


class MessageRouter:
    """消息路由器。

    负责：
    - 路由：根据消息属性和配置规则，分发到合适的通知渠道
    - 限速：防止短时间内发送过多消息
    - 批量：将多条消息合并为一条发送

    Usage:
        router = MessageRouter()
        router.register_notifier("email", EmailNotifier(...))
        router.register_rule("high_priority", lambda msg: msg.priority >= Priority.HIGH, "email")
        router.send(Message(title="Alert", content="...", priority=Priority.HIGH))
    """

    def __init__(self, rate_limit_per_minute: int = 10,
                 batch_window: float = 5.0) -> None:
        """
        Parameters
        ----------
        rate_limit_per_minute : int
            每个渠道每分钟最大发送次数
        batch_window : float
            批量发送窗口（秒），在此窗口内的消息合并发送
        """
        self._notifiers: Dict[str, Notifier] = {}
        self._rules: List[tuple[Callable[[Message], bool], List[str]]] = []
        self._rate_limits: Dict[str, List[float]] = defaultdict(list)
        self._rate_limit = rate_limit_per_minute
        self._batch_window = batch_window
        self._pending_messages: List[Message] = []

    def register_notifier(self, name: str, notifier: Notifier) -> None:
        """注册通知器。"""
        self._notifiers[name] = notifier
        logger.debug("Registered notifier: %s", name)

    def register_rule(self, name: str, predicate: Callable[[Message], bool],
                      channels: List[str]) -> None:
        """注册路由规则。

        Parameters
        ----------
        name : str
            规则名称（用于日志）
        predicate : Callable[[Message], bool]
            消息匹配函数
        channels : list[str]
            匹配时使用的渠道
        """
        self._rules.append((predicate, channels))
        logger.debug("Registered rule: %s -> %s", name, channels)

    def send(self, message: Message) -> Dict[str, bool]:
        """发送消息到所有匹配的渠道。

        Returns
        -------
        dict — {channel_name: success_bool}
        """
        results: Dict[str, bool] = {}
        matching_channels = self._resolve_channels(message)

        for channel in matching_channels:
            if not self._should_send(channel):
                logger.debug("Rate limited: %s", channel)
                continue

            notifier = self._notifiers.get(channel)
            if notifier is None:
                logger.warning("No notifier registered for channel: %s", channel)
                continue

            try:
                success = notifier.send(message.content, title=message.title)
                results[channel] = success
                if success:
                    self._rate_limits[channel].append(time.time())
                logger.info(
                    "Message sent to %s (success=%s, priority=%s)",
                    channel, success, message.priority.name,
                )
            except Exception as exc:
                logger.error("Failed to send to %s: %s", channel, exc)
                results[channel] = False

        return results

    def _resolve_channels(self, message: Message) -> List[str]:
        """解析消息应发送到的渠道列表。"""
        if "all" in message.channels:
            # 使用规则路由
            matched: List[str] = []
            for predicate, channels in self._rules:
                if predicate(message):
                    matched.extend(channels)
            return list(dict.fromkeys(matched))  # 去重，保持顺序
        else:
            # 使用显式渠道
            explicit = [c for c in message.channels if c in self._notifiers]
            return explicit

    def _should_send(self, channel: str) -> bool:
        """检查是否超过限速。"""
        now = time.time()
        cutoff = now - 60.0
        timestamps = self._rate_limits[channel]

        # 清理过期记录
        self._rate_limits[channel] = [t for t in timestamps if t > cutoff]

        return len(self._rate_limits[channel]) < self._rate_limit

    def send_batch(self, messages: List[Message]) -> Dict[str, int]:
        """批量发送消息。

        将消息按渠道分组，每条渠道只发一次合并后的消息。

        Returns
        -------
        dict — {channel_name: message_count}
        """
        if not messages:
            return {}

        # 按渠道分组
        channel_messages: Dict[str, List[Message]] = defaultdict(list)
        for msg in messages:
            channels = self._resolve_channels(msg)
            for ch in channels:
                channel_messages[ch].append(msg)

        results: Dict[str, int] = {}
        for channel, batch_msgs in channel_messages.items():
            if not self._should_send(channel):
                logger.debug("Rate limited batch for: %s", channel)
                continue

            notifier = self._notifiers.get(channel)
            if notifier is None:
                logger.warning("No notifier for channel: %s", channel)
                continue

            # 合并消息内容
            merged_title = f"批量通知 ({len(batch_msgs)} 条)"
            merged_content = "\n\n---\n\n".join(
                f"[{msg.priority.name}] {msg.title}\n{msg.content}"
                for msg in batch_msgs
            )

            try:
                success = notifier.send(merged_content, title=merged_title)
                self._rate_limits[channel].append(time.time())
                results[channel] = len(batch_msgs) if success else 0
                logger.info("Batch sent to %s (%d messages, success=%s)",
                            channel, len(batch_msgs), success)
            except Exception as exc:
                logger.error("Batch send failed for %s: %s", channel, exc)
                results[channel] = 0

        return results

    def get_status(self) -> Dict[str, dict]:
        """获取路由状态。"""
        now = time.time()
        status: Dict[str, dict] = {}
        for channel, notifier in self._notifiers.items():
            cutoff = now - 60.0
            recent = [t for t in self._rate_limits.get(channel, []) if t > cutoff]
            status[channel] = {
                "registered": True,
                "send_count_last_minute": len(recent),
                "rate_limit": self._rate_limit,
                "remaining": max(0, self._rate_limit - len(recent)),
            }
        return status
