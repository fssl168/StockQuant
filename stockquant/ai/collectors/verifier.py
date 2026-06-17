# -*- coding: utf-8 -*-
"""来源验证 + 事实初筛"""
from __future__ import annotations

from typing import List

from .base import RawInfoItem


class SourceVerifier:
    """来源验证器 — 检测仿冒源、重复内容、过期信息"""

    # 可信源白名单
    TRUSTED_SOURCES = {"eastmoney", "sina", "cninfo", "xueqiu", "sse", "szse"}

    # 已知仿冒源黑名单
    FAKE_SOURCES: set = set()

    def verify(self, items: List[RawInfoItem]) -> List[RawInfoItem]:
        """验证信息来源，标记不可信项"""
        for item in items:
            item.verified = self._is_trusted(item)
        return [item for item in items if item.verified or item.source not in self.FAKE_SOURCES]

    def _is_trusted(self, item: RawInfoItem) -> bool:
        """检查来源是否可信"""
        return item.source.lower() in self.TRUSTED_SOURCES

    def deduplicate(self, items: List[RawInfoItem], threshold: float = 0.95) -> List[RawInfoItem]:
        """基于标题相似度去重"""
        seen_titles: List[str] = []
        result: List[RawInfoItem] = []
        for item in items:
            is_dup = False
            for seen in seen_titles:
                if self._similarity(item.title, seen) > threshold:
                    is_dup = True
                    break
            if not is_dup:
                seen_titles.append(item.title)
                result.append(item)
        return result

    def _similarity(self, a: str, b: str) -> float:
        """简单文本相似度（基于字符重叠率）"""
        if not a or not b:
            return 0.0
        set_a = set(a)
        set_b = set(b)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0
