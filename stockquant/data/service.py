# -*- coding: utf-8 -*-
"""DataService - 统一数据服务层"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from stockquant.config import DataProvider, get_config
from stockquant.data.protocol import DataSourceResolver

logger = logging.getLogger("stockquant.data.service")


class KlineResult:
    """K线查询结果"""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
        data: pd.DataFrame,
        source: str,
        cached: bool = False,
        error: str = "",
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.start = start
        self.end = end
        self.data = data
        self.source = source
        self.cached = cached
        self.error = error

    @property
    def empty(self) -> bool:
        return self.data is None or self.data.empty

    @property
    def count(self) -> int:
        return len(self.data) if self.data is not None else 0

    def to_list(self) -> List[Dict[str, Any]]:
        if self.empty:
            return []
        rows = []
        from datetime import datetime as _dt

        for _, row in self.data.iterrows():
            dv = row.get("datetime", row.get("date", ""))
            if hasattr(dv, "strftime"):
                dv = dv.strftime("%Y-%m-%d")
            elif isinstance(dv, (int, float)):
                if dv > 1e12:
                    dv = _dt.fromtimestamp(dv / 1000).strftime("%Y-%m-%d")
                else:
                    dv = _dt.fromtimestamp(dv).strftime("%Y-%m-%d")
            elif isinstance(dv, str) and dv.isdigit() and "date" in row.index:
                dv = row["date"]
            rows.append({
                "date": str(dv),
                "open": round(float(row.get("open", 0)), 2),
                "high": round(float(row.get("high", 0)), 2),
                "low": round(float(row.get("low", 0)), 2),
                "close": round(float(row.get("close", 0)), 2),
                "volume": int(row.get("volume", 0)),
                "turnover": round(float(row.get("turnover", 0)), 2),
                "amount": round(float(row.get("amount", row.get("turnover", 0))), 2),
            })
        return rows


class DataCache:
    """内存+文件K线缓存"""

    def __init__(self, cache_dir: str = ""):
        self._mem_cache: Dict[str, Tuple[pd.DataFrame, float]] = {}
        self._mem_ttl = 300
        if not cache_dir:
            cache_dir = str(Path.home() / ".stockquant" / "data")
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, symbol: str, timeframe: str, start: str, end: str) -> str:
        return f"{symbol}:{timeframe}:{start}:{end}"

    def get(
        self,
        symbol: str,
        timeframe: str,
        start: str = "",
        end: str = "",
    ) -> pd.DataFrame:
        key = self._key(symbol, timeframe, start, end)
        if key in self._mem_cache:
            df, ts = self._mem_cache[key]
            if time.time() - ts < self._mem_ttl:
                return df.copy()
            self._mem_cache.pop(key, None)
        df = self._load_from_file(symbol, timeframe, start, end)
        if df is not None and not df.empty:
            self._mem_cache[key] = (df, time.time())
            return df.copy()
        return pd.DataFrame()

    def put(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
        df: pd.DataFrame,
    ):
        if df.empty:
            return
        key = self._key(symbol, timeframe, start, end)
        self._mem_cache[key] = (df, time.time())
        try:
            path = self._cache_dir / f"{key}.csv"
            df.to_csv(path)
        except Exception as e:
            logger.warning("Cache write failed: %s", e)

    def invalidate(self, symbol: str, timeframe: str = ""):
        if timeframe:
            prefix = f"{symbol}:{timeframe}:"
            keys_to_remove = [k for k in self._mem_cache if k.startswith(prefix)]
        else:
            prefix = f"{symbol}:"
            keys_to_remove = [k for k in self._mem_cache if k.startswith(prefix)]
        for k in keys_to_remove:
            self._mem_cache.pop(k, None)
        try:
            pat = f"{symbol}_{timeframe}_*" if timeframe else f"{symbol}_*"
            for f in self._cache_dir.glob(pat):
                f.unlink(missing_ok=True)
        except Exception:
            pass

    def clear(self):
        self._mem_cache.clear()
        try:
            for f in self._cache_dir.glob("*"):
                f.unlink(missing_ok=True)
        except Exception:
            pass

    def stats(self) -> Dict[str, Any]:
        return {
            "memory_entries": len(self._mem_cache),
            "cache_dir": str(self._cache_dir),
            "file_count": len(list(self._cache_dir.glob("*"))),
            "total_size_mb": round(
                sum(f.stat().st_size for f in self._cache_dir.glob("*") if f.is_file())
                / (1024 * 1024),
                2,
            ),
        }

    def _load_from_file(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
    ) -> Optional[pd.DataFrame]:
        patterns = [f"{symbol}_{timeframe}*.csv", f"{symbol}_*.csv"]
        for pat in patterns:
            for f in self._cache_dir.glob(pat):
                try:
                    df = pd.read_csv(f, parse_dates=True, index_col=0)
                    if df.empty:
                        continue
                    if start and not df.index.min() >= pd.Timestamp(start):
                        continue
                    if end and not df.index.max() <= pd.Timestamp(end):
                        continue
                    return df
                except Exception:
                    continue
        return None


class DataService:
    """统一数据服务层"""

    def __init__(self, cache: Optional[DataCache] = None):
        self.cache = cache or DataCache()

    def get_kline(
        self,
        symbol: str,
        timeframe: str = "1d",
        start: str = "",
        end: str = "",
        provider: Optional[DataProvider] = None,
    ) -> KlineResult:
        logger.debug("DataService.get_kline: %s %s %s/%s", symbol, timeframe, start, end)
        cached_df = self.cache.get(symbol, timeframe, start, end)
        if not cached_df.empty:
            return KlineResult(
                symbol, timeframe, start, end, cached_df, source="cache", cached=True
            )

        # 使用 protocol.py 中的 DataSourceResolver
        feeds = DataSourceResolver.resolve(str(provider.value) if provider else None)
        last_error = ""
        for name, feed in feeds:
            try:
                df = self._fetch_from_feed(feed, symbol, timeframe, start, end)
                if df is not None and not df.empty:
                    self.cache.put(symbol, timeframe, start, end, df)
                    logger.info("Fetched %d bars for %s from %s", len(df), symbol, name)
                    return KlineResult(
                        symbol, timeframe, start, end, df, source=name, cached=False
                    )
            except Exception as e:
                last_error = str(e)
                logger.warning("Provider %s failed for %s: %s", name, symbol, e)

        return KlineResult(
            symbol, timeframe, start, end, pd.DataFrame(), source="none", error=last_error
        )

    def _fetch_from_feed(
        self, feed, symbol: str, timeframe: str, start: str, end: str
    ) -> Optional[pd.DataFrame]:
        if hasattr(feed, "get_dataframe"):
            if hasattr(feed, "symbols") and feed.symbols:
                return feed.get_dataframe()
            else:
                return feed.get_dataframe(symbol)
        if hasattr(feed, "fetch"):
            feed.fetch(symbol, timeframe, start, end)
            return feed.get_dataframe() if hasattr(feed, "get_dataframe") else None
        return None

    def get_multiple_klines(
        self,
        symbols: List[str],
        timeframe: str = "1d",
        start: str = "",
        end: str = "",
    ) -> Dict[str, KlineResult]:
        return {s: self.get_kline(s, timeframe, start, end) for s in symbols}

    def get_health(self) -> List[Dict[str, Any]]:
        result = []
        for name, feed in DataSourceResolver.resolve():
            healthy = True
            error = ""
            try:
                test_df = self.get_kline(
                    "sh600519", timeframe="1d", start="2024-01-01", end="2024-01-05"
                )
                if test_df.empty and name != "cache":
                    healthy = False
                    error = "test fetch returned empty"
            except Exception as e:
                healthy = False
                error = str(e)
            result.append(
                {
                    "provider": name,
                    "healthy": healthy,
                    "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "error": error,
                }
            )
        return result

    def refresh_kline(self, symbol: str, timeframe: str = "1d") -> KlineResult:
        self.cache.invalidate(symbol, timeframe)
        return self.get_kline(symbol, timeframe)

    @property
    def _cache_dir(self) -> Path:
        return self.cache._cache_dir

    def upload_csv(self, content: bytes, filename: str) -> Dict[str, Any]:
        import pandas as _pd

        required = {"date", "open", "high", "low", "close", "volume"}
        try:
            df = _pd.read_csv(_pd.io.common.BytesIO(content))
            df.columns = df.columns.str.lower()
            missing = required - set(df.columns)
            if missing:
                return {
                    "success": False,
                    "error": f"CSV missing columns: {', '.join(sorted(missing))}",
                }
            symbols = []
            if "symbol" in df.columns:
                symbols = df["symbol"].unique().tolist()
                for sym in symbols:
                    sym_df = df[df["symbol"] == sym].sort_values("date")
                    path = self._cache_dir / f"{sym}_{filename}"
                    sym_df.to_csv(path, index=False)
            else:
                path = self._cache_dir / filename
                df.sort_values("date").to_csv(path, index=False)
            return {
                "success": True,
                "filename": filename,
                "rows": len(df),
                "symbols": symbols,
                "columns": df.columns.tolist(),
            }
        except Exception as e:
            logger.error("CSV upload failed: %s", e, exc_info=True)
            return {"success": False, "error": str(e)}