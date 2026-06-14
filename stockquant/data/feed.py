# -*- coding: utf-8 -*-
"""F011 数据层抽象 — DataFeed ABC"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd

from stockquant.models.bar import BarData


class DataFeed(ABC):
    """
    数据源抽象基类。

    所有数据源实现此接口，确保策略代码与数据源解耦。
    """

    @abstractmethod
    def start(self):
        """启动数据源连接"""
        ...

    @abstractmethod
    def stop(self):
        """停止数据源连接"""
        ...

    @abstractmethod
    def __len__(self) -> int:
        """返回 K 线数据总条数"""
        ...

    @abstractmethod
    def __getitem__(self, index: int) -> BarData:
        """获取第 index 根 K 线"""
        ...

    @abstractmethod
    def get_dataframe(self) -> pd.DataFrame:
        """返回 DataFrame（用于分析/报表）"""
        ...

    @property
    @abstractmethod
    def symbol(self) -> str:
        ...

    @property
    @abstractmethod
    def timeframe(self) -> str:
        ...


class DataCache:
    """
    数据缓存层。

    首次请求时从数据源下载并缓存为 Parquet，
    后续请求从缓存读取，增量更新。
    """

    def __init__(self, cache_dir: str = "./.stockquant_cache"):
        self._cache_dir = cache_dir
        self._cache: Dict[str, pd.DataFrame] = {}

    def get(self, symbol: str, timeframe: str, start: str = "", end: str = "") -> pd.DataFrame:
        """
        获取缓存数据。

        如果缓存命中且数据完整，直接返回 DataFrame。
        否则返回空 DataFrame 触发数据源下载。
        """
        key = f"{symbol}:{timeframe}:{start}:{end}"

        if key in self._cache:
            df = self._cache[key]
            # 检查数据范围是否满足
            if start and df.index.min() >= pd.Timestamp(start):
                if end and df.index.max() <= pd.Timestamp(end):
                    return df.copy()
            # 部分命中：返回增量更新
            mask = pd.Series(True, index=df.index)
            if start:
                mask &= df.index >= pd.Timestamp(start)
            if end:
                mask &= df.index <= pd.Timestamp(end)
            return df[mask].copy() if mask.any() else pd.DataFrame()

        return pd.DataFrame()

    def put(self, key: str, df: pd.DataFrame):
        """将数据写入缓存"""
        self._cache[key] = df

    def invalidate(self, symbol: str, timeframe: str = ""):
        """清除缓存"""
        if timeframe:
            key = f"{symbol}:{timeframe}"
            self._cache.pop(key, None)
        else:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{symbol}:")]
            for k in keys_to_remove:
                self._cache.pop(k, None)

    def clear(self):
        """清除全部缓存"""
        self._cache.clear()

    @property
    def stats(self) -> dict:
        """缓存统计"""
        return {
            "entries": len(self._cache),
            "keys": list(self._cache.keys()),
        }
