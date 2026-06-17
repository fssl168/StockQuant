# -*- coding: utf-8 -*-
"""F011 AlphaFeed 数据源 — 实时和历史 A 股数据

AlphaFeed 是专业级 A 股数据服务，提供高质量的历史和实时行情数据。

SDK 安装:
    pip install alphafeed

配置:
    环境变量 ALPHAFEED_KEY 设置 API Key

如未安装或未配置 API Key，将降级为 AkShare 数据源。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd

from stockquant.data.feed import DataFeed
from stockquant.models.bar import BarData

logger = logging.getLogger("stockquant.data")

# AlphaFeed SDK 可选导入
_ALPHAFEED_AVAILABLE = False
try:
    from alphafeed import AlphaFeed as _AlphaFeedClient
    _ALPHAFEED_AVAILABLE = True
except ImportError:
    logger.info("alphafeed SDK 未安装，AlphaFeed 数据源不可用")


def _get_api_key() -> str:
    """从环境变量获取 AlphaFeed API Key"""
    return os.environ.get("ALPHAFEED_KEY", "")


class AlphaFeedFeed(DataFeed):
    """AlphaFeed 数据源。

    使用 alphafeed SDK 获取 A 股数据，支持日线/分钟线/周线/月线。

    用法:
        feed = AlphaFeedFeed(
            symbols=["600519"],
            timeframe="1d",
            start="20200101",
            end="20241231",
        )
        cerebro.add_data(feed)

    支持的时间框架:
        - "1d": 日线
        - "1w": 周线
        - "1M": 月线
        - "1m", "5m", "15m", "30m", "60m": 分钟线

    标的代码格式: AlphaFeed 使用 "代码.交易所" 格式
        - 上海: "600000.SH"
        - 深圳: "000001.SZ"
        - 也支持纯数字格式 "600000"，SDK 自动补全
    """

    # 时间框架映射: 内部 → AlphaFeed Period
    _PERIOD_MAP = {
        "1d": "1d", "1w": "1w", "1M": "1M", "1m": "1m",
        "5m": "5m", "15m": "15m", "30m": "30m", "60m": "60m",
        # 兼容旧格式
        "daily": "1d", "weekly": "1w", "monthly": "1M",
        "5min": "5m", "15min": "15m", "30min": "30m", "60min": "60m",
    }

    def __init__(self, symbols: List[str], timeframe: str = "1d",
                 start: str = "", end: str = "", cache_dir: Optional[str] = None,
                 api_key: Optional[str] = None, adjust: str = "forward"):
        """
        Parameters
        ----------
        symbols : List[str]
            标的代码列表，如 ["600519", "000858"] 或 ["600000.SH"]
        timeframe : str
            时间框架
        start : str
            开始日期 "YYYYMMDD" 或 "YYYY-MM-DD"
        end : str
            结束日期 "YYYYMMDD" 或 "YYYY-MM-DD"
        cache_dir : str or None
            缓存目录路径
        api_key : str or None
            AlphaFeed API Key，默认从环境变量 ALPHAFEED_KEY 读取
        adjust : str
            复权类型: "forward"(前复权), "backward"(后复权), "none"(不复权)
        """
        self._symbols = symbols
        self._timeframe = timeframe
        self._start = start
        self._end = end
        self._cache_dir = cache_dir
        self._adjust = adjust
        self._api_key = api_key or _get_api_key()
        self._client = None

        self._bars: dict[str, List[BarData]] = {}
        self._dataframes: dict[str, pd.DataFrame] = {}
        self._started = False

        # 初始化 AlphaFeed 客户端
        if _ALPHAFEED_AVAILABLE and self._api_key:
            try:
                self._client = _AlphaFeedClient(api_key=self._api_key)
                logger.info("AlphaFeed 客户端初始化成功")
            except Exception as e:
                logger.warning("AlphaFeed 客户端初始化失败: %s，降级为 AkShare", e)
                self._client = None

    def start(self):
        """启动时拉取数据"""
        logger.info(f"AlphaFeedFeed: fetching data for {self._symbols} ({self._timeframe})")
        self._fetch_all()
        self._started = True

    def stop(self):
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        self._started = False

    def _fetch_all(self):
        """拉取所有标的的数据"""
        if self._client is None:
            # 降级到 AkShare
            logger.warning("AlphaFeed 不可用，降级为 AkShare 数据源")
            self._fetch_all_akshare()
            return

        for symbol in self._symbols:
            try:
                bars = self._fetch_single(symbol)
                self._bars[symbol] = bars
                self._dataframes[symbol] = self._bars_to_df(symbol)
            except Exception as e:
                logger.error(f"AlphaFeedFeed: failed to fetch {symbol}: {e}")
                self._bars[symbol] = []
                self._dataframes[symbol] = pd.DataFrame()

    def _fetch_single(self, symbol: str) -> List[BarData]:
        """拉取单个标的数据"""
        # 尝试缓存
        cached = self._read_cache(symbol)
        if cached is not None:
            return cached

        # 标的代码格式转换: "600519" → "600519.SH" (AlphaFeed 格式)
        af_symbol = self._normalize_symbol(symbol)

        # 时间框架映射
        period = self._PERIOD_MAP.get(self._timeframe, "1d")

        # 时间参数
        kwargs = {}
        if self._start:
            start_str = self._start.replace("-", "")
            kwargs["start_time"] = self._date_to_timestamp(start_str)
        if self._end:
            end_str = self._end.replace("-", "")
            kwargs["end_time"] = self._date_to_timestamp(end_str, end_of_day=True)

        try:
            df = self._client.klines.get(
                af_symbol,
                period=period,
                adjust=self._adjust,
                to_dataframe=True,
                **kwargs,
            )
        except Exception as e:
            logger.warning(f"AlphaFeedFeed: API call failed for {symbol}: {e}")
            return []

        bars = self._df_to_bars(df, symbol)

        # 写入缓存
        self._write_cache(symbol, bars)
        return bars

    def _fetch_all_akshare(self):
        """降级: 使用 AkShare 拉取数据"""
        try:
            import akshare as ak
        except ImportError:
            logger.error("AlphaFeed 和 AkShare 均不可用，无法获取数据")
            for symbol in self._symbols:
                self._bars[symbol] = []
                self._dataframes[symbol] = pd.DataFrame()
            return

        for symbol in self._symbols:
            try:
                bars = self._fetch_single_akshare(symbol)
                self._bars[symbol] = bars
                self._dataframes[symbol] = self._bars_to_df(symbol)
            except Exception as e:
                logger.error(f"AkShare fallback: failed to fetch {symbol}: {e}")
                self._bars[symbol] = []
                self._dataframes[symbol] = pd.DataFrame()

    def _fetch_single_akshare(self, symbol: str) -> List[BarData]:
        """降级: 使用 AkShare 拉取单个标的"""
        cached = self._read_cache(symbol)
        if cached is not None:
            return cached

        import akshare as ak

        timeframe_map = {
            "1d": "daily", "1w": "weekly", "1M": "monthly", "1m": "monthly",
            "5m": "5", "15m": "15", "30m": "30", "60m": "60",
            "5min": "5", "15min": "15", "30min": "30", "60min": "60",
        }
        period = timeframe_map.get(self._timeframe, "daily")

        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=self._start.replace("-", "") if self._start else "",
                end_date=self._end.replace("-", "") if self._end else "",
                adjust="qfq",
            )
        except Exception as e:
            logger.warning(f"AkShare fallback: API call failed for {symbol}: {e}")
            return []

        bars = self._df_to_bars(df, symbol)
        self._write_cache(symbol, bars)
        return bars

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """将标的代码转为 AlphaFeed 格式

        "600519" → "600519.SH"
        "000858" → "000858.SZ"
        "600000.SH" → "600000.SH" (已符合格式)
        """
        if "." in symbol:
            return symbol

        # 根据代码规则判断交易所
        if symbol.startswith(("6", "5", "9")):
            return f"{symbol}.SH"  # 上海
        elif symbol.startswith(("0", "3", "1")):
            return f"{symbol}.SZ"  # 深圳
        else:
            return symbol  # 无法判断，原样返回

    @staticmethod
    def _date_to_timestamp(date_str: str, end_of_day: bool = False) -> int:
        """将日期字符串转为 Unix 时间戳（毫秒）"""
        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(date_str, fmt)
                if end_of_day:
                    dt = dt.replace(hour=23, minute=59, second=59)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue
        return 0

    @staticmethod
    def _df_to_bars(df: pd.DataFrame, symbol: str) -> List[BarData]:
        """将 DataFrame 转为 BarData 列表

        兼容 AlphaFeed 和 AkShare 两种列名格式。
        """
        bars = []
        if df is None or df.empty:
            return bars

        # 标准化列名 (兼容 AlphaFeed 英文列名 + AkShare 中文列名)
        col_map = {}
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if col_lower in ("日期", "date", "datetime", "time", "timestamp"):
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
                date_val = row.get("date", "")
                if isinstance(date_val, (int, float)):
                    # AlphaFeed 返回时间戳
                    dt = datetime.fromtimestamp(date_val / 1000)
                elif isinstance(date_val, pd.Timestamp):
                    dt = date_val.to_pydatetime()
                else:
                    date_str = str(date_val)
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
                    adjust_flag="forward",
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
            logger.info(f"AlphaFeedFeed: loaded {len(bars)} bars from cache for {symbol}")
            return bars
        except Exception as e:
            logger.warning(f"AlphaFeedFeed: cache read failed for {symbol}: {e}")
            return None

    def _write_cache(self, symbol: str, bars: List[BarData]):
        path = self._cache_path(symbol)
        if not path:
            return
        try:
            df = pd.DataFrame([b.__dict__ for b in bars])
            df.to_csv(path, index=False)
            logger.info(f"AlphaFeedFeed: cached {len(bars)} bars for {symbol}")
        except Exception as e:
            logger.warning(f"AlphaFeedFeed: cache write failed for {symbol}: {e}")

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
