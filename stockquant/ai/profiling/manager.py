# -*- coding: utf-8 -*-
"""F020 FinMem Profiling 模块统一接口

负责：
1. 读取/更新用户风险偏好（UserModel.risk_profile）
2. 触发动态转换（ProfileTransitioner）
3. 返回当前 ProfileParams 供 Decision-making 使用
4. 记录转换历史（UserProfileHistory）

数据库后端：PostgreSQL + asyncpg（与 L2Store/L3Store 一致）。
不可用时降级为内存存储（仅用于测试）。
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .risk_profile import RiskProfile, ProfileParams, PROFILE_PARAMS, get_params
from .transition import (
    ProfileTransitioner,
    TransitionContext,
    TRIGGER_MANUAL,
)

logger = logging.getLogger("stockquant.ai.profiling.manager")


def _default_db_url() -> str:
    """获取默认数据库 URL"""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://stockquant:stockquant_secret@localhost:5432/stockquant",
    )


class ProfilingManager:
    """Profiling 模块统一接口

    用法：
        mgr = ProfilingManager()
        profile = mgr.get_profile("user1")           # 读取
        params = mgr.get_params("user1")              # 获取决策参数
        mgr.update_profile("user1", RiskProfile.AGGRESSIVE)  # 手动覆盖
        mgr.evaluate_transition("user1", context)     # 触发自动转换
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        user_id: str = "test_user",
        transitioner: Optional[ProfileTransitioner] = None,
    ) -> None:
        self._db_url = db_url or _default_db_url()
        self._user_id = user_id
        self._transitioner = transitioner or ProfileTransitioner()
        self._engine = None
        self._session_factory = None
        self._backend = "memory"
        # 内存降级后备：{user_id: {"profile": str, "updated_at": ISO, "history": [...]}}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._init_db()

    # ── 初始化 ────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """初始化 PostgreSQL 后端，失败时降级为内存存储"""
        try:
            url = self._db_url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql+psycopg2://"):
                url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)

            self._engine = create_async_engine(url, echo=False, pool_size=5)
            self._session_factory = sessionmaker(
                self._engine, class_=AsyncSession, expire_on_commit=False,
            )
            # 确保表已创建
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        pool.submit(lambda: asyncio.run(self._ensure_tables())).result()
                else:
                    loop.run_until_complete(self._ensure_tables())
            except RuntimeError:
                asyncio.run(self._ensure_tables())
            except Exception:
                raise
            self._backend = "postgresql"
            logger.info("ProfilingManager 使用 PostgreSQL 后端")
            return
        except ImportError:
            logger.warning("asyncpg/SQLAlchemy 未安装，ProfilingManager 降级为内存存储")
        except Exception as exc:
            logger.warning("PostgreSQL 连接失败: %s，ProfilingManager 降级为内存存储", exc)

        self._engine = None
        self._session_factory = None
        self._backend = "memory"

    async def _ensure_tables(self) -> None:
        """确保表结构已创建"""
        from stockquant.persistence.models import Base
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # ── 同步包装器（对外主接口） ────────────────────────────────────────

    def get_profile(self, user_id: Optional[str] = None) -> RiskProfile:
        """读取用户风险偏好"""
        uid = user_id or self._user_id
        if self._backend == "memory":
            return self._get_profile_memory(uid)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(lambda: asyncio.run(self._get_profile_async(uid))).result()
            return loop.run_until_complete(self._get_profile_async(uid))
        except RuntimeError:
            return asyncio.run(self._get_profile_async(uid))

    def get_params(self, user_id: Optional[str] = None) -> ProfileParams:
        """获取用户风险偏好对应的决策参数"""
        profile = self.get_profile(user_id)
        return get_params(profile)

    def update_profile(
        self,
        new_profile: RiskProfile,
        user_id: Optional[str] = None,
        trigger: str = TRIGGER_MANUAL,
        context: Optional[TransitionContext] = None,
    ) -> None:
        """更新用户风险偏好（手动覆盖或自动触发）

        Args:
            new_profile: 新的风险偏好
            user_id: 用户 ID（默认使用初始化时的 user_id）
            trigger: 触发器类型，默认为 manual
            context: 转换上下文（写入 history.context_json）
        """
        uid = user_id or self._user_id
        ctx = context or TransitionContext(user_target=new_profile)
        if self._backend == "memory":
            return self._update_profile_memory(uid, new_profile, trigger, ctx)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(
                        lambda: asyncio.run(self._update_profile_async(uid, new_profile, trigger, ctx))
                    ).result()
            return loop.run_until_complete(self._update_profile_async(uid, new_profile, trigger, ctx))
        except RuntimeError:
            return asyncio.run(self._update_profile_async(uid, new_profile, trigger, ctx))

    def evaluate_transition(
        self,
        context: TransitionContext,
        user_id: Optional[str] = None,
    ) -> Optional[RiskProfile]:
        """评估是否应该触发自动转换，如有则更新并返回新偏好

        Args:
            context: 转换上下文（市场环境/命中率等）
            user_id: 用户 ID

        Returns:
            新的风险偏好（如果触发转换），否则 None
        """
        uid = user_id or self._user_id
        current = self.get_profile(uid)
        last_transition_at = self._get_last_transition_at(uid)

        trigger, new_profile = self._transitioner.evaluate(
            current=current,
            context=context,
            last_transition_at=last_transition_at,
        )

        if trigger is None or new_profile == current:
            return None

        # 自动触发器重写为非 manual
        self.update_profile(new_profile, uid, trigger=trigger, context=context)
        return new_profile

    def get_history(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[Dict[str, Any]]:
        """获取用户风险偏好转换历史"""
        uid = user_id or self._user_id
        if self._backend == "memory":
            return list(self._cache.get(uid, {}).get("history", []))[:limit]
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(
                        lambda: asyncio.run(self._get_history_async(uid, limit))
                    ).result()
            return loop.run_until_complete(self._get_history_async(uid, limit))
        except RuntimeError:
            return asyncio.run(self._get_history_async(uid, limit))

    # ── 异步 PostgreSQL 操作 ──────────────────────────────────────────

    async def _get_profile_async(self, user_id: str) -> RiskProfile:
        from stockquant.persistence.models import UserModel
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserModel.risk_profile).where(UserModel.id == user_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                # 用户不存在，返回默认偏好
                return RiskProfile.NEUTRAL
            return RiskProfile.from_str(row)

    async def _update_profile_async(
        self,
        user_id: str,
        new_profile: RiskProfile,
        trigger: str,
        context: TransitionContext,
    ) -> None:
        from stockquant.persistence.models import UserModel, UserProfileHistory
        now = datetime.now()
        async with self._session_factory() as session:
            # 1. 读取当前偏好（用于历史记录的 from_profile）
            result = await session.execute(
                select(UserModel.risk_profile).where(UserModel.id == user_id)
            )
            current_str = result.scalar_one_or_none()
            current = RiskProfile.from_str(current_str) if current_str else RiskProfile.NEUTRAL

            # 2. 更新 UserModel
            await session.execute(
                update(UserModel)
                .where(UserModel.id == user_id)
                .values(
                    risk_profile=new_profile.value,
                    profile_updated_at=now,
                )
            )

            # 3. 写入转换历史
            history = UserProfileHistory(
                user_id=user_id,
                from_profile=current.value,
                to_profile=new_profile.value,
                trigger=trigger,
                context_json=context.to_json(),
                timestamp=now,
            )
            session.add(history)
            await session.commit()

    async def _get_history_async(
        self, user_id: str, limit: int
    ) -> list[Dict[str, Any]]:
        from stockquant.persistence.models import UserProfileHistory
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserProfileHistory)
                .where(UserProfileHistory.user_id == user_id)
                .order_by(UserProfileHistory.timestamp.desc())
                .limit(limit)
            )
            rows = result.scalars().all()
            return [
                {
                    "id": row.id,
                    "user_id": row.user_id,
                    "from_profile": row.from_profile,
                    "to_profile": row.to_profile,
                    "trigger": row.trigger,
                    "context_json": row.context_json,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                }
                for row in rows
            ]

    # ── 内存降级实现 ──────────────────────────────────────────────────

    def _get_profile_memory(self, user_id: str) -> RiskProfile:
        entry = self._cache.get(user_id)
        if entry is None:
            return RiskProfile.NEUTRAL
        return RiskProfile.from_str(entry.get("profile", "neutral"))

    def _update_profile_memory(
        self,
        user_id: str,
        new_profile: RiskProfile,
        trigger: str,
        context: TransitionContext,
    ) -> None:
        entry = self._cache.setdefault(user_id, {"profile": "neutral", "history": []})
        current = RiskProfile.from_str(entry["profile"])
        now = datetime.now().isoformat()
        entry["profile"] = new_profile.value
        entry["updated_at"] = now
        entry["history"].insert(0, {
            "from_profile": current.value,
            "to_profile": new_profile.value,
            "trigger": trigger,
            "context_json": context.to_json(),
            "timestamp": now,
        })

    def _get_last_transition_at(self, user_id: str) -> Optional[datetime]:
        """获取上次转换时间（用于冷却期判断）"""
        if self._backend == "memory":
            entry = self._cache.get(user_id)
            if not entry or not entry.get("updated_at"):
                return None
            try:
                return datetime.fromisoformat(entry["updated_at"])
            except (ValueError, TypeError):
                return None
        # PostgreSQL：从 history 表读取最新一条
        try:
            history = self.get_history(user_id, limit=1)
            if not history:
                return None
            ts = history[0].get("timestamp")
            if not ts:
                return None
            return datetime.fromisoformat(ts)
        except Exception as exc:
            logger.debug("读取上次转换时间失败: %s", exc)
            return None
