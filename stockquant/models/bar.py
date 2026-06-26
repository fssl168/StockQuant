# -*- coding: utf-8 -*-
"""K线数据"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BarData:
    """单根K线数据"""
    symbol: str
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    turnover: float = 0.0
    adjust_flag: str = ""

    @property
    def mid_price(self) -> float:
        return (self.high + self.low) / 2

    @property
    def amplitude(self) -> float:
        if self.low == 0:
            return 0.0
        return (self.high - self.low) / self.low * 100

    def __lt__(self, other: "BarData") -> bool:
        return self.datetime < other.datetime

    def __le__(self, other: "BarData") -> bool:
        return self.datetime <= other.datetime
