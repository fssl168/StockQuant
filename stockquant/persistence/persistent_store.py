# -*- coding: utf-8 -*-
"""持久化存储包装器 — 用于替代内存字典存储"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from stockquant.persistence.repository import (
    get_backtest_task,
    save_backtest_task,
    list_backtest_tasks,
    delete_backtest_task,
    get_strategy,
    save_strategy,
    list_strategies,
    delete_strategy,
)


def _get_db_url():
    """获取数据库 URL"""
    return os.environ.get("DATABASE_URL", "sqlite:///./stockquant.db")


class BacktestTaskStore:
    """回测任务存储 — 模拟字典接口，底层使用数据库"""

    def __init__(self):
        self._db_url = _get_db_url()
        # 内存缓存
        self._cache: Dict[str, Any] = {}
        self._load_from_db()

    def _load_from_db(self):
        """从数据库加载数据到缓存"""
        try:
            tasks = list_backtest_tasks(self._db_url)
            for task in tasks:
                self._cache[task["id"]] = task
        except Exception:
            pass

    def __getitem__(self, key: str) -> Any:
        return self._cache.get(key)

    def __setitem__(self, key: str, value: Any):
        self._cache[key] = value
        # 异步保存到数据库
        try:
            status = value.get("status", "running")
            result = value.get("result")
            save_backtest_task(self._db_url, key, status, result)
        except Exception:
            pass

    def __delitem__(self, key: str):
        if key in self._cache:
            del self._cache[key]
            try:
                delete_backtest_task(self._db_url, key)
            except Exception:
                pass

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def get(self, key: str, default: Any = None) -> Any:
        return self._cache.get(key, default)

    def keys(self):
        return self._cache.keys()

    def values(self):
        return self._cache.values()

    def items(self):
        return self._cache.items()

    def __len__(self):
        return len(self._cache)

    def clear(self):
        self._cache.clear()


class StrategyStore:
    """策略存储 — 模拟字典接口，底层使用数据库"""

    def __init__(self):
        self._db_url = _get_db_url()
        # 内存缓存
        self._cache: Dict[str, Any] = {}
        self._load_from_db()

    def _load_from_db(self):
        """从数据库加载数据到缓存"""
        try:
            strategies = list_strategies(self._db_url)
            for strategy in strategies:
                self._cache[strategy["id"]] = strategy
        except Exception:
            pass

    def __getitem__(self, key: str) -> Any:
        return self._cache.get(key)

    def __setitem__(self, key: str, value: Any):
        self._cache[key] = value
        # 异步保存到数据库
        try:
            name = value.get("name", "")
            code = value.get("code", "")
            description = value.get("description")
            parameters = value.get("parameters")
            save_strategy(self._db_url, key, name, code, description, parameters)
        except Exception:
            pass

    def __delitem__(self, key: str):
        if key in self._cache:
            del self._cache[key]
            try:
                delete_strategy(self._db_url, key)
            except Exception:
                pass

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def get(self, key: str, default: Any = None) -> Any:
        return self._cache.get(key, default)

    def keys(self):
        return self._cache.keys()

    def values(self):
        return self._cache.values()

    def items(self):
        return self._cache.items()

    def __len__(self):
        return len(self._cache)

    def clear(self):
        self._cache.clear()