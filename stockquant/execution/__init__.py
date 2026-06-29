# -*- coding: utf-8 -*-
"""F005/F012/F017/F018 交易执行 + 仿真撮合引擎 + 消息推送模块

仿真撮合引擎（F005/F012）:
- SimulationMatchingEngine: 统一入口
- ContinuousMatchingEngine: 连续竞价撮合
- CallAuctionEngine: 集合竞价撮合
- OrderBook: 订单簿（价格优先 + 时间优先）
- ASharePriceLimit: A 股涨跌停价格计算
- OrderEntry: 撮合队列原子单元

模拟盘账户（F003/F012）:
- PaperAccount: 虚拟资金、持仓跟踪
- FeeCalculator: 费用计算（手续费、印花税）
- CommissionConfig: 手续费配置
- PositionInfo: 持仓信息

消息推送:
- 各渠道 Notifier
"""

from __future__ import annotations

# ── 仿真撮合引擎 ─────────────────────────────────────────────────────

from stockquant.execution.matching_engine import (
    ASharePriceLimit,
    CallAuctionEngine,
    ContinuousMatchingEngine,
    OrderBook,
    OrderEntry,
    SimulationMatchingEngine,
)

# ── 模拟盘账户 ───────────────────────────────────────────────────────

from stockquant.execution.account_manager import (
    CommissionConfig,
    FeeCalculator,
    PaperAccount,
    PositionInfo,
)

# ── 消息推送 ─────────────────────────────────────────────────────────

from stockquant.execution.notifier.dingtalk import DingTalkNotifier
from stockquant.execution.notifier.email import EmailNotifier
from stockquant.execution.notifier.wechat import WeChatNotifier
from stockquant.execution.notifier.telegram import TelegramNotifier
from stockquant.execution.notifier.discord import DiscordNotifier
from stockquant.execution.notifier.pushplus import PushPlusNotifier
from stockquant.execution.notifier.serverchan import ServerChanNotifier
from stockquant.execution.notifier.webhook import WebhookNotifier
from stockquant.execution.notifier.feishu import FeishuNotifier
from stockquant.execution.report_renderer import render_md_to_image
from stockquant.execution.notifier.router import MessageRouter, Message, Priority

__all__ = [
    # 仿真撮合引擎
    "ASharePriceLimit",
    "CallAuctionEngine",
    "ContinuousMatchingEngine",
    "OrderBook",
    "OrderEntry",
    "SimulationMatchingEngine",
    # 模拟盘账户
    "CommissionConfig",
    "FeeCalculator",
    "PaperAccount",
    "PositionInfo",
    # 消息推送
    "DingTalkNotifier",
    "EmailNotifier",
    "WeChatNotifier",
    "TelegramNotifier",
    "DiscordNotifier",
    "PushPlusNotifier",
    "ServerChanNotifier",
    "WebhookNotifier",
    "FeishuNotifier",
    "render_md_to_image",
    "MessageRouter",
    "Message",
    "Priority",
]
