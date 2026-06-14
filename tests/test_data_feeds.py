# -*- coding: utf-8 -*-
"""F011 ParquetFeed + SQLiteFeed 测试"""

import os
import tempfile

import numpy as np
import pytest

from stockquant.data.providers.sqlite_feed import SQLiteFeed

# Parquet requires pyarrow which is optional
try:
    import pyarrow  # noqa: F401
    _has_pyarrow = True
except ImportError:
    _has_pyarrow = False


def _create_parquet_file():
    """创建临时 Parquet 文件"""
    import pandas as pd
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    np.random.seed(42)
    prices = [100.0]
    for _ in range(100):
        prices.append(prices[-1] * (1 + np.random.randn() * 0.02))

    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices[:-1],
        "high": [p * 1.02 for p in prices[:-1]],
        "low": [p * 0.98 for p in prices[:-1]],
        "close": prices[:-1],
        "volume": [1_000_000] * 100,
    })

    tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
    tmp.close()
    df.to_parquet(tmp.name, index=False)
    return tmp.name


def _create_sqlite_file():
    """创建临时 SQLite 数据库"""
    import sqlite3
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    conn = sqlite3.connect(tmp.name)
    conn.execute("""
        CREATE TABLE kline (
            timestamp TEXT, symbol TEXT,
            open REAL, high REAL, low REAL, close REAL, volume REAL
        )
    """)
    np.random.seed(42)
    prices = [100.0]
    for _ in range(100):
        prices.append(prices[-1] * (1 + np.random.randn() * 0.02))
        dt = f"2024-{(len(prices)//30)+1:02d}-{(len(prices)%28)+1:02d}"
        conn.execute(
            "INSERT INTO kline VALUES (?, ?, ?, ?, ?, ?, ?)",
            (dt, "sh600519", prices[-1], prices[-1]*1.02, prices[-1]*0.98, prices[-1], 1_000_000),
        )
    conn.commit()
    conn.close()
    return tmp.name


@pytest.mark.skipif(not _has_pyarrow, reason="pyarrow not installed")
class TestParquetFeed:
    def test_load_and_len(self):
        path = _create_parquet_file()
        try:
            feed = ParquetFeed(path, symbol="test", timeframe="1d")
            assert len(feed) == 100
            assert feed.symbol == "test"
            assert feed.timeframe == "1d"
        finally:
            os.unlink(path)

    def test_getitem(self):
        path = _create_parquet_file()
        try:
            feed = ParquetFeed(path, symbol="test", timeframe="1d")
            bar = feed[0]
            assert bar.symbol == "test"
            assert bar.open > 0
            assert bar.close > 0
        finally:
            os.unlink(path)

    def test_get_dataframe(self):
        path = _create_parquet_file()
        try:
            feed = ParquetFeed(path, symbol="test", timeframe="1d")
            df = feed.get_dataframe()
            assert len(df) == 100
            assert "close" in df.columns
        finally:
            os.unlink(path)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            ParquetFeed("/nonexistent/file.parquet")


class TestSQLiteFeed:
    def test_load_and_len(self):
        path = _create_sqlite_file()
        try:
            feed = SQLiteFeed(path, table="kline", symbol="sh600519", timeframe="1d")
            assert len(feed) == 100
            assert feed.symbol == "sh600519"
        finally:
            os.unlink(path)

    def test_getitem(self):
        path = _create_sqlite_file()
        try:
            feed = SQLiteFeed(path, table="kline", symbol="sh600519", timeframe="1d")
            bar = feed[0]
            assert bar.symbol == "sh600519"
            assert bar.close > 0
        finally:
            os.unlink(path)

    def test_get_dataframe(self):
        path = _create_sqlite_file()
        try:
            feed = SQLiteFeed(path, table="kline", symbol="sh600519", timeframe="1d")
            df = feed.get_dataframe()
            assert len(df) == 100
            assert "close" in df.columns
        finally:
            os.unlink(path)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            SQLiteFeed("/nonexistent/db.sqlite")
