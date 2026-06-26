# -*- coding: utf-8 -*-
"""交易日历 — 基于 exchange-calendars 的 A 股/港股/美股日历"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, List, Optional

logger = logging.getLogger(__name__)

# Market calendars supported by exchange_calendars
MARKET_CALENDARS = {
    'CN': 'XSHG',   # Shanghai Stock Exchange (covers A-shares)
    'HK': 'XHKG',   # Hong Kong Stock Exchange
    'US': 'XNYS',   # NYSE (proxy for US markets)
}

if TYPE_CHECKING:
    pass


class TradingCalendar:
    """交易日历管理器。

    基于 exchange_calendars 库，支持 CN（中国A股）/ HK / US 市场。
    exchange_calendars 为软依赖，未安装时提供 fallback 逻辑（仅周末判断）。

    Usage:
        cal = TradingCalendar(market='CN')
        cal.is_trading_day(date(2024, 10, 1))  # False (holiday)
        cal.next_trading_day(date(2024, 10, 7))  # 2024-10-08
    """

    def __init__(self, market: str = 'CN') -> None:
        """
        Parameters
        ----------
        market : str
            'CN' (default), 'HK', or 'US'
        """
        market_upper = market.upper()
        if market_upper not in MARKET_CALENDARS:
            raise ValueError(
                f"Unsupported market '{market}'. "
                f"Supported: {list(MARKET_CALENDARS.keys())}"
            )
        self.market = market_upper
        self.exchange_id = MARKET_CALENDARS[market_upper]
        self._cache: dict[date, bool] = {}
        self._calendar = self._get_calendar()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_calendar(self):
        """Get exchange_calendars calendar, or None if not installed."""
        try:
            import exchange_calendars as xcals  # noqa: F811
            return xcals.get_calendar(self.exchange_id)
        except ImportError:
            return None

    @staticmethod
    def _parse_date(d: date | datetime | str) -> date:
        """统一解析日期为 date 对象。"""
        if isinstance(d, str):
            return datetime.strptime(d, "%Y-%m-%d").date()
        if isinstance(d, datetime):
            return d.date()
        if isinstance(d, date):
            return d
        raise TypeError(f"Unsupported date type: {type(d)}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_trading_day(self, d: date | datetime | str) -> bool:
        """判断指定日期是否为交易日。

        Parameters
        ----------
        d : date | datetime | str
            日期，支持 date/datetime/str (YYYY-MM-DD)

        Returns
        -------
        bool
        """
        target = self._parse_date(d)

        # 命中缓存
        if target in self._cache:
            return self._cache[target]

        # 快速周末检查
        if self._is_weekend_fallback(target):
            self._cache[target] = False
            return False

        # 精确日历
        if self._calendar is not None:
            result = self._calendar.is_session(target)
            self._cache[target] = result
            return result

        # fallback：仅周末判断
        self._cache[target] = not self._is_weekend_fallback(target)
        return not self._is_weekend_fallback(target)

    def next_trading_day(self, d: date | datetime | str, n: int = 1) -> date:
        """获取第 N 个交易日之后的日期。

        Parameters
        ----------
        d : date | datetime | str
        n : int
            第 N 个交易日，默认 1

        Returns
        -------
        date
        """
        if n < 1:
            raise ValueError("n must be >= 1")
        current = self._parse_date(d)
        days = 0
        candidate = current
        while days < n:
            candidate += timedelta(days=1)
            if self.is_trading_day(candidate):
                days += 1
        return candidate

    def prev_trading_day(self, d: date | datetime | str, n: int = 1) -> date:
        """获取第 N 个交易日之前的日期。

        Parameters
        ----------
        d : date | datetime | str
        n : int
            第 N 个交易日，默认 1

        Returns
        -------
        date
        """
        if n < 1:
            raise ValueError("n must be >= 1")
        current = self._parse_date(d)
        days = 0
        candidate = current
        while days < n:
            candidate -= timedelta(days=1)
            if self.is_trading_day(candidate):
                days += 1
        return candidate

    def days_between(self, start: date | datetime | str,
                     end: date | datetime | str) -> int:
        """两个日期之间的交易日天数。

        Parameters
        ----------
        start : date | datetime | str
        end : date | datetime | str

        Returns
        -------
        int
            交易日天数（end - start，若 end < start 则返回负数）
        """
        s = self._parse_date(start)
        e = self._parse_date(end)
        if s == e:
            return 0

        direction = 1 if e > s else -1
        count = 0
        current = s
        while current != e:
            current += timedelta(days=direction)
            if self.is_trading_day(current):
                count += 1
        return count * direction

    def get_trading_days(self, start: date | datetime | str,
                         end: date | datetime | str,
                         n: Optional[int] = None) -> List[date]:
        """获取指定范围内的交易日列表。

        Parameters
        ----------
        start : date | datetime | str
        end : date | datetime | str
        n : int | None
            如果指定，最多返回 n 个交易日

        Returns
        -------
        List[date]
        """
        s = self._parse_date(start)
        e = self._parse_date(end)
        if s > e:
            return []

        result: List[date] = []
        current = s
        while current <= e:
            if self.is_trading_day(current):
                result.append(current)
                if n is not None and len(result) >= n:
                    break
            current += timedelta(days=1)
        return result

    # ------------------------------------------------------------------
    # Static / fallback helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_weekend_fallback(d: date) -> bool:
        """判断是否为周末（0=Monday .. 4=Friday, 5=Saturday, 6=Sunday）。"""
        return d.weekday() >= 5

    @staticmethod
    def is_weekend(d: date | datetime) -> bool:
        """判断是否为周末（fallback 用）。"""
        return TradingCalendar._is_weekend_fallback(
            d.date() if isinstance(d, datetime) else d
        )
