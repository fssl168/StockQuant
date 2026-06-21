# -*- coding: utf-8 -*-
"""CSV 数据源 — F011 数据层实现"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import pandas as pd

from stockquant.data.feed import DataFeed
from stockquant.models.bar import BarData


class CSVFeed(DataFeed):
    """
    从本地 CSV 文件加载 K 线数据。

    CSV 格式要求:
        timestamp,open,high,low,close,volume
        2020-01-01,10.5,11.0,10.2,10.8,1000000
        ...

    Usage:
        feed = CSVFeed("sh600519_1d.csv", symbol="sh600519", timeframe="1d")
        cerebro.add_data(feed)
    """

    _COLUMNS = {
        "open": 0,
        "high": 1,
        "low": 2,
        "close": 3,
        "volume": 4,
    }

    def __init__(
        self,
        filepath: str,
        symbol: str = "",
        timeframe: str = "1d",
        datetime_col: str = "timestamp",
        datetime_fmt: Optional[str] = None,
    ):
        self._filepath = filepath
        self._symbol = symbol or os.path.basename(filepath).replace(".csv", "")
        self._timeframe = timeframe
        self._datetime_col = datetime_col
        self._datetime_fmt = datetime_fmt

        # 加载数据
        self._df = self._load()
        self._bars: Optional[list[BarData]] = None

    def _load(self) -> pd.DataFrame:
        """加载 CSV 文件"""
        if not os.path.exists(self._filepath):
            raise FileNotFoundError(f"CSV file not found: {self._filepath}")

        df = pd.read_csv(self._filepath)

        # 解析日期列
        if self._datetime_col in df.columns:
            df[self._datetime_col] = pd.to_datetime(df[self._datetime_col], errors='coerce')
            df = df.dropna(subset=[self._datetime_col])
            df.set_index(self._datetime_col, inplace=True)
        elif len(df.columns) > 0:
            # 尝试第一列作为日期
            df.columns = list(df.columns)
            try:
                df.index = pd.to_datetime(df.iloc[:, 0])
            except Exception:
                pass

        df.sort_index(inplace=True)
        return df

    def start(self):
        """预加载数据到内存，无需异步启动。"""

    def stop(self):
        """预加载数据在内存中，无需主动关闭连接。"""

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
            bar = BarData(
                symbol=self._symbol,
                datetime=dt,
                open=float(row.get("open", row.iloc[0])),
                high=float(row.get("high", row.iloc[1])),
                low=float(row.get("low", row.iloc[2])),
                close=float(row.get("close", row.iloc[3])),
                volume=float(row.get("volume", row.iloc[4])) if len(row) > 4 else 0.0,
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
