# -*- coding: utf-8 -*-
"""F011 数据源提供者"""

from stockquant.data.providers.baostock_feed import BaoStockFeed
from stockquant.data.providers.csv_feed import CSVFeed
from stockquant.data.providers.parquet_feed import ParquetFeed
from stockquant.data.providers.sqlite_feed import SQLiteFeed
from stockquant.data.providers.alphafeed_feed import AlphaFeedFeed
from stockquant.data.standardize import (
    STANDARD_COLUMNS,
    normalize_columns,
    clean_dataframe,
    calculate_standard_indicators,
)

# 向后兼容: AkShareFeed 现在是 AlphaFeedFeed 的别名
AkShareFeed = AlphaFeedFeed

__all__ = [
    "BaoStockFeed",
    "CSVFeed",
    "ParquetFeed",
    "SQLiteFeed",
    "AlphaFeedFeed",
    "AkShareFeed",
    "STANDARD_COLUMNS",
    "normalize_columns",
    "clean_dataframe",
    "calculate_standard_indicators",
]
