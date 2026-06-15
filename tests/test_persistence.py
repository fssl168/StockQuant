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

        retrieved = get_backtest(ENGINE_URL, result_id)
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
        assert delete_backtest(ENGINE_URL, rid) is True
        assert delete_backtest(ENGINE_URL, rid) is False  # already deleted

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
        assert get_backtest(ENGINE_URL, 999) is None

    def test_get_kline_missing_symbol(self):
        """get_kline for a symbol that doesn't exist returns empty list."""
        assert get_kline(ENGINE_URL, "NONEXISTENT.SZ") == []

    def test_delete_nonexistent_id(self):
        """delete_backtest(id=999) returns False for non-existing record."""
        assert delete_backtest(ENGINE_URL, 999) is False
