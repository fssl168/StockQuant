# -*- coding: utf-8 -*-
"""Tests for stockquant.data.retry"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from stockquant.data.retry import (
    data_fetch_retry,
    random_sleep,
    BAOSTOCK_RETRY,
    PUBLIC_API_RETRY,
    SENSITIVE_API_RETRY,
    no_retry,
)
from stockquant.data.exceptions import (
    DataFetchError,
    RateLimitError,
    DataSourceUnavailableError,
    DataError,
)


class TestDataFetchRetry:
    def test_retry_succeeds_on_transient_error(self):
        """Should retry and succeed on ConnectionError."""
        call_count = 0

        @data_fetch_retry(max_retries=2, base_wait=0.01, max_wait=0.01, jitter=0)
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("network blip")
            return "success"

        result = failing_then_success()
        assert result == "success"
        assert call_count == 3

    def test_retry_exhausted_raises(self):
        """Should raise after max_retries exhausted."""
        call_count = 0

        @data_fetch_retry(max_retries=2, base_wait=0.01, max_wait=0.01, jitter=0)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("permanent failure")

        with pytest.raises(ConnectionError):
            always_fails()
        assert call_count == 3  # 1 initial + 2 retries

    def test_rate_limited_not_retryable(self):
        """RateLimitError (not subclass of DataFetchError) should NOT be retried."""
        call_count = 0

        @data_fetch_retry(max_retries=3, base_wait=0.01, max_wait=0.01, jitter=0)
        def rate_limited():
            nonlocal call_count
            call_count += 1
            raise RateLimitError("too fast")

        with pytest.raises(RateLimitError):
            rate_limited()
        assert call_count == 1  # No retry for RateLimitError

    def test_datasource_unavailable_no_retry(self):
        """DataSourceUnavailableError should NOT be retried."""
        call_count = 0

        @data_fetch_retry(max_retries=3, base_wait=0.01, max_wait=0.01, jitter=0)
        def unavailable():
            nonlocal call_count
            call_count += 1
            raise DataSourceUnavailableError("down")

        with pytest.raises(DataSourceUnavailableError):
            unavailable()
        assert call_count == 1

    def test_normal_return_value(self):
        """Should pass through normal return values."""
        @data_fetch_retry(max_retries=1)
        def returns_data():
            return {"data": [1, 2, 3]}

        result = returns_data()
        assert result == {"data": [1, 2, 3]}

    def test_timeout_error_retries(self):
        """TimeoutError should trigger retry."""
        call_count = 0

        @data_fetch_retry(max_retries=2, base_wait=0.01, max_wait=0.01, jitter=0)
        def times_out():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("timeout")
            return "ok"

        assert times_out() == "ok"
        assert call_count == 2

    def test_os_error_retries(self):
        """OSError should trigger retry."""
        call_count = 0

        @data_fetch_retry(max_retries=2, base_wait=0.01, max_wait=0.01, jitter=0)
        def os_fails():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OSError("device error")
            return "ok"

        assert os_fails() == "ok"
        assert call_count == 2


class TestRandomSleep:
    def test_sleeps_before_call(self):
        """Decorator should add delay before function call."""
        start = time.time()

        @random_sleep(min_delay=0.01, max_delay=0.05)
        def quick_func():
            return "done"

        result = quick_func()
        elapsed = time.time() - start

        assert result == "done"
        assert elapsed >= 0.01  # At least min_delay

    def test_preserves_function_metadata(self):
        """Wrapped function should preserve original metadata."""
        @random_sleep(min_delay=0.01, max_delay=0.01)
        def named_function():
            """Original docstring."""
            return 42

        assert named_function.__name__ == "named_function"
        assert named_function.__doc__ == "Original docstring."


class TestPresetConfigs:
    def test_baostock_retry_config(self):
        assert isinstance(BAOSTOCK_RETRY, dict)
        assert BAOSTOCK_RETRY['max_retries'] == 3
        assert BAOSTOCK_RETRY['base_wait'] == 2.0

    def test_public_api_retry_config(self):
        assert isinstance(PUBLIC_API_RETRY, dict)
        assert PUBLIC_API_RETRY['max_retries'] == 5

    def test_sensitive_api_retry_config(self):
        assert isinstance(SENSITIVE_API_RETRY, dict)
        assert SENSITIVE_API_RETRY['max_retries'] == 2
        assert SENSITIVE_API_RETRY['max_wait'] == 60.0

    def test_no_retry_is_identity(self):
        """no_retry should pass through the function unchanged."""
        @no_retry
        def my_func():
            return "safe"

        assert my_func() == "safe"


class TestRetryWithMock:
    def test_mock_data_source(self):
        """Test retry with a mock that tracks call count."""
        mock = MagicMock(side_effect=[DataFetchError("fail"), DataFetchError("fail"), "success"])

        @data_fetch_retry(max_retries=3, base_wait=0.01, max_wait=0.01, jitter=0)
        def fetch_data():
            return mock()

        result = fetch_data()
        assert result == "success"
        assert mock.call_count == 3
