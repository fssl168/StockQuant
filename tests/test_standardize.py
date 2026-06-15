# -*- coding: utf-8 -*-
"""Tests for stockquant.data.standardize"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stockquant.data.standardize import (
    STANDARD_COLUMNS,
    COLUMN_MAPPINGS,
    normalize_columns,
    clean_dataframe,
    calculate_standard_indicators,
)


class TestStandardColumns:
    def test_standard_columns_defined(self):
        assert STANDARD_COLUMNS == [
            'date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg',
        ]

    def test_column_mappings_exist(self):
        assert 'baostock' in COLUMN_MAPPINGS
        assert 'akshare' in COLUMN_MAPPINGS
        assert 'csv' in COLUMN_MAPPINGS
        assert 'yahoo' in COLUMN_MAPPINGS


class TestNormalizeColumns:
    def test_baostock_mapping(self):
        df = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02'],
            'open': [10.0, 11.0],
            'high': [11.0, 12.0],
            'low': [9.5, 10.5],
            'close': [10.5, 11.5],
            'volume': [1000, 1100],
            'amount': [10500, 12650],
        })
        result = normalize_columns(df, provider='baostock')
        # date is set as index, so columns should be the non-date standard columns
        assert 'open' in result.columns
        assert 'high' in result.columns
        assert 'low' in result.columns
        assert 'close' in result.columns
        assert 'volume' in result.columns
        assert 'amount' in result.columns
        assert 'pct_chg' in result.columns
        assert isinstance(result.index, pd.DatetimeIndex)

    def test_akshare_mapping(self):
        df = pd.DataFrame({
            '日期': ['2024-01-01', '2024-01-02'],
            '开盘': [10.0, 11.0],
            '最高': [11.0, 12.0],
            '最低': [9.5, 10.5],
            '收盘': [10.5, 11.5],
            '成交量': [1000, 1100],
            '成交额': [10500, 12650],
        })
        result = normalize_columns(df, provider='akshare')
        assert 'open' in result.columns
        assert 'close' in result.columns
        assert isinstance(result.index, pd.DatetimeIndex)

    def test_generic_no_remap(self):
        df = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02'],
            'open': [10.0, 11.0],
            'high': [11.0, 12.0],
            'low': [9.5, 10.5],
            'close': [10.5, 11.5],
            'volume': [1000, 1100],
            'amount': [10500, 12650],
        })
        result = normalize_columns(df, provider='generic')
        assert 'open' in result.columns
        assert 'close' in result.columns
        assert isinstance(result.index, pd.DatetimeIndex)

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = normalize_columns(df, provider='generic')
        assert result.empty
        assert 'date' in result.columns

    def test_missing_columns_filled_with_nan(self):
        df = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02'],
            'open': [10.0, 11.0],
            'close': [10.5, 11.5],
        })
        result = normalize_columns(df, provider='generic')
        assert 'high' in result.columns
        assert 'volume' in result.columns
        assert pd.isna(result['high']).all()

    def test_date_set_as_index(self):
        df = pd.DataFrame({
            'date': ['2024-01-02', '2024-01-01'],
            'open': [11.0, 10.0],
            'close': [11.5, 10.5],
        })
        result = normalize_columns(df, provider='generic')
        assert isinstance(result.index, pd.DatetimeIndex)
        assert result.index[0] < result.index[1]


class TestCleanDataFrame:
    def test_fill_pct_chg(self):
        df = pd.DataFrame({
            'open': [10.0, 11.0, 12.0],
            'high': [11.0, 12.0, 13.0],
            'low': [9.5, 10.5, 11.5],
            'close': [10.5, 11.5, 12.5],
            'volume': [1000, 1100, 1200],
            'amount': [10500, 12650, 15000],
        })
        result = clean_dataframe(df)
        assert 'pct_chg' in result.columns
        assert pd.isna(result['pct_chg'].iloc[0])  # first row: no previous close
        assert result['pct_chg'].iloc[1] > 0  # 10.5 -> 11.5 is positive

    def test_fill_zero_volume(self):
        df = pd.DataFrame({
            'open': [10.0, np.nan],
            'high': [11.0, np.nan],
            'low': [9.5, np.nan],
            'close': [10.5, np.nan],
            'volume': [0, 0],
            'amount': [0, 0],
        })
        result = clean_dataframe(df)
        # Only first row should remain (second has NaN in OHLC)
        assert len(result) == 1

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = clean_dataframe(df)
        assert result.empty

    def test_fill_zero_volume(self):
        df = pd.DataFrame({
            'open': [10.0, np.nan],
            'high': [11.0, np.nan],
            'low': [9.5, np.nan],
            'close': [10.5, np.nan],
            'volume': [0, 0],
            'amount': [0, 0],
        })
        result = clean_dataframe(df)
        # Only first row should remain (second has NaN in OHLC)
        assert len(result) == 1
        assert result['volume'].iloc[0] == 0


class TestCalculateStandardIndicators:
    def test_calculate_ma(self):
        n = 25
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=n),
            'open': [10.0] * n,
            'high': [11.0] * n,
            'low': [9.5] * n,
            'close': [10.5 + i * 0.1 for i in range(n)],
            'volume': [1000] * n,
            'amount': [10500] * n,
        })
        result = calculate_standard_indicators(df)
        assert 'ma5' in result.columns
        assert 'ma10' in result.columns
        assert 'ma20' in result.columns
        assert 'volume_ratio' in result.columns

    def test_volume_ratio(self):
        n = 20
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=n),
            'open': [10.0] * n,
            'high': [11.0] * n,
            'low': [9.5] * n,
            'close': [10.5] * n,
            'volume': [1000] * n,
            'amount': [10500] * n,
        })
        result = calculate_standard_indicators(df)
        # Volume 1000, avg over 5 = 1000, ratio = 1.0
        assert result['volume_ratio'].iloc[4] == 1.0  # first valid ratio (after 5-day warmup)

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = calculate_standard_indicators(df)
        assert result.empty
