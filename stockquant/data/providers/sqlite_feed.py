# -*- coding: utf-8 -*-
"""数据库数据源 — 支持 SQLite 和 PostgreSQL"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import pandas as pd

from stockquant.data.feed import DataFeed
from stockquant.models.bar import BarData


class SQLiteFeed(DataFeed):
    """
    从数据库加载 K 线数据（支持 SQLite 和 PostgreSQL）。

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

    支持两种连接方式:
        1. SQLite: db_path="market.db" (使用 sqlite3)
        2. PostgreSQL: db_url="postgresql://..." (使用 SQLAlchemy)

    Usage:
        # SQLite
        feed = SQLiteFeed("market.db", table="kline", symbol="sh600519", timeframe="1d")
        # PostgreSQL
        feed = SQLiteFeed("postgresql://user:pass@host:5432/db", table="kline", symbol="sh600519", timeframe="1d")
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
        self._is_postgresql = db_path.startswith("postgresql://")
        self._df = self._load()
        self._bars: Optional[list[BarData]] = None

    def _connect(self):
        """创建数据库连接（懒加载）"""
        if self._is_postgresql:
            import sqlalchemy
            engine = sqlalchemy.create_engine(self._db_path)
            return engine.connect()
        else:
            import sqlite3
            if not os.path.exists(self._db_path):
                raise FileNotFoundError(f"SQLite database not found: {self._db_path}")
            return sqlite3.connect(self._db_path)

    def _load(self) -> pd.DataFrame:
        """从数据库加载数据"""
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

    def start(self):
        """数据已在 _load() 中加载，无需异步启动。"""

    def stop(self):
        """数据库连接在 _load() 后已关闭，无需主动关闭。"""

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
