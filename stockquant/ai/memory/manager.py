# -*- coding: utf-8 -*-
"""F020 记忆管理器 — 代理到 ReportSystem（日报/月报/年报三级报告体系）

向后兼容旧接口，内部使用 ReportSystem 实现。
保留 search / write / compress / forget / get_noise_patterns / get_disproved_facts / close 接口。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.memory.manager")


def _default_db_url() -> str:
    """获取默认数据库 URL"""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://stockquant:stockquant_secret@localhost:5432/stockquant",
    )


class MemoryManager:
    """记忆管理器 — 代理到 ReportSystem

    保留旧接口供外部调用方使用，内部统一委托给 ReportSystem。
    旧 write(level, item) 接口映射:
    - level=1 → 写入日报（daily report 作为工作记忆替代）
    - level=2 → 写入日报（daily report）
    - level=3 → 写入月报或年报（monthly/annual report）

    旧 search() 接口映射到 ReportSystem.search_by_layer()。
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        working_max_size: int = 200,
        llm_adapter: Any = None,
    ) -> None:
        url = db_url or _default_db_url()
        try:
            from .system import ReportSystem
            self._system = ReportSystem(
                db_url=url,
                user_id="test_user",
                llm_adapter=llm_adapter,
            )
        except Exception as exc:
            logger.warning("ReportSystem 初始化失败，降级为空壳: %s", exc)
            self._system = None

        # 兼容旧接口：保留对 compressor / forgetting 的引用
        try:
            from .forgetting import ForgettingMechanism
            self._forgetting = ForgettingMechanism()
        except ImportError:
            self._forgetting = None

        try:
            from .compressor import MemoryCompressor
            self._compressor = MemoryCompressor(llm_adapter=llm_adapter)
        except ImportError:
            self._compressor = None

    def write(self, level: int, item: Dict[str, Any]) -> str:
        """写入记忆（向后兼容）

        映射到 ReportSystem:
        - level=1 → 转换为日报条目
        - level=2 → 转换为日报条目
        - level=3 → 转换为月报/年报条目
        """
        if self._system is not None:
            try:
                # 将旧的 level 映射到 report_type
                report_type_map = {1: "daily", 2: "daily", 3: "monthly"}
                report_type = report_type_map.get(level, "daily")
                report_item = {
                    "report_type": report_type,
                    "report_date": datetime.now().strftime("%Y-%m-%d"),
                    "report_period_start": datetime.now().strftime("%Y-%m-%d"),
                    "report_period_end": datetime.now().strftime("%Y-%m-%d"),
                    "market_review": item.get("content", ""),
                    "trading_record": "",
                    "strategy_performance": "",
                    "ai_insights": "",
                    "metrics_json": "{}",
                    "metadata_json": str(item.get("metadata", {})),
                    "full_content": item.get("content", ""),
                    "summary": item.get("summary", ""),
                    "confidence": item.get("confidence", 1.0),
                    "importance_score": item.get("importance_score", 0.5),
                }
                return self._system.add_report(report_item)
            except Exception as exc:
                logger.debug("MemoryManager.write 通过 ReportSystem 失败: %s", exc)

        # 降级：返回一个模拟 ID
        return f"{report_type_map.get(level, 'daily')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def search(self, query: str, levels: Optional[List[int]] = None, top_k: int = 10) -> List[Dict[str, Any]]:
        """检索记忆（向后兼容，映射到 ReportSystem.search_by_layer）"""
        if self._system is not None:
            try:
                return self._system.search_by_layer(query, layer="all", top_k=top_k)
            except Exception as exc:
                logger.debug("MemoryManager.search 通过 ReportSystem 失败: %s", exc)
        return []

    def search_unified(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """跨层统一评分检索（向后兼容）"""
        return self.search(query, levels=[1, 2, 3], top_k=top_k)

    def compress(self) -> int:
        """压缩迁移（向后兼容）

        日报 → 月报 / 月报 → 年报 的聚合升级。
        """
        if self._compressor is not None:
            try:
                return self._compressor.compress(self._system)
            except Exception as exc:
                logger.debug("MemoryManager.compress 失败: %s", exc)
        return 0

    def forget(self) -> Dict[str, int]:
        """执行遗忘机制（向后兼容）

        基于 report_type 的过期策略。
        """
        result: Dict[str, int] = {"daily": 0, "monthly": 0, "annual": 0}
        if self._forgetting is not None and self._system is not None:
            try:
                result = self._forgetting.forget(self._system)
            except Exception as exc:
                logger.debug("MemoryManager.forget 失败: %s", exc)
        return result

    # ── B6.3: 噪音模式库 + 已证伪事实（透传） ──────────────────────

    def get_noise_patterns(self) -> List[str]:
        """获取已知噪音模式（B6.3 透传）"""
        if self._system is not None:
            return self._system.get_noise_patterns()
        return []

    def get_disproved_facts(self, symbol: Optional[str] = None) -> List[str]:
        """获取已证伪事实（B6.3 透传）"""
        if self._system is not None:
            return self._system.get_disproved_facts(symbol=symbol)
        return []

    def close(self) -> None:
        """关闭所有连接（向后兼容）"""
        # ReportSystem 目前无连接需关闭
        pass
