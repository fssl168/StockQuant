# -*- coding: utf-8 -*-
"""F020 记忆系统编排 — 统一使用 PostgreSQL + asyncpg + pgvector"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .working import WorkingMemory
from .l2_store import L2Store
from .l3_store import L3Store


def _default_db_url() -> str:
    """获取默认数据库 URL"""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://stockquant:stockquant_secret@localhost:5432/stockquant",
    )


class MemorySystem:
    """记忆系统 — 编排 L1/L2/L3 三层记忆

    存储后端: PostgreSQL + asyncpg + pgvector
    """

    def __init__(
        self,
        working_max_size: int = 200,
        db_url: str | None = None,
    ) -> None:
        url = db_url or _default_db_url()
        self.l1 = WorkingMemory(max_size=working_max_size)
        self.l2 = L2Store(db_url=url)
        self.l3 = L3Store(db_url=url)

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
        return self.l2.write({
            "symbol": symbol,
            "content": content,
            "metadata": metadata or {},
        })

    def search_short_term(
        self,
        symbol: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        results = self.l2.search(keyword or "", top_k=limit)
        if symbol:
            results = [r for r in results if r.get("symbol") == symbol]
        return results[:limit]

    # ── L3 接口 ──
    def add_long_term(self, insight: Dict[str, Any]) -> str:
        return self.l3.write(insight)

    def search_long_term(
        self,
        symbol: Optional[str] = None,
        keyword: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        results = self.l3.search(keyword or "", top_k=limit)
        if symbol:
            results = [r for r in results if r.get("symbol") == symbol]
        if min_confidence > 0:
            results = [r for r in results if r.get("confidence", 0) >= min_confidence]
        return results[:limit]
