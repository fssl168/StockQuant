# -*- coding: utf-8 -*-
"""持久化存储包装器 — 用于替代内存字典存储。

DEPRECATED: 这些 Store 类是仓储层合并（Phase 5）的中间产物。
新的代码应直接使用 repository_v2.py 中的 Repository 类（通过 Repository.instance()）。

Store 类通过 __setitem__/__delitem__ 自动持久化到数据库，
同时维护 _cache 内存缓存作为性能优化。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import sessionmaker

from stockquant.persistence.repository_v2 import Repository
# Repository 类的 save_strategy/get_strategy/list_strategies 签名与 repository.py 不同
# （engine_url 位置不同），直接从 repository.py 导入以保持 Store 类调用兼容
from stockquant.persistence.repository import (
    save_strategy,
    list_strategies,
    delete_strategy,
)
from stockquant.persistence.models import (
    Notification as NotificationModel,
    get_engine,
)

_repo = Repository.instance()

# 以下函数通过 Repository.__getattr__ 委托到 repository.py 模块级函数
get_backtest_task = _repo.get_backtest_task
save_backtest_task = _repo.save_backtest_task
list_backtest_tasks = _repo.list_backtest_tasks
delete_backtest_task = _repo.delete_backtest_task
save_collect_task = _repo.save_collect_task
list_collect_tasks = _repo.list_collect_tasks
delete_collect_task = _repo.delete_collect_task
save_optimize_task = _repo.save_optimize_task
list_optimize_tasks = _repo.list_optimize_tasks
delete_optimize_task = _repo.delete_optimize_task
save_comparison_history = _repo.save_comparison_history
list_comparison_history = _repo.list_comparison_history
save_order_audit = _repo.save_order_audit
list_order_audits = _repo.list_order_audits
delete_order_audit = _repo.delete_order_audit
list_notifications = _repo.list_notifications
delete_notification = _repo.delete_notification
list_monitor_alerts = _repo.list_monitor_alerts
save_monitor_alert = _repo.save_monitor_alert
save_scheduler_task = _repo.save_scheduler_task
list_scheduler_tasks = _repo.list_scheduler_tasks
delete_scheduler_task = _repo.delete_scheduler_task

logger = logging.getLogger(__name__)


def _get_db_url():
    """获取数据库 URL"""
    return os.environ.get("DATABASE_URL", "sqlite:///./stockquant.db")


class BacktestTaskStore:
    """[DEPRECATED] 回测任务存储 — 使用 repository.save_backtest_task/list_backtest_tasks 替代"""

    def __init__(self, user_id: Optional[str] = None):
        self._db_url = _get_db_url()
        self._user_id = user_id
        self._cache: Dict[str, Any] = {}
        self._load_from_db()

    def _load_from_db(self):
        """从数据库加载数据到缓存"""
        try:
            tasks = list_backtest_tasks(self._db_url, self._user_id)
            for task in tasks:
                # 将 result 中保存的完整数据合并到顶层
                result_data = task.get("result")
                if isinstance(result_data, str):
                    try:
                        result_data = json.loads(result_data)
                    except (json.JSONDecodeError, TypeError):
                        result_data = {}
                if isinstance(result_data, dict):
                    merged = dict(task)
                    merged.update(result_data)
                    self._cache[merged["id"]] = merged
            logger.info("BacktestTaskStore loaded %d tasks from database", len(self._cache))
        except Exception as exc:
            logger.warning("BacktestTaskStore failed to load from database, using empty cache: %s", exc)

    def __getitem__(self, key: str) -> Any:
        return self._cache.get(key)

    def __setitem__(self, key: str, value: Any):
        self._cache[key] = value
        try:
            status = value.get("status", "running")
            value.get("progress", 0.0)
            result = json.dumps(value, default=str)
            save_backtest_task(self._db_url, self._user_id, key, status, result)
        except Exception:
            logger.debug("BacktestTaskStore: Failed to persist task %s to database, using memory only", key)

    def __delitem__(self, key: str):
        if key in self._cache:
            del self._cache[key]
            try:
                delete_backtest_task(self._db_url, self._user_id, key)
            except Exception:
                logger.debug("BacktestTaskStore: Failed to delete task %s from database", key)

    def __contains__(self, key: str) -> bool:
        return str(key) in self._cache

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
        """清空内存缓存"""
        self._cache.clear()


class StrategyStore:
    """[DEPRECATED] 策略存储 — 使用 repository.save_strategy/list_strategies 替代"""

    def __init__(self, user_id: Optional[str] = None):
        self._db_url = _get_db_url()
        self._user_id = user_id
        self._cache: Dict[str, Any] = {}
        self._load_from_db()

    def _load_from_db(self):
        """从数据库加载数据到缓存"""
        try:
            strategies = list_strategies(self._db_url, self._user_id)
            for strategy in strategies:
                # 统一 key 类型为 str，兼容 DB 中整数 ID
                self._cache[str(strategy["id"])] = strategy
            logger.info("StrategyStore loaded %d strategies from database", len(self._cache))
        except Exception as exc:
            logger.warning("StrategyStore failed to load from database, using empty cache: %s", exc)

    def __getitem__(self, key: str) -> Any:
        return self._cache.get(key)

    def __setitem__(self, key: str, value: Any):
        self._cache[key] = value
        try:
            name = value.get("name", "")
            code = value.get("code", "")
            description = value.get("description")
            parameters = value.get("parameters")
            save_strategy(self._db_url, self._user_id, key, name, code, description, parameters)
        except Exception:
            logger.debug("StrategyStore: Failed to persist strategy %s to database, using memory only", key)

    def __delitem__(self, key: str):
        str_key = str(key)
        if str_key in self._cache:
            del self._cache[str_key]
            try:
                delete_strategy(self._db_url, self._user_id, str_key)
            except Exception:
                logger.debug("StrategyStore: Failed to delete strategy %s from database", key)

    def __contains__(self, key: str) -> bool:
        return str(key) in self._cache

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
    """[DEPRECATED] 数据收集任务存储 — 使用 repository.save_collect_task 替代"""

    def __init__(self, user_id: Optional[str] = None):
        self._db_url = _get_db_url()
        self._user_id = user_id
        self._cache: Dict[str, Any] = {}
        self._load_from_db()

    def _load_from_db(self):
        try:
            tasks = list_collect_tasks(self._db_url, self._user_id)
            for task in tasks:
                # 将 result 中保存的完整数据合并到顶层，保持与原有内存 dict 一致的格式
                result_data = task.get("result")
                if isinstance(result_data, str):
                    try:
                        result_data = json.loads(result_data)
                    except (json.JSONDecodeError, TypeError):
                        result_data = {}
                if isinstance(result_data, dict):
                    # 用本地副本，避免 pop 修改原始返回值
                    merged = dict(task)
                    merged.update(result_data)
                    self._cache[task["id"]] = merged
            logger.info("CollectTaskStore loaded %d tasks from database", len(self._cache))
        except Exception as exc:
            logger.warning("CollectTaskStore failed to load from database, using empty cache: %s", exc)

    def __setitem__(self, key: str, value: Any):
        self._cache[key] = value
        try:
            status = value.get("status", "running")
            progress = value.get("progress", 0.0)
            result = json.dumps(value, default=str)
            save_collect_task(self._db_url, self._user_id, key, status, progress, result)
        except Exception:
            logger.debug("CollectTaskStore: Failed to persist task %s to database, using memory only", key)

    def __getitem__(self, key: str) -> Any:
        return self._cache.get(key)

    def __delitem__(self, key: str):
        if key in self._cache:
            del self._cache[key]
            try:
                delete_collect_task(self._db_url, self._user_id, key)
            except Exception:
                logger.debug("CollectTaskStore: Failed to delete task %s from database", key)

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

    def update(self, other: Dict[str, Any] | None = None, **kwargs: Any) -> None:
        """批量更新缓存（不写数据库，由调用方自行批量写入）。"""
        if other:
            self._cache.update(other)
        if kwargs:
            self._cache.update(kwargs)


class OptimizeTaskStore:
    """[DEPRECATED] 参数优化任务存储 — 使用 repository.save_optimize_task 替代"""

    def __init__(self, user_id: Optional[str] = None):
        self._db_url = _get_db_url()
        self._user_id = user_id
        self._cache: Dict[str, Any] = {}
        self._load_from_db()

    def _load_from_db(self):
        try:
            tasks = list_optimize_tasks(self._db_url, self._user_id)
            for task in tasks:
                result_data = task.get("result")
                if isinstance(result_data, str):
                    try:
                        result_data = json.loads(result_data)
                    except (json.JSONDecodeError, TypeError):
                        result_data = {}
                if isinstance(result_data, dict):
                    merged = dict(task)
                    merged.update(result_data)
                    self._cache[merged["id"]] = merged
            logger.info("OptimizeTaskStore loaded %d tasks from database", len(self._cache))
        except Exception as exc:
            logger.warning("OptimizeTaskStore failed to load from database, using empty cache: %s", exc)

    def __setitem__(self, key: str, value: Any):
        self._cache[key] = value
        try:
            status = value.get("status", "running")
            value.get("progress", 0.0)
            result = json.dumps(value, default=str)
            save_optimize_task(self._db_url, self._user_id, key, status=status, result=result)
        except Exception:
            logger.debug("OptimizeTaskStore: Failed to persist task %s to database, using memory only", key)

    def __getitem__(self, key: str) -> Any:
        return self._cache.get(key)

    def __delitem__(self, key: str):
        if key in self._cache:
            del self._cache[key]
            try:
                delete_optimize_task(self._db_url, self._user_id, key)
            except Exception:
                logger.debug("OptimizeTaskStore: Failed to delete task %s from database", key)

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

    def update(self, other: Dict[str, Any] | None = None, **kwargs: Any) -> None:
        """批量更新缓存（不写数据库，由调用方自行批量写入）。"""
        if other:
            self._cache.update(other)
        if kwargs:
            self._cache.update(kwargs)


class ComparisonHistoryStore:
    """[DEPRECATED] 策略对比历史存储 — 使用 repository.save_comparison_history 替代"""

    def __init__(self, user_id: Optional[str] = None):
        self._db_url = _get_db_url()
        self._user_id = user_id
        self._cache: List[Dict[str, Any]] = []
        self._load_from_db()

    def _load_from_db(self):
        try:
            self._cache = list_comparison_history(self._db_url, self._user_id)
            logger.info("ComparisonHistoryStore loaded %d records from database", len(self._cache))
        except Exception as exc:
            logger.warning("ComparisonHistoryStore failed to load from database, using empty cache: %s", exc)

    def append(self, value: Dict[str, Any]):
        self._cache.append(value)
        try:
            import uuid
            history_id = str(uuid.uuid4())
            strategy_ids = value.get("strategy_ids", "")
            result = json.dumps(value.get("result"), default=str) if value.get("result") is not None else None
            save_comparison_history(self._db_url, self._user_id, history_id, strategy_ids, result)
        except Exception:
            logger.debug("ComparisonHistoryStore: Failed to persist record to database, using memory only")

    def __getitem__(self, index: int) -> Any:
        return self._cache[index]

    def __len__(self):
        return len(self._cache)

    def __iter__(self):
        return iter(self._cache)

    def reversed(self):
        """返回倒序迭代器（兼容旧代码调用 store.reversed()）。"""
        return reversed(self._cache)

    def __reversed__(self):
        """支持 built-in reversed() 函数。"""
        return reversed(self._cache)

    def clear(self):
        self._cache.clear()


class OrderAuditStore:
    """订单审计存储  模拟字典接口，底层使用数据库"""

    def __init__(self, user_id: Optional[str] = None):
        self._db_url = _get_db_url()
        self._user_id = user_id
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_from_db()

    def _load_from_db(self):
        try:
            audits = list_order_audits(self._db_url, self._user_id)
            for audit in audits:
                if audit["order_id"] not in self._cache:
                    self._cache[audit["order_id"]] = {}
                self._cache[audit["order_id"]][audit["id"]] = audit
            logger.info("OrderAuditStore loaded audits for %d orders from database", len(self._cache))
        except Exception as exc:
            logger.warning("OrderAuditStore failed to load from database, using empty cache: %s", exc)

    def __setitem__(self, key: str, value: Any):
        self._cache[key] = value
        try:
            import uuid
            audit_id = str(uuid.uuid4())
            order_id = key
            action = value.get("action", "")
            details = value.get("details")
            save_order_audit(self._db_url, self._user_id, audit_id, order_id, action, details)
        except Exception:
            logger.debug("OrderAuditStore: Failed to persist audit for order %s to database", key)

    def __getitem__(self, key: str) -> Any:
        return self._cache.get(key)

    def __delitem__(self, key: str):
        """删除某个 order_id 下的所有审计记录（同时清理缓存和数据库）。"""
        if key in self._cache:
            audit_ids = list(self._cache[key].keys())
            del self._cache[key]
            try:
                for audit_id in audit_ids:
                    delete_order_audit(self._db_url, self._user_id, audit_id)
            except Exception:
                logger.debug("OrderAuditStore: Failed to delete audits for order %s from database", key)

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

    def update(self, other: Dict[str, Any] | None = None, **kwargs: Any) -> None:
        """批量更新缓存（不写数据库，由调用方自行批量写入）。"""
        if other:
            self._cache.update(other)
        if kwargs:
            self._cache.update(kwargs)


# ── 通知存储 ──────────────────────────────────────────────────────────


class NotificationStore:
    """[DEPRECATED] 通知存储 — 使用 repository.list_notifications 替代"""

    def __init__(self, user_id: Optional[str] = None):
        self._db_url = _get_db_url()
        self._user_id = user_id
        self._cache: List[Dict[str, Any]] = []
        self._load_from_db()

    def _load_from_db(self):
        try:
            self._cache = list_notifications(self._db_url, self._user_id)
            logger.info("NotificationStore loaded %d notifications from database", len(self._cache))
        except Exception as exc:
            logger.warning("NotificationStore failed to load from database, using empty cache: %s", exc)

    def append(self, value: Dict[str, Any]):
        self._cache.append(value)
        try:
            sf = sessionmaker(bind=get_engine(self._db_url))
            with sf() as session:
                session.add(NotificationModel(
                    id=value.get("id", ""),
                    user_id=self._user_id or "",
                    notification_type=value.get("type", "info"),
                    title=value.get("title", ""),
                    message=value.get("message", ""),
                    is_read=1 if value.get("read", False) else 0,
                    created_at=datetime.fromisoformat(value["time"]) if value.get("time") else None,
                ))
                session.commit()
        except Exception:
            logger.debug("NotificationStore: Failed to persist notification to database, using memory only")

    def __getitem__(self, index: int) -> Any:
        return self._cache[index]

    def __len__(self):
        return len(self._cache)

    def __iter__(self):
        return iter(self._cache)

    def clear(self):
        self._cache.clear()


# ── 盯盘告警存储 ─────────────────────────────────────────────────────

class MonitorAlertStore:
    """盯盘告警存储  模拟列表接口，底层使用数据库"""

    def __init__(self, user_id: Optional[str] = None):
        self._db_url = _get_db_url()
        self._user_id = user_id
        self._cache: List[Dict[str, Any]] = []
        self._load_from_db()

    def _load_from_db(self):
        try:
            self._cache = list_monitor_alerts(self._db_url, self._user_id)
            logger.info("MonitorAlertStore loaded %d alerts from database", len(self._cache))
        except Exception as exc:
            logger.warning("MonitorAlertStore failed to load from database, using empty cache: %s", exc)

    def append(self, value: Dict[str, Any]):
        self._cache.append(value)
        try:
            import uuid
            save_monitor_alert(
                self._db_url,
                value.get("id", str(uuid.uuid4())),
                self._user_id or "",
                value.get("symbol", ""),
                value.get("direction", ""),
                value.get("reason", ""),
                value.get("confidence", 0.0),
                value.get("signal_type", ""),
                value.get("is_portfolio_hold", False),
            )
        except Exception:
            logger.debug("MonitorAlertStore: Failed to persist alert to database")

    def __getitem__(self, index: int) -> Any:
        return self._cache[index]

    def __len__(self):
        return len(self._cache)

    def __iter__(self):
        return iter(self._cache)

    def clear(self):
        self._cache.clear()


# ── 定时调度存储 ─────────────────────────────────────────────────────

class SchedulerStore:
    """定时调度任务存储  模拟字典接口，底层使用数据库"""

    def __init__(self, user_id: Optional[str] = None):
        self._db_url = _get_db_url()
        self._user_id = user_id
        self._cache: Dict[str, Any] = {}
        self._load_from_db()

    def _load_from_db(self):
        try:
            tasks = list_scheduler_tasks(self._db_url, self._user_id)
            for task in tasks:
                self._cache[task["id"]] = task
            logger.info("SchedulerStore loaded %d tasks from database", len(self._cache))
        except Exception as exc:
            logger.warning("SchedulerStore failed to load from database, using empty cache: %s", exc)

    def __getitem__(self, key: str) -> Any:
        return self._cache.get(key)

    def __setitem__(self, key: str, value: Any):
        self._cache[key] = value
        try:
            save_scheduler_task(
                self._db_url,
                self._user_id,
                task_id=key,
                name=value.get("name", ""),
                cron_expression=value.get("cron_expression", ""),
                action=value.get("action", ""),
                args=json.dumps(value.get("args"), default=str) if value.get("args") else None,
                kwargs=json.dumps(value.get("kwargs"), default=str) if value.get("kwargs") else None,
                enabled=value.get("enabled", True),
            )
        except Exception:
            logger.debug("SchedulerStore: Failed to persist task %s to database, using memory only", key)

    def __delitem__(self, key: str):
        if key in self._cache:
            del self._cache[key]
            try:
                delete_scheduler_task(self._db_url, self._user_id, key)
            except Exception:
                logger.debug("SchedulerStore: Failed to delete task %s from database", key)

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
