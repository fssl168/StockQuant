# -*- coding: utf-8 -*-
"""F020 来源验证 + 事实初筛（C6: FAKE_SOURCES 黑名单 + 变更检测）

增强点：
- 预置初始仿冒源黑名单（FAKE_SOURCES）
- 支持运行时动态扩展黑名单（add_fake_source / register_fake_sources）
- 新增 detect_source_change() 检测数据源页面结构变更（占位接口）
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional, Set

from .base import RawInfoItem

logger = logging.getLogger("stockquant.ai.collectors.verifier")


class SourceVerifier:
    """来源验证器 — 检测仿冒源、重复内容、过期信息

    Attributes:
        TRUSTED_SOURCES: 可信源白名单
        FAKE_SOURCES: 仿冒源黑名单（运行时可扩展）
    """

    # 可信源白名单
    TRUSTED_SOURCES = {
        "eastmoney", "sina", "cninfo", "xueqiu", "sse", "szse",
        # C6: 新增可信源（新采集器产生的）
        "eastmoney_research", "sina_financial", "eastmoney_financial",
        "sse_disclosure", "szse_disclosure", "exchange_lhb",
        "eastmoney_express", "xueqiu_hot", "cls_telegraph",
        "cctv", "global_em", "alphafeed",
    }

    # C6: 初始仿冒源黑名单
    INITIAL_FAKE_SOURCES: Set[str] = {
        "fake-eastmoney", "fake-sina", "fake-cninfo",
        "stock-tip-xxx", "spam-news", "unknown-source",
        # 常见营销号源
        "toutiao-promo", "wechat-spam", "free-stock-tip",
    }

    def __init__(self) -> None:
        # C6: 实例级黑名单（可运行时扩展，不污染类级常量）
        self.FAKE_SOURCES: Set[str] = set(self.INITIAL_FAKE_SOURCES)
        # C6: 源结构指纹缓存（用于变更检测）
        self._source_fingerprints: Dict[str, str] = {}

    def verify(self, items: List[RawInfoItem]) -> List[RawInfoItem]:
        """验证信息来源，标记不可信项

        Args:
            items: 待验证条目列表

        Returns:
            通过验证的条目列表（已过滤 FAKE_SOURCES 中的条目）
        """
        for item in items:
            item.verified = self._is_trusted(item)
        return [item for item in items if item.verified or item.source not in self.FAKE_SOURCES]

    def _is_trusted(self, item: RawInfoItem) -> bool:
        """检查来源是否可信"""
        return item.source.lower() in self.TRUSTED_SOURCES

    # ── C6: 黑名单动态扩展 ──────────────────────────────────────────────

    def add_fake_source(self, source: str) -> None:
        """添加单个仿冒源到黑名单

        Args:
            source: 仿冒源标识（小写）
        """
        if source:
            self.FAKE_SOURCES.add(source.lower())
            logger.info("添加仿冒源到黑名单: %s", source)

    def register_fake_sources(self, sources: List[str]) -> int:
        """批量添加仿冒源到黑名单

        Args:
            sources: 仿冒源标识列表

        Returns:
            新增的条目数
        """
        original_count = len(self.FAKE_SOURCES)
        for source in sources:
            if source:
                self.FAKE_SOURCES.add(source.lower())
        added = len(self.FAKE_SOURCES) - original_count
        if added > 0:
            logger.info("批量添加 %d 个仿冒源到黑名单", added)
        return added

    def is_fake_source(self, source: str) -> bool:
        """检查给定源是否在黑名单中"""
        return source.lower() in self.FAKE_SOURCES if source else False

    def get_fake_sources(self) -> Set[str]:
        """获取当前黑名单（只读视图）"""
        return set(self.FAKE_SOURCES)

    # ── C6: 数据源变更检测 ──────────────────────────────────────────────

    def detect_source_change(
        self,
        source: str,
        current_response: str,
    ) -> Dict[str, Any]:
        """检测数据源页面结构是否变更

        通过对响应内容计算指纹（hash），与上次采集的指纹对比。
        如果指纹不同，可能意味着数据源页面结构已变更（API 改版/反爬升级）。

        Args:
            source: 数据源标识
            current_response: 当前响应文本

        Returns:
            变更检测结果字典：
            - source: 数据源
            - changed: 是否变更
            - current_fingerprint: 当前指纹
            - previous_fingerprint: 上次指纹（首次采集为 None）
        """
        current_fp = self._compute_fingerprint(current_response)
        previous_fp = self._source_fingerprints.get(source)

        result = {
            "source": source,
            "changed": previous_fp is not None and previous_fp != current_fp,
            "current_fingerprint": current_fp,
            "previous_fingerprint": previous_fp,
        }

        # 更新缓存
        self._source_fingerprints[source] = current_fp

        if result["changed"]:
            logger.warning(
                "数据源 [%s] 结构可能变更: %s → %s",
                source, previous_fp, current_fp,
            )

        return result

    @staticmethod
    def _compute_fingerprint(text: str) -> str:
        """计算响应文本的结构指纹

        使用 SHA-256 哈希，只取前 16 字节作为短指纹（便于日志展示）。
        """
        if not text:
            return ""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

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
