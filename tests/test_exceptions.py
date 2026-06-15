# -*- coding: utf-8 -*-
"""Tests for stockquant.data.exceptions"""

from __future__ import annotations

import pytest

from stockquant.data.exceptions import (
    StockQuantError,
    DataError,
    DataFetchError,
    RateLimitError,
    DataSourceUnavailableError,
    DataValidationError,
    EngineError,
    OrderError,
    RiskError,
    AIError,
    LLMResponseError,
    ToolExecutionError,
)


class TestStockQuantError:
    def test_base_exception(self):
        with pytest.raises(StockQuantError):
            raise StockQuantError("base error")


class TestDataFetchError:
    def test_default_values(self):
        err = DataFetchError("fetch failed")
        assert str(err) == "fetch failed"
        assert err.source == ""
        assert err.retryable is True

    def test_custom_source(self):
        err = DataFetchError("fetch failed", source="baostock")
        assert err.source == "baostock"

    def test_is_subclass_of_data_error(self):
        err = DataFetchError("test")
        assert isinstance(err, DataError)
        assert isinstance(err, StockQuantError)


class TestRateLimitError:
    def test_source_stored(self):
        err = RateLimitError("rate limit", source="akshare")
        assert err.source == "akshare"
        assert isinstance(err, DataError)

    def test_default_message(self):
        err = RateLimitError(source="test")
        assert isinstance(err, DataError)


class TestDataSourceUnavailableError:
    def test_source_stored(self):
        err = DataSourceUnavailableError("connection refused", source="tushare")
        assert err.source == "tushare"
        assert isinstance(err, DataError)


class TestDataValidationError:
    def test_not_retryable(self):
        err = DataValidationError("missing OHLC columns", source="csv")
        # DataValidationError inherits from DataError (not DataFetchError), so no retryable attr
        assert isinstance(err, DataError)
        assert isinstance(err, StockQuantError)


class TestEngineErrors:
    def test_order_error(self):
        err = OrderError("invalid quantity")
        assert isinstance(err, EngineError)
        assert isinstance(err, StockQuantError)

    def test_risk_error(self):
        err = RiskError("position limit exceeded")
        assert isinstance(err, EngineError)


class TestAIErrors:
    def test_llm_response_error(self):
        err = LLMResponseError("malformed JSON")
        assert isinstance(err, AIError)

    def test_tool_execution_error(self):
        err = ToolExecutionError("tool returned error")
        assert isinstance(err, AIError)


class TestExceptionHierarchy:
    def test_all_inherit_from_stock_quant_error(self):
        classes = [
            DataError, DataFetchError, RateLimitError,
            DataSourceUnavailableError, DataValidationError,
            EngineError, OrderError, RiskError,
            AIError, LLMResponseError, ToolExecutionError,
        ]
        for cls in classes:
            assert issubclass(cls, StockQuantError), f"{cls.__name__} should inherit from StockQuantError"

    def test_rate_limit_directly_from_data_error(self):
        """RateLimitError inherits directly from DataError (not DataFetchError)."""
        assert issubclass(RateLimitError, DataError)
        assert not issubclass(RateLimitError, DataFetchError)

    def test_datasource_unavailable_directly_from_data_error(self):
        """DataSourceUnavailableError inherits directly from DataError."""
        assert issubclass(DataSourceUnavailableError, DataError)
        assert not issubclass(DataSourceUnavailableError, DataFetchError)
