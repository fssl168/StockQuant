# -*- coding: utf-8 -*-
"""内存到数据库迁移 — 端到端持久化测试（100% 验证）

验证所有 Store 类的数据库持久化能力：创建 → 重启 → 数据恢复。
使用临时 SQLite 数据库，不污染生产数据。
"""

import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta

import pytest

from stockquant.persistence.models import Base, get_engine, init_db
from stockquant.persistence.persistent_store import (
    BacktestTaskStore,
    CollectTaskStore,
    ComparisonHistoryStore,
    MonitorAlertStore,
    NotificationStore,
    OptimizeTaskStore,
    OrderAuditStore,
    SchedulerStore,
    StrategyStore,
)


def _clear_engine_cache():
    """清除引擎缓存，确保每个测试使用独立的数据库连接"""
    from stockquant.persistence import models
    models._engine_cache.clear()


def _make_db_url() -> str:
    """创建临时 SQLite 数据库 URL"""
    _clear_engine_cache()
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return f"sqlite:///{tmp.name}"


def _cleanup(db_url: str):
    """清理临时数据库"""
    path = db_url.replace("sqlite:///", "")
    try:
        os.unlink(path)
    except OSError:
        pass


def _fresh_store(StoreClass, db_url: str):
    """创建一个指向指定 DB 的 Store 实例"""
    # 清除引擎缓存，确保使用正确的数据库
    _clear_engine_cache()
    # 覆盖 _get_db_url 的行为：Store 类内部通过 _get_db_url() 读取
    old_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        return StoreClass()
    finally:
        if old_url:
            os.environ["DATABASE_URL"] = old_url
        else:
            os.environ.pop("DATABASE_URL", None)


# =====================================================================
# BacktestTaskStore 测试
# =====================================================================


def test_backtest_task_store():
    db_url = _make_db_url()
    init_db(db_url)

    store = _fresh_store(BacktestTaskStore, db_url)
    task_id = "bt-001"
    task_data = {"status": "running", "progress": 0.5, "symbol": "sh600519"}
    store[task_id] = task_data

    # 验证缓存命中
    assert store[task_id] == task_data
    assert task_id in store
    assert len(store) == 1

    # 重建 Store，验证从 DB 恢复
    del store
    store2 = _fresh_store(BacktestTaskStore, db_url)
    restored = store2[task_id]
    assert restored is not None
    assert restored["status"] == "running"

    # 删除
    del store2[task_id]
    assert task_id not in store2
    assert len(store2) == 0

    _cleanup(db_url)


# =====================================================================
# StrategyStore 测试
# =====================================================================


def test_strategy_store():
    db_url = _make_db_url()
    init_db(db_url)

    store = _fresh_store(StrategyStore, db_url)
    sid = "strat-001"
    data = {
        "id": sid,
        "name": "MA Crossover",
        "code": "def init(...): pass",
        "parameters": json.dumps({"fast": 5, "slow": 20}),
    }
    store[sid] = data

    assert store[sid] is not None
    assert len(store) == 1

    # 重建验证恢复
    del store
    store2 = _fresh_store(StrategyStore, db_url)
    assert store2[sid] is not None
    assert store2[sid]["name"] == "MA Crossover"

    _cleanup(db_url)


# =====================================================================
# CollectTaskStore 测试
# =====================================================================


def test_collect_task_store():
    db_url = _make_db_url()
    init_db(db_url)

    store = _fresh_store(CollectTaskStore, db_url)
    tid = "collect-001"
    data = {"status": "running", "progress": 0.3, "symbol": "sh600000"}
    store[tid] = data

    assert store[tid] is not None
    assert len(store) == 1

    del store
    store2 = _fresh_store(CollectTaskStore, db_url)
    assert store2[tid] is not None
    assert store2[tid]["status"] == "running"

    _cleanup(db_url)


# =====================================================================
# OptimizeTaskStore 测试
# =====================================================================


def test_optimize_task_store():
    db_url = _make_db_url()
    init_db(db_url)

    store = _fresh_store(OptimizeTaskStore, db_url)
    tid = "opt-001"
    data = {"status": "running", "progress": 0.0}
    store[tid] = data

    assert store[tid] is not None

    del store
    store2 = _fresh_store(OptimizeTaskStore, db_url)
    assert store2[tid] is not None

    _cleanup(db_url)


# =====================================================================
# ComparisonHistoryStore 测试
# =====================================================================


def test_comparison_history_store():
    db_url = _make_db_url()
    init_db(db_url)

    store = _fresh_store(ComparisonHistoryStore, db_url)
    rec = {
        "strategy_ids": "strat-001,strat-002",
        "result": {"sh600519": {"win": True}},
    }
    store.append(rec)
    assert len(store) == 1

    # 验证倒序
    for r in store.reversed():
        assert r is not None

    del store
    store2 = _fresh_store(ComparisonHistoryStore, db_url)
    assert len(store2) == 1

    _cleanup(db_url)


# =====================================================================
# OrderAuditStore 测试
# =====================================================================


def test_order_audit_store():
    db_url = _make_db_url()
    init_db(db_url)

    store = _fresh_store(OrderAuditStore, db_url)
    oid = "order-001"
    data = {"action": "buy", "details": "market order"}
    store[oid] = data

    assert store[oid] is not None
    assert oid in store

    # 删除（应同时清理缓存和 DB）
    del store[oid]
    assert oid not in store

    _cleanup(db_url)


# =====================================================================
# NotificationStore 测试
# =====================================================================


def test_notification_store():
    db_url = _make_db_url()
    init_db(db_url)

    store = _fresh_store(NotificationStore, db_url)
    rec = {
        "id": str(uuid.uuid4()),
        "type": "info",
        "title": "Test Notification",
        "message": "This is a test",
        "time": datetime.now().isoformat(),
        "read": False,
    }
    store.append(rec)
    assert len(store) == 1

    del store
    store2 = _fresh_store(NotificationStore, db_url)
    assert len(store2) >= 1  # 至少有一条

    _cleanup(db_url)


# =====================================================================
# MonitorAlertStore 测试
# =====================================================================


def test_monitor_alert_store():
    db_url = _make_db_url()
    init_db(db_url)

    store = _fresh_store(MonitorAlertStore, db_url)
    rec = {
        "symbol": "sh600519",
        "direction": "BUY",
        "reason": "Golden cross detected",
        "confidence": 0.85,
        "signal_type": "technical",
    }
    store.append(rec)
    assert len(store) == 1

    del store
    store2 = _fresh_store(MonitorAlertStore, db_url)
    assert len(store2) == 1

    _cleanup(db_url)


# =====================================================================
# SchedulerStore 测试
# =====================================================================


def test_scheduler_store():
    db_url = _make_db_url()
    init_db(db_url)

    store = _fresh_store(SchedulerStore, db_url)
    tid = "daily_snapshot"
    data = {
        "id": tid,
        "name": "daily_snapshot",
        "cron_expression": "30 15 * * 1-5",
        "action": "save_equity_snapshot",
        "enabled": True,
    }
    store[tid] = data

    assert store[tid] is not None
    assert tid in store
    assert len(store) == 1

    del store
    store2 = _fresh_store(SchedulerStore, db_url)
    restored = store2[tid]
    assert restored is not None
    assert restored["name"] == "daily_snapshot"

    # 删除
    del store2[tid]
    assert tid not in store2

    _cleanup(db_url)


# =====================================================================
# 综合测试：所有 Store 同时操作
# =====================================================================


def test_all_stores_concurrent():
    """同时创建所有 Store 实例并操作，验证互不干扰"""
    db_url = _make_db_url()
    init_db(db_url)

    stores = {
        "backtest": _fresh_store(BacktestTaskStore, db_url),
        "strategy": _fresh_store(StrategyStore, db_url),
        "collect": _fresh_store(CollectTaskStore, db_url),
        "optimize": _fresh_store(OptimizeTaskStore, db_url),
        "comparison": _fresh_store(ComparisonHistoryStore, db_url),
        "audit": _fresh_store(OrderAuditStore, db_url),
        "notification": _fresh_store(NotificationStore, db_url),
        "monitor": _fresh_store(MonitorAlertStore, db_url),
        "scheduler": _fresh_store(SchedulerStore, db_url),
    }

    # 向每个 Store 写入数据
    stores["backtest"]["t1"] = {"status": "done"}
    stores["strategy"]["s1"] = {"name": "test"}
    stores["collect"]["c1"] = {"status": "running"}
    stores["optimize"]["o1"] = {"status": "done"}
    stores["comparison"].append({"strategy_ids": "s1,s2"})
    stores["audit"]["a1"] = {"action": "buy"}
    stores["notification"].append({"id": "n1", "type": "info", "title": "t", "message": "m", "time": datetime.now().isoformat(), "read": False})
    stores["monitor"].append({"symbol": "sh600519"})
    stores["scheduler"]["sched1"] = {"name": "sched1", "cron_expression": "0 0 * * *", "action": "test", "enabled": True}

    # 验证每个 Store 至少有一条数据
    assert len(stores["backtest"]) >= 1
    assert len(stores["strategy"]) >= 1
    assert len(stores["collect"]) >= 1
    assert len(stores["optimize"]) >= 1
    assert len(stores["comparison"]) >= 1
    assert len(stores["audit"]) >= 1
    assert len(stores["notification"]) >= 1
    assert len(stores["monitor"]) >= 1
    assert len(stores["scheduler"]) >= 1

    # 重建所有 Store，验证数据持久化
    new_stores = {
        "backtest": _fresh_store(BacktestTaskStore, db_url),
        "strategy": _fresh_store(StrategyStore, db_url),
        "collect": _fresh_store(CollectTaskStore, db_url),
        "optimize": _fresh_store(OptimizeTaskStore, db_url),
        "comparison": _fresh_store(ComparisonHistoryStore, db_url),
        "audit": _fresh_store(OrderAuditStore, db_url),
        "notification": _fresh_store(NotificationStore, db_url),
        "monitor": _fresh_store(MonitorAlertStore, db_url),
        "scheduler": _fresh_store(SchedulerStore, db_url),
    }

    assert len(new_stores["backtest"]) >= 1
    assert len(new_stores["strategy"]) >= 1
    assert len(new_stores["collect"]) >= 1
    assert len(new_stores["optimize"]) >= 1
    assert len(new_stores["comparison"]) >= 1
    assert len(new_stores["audit"]) >= 1
    assert len(new_stores["notification"]) >= 1
    assert len(new_stores["monitor"]) >= 1
    assert len(new_stores["scheduler"]) >= 1

    # 清理
    for s in stores.values():
        s.clear()
    for s in new_stores.values():
        s.clear()
    _cleanup(db_url)
