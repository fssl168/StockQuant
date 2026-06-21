# -*- coding: utf-8 -*-
"""F011 AkShare 数据源 — 实时和历史 A 股数据"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd

from stockquant.data.feed import DataFeed
from stockquant.models.bar import BarData

logger = logging.getLogger("stockquant.data")


class AkShareFeed(DataFeed):
    """AkShare 数据源。

    使用 akshare 库获取 A 股数据。

    用法:
        feed = AkShareFeed(
            symbols=["600519"],
            timeframe="1d",
            start="20200101",
            end="20241231",
        )
        cerebro.add_data(feed)

    支持的时间框架:
        - "1d": 日线
        - "1w": 周线
        - "1m": 月线
        - "5min", "15min", "30min", "60min": 分钟线
    """

    def __init__(self, symbols: List[str], timeframe: str = "1d",
                 start: str = "", end: str = "", cache_dir: Optional[str] = None):
        """
        Parameters
        ----------
        symbols : List[str]
            标的代码列表，如 ["600519", "000858"]（不需要 sh/sz 前缀）
        timeframe : str
            时间框架
        start : str
            开始日期 "YYYYMMDD"
        end : str
            结束日期 "YYYYMMDD"
        cache_dir : str or None
            缓存目录路径
        """
        self._symbols = symbols
        self._timeframe = timeframe
        self._start = start
        self._end = end
        self._cache_dir = cache_dir

        self._bars: dict[str, List[BarData]] = {}
        self._dataframes: dict[str, pd.DataFrame] = {}
        self._started = False

    def start(self):
        """启动时拉取数据"""
        logger.info(f"AkShareFeed: fetching data for {self._symbols} ({self._timeframe})")
        self._fetch_all()
        self._started = True

    def fetch(self, symbol: str, timeframe: str = "1d",
              start: str = "", end: str = "", days: int = 0) -> None:
        """按需加载单个标的的数据"""
        if symbol in self._dataframes and not self._dataframes[symbol].empty:
            return  # 已加载，直接返回
        from datetime import timedelta
        if days > 0:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")
        elif not start:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        else:
            start_date = start.replace("-", "")
        end_date = end.replace("-", "") if end else datetime.now().strftime("%Y%m%d")

        try:
            import akshare as ak
            # 转换 symbol 格式：sh600519 -> 600519
            sym = symbol[2:] if len(symbol) == 8 and symbol[:2] in ("sh", "sz") else symbol
            df = ak.stock_zh_a_hist(symbol=sym, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
            if df is not None and not df.empty:
                self._dataframes[symbol] = df
                logger.info(f"AkShareFeed: fetched {len(df)} rows for {symbol}")
        except Exception as e:
            logger.warning(f"AkShareFeed: failed to fetch {symbol}: {e}")

    def stop(self):
        self._started = False

    def _fetch_all(self):
        """拉取所有标的的数据"""
        try:
            import akshare as ak
        except ImportError:
            logger.error(
                "akshare package not installed. "
                "Install with: pip install akshare "
                "Or use CSVFeed for CSV-based backtesting."
            )
            return

        for symbol in self._symbols:
            try:
                bars = self._fetch_single(symbol)
                self._bars[symbol] = bars
                self._dataframes[symbol] = self._bars_to_df(symbol)
            except Exception as e:
                logger.error(f"AkShareFeed: failed to fetch {symbol}: {e}")
                self._bars[symbol] = []
                self._dataframes[symbol] = pd.DataFrame()

    def _fetch_single(self, symbol: str) -> List[BarData]:
        """拉取单个标的数据"""
        # 尝试缓存
        cached = self._read_cache(symbol)
        if cached is not None:
            return cached

        import akshare as ak

        timeframe_map = {
            "1d": "daily", "1w": "weekly", "1m": "monthly",
            "5min": "5", "15min": "15", "30min": "30", "60min": "60",
        }
        period = timeframe_map.get(self._timeframe, "daily")

        try:
            if period in ("5", "15", "30", "60"):
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period=period,
                    start_date=self._start.replace("-", ""),
                    end_date=self._end.replace("-", ""),
                    adjust="qfq",
                )
            else:
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period=period,
                    start_date=self._start or "",
                    end_date=self._end or "",
                    adjust="qfq",
                )
        except Exception as e:
            logger.warning(f"AkShareFeed: API call failed for {symbol}: {e}")
            return []

        bars = self._df_to_bars(df, symbol)

        # 写入缓存
        self._write_cache(symbol, bars)
        return bars

    @staticmethod
    def _df_to_bars(df: pd.DataFrame, symbol: str) -> List[BarData]:
        """将 AkShare DataFrame 转为 BarData 列表"""
        bars = []
        if df.empty:
            return bars

        # 标准化列名
        col_map = {}
        for col in df.columns:
            col_lower = col.lower().strip()
            if col_lower in ("日期", "date", "datetime"):
                col_map[col] = "date"
            elif col_lower in ("开盘", "open"):
                col_map[col] = "open"
            elif col_lower in ("最高", "high"):
                col_map[col] = "high"
            elif col_lower in ("最低", "low"):
                col_map[col] = "low"
            elif col_lower in ("收盘", "close"):
                col_map[col] = "close"
            elif col_lower in ("成交量", "volume"):
                col_map[col] = "volume"
            elif col_lower in ("成交额", "amount", "turnover"):
                col_map[col] = "turnover"

        df = df.rename(columns=col_map)

        for _, row in df.iterrows():
            try:
                date_str = str(row.get("date", ""))
                # 处理各种日期格式
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
                    try:
                        dt = datetime.strptime(date_str.strip(), fmt)
                        break
                    except ValueError:
                        continue
                else:
                    dt = pd.to_datetime(date_str).to_pydatetime()

                bar = BarData(
                    symbol=symbol,
                    datetime=dt,
                    open=float(row.get("open", 0)),
                    high=float(row.get("high", 0)),
                    low=float(row.get("low", 0)),
                    close=float(row.get("close", 0)),
                    volume=float(row.get("volume", 0)),
                    turnover=float(row.get("turnover", 0)),
                    adjust_flag="qfq",
                )
                bars.append(bar)
            except (ValueError, TypeError):
                continue

        return bars

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
                    volume=float(row.get("volume", 0)) if pd.notna(row.get("volume", 0)) else 0.0,
                    turnover=float(row.get("turnover", 0)) if pd.notna(row.get("turnover", 0)) else 0.0,
                )
                bars.append(bar)
            logger.info(f"AkShareFeed: loaded {len(bars)} bars from cache for {symbol}")
            return bars
        except Exception as e:
            logger.warning(f"AkShareFeed: cache read failed for {symbol}: {e}")
            return None

    def _write_cache(self, symbol: str, bars: List[BarData]):
        path = self._cache_path(symbol)
        if not path:
            return
        try:
            df = pd.DataFrame([b.__dict__ for b in bars])
            df.to_csv(path, index=False)
            logger.info(f"AkShareFeed: cached {len(bars)} bars for {symbol}")
        except Exception as e:
            logger.warning(f"AkShareFeed: cache write failed for {symbol}: {e}")

    # ------------------------------------------------------------------
    # DataFeed ABC
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        first = self._symbols[0] if self._symbols else None
        return len(self._bars.get(first, []))

    def __getitem__(self, key):
        if isinstance(key, int):
            first = self._symbols[0] if self._symbols else None
            if not first:
                raise IndexError("No symbols")
            bars = self._bars.get(first, [])
            if key < 0:
                key = len(bars) + key
            return bars[key]
        elif isinstance(key, str):
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
        dfs = [df for df in self._dataframes.values() if not df.empty]
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
