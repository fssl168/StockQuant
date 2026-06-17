# -*- coding: utf-8 -*-
"""F020 L2 短期记忆 — 委托给 L2Store (PostgreSQL + asyncpg)"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .l2_store import L2Store


class ShortTermMemory:
    """L2 短期记忆 — 委托给 L2Store (PostgreSQL + asyncpg) 实现"""

    def __init__(self, db_url: str | None = None) -> None:
        self._store = L2Store(db_url=db_url)

    def add(self, symbol: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """添加条目"""
        return self._store.write({
            "symbol": symbol,
            "content": content,
            "metadata": metadata or {},
        })

    def search(
        self,
        symbol: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """搜索条目"""
        results = self._store.search(keyword or "", top_k=limit)
        if symbol:
            results = [r for r in results if r.get("symbol") == symbol]
        return results[:limit]

    def get_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 获取条目"""
        results = self._store.search("", top_k=1)
        for r in results:
            if r.get("id") == entry_id:
                return r
        return None

    def delete(self, entry_id: str) -> bool:
        return self._store.delete(entry_id)

    def clear(self) -> None:
        """清空所有条目"""
        items = self._store.get_all(limit=100000)
        for item in items:
            self._store.delete(item["id"])

    def count(self) -> int:
        return self._store.count()

    def close(self) -> None:
        self._store.close()
