# -*- coding: utf-8 -*-
"""持久化存储包装器  用于替代内存字典存储"""

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
    save_collect_task,
    list_collect_tasks,
    delete_collect_task,
    save_optimize_task,
    list_optimize_tasks,
    delete_optimize_task,
    save_comparison_history,
    list_comparison_history,
    save_pending_order,
    list_pending_orders,
    delete_pending_order,
    save_order_audit,
    list_order_audits,
)


def _get_db_url():
    """获取数据库 URL"""
    return os.environ.get("DATABASE_URL", "sqlite:///./stockquant.db")


class BacktestTaskStore:
    """回测任务存储  模拟字典接口，底层使用数据库"""

    def __init__(self):
        self._db_url = _get_db_url()
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
    """策略存储  模拟字典接口，底层使用数据库"""

    def __init__(self):
        self._db_url = _get_db_url()
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


class CollectTaskStore:
    """数据收集任务存储  模拟字典接口，底层使用数据库"""

    def __init__(self):
        self._db_url = _get_db_url()
        self._cache: Dict[str, Any] = {}
        self._load_from_db()

    def _load_from_db(self):
        try:
            tasks = list_collect_tasks(self._db_url)
            for task in tasks:
                self._cache[task["id"]] = task
        except Exception:
            pass

    def __setitem__(self, key: str, value: Any):
        self._cache[key] = value
        try:
            status = value.get("status", "running")
            progress = value.get("progress", 0.0)
            save_collect_task(self._db_url, key, status, progress)
        except Exception:
            pass

    def __getitem__(self, key: str) -> Any:
        return self._cache.get(key)

    def __delitem__(self, key: str):
        if key in self._cache:
            del self._cache[key]
            try:
                delete_collect_task(self._db_url, key)
            except Exception:
                pass

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def get(self, key: str, default: Any = None) -> Any:
        return self._cache.get(key, default)

    def values(self):
        return self._cache.values()

    def __len__(self):
        return len(self._cache)


class OptimizeTaskStore:
    """参数优化任务存储  模拟字典接口，底层使用数据库"""

    def __init__(self):
        self._db_url = _get_db_url()
        self._cache: Dict[str, Any] = {}
        self._load_from_db()

    def _load_from_db(self):
        try:
            tasks = list_optimize_tasks(self._db_url)
            for task in tasks:
                self._cache[task["id"]] = task
        except Exception:
            pass

    def __setitem__(self, key: str, value: Any):
        self._cache[key] = value
        try:
            status = value.get("status", "running")
            result = value.get("result")
            save_optimize_task(self._db_url, key, status, result)
        except Exception:
            pass

    def __getitem__(self, key: str) -> Any:
        return self._cache.get(key)

    def __delitem__(self, key: str):
        if key in self._cache:
            del self._cache[key]
            try:
                delete_optimize_task(self._db_url, key)
            except Exception:
                pass

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def get(self, key: str, default: Any = None) -> Any:
        return self._cache.get(key, default)

    def values(self):
        return self._cache.values()

    def __len__(self):
        return len(self._cache)


class ComparisonHistoryStore:
    """策略对比历史存储  模拟列表接口，底层使用数据库"""

    def __init__(self):
        self._db_url = _get_db_url()
        self._cache: List[Dict[str, Any]] = []
        self._load_from_db()

    def _load_from_db(self):
        try:
            self._cache = list_comparison_history(self._db_url)
        except Exception:
            pass

    def append(self, value: Dict[str, Any]):
        self._cache.append(value)
        try:
            import uuid
            history_id = str(uuid.uuid4())
            strategy_ids = value.get("strategy_ids", "")
            result = value.get("result")
            save_comparison_history(self._db_url, history_id, strategy_ids, result)
        except Exception:
            pass

    def __getitem__(self, index: int) -> Any:
        return self._cache[index]

    def __len__(self):
        return len(self._cache)

    def __iter__(self):
        return iter(self._cache)

    def reversed(self):
        return reversed(self._cache)

    def clear(self):
        self._cache.clear()


class PendingOrderStore:
    """待处理订单存储  模拟字典接口，底层使用数据库"""

    def __init__(self):
        self._db_url = _get_db_url()
        self._cache: Dict[str, Any] = {}
        self._load_from_db()

    def _load_from_db(self):
        try:
            orders = list_pending_orders(self._db_url)
            for order in orders:
                self._cache[order["id"]] = order
        except Exception:
            pass

    def __setitem__(self, key: str, value: Any):
        self._cache[key] = value
        try:
            symbol = value.get("symbol", "")
            type = value.get("type", "buy")
            price = value.get("price", 0.0)
            quantity = value.get("quantity", 0)
            status = value.get("status", "pending")
            save_pending_order(self._db_url, key, symbol, type, price, quantity, status)
        except Exception:
            pass

    def __getitem__(self, key: str) -> Any:
        return self._cache.get(key)

    def __delitem__(self, key: str):
        if key in self._cache:
            del self._cache[key]
            try:
                delete_pending_order(self._db_url, key)
            except Exception:
                pass

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def get(self, key: str, default: Any = None) -> Any:
        return self._cache.get(key, default)

    def values(self):
        return self._cache.values()

    def items(self):
        return self._cache.items()

    def __len__(self):
        return len(self._cache)


class OrderAuditStore:
    """订单审计存储  模拟字典接口，底层使用数据库"""

    def __init__(self):
        self._db_url = _get_db_url()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_from_db()

    def _load_from_db(self):
        try:
            audits = list_order_audits(self._db_url)
            for audit in audits:
                if audit["order_id"] not in self._cache:
                    self._cache[audit["order_id"]] = {}
                self._cache[audit["order_id"]][audit["id"]] = audit
        except Exception:
            pass

    def __setitem__(self, key: str, value: Any):
        self._cache[key] = value
        try:
            import uuid
            audit_id = str(uuid.uuid4())
            order_id = key
            action = value.get("action", "")
            details = value.get("details")
            save_order_audit(self._db_url, audit_id, order_id, action, details)
        except Exception:
            pass

    def __getitem__(self, key: str) -> Any:
        return self._cache.get(key)

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def get(self, key: str, default: Any = None) -> Any:
        return self._cache.get(key, default)

    def values(self):
        return self._cache.values()

    def __len__(self):
        return len(self._cache)
