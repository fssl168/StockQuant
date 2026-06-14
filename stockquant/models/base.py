# -*- coding: utf-8 -*-
"""基础数据模型 — 事件系统"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(Enum):
    """事件类型枚举"""
    TIMER = "TimerEvent"
    BAR = "BarEvent"
    TICK = "TickEvent"
    TRADE = "TradeEvent"
    ORDER = "OrderEvent"
    ACCOUNT = "AccountEvent"
    PORTFOLIO = "PortfolioEvent"
    # AI 扩展事件
    NEWS = "NewsEvent"
    SENTIMENT = "SentimentEvent"
    SIGNAL = "SignalEvent"
    ALERT = "AlertEvent"


@dataclass
class Event:
    """事件基类"""
    type: EventType
    data: Any = None
    timestamp: float = field(default_factory=datetime.now().timestamp)

    def __repr__(self) -> str:
        return f"{self.type.value}@{self.timestamp}"
