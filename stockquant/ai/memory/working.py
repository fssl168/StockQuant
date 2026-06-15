# -*- coding: utf-8 -*-
"""F020 L1 工作记忆 — 内存存储，最近 N 条"""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional


class WorkingMemory:
    """L1 工作记忆 — 内存中存储最近 N 条关键信息"""

    def __init__(self, max_size: int = 200) -> None:
        self._max_size = max_size
        self._entries: deque[Dict[str, Any]] = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def append(self, entry: Dict[str, Any]) -> None:
        with self._lock:
            entry.setdefault("timestamp", datetime.now().isoformat())
            self._entries.append(entry)

    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._entries)[-n:]

    def query(
        self,
        symbol: Optional[str] = None,
        since: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            results = list(self._entries)
        if symbol:
            results = [e for e in results if e.get("symbol") == symbol]
        if since:
            results = [e for e in results if e.get("timestamp", "") >= since]
        return results

    def get_sentiment_baseline(self, symbol: str, window_days: int = 30) -> float:
        """获取某标的的情绪基线（最近 N 天的平均情绪分）"""
        entries = self.query(symbol=symbol)
        sentiments = [e.get("sentiment", 0) for e in entries if "sentiment" in e]
        if not sentiments:
            return 0.0
        return sum(sentiments) / len(sentiments)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
