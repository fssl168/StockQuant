# -*- coding: utf-8 -*-
"""Tests for stockquant.persistence (models + repository)"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import inspect

from stockquant.persistence.models import (
    AnalysisHistory,
    BacktestResult,
    Base,
    KlineData,
    drop_db,
    get_engine,
    init_db,
)
from stockquant.persistence.repository import (
    delete_backtest,
    get_backtest,
    get_kline,
    list_backtests,
    list_analyses,
    save_analysis,
    save_backtest,
    save_kline,
    # New task store functions
    save_backtest_task,
    get_backtest_task,
    list_backtest_tasks,
    delete_backtest_task,
    save_collect_task,
    get_collect_task,
    list_collect_tasks,
    delete_collect_task,
    save_optimize_task,
    get_optimize_task,
    list_optimize_tasks,
    delete_optimize_task,
    save_comparison_history,
    get_comparison_history,
    list_comparison_history,
    delete_comparison_history,
    save_pending_order,
    get_pending_order,
    list_pending_orders,
    delete_pending_order,
    save_order_audit,
    get_order_audit,
    list_order_audits,
    delete_order_audit,
)

ENGINE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def _reset_db():
    """Each test gets a fresh in-memory database."""
    drop_db(ENGINE_URL)
    init_db(ENGINE_URL)
    yield
    # No cleanup needed for in-memory sqlite


# ── test_init_db_creates_tables ──────────────────────────────────────────


class TestInitDbCreatesTables:
    def test_init_db_creates_all_tables(self):
        """init_db creates every table defined in Base.metadata."""
        engine = init_db(ENGINE_URL)
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        assert "backtest_results" in table_names
        assert "kline_data" in table_names
        assert "analysis_history" in table_names
        assert "chat_messages" in table_names


# ── test_save_and_get_backtest ───────────────────────────────────────────


class TestSaveAndGetBacktest:
    def test_save_and_get_backtest(self):
        """Save a backtest result, then retrieve by ID."""
        metrics = {"sharpe": 1.2, "max_drawdown": -0.08}
        equity_curve = [(0, 1_000_000.0), (1, 1_050_000.0)]
        trades = [{"symbol": "600519", "pnl": 5000}]

        result_id = save_backtest(
            engine_url=ENGINE_URL,
            strategy_name="ma_cross",
            symbol="600519.SH",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_cash=1_000_000.0,
            final_equity=1_100_000.0,
            metrics=metrics,
            equity_curve=equity_curve,
            trades_summary=trades,
        )
        assert isinstance(result_id, int) and result_id >= 1

        retrieved = get_backtest(ENGINE_URL, result_id=result_id)
        assert retrieved is not None
        assert retrieved["strategy_name"] == "ma_cross"
        assert retrieved["symbol"] == "600519.SH"
        assert retrieved["initial_cash"] == 1_000_000.0
        assert retrieved["final_equity"] == 1_100_000.0
        assert retrieved["metrics"] == metrics
        assert retrieved["equity_curve"] == [list(t) for t in equity_curve]
        assert retrieved["trades_summary"] == trades


# ── test_list_backtests ──────────────────────────────────────────────────


class TestListBacktests:
    def test_list_backtests(self):
        """Insert multiple backtests and verify listing with limit/offset."""
        ids = []
        for i in range(5):
            rid = save_backtest(
                engine_url=ENGINE_URL,
                strategy_name=f"strategy_{i}",
                symbol="000001.SZ",
                start_date="2024-01-01",
                end_date="2024-06-30",
                initial_cash=500_000.0,
                final_equity=550_000.0 + i * 10_000.0,
                metrics={},
                equity_curve=[],
                trades_summary=[],
            )
            ids.append(rid)

        all_results = list_backtests(ENGINE_URL, limit=50, offset=0)
        assert len(all_results) == 5

        # Verify ordering: most recent first
        assert all_results[0]["strategy_name"] == "strategy_4"
        assert all_results[4]["strategy_name"] == "strategy_0"

        # Test limit
        limited = list_backtests(ENGINE_URL, limit=2, offset=0)
        assert len(limited) == 2

        # Test offset
        offset_list = list_backtests(ENGINE_URL, limit=50, offset=3)
        assert len(offset_list) == 2
        assert offset_list[0]["strategy_name"] == "strategy_1"


# ── test_delete_backtest ─────────────────────────────────────────────────


class TestDeleteBacktest:
    def test_delete_backtest_returns_true(self):
        """Deleting an existing record returns True; deleting non-existing returns False."""
        rid = save_backtest(
            engine_url=ENGINE_URL,
            user_id="test_user",
            strategy_name="test_strat",
            symbol="000001.SZ",
            start_date="2024-01-01",
            end_date="2024-06-30",
            initial_cash=100_000.0,
            final_equity=110_000.0,
            metrics={},
            equity_curve=[],
            trades_summary=[],
        )
        assert delete_backtest(ENGINE_URL, user_id="test_user", result_id=rid) is True
        assert delete_backtest(ENGINE_URL, user_id="test_user", result_id=rid) is False  # already deleted

    def test_delete_nonexistent(self):
        assert delete_backtest(ENGINE_URL, 99999) is False


# ── test_save_and_get_kline ──────────────────────────────────────────────


class TestSaveAndGetKline:
    def test_save_and_get_kline(self):
        """Bulk save K-line bars, retrieve and filter by date range."""
        bars = [
            {
                "datetime": "2024-01-02T00:00:00",
                "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.3,
                "volume": 100000, "amount": 1030000.0,
            },
            {
                "datetime": "2024-01-03T00:00:00",
                "open": 10.3, "high": 10.8, "low": 10.1, "close": 10.6,
                "volume": 120000, "amount": 1272000.0,
            },
            {
                "datetime": "2024-01-04T00:00:00",
                "open": 10.6, "high": 11.0, "low": 10.4, "close": 10.9,
                "volume": 150000, "amount": 1635000.0,
            },
        ]

        inserted = save_kline(ENGINE_URL, "000001.SZ", "1d", bars)
        assert inserted == 3

        all_kline = get_kline(ENGINE_URL, "000001.SZ", "1d")
        assert len(all_kline) == 3
        assert all_kline[0]["close"] == 10.3
        assert all_kline[0]["volume"] == 100000

        # Filter by date range
        filtered = get_kline(
            ENGINE_URL, "000001.SZ", "1d",
            start="2024-01-03T00:00:00",
            end="2024-01-03T23:59:59",
        )
        assert len(filtered) == 1
        assert filtered[0]["close"] == 10.6

        # Wrong symbol → empty
        assert get_kline(ENGINE_URL, "600519.SH", "1d") == []

        # Wrong timeframe → empty
        assert get_kline(ENGINE_URL, "000001.SZ", "5m") == []


# ── test_save_analysis ───────────────────────────────────────────────────


class TestSaveAnalysis:
    def test_save_and_list_analysis(self):
        """Save analysis results and list them back."""
        aid1 = save_analysis(
            engine_url=ENGINE_URL,
            symbol="000001.SZ",
            analysis_type="backtest_interpretation",
            input_data={"strategy": "ma_cross", "period": "2024-01"},
            output_data={"signal": "buy", "confidence": 0.85},
        )
        aid2 = save_analysis(
            engine_url=ENGINE_URL,
            symbol="600519.SH",
            analysis_type="risk_assessment",
            input_data={"portfolio_value": 2_000_000},
            output_data={"risk_level": "medium", "max_drawdown": -0.05},
        )

        assert aid1 >= 1
        assert aid2 >= 1

        all_analyses = list_analyses(ENGINE_URL, limit=50)
        assert len(all_analyses) == 2
        # Most recent first (by id, since created_at may be identical within the same second)
        assert all_analyses[0]["id"] > all_analyses[1]["id"]

        # Filter by symbol
        filtered = list_analyses(ENGINE_URL, symbol="000001.SZ", limit=50)
        assert len(filtered) == 1
        assert filtered[0]["analysis_type"] == "backtest_interpretation"
        assert filtered[0]["input_data"]["strategy"] == "ma_cross"


# ── test_none_result_for_missing ─────────────────────────────────────────


class TestNoneResultForMissing:
    def test_get_backtest_missing_id(self):
        """get_backtest(id=999) returns None for non-existing record."""
        assert get_backtest(ENGINE_URL, result_id=999) is None

    def test_get_kline_missing_symbol(self):
        """get_kline for a symbol that doesn't exist returns empty list."""
        assert get_kline(ENGINE_URL, "NONEXISTENT.SZ") == []

    def test_delete_nonexistent_id(self):
        """delete_backtest(id=999) returns False for non-existing record."""
        assert delete_backtest(ENGINE_URL, 999) is False


# ── TestBacktestTaskCrud ──────────────────────────────────────────────────


class TestBacktestTaskCrud:
    def test_save_and_get_backtest_task(self):
        save_backtest_task(ENGINE_URL, user_id="u1", task_id="bt1", status="running", result=json.dumps({"pnl": 100}))
        task = get_backtest_task(ENGINE_URL, user_id="u1", task_id="bt1")
        assert task is not None
        assert task["status"] == "running"

    def test_list_backtest_tasks(self):
        for i in range(3):
            save_backtest_task(ENGINE_URL, user_id="u2", task_id=f"bt_u2_{i}", status="completed")
        tasks = list_backtest_tasks(ENGINE_URL, user_id="u2")
        assert len(tasks) == 3

    def test_delete_backtest_task(self):
        save_backtest_task(ENGINE_URL, user_id="u3", task_id="bt_del", status="running")
        assert delete_backtest_task(ENGINE_URL, user_id="u3", task_id="bt_del") is True
        assert delete_backtest_task(ENGINE_URL, user_id="u3", task_id="bt_del") is False


# ── TestCollectTaskCrud ───────────────────────────────────────────────────


class TestCollectTaskCrud:
    def test_save_and_get_collect_task(self):
        save_collect_task(ENGINE_URL, user_id="u1", task_id="ct1", status="running", progress=0.5)
        task = get_collect_task(ENGINE_URL, user_id="u1", task_id="ct1")
        assert task is not None
        assert task["status"] == "running"
        assert task["progress"] == 0.5

    def test_list_collect_tasks(self):
        for i in range(3):
            save_collect_task(ENGINE_URL, user_id="u2", task_id=f"ct_u2_{i}", status="completed")
        tasks = list_collect_tasks(ENGINE_URL, user_id="u2")
        assert len(tasks) == 3

    def test_delete_collect_task(self):
        save_collect_task(ENGINE_URL, user_id="u3", task_id="ct_del", status="running")
        assert delete_collect_task(ENGINE_URL, user_id="u3", task_id="ct_del") is True
        assert delete_collect_task(ENGINE_URL, user_id="u3", task_id="ct_del") is False


# ── TestOptimizeTaskCrud ──────────────────────────────────────────────────


class TestOptimizeTaskCrud:
    def test_save_and_get_optimize_task(self):
        save_optimize_task(ENGINE_URL, user_id="u1", task_id="ot1", status="running", result=json.dumps({"best": 0.9}))
        task = get_optimize_task(ENGINE_URL, user_id="u1", task_id="ot1")
        assert task is not None
        assert task["status"] == "running"

    def test_list_optimize_tasks(self):
        for i in range(3):
            save_optimize_task(ENGINE_URL, user_id="u2", task_id=f"ot_u2_{i}", status="completed")
        tasks = list_optimize_tasks(ENGINE_URL, user_id="u2")
        assert len(tasks) == 3

    def test_delete_optimize_task(self):
        save_optimize_task(ENGINE_URL, user_id="u3", task_id="ot_del", status="running")
        assert delete_optimize_task(ENGINE_URL, user_id="u3", task_id="ot_del") is True
        assert delete_optimize_task(ENGINE_URL, user_id="u3", task_id="ot_del") is False


# ── TestComparisonHistoryCrud ─────────────────────────────────────────────


class TestComparisonHistoryCrud:
    def test_save_and_get_comparison_history(self):
        import uuid
        hid = str(uuid.uuid4())
        save_comparison_history(ENGINE_URL, user_id="u1", history_id=hid, strategy_ids="s1,s2", result=json.dumps({"win": True}))
        history = get_comparison_history(ENGINE_URL, user_id="u1", history_id=hid)
        assert history is not None
        assert history["strategy_ids"] == "s1,s2"

    def test_list_comparison_history(self):
        for i in range(3):
            import uuid
            save_comparison_history(ENGINE_URL, user_id="u2", history_id=str(uuid.uuid4()), strategy_ids=f"s{i},s{i+1}")
        histories = list_comparison_history(ENGINE_URL, user_id="u2")
        assert len(histories) == 3

    def test_delete_comparison_history(self):
        import uuid
        hid = str(uuid.uuid4())
        save_comparison_history(ENGINE_URL, user_id="u3", history_id=hid, strategy_ids="s1,s2")
        assert delete_comparison_history(ENGINE_URL, user_id="u3", history_id=hid) is True
        assert delete_comparison_history(ENGINE_URL, user_id="u3", history_id=hid) is False


# ── TestPendingOrderCrud ──────────────────────────────────────────────────


class TestPendingOrderCrud:
    def test_save_and_get_pending_order(self):
        save_pending_order(ENGINE_URL, user_id="u1", order_id="po1", symbol="sh600519", type="buy", price=1800.0, quantity=100, status="pending")
        order = get_pending_order(ENGINE_URL, user_id="u1", order_id="po1")
        assert order is not None
        assert order["symbol"] == "sh600519"
        assert order["price"] == 1800.0

    def test_list_pending_orders(self):
        for i in range(3):
            save_pending_order(ENGINE_URL, user_id="u2", order_id=f"po_u2_{i}", symbol="sh600519", type="buy")
        orders = list_pending_orders(ENGINE_URL, user_id="u2")
        assert len(orders) == 3

    def test_delete_pending_order(self):
        save_pending_order(ENGINE_URL, user_id="u3", order_id="po_del", symbol="sh600519", type="buy")
        assert delete_pending_order(ENGINE_URL, user_id="u3", order_id="po_del") is True
        assert delete_pending_order(ENGINE_URL, user_id="u3", order_id="po_del") is False


# ── TestOrderAuditCrud ────────────────────────────────────────────────────


class TestOrderAuditCrud:
    def test_save_and_get_order_audit(self):
        import uuid
        aid = str(uuid.uuid4())
        save_order_audit(ENGINE_URL, user_id="u1", audit_id=aid, order_id="ord1", action="SUBMITTED", details=json.dumps({"price": 1800}))
        audit = get_order_audit(ENGINE_URL, user_id="u1", audit_id=aid)
        assert audit is not None
        assert audit["order_id"] == "ord1"
        assert audit["action"] == "SUBMITTED"

    def test_list_order_audits(self):
        for i in range(3):
            import uuid
            save_order_audit(ENGINE_URL, user_id="u2", audit_id=str(uuid.uuid4()), order_id=f"ord_{i}", action="FILLED")
        audits = list_order_audits(ENGINE_URL, user_id="u2")
        assert len(audits) == 3

    def test_delete_order_audit(self):
        import uuid
        aid = str(uuid.uuid4())
        save_order_audit(ENGINE_URL, user_id="u3", audit_id=aid, order_id="ord_del", action="CANCELLED")
        assert delete_order_audit(ENGINE_URL, user_id="u3", audit_id=aid) is True
        assert delete_order_audit(ENGINE_URL, user_id="u3", audit_id=aid) is False
