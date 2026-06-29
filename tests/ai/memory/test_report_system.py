# -*- coding: utf-8 -*-
"""F020 ReportSystem 测试 -- 日报/月报/年报报告体系

覆盖：
1. ReportSystem 初始化（内存后端）
2. search_by_layer 兼容映射（working→daily, shallow→daily, intermediate→monthly, deep→annual）
3. get_recent 兼容（映射到日报列表）
4. get_noise_patterns / get_disproved_facts 降级
5. search_by_layer 无效 layer 降级到 all
6. 日报/月报/年报 CRUD 流程
7. 旧类名 MemorySystem 兼容
"""
from __future__ import annotations

import os
from datetime import datetime

import pytest

# 强制内存模式（避免依赖 PostgreSQL）
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none"
)


# ========================================================================
# ReportSystem 初始化
# ========================================================================

class TestReportSystemInit:
    """ReportSystem 初始化测试"""

    def test_init_with_memory_backend(self):
        """初始化时使用内存后端（PostgreSQL 不可用）"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        assert rs.store is not None
        assert rs.store._backend == "memory"

    def test_init_with_generator(self):
        """初始化时 ReportGenerator 可用"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        assert rs.generator is not None

    def test_init_clear_all(self):
        """clear_all 清空存储"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        rs.clear_all()
        assert rs.store.count() == 0

    def test_legacy_memory_system_alias(self):
        """MemorySystem 是 ReportSystem 的别名"""
        from stockquant.ai.memory.system import ReportSystem, MemorySystem
        assert MemorySystem is ReportSystem


# ========================================================================
# search_by_layer 兼容映射
# ========================================================================

class TestSearchByLayerMapping:
    """search_by_layer 兼容映射测试

    映射规则：
    - working / shallow → daily
    - intermediate → monthly
    - deep → annual
    - all → all
    """

    @pytest.fixture(autouse=True)
    def _setup(self):
        """每个测试前清空并写入测试数据"""
        from stockquant.ai.memory.system import ReportSystem
        self.rs = ReportSystem(
            db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none"
        )
        self.rs.clear_all()

        # 写入各类型报告
        self.rs.store.write({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "今日市场上涨",
            "summary": "日报测试",
            "confidence": 0.8,
            "importance_score": 0.5,
        })
        self.rs.store.write({
            "report_type": "monthly",
            "report_date": "2026-06-30",
            "market_review": "本月市场震荡",
            "summary": "月报测试",
            "confidence": 0.8,
            "importance_score": 0.7,
        })
        self.rs.store.write({
            "report_type": "annual",
            "report_date": "2026-12-31",
            "market_review": "本年度市场总结",
            "summary": "年报测试",
            "confidence": 0.8,
            "importance_score": 0.9,
        })

    def test_layer_working_maps_to_daily(self):
        """layer='working' 映射到 daily 报告"""
        results = self.rs.search_by_layer("市场", layer="working")
        assert len(results) >= 1
        assert results[0]["report_type"] == "daily"

    def test_layer_shallow_maps_to_daily(self):
        """layer='shallow' 映射到 daily 报告"""
        results = self.rs.search_by_layer("市场", layer="shallow")
        assert len(results) >= 1
        assert results[0]["report_type"] == "daily"

    def test_layer_intermediate_maps_to_monthly(self):
        """layer='intermediate' 映射到 monthly 报告"""
        results = self.rs.search_by_layer("市场", layer="intermediate")
        assert len(results) >= 1
        assert results[0]["report_type"] == "monthly"

    def test_layer_deep_maps_to_annual(self):
        """layer='deep' 映射到 annual 报告"""
        results = self.rs.search_by_layer("市场", layer="deep")
        assert len(results) >= 1
        assert results[0]["report_type"] == "annual"

    def test_layer_all_returns_cross_type(self):
        """layer='all' 返回所有类型报告"""
        results = self.rs.search_by_layer("市场", layer="all")
        assert len(results) >= 1

    def test_layer_daily_maps_to_daily(self):
        """layer='daily' 直接映射到 daily"""
        results = self.rs.search_by_layer("日报", layer="daily")
        assert len(results) >= 1
        assert results[0]["report_type"] == "daily"

    def test_layer_monthly_maps_to_monthly(self):
        """layer='monthly' 直接映射到 monthly"""
        results = self.rs.search_by_layer("月报", layer="monthly")
        assert len(results) >= 1
        assert results[0]["report_type"] == "monthly"

    def test_layer_annual_maps_to_annual(self):
        """layer='annual' 直接映射到 annual"""
        results = self.rs.search_by_layer("年报", layer="annual")
        assert len(results) >= 1
        assert results[0]["report_type"] == "annual"

    def test_invalid_layer_falls_back_to_all(self):
        """无效 layer 降级到 all"""
        results = self.rs.search_by_layer("市场", layer="nonexistent_layer")
        # 不应报错，应返回结果（降级到 all）
        assert isinstance(results, list)


# ========================================================================
# get_recent 兼容
# ========================================================================

class TestGetRecentCompat:
    """get_recent 兼容测试"""

    def test_get_recent_returns_daily_reports(self):
        """get_recent 返回最近日报"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        rs.clear_all()

        # 写入日报
        for i in range(5):
            rs.store.write({
                "report_type": "daily",
                "report_date": f"2026-06-{25 + i:02d}",
                "market_review": f"日报 {i}",
                "summary": f"日报摘要 {i}",
            })

        results = rs.get_recent(3)
        assert len(results) == 3
        # 所有返回的应该是 daily 类型
        assert all(r["report_type"] == "daily" for r in results)

    def test_get_recent_empty(self):
        """无数据时 get_recent 返回空列表"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        rs.clear_all()
        assert rs.get_recent(10) == []

    def test_get_recent_limited(self):
        """get_recent 限制返回数量"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        rs.clear_all()

        for i in range(10):
            rs.store.write({
                "report_type": "daily",
                "report_date": f"2026-06-{20 + i:02d}",
                "market_review": f"日报 {i}",
                "summary": f"摘要 {i}",
            })

        results = rs.get_recent(3)
        assert len(results) == 3


# ========================================================================
# get_noise_patterns / get_disproved_facts 降级
# ========================================================================

class TestNoiseDisprovedFallback:
    """噪音模式库和已证伪事实的降级测试"""

    def test_get_noise_patterns_returns_list(self):
        """get_noise_patterns 始终返回列表，不抛异常"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        result = rs.get_noise_patterns()
        assert isinstance(result, list)

    def test_get_disproved_facts_returns_list(self):
        """get_disproved_facts 始终返回列表，不抛异常"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        result = rs.get_disproved_facts()
        assert isinstance(result, list)

    def test_get_disproved_facts_with_symbol(self):
        """带 symbol 参数不抛异常"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        result = rs.get_disproved_facts(symbol="sh600519")
        assert isinstance(result, list)


# ========================================================================
# ReportSystem CRUD
# ========================================================================

class TestReportSystemCrud:
    """ReportSystem 日报/月报/年报 CRUD 测试"""

    def test_write_and_get_daily(self):
        """写入并获取日报"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        rs.clear_all()

        report_id = rs.add_report({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "今日大盘上涨 2%",
            "summary": "上涨行情",
        })
        assert report_id is not None

        report = rs.get_daily_report("2026-06-29")
        assert report is not None
        assert report["report_type"] == "daily"
        assert report["summary"] == "上涨行情"

    def test_write_and_get_monthly(self):
        """写入并获取月报"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        rs.clear_all()

        rs.add_report({
            "report_type": "monthly",
            "report_date": "2026-06-30",
            "market_review": "本月市场震荡上行",
            "summary": "月度震荡",
        })

        report = rs.get_monthly_report("2026-06")
        assert report is not None
        assert report["report_type"] == "monthly"

    def test_write_and_get_annual(self):
        """写入并获取年报"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        rs.clear_all()

        rs.add_report({
            "report_type": "annual",
            "report_date": "2026-12-31",
            "market_review": "本年度市场总结",
            "summary": "年度总结",
        })

        report = rs.get_annual_report("2026")
        assert report is not None
        assert report["report_type"] == "annual"

    def test_list_daily_reports(self):
        """列出日报"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        rs.clear_all()

        for i in range(5):
            rs.add_report({
                "report_type": "daily",
                "report_date": f"2026-06-{25 + i:02d}",
                "market_review": f"日报 {i}",
                "summary": f"摘要 {i}",
            })

        reports = rs.list_daily_reports(limit=3)
        assert len(reports) == 3
        assert all(r["report_type"] == "daily" for r in reports)

    def test_list_monthly_reports(self):
        """列出月报"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        rs.clear_all()

        rs.add_report({
            "report_type": "monthly",
            "report_date": "2026-05-31",
            "market_review": "5月月报",
            "summary": "5月",
        })
        rs.add_report({
            "report_type": "monthly",
            "report_date": "2026-06-30",
            "market_review": "6月月报",
            "summary": "6月",
        })

        reports = rs.list_monthly_reports()
        assert len(reports) == 2

    def test_list_annual_reports(self):
        """列出年报"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        rs.clear_all()

        rs.add_report({
            "report_type": "annual",
            "report_date": "2026-12-31",
            "market_review": "2026年报",
            "summary": "2026",
        })

        reports = rs.list_annual_reports()
        assert len(reports) == 1

    def test_delete_report(self):
        """删除报告"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        rs.clear_all()

        report_id = rs.add_report({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "待删除",
            "summary": "待删除",
        })
        assert report_id is not None

        result = rs.delete_report(report_id)
        assert result is True

        # 删除后获取应返回 None
        report = rs.get_daily_report("2026-06-29")
        assert report is None

    def test_search_reports(self):
        """统一检索"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        rs.clear_all()

        rs.add_report({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "今日茅台涨停",
            "summary": "茅台涨停",
        })

        results = rs.search("茅台")
        assert len(results) >= 1

    def test_get_nonexistent_daily(self):
        """获取不存在的日报返回 None"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none")
        rs.clear_all()
        report = rs.get_daily_report("2099-01-01")
        assert report is None


# ========================================================================
# ReportSystem 生成（无 LLM 降级）
# ========================================================================

class TestReportSystemGeneration:
    """报告生成测试（无 LLM 降级）"""

    def test_generate_daily_without_llm(self):
        """无 LLM 时生成日报（降级文本）"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(
            db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none",
            llm_adapter=None,
        )
        rs.clear_all()

        report_id = rs.generate_daily_report("2026-06-29")
        assert report_id is not None

        report = rs.get_daily_report("2026-06-29")
        assert report is not None
        assert report["report_type"] == "daily"

    def test_generate_monthly_without_llm(self):
        """无 LLM 时生成月报（降级文本）"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(
            db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none",
            llm_adapter=None,
        )
        rs.clear_all()

        report_id = rs.generate_monthly_report("2026-06")
        assert report_id is not None

        report = rs.get_monthly_report("2026-06")
        assert report is not None
        assert report["report_type"] == "monthly"

    def test_generate_annual_without_llm(self):
        """无 LLM 时生成年报（降级文本）"""
        from stockquant.ai.memory.system import ReportSystem
        rs = ReportSystem(
            db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none",
            llm_adapter=None,
        )
        rs.clear_all()

        report_id = rs.generate_annual_report("2026")
        assert report_id is not None

        report = rs.get_annual_report("2026")
        assert report is not None
        assert report["report_type"] == "annual"
