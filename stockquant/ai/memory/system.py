# -*- coding: utf-8 -*-
"""F020 记忆系统编排"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .working import WorkingMemory
from .short_term import ShortTermMemory
from .long_term import LongTermMemory


class MemorySystem:
    """记忆系统 — 编排 L1/L2/L3 三层记忆"""

    def __init__(
        self,
        working_max_size: int = 200,
        db_url: str = "sqlite:///./stockquant_ai.db",
    ) -> None:
        self.l1 = WorkingMemory(max_size=working_max_size)
        self.l2 = ShortTermMemory(db_url=db_url)
        self.l3 = LongTermMemory()

    # ── L1 接口 ──
    def add_working(self, entry: Dict[str, Any]) -> None:
        self.l1.append(entry)

    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        return self.l1.get_recent(n)

    def search_working(self, symbol: Optional[str] = None, since: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.l1.query(symbol=symbol, since=since)

    def get_sentiment_baseline(self, symbol: str, window_days: int = 30) -> float:
        return self.l1.get_sentiment_baseline(symbol, window_days)

    # ── L2 接口 ──
    def add_short_term(self, symbol: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        return self.l2.add(symbol, content, metadata)

    def search_short_term(
        self,
        symbol: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        return self.l2.search(symbol=symbol, keyword=keyword, limit=limit)

    # ── L3 接口 ──
    def add_long_term(self, insight: Dict[str, Any]) -> str:
        return self.l3.add(insight)

    def search_long_term(
        self,
        symbol: Optional[str] = None,
        keyword: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        return self.l3.search(symbol=symbol, keyword=keyword, min_confidence=min_confidence, limit=limit)
