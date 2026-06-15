# -*- coding: utf-8 -*-
"""Tests for stockquant.data.calendar"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from stockquant.data.calendar import TradingCalendar


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture
def cn_calendar():
    """CN market calendar with exchange_calendars mocked absent (fallback)."""
    with patch('stockquant.data.calendar.TradingCalendar._get_calendar', return_value=None):
        return TradingCalendar(market='CN')


@pytest.fixture
def cn_calendar_with_lib():
    """CN market calendar with exchange_calendars available."""
    mock_sessions = {
        date(2024, 1, 8),  # Mon — trading day
    }

    mock_xcals = MagicMock()

    def make_cal(sessions):
        mock_cal = MagicMock()
        mock_cal.all_sessions = sessions
        mock_cal.is_session.side_effect = lambda d: d in sessions
        return mock_cal

    mock_xcals.get_calendar.side_effect = lambda _: make_cal(mock_sessions)

    with patch.dict('sys.modules', {'exchange_calendars': mock_xcals}):
        import importlib
        import stockquant.data.calendar as cal_mod
        importlib.reload(cal_mod)
        cal = cal_mod.TradingCalendar(market='CN')
        yield cal


# ======================================================================
# is_trading_day — fallback (no exchange_calendars)
# ======================================================================

class TestIsTradingDayFallback:

    def test_is_trading_day_weekend(self, cn_calendar):
        """Saturdays and Sundays should return False in fallback mode."""
        assert cn_calendar.is_trading_day(date(2024, 1, 6)) is False  # Saturday
        assert cn_calendar.is_trading_day(date(2024, 1, 7)) is False  # Sunday

    def test_is_trading_day_regular_day(self, cn_calendar):
        """A regular weekday should return True in fallback mode."""
        assert cn_calendar.is_trading_day(date(2024, 1, 8)) is True   # Monday
        assert cn_calendar.is_trading_day(date(2024, 1, 10)) is True  # Wednesday

    def test_is_trading_day_string_input(self, cn_calendar):
        """String date should be parsed and work the same."""
        assert cn_calendar.is_trading_day("2024-01-06") is False  # Saturday
        assert cn_calendar.is_trading_day("2024-01-08") is True   # Monday

    def test_is_trading_day_datetime_input(self, cn_calendar):
        """datetime input should be converted to date."""
        assert cn_calendar.is_trading_day(datetime(2024, 1, 6, 9, 30)) is False
        assert cn_calendar.is_trading_day(datetime(2024, 1, 8, 9, 30)) is True


# ======================================================================
# is_trading_day — with exchange_calendars mock
# ======================================================================

class TestIsTradingDayWithCalendar:

    def test_is_trading_day_known_holiday(self, cn_calendar_with_lib):
        """2024-01-08 (the only trading day in our mock) should be True;
        other dates should be False."""
        # 2024-01-08 is a trading day
        assert cn_calendar_with_lib.is_trading_day(date(2024, 1, 8)) is True
        # 2024-01-01 is NOT in mock_sessions -> False
        assert cn_calendar_with_lib.is_trading_day(date(2024, 1, 1)) is False

    def test_is_trading_day_weekend(self, cn_calendar_with_lib):
        """Weekend dates should be False (caught by weekend check)."""
        assert cn_calendar_with_lib.is_trading_day(date(2024, 1, 6)) is False  # Sat
        assert cn_calendar_with_lib.is_trading_day(date(2024, 1, 7)) is False  # Sun

    def test_is_trading_day_regular_day(self, cn_calendar_with_lib):
        """2024-01-08 (Monday) should be True."""
        assert cn_calendar_with_lib.is_trading_day(date(2024, 1, 8)) is True

    def test_is_trading_day_string_input(self, cn_calendar_with_lib):
        """String input should work."""
        assert cn_calendar_with_lib.is_trading_day("2024-01-08") is True
        assert cn_calendar_with_lib.is_trading_day("2024-01-01") is False


# ======================================================================
# Cache behaviour
# ======================================================================

class TestCache:

    def test_cache_hits_store_results(self, cn_calendar):
        """Results should be cached for repeated calls."""
        d = date(2024, 1, 8)
        cn_calendar.is_trading_day(d)
        assert d in cn_calendar._cache
        assert cn_calendar._cache[d] is True


# ======================================================================
# next_trading_day
# ======================================================================

class TestNextTradingDay:

    def test_next_trading_day_after_weekday(self, cn_calendar):
        """Monday 2024-01-08 -> Tuesday 2024-01-09 (1 day)."""
        result = cn_calendar.next_trading_day(date(2024, 1, 8))
        assert result == date(2024, 1, 9)

    def test_next_trading_day_after_friday(self, cn_calendar):
        """Friday -> next Monday (skip weekend)."""
        result = cn_calendar.next_trading_day(date(2024, 1, 5))
        assert result == date(2024, 1, 8)

    def test_next_trading_day_n(self, cn_calendar):
        """n=2 should skip two trading days."""
        result = cn_calendar.next_trading_day(date(2024, 1, 8), n=2)
        assert result == date(2024, 1, 10)

    def test_next_trading_day_invalid_n(self, cn_calendar):
        """n < 1 should raise ValueError."""
        with pytest.raises(ValueError, match=">= 1"):
            cn_calendar.next_trading_day(date(2024, 1, 8), n=0)


# ======================================================================
# prev_trading_day
# ======================================================================

class TestPrevTradingDay:

    def test_prev_trading_day_after_weekday(self, cn_calendar):
        """Tuesday 2024-01-09 -> Monday 2024-01-08."""
        result = cn_calendar.prev_trading_day(date(2024, 1, 9))
        assert result == date(2024, 1, 8)

    def test_prev_trading_day_after_monday(self, cn_calendar):
        """Monday -> previous Friday (skip weekend)."""
        result = cn_calendar.prev_trading_day(date(2024, 1, 8))
        assert result == date(2024, 1, 5)

    def test_prev_trading_day_n(self, cn_calendar):
        """n=2 should go back two trading days."""
        result = cn_calendar.prev_trading_day(date(2024, 1, 10), n=2)
        assert result == date(2024, 1, 8)

    def test_prev_trading_day_invalid_n(self, cn_calendar):
        with pytest.raises(ValueError, match=">= 1"):
            cn_calendar.prev_trading_day(date(2024, 1, 8), n=-1)


# ======================================================================
# days_between
# ======================================================================

class TestDaysBetween:

    def test_days_between_same_day(self, cn_calendar):
        assert cn_calendar.days_between(date(2024, 1, 8), date(2024, 1, 8)) == 0

    def test_days_between_adjacent_days(self, cn_calendar):
        """Mon -> Tue = 1 trading day."""
        assert cn_calendar.days_between(date(2024, 1, 8), date(2024, 1, 9)) == 1

    def test_days_between_weekend(self, cn_calendar):
        """Fri 1/5 -> Mon 1/8 = 1 trading day (Sat/Sun skipped)."""
        assert cn_calendar.days_between(date(2024, 1, 5), date(2024, 1, 8)) == 1

    def test_days_between_reversed(self, cn_calendar):
        """end < start should return negative."""
        assert cn_calendar.days_between(date(2024, 1, 9), date(2024, 1, 8)) == -1


# ======================================================================
# get_trading_days
# ======================================================================

class TestGetTradingDays:

    def test_get_trading_days_range(self, cn_calendar):
        """Fri 1/5 -> Mon 1/8 should include 1/5, 1/8 (2 days)."""
        result = cn_calendar.get_trading_days(date(2024, 1, 5), date(2024, 1, 8))
        assert result == [date(2024, 1, 5), date(2024, 1, 8)]

    def test_get_trading_days_with_n(self, cn_calendar):
        """n=1 should return at most 1 day."""
        result = cn_calendar.get_trading_days(
            date(2024, 1, 5), date(2024, 1, 10), n=1
        )
        assert len(result) == 1
        assert result[0] == date(2024, 1, 5)

    def test_get_trading_days_empty_range(self, cn_calendar):
        """start > end returns empty list."""
        result = cn_calendar.get_trading_days(date(2024, 1, 10), date(2024, 1, 5))
        assert result == []

    def test_get_trading_days_string_inputs(self, cn_calendar):
        """String date inputs should work."""
        result = cn_calendar.get_trading_days("2024-01-05", "2024-01-08")
        assert result == [date(2024, 1, 5), date(2024, 1, 8)]


# ======================================================================
# Market support
# ======================================================================

class TestMarketSupport:

    def test_calendar_cn_market(self):
        cal = TradingCalendar(market='CN')
        assert cal.market == 'CN'
        assert cal.exchange_id == 'XSHG'

    def test_calendar_us_market(self):
        cal = TradingCalendar(market='US')
        assert cal.market == 'US'
        assert cal.exchange_id == 'XNYS'

    def test_calendar_hk_market(self):
        cal = TradingCalendar(market='HK')
        assert cal.market == 'HK'
        assert cal.exchange_id == 'XHKG'

    def test_case_insensitive_market(self):
        cal = TradingCalendar(market='cn')
        assert cal.market == 'CN'

    def test_unsupported_market_raises(self):
        with pytest.raises(ValueError, match="Unsupported market"):
            TradingCalendar(market='JP')


# ======================================================================
# Static helpers
# ======================================================================

class TestStaticHelpers:

    def test_is_weekend_saturday(self):
        assert TradingCalendar.is_weekend(date(2024, 1, 6)) is True

    def test_is_weekend_sunday(self):
        assert TradingCalendar.is_weekend(date(2024, 1, 7)) is True

    def test_is_weekend_weekday(self):
        assert TradingCalendar.is_weekend(date(2024, 1, 8)) is False

    def test_is_weekend_datetime(self):
        assert TradingCalendar.is_weekend(datetime(2024, 1, 6, 12, 0)) is True

    def test_parse_date_str(self):
        result = TradingCalendar._parse_date("2024-01-08")
        assert result == date(2024, 1, 8)

    def test_parse_date_date(self):
        d = date(2024, 1, 8)
        result = TradingCalendar._parse_date(d)
        assert result is d

    def test_parse_date_datetime(self):
        dt = datetime(2024, 1, 8, 14, 30)
        result = TradingCalendar._parse_date(dt)
        assert result == date(2024, 1, 8)

    def test_parse_date_invalid_type(self):
        with pytest.raises(TypeError, match="Unsupported date type"):
            TradingCalendar._parse_date(12345)  # type: ignore
