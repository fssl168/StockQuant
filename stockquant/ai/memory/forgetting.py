# -*- coding: utf-8 -*-
"""F020 遗忘机制 — 时间遗忘 + 置信度遗忘 + 冗余压缩"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("stockquant.ai.memory.forgetting")


class ForgettingMechanism:
    """遗忘机制

    三种遗忘策略:
    1. 时间遗忘: 删除过期条目
    2. 置信度遗忘: 删除低置信度条目
    3. 冗余压缩: 合并相似条目
    """

    # 默认置信度阈值，低于此值的条目将被遗忘
    DEFAULT_CONFIDENCE_THRESHOLD = 0.3

    def forget(self, l2_store: Any, l3_store: Any) -> Dict[str, int]:
        """执行全部遗忘策略

        Args:
            l2_store: L2Store 实例
            l3_store: L3Store 实例

        Returns:
            各层删除的条目数
        """
        result: Dict[str, int] = {"l2": 0, "l3": 0}

        # L2 遗忘
        result["l2"] += self._time_forget_l2(l2_store)
        result["l2"] += self._confidence_forget_l2(l2_store)

        # L3 遗忘
        result["l3"] += self._confidence_forget_l3(l3_store)

        return result

    def _time_forget_l2(self, l2_store: Any) -> int:
        """时间遗忘: 清理 L2 过期条目"""
        try:
            return l2_store.cleanup_expired()
        except Exception as exc:
            logger.warning("L2 时间遗忘失败: %s", exc)
            return 0

    def _confidence_forget_l2(self, l2_store: Any, threshold: float = 0.0) -> int:
        """置信度遗忘: 删除 L2 低置信度条目"""
        threshold = threshold or self.DEFAULT_CONFIDENCE_THRESHOLD
        deleted = 0
        try:
            items = l2_store.get_all()
            for item in items:
                if item.get("confidence", 1.0) < threshold:
                    if l2_store.delete(item["id"]):
                        deleted += 1
        except Exception as exc:
            logger.warning("L2 置信度遗忘失败: %s", exc)
        return deleted

    def _confidence_forget_l3(self, l3_store: Any, threshold: float = 0.0) -> int:
        """置信度遗忘: 删除 L3 低置信度条目

        L3 的置信度阈值比 L2 更低，因为进入 L3 的条目已经过验证。
        """
        threshold = threshold or self.DEFAULT_CONFIDENCE_THRESHOLD * 0.5
        deleted = 0
        try:
            items = l3_store.get_all(limit=5000)
            for item in items:
                if item.get("confidence", 1.0) < threshold:
                    if l3_store.delete(item["id"]):
                        deleted += 1
        except Exception as exc:
            logger.warning("L3 置信度遗忘失败: %s", exc)
        return deleted

    def redundancy_compress(self, items: List[Dict[str, Any]], similarity_threshold: float = 0.9) -> List[Dict[str, Any]]:
        """冗余压缩: 合并相似条目

        基于内容字符重叠率，将相似度超过阈值的条目合并为一条。
        """
        if not items:
            return items

        result: List[Dict[str, Any]] = []
        for item in items:
            is_dup = False
            for existing in result:
                if self._similarity(item.get("content", ""), existing.get("content", "")) > similarity_threshold:
                    # 保留置信度更高的
                    if item.get("confidence", 0) > existing.get("confidence", 0):
                        existing.update(item)
                    is_dup = True
                    break
            if not is_dup:
                result.append(item)
        return result

    def _similarity(self, a: str, b: str) -> float:
        """简单字符重叠率"""
        if not a or not b:
            return 0.0
        set_a = set(a)
        set_b = set(b)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0
