# -*- coding: utf-8 -*-
"""F020 报告系统编排 — 日报/月报/年报三级报告体系

替代原有 L1/L2/L3 三级记忆系统（MemorySystem），采用日报(daily)/月报(monthly)/
年报(annual) 三级报告体系作为新的主入口。

核心类:
- ReportSystem: 报告系统编排层（替代 MemorySystem）
- ReportStore: 报告存储层（另个任务实现，此处 try/except 导入）
- ReportGenerator: 报告生成器（另个任务实现，此处 try/except 导入）

旧接口兼容:
- search_by_layer() — 旧的分层检索映射到新的 report_type 检索
- get_recent() — 旧的最近记忆映射到最近日报列表
- get_noise_patterns() / get_disproved_facts() — 透传到 L3Store
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.memory.system")


# ─── 尝试导入 ReportStore / ReportGenerator（另个任务实现） ──────

try:
    from .report_store import ReportStore
except ImportError:
    ReportStore = None  # type: ignore[assignment,misc]

try:
    from .report_generator import ReportGenerator
except ImportError:
    ReportGenerator = None  # type: ignore[assignment,misc]


# ─── ReportSystem ──────────────────────────────────────────────────


class ReportSystem:
    """报告系统 — 编排日报/月报/年报三级报告体系

    替代原有 MemorySystem（L1/L2/L3 三层记忆），提供以下能力：
    - 日报：每日市场回顾、交易记录、策略表现、AI 洞察
    - 月报：聚合当月所有日报，生成月度策略复盘
    - 年报：聚合当年所有月报，生成年度总结
    - 统一检索：跨所有报告类型的全文/向量检索

    存储后端: PostgreSQL + pgvector
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        user_id: str = "test_user",
        llm_adapter: Any = None,
    ) -> None:
        # ReportStore / ReportGenerator 实现留到另个任务
        if ReportStore is not None:
            self.store = ReportStore(db_url=db_url, user_id=user_id)
        else:
            logger.warning("ReportStore 未实现，ReportSystem.store 设为 None")
            self.store = None  # type: ignore[assignment]

        if ReportGenerator is not None:
            self.generator = ReportGenerator(llm_adapter=llm_adapter, store=self.store)
        else:
            logger.warning("ReportGenerator 未实现，ReportSystem.generator 设为 None")
            self.generator = None  # type: ignore[assignment]

    # ── 日报接口 ──

    def generate_daily_report(self, date: Optional[str] = None) -> str:
        """AI 自动生成日报

        Args:
            date: 日期字符串 YYYY-MM-DD，默认为今天

        Returns:
            生成的日报内容
        """
        if self.generator is None:
            raise NotImplementedError("ReportGenerator 尚未实现，无法生成日报")
        return self.generator.generate_daily(date)

    def get_daily_report(self, date: str) -> Optional[Dict]:
        """获取指定日期的日报

        Args:
            date: 日期字符串 YYYY-MM-DD

        Returns:
            日报字典，不存在返回 None
        """
        if self.store is None:
            raise NotImplementedError("ReportStore 尚未实现")
        return self.store.get_report("daily", date)

    def list_daily_reports(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """列出日报

        Args:
            start: 起始日期（可选）
            end: 截止日期（可选）
            limit: 最大返回数量

        Returns:
            日报字典列表
        """
        if self.store is None:
            raise NotImplementedError("ReportStore 尚未实现")
        return self.store.list_reports("daily", start, end, limit)

    # ── 月报接口 ──

    def generate_monthly_report(self, year_month: Optional[str] = None) -> str:
        """AI 自动生成月报（聚合当月所有日报）

        Args:
            year_month: 年月字符串 YYYY-MM，默认为当前月

        Returns:
            生成的月报内容
        """
        if self.generator is None:
            raise NotImplementedError("ReportGenerator 尚未实现，无法生成月报")
        return self.generator.generate_monthly(year_month)

    def get_monthly_report(self, year_month: str) -> Optional[Dict]:
        """获取指定年月的月报

        Args:
            year_month: 年月字符串 YYYY-MM

        Returns:
            月报字典，不存在返回 None
        """
        if self.store is None:
            raise NotImplementedError("ReportStore 尚未实现")
        return self.store.get_report("monthly", year_month)

    def list_monthly_reports(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """列出月报

        Args:
            start: 起始年月（可选）
            end: 截止年月（可选）
            limit: 最大返回数量

        Returns:
            月报字典列表
        """
        if self.store is None:
            raise NotImplementedError("ReportStore 尚未实现")
        return self.store.list_reports("monthly", start, end, limit)

    # ── 年报接口 ──

    def generate_annual_report(self, year: Optional[str] = None) -> str:
        """AI 自动生成年报（聚合当年所有月报）

        Args:
            year: 年份字符串 YYYY，默认为当前年

        Returns:
            生成的年报内容
        """
        if self.generator is None:
            raise NotImplementedError("ReportGenerator 尚未实现，无法生成年报")
        return self.generator.generate_annual(year)

    def get_annual_report(self, year: str) -> Optional[Dict]:
        """获取指定年份的年报

        Args:
            year: 年份字符串 YYYY

        Returns:
            年报字典，不存在返回 None
        """
        if self.store is None:
            raise NotImplementedError("ReportStore 尚未实现")
        return self.store.get_report("annual", year)

    def list_annual_reports(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """列出年报

        Args:
            start: 起始年份（可选）
            end: 截止年份（可选）
            limit: 最大返回数量

        Returns:
            年报字典列表
        """
        if self.store is None:
            raise NotImplementedError("ReportStore 尚未实现")
        return self.store.list_reports("annual", start, end, limit)

    # ── 统一检索 ──

    def search(
        self,
        query: str,
        report_type: str = "all",
        top_k: int = 10,
    ) -> List[Dict]:
        """跨所有报告类型的统一检索

        Args:
            query: 检索查询
            report_type: 报告类型（all/daily/monthly/annual）
            top_k: 返回最大条目数

        Returns:
            检索结果列表
        """
        if self.store is None:
            raise NotImplementedError("ReportStore 尚未实现")
        return self.store.search(query, report_type, top_k)

    # ── CRUD ──

    def add_report(self, report: Dict) -> str:
        """写入一份报告

        Args:
            report: 报告字典（含 report_type/report_date 等字段）

        Returns:
            报告 ID
        """
        if self.store is None:
            raise NotImplementedError("ReportStore 尚未实现")
        return self.store.write(report)

    def delete_report(self, report_id: str) -> bool:
        """删除一份报告

        Args:
            report_id: 报告 ID

        Returns:
            是否删除成功
        """
        if self.store is None:
            raise NotImplementedError("ReportStore 尚未实现")
        return self.store.delete(report_id)

    # ── 兼容旧接口（供 InsightsBridge 等调用方使用） ──

    def search_by_layer(
        self,
        query: str,
        layer: str = "all",
        top_k: int = 10,
    ) -> List[Dict]:
        """兼容旧 search_by_layer 接口，映射到新的 search

        旧 layer 名称映射:
        - working / shallow → daily
        - intermediate → monthly
        - deep → annual
        - all / daily / monthly / annual → 保持不变
        """
        type_map = {
            "all": "all",
            "working": "daily",
            "shallow": "daily",
            "intermediate": "monthly",
            "deep": "annual",
            "daily": "daily",
            "monthly": "monthly",
            "annual": "annual",
        }
        mapped_type = type_map.get(layer, "all")
        if self.store is None:
            return []
        return self.store.search(query, mapped_type, top_k)

    def get_recent(self, n: int = 20) -> List[Dict]:
        """兼容旧 get_recent 接口，返回最近 n 份日报"""
        if self.store is None:
            return []
        return self.store.list_reports("daily", limit=n)

    # ── 噪音/证伪透传（保持 B6.3 兼容） ──

    def get_noise_patterns(self) -> List[str]:
        """获取已知噪音模式（B6.3 透传到 L3Store）

        供 DenoiseStage Step 4 调用，查询 L3 中存储的噪音模式（标题党/营销号模板）。
        """
        try:
            from .l3_store import L3Store
            l3 = L3Store()
            return l3.get_noise_patterns()
        except Exception:
            return []

    def get_disproved_facts(self, symbol: Optional[str] = None) -> List[str]:
        """获取已证伪事实（B6.3 透传到 L3Store）

        供 DenoiseStage Step 5 调用，查询 L3 中存储的已证伪事实。
        """
        try:
            from .l3_store import L3Store
            l3 = L3Store()
            return l3.get_disproved_facts(symbol=symbol)
        except Exception:
            return []

    # ── 清理（测试用） ──

    def clear_all(self) -> None:
        """清空所有报告（用于测试隔离）"""
        if self.store is not None:
            self.store.clear_all()


# ─── 旧类名保留（向后兼容） ─────────────────────────────────────────

MemorySystem = ReportSystem  # 旧代码 from .system import MemorySystem 仍可用
