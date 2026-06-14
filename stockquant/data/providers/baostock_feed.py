# -*- coding: utf-8 -*-
"""F011 BaoStock 数据源 — 历史 K 线数据"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from stockquant.data.feed import DataFeed
from stockquant.models.bar import BarData

logger = logging.getLogger("stockquant.data")


class BaoStockFeed(DataFeed):
    """
    BaoStock 数据源。

    用法:
        feed = BaoStockFeed(
            symbols=["sh600519", "sz000858"],
            timeframe="1d",
            start="2020-01-01",
            end="2024-12-31",
        )
        cerebro.add_data(feed)

    支持的时间框架:
        - "1d": 日线
        - "1w": 周线
        - "1m": 月线
        - "5min", "15min", "30min", "60min": 分钟线
    """

    _api_url = "http://api.baostock.org/rest"
    _cache_dir: Optional[str] = None

    def __init__(
        self,
        symbols: List[str],
        timeframe: str = "1d",
        start: str = "",
        end: str = "",
        adjustflag: str = "3",  # 3: 复权（前复权）
        cache_dir: Optional[str] = None,
    ):
        """
        Parameters
        ----------
        symbols : List[str]
            标的代码列表，如 ["sh600519", "sz000858"]
        timeframe : str
            时间框架
        start : str
            开始日期 "YYYY-MM-DD"
        end : str
            结束日期 "YYYY-MM-DD"
        adjustflag : str
            复权方式: 2(后复权) 3(前复权)
        cache_dir : str or None
            缓存目录路径
        """
        self._symbols = symbols
        self._timeframe = timeframe
        self._start = start or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        self._end = end or datetime.now().strftime("%Y-%m-%d")
        self._adjustflag = adjustflag
        self._cache_dir = cache_dir

        self._bars: Dict[str, List[BarData]] = {}
        self._dataframes: Dict[str, pd.DataFrame] = {}
        self._started = False

    def start(self):
        """启动时拉取数据"""
        logger.info(f"BaoStockFeed: fetching data for {self._symbols} ({self._timeframe})")
        self._fetch_all()
        self._started = True

    def stop(self):
        self._started = False

    def _fetch_all(self):
        """拉取所有标的的数据"""
        try:
            import requests
        except ImportError:
            logger.error("BaoStockFeed requires 'requests' package")
            return

        # 尝试导入 baostock
        try:
            import baostock as bs
        except ImportError:
            logger.warning(
                "baostock package not installed. "
                "Install with: pip install baostock "
                "Or use CSVFeed for CSV-based backtesting."
            )
            return

        # 登录
        lg = bs.login()
        if lg.error_code != "0":
            logger.error(f"BaoStock login failed: {lg.error_msg}")
            return

        try:
            for symbol in self._symbols:
                bars = self._fetch_single(bs, symbol)
                self._bars[symbol] = bars
                self._dataframes[symbol] = self._bars_to_df(symbol)
        finally:
            bs.logout()

    def _fetch_single(self, bs, symbol: str) -> List[BarData]:
        """拉取单个标的数据"""
        # 尝试缓存
        cached = self._read_cache(symbol)
        if cached is not None:
            return cached

        fields = "date,open,high,low,close,volume,amount"
        query = bs.query_history_k_data_plus(
            symbol,
            fields,
            start_date=self._start,
            end_date=self._end,
            frequency=self._timeframe_to_bs(),
            adjustflag=self._adjustflag,
        )

        bars = []
        while (query.error_code == "0") and query.next():
            row = query.get_row_data()
            bar = self._row_to_bar(row, symbol)
            if bar:
                bars.append(bar)

        # 写入缓存
        self._write_cache(symbol, bars)
        return bars

    @staticmethod
    def _timeframe_to_bs() -> str:
        mapping = {
            "1d": "d", "1w": "w", "1m": "m",
            "5min": "5", "15min": "15", "30min": "30", "60min": "60",
        }
        return mapping.get("1d", "d")

    @staticmethod
    def _row_to_bar(row: List[str], symbol: str) -> Optional[BarData]:
        """将 BaoStock 行数据转为 BarData"""
        try:
            dt = datetime.strptime(row[0], "%Y-%m-%d")
            return BarData(
                symbol=symbol,
                datetime=dt,
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=int(float(row[5])) if row[5] else 0,
                turnover=float(row[6]) if len(row) > 6 and row[6] else 0.0,
            )
        except (ValueError, IndexError):
            return None

    def _bars_to_df(self, symbol: str) -> pd.DataFrame:
        bars = self._bars.get(symbol, [])
        if not bars:
            return pd.DataFrame()
        df = pd.DataFrame([b.__dict__ for b in bars])
        df = df.sort_values("datetime")
        return df.reset_index(drop=True)

    # ------------------------------------------------------------------
    # 缓存
    # ------------------------------------------------------------------

    def _cache_path(self, symbol: str) -> Optional[str]:
        if not self._cache_dir:
            return None
        os.makedirs(self._cache_dir, exist_ok=True)
        return os.path.join(self._cache_dir, f"{symbol}_{self._timeframe}.csv")

    def _read_cache(self, symbol: str) -> Optional[List[BarData]]:
        path = self._cache_path(symbol)
        if not path or not os.path.exists(path):
            return None
        try:
            df = pd.read_csv(path)
            bars = []
            for _, row in df.iterrows():
                dt = pd.to_datetime(row["datetime"])
                bar = BarData(
                    symbol=symbol,
                    datetime=dt.to_pydatetime(),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(row["volume"]) if pd.notna(row["volume"]) else 0,
                    turnover=float(row["turnover"]) if pd.notna(row["turnover"]) else 0.0,
                )
                bars.append(bar)
            logger.info(f"BaoStockFeed: loaded {len(bars)} bars from cache for {symbol}")
            return bars
        except Exception as e:
            logger.warning(f"BaoStockFeed: cache read failed for {symbol}: {e}")
            return None

    def _write_cache(self, symbol: str, bars: List[BarData]):
        path = self._cache_path(symbol)
        if not path:
            return
        try:
            df = pd.DataFrame([b.__dict__ for b in bars])
            df.to_csv(path, index=False)
            logger.info(f"BaoStockFeed: cached {len(bars)} bars for {symbol}")
        except Exception as e:
            logger.warning(f"BaoStockFeed: cache write failed for {symbol}: {e}")

    # ------------------------------------------------------------------
    # DataFeed ABC
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        first = self._symbols[0] if self._symbols else None
        return len(self._bars.get(first, []))

    def __getitem__(self, key):
        # 支持 index 和 symbol
        if isinstance(key, int):
            # 按 index 取第一个标的的 bar
            first = self._symbols[0] if self._symbols else None
            if not first:
                raise IndexError("No symbols")
            bars = self._bars.get(first, [])
            if key < 0:
                key = len(bars) + key
            return bars[key]
        elif isinstance(key, str):
            # 按 symbol 返回 dataframe
            return self._dataframes.get(key, pd.DataFrame())
        else:
            raise TypeError(f"Key must be int or str, got {type(key)}")

    @property
    def symbol(self) -> str:
        return ",".join(self._symbols)

    @property
    def timeframe(self) -> str:
        return self._timeframe

    def get_dataframe(self, symbol: Optional[str] = None) -> pd.DataFrame:
        if symbol:
            return self._dataframes.get(symbol, pd.DataFrame())
        # 合并所有标的
        dfs = [df for df in self._dataframes.values() if not df.empty]
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
