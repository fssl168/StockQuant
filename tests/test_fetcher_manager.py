# -*- coding: utf-8 -*-
"""F011 DataFetcherManager 测试"""

from unittest import mock

import pytest

import pandas as pd

from stockquant.data.fetcher_manager import DataFetcherManager, FetcherStatus


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_mock_feed(name="test_feed", healthy=True, data=None):
    """创建一个模拟 DataFeed"""
    if data is None:
        data = pd.DataFrame({
            "open": [10.0],
            "high": [11.0],
            "low": [9.0],
            "close": [10.5],
            "volume": [1000],
        })
    feed = mock.MagicMock()
    feed.symbol = name
    feed.get_dataframe.return_value = data
    feed.is_healthy = healthy
    return feed


def _make_empty_feed(name="empty_feed"):
    """创建一个返回空 DataFrame 的模拟 DataFeed"""
    return _make_mock_feed(name, data=pd.DataFrame())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRegisterAndFetch:
    def test_register_and_fetch(self):
        """注册数据源后 fetch 正常工作"""
        mgr = DataFetcherManager()
        feed = _make_mock_feed("primary")
        mgr.register_fetcher(feed, priority=1)

        df = mgr.fetch("sh600519", "1d", "2024-01-01", "2024-12-31")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "close" in df.columns
        feed.get_dataframe.assert_called_once()

    def test_register_multiple(self):
        """注册多个数据源"""
        mgr = DataFetcherManager()
        f1 = _make_mock_feed("feed1")
        f2 = _make_mock_feed("feed2")
        mgr.register_fetcher(f1, priority=1)
        mgr.register_fetcher(f2, priority=2)

        assert len(mgr._fetchers) == 2
        assert "feed1" in mgr._fetchers
        assert "feed2" in mgr._fetchers


class TestFailoverOnError:
    def test_failover_on_error(self):
        """主数据源失败时自动切换到备用"""
        mgr = DataFetcherManager(failover_threshold=1)
        primary = _make_mock_feed("primary")
        secondary = _make_mock_feed("secondary")
        mgr.register_fetcher(primary, priority=1)
        mgr.register_fetcher(secondary, priority=0)

        # 让主数据源抛异常
        primary.get_dataframe.side_effect = Exception("API timeout")

        df = mgr.fetch("sh600519", "1d", "2024-01-01", "2024-12-31")
        assert isinstance(df, pd.DataFrame)
        # 主数据源已被标记为不健康，第二次调用时应使用备用
        assert secondary.get_dataframe.called

    def test_empty_result_triggers_failover(self):
        """主数据源返回空数据时切换到备用"""
        mgr = DataFetcherManager(failover_threshold=1)
        primary = _make_empty_feed("primary")
        secondary = _make_mock_feed("secondary")
        mgr.register_fetcher(primary, priority=1)
        mgr.register_fetcher(secondary, priority=0)

        df = mgr.fetch("sh600519", "1d", "2024-01-01", "2024-12-31")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1


class TestMarkUnhealthyThenHealthy:
    def test_mark_unhealthy(self):
        """标记为不健康"""
        mgr = DataFetcherManager(failover_threshold=1)
        feed = _make_mock_feed("test")
        mgr.register_fetcher(feed, priority=1)

        mgr.mark_unhealthy("test", error="connection refused")
        status = mgr._statuses["test"]
        assert not status.is_healthy
        assert status.last_error == "connection refused"
        assert status.failure_count >= 1

    def test_mark_healthy_restores(self):
        """标记为健康后恢复"""
        mgr = DataFetcherManager(failover_threshold=1)
        feed = _make_mock_feed("test")
        mgr.register_fetcher(feed, priority=1)

        mgr.mark_unhealthy("test", error="timeout")
        assert not mgr._statuses["test"].is_healthy

        mgr.mark_healthy("test")
        assert mgr._statuses["test"].is_healthy
        assert mgr._statuses["test"].failure_count == 0

    def test_threshold_based_unhealthy(self):
        """连续失败达到阈值后自动标记不健康"""
        mgr = DataFetcherManager(failover_threshold=3)
        feed = _make_mock_feed("test")
        mgr.register_fetcher(feed, priority=1)

        mgr.mark_unhealthy("test", error="err1")
        assert mgr._statuses["test"].is_healthy
        mgr.mark_unhealthy("test", error="err2")
        assert mgr._statuses["test"].is_healthy
        mgr.mark_unhealthy("test", error="err3")
        assert not mgr._statuses["test"].is_healthy


class TestGetHealthyFetchers:
    def test_returns_only_healthy(self):
        """只返回健康的数据源"""
        mgr = DataFetcherManager(failover_threshold=1)
        f1 = _make_mock_feed("healthy1")
        f2 = _make_mock_feed("healthy2")
        f3 = _make_mock_feed("unhealthy")
        mgr.register_fetcher(f1, priority=1)
        mgr.register_fetcher(f2, priority=2)
        mgr.register_fetcher(f3, priority=3)

        mgr.mark_unhealthy("unhealthy")

        healthy = mgr.get_healthy_fetchers()
        names = [f.symbol for f in healthy]
        assert "unhealthy" not in names
        assert "healthy1" in names
        assert "healthy2" in names

    def test_priority_ordering(self):
        """按优先级降序返回"""
        mgr = DataFetcherManager()
        f_low = _make_mock_feed("low_pri")
        f_high = _make_mock_feed("high_pri")
        mgr.register_fetcher(f_low, priority=1)
        mgr.register_fetcher(f_high, priority=10)

        healthy = mgr.get_healthy_fetchers()
        assert healthy[0].symbol == "high_pri"
        assert healthy[1].symbol == "low_pri"


class TestStatusProperty:
    def test_status_dict(self):
        """status 返回状态字典"""
        mgr = DataFetcherManager()
        feed = _make_mock_feed("test")
        mgr.register_fetcher(feed, priority=5)

        status = mgr.status
        assert "test" in status
        assert status["test"]["name"] == "test"
        assert status["test"]["is_healthy"] is True
        assert status["test"]["priority"] == 5
        assert status["test"]["failure_count"] == 0


class TestReset:
    def test_resets_all_to_healthy(self):
        """重置所有数据源为健康"""
        mgr = DataFetcherManager(failover_threshold=1)
        f1 = _make_mock_feed("feed1")
        f2 = _make_mock_feed("feed2")
        mgr.register_fetcher(f1, priority=1)
        mgr.register_fetcher(f2, priority=2)

        mgr.mark_unhealthy("feed1", error="e1")
        mgr.mark_unhealthy("feed2", error="e2")
        assert not mgr._statuses["feed1"].is_healthy
        assert not mgr._statuses["feed2"].is_healthy

        mgr.reset()
        assert mgr._statuses["feed1"].is_healthy
        assert mgr._statuses["feed2"].is_healthy
        assert mgr._statuses["feed1"].failure_count == 0
        assert mgr._statuses["feed2"].failure_count == 0


class TestEmptyNoFetchers:
    def test_raises_value_error(self):
        """没有注册数据源时抛出 ValueError"""
        mgr = DataFetcherManager()
        with pytest.raises(ValueError, match="No healthy fetchers"):
            mgr.fetch("sh600519", "1d", "2024-01-01", "2024-12-31")

    def test_all_fail_raises_value_error(self):
        """所有数据源都失败时抛出 ValueError"""
        mgr = DataFetcherManager(failover_threshold=1)
        f1 = _make_mock_feed("feed1")
        f2 = _make_mock_feed("feed2")
        f1.get_dataframe.side_effect = Exception("broken")
        f2.get_dataframe.side_effect = Exception("also broken")
        mgr.register_fetcher(f1, priority=1)
        mgr.register_fetcher(f2, priority=0)

        with pytest.raises(ValueError, match="All fetchers failed"):
            mgr.fetch("sh600519", "1d", "2024-01-01", "2024-12-31")


class TestPriorityOrdering:
    def test_higher_priority_tried_first(self):
        """更高优先级的数据源先被尝试"""
        mgr = DataFetcherManager()
        f_low = _make_mock_feed("low_priority")
        f_mid = _make_mock_feed("mid_priority")
        f_high = _make_mock_feed("high_priority")
        mgr.register_fetcher(f_low, priority=1)
        mgr.register_fetcher(f_mid, priority=5)
        mgr.register_fetcher(f_high, priority=10)

        # 所有数据源都正常时，最高优先级的最先被调用
        df = mgr.fetch("sh600519")
        assert f_high.get_dataframe.called
        # 因为高优先级先被调用且成功返回，不会调用其他
        assert f_mid.get_dataframe.call_count == 0
        assert f_low.get_dataframe.call_count == 0

    def test_failover_preserves_order(self):
        """故障切换时按优先级顺序尝试"""
        mgr = DataFetcherManager(failover_threshold=1)
        f_a = _make_mock_feed("priority_a")
        f_b = _make_mock_feed("priority_b")
        f_c = _make_mock_feed("priority_c")
        mgr.register_fetcher(f_a, priority=3)
        mgr.register_fetcher(f_b, priority=2)
        mgr.register_fetcher(f_c, priority=1)

        f_a.get_dataframe.side_effect = Exception("failed")
        f_b.get_dataframe.side_effect = Exception("failed")

        df = mgr.fetch("sh600519")
        assert df is not None
        # c 最终被调用
        assert f_c.get_dataframe.called
