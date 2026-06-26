# -*- coding: utf-8 -*-
"""DEPRECATED — 信息降噪器（旧版）

请改用 :mod:`stockquant.ai.pipeline.denoise`（新版 DenoiseStage）。
此文件保留仅供向后兼容，将在下一大版本移除。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from stockquant.ai.collectors.base import RawInfoItem

logger = logging.getLogger("stockquant.ai.pipeline.denoiser")


class Denoiser:
    """信息降噪器

    四步降噪:
    1. 来源信用降权 — 基于 L3 历史准确率降权低可信来源
    2. 时效降权 — 7d/30d/永久 三级时效降权
    3. 一致性过滤 — 屏蔽已被证伪的信息
    4. 冗余压缩 — 合并相似内容
    """

    # 来源基础信用度
    SOURCE_CREDIBILITY: Dict[str, float] = {
        "cninfo": 1.0,
        "cls": 0.9,
        "eastmoney": 0.8,
        "news_searcher": 0.7,
        "sina": 0.7,
        "xueqiu": 0.6,
    }

    # 时效降权阈值
    TIME_DECAY_7D = 0.8   # 7 天内轻微降权
    TIME_DECAY_30D = 0.5  # 30 天内中度降权
    TIME_DECAY_PERM = 0.1 # 超过 30 天严重降权

    def __init__(
        self,
        memory_system: Any = None,
        min_credibility: float = 0.3,
        similarity_threshold: float = 0.8,
    ) -> None:
        self._memory = memory_system
        self._min_credibility = min_credibility
        self._similarity_threshold = similarity_threshold

    def denoise(self, items: List[RawInfoItem]) -> List[RawInfoItem]:
        """执行四步降噪"""
        if not items:
            return []

        # Step 1: 来源信用降权
        items = self._source_credibility_downgrade(items)

        # Step 2: 时效降权
        items = self._time_based_downgrade(items)

        # Step 3: 一致性过滤（屏蔽已证伪信息）
        items = self._consistency_filter(items)

        # Step 4: 冗余压缩（合并相似内容）
        items = self._redundancy_compression(items)

        # 过滤低于最低信用度的条目
        items = [item for item in items
                 if getattr(item, "_credibility_score", 1.0) >= self._min_credibility]

        logger.info("降噪完成: 输出 %d 条", len(items))
        return items

    def _source_credibility_downgrade(self, items: List[RawInfoItem]) -> List[RawInfoItem]:
        """来源信用降权 — 基于 L3 历史准确率"""
        l3_accuracy = self._get_l3_source_accuracy()

        for item in items:
            base_score = self.SOURCE_CREDIBILITY.get(item.source, 0.5)
            # 如果 L3 有该来源的历史准确率，加权调整
            if item.source in l3_accuracy:
                l3_score = l3_accuracy[item.source]
                adjusted = base_score * 0.6 + l3_score * 0.4
            else:
                adjusted = base_score
            item._credibility_score = adjusted  # type: ignore[attr-defined]

        return items

    def _time_based_downgrade(self, items: List[RawInfoItem]) -> List[RawInfoItem]:
        """时效降权 — 7d/30d/永久三级"""
        now = datetime.now()

        for item in items:
            score = getattr(item, "_credibility_score", 1.0)
            ts = item.timestamp

            if ts is None:
                item._credibility_score = score * self.TIME_DECAY_30D  # type: ignore[attr-defined]
                continue

            age = now - ts
            if age <= timedelta(days=7):
                factor = self.TIME_DECAY_7D
            elif age <= timedelta(days=30):
                factor = self.TIME_DECAY_30D
            else:
                factor = self.TIME_DECAY_PERM

            item._credibility_score = score * factor  # type: ignore[attr-defined]

        return items

    def _consistency_filter(self, items: List[RawInfoItem]) -> List[RawInfoItem]:
        """一致性过滤 — 屏蔽已被证伪的信息"""
        if not self._memory:
            return items

        disproved_keywords: List[str] = []
        try:
            disproved = self._memory.search_long_term(
                keyword="已证伪", min_confidence=0.8, limit=20
            )
            for entry in disproved:
                content = entry.get("content", "")
                if content:
                    disproved_keywords.append(content[:20].lower())
        except Exception as exc:
            logger.warning("L3 证伪检索失败: %s", exc)
            return items

        if not disproved_keywords:
            return items

        filtered = []
        for item in items:
            content_lower = item.content.lower() if item.content else ""
            is_disproved = any(kw in content_lower for kw in disproved_keywords)
            if not is_disproved:
                filtered.append(item)
            else:
                logger.debug("一致性过滤: 屏蔽已证伪信息 — %s", item.title[:30])

        return filtered

    def _redundancy_compression(self, items: List[RawInfoItem]) -> List[RawInfoItem]:
        """冗余压缩 — 合并相似内容"""
        if len(items) <= 1:
            return items

        merged: List[RawInfoItem] = []
        used: set = set()

        for i, item in enumerate(items):
            if i in used:
                continue
            group = [item]
            for j in range(i + 1, len(items)):
                if j in used:
                    continue
                if self._is_similar(item, items[j]):
                    group.append(items[j])
                    used.add(j)

            # 取信用度最高的作为代表
            best = max(group, key=lambda x: getattr(x, "_credibility_score", 1.0))
            # 合并来源信息
            sources = list(set(it.source for it in group))
            if len(sources) > 1:
                best.content = f"[多源确认: {', '.join(sources)}] {best.content}"

            merged.append(best)
            used.add(i)

        return merged

    def _get_l3_source_accuracy(self) -> Dict[str, float]:
        """从 L3 记忆获取各来源历史准确率"""
        if not self._memory:
            return {}

        try:
            records = self._memory.search_long_term(
                keyword="source_accuracy", limit=50
            )
            accuracy: Dict[str, float] = {}
            for r in records:
                meta = r.get("metadata", {})
                source = meta.get("source", "")
                acc = meta.get("accuracy", 0.5)
                if source:
                    accuracy[source] = acc
            return accuracy
        except Exception:
            return {}

    @staticmethod
    def _is_similar(a: RawInfoItem, b: RawInfoItem) -> bool:
        """判断两个条目是否相似（基于标题字符重叠率）"""
        if not a.title or not b.title:
            return False
        set_a = set(a.title.lower())
        set_b = set(b.title.lower())
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return (intersection / union) >= 0.8 if union > 0 else False
