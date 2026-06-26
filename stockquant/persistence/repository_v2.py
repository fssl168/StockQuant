# ============================================================================
# Phase 5: Repository 统一仓储层 — 合并 repository.py + persistent_store.py
# ============================================================================

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from stockquant.persistence.models import (
    BacktestResult,
    ChatMessage,
    Notification,
    EquitySnapshot as EquitySnapshotModel,
    PositionSnapshot,
    StrategyModel,
    get_engine,
)

logger = logging.getLogger(__name__)


def _default_db_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///./stockquant.db")


def _session_factory(engine_url: str):
    return sessionmaker(bind=get_engine(engine_url))


# ── Cache 管理 ──────────────────────────────────────────────────────────


class CacheEntry:
    """缓存条目"""
    __slots__ = ("data", "expires_at")

    def __init__(self, data: Any, ttl: int):
        self.data = data
        self.expires_at = time.monotonic() + ttl


class CacheManager:
    """Repository 级缓存管理（TTL + 前缀失效）"""

    def __init__(self, ttl: int = 300):
        self._ttl = ttl
        self._store: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() >= entry.expires_at:
            del self._store[key]
            return None
        return entry.data

    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        self._store[key] = CacheEntry(data, ttl or self._ttl)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def invalidate_pattern(self, prefix: str) -> int:
        """按前缀清除缓存，返回清除数量"""
        to_remove = [k for k in self._store if k.startswith(prefix)]
        for k in to_remove:
            del self._store[k]
        return len(to_remove)

    def clear_all(self) -> int:
        count = len(self._store)
        self._store.clear()
        return count


# ── Repository 统一仓储类 ────────────────────────────────────────────


class Repository:
    """统一仓储层 — 合并 repository.py + persistent_store.py

    提供统一 CRUD 入口 + 内存缓存，替代分散的函数式 API + Store 类。
    """

    _instance: Optional["Repository"] = None

    def __init__(self, cache_ttl: int = 300, cache_enabled: bool = True):
        self._cache_enabled = cache_enabled
        self._cache = CacheManager(cache_ttl) if cache_enabled else None
        self._default_url: Optional[str] = None

    @classmethod
    def instance(cls) -> "Repository":
        """获取模块级单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── 内部工具 ──────────────────────────────────────────────────

    @property
    def cache(self) -> Optional[CacheManager]:
        return self._cache

    def _get_engine_url(self, engine_url: Optional[str] = None) -> str:
        return engine_url or self._default_url or _default_db_url()

    def _sf(self, engine_url: Optional[str] = None):
        return sessionmaker(bind=get_engine(self._get_engine_url(engine_url)))

    def _ck(self, prefix: str, *args: Any) -> str:
        return f"{prefix}::{'::'.join(str(a) for a in args)}"

    def _cget(self, key: str) -> Optional[Any]:
        if not self._cache:
            return None
        return self._cache.get(key)

    def _cset(self, key: str, data: Any) -> None:
        if self._cache and data is not None:
            self._cache.set(key, data)

    def _cinvalid(self, prefix: str) -> None:
        if self._cache:
            self._cache.invalidate_pattern(prefix)

    # ── BacktestResult CRUD ─────────────────────────────────────

    def save_backtest(self, user_id: Optional[str] = None, strategy_name: str = "",
                      symbol: str = "", start_date: str = "", end_date: str = "",
                      initial_cash: float = 0.0, final_equity: float = 0.0,
                      metrics: Optional[Dict] = None, equity_curve: Optional[List] = None,
                      trades_summary: Optional[List[Dict]] = None,
                      engine_url: Optional[str] = None) -> int:
        if metrics is None: metrics = {}
        if equity_curve is None: equity_curve = []
        if trades_summary is None: trades_summary = []
        url = self._get_engine_url(engine_url)
        sf = _session_factory(url)
        with sf() as session:
            row = BacktestResult(
                user_id=user_id or "", strategy_name=strategy_name, symbol=symbol,
                start_date=start_date, end_date=end_date,
                initial_cash=initial_cash, final_equity=final_equity,
                metrics=json.dumps(metrics),
                equity_curve=json.dumps([list(t) if isinstance(t, (tuple, list)) else t for t in equity_curve]),
                trades_summary=json.dumps(trades_summary),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
        self._cinvalid("backtest_result:")
        self._cinvalid("backtests:")
        return row.id

    def get_backtest(self, result_id: int, user_id: Optional[str] = None,
                     engine_url: Optional[str] = None) -> Optional[Dict]:
        if self._cache:
            cached = self._cget(self._ck("backtest_result", result_id, user_id or ""))
            if cached is not None:
                return cached
        url = self._get_engine_url(engine_url)
        sf = _session_factory(url)
        with sf() as session:
            row = session.get(BacktestResult, result_id)
            if row is None or (user_id is not None and row.user_id != user_id):
                return None
            result = {
                "id": row.id, "strategy_name": row.strategy_name, "symbol": row.symbol,
                "start_date": row.start_date, "end_date": row.end_date,
                "initial_cash": row.initial_cash, "final_equity": row.final_equity,
                "metrics": json.loads(row.metrics) if isinstance(row.metrics, str) else row.metrics,
                "equity_curve": json.loads(row.equity_curve) if isinstance(row.equity_curve, str) else row.equity_curve,
                "trades_summary": json.loads(row.trades_summary) if isinstance(row.trades_summary, str) else row.trades_summary,
                "created_at": row.created_at,
            }
        self._cset(self._ck("backtest_result", result_id, user_id or ""), result)
        return result

    def list_backtests(self, user_id: Optional[str] = None, limit: int = 50, offset: int = 0,
                       engine_url: Optional[str] = None) -> List[Dict]:
        if self._cache:
            cached = self._cget(self._ck("backtests", user_id or "all", limit, offset))
            if cached is not None:
                return cached
        url = self._get_engine_url(engine_url)
        sf = _session_factory(url)
        with sf() as session:
            stmt = select(BacktestResult).order_by(BacktestResult.created_at.desc()).limit(limit).offset(offset)
            if user_id is not None:
                stmt = stmt.where(BacktestResult.user_id == user_id)
            rows = session.execute(stmt).scalars().all()
            result = [{
                "id": r.id, "strategy_name": r.strategy_name, "symbol": r.symbol,
                "start_date": r.start_date, "end_date": r.end_date,
                "initial_cash": r.initial_cash, "final_equity": r.final_equity,
                "metrics": json.loads(r.metrics) if isinstance(r.metrics, str) else r.metrics,
                "equity_curve": json.loads(r.equity_curve) if isinstance(r.equity_curve, str) else r.equity_curve,
                "trades_summary": json.loads(r.trades_summary) if isinstance(r.trades_summary, str) else r.trades_summary,
                "created_at": r.created_at,
            } for r in rows]
        self._cset(self._ck("backtests", user_id or "all", limit, offset), result)
        return result

    # ── Strategy CRUD ───────────────────────────────────────────

    def save_strategy(self, strategy_id: str, user_id: Optional[str] = None,
                      name: str = "", code: str = "", description: Optional[str] = None,
                      parameters: Optional[str] = None, engine_url: Optional[str] = None) -> None:
        url = self._get_engine_url(engine_url)
        sf = _session_factory(url)
        uid = user_id or ""
        with sf() as session:
            s = session.execute(select(StrategyModel).where(
                StrategyModel.id == strategy_id, StrategyModel.user_id == uid
            )).scalars().first()
            if s:
                s.name, s.code = name, code
                s.description, s.parameters = description, parameters
                s.updated_at = datetime.now()
            else:
                s = StrategyModel(id=strategy_id, user_id=uid, name=name, code=code,
                                  description=description, parameters=parameters,
                                  created_at=datetime.now(), updated_at=datetime.now())
                session.add(s)
            session.commit()
        self._cinvalid("strategy:")
        self._cinvalid("strategies:")

    def get_strategy(self, strategy_id: str, user_id: Optional[str] = None,
                     engine_url: Optional[str] = None) -> Optional[Dict]:
        if self._cache:
            cached = self._cget(self._ck("strategy", strategy_id, user_id or ""))
            if cached is not None:
                return cached
        url = self._get_engine_url(engine_url)
        sf = _session_factory(url)
        uid = user_id or ""
        with sf() as session:
            s = session.execute(select(StrategyModel).where(
                StrategyModel.id == strategy_id, StrategyModel.user_id == uid
            )).scalars().first()
            if s is None:
                return None
            result = {"id": s.id, "user_id": s.user_id, "name": s.name,
                      "description": s.description, "code": s.code, "parameters": s.parameters,
                      "created_at": s.created_at, "updated_at": s.updated_at}
        self._cset(self._ck("strategy", strategy_id, user_id or ""), result)
        return result

    def list_strategies(self, user_id: Optional[str] = None, engine_url: Optional[str] = None) -> List[Dict]:
        if self._cache:
            cached = self._cget(self._ck("strategies", user_id or "all"))
            if cached is not None:
                return cached
        url = self._get_engine_url(engine_url)
        sf = _session_factory(url)
        with sf() as session:
            stmt = select(StrategyModel).order_by(StrategyModel.created_at.desc())
            if user_id is not None:
                stmt = stmt.where(StrategyModel.user_id == user_id)
            strategies = session.execute(stmt).scalars().all()
            result = [{"id": s.id, "user_id": s.user_id, "name": s.name, "description": s.description,
                       "code": s.code, "parameters": s.parameters,
                       "created_at": s.created_at, "updated_at": s.updated_at} for s in strategies]
        self._cset(self._ck("strategies", user_id or "all"), result)
        return result

    # ── Notification CRUD ─────────────────────────────────────────

    def save_notification(self, notification_id: str, user_id: Optional[str] = None,
                          notification_type: str = "info", title: str = "", message: str = "",
                          is_read: bool = False, created_at: Optional[datetime] = None,
                          engine_url: Optional[str] = None) -> None:
        if created_at is None:
            created_at = datetime.now()
        url = self._get_engine_url(engine_url)
        sf = _session_factory(url)
        with sf() as session:
            row = session.get(Notification, notification_id)
            if row is None:
                row = Notification(
                    id=notification_id, user_id=user_id or "",
                    notification_type=notification_type, title=title,
                    message=message, is_read=1 if is_read else 0, created_at=created_at,
                )
                session.add(row)
            else:
                row.notification_type, row.title, row.message = notification_type, title, message
                row.is_read = 1 if is_read else 0
                row.created_at = created_at
            session.commit()
        self._cinvalid("notifications:")

    def update_notification_read(self, notification_id: str, is_read: bool,
                                  engine_url: Optional[str] = None) -> bool:
        url = self._get_engine_url(engine_url)
        sf = _session_factory(url)
        with sf() as session:
            row = session.get(Notification, notification_id)
            if row is None:
                return False
            row.is_read = 1 if is_read else 0
            session.commit()
        self._cinvalid("notifications:")
        return True

    # ── Equity Snapshot CRUD ──────────────────────────────────────

    def save_equity_snapshot(self, snapshot_id: str, user_id: str, date: str, equity: float,
                              cash: float = 0.0, market_value: float = 0.0,
                              positions_count: int = 0, engine_url: Optional[str] = None) -> None:
        url = self._get_engine_url(engine_url)
        sf = _session_factory(url)
        with sf() as session:
            row = session.get(EquitySnapshotModel, snapshot_id)
            if row is None:
                row = EquitySnapshotModel(
                    id=snapshot_id, user_id=user_id, date=date, equity=equity,
                    cash=cash, market_value=market_value, positions_count=positions_count,
                    created_at=datetime.now(),
                )
                session.add(row)
            else:
                row.equity, row.cash, row.market_value, row.positions_count = equity, cash, market_value, positions_count
            session.commit()

    # ── Chat/Session CRUD ─────────────────────────────────────────

    def list_chat_sessions(self, user_id: Optional[str] = None, limit: int = 50,
                           engine_url: Optional[str] = None) -> List[Dict]:
        if self._cache:
            cached = self._cget(self._ck("chat_sessions", user_id or "all", limit))
            if cached is not None:
                return cached
        url = self._get_engine_url(engine_url)
        sf = _session_factory(url)
        from sqlalchemy import func, desc
        with sf() as session:
            stmt = (
                select(ChatMessage.session_id, func.max(ChatMessage.created_at).label("latest_at"),
                       func.min(ChatMessage.id).label("first_msg_id"),
                       func.count(ChatMessage.id).label("message_count"))
                .group_by(ChatMessage.session_id).order_by(desc("latest_at")).limit(limit)
            )
            if user_id is not None:
                stmt = stmt.where(ChatMessage.user_id == user_id)
            rows = session.execute(stmt).all()
            result = []
            for row in rows:
                title = None
                if row.first_msg_id:
                    first_msg = session.query(ChatMessage).filter(ChatMessage.id == row.first_msg_id).first()
                    if first_msg and first_msg.role == "user":
                        title = first_msg.content[:30] if len(first_msg.content) > 30 else first_msg.content
                result.append({"id": row.session_id, "user_id": user_id or "",
                               "created_at": row.latest_at.isoformat() if row.latest_at else None,
                               "message_count": row.message_count, "title": title})
        self._cset(self._ck("chat_sessions", user_id or "all", limit), result)
        return result

    # ── 快捷委托方法（调用现有 repository.py 函数） ─────────────────

    def __getattr__(self, name: str) -> Any:
        """自动委托未知方法到 repository.py 模块级函数"""
        # 延迟导入避免循环依赖
        if name.startswith("_"):
            raise AttributeError(name)
        import importlib
        repo = importlib.import_module("stockquant.persistence.repository")
        func = getattr(repo, name, None)
        if func is None:
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")
        # 缓存方法引用
        setattr(self, name, func)
        return func


# ── 模块级单例 ────────────────────────────────────────────────────────

_repo: Optional[Repository] = None


def get_repo() -> Repository:
    """获取 Repository 单例"""
    global _repo
    if _repo is None:
        _repo = Repository.instance()
    return _repo


# ── 缺失函数补充 ────────────────────────────────────────────────────


def delete_all_strategies(engine_url: str, user_id: Optional[str] = None) -> int:
    """[新增] 删除用户所有策略，返回删除数量"""
    from stockquant.persistence.models import StrategyModel
    count = 0
    try:
        sf = _session_factory(engine_url)
        with sf() as session:
            strategies = session.query(StrategyModel).filter(
                StrategyModel.user_id == (user_id or "")
            ).all()
            for s in strategies:
                session.delete(s)
                count += 1
            session.commit()
    except Exception as e:
        logger.error("Failed to delete all strategies for user %s: %s", user_id, e)
    logger.info("Deleted %d strategies for user=%s", count, user_id)
    return count


def clear_cache() -> int:
    """清空 Repository 缓存"""
    repo = get_repo()
    if repo._cache:
        return repo._cache.clear_all()
    return 0
