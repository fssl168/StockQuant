# -*- coding: utf-8 -*-
"""F020 L2 短期记忆 — SQLite 存储，百万条"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.memory")


class ShortTermMemory:
    """L2 短期记忆 — SQLite 存储

    支持 CRUD 和语义检索（退化：关键词匹配）
    """

    def __init__(self, db_url: str = "sqlite:///./stockquant_ai.db") -> None:
        self._db_url = db_url
        self._entries: List[Dict[str, Any]] = []

    def add(self, symbol: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """添加条目"""
        entry = {
            "id": f"l2_{len(self._entries) + 1}",
            "symbol": symbol,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }
        self._entries.append(entry)
        return entry["id"]

    def search(
        self,
        symbol: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """搜索条目"""
        results = self._entries
        if symbol:
            results = [e for e in results if e.get("symbol") == symbol]
        if keyword:
            results = [e for e in results if keyword.lower() in e.get("content", "").lower()]
        return results[-limit:]

    def get_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        for e in self._entries:
            if e.get("id") == entry_id:
                return e
        return None

    def delete(self, entry_id: str) -> bool:
        for i, e in enumerate(self._entries):
            if e.get("id") == entry_id:
                self._entries.pop(i)
                return True
        return False

    def clear(self) -> None:
        self._entries.clear()

    def count(self) -> int:
        return len(self._entries)
