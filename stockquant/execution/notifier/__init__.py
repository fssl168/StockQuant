# -*- coding: utf-8 -*-
"""F018 消息推送模块 — 通知器包"""

from __future__ import annotations

from stockquant.execution.notifier.base import Notifier
from stockquant.execution.notifier.dingtalk import DingTalkNotifier
from stockquant.execution.notifier.discord import DiscordNotifier
from stockquant.execution.notifier.email import EmailNotifier
from stockquant.execution.notifier.feishu import FeishuNotifier
from stockquant.execution.notifier.pushplus import PushPlusNotifier
from stockquant.execution.notifier.serverchan import ServerChanNotifier
from stockquant.execution.notifier.telegram import TelegramNotifier
from stockquant.execution.notifier.webhook import WebhookNotifier
from stockquant.execution.notifier.wechat import WeChatNotifier

__all__ = [
    "Notifier",
    "DingTalkNotifier",
    "DiscordNotifier",
    "EmailNotifier",
    "FeishuNotifier",
    "PushPlusNotifier",
    "ServerChanNotifier",
    "TelegramNotifier",
    "WebhookNotifier",
    "WeChatNotifier",
]
