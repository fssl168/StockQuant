# -*- coding: utf-8 -*-
"""F020 L3 长期记忆 — 已验证知识存储"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


class LongTermMemory:
    """L3 长期记忆 — 已验证洞察和知识

    退化实现：内存存储
    """

    def __init__(self) -> None:
        self._insights: List[Dict[str, Any]] = []

    def add(self, insight: Dict[str, Any]) -> str:
        self._insights.append(insight)
        return f"l3_{len(self._insights)}"

    def search(
        self,
        symbol: Optional[str] = None,
        keyword: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        results = self._insights
        if symbol:
            results = [i for i in results if i.get("symbol") == symbol]
        if keyword:
            results = [i for i in results if keyword.lower() in json.dumps(i, ensure_ascii=False).lower()]
        if min_confidence > 0:
            results = [i for i in results if i.get("confidence", 0) >= min_confidence]
        return results[-limit:]
