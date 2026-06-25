# -*- coding: utf-8 -*-
'''Unified data fetcher protocol - abstract base for all data providers'''

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class DataQualityReport:
    '''Data quality assessment result'''
    symbol: str = ''
    is_valid: bool = True
    row_count: int = 0
    date_range: tuple = field(default_factory=tuple)
    missing_values: Dict[str, int] = field(default_factory=dict)
    duplicates: int = 0
    anomalies: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class StandardKlineSchema:
    '''Standard column names for kline data'''
    DATE = 'date'
    OPEN = 'open'
    HIGH = 'high'
    LOW = 'low'
    CLOSE = 'close'
    VOLUME = 'volume'
    TURNOVER = 'turnover'
    AMOUNT = 'amount'


class DataFetcherProtocol(ABC):
    '''Abstract base class for all data providers.
    
    All data providers must implement these methods to ensure
    consistent interface across different data sources.
    '''
    
    @abstractmethod
    def get_name(self) -> str:
        '''Return provider name (e.g., baostock, alphafeed)'''
        ...
    
    @abstractmethod
    def fetch(
        self,
        symbol: str,
        timeframe: str = '1d',
        start: str = '',
        end: str = '',
        **kwargs: Any,
    ) -> Optional[pd.DataFrame]:
        '''Fetch kline data for a symbol.
        
        Returns standardized DataFrame with columns:
        date, open, high, low, close, volume, turnover
        '''
        ...
    
    @abstractmethod
    def get_health(self) -> Dict[str, Any]:
        '''Check provider health and return status info'''
        ...
    
    def validate(self, df: pd.DataFrame, symbol: str = '') -> DataQualityReport:
        '''Validate data quality. Default implementation provides basic checks.'''
        report = DataQualityReport(symbol=symbol)
        
        if df is None or df.empty:
            report.is_valid = False
            report.warnings.append('Empty or None dataframe')
            return report
        
        report.row_count = len(df)
        
        # Check required columns
        required_cols = {StandardKlineSchema.OPEN, StandardKlineSchema.HIGH, 
                        StandardKlineSchema.LOW, StandardKlineSchema.CLOSE,
                        StandardKlineSchema.VOLUME}
        actual_cols = set(df.columns.str.lower()) if df.columns is not None else set()
        missing_cols = required_cols - actual_cols
        if missing_cols:
            report.is_valid = False
            report.warnings.append(f'Missing columns: {missing_cols}')
        
        # Check for NaN values
        for col in required_cols:
            col_lower = col.lower()
            if col_lower in df.columns:
                nan_count = int(df[col_lower].isna().sum())
                if nan_count > 0:
                    report.missing_values[col] = nan_count
        
        # Check for duplicates
        report.duplicates = df.duplicated(subset=[StandardKlineSchema.DATE]).sum() if StandardKlineSchema.DATE in df.columns else 0
        
        return report


class DataSourceResolver:
    '''Resolves and manages data provider instances.
    
    Handles provider selection based on configuration and availability.
    '''
    
    @staticmethod
    def resolve(provider_name: Optional[str] = None) -> List[Tuple[str, DataFetcherProtocol]]:
        '''Resolve available data providers based on configuration.'''
        from stockquant.config import get_config, DataProvider
        from pathlib import Path
        
        config = get_config()
        preferred = provider_name or config.data_provider.source
        providers: List[DataFetcherProtocol] = []
        cache_dir = str(Path.home() / '.stockquant' / 'data')
        
        # Try preferred provider first
        if preferred == DataProvider.ALPHAFeed:
            try:
                from stockquant.data.providers.alphafeed_feed import AlphaFeedFeed
                providers.append(("alphafeed", AlphaFeedFeed(
                    symbols=[], timeframe='1d',
                    api_key=config.data_provider.alphafeed_key or None,
                    cache_dir=cache_dir,
                )))
            except Exception as e:
                import logging
                logging.getLogger('stockquant.data').debug(f'AlphaFeed unavailable: {e}')
        
        if preferred != DataProvider.BAOSTOCK:
            try:
                from stockquant.data.providers.baostock_feed import BaoStockFeed
                providers.append(("baostock", BaoStockFeed(symbols=[])))
            except Exception as e:
                import logging
                logging.getLogger('stockquant.data').debug(f'BaoStock unavailable: {e}')
        
        try:
            from stockquant.data.providers.sqlite_feed import SQLiteFeed
            providers.append(("sqlite", SQLiteFeed()))
        except Exception as e:
            import logging
            logging.getLogger('stockquant.data').debug(f'SQLiteFeed unavailable: {e}')
        
        try:
            from stockquant.data.providers.csv_feed import CSVFeed
            csv_dir = config.data_provider.csv.directory
            if csv_dir:
                providers.append(("csv", CSVFeed(directory=csv_dir)))
        except Exception as e:
            import logging
            logging.getLogger('stockquant.data').debug(f'CSVFeed unavailable: {e}')
        
        if not providers:
            import logging
            logging.getLogger('stockquant.data').warning('No data providers available')
        return providers
