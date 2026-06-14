# -*- coding: utf-8 -*-
"""F011 数据源提供者"""

from stockquant.data.providers.baostock_feed import BaoStockFeed
from stockquant.data.providers.csv_feed import CSVFeed

__all__ = ["BaoStockFeed", "CSVFeed"]
