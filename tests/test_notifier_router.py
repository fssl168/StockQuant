# -*- coding: utf-8 -*-
"""消息路由器测试"""

from unittest.mock import MagicMock, patch

import pytest

from stockquant.execution.notifier.router import Message, MessageRouter, Priority
from stockquant.execution.notifier.base import Notifier


class MockNotifier(Notifier):
    """模拟通知器，用于测试"""

    def __init__(self) -> None:
        self.send_history: list[tuple[str, str | None]] = []

    def send(self, message: str, title: str | None = None) -> bool:
        self.send_history.append((message, title))
        return True

    def fail_next(self) -> None:
        """下一行 send 返回 False"""
        self._fail_next = True

    def send(self, message: str, title: str | None = None) -> bool:
        if getattr(self, "_fail_next", False):
            self._fail_next = False
            return False
        self.send_history.append((message, title))
        return True


class TestRegisterAndSend:
    def test_register_notifier(self):
        """注册通知器"""
        router = MessageRouter()
        notifier = MockNotifier()
        router.register_notifier("test_channel", notifier)
        assert "test_channel" in router._notifiers

    def test_send_to_registered_notifier(self):
        """注册通知器后发送消息，检查分发"""
        router = MessageRouter()
        notifier = MockNotifier()
        router.register_notifier("email", notifier)

        msg = Message(title="Test", content="Hello", channels=["email"])
        results = router.send(msg)

        assert "email" in results
        assert results["email"] is True
        assert len(notifier.send_history) == 1
        assert notifier.send_history[0] == ("Hello", "Test")

    def test_send_multiple_channels(self):
        """发送到多个渠道"""
        router = MessageRouter()
        email = MockNotifier()
        telegram = MockNotifier()
        router.register_notifier("email", email)
        router.register_notifier("telegram", telegram)

        msg = Message(title="Alert", content="Warning", channels=["email", "telegram"])
        results = router.send(msg)

        assert results["email"] is True
        assert results["telegram"] is True


class TestRuleRouting:
    def test_rules_route_correct_channels(self):
        """规则路由到正确的渠道"""
        router = MessageRouter()
        email = MockNotifier()
        telegram = MockNotifier()
        router.register_notifier("email", email)
        router.register_notifier("telegram", telegram)

        router.register_rule(
            "high_priority",
            lambda msg: msg.priority >= Priority.HIGH,
            ["email", "telegram"],
        )
        router.register_rule(
            "critical_only",
            lambda msg: msg.priority == Priority.CRITICAL,
            ["telegram"],
        )

        # 高优先级消息 — 走 email + telegram
        msg = Message(title="High", content="Alert", priority=Priority.HIGH)
        results = router.send(msg)
        assert "email" in results
        assert "telegram" in results
        assert email.send_history[0][1] == "High"

        # 仅 critical 走 telegram
        critical = Message(title="Critical", content="Emergency", priority=Priority.CRITICAL)
        results = router.send(critical)
        assert "telegram" in results
        assert len(telegram.send_history) == 2  # HIGH 一次 + CRITICAL 一次

    def test_all_channels_with_rules(self):
        """channels=['all'] 时使用规则路由"""
        router = MessageRouter()
        notifier = MockNotifier()
        router.register_notifier("pinned", notifier)

        router.register_rule(
            "pinned_rule",
            lambda msg: True,  # 所有消息都匹配
            ["pinned"],
        )

        msg = Message(title="Universal", content="Broadcast", channels=["all"])
        results = router.send(msg)
        assert "pinned" in results


class TestRateLimiting:
    def test_send_rate_limited(self):
        """超过限速后被限制"""
        router = MessageRouter(rate_limit_per_minute=3)
        notifier = MockNotifier()
        router.register_notifier("limited", notifier)

        msg = Message(title="Fast", content="Burst", channels=["limited"])

        # 发送 3 条（限速上限）
        for _ in range(3):
            router.send(msg)

        # 第 4 条应被限速
        results = router.send(msg)
        assert "limited" not in results or results.get("limited") is False
        assert len(notifier.send_history) == 3

    def test_rate_limit_resets_after_window(self):
        """限速窗口过期后恢复"""
        import time
        router = MessageRouter(rate_limit_per_minute=1)
        notifier = MockNotifier()
        router.register_notifier("reset_test", notifier)

        msg = Message(title="A", content="msg", channels=["reset_test"])
        router.send(msg)

        # 第 2 条被限速
        results = router.send(msg)
        assert "reset_test" not in results

        # 等待窗口过期（1 分钟），强制跳过
        router._rate_limits["reset_test"].clear()
        router.send(msg)
        assert len(notifier.send_history) == 2


class TestSendBatch:
    def test_batch_sends_merged_message(self):
        """批量发送合并消息"""
        router = MessageRouter()
        notifier = MockNotifier()
        router.register_notifier("batch_channel", notifier)

        messages = [
            Message(title=f"Msg {i}", content=f"Content {i}", channels=["batch_channel"])
            for i in range(5)
        ]

        results = router.send_batch(messages)
        assert "batch_channel" in results
        assert results["batch_channel"] == 5
        # 只发送了一次合并消息
        assert len(notifier.send_history) == 1
        # 合并消息应包含多条内容
        merged = notifier.send_history[0][0]
        assert "Msg 0" in merged
        assert "Msg 4" in merged

    def test_batch_empty(self):
        """空批量返回空字典"""
        router = MessageRouter()
        results = router.send_batch([])
        assert results == {}

    def test_batch_across_channels(self):
        """跨渠道批量发送"""
        router = MessageRouter()
        email = MockNotifier()
        telegram = MockNotifier()
        router.register_notifier("email", email)
        router.register_notifier("telegram", telegram)

        # 所有消息都发到 email + telegram
        messages = [
            Message(title=f"Msg {i}", content=f"Content {i}", channels=["email", "telegram"])
            for i in range(3)
        ]

        results = router.send_batch(messages)
        assert results["email"] == 3
        assert results["telegram"] == 3


class TestNoMatch:
    def test_no_rules_match_dropped(self):
        """无规则匹配，消息被丢弃"""
        router = MessageRouter()
        notifier = MockNotifier()
        router.register_notifier("should_not_receive", notifier)

        # 规则只匹配 CRITICAL，但我们发 NORMAL
        router.register_rule(
            "critical_only",
            lambda msg: msg.priority == Priority.CRITICAL,
            ["should_not_receive"],
        )

        msg = Message(title="Normal", content="Info", priority=Priority.NORMAL)
        results = router.send(msg)
        # channels 不是 ["all"]，也没有显式规则渠道匹配
        assert results == {}
        assert len(notifier.send_history) == 0

    def test_no_notifier_registered(self):
        """渠道没有注册通知器 → 记录警告"""
        router = MessageRouter()
        msg = Message(title="Orphan", content="No target", channels=["ghost_channel"])
        results = router.send(msg)
        assert results == {}


class TestChannelSpecificRouting:
    def test_specific_channels_only(self):
        """指定具体渠道，不使用规则"""
        router = MessageRouter()
        notifier1 = MockNotifier()
        notifier2 = MockNotifier()
        router.register_notifier("specific", notifier1)
        router.register_notifier("ignored", notifier2)

        # 显式指定 only_specific
        msg = Message(title="Targeted", content="Direct", channels=["specific"])
        results = router.send(msg)

        assert "specific" in results
        assert results["specific"] is True
        assert "ignored" not in results
        assert len(notifier1.send_history) == 1
        assert len(notifier2.send_history) == 0

    def test_unknown_specific_channel_dropped(self):
        """指定了未注册的渠道 → 被丢弃"""
        router = MessageRouter()
        msg = Message(title="Ghost", content="Nowhere", channels=["nonexistent"])
        results = router.send(msg)
        assert results == {}


class TestStatus:
    def test_get_status(self):
        """获取路由状态"""
        router = MessageRouter(rate_limit_per_minute=10)
        notifier = MockNotifier()
        router.register_notifier("status_test", notifier)

        status = router.get_status()
        assert "status_test" in status
        assert status["status_test"]["registered"] is True
        assert status["status_test"]["rate_limit"] == 10
        assert status["status_test"]["remaining"] == 10

    def test_status_after_sends(self):
        """发送后状态更新"""
        router = MessageRouter(rate_limit_per_minute=5)
        notifier = MockNotifier()
        router.register_notifier("count_test", notifier)

        msg = Message(title="A", content="a", channels=["count_test"])
        for _ in range(3):
            router.send(msg)

        status = router.get_status()
        assert status["count_test"]["send_count_last_minute"] == 3
        assert status["count_test"]["remaining"] == 2
