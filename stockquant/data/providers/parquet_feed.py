# -*- coding: utf-8 -*-
"""Parquet 数据源 — F011 高性能本地 Parquet 读取"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import pandas as pd

from stockquant.data.feed import DataFeed
from stockquant.models.bar import BarData


class ParquetFeed(DataFeed):
    """
    从本地 Parquet 文件加载 K 线数据。

    Parquet 是列式存储格式，读取速度比 CSV 快 5-10 倍，适合大规模回测。

    Usage:
        feed = ParquetFeed("sh600519_1d.parquet", symbol="sh600519", timeframe="1d")
        cerebro.add_data(feed)
    """

    def __init__(
        self,
        filepath: str,
        symbol: str = "",
        timeframe: str = "1d",
        date_col: str = "timestamp",
        date_format: Optional[str] = None,
    ):
        self._filepath = filepath
        self._symbol = symbol or os.path.basename(filepath).replace(".parquet", "")
        self._timeframe = timeframe
        self._date_col = date_col
        self._date_format = date_format
        self._df = self._load()
        self._bars: Optional[list[BarData]] = None

    def _load(self) -> pd.DataFrame:
        """加载 Parquet 文件"""
        if not os.path.exists(self._filepath):
            raise FileNotFoundError(f"Parquet file not found: {self._filepath}")

        df = pd.read_parquet(self._filepath)

        # 解析日期
        if self._date_col in df.columns:
            df[self._date_col] = pd.to_datetime(df[self._date_col], format=self._date_format)
            df.set_index(self._date_col, inplace=True)
        elif not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception:
                pass

        df.sort_index(inplace=True)
        return df

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
            # 尝试标准列名，fallback 到位置索引
            open_v = float(row.get("open", row.iloc[0]))
            high_v = float(row.get("high", row.iloc[1]))
            low_v = float(row.get("low", row.iloc[2]))
            close_v = float(row.get("close", row.iloc[3]))
            vol_v = float(row.get("volume", row.iloc[4])) if len(row) > 4 else 0.0
            bar = BarData(
                symbol=self._symbol,
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
