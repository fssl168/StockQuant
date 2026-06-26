# -*- coding: utf-8 -*-
"""数据标准化 - 列名映射、清洗、通用指标计算"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

STANDARD_COLUMNS: list[str] = [
    "date", "open", "high", "low", "close", "volume", "amount", "pct_chg",
]

COLUMN_MAPPINGS: Dict[str, Dict[str, str]] = {
    "baostock": {
        "date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "amount": "amount",
    },
    "akshare": {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount",
    },
    "csv": {
        "timestamp": "date",
        "datetime": "date",
    },
    "yahoo": {
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
        "Adj Close": "adj_close",
    },
}

# 扩展映射：源列名 -> 标准列名的完整字典
_SOURCE_TO_STANDARD: Dict[str, str] = {}
for _mapping in COLUMN_MAPPINGS.values():
    _SOURCE_TO_STANDARD.update(_mapping)
del _mapping


# ---------------------------------------------------------------------------
# 核心函数
# ---------------------------------------------------------------------------

def normalize_columns(
    df: pd.DataFrame,
    provider: str = "generic",
    date_col: str = "date",
    index_col: Optional[str] = None,
) -> pd.DataFrame:
    """将不同数据源的列映射到 STANDARD_COLUMNS。

    * 根据 provider 选择预定义列映射，用户也可传入自定义 date_col。
    * 缺失的列以 NaN 填充。
    * 默认将 date 列设为 DataFrame index。
    """
    if df.empty:
        df = pd.DataFrame(columns=[date_col] + [
            c for c in STANDARD_COLUMNS if c != date_col
        ])
        return df

    mapping = COLUMN_MAPPINGS.get(provider, {})
    if not mapping:
        mapping = {
            col: STANDARD_COLUMNS[i]
            for i, col in enumerate(STANDARD_COLUMNS[: len(df.columns)])
            if col in df.columns
        }

    rename_map = {src: dst for src, dst in mapping.items() if src in df.columns}
    if rename_map:
        df = df.rename(columns=rename_map)

    for col in STANDARD_COLUMNS:
        if col not in df.columns:
            if col == date_col:
                df[col] = pd.to_datetime(df.get("date", pd.DataFrame()), errors="coerce")
            else:
                df[col] = pd.NA

    keep = [c for c in STANDARD_COLUMNS if c in df.columns]
    df = df[keep].copy()

    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    idx = index_col if index_col else date_col
    if idx in df.columns and idx != df.index.name:
        df = df.set_index(idx)
        df.index.name = "date"

    df = df.sort_index()
    return df


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """清洗 OHLCV DataFrame。

    * 丢弃 OHLC 全为 NaN 的行。
    * volume / amount 缺失时填 0。
    * 如果缺少 pct_chg，自动计算当日涨跌幅。
    * 确保数值列类型为 float。
    """
    if df.empty:
        return df.copy()

    df = df.copy()

    numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    ohlc_cols = ["open", "high", "low", "close"]
    ohlc_present = [c for c in ohlc_cols if c in df.columns]
    if ohlc_present:
        df = df[~df[ohlc_present].isna().all(axis=1)]

    if df.empty:
        return df

    for col in ("volume", "amount"):
        if col in df.columns:
            df[col] = df[col].fillna(0.0)

    if "pct_chg" not in df.columns and "close" in df.columns:
        prev_close = df["close"].shift(1)
        df["pct_chg"] = (df["close"] - prev_close) / prev_close * 100.0
        df["pct_chg"] = df["pct_chg"].replace([float("inf"), float("-inf")], pd.NA)

    if df.index.name == "date" or (not df.index.name and "date" in df.columns):
        try:
            df.index = pd.to_datetime(df.index)
        except (ValueError, TypeError):
            pass

    return df


def calculate_standard_indicators(
    df: pd.DataFrame,
    append: bool = True,
) -> pd.DataFrame:
    """计算通用技术指标并可选地追加到 DataFrame。

    计算的指标：
    * ma5 - 5 日简单移动平均
    * ma10 - 10 日简单移动平均
    * ma20 - 20 日简单移动平均
    * volume_ratio - 当日成交量 / 5 日均量
    """
    if df.empty or "close" not in df.columns:
        logger.warning("calculate_standard_indicators: empty or no close column")
        return df if append else {}

    df = df.copy()
    close = df["close"]
    volume = df.get("volume", pd.Series(0.0, index=df.index))

    indicators: Dict[str, pd.Series] = {
        "ma5": close.rolling(5).mean(),
        "ma10": close.rolling(10).mean(),
        "ma20": close.rolling(20).mean(),
    }

    ma5_vol = volume.rolling(5).mean()
    indicators["volume_ratio"] = volume / ma5_vol.replace(0, pd.NA)

    if append:
        for name, series in indicators.items():
            df[name] = series
        return df
    return indicators