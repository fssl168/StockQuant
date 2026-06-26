# -*- coding: utf-8 -*-
"""F020 Phase F1 测试 — asyncio 自动调度器 (PipelineScheduler)

注意：异步任务（asyncio.create_task）必须在同一事件循环中执行，
所以测试使用单一协程把 start → sleep → stop 全流程包起来。
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest

from stockquant.ai.scheduler import (
    PipelineScheduler,
    ScheduleSpec,
    get_scheduler,
    reset_scheduler,
)


# ── 辅助 ──────────────────────────────────────────────────────────────────


def run_async(coro, timeout=10.0):
    """同步执行异步协程"""
    return asyncio.new_event_loop().run_until_complete(
        asyncio.wait_for(coro, timeout=timeout)
    )


def _make_pipeline(result=None, exc=None, delay=0.0):
    """构造 mock pipeline 函数"""
    async def _pipeline(symbols: List[str]):
        if delay > 0:
            await asyncio.sleep(delay)
        if exc is not None:
            raise exc
        return result if result is not None else {
            "articles_processed": 5,
            "filtered_count": 2,
            "insights": [{"k": "v"}],
            "decision_context": None,
        }
    return _pipeline


# ── 1. ScheduleSpec 数据结构 ───────────────────────────────────────────────


class TestScheduleSpec:
    def test_default_values(self):
        s = ScheduleSpec(name="test")
        assert s.name == "test"
        assert s.level == "realtime"
        assert s.interval_seconds == 60
        assert s.daily_hour == 18
        assert s.daily_minute == 0
        assert s.symbols == []
        assert s.enabled is True
        assert s.last_run_at == ""
        assert s.last_result == ""
        assert s.run_count == 0
        assert s.error_count == 0

    def test_custom_init(self):
        s = ScheduleSpec(
            name="daily_news",
            level="daily",
            daily_hour=9,
            daily_minute=30,
            symbols=["sh600519"],
            enabled=False,
        )
        assert s.level == "daily"
        assert s.daily_hour == 9
        assert s.daily_minute == 30
        assert s.symbols == ["sh600519"]
        assert s.enabled is False


# ── 2. 任务管理 ──────────────────────────────────────────────────────────


class TestTaskManagement:
    def test_add_task(self):
        s = PipelineScheduler()
        spec = ScheduleSpec(name="t1")
        s.add_task(spec)
        assert s.get_task("t1") is spec
        assert len(s.list_tasks()) == 1

    def test_add_duplicate_overrides(self):
        s = PipelineScheduler()
        s.add_task(ScheduleSpec(name="t1", interval_seconds=10))
        s.add_task(ScheduleSpec(name="t1", interval_seconds=30))
        assert s.get_task("t1").interval_seconds == 30

    def test_remove_task(self):
        s = PipelineScheduler()
        s.add_task(ScheduleSpec(name="t1"))
        assert s.remove_task("t1") is True
        assert s.get_task("t1") is None
        assert s.remove_task("nonexistent") is False


# ── 3. 生命周期（在单一协程内执行）─────────────────────────────────────────


class TestLifecycle:
    def test_start_stop(self):
        async def _scenario():
            s = PipelineScheduler()
            s.bind_pipeline(_make_pipeline())
            s.add_task(ScheduleSpec(name="t1", interval_seconds=1))
            await s.start()
            assert s.is_running is True
            await s.stop()
            assert s.is_running is False

        run_async(_scenario())

    def test_start_twice_ignored(self):
        async def _scenario():
            s = PipelineScheduler()
            s.bind_pipeline(_make_pipeline())
            s.add_task(ScheduleSpec(name="t1", interval_seconds=1))
            await s.start()
            await s.start()  # 应被忽略
            assert s.is_running is True
            await s.stop()

        run_async(_scenario())

    def test_stop_when_not_running(self):
        s = PipelineScheduler()
        run_async(s.stop())
        assert s.is_running is False

    def test_disabled_task_not_started(self):
        async def _scenario():
            s = PipelineScheduler()
            s.bind_pipeline(_make_pipeline())
            s.add_task(ScheduleSpec(name="t1", enabled=False))
            await s.start()
            assert "t1" not in s._tasks
            await s.stop()

        run_async(_scenario())


# ── 4. 单任务执行 ──────────────────────────────────────────────────────────


class TestTaskExecution:
    def test_execute_success(self):
        async def _scenario():
            s = PipelineScheduler()
            s.bind_pipeline(_make_pipeline(result={"articles_processed": 5}))
            spec = ScheduleSpec(name="t1", interval_seconds=1, symbols=["sh600519"])
            s.add_task(spec)
            await s.start()
            await asyncio.sleep(1.3)
            await s.stop()
            return spec

        spec = run_async(_scenario(), timeout=5.0)
        assert spec.run_count >= 1
        assert spec.error_count == 0
        assert "articles_processed" in spec.last_result
        assert spec.last_run_at != ""

    def test_execute_with_exception(self):
        async def _scenario():
            s = PipelineScheduler()
            s.bind_pipeline(_make_pipeline(exc=RuntimeError("boom")))
            spec = ScheduleSpec(name="t1", interval_seconds=1)
            s.add_task(spec)
            await s.start()
            await asyncio.sleep(1.3)
            await s.stop()
            return spec

        spec = run_async(_scenario(), timeout=5.0)
        assert spec.error_count >= 1
        assert "boom" in spec.last_result
        assert spec.run_count == 0

    def test_no_pipeline_bound_skips(self):
        async def _scenario():
            s = PipelineScheduler()  # 不 bind_pipeline
            spec = ScheduleSpec(name="t1", interval_seconds=1)
            s.add_task(spec)
            await s.start()
            await asyncio.sleep(1.3)
            await s.stop()
            return spec

        spec = run_async(_scenario(), timeout=5.0)
        assert spec.run_count == 0
        assert spec.error_count == 0
        assert spec.last_result == ""


# ── 5. 异常隔离 ──────────────────────────────────────────────────────────


class TestExceptionIsolation:
    def test_one_failure_doesnt_affect_others(self):
        async def _pipeline(symbols):
            if "FAIL" in symbols:
                raise RuntimeError("designed to fail")
            return {"articles_processed": 1}

        async def _scenario():
            s = PipelineScheduler()
            s.bind_pipeline(_pipeline)
            s.add_task(ScheduleSpec(name="t1_fail", interval_seconds=1, symbols=["FAIL"]))
            s.add_task(ScheduleSpec(name="t2_ok", interval_seconds=1, symbols=["OK"]))
            await s.start()
            await asyncio.sleep(1.3)
            await s.stop()
            return s.get_task("t1_fail"), s.get_task("t2_ok")

        fail_spec, ok_spec = run_async(_scenario(), timeout=5.0)
        assert fail_spec.error_count >= 1
        assert ok_spec.run_count >= 1


# ── 6. 辅助方法 ──────────────────────────────────────────────────────────


class TestHelpers:
    def test_seconds_until_next_daily_future(self):
        """daily 时刻在今天未来"""
        now = datetime.now()
        target_hour = (now.hour + 1) % 24
        seconds = PipelineScheduler._seconds_until_next_daily(target_hour, 0)
        assert 0 < seconds <= 3600 + 60

    def test_seconds_until_next_daily_past_today(self):
        """daily 时刻在今天过去，应推到明天（24 小时左右）"""
        now = datetime.now()
        # 设为 1 小时前
        target_hour = (now.hour - 1) % 24
        seconds = PipelineScheduler._seconds_until_next_daily(target_hour, 0)
        # 应在 22-25 小时之间
        assert 22 * 3600 < seconds < 25 * 3600

    def test_summarize_result_none(self):
        assert PipelineScheduler._summarize_result(None) == "None"

    def test_summarize_result_dict(self):
        result = {
            "articles_processed": 10,
            "filtered_count": 3,
            "insights": [{"a": 1}],
            "decision_context": None,
        }
        summary = PipelineScheduler._summarize_result(result)
        assert "articles_processed" in summary
        assert "filtered_count" in summary
        assert "insights=1" in summary
        assert "decision_context=empty" in summary

    def test_summarize_result_string(self):
        result = "raw string result"
        summary = PipelineScheduler._summarize_result(result)
        assert summary == "raw string result"

    def test_summarize_result_long_dict(self):
        result = {"other_field": "value", "another": [1, 2, 3]}
        summary = PipelineScheduler._summarize_result(result)
        assert "other_field" in summary


# ── 7. 状态查询 ──────────────────────────────────────────────────────────


class TestStatus:
    def test_status_initial(self):
        s = PipelineScheduler()
        status = s.status()
        assert status["running"] is False
        assert status["task_count"] == 0
        assert status["active_tasks"] == 0
        assert status["tasks"] == []

    def test_status_with_tasks(self):
        s = PipelineScheduler()
        s.add_task(ScheduleSpec(name="t1", interval_seconds=10, symbols=["sh600519"]))
        status = s.status()
        assert status["task_count"] == 1
        assert status["tasks"][0]["name"] == "t1"
        assert status["tasks"][0]["level"] == "realtime"
        assert status["tasks"][0]["run_count"] == 0


# ── 8. 单例 ──────────────────────────────────────────────────────────────


class TestSingleton:
    def setup_method(self):
        reset_scheduler()

    def teardown_method(self):
        reset_scheduler()

    def test_get_scheduler_returns_same_instance(self):
        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2

    def test_reset_clears_singleton(self):
        s1 = get_scheduler()
        reset_scheduler()
        s2 = get_scheduler()
        assert s1 is not s2


# ── 9. 集成：完整调度循环 ──────────────────────────────────────────────────


class TestIntegration:
    def test_full_lifecycle_with_multiple_tasks(self):
        """完整流程：3 任务并行执行"""
        call_log = []

        async def _pipeline(symbols):
            call_log.append((symbols, datetime.now().isoformat()))
            return {"articles_processed": len(symbols)}

        async def _scenario():
            s = PipelineScheduler()
            s.bind_pipeline(_pipeline)
            s.add_task(ScheduleSpec(name="t1", interval_seconds=1, symbols=["sh600519"]))
            s.add_task(ScheduleSpec(name="t2", interval_seconds=1, symbols=["sz000858"]))
            s.add_task(ScheduleSpec(name="t3", interval_seconds=1, symbols=["sh600000"]))
            await s.start()
            await asyncio.sleep(1.5)
            await s.stop()
            return s

        s = run_async(_scenario(), timeout=5.0)
        assert len(call_log) >= 3
        for name in ("t1", "t2", "t3"):
            spec = s.get_task(name)
            assert spec.run_count >= 1
            assert "articles_processed" in spec.last_result

    def test_dynamic_add_remove_during_run(self):
        """运行时动态添加/移除任务"""
        async def _scenario():
            s = PipelineScheduler()
            s.bind_pipeline(_make_pipeline())
            await s.start()
            # 运行中添加（在事件循环内）
            s.add_task(ScheduleSpec(name="t1", interval_seconds=1))
            await asyncio.sleep(0.1)
            assert s.get_task("t1") is not None
            assert s.remove_task("t1") is True
            assert s.get_task("t1") is None
            await s.stop()

        run_async(_scenario(), timeout=5.0)

    def test_status_after_run(self):
        async def _scenario():
            s = PipelineScheduler()
            s.bind_pipeline(_make_pipeline())
            s.add_task(ScheduleSpec(name="t1", interval_seconds=1, symbols=["sh600519"]))
            await s.start()
            await asyncio.sleep(1.3)
            await s.stop()
            return s

        s = run_async(_scenario(), timeout=5.0)
        status = s.status()
        assert status["running"] is False
        assert status["task_count"] == 1
        assert status["tasks"][0]["run_count"] >= 1
