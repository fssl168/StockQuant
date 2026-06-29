# -*- coding: utf-8 -*-
"""F020 ReportStore 测试 -- 日报/月报/年报存储层

覆盖：
1. ReportStore 内存后端初始化
2. write + get_report 日报/月报/年报
3. list_reports 按类型筛选
4. search 关键词匹配（无 pgvector 降级）
5. delete
6. clear_all
7. count
8. get_dailies_for_period
9. UPSERT 逻辑（同一 report_type + report_date 覆盖）
"""
from __future__ import annotations

import os
from datetime import datetime

import pytest

# 强制内存模式（避免依赖 PostgreSQL）
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none"
)

_FAKE_DB_URL = "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none"


# ========================================================================
# 内存后端初始化
# ========================================================================

class TestReportStoreInit:
    """ReportStore 内存后端初始化测试"""

    def test_init_memory_backend(self):
        """PostgreSQL 不可用时降级为内存后端"""
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL)
        assert store._backend == "memory"
        assert store._entries == []

    def test_init_with_custom_user_id(self):
        """自定义 user_id"""
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL, user_id="custom_user")
        assert store._user_id == "custom_user"

    def test_init_empty_count(self):
        """初始化后 count 为 0"""
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL)
        store.clear_all()
        assert store.count() == 0


# ========================================================================
# write + get_report 日报/月报/年报
# ========================================================================

class TestWriteAndGetReport:
    """写入和获取报告测试"""

    def _make_store(self):
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL, user_id="test_user")
        store.clear_all()
        return store

    def test_write_daily_and_get(self):
        """写入日报并获取"""
        store = self._make_store()
        report_id = store.write({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "report_period_start": "2026-06-29",
            "report_period_end": "2026-06-29",
            "market_review": "今日大盘上涨",
            "trading_record": "买入茅台",
            "strategy_performance": "策略收益率 +2%",
            "ai_insights": "市场情绪偏多",
            "summary": "上涨行情",
            "confidence": 0.85,
            "importance_score": 0.6,
            "metrics_json": {"total_pnl": 1000},
            "metadata_json": {"source": "auto"},
        })

        assert report_id is not None
        assert "daily" in report_id

        report = store.get_report("daily", "2026-06-29")
        assert report is not None
        assert report["report_type"] == "daily"
        assert report["report_date"] == "2026-06-29"
        assert report["summary"] == "上涨行情"
        assert report["market_review"] == "今日大盘上涨"
        assert report["confidence"] == 0.85
        assert report["metrics"]["total_pnl"] == 1000

    def test_write_monthly_and_get(self):
        """写入月报并获取"""
        store = self._make_store()
        store.write({
            "report_type": "monthly",
            "report_date": "2026-06-30",
            "report_period_start": "2026-06-01",
            "report_period_end": "2026-06-30",
            "market_review": "本月震荡上行",
            "summary": "月度震荡",
        })

        report = store.get_report("monthly", "2026-06")
        assert report is not None
        assert report["report_type"] == "monthly"
        assert report["summary"] == "月度震荡"

    def test_write_annual_and_get(self):
        """写入年报并获取"""
        store = self._make_store()
        store.write({
            "report_type": "annual",
            "report_date": "2026-12-31",
            "report_period_start": "2026-01-01",
            "report_period_end": "2026-12-31",
            "market_review": "本年度总结",
            "summary": "年度总结",
        })

        report = store.get_report("annual", "2026")
        assert report is not None
        assert report["report_type"] == "annual"
        assert report["report_date"] == "2026-12-31"

    def test_get_nonexistent_report(self):
        """获取不存在的报告返回 None"""
        store = self._make_store()
        report = store.get_report("daily", "2099-01-01")
        assert report is None

    def test_get_nonexistent_type(self):
        """获取不支持的报告类型返回 None"""
        store = self._make_store()
        report = store.get_report("invalid_type", "2026-06-29")
        assert report is None

    def test_write_auto_generates_id(self):
        """写入时自动生成 report_id"""
        store = self._make_store()
        report_id = store.write({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "测试",
            "summary": "测试",
        })
        assert report_id is not None
        assert isinstance(report_id, str)
        assert len(report_id) > 0


# ========================================================================
# list_reports 按类型筛选
# ========================================================================

class TestListReports:
    """列出报告并按类型筛选"""

    def _make_store_with_data(self):
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL, user_id="test_user")
        store.clear_all()

        # 写入多种类型的报告
        for i in range(5):
            store.write({
                "report_type": "daily",
                "report_date": f"2026-06-{25 + i:02d}",
                "market_review": f"日报 {i}",
                "summary": f"日报摘要 {i}",
            })

        for m in ["2026-05-31", "2026-06-30"]:
            store.write({
                "report_type": "monthly",
                "report_date": m,
                "market_review": f"月报 {m}",
                "summary": f"月报摘要 {m}",
            })

        store.write({
            "report_type": "annual",
            "report_date": "2026-12-31",
            "market_review": "年报 2026",
            "summary": "年度总结",
        })

        return store

    def test_list_daily_reports(self):
        """列出日报"""
        store = self._make_store_with_data()
        reports = store.list_reports("daily")
        assert len(reports) == 5
        assert all(r["report_type"] == "daily" for r in reports)

    def test_list_monthly_reports(self):
        """列出月报"""
        store = self._make_store_with_data()
        reports = store.list_reports("monthly")
        assert len(reports) == 2
        assert all(r["report_type"] == "monthly" for r in reports)

    def test_list_annual_reports(self):
        """列出年报"""
        store = self._make_store_with_data()
        reports = store.list_reports("annual")
        assert len(reports) == 1
        assert reports[0]["report_type"] == "annual"

    def test_list_reports_with_limit(self):
        """limit 限制返回数量"""
        store = self._make_store_with_data()
        reports = store.list_reports("daily", limit=2)
        assert len(reports) == 2

    def test_list_reports_with_offset(self):
        """offset 偏移"""
        store = self._make_store_with_data()
        reports = store.list_reports("daily", limit=10, offset=3)
        assert len(reports) == 2

    def test_list_reports_order_by_date_desc(self):
        """按日期倒序排列"""
        store = self._make_store_with_data()
        reports = store.list_reports("daily")
        dates = [r["report_date"] for r in reports]
        assert dates == sorted(dates, reverse=True)

    def test_list_reports_with_date_range(self):
        """按日期范围筛选"""
        store = self._make_store_with_data()
        reports = store.list_reports("daily", start="2026-06-27", end="2026-06-28")
        assert len(reports) == 2

    def test_list_reports_empty_type(self):
        """列出不存在的类型返回空列表"""
        store = self._make_store_with_data()
        reports = store.list_reports("nonexistent")
        assert reports == []


# ========================================================================
# search 关键词匹配（无 pgvector 降级）
# ========================================================================

class TestSearch:
    """搜索报告测试（无 pgvector 降级到关键词匹配）"""

    def _make_store_with_data(self):
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL, user_id="test_user")
        store.clear_all()

        store.write({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "贵州茅台今日涨停，成交额放大",
            "summary": "茅台涨停",
        })
        store.write({
            "report_type": "daily",
            "report_date": "2026-06-28",
            "market_review": "五粮液震荡整理",
            "summary": "五粮液整理",
        })
        store.write({
            "report_type": "monthly",
            "report_date": "2026-06-30",
            "market_review": "本月白酒板块表现强势",
            "summary": "白酒强势",
        })

        return store

    def test_search_by_keyword(self):
        """关键词搜索"""
        store = self._make_store_with_data()
        results = store.search("茅台", report_type="all")
        assert len(results) >= 1
        assert any("茅台" in r.get("summary", "") or "茅台" in r.get("market_review", "") for r in results)

    def test_search_by_type(self):
        """按类型搜索"""
        store = self._make_store_with_data()
        results = store.search("涨停", report_type="daily")
        assert len(results) >= 1
        assert all(r["report_type"] == "daily" for r in results)

    def test_search_no_match(self):
        """搜索无匹配"""
        store = self._make_store_with_data()
        results = store.search("不存在的关键词_xyz")
        assert results == []

    def test_search_empty_query(self):
        """空查询"""
        store = self._make_store_with_data()
        results = store.search("")
        # 空查询可能返回全部或空，不抛异常即可
        assert isinstance(results, list)

    def test_search_top_k(self):
        """top_k 限制返回数量"""
        store = self._make_store_with_data()
        results = store.search("白酒", top_k=1)
        assert len(results) <= 1

    def test_search_all_types(self):
        """跨类型搜索"""
        store = self._make_store_with_data()
        results = store.search("白酒", report_type="all")
        assert isinstance(results, list)


# ========================================================================
# delete
# ========================================================================

class TestDelete:
    """删除报告测试"""

    def _make_store_with_data(self):
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL, user_id="test_user")
        store.clear_all()
        self._report_id = store.write({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "待删除报告",
            "summary": "待删除",
        })
        return store

    def test_delete_existing_report(self):
        """删除已存在的报告"""
        store = self._make_store_with_data()
        result = store.delete(self._report_id)
        assert result is True

        report = store.get_report("daily", "2026-06-29")
        assert report is None

    def test_delete_nonexistent_report(self):
        """删除不存在的报告返回 False"""
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL, user_id="test_user")
        store.clear_all()

        result = store.delete("nonexistent_id")
        assert result is False

    def test_delete_one_preserves_others(self):
        """删除一份不影响其他报告"""
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL, user_id="test_user")
        store.clear_all()

        id1 = store.write({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "报告1",
            "summary": "1",
        })
        store.write({
            "report_type": "daily",
            "report_date": "2026-06-28",
            "market_review": "报告2",
            "summary": "2",
        })

        store.delete(id1)
        assert store.count("daily") == 1


# ========================================================================
# clear_all
# ========================================================================

class TestClearAll:
    """清空所有报告测试"""

    def test_clear_all_removes_everything(self):
        """clear_all 清空所有报告"""
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL, user_id="test_user")
        store.clear_all()

        store.write({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "日报",
            "summary": "日报",
        })
        store.write({
            "report_type": "monthly",
            "report_date": "2026-06-30",
            "market_review": "月报",
            "summary": "月报",
        })

        removed = store.clear_all()
        assert removed >= 2
        assert store.count() == 0
        assert store.count("daily") == 0
        assert store.count("monthly") == 0

    def test_clear_all_empty_store(self):
        """空存储清空返回 0"""
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL, user_id="test_user")
        store.clear_all()

        removed = store.clear_all()
        assert removed == 0


# ========================================================================
# count
# ========================================================================

class TestCount:
    """统计报告数量测试"""

    def _make_store_with_data(self):
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL, user_id="test_user")
        store.clear_all()

        for i in range(5):
            store.write({
                "report_type": "daily",
                "report_date": f"2026-06-{25 + i:02d}",
                "market_review": f"日报 {i}",
                "summary": f"日报 {i}",
            })
        for i in range(3):
            store.write({
                "report_type": "monthly",
                "report_date": f"2026-{3 + i:02d}-30",
                "market_review": f"月报 {i}",
                "summary": f"月报 {i}",
            })
        store.write({
            "report_type": "annual",
            "report_date": "2026-12-31",
            "market_review": "年报",
            "summary": "年报",
        })
        return store

    def test_count_all(self):
        """统计所有报告"""
        store = self._make_store_with_data()
        assert store.count() == 9

    def test_count_daily(self):
        """统计日报数量"""
        store = self._make_store_with_data()
        assert store.count("daily") == 5

    def test_count_monthly(self):
        """统计月报数量"""
        store = self._make_store_with_data()
        assert store.count("monthly") == 3

    def test_count_annual(self):
        """统计年报数量"""
        store = self._make_store_with_data()
        assert store.count("annual") == 1

    def test_count_nonexistent_type(self):
        """统计不存在的类型返回 0"""
        store = self._make_store_with_data()
        assert store.count("nonexistent") == 0

    def test_count_empty(self):
        """空存储统计返回 0"""
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL, user_id="test_user")
        store.clear_all()
        assert store.count() == 0


# ========================================================================
# get_dailies_for_period
# ========================================================================

class TestGetDailiesForPeriod:
    """获取指定日期范围内日报测试"""

    def _make_store_with_data(self):
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL, user_id="test_user")
        store.clear_all()

        for day in range(1, 11):
            store.write({
                "report_type": "daily",
                "report_date": f"2026-06-{day:02d}",
                "market_review": f"6月{day}日",
                "summary": f"日报 {day}",
            })
        return store

    def test_get_dailies_for_full_period(self):
        """获取完整月份的日报"""
        store = self._make_store_with_data()
        dailies = store.get_dailies_for_period("2026-06-01", "2026-06-10")
        assert len(dailies) == 10
        assert all(d["report_type"] == "daily" for d in dailies)

    def test_get_dailies_for_partial_period(self):
        """获取部分日期范围的日报"""
        store = self._make_store_with_data()
        dailies = store.get_dailies_for_period("2026-06-03", "2026-06-07")
        assert len(dailies) == 5

    def test_get_dailies_for_empty_period(self):
        """获取空日期范围返回空列表"""
        store = self._make_store_with_data()
        dailies = store.get_dailies_for_period("2026-07-01", "2026-07-10")
        assert dailies == []

    def test_get_dailies_excludes_other_types(self):
        """只返回 daily 类型"""
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL, user_id="test_user")
        store.clear_all()

        store.write({
            "report_type": "daily",
            "report_date": "2026-06-15",
            "market_review": "日报",
            "summary": "日报",
        })
        store.write({
            "report_type": "monthly",
            "report_date": "2026-06-15",
            "market_review": "月报",
            "summary": "月报",
        })

        dailies = store.get_dailies_for_period("2026-06-15", "2026-06-15")
        assert len(dailies) == 1
        assert dailies[0]["report_type"] == "daily"


# ========================================================================
# UPSERT 逻辑（同一 report_type + report_date 覆盖）
# ========================================================================

class TestUpsert:
    """UPSERT 逻辑测试（同一 report_type + report_date 覆盖）"""

    def _make_store(self):
        from stockquant.ai.memory.report_store import ReportStore
        store = ReportStore(db_url=_FAKE_DB_URL, user_id="test_user")
        store.clear_all()
        return store

    def test_upsert_daily_same_date(self):
        """同一 report_type + report_date 覆盖日报"""
        store = self._make_store()

        id1 = store.write({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "第一次写入",
            "summary": "初始版本",
            "confidence": 0.8,
        })

        id2 = store.write({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "更新后的内容",
            "summary": "更新版本",
            "confidence": 0.9,
        })

        # 应该只有一份报告
        assert store.count("daily") == 1

        # 内容应是更新后的
        report = store.get_report("daily", "2026-06-29")
        assert report["market_review"] == "更新后的内容"
        assert report["summary"] == "更新版本"
        assert report["confidence"] == 0.9

        # ID 应保持不变（UPSERT）
        assert id1 == id2

    def test_upsert_monthly_same_date(self):
        """同一 report_type + report_date 覆盖月报"""
        store = self._make_store()

        id1 = store.write({
            "report_type": "monthly",
            "report_date": "2026-06-30",
            "market_review": "第一次月报",
            "summary": "初始月报",
        })

        id2 = store.write({
            "report_type": "monthly",
            "report_date": "2026-06-30",
            "market_review": "更新后的月报",
            "summary": "更新月报",
        })

        assert store.count("monthly") == 1
        assert id1 == id2

        report = store.get_report("monthly", "2026-06")
        assert report["market_review"] == "更新后的月报"

    def test_upsert_annual_same_date(self):
        """同一 report_type + report_date 覆盖年报"""
        store = self._make_store()

        id1 = store.write({
            "report_type": "annual",
            "report_date": "2026-12-31",
            "market_review": "第一次年报",
            "summary": "初始年报",
        })

        id2 = store.write({
            "report_type": "annual",
            "report_date": "2026-12-31",
            "market_review": "更新后的年报",
            "summary": "更新年报",
        })

        assert store.count("annual") == 1
        assert id1 == id2

    def test_different_dates_no_upsert(self):
        """不同日期的报告不互相覆盖"""
        store = self._make_store()

        store.write({
            "report_type": "daily",
            "report_date": "2026-06-28",
            "market_review": "6月28日",
            "summary": "28日",
        })
        store.write({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "6月29日",
            "summary": "29日",
        })

        assert store.count("daily") == 2

    def test_different_types_same_date_no_upsert(self):
        """同日期不同类型不互相覆盖"""
        store = self._make_store()

        store.write({
            "report_type": "daily",
            "report_date": "2026-06-30",
            "market_review": "日报",
            "summary": "日报",
        })
        store.write({
            "report_type": "monthly",
            "report_date": "2026-06-30",
            "market_review": "月报",
            "summary": "月报",
        })

        assert store.count("daily") == 1
        assert store.count("monthly") == 1

        daily = store.get_report("daily", "2026-06-30")
        assert daily["summary"] == "日报"

        monthly = store.get_report("monthly", "2026-06")
        assert monthly["summary"] == "月报"

    def test_upsert_preserves_created_at(self):
        """UPSERT 更新时保留原始 created_at"""
        store = self._make_store()

        store.write({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "初始",
            "summary": "初始",
        })

        report1 = store.get_report("daily", "2026-06-29")
        original_created_at = report1["created_at"]

        store.write({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "更新",
            "summary": "更新",
        })

        report2 = store.get_report("daily", "2026-06-29")
        assert report2["created_at"] == original_created_at

    def test_upsert_updates_last_accessed_at(self):
        """UPSERT 更新时刷新 last_accessed_at"""
        store = self._make_store()

        store.write({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "初始",
            "summary": "初始",
        })

        report1 = store.get_report("daily", "2026-06-29")

        store.write({
            "report_type": "daily",
            "report_date": "2026-06-29",
            "market_review": "更新",
            "summary": "更新",
        })

        report2 = store.get_report("daily", "2026-06-29")
        # last_accessed_at 应被刷新
        assert report2["last_accessed_at"] is not None
