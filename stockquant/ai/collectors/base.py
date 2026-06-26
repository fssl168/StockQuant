# -*- coding: utf-8 -*-
"""采集器基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class RawInfoItem:
    """原始信息条目"""
    url: str = ""
    source: str = ""
    title: str = ""
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    sentiment_score: float = 0.0
    verified: bool = False
    symbol: str = ""


class BaseCollector(ABC):
    """采集器抽象基类"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def collect(self, symbol: str = "", limit: int = 20) -> List[RawInfoItem]:
        """采集信息，返回原始条目列表"""
        ...

    def _create_item(self, url: str, source: str, title: str, content: str,
                     symbol: str = "", sentiment: float = 0.0) -> RawInfoItem:
        return RawInfoItem(
            url=url, source=source, title=title, content=content,
            symbol=symbol, sentiment_score=sentiment,
        )
