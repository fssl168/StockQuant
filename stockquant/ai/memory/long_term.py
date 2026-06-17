# -*- coding: utf-8 -*-
"""F020 L3 长期记忆 — 委托给 L3Store (PostgreSQL + pgvector)"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .l3_store import L3Store


class LongTermMemory:
    """L3 长期记忆 — 已验证洞察和知识

    委托给 L3Store (PostgreSQL + pgvector) 实现。
    """

    def __init__(self, db_url: str | None = None) -> None:
        self._store = L3Store(db_url=db_url)

    def add(self, insight: Dict[str, Any]) -> str:
        return self._store.write(insight)

    def search(
        self,
        symbol: Optional[str] = None,
        keyword: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        results = self._store.search(keyword or "", top_k=limit)
        if symbol:
            results = [r for r in results if r.get("symbol") == symbol]
        if min_confidence > 0:
            results = [r for r in results if r.get("confidence", 0) >= min_confidence]
        return results[:limit]

    def count(self) -> int:
        return self._store.count()

    def delete(self, item_id: str) -> bool:
        return self._store.delete(item_id)

    def get_all(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return self._store.get_all(limit)

    def close(self) -> None:
        self._store.close()
