# -*- coding: utf-8 -*-
"""F020 信息降噪阶段 — 5 步完整化（B5.1）

合并旧版 DEPRECATED `denoiser.py` 的 L3 集成能力：

Step 1: temporal_filter   — 时效过滤（24h 默认，保留）
Step 2: deduplicate       — Jaccard 语义去重（≥60%，保留）
Step 3: source_rank       — 信源信用度排序（保留）
Step 4: l3_noise_filter   — 查询 L3 已知噪音模式（标题党/营销号模板）过滤
Step 5: l3_disproved_filter — 查询 L3 已证伪事实，降权或过滤

设计原则：
- 完全向后兼容：旧调用 `DenoiseStage().execute(articles)` 不需修改
- 渐进增强：传入 memory_system 才启用 Step 4/5；不传则等同旧 3 步
- 不引入新依赖
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .collection import RawArticle

logger = logging.getLogger("stockquant.ai.pipeline.denoise")


# ─── 默认噪音模式库（无需 L3 即可使用） ────────────────────────────────
# 当 L3 中无噪音模式记录时使用此默认库。B6.3 后续可将运行时学习的模式写入 L3。
DEFAULT_NOISE_PATTERNS: List[str] = [
    # 标题党模板
    "震惊",
    "速看",
    "曝光",
    "揭秘",
    "重大利好",  # 仅当无来源支撑时为噪音
    "重大利空",
    # 营销号模板
    "扫码进群",
    "加微信",
    "免费诊股",
    "推荐牛股",
    "内幕消息",
    "稳赚不赔",
    "包赚",
    "翻倍",
    "百倍",
]


class DenoiseStage:
    """信息降噪阶段 — 5 步完整化

    Step 1: temporal_filter      时效过滤
    Step 2: deduplicate          Jaccard 去重
    Step 3: source_rank          信源排序
    Step 4: l3_noise_filter      L3 噪音模式过滤
    Step 5: l3_disproved_filter  L3 已证伪事实过滤

    用法（向后兼容）：
        stage = DenoiseStage()
        filtered = stage.execute(articles)

    用法（启用 L3 集成）：
        stage = DenoiseStage(memory_system=memory)
        filtered = stage.execute(articles)
    """

    def __init__(
        self,
        max_articles: int = 30,
        max_age_hours: int = 24,
        memory_system: Any = None,
        noise_similarity_threshold: float = 0.6,
        disproved_score_threshold: float = 0.5,
    ) -> None:
        self._max = max_articles
        self._max_age = timedelta(hours=max_age_hours)
        self._memory = memory_system
        self._noise_threshold = noise_similarity_threshold
        self._disproved_threshold = disproved_score_threshold
        # 缓存 L3 噪音/已证伪记录，避免每条文章都查一次
        self._noise_cache: Optional[List[str]] = None
        self._disproved_cache: Optional[List[str]] = None

    def execute(self, articles: List[RawArticle]) -> List[RawArticle]:
        """执行 5 步降噪"""
        if not articles:
            return []

        # Step 1: 时效过滤
        articles = self._temporal_filter(articles)
        logger.debug("Step 1 temporal_filter: %d → %d", len(articles), len(articles))

        # Step 2: 语义去重
        before = len(articles)
        articles = self._deduplicate(articles)
        logger.debug("Step 2 deduplicate: %d → %d", before, len(articles))

        # Step 3: 按来源信用度排序
        articles = self._source_rank(articles)

        # Step 4: L3 噪音模式过滤
        before = len(articles)
        articles = self._l3_noise_filter(articles)
        logger.debug("Step 4 l3_noise_filter: %d → %d", before, len(articles))

        # Step 5: L3 已证伪事实过滤
        before = len(articles)
        articles = self._l3_disproved_filter(articles)
        logger.debug("Step 5 l3_disproved_filter: %d → %d", before, len(articles))

        return articles[: self._max]

    # ─── Step 1: 时效过滤 ───────────────────────────────────────────────
    def _temporal_filter(self, articles: List[RawArticle]) -> List[RawArticle]:
        """过滤超过时效的文章"""
        cutoff = datetime.now() - self._max_age
        return [
            a for a in articles
            if a.published_at is None or a.published_at >= cutoff
        ]

    # ─── Step 2: 语义去重 ───────────────────────────────────────────────
    def _deduplicate(self, articles: List[RawArticle]) -> List[RawArticle]:
        """语义去重 — 基于 Jaccard 词集合重叠率（≥60% 视为重复）"""
        seen: List[RawArticle] = []
        for a in articles:
            title_words = set(a.title.lower().split())
            if not title_words:
                seen.append(a)
                continue
            is_dup = False
            for existing in seen:
                exist_words = set(existing.title.lower().split())
                if not exist_words:
                    continue
                overlap = len(title_words & exist_words)
                min_len = min(len(title_words), len(exist_words))
                if min_len > 0 and overlap / min_len >= 0.6:
                    is_dup = True
                    break
            if not is_dup:
                seen.append(a)
        return seen

    # ─── Step 3: 信源排序 ───────────────────────────────────────────────
    def _source_rank(self, articles: List[RawArticle]) -> List[RawArticle]:
        """按来源信用度排序"""
        score_map = {
            "cninfo": 1.0,
            "cls": 0.9,
            "eastmoney": 0.8,
            "xueqiu": 0.6,
            "news_searcher": 0.7,
        }
        return sorted(
            articles,
            key=lambda a: score_map.get(a.source, 0.5),
            reverse=True,
        )

    # ─── Step 4: L3 噪音模式过滤 ───────────────────────────────────────
    def _l3_noise_filter(self, articles: List[RawArticle]) -> List[RawArticle]:
        """Step 4 — 查询 L3 已知噪音模式 + 默认噪音模式库

        过滤匹配噪音模式的文章：
        - 标题党模板（震惊/速看/曝光等）
        - 营销号模板（扫码进群/免费诊股等）
        - L3 运行时学习的噪音模式
        """
        patterns = self._get_noise_patterns()
        if not patterns:
            return articles

        filtered: List[RawArticle] = []
        for a in articles:
            is_noise = self._match_noise_pattern(a, patterns)
            if not is_noise:
                filtered.append(a)
            else:
                logger.debug("noise_filter 屏蔽: %s", a.title[:50])
        return filtered

    def _get_noise_patterns(self) -> List[str]:
        """获取噪音模式（默认库 + L3 缓存）"""
        if self._noise_cache is not None:
            return self._noise_cache

        patterns: List[str] = list(DEFAULT_NOISE_PATTERNS)

        # 从 L3 检索已学习的噪音模式
        if self._memory is not None:
            try:
                # B6.3 优先使用专门的 get_noise_patterns 接口
                if hasattr(self._memory, "get_noise_patterns"):
                    l3_patterns = self._memory.get_noise_patterns()
                    patterns.extend(p for p in l3_patterns if p)
                else:
                    # 降级：通过 search_long_term 检索 type=noise_pattern 的条目
                    noise_records = self._memory.search_long_term(
                        keyword="noise_pattern", limit=50
                    )
                    for r in noise_records:
                        content = r.get("content", "")
                        if content:
                            patterns.append(content[:80])
            except Exception as exc:
                logger.warning("L3 噪音模式检索失败，使用默认库: %s", exc)

        # 去重
        self._noise_cache = list(dict.fromkeys(patterns))
        return self._noise_cache

    @staticmethod
    def _match_noise_pattern(article: RawArticle, patterns: List[str]) -> bool:
        """判断文章是否匹配噪音模式

        简单关键词包含匹配（噪音模式通常为关键词模板）。
        """
        text = (article.title or "") + " " + (article.content or "")
        text_lower = text.lower()
        for pattern in patterns:
            if not pattern:
                continue
            if pattern.lower() in text_lower:
                return True
        return False

    # ─── Step 5: L3 已证伪事实过滤 ─────────────────────────────────────
    def _l3_disproved_filter(self, articles: List[RawArticle]) -> List[RawArticle]:
        """Step 5 — 查询 L3 已证伪事实，降权或过滤

        - 如果文章内容包含已证伪声明，且置信度低于阈值，过滤
        - 否则保留（让上层决定如何降权）
        """
        disproved = self._get_disproved_facts()
        if not disproved:
            return articles

        filtered: List[RawArticle] = []
        for a in articles:
            confidence = a.raw.get("confidence", 1.0) if a.raw else 1.0
            is_disproved = self._match_disproved(a, disproved)
            if is_disproved and confidence < self._disproved_threshold:
                logger.debug("disproved_filter 屏蔽低置信已证伪: %s", a.title[:50])
                continue
            filtered.append(a)
        return filtered

    def _get_disproved_facts(self) -> List[str]:
        """获取已证伪事实（L3）"""
        if self._disproved_cache is not None:
            return self._disproved_cache

        facts: List[str] = []
        if self._memory is not None:
            try:
                # B6.3 优先使用专门的 get_disproved_facts 接口
                if hasattr(self._memory, "get_disproved_facts"):
                    l3_disproved = self._memory.get_disproved_facts()
                    facts.extend(f for f in l3_disproved if f)
                else:
                    # 降级：通过 search_long_term 检索 type=disproved 的条目
                    disproved_records = self._memory.search_long_term(
                        keyword="已证伪", limit=30
                    )
                    for r in disproved_records:
                        content = r.get("content", "")
                        if content:
                            facts.append(content[:80])
            except Exception as exc:
                logger.warning("L3 已证伪事实检索失败: %s", exc)

        self._disproved_cache = facts
        return facts

    @staticmethod
    def _match_disproved(article: RawArticle, disproved: List[str]) -> bool:
        """判断文章是否包含已证伪声明"""
        text = (article.title or "") + " " + (article.content or "")
        text_lower = text.lower()
        for fact in disproved:
            if not fact:
                continue
            if fact.lower() in text_lower:
                return True
        return False


# ─── 工厂函数（保持与旧版 Denoiser 兼容的导入路径） ────────────────────
def make_denoise_stage(
    max_articles: int = 30,
    max_age_hours: int = 24,
    memory_system: Any = None,
) -> DenoiseStage:
    """构造 DenoiseStage — 便捷工厂"""
    return DenoiseStage(
        max_articles=max_articles,
        max_age_hours=max_age_hours,
        memory_system=memory_system,
    )
