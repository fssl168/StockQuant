# -*- coding: utf-8 -*-
"""F020 记忆管理器 — 编排 L1/L2/L3 三层记忆 + 压缩 + 遗忘（B6: 跨层统一评分）

统一使用 PostgreSQL + asyncpg + pgvector 作为存储后端。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .working import WorkingMemory
from .l2_store import L2Store
from .l3_store import L3Store
from .forgetting import ForgettingMechanism
from .compressor import MemoryCompressor

logger = logging.getLogger("stockquant.ai.memory.manager")


def _default_db_url() -> str:
    """获取默认数据库 URL"""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://stockquant:stockquant_secret@localhost:5432/stockquant",
    )


class MemoryManager:
    """记忆管理器 — 统一管理 L1/L2/L3 三层记忆

    职责:
    1. 统一写入/检索接口
    2. L2→L3 压缩迁移
    3. 过期/低置信度遗忘
    4. B6: 跨层统一评分（基于 RecallScorer 三因子融合）

    存储后端: PostgreSQL + asyncpg + pgvector
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        working_max_size: int = 200,
        llm_adapter: Any = None,
    ) -> None:
        url = db_url or _default_db_url()
        self.l1 = WorkingMemory(max_size=working_max_size)
        self.l2 = L2Store(db_url=url)
        self.l3 = L3Store(db_url=url)
        self._forgetting = ForgettingMechanism()
        # B6.1: 把 LLM 适配器传给 compressor
        self._compressor = MemoryCompressor(llm_adapter=llm_adapter)
        # B6: 跨层评分器
        try:
            from .recall_scorer import RecallScorer
            self._scorer = RecallScorer(scene="default")
        except ImportError:
            self._scorer = None

    def write(self, level: int, item: Dict[str, Any]) -> str:
        """写入指定层级的记忆

        Args:
            level: 1=L1工作记忆, 2=L2短期记忆, 3=L3长期记忆
            item: 记忆条目

        Returns:
            条目 ID
        """
        if level == 1:
            self.l1.append(item)
            return f"l1_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        elif level == 2:
            return self.l2.write(item)
        elif level == 3:
            return self.l3.write(item)
        else:
            raise ValueError(f"无效的记忆层级: {level}")

    def search(self, query: str, levels: Optional[List[int]] = None, top_k: int = 10) -> List[Dict[str, Any]]:
        """跨层检索（B6: 应用 RecallScorer 统一评分）

        Args:
            query: 检索查询
            levels: 要检索的层级列表，默认 [1, 2, 3]
            top_k: 每层返回的最大条目数

        Returns:
            合并后的检索结果（按 RecallScorer 综合评分降序）
        """
        levels = levels or [1, 2, 3]
        results: List[Dict[str, Any]] = []

        if 1 in levels:
            l1_items = self.l1.get_recent(n=top_k)
            for item in l1_items:
                content = item.get("content", "")
                if query.lower() in content.lower():
                    results.append({**item, "level": 1, "tier": "working"})

        if 2 in levels:
            l2_items = self.l2.search(query, top_k=top_k)
            for item in l2_items:
                results.append({**item, "level": 2, "tier": "shallow"})

        if 3 in levels:
            l3_items = self.l3.search(query, top_k=top_k)
            for item in l3_items:
                results.append({**item, "level": 3})

        # B6: 应用跨层 RecallScorer 统一评分
        return self._cross_layer_rerank(results, query, top_k)

    def search_unified(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """跨层统一评分检索（B6 新增）

        对 L1+L2+L3 三层结果统一应用 RecallScorer 三因子评分
        （relevance + recency + importance），返回 Top-K。

        Args:
            query: 检索查询
            top_k: 返回最大条目数

        Returns:
            按综合评分降序排列的记忆条目列表
        """
        return self.search(query, levels=[1, 2, 3], top_k=top_k)

    def _cross_layer_rerank(
        self,
        items: List[Dict[str, Any]],
        query: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """跨层 RecallScorer 重排序（B6）

        对所有层的结果统一评分，按评分降序返回 Top-K。
        评分失败时降级为原始顺序。
        """
        if not items:
            return []

        if self._scorer is None:
            return items[:top_k * 3]

        try:
            # 给每条记忆补充 tier 字段（如果缺失）
            normalized: List[Dict[str, Any]] = []
            for item in items:
                if "tier" not in item:
                    # L1 -> working, L2 -> shallow, L3 -> 用 item 自身 tier
                    level = item.get("level", 3)
                    if level == 1:
                        item["tier"] = "working"
                    elif level == 2:
                        item["tier"] = "shallow"
                    else:
                        item["tier"] = item.get("tier", "shallow")
                normalized.append(item)

            ranked = self._scorer.rank(normalized, query=query, top_k=top_k * 3)
            return [item for item, _ in ranked][:top_k * 3]
        except Exception as exc:
            logger.debug("跨层 RecallScorer 评分失败，降级原始顺序: %s", exc)
            return items[:top_k * 3]

    def compress(self) -> int:
        """L2→L3 压缩迁移

        将 L2 中较旧的条目压缩摘要后迁移到 L3。

        Returns:
            迁移的条目数
        """
        migrated = self._compressor.compress_l2_to_l3(self.l2, self.l3)
        if migrated > 0:
            logger.info("L2→L3 压缩迁移: %d 条", migrated)
        return migrated

    def forget(self) -> Dict[str, int]:
        """执行遗忘机制

        Returns:
            各层删除的条目数 {"l2": n, "l3": n}
        """
        result = self._forgetting.forget(self.l2, self.l3)
        total = sum(result.values())
        if total > 0:
            logger.info("遗忘清理: L2=%d, L3=%d", result.get("l2", 0), result.get("l3", 0))
        return result

    # ── B6.3: 噪音模式库 + 已证伪事实（透传到 L3） ──────────────────────

    def get_noise_patterns(self) -> List[str]:
        """获取已知噪音模式（B6.3 透传到 L3Store）"""
        try:
            return self.l3.get_noise_patterns()
        except Exception as exc:
            logger.debug("MemoryManager.get_noise_patterns 失败: %s", exc)
            return []

    def get_disproved_facts(self, symbol: Optional[str] = None) -> List[str]:
        """获取已证伪事实（B6.3 透传到 L3Store）"""
        try:
            return self.l3.get_disproved_facts(symbol=symbol)
        except Exception as exc:
            logger.debug("MemoryManager.get_disproved_facts 失败: %s", exc)
            return []

    def close(self) -> None:
        """关闭所有存储连接"""
        self.l2.close()
        self.l3.close()
