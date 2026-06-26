# -*- coding: utf-8 -*-
"""F020 信息采集阶段

F020 Phase F4 增强：采集后自动运行数据源变更检测
- 集成 SourceVerifier.detect_source_change()（C6 已实现）
- 检测到变更时记录审计日志 + 发出 warning
- 可通过 enable_change_detection=False 禁用
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.pipeline")


@dataclass
class RawArticle:
    """原始采集文章"""
    title: str
    content: str
    url: str
    source: str
    published_at: Optional[datetime] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectionEvent:
    """采集事件"""
    symbols: List[str]
    sources: List[str] = field(default_factory=list)
    since: Optional[datetime] = None


class CollectionStage:
    """信息采集阶段 — 多渠道采集新闻和市场信息

    集成 NewsCollector (AlphaFeed/AkShare/直连API) + NewsSearcher

    F020 Phase F4：采集后自动运行数据源变更检测
    """

    def __init__(
        self,
        max_articles_per_source: int = 20,
        enable_change_detection: bool = True,
        verifier: Any = None,
    ) -> None:
        self._max_articles = max_articles_per_source
        self._news_collector = None
        # F4: 变更检测
        self._enable_change_detection = enable_change_detection
        self._verifier = verifier  # 可注入便于测试
        self._change_detector: Any = None  # lazy init

    def _get_news_collector(self):
        """获取新闻采集器单例"""
        if self._news_collector is None:
            try:
                from stockquant.ai.collectors.news_collector import NewsCollector
                self._news_collector = NewsCollector()
            except ImportError as e:
                logger.warning("NewsCollector not available: %s", e)
        return self._news_collector

    def execute(self, event: CollectionEvent) -> List[RawArticle]:
        """执行采集"""
        articles: List[RawArticle] = []
        for src in event.sources or ["news_searcher"]:
            try:
                if src == "news_searcher":
                    articles.extend(self._collect_from_news(event.symbols))
                else:
                    articles.extend(self._collect_from_source(src, event))
            except Exception as exc:
                logger.warning("Collection failed for source %s: %s", src, exc)
        # F4: 变更检测
        if self._enable_change_detection and articles:
            self.detect_source_changes(articles)
        return articles[:self._max_articles * 10]

    def _collect_from_news(self, symbols: List[str]) -> List[RawArticle]:
        """通过 NewsSearcher 采集"""
        try:
            from stockquant.ai.news_searcher import NewsSearcher
            searcher = NewsSearcher()
            articles = []
            for sym in symbols:
                items = searcher.search(sym, days=3)
                for item in items[:5]:
                    articles.append(RawArticle(
                        title=item.title,
                        content=item.summary,
                        url=item.url,
                        source=item.source,
                        published_at=item.published_at,
                        raw={"sentiment": item.sentiment},
                    ))
            return articles
        except ImportError:
            logger.warning("NewsSearcher not available")
            return []

    def _collect_from_source(self, source: str, event: CollectionEvent) -> List[RawArticle]:
        """通过 NewsCollector 采集多源新闻"""
        collector = self._get_news_collector()
        if collector is None:
            logger.warning("NewsCollector not available, falling back to NewsSearcher")
            return self._collect_from_news(event.symbols)
        
        articles: List[RawArticle] = []
        for symbol in event.symbols:
            try:
                # 同步调用异步采集器
                import asyncio
                items = asyncio.run(collector.collect(symbol, self._max_articles))
                for item in items:
                    articles.append(RawArticle(
                        title=item.title,
                        content=item.content or "",
                        url=item.url or "",
                        source=item.source,
                        published_at=item.timestamp if hasattr(item, 'timestamp') else None,
                        raw={"sentiment": item.sentiment_score, "symbol": item.symbol},
                    ))
            except Exception as exc:
                logger.warning("Collection failed for source %s, symbol %s: %s", source, symbol, exc)
        
        return articles

    # ── F020 Phase F4: 数据源变更检测 ─────────────────────────────────

    def _get_change_detector(self):
        """获取 SourceVerifier 实例（可注入）"""
        if self._change_detector is None:
            if self._verifier is not None:
                self._change_detector = self._verifier
            else:
                try:
                    from stockquant.ai.collectors.verifier import SourceVerifier
                    self._change_detector = SourceVerifier()
                except ImportError:
                    logger.warning("SourceVerifier not available, 变更检测禁用")
                    self._change_detector = None
        return self._change_detector

    def detect_source_changes(self, articles: List[RawArticle]) -> List[Dict[str, Any]]:
        """对采集到的文章按源分组运行变更检测

        Args:
            articles: 已采集的文章列表

        Returns:
            变更检测结果列表（仅包含 changed=True 的源）
        """
        if not articles:
            return []
        # 按源分组，拼接内容用于指纹计算
        source_to_content: Dict[str, List[str]] = {}
        for a in articles:
            if a.source:
                source_to_content.setdefault(a.source, []).append(a.content or "")

        detector = self._get_change_detector()
        if detector is None:
            return []

        changes: List[Dict[str, Any]] = []
        for source, contents in source_to_content.items():
            text = "\n---\n".join(contents)
            try:
                result = detector.detect_source_change(source, text)
                if result.get("changed"):
                    changes.append(result)
                    logger.warning(
                        "数据源 [%s] 结构可能变更: %s → %s",
                        source,
                        result.get("previous_fingerprint", "")[:8],
                        result.get("current_fingerprint", "")[:8],
                    )
                    # 写入审计日志（同步接口，避免在 execute() 中触发 async）
                    try:
                        from stockquant.ai.collectors.audit_log import get_audit_log
                        get_audit_log().append_sync(
                            collector="collection_stage",
                            action="source_change_detected",
                            source=source,
                            result="partial",
                            count=len(contents),
                            metadata={
                                "previous_fingerprint": result.get("previous_fingerprint"),
                                "current_fingerprint": result.get("current_fingerprint"),
                            },
                        )
                    except Exception as log_exc:
                        logger.debug("写入变更检测审计日志失败: %s", log_exc)
            except Exception as exc:
                logger.debug("变更检测失败 source=%s: %s", source, exc)

        if changes:
            logger.info(
                "采集后变更检测：%d 个数据源结构变更: %s",
                len(changes),
                [c["source"] for c in changes],
            )
        return changes
