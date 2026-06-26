# -*- coding: utf-8 -*-
"""F020 记忆系统编排 — 统一使用 PostgreSQL + asyncpg + pgvector

B3 扩展：新增分层接口 add_intermediate / add_deep / search_by_layer，
对齐 FinMem 论文 §3.3 的分层记忆架构。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .working import WorkingMemory
from .l2_store import L2Store
from .l3_store import L3Store


def _default_db_url() -> str:
    """获取默认数据库 URL"""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://stockquant:stockquant_secret@localhost:5432/stockquant",
    )


class MemorySystem:
    """记忆系统 — 编排 L1/L2/L3 三层记忆

    存储后端: PostgreSQL + asyncpg + pgvector

    L3 分层（B3）：
        - shallow      浅层-市场新闻（3 天半衰期）
        - intermediate 中层-季报（90 天半衰期）
        - deep         深层-年报（365 天半衰期）
    L1 工作记忆通常不入 L3（独立的 working tier）。
    """

    def __init__(
        self,
        working_max_size: int = 200,
        db_url: str | None = None,
        user_id: str = "test_user",
    ) -> None:
        url = db_url or _default_db_url()
        self.l1 = WorkingMemory(max_size=working_max_size)
        self.l2 = L2Store(db_url=url, user_id=user_id)
        self.l3 = L3Store(db_url=url, user_id=user_id)

    # ── L1 接口 ──
    def add_working(self, entry: Dict[str, Any]) -> None:
        self.l1.append(entry)

    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        return self.l1.get_recent(n)

    def search_working(self, symbol: Optional[str] = None, since: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.l1.query(symbol=symbol, since=since)

    def get_sentiment_baseline(self, symbol: str, window_days: int = 30) -> float:
        return self.l1.get_sentiment_baseline(symbol, window_days)

    # ── L2 接口 ──
    def add_short_term(self, symbol: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        return self.l2.write({
            "user_id": self.l2._user_id,
            "symbol": symbol,
            "content": content,
            "metadata": metadata or {},
        })

    def search_short_term(
        self,
        symbol: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        results = self.l2.search(keyword or "", top_k=limit)
        if symbol:
            results = [r for r in results if r.get("symbol") == symbol]
        return results[:limit]

    # ── L3 接口 ──
    def add_long_term(self, insight: Dict[str, Any]) -> str:
        item = dict(insight)
        item.setdefault("user_id", self.l3._user_id)
        return self.l3.write(item)

    def search_long_term(
        self,
        symbol: Optional[str] = None,
        keyword: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        results = self.l3.search(keyword or "", top_k=limit)
        if symbol:
            results = [r for r in results if r.get("symbol") == symbol]
        if min_confidence > 0:
            results = [r for r in results if r.get("confidence", 0) >= min_confidence]
        return results[:limit]

    # ── B3: L3 分层接口 ────────────────────────────────────────────────

    def add_intermediate(
        self,
        symbol: str,
        content: str,
        period_type: str = "quarterly",
        importance: float = 0.5,
        summary: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """写入中层记忆（季报/中报/重大事件，tier=intermediate）

        Args:
            symbol: 标的代码
            content: 原始内容（季报全文/事件描述）
            period_type: 报告期类型（quarterly/half_year/mid_year）
            importance: 重要性评分 [0, 1]，默认 0.5
            summary: 摘要（可选）
            metadata: 额外元数据

        Returns:
            条目 ID
        """
        item = {
            "user_id": self.l3._user_id,
            "symbol": symbol,
            "content": content,
            "summary": summary,
            "metadata": metadata or {},
            "tier": "intermediate",
            "period_type": period_type,
            "importance_score": float(importance),
            "timestamp": datetime.now().isoformat(),
        }
        return self.l3.write(item)

    def add_deep(
        self,
        symbol: str,
        content: str,
        period_type: str = "annual",
        importance: float = 0.7,
        summary: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """写入深层记忆（年报/深度研报，tier=deep）

        Args:
            symbol: 标的代码
            content: 原始内容（年报全文/深度研报）
            period_type: 报告期类型（annual/biennial）
            importance: 重要性评分 [0, 1]，默认 0.7（高于 intermediate）
            summary: 摘要（可选）
            metadata: 额外元数据

        Returns:
            条目 ID
        """
        item = {
            "user_id": self.l3._user_id,
            "symbol": symbol,
            "content": content,
            "summary": summary,
            "metadata": metadata or {},
            "tier": "deep",
            "period_type": period_type,
            "importance_score": float(importance),
            "timestamp": datetime.now().isoformat(),
        }
        return self.l3.write(item)

    def search_by_layer(
        self,
        query: str,
        layer: str = "all",
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """按层检索（B3 新增）

        Args:
            query: 查询关键词
            layer: 检索层级，可选：
                - "working": L1 工作记忆
                - "shallow": L2 短期 + L3 浅层（市场新闻，3 天半衰期）
                - "intermediate": L3 中层（季报，90 天半衰期）
                - "deep": L3 深层（年报，365 天半衰期）
                - "all": 跨所有层检索（默认）
            top_k: 每层返回最大条目数

        Returns:
            合并后的检索结果，按 RecallScorer 综合评分排序
        """
        results: List[Dict[str, Any]] = []

        if layer == "all":
            # 跨层检索：L1 + L2 + L3（不分层）
            l1_items = self.l1.get_recent(n=top_k * 2)
            for item in l1_items:
                content = item.get("content", "")
                if query.lower() in content.lower():
                    results.append({**item, "layer": "working"})

            l2_items = self.l2.search(query, top_k=top_k)
            for item in l2_items:
                results.append({**item, "layer": "shallow"})

            l3_items = self.l3.search(query, top_k=top_k)
            for item in l3_items:
                layer_name = item.get("tier", "shallow")
                results.append({**item, "layer": layer_name})

            # 用 RecallScorer 跨层统一排序
            try:
                from .recall_scorer import RecallScorer
                scorer = RecallScorer(scene="default")
                # 每条 item 添加 layer 信息后用 RecallScorer 排序
                # tier 由 layer 字段决定（用于半衰期和重要性计算）
                ranked = []
                for item in results:
                    layer_tier = item.get("layer", "shallow")
                    # working / shallow / intermediate / deep 统一映射到 tier
                    tier = layer_tier if layer_tier in (
                        "working", "shallow", "intermediate", "deep"
                    ) else "shallow"
                    breakdown = scorer.score(
                        item, query_text=query, tier=tier
                    )
                    ranked.append((item, breakdown))
                ranked.sort(key=lambda x: x[1].final_score, reverse=True)
                return [
                    {**item, "_final_score": b.final_score, "_score_breakdown": b.to_dict()}
                    for item, b in ranked[:top_k]
                ]
            except Exception:
                # 降级：直接返回前 top_k 条
                return results[:top_k]

        if layer == "working":
            items = self.l1.get_recent(n=top_k * 2)
            for item in items:
                content = item.get("content", "")
                if query.lower() in content.lower():
                    results.append({**item, "layer": "working"})
            return results[:top_k]

        if layer == "shallow":
            # shallow 同时检索 L2 和 L3 中 tier=shallow 的条目
            l2_items = self.l2.search(query, top_k=top_k)
            for item in l2_items:
                results.append({**item, "layer": "shallow"})
            l3_items = self.l3.search_by_tier(query, tier="shallow", top_k=top_k)
            for item in l3_items:
                results.append({**item, "layer": "shallow"})
            return results[:top_k]

        if layer in ("intermediate", "deep"):
            items = self.l3.search_by_tier(query, tier=layer, top_k=top_k)
            for item in items:
                results.append({**item, "layer": layer})
            return results

        # 未知 layer 返回空
        return []

    # ── 清理（测试用） ──
    def clear_all(self) -> None:
        """清空 L2 和 L3 所有条目（用于测试隔离）"""
        self.l2.clear_all()
        self.l3.clear_all()

    # ── B6.3: 噪音模式库 + 已证伪事实（透传到 L3Store） ──────────────────

    def get_noise_patterns(self) -> List[str]:
        """获取已知噪音模式（B6.3 透传到 L3Store）

        供 DenoiseStage Step 4 调用，查询 L3 中存储的噪音模式（标题党/营销号模板）。
        """
        try:
            return self.l3.get_noise_patterns()
        except Exception:
            return []

    def get_disproved_facts(self, symbol: Optional[str] = None) -> List[str]:
        """获取已证伪事实（B6.3 透传到 L3Store）

        供 DenoiseStage Step 5 调用，查询 L3 中存储的已证伪事实。
        """
        try:
            return self.l3.get_disproved_facts(symbol=symbol)
        except Exception:
            return []
