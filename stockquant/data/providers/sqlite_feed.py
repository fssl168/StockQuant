# -*- coding: utf-8 -*-
"""SQLite 数据源 — F011 SQLite 数据库读取"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import pandas as pd

from stockquant.data.feed import DataFeed
from stockquant.models.bar import BarData


class SQLiteFeed(DataFeed):
    """
    从 SQLite 数据库加载 K 线数据。

    数据库表结构要求:
        CREATE TABLE kline (
            timestamp TEXT PRIMARY KEY,
            symbol TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL
        );

    Usage:
        feed = SQLiteFeed("market.db", table="kline", symbol="sh600519", timeframe="1d")
        cerebro.add_data(feed)
    """

    def __init__(
        self,
        db_path: str,
        table: str = "kline",
        symbol: str = "",
        timeframe: str = "1d",
        date_col: str = "timestamp",
        where: Optional[str] = None,
    ):
        self._db_path = db_path
        self._table = table
        self._symbol = symbol
        self._timeframe = timeframe
        self._date_col = date_col
        self._where = where or (f"symbol = '{symbol}'" if symbol else "")
        self._df = self._load()
        self._bars: Optional[list[BarData]] = None

    def _load(self) -> pd.DataFrame:
        """从 SQLite 加载数据"""
        if not os.path.exists(self._db_path):
            raise FileNotFoundError(f"SQLite database not found: {self._db_path}")

        query = f"SELECT * FROM {self._table}"
        if self._where:
            query += f" WHERE {self._where}"
        query += f" ORDER BY {self._date_col}"

        conn = self._connect()
        try:
            df = pd.read_sql_query(query, conn)
        finally:
            conn.close()

        if df.empty:
            return pd.DataFrame()

        # 解析日期
        if self._date_col in df.columns:
            df[self._date_col] = pd.to_datetime(df[self._date_col])
            df.set_index(self._date_col, inplace=True)
        elif not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        df.sort_index(inplace=True)
        return df

    def _connect(self):
        """创建数据库连接（懒加载 sqlite3）"""
        import sqlite3
        return sqlite3.connect(self._db_path)

    def start(self):
        pass

    def stop(self):
        pass

    def __len__(self) -> int:
        return len(self._df)

    def __getitem__(self, index: int) -> BarData:
        if self._bars is None:
            self._bars = self._to_bars()
        return self._bars[index]

    def _to_bars(self) -> list[BarData]:
        """将 DataFrame 转换为 BarData 列表"""
        bars = []
        for idx, row in self._df.iterrows():
            dt = idx if isinstance(idx, datetime) else idx.to_pydatetime()
            open_v = float(row.get("open", row.iloc[0]))
            high_v = float(row.get("high", row.iloc[1]))
            low_v = float(row.get("low", row.iloc[2]))
            close_v = float(row.get("close", row.iloc[3]))
            vol_v = float(row.get("volume", row.iloc[4])) if len(row) > 4 else 0.0
            bar = BarData(
                symbol=self._symbol or row.get("symbol", "unknown"),
                datetime=dt,
                open=open_v,
                high=high_v,
                low=low_v,
                close=close_v,
                volume=vol_v,
            )
            bars.append(bar)
        return bars

    def get_dataframe(self) -> pd.DataFrame:
        return self._df.copy()

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def timeframe(self) -> str:
        return self._timeframe
