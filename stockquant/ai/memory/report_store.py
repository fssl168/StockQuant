# -*- coding: utf-8 -*-
"""F020 报告存储层 -- PostgreSQL + pgvector，支持日报/月报/年报三级报告

统一使用 PostgreSQL + asyncpg + pgvector 作为存储后端。
PostgreSQL 不可用时自动降级为内存存储。
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.memory.report_store")


# ─── 轻量级 ORM 模型（内联定义，避免修改 persistence/models.py） ──

_REPORT_TABLE_NAME = "ai_reports"

# pgvector 可用时使用 Vector 类型，否则降级为 Text
_HAS_PGVECTOR_REPORT = False
_ReportVectorClass: Any = __import__("sqlalchemy").Text

try:
    from pgvector.sqlalchemy import Vector as _VecCls
    _ReportVectorClass = _VecCls
    _HAS_PGVECTOR_REPORT = True
except ImportError:
    pass


def _get_report_table(base):
    """动态创建 Report 表的 ORM 模型

    使用函数封装延迟导入，避免循环依赖。
    """
    from sqlalchemy import (
        Column, Float, Index, Integer, String, Text, UniqueConstraint,
    )
    from sqlalchemy.orm import Mapped, mapped_column

    class ReportModel(base):
        """AI 报告模型 -- 日报/月报/年报统一存储"""
        __tablename__ = _REPORT_TABLE_NAME

        id: Mapped[str] = mapped_column(String(100), primary_key=True)
        user_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
        report_type: Mapped[str] = mapped_column(
            String(20), nullable=False, index=True,
        )  # daily | monthly | annual
        report_date: Mapped[str] = mapped_column(
            String(10), nullable=False, index=True,
        )  # YYYY-MM-DD
        report_period_start: Mapped[Optional[str]] = mapped_column(
            String(10), nullable=True,
        )
        report_period_end: Mapped[Optional[str]] = mapped_column(
            String(10), nullable=True,
        )
        market_review: Mapped[str] = mapped_column(Text, nullable=False, default="")
        trading_record: Mapped[str] = mapped_column(Text, nullable=False, default="")
        strategy_performance: Mapped[str] = mapped_column(
            Text, nullable=False, default="",
        )
        ai_insights: Mapped[str] = mapped_column(Text, nullable=False, default="")
        full_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
        summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
        confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
        importance_score: Mapped[float] = mapped_column(
            Float, nullable=False, default=0.5,
        )
        metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
        metadata_json: Mapped[str] = mapped_column(
            Text, nullable=False, default="{}",
        )
        created_at: Mapped[str] = mapped_column(
            String(30), nullable=False,
        )
        last_accessed_at: Mapped[Optional[str]] = mapped_column(
            String(30), nullable=True,
        )
        embedding = Column(_ReportVectorClass, nullable=True)

        __table_args__ = (
            UniqueConstraint(
                "user_id", "report_type", "report_date",
                name="uq_report_user_type_date",
            ),
            Index("ix_report_user_type", "user_id", "report_type"),
            Index("ix_report_date", "report_date"),
        )

    return ReportModel


def _default_db_url() -> str:
    """获取默认数据库 URL"""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://stockquant:stockquant_secret@localhost:5432/stockquant",
    )


class ReportStore:
    """报告存储层 -- 日报/月报/年报统一存储

    PostgreSQL + pgvector 向量检索，降级到内存存储。
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        user_id: str = "test_user",
        embedding_dim: int = 1536,
    ) -> None:
        self._db_url = db_url or _default_db_url()
        self._embedding_dim = embedding_dim
        self._user_id = user_id
        self._backend = "memory"  # 默认降级为内存
        self._engine = None
        self._session_factory = None
        self._has_pgvector = False
        self._entries: List[Dict[str, Any]] = []  # 内存降级后备
        # RecallScorer 实例
        try:
            from .recall_scorer import RecallScorer
            self._scorer = RecallScorer(scene="review")
        except ImportError:
            self._scorer = None
        self._init_backend()

    # ── 后端初始化 ───────────────────────────────────────────────────

    def _init_backend(self) -> None:
        """初始化存储后端，优先 PostgreSQL + pgvector"""
        try:
            from sqlalchemy.ext.asyncio import (
                AsyncSession,
                create_async_engine,
            )
            from sqlalchemy.orm import sessionmaker

            url = self._db_url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql+psycopg2://"):
                url = url.replace(
                    "postgresql+psycopg2://", "postgresql+asyncpg://", 1,
                )

            self._engine = create_async_engine(url, echo=False, pool_size=5)
            self._session_factory = sessionmaker(
                self._engine, class_=AsyncSession, expire_on_commit=False,
            )

            self._check_pgvector()
            if self._backend == "memory":
                logger.info(
                    "ReportStore 使用内存后端 (pgvector=%s)",
                    self._has_pgvector,
                )
            else:
                logger.info(
                    "ReportStore 使用 PostgreSQL 后端 (pgvector=%s)",
                    self._has_pgvector,
                )
            return
        except ImportError:
            logger.warning(
                "asyncpg/SQLAlchemy 未安装，ReportStore 降级为内存存储"
            )
        except Exception as exc:
            logger.warning(
                "PostgreSQL 连接失败: %s，ReportStore 降级为内存存储", exc
            )

        self._engine = None
        self._session_factory = None
        self._backend = "memory"

    def _check_pgvector(self) -> None:
        """检测 pgvector 扩展是否可用"""
        import asyncio
        try:
            loop = asyncio.get_running_loop()

            async def _async_init():
                try:
                    await self._ensure_tables()
                    self._backend = "postgresql"
                except Exception as exc:
                    logger.warning(
                        "异步初始化失败: %s，ReportStore 降级为内存存储", exc
                    )
                    self._backend = "memory"
                    self._engine = None
                    self._session_factory = None

            loop.create_task(_async_init())
            self._backend = "memory"
            logger.info("检测到运行中的事件循环，pgvector 初始化异步进行中")
        except RuntimeError:
            try:
                asyncio.get_event_loop().run_until_complete(
                    self._ensure_tables()
                )
                self._backend = "postgresql"
            except Exception as exc:
                logger.warning(
                    "PostgreSQL 表创建失败: %s，ReportStore 降级为内存存储",
                    exc,
                )
                raise

    async def _ensure_tables(self) -> None:
        """确保 pgvector 扩展已安装，并创建 Report 表和默认用户"""
        from sqlalchemy import select

        async with self._engine.begin() as conn:
            try:
                await conn.execute(
                    __import__("sqlalchemy").text(
                        "CREATE EXTENSION IF NOT EXISTS vector"
                    )
                )
                self._has_pgvector = True
                logger.info("pgvector 扩展已启用 (ReportStore)")
            except Exception as exc:
                logger.warning(
                    "pgvector 扩展不可用: %s，向量检索将降级为关键词匹配",
                    exc,
                )
                self._has_pgvector = False

        # 创建表（如果不存在）
        async with self._engine.begin() as conn:
            try:
                from sqlalchemy.ext.declarative import DeclarativeBase

                class _ReportBase(DeclarativeBase):
                    pass

                ReportModel = _get_report_table(_ReportBase)
                await conn.run_sync(
                    _ReportBase.metadata.create_all
                )
            except Exception:
                raise

        # 确保默认用户存在
        try:
            from stockquant.persistence.models import Base, UserModel

            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            async with self._session_factory() as session:
                user = await session.execute(
                    select(UserModel).where(UserModel.id == self._user_id)
                )
                if user.scalar_one_or_none() is None:
                    session.add(
                        UserModel(
                            id=self._user_id,
                            username="test_user",
                            hashed_password="not_used",
                            roles='["user"]',
                            disabled=0,
                        )
                    )
                    await session.commit()
        except Exception as exc:
            logger.warning("默认用户创建失败: %s，降级为内存存储", exc)
            raise

    # ── 同步包装器 ──────────────────────────────────────────────────

    def _sync_call(self, async_fn, *args, **kwargs):
        """统一的异步/同步桥接调用（与 L3Store 模式一致）"""
        if self._backend == "memory":
            return None  # 由调用方处理内存分支
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(
                        self._run_in_new_loop, async_fn, *args, **kwargs
                    ).result()
            return loop.run_until_complete(async_fn(*args, **kwargs))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(async_fn(*args, **kwargs))
            finally:
                loop.close()

    def _run_in_new_loop(self, async_fn, *args, **kwargs):
        """在独立事件循环中运行异步函数（ThreadPoolExecutor 辅助）"""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(async_fn(*args, **kwargs))
        finally:
            loop.close()

    # ── 公开 API ─────────────────────────────────────────────────────

    def write(self, report: Dict) -> str:
        """写入一份报告

        参数:
            report: 包含以下字段：
                - report_type: "daily" | "monthly" | "annual"
                - report_date: "YYYY-MM-DD"
                - report_period_start: "YYYY-MM-DD"
                - report_period_end: "YYYY-MM-DD"
                - market_review: 市场回顾文本
                - trading_record: 交易记录文本
                - strategy_performance: 策略表现文本
                - ai_insights: AI 洞察文本
                - metrics_json: 关键指标 JSON
                - metadata_json: 扩展元数据 JSON
                - summary: 摘要
                - confidence: 置信度
                - importance_score: 重要性
        返回: 报告 ID
        """
        if self._backend == "memory":
            return self._write_memory(report)
        return self._sync_call(self._write_async, report)

    def get_report(self, report_type: str, date_key: str) -> Optional[Dict]:
        """获取指定类型的报告（按日期/月份/年份）

        daily: date_key = "YYYY-MM-DD"
        monthly: date_key = "YYYY-MM"
        annual: date_key = "YYYY"
        """
        if self._backend == "memory":
            return self._get_report_memory(report_type, date_key)
        return self._sync_call(self._get_report_async, report_type, date_key)

    def list_reports(
        self,
        report_type: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict]:
        """列出指定类型的报告，按日期倒序"""
        if self._backend == "memory":
            return self._list_reports_memory(
                report_type, start, end, limit, offset
            )
        return self._sync_call(
            self._list_reports_async, report_type, start, end, limit, offset
        )

    def search(
        self,
        query: str,
        report_type: str = "all",
        top_k: int = 10,
    ) -> List[Dict]:
        """语义检索报告

        1. 优先 pgvector 向量检索
        2. 降级 TF-IDF (sklearn)
        3. 降级关键词匹配
        4. 用 RecallScorer 重排序
        """
        if self._backend == "memory":
            return self._search_memory(query, report_type, top_k)
        return self._sync_call(self._search_async, query, report_type, top_k)

    def delete(self, report_id: str) -> bool:
        """删除报告"""
        if self._backend == "memory":
            before = len(self._entries)
            self._entries = [
                e for e in self._entries if e.get("id") != report_id
            ]
            return len(self._entries) < before
        return self._sync_call(self._delete_async, report_id)

    def clear_all(self) -> int:
        """清空所有报告"""
        if self._backend == "memory":
            n = len(self._entries)
            self._entries.clear()
            return n
        return self._sync_call(self._clear_all_async)

    def count(self, report_type: Optional[str] = None) -> int:
        """统计报告数量"""
        if self._backend == "memory":
            if report_type:
                return sum(
                    1 for e in self._entries
                    if e.get("report_type") == report_type
                )
            return len(self._entries)
        return self._sync_call(self._count_async, report_type)

    def get_dailies_for_period(
        self, period_start: str, period_end: str
    ) -> List[Dict]:
        """获取指定日期范围内所有日报（用于月报/年报聚合）"""
        if self._backend == "memory":
            return [
                e for e in self._entries
                if e.get("report_type") == "daily"
                and period_start <= (e.get("report_date", "") or "") <= period_end
            ]
        return self._sync_call(
            self._get_dailies_for_period_async, period_start, period_end
        )

    def get_monthlies_for_period(
        self, period_start: str, period_end: str
    ) -> List[Dict]:
        """获取指定日期范围内所有月报（用于年报聚合）"""
        if self._backend == "memory":
            return [
                e for e in self._entries
                if e.get("report_type") == "monthly"
                and period_start <= (e.get("report_date", "") or "") <= period_end
            ]
        return self._sync_call(
            self._get_monthlies_for_period_async, period_start, period_end
        )

    def close(self) -> None:
        """关闭连接"""
        if self._engine:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._engine.dispose())
                else:
                    loop.run_until_complete(self._engine.dispose())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self._engine.dispose())
        self._engine = None
        self._session_factory = None

    # ── 异步 PostgreSQL 操作 ──────────────────────────────────────────

    def _get_report_model(self):
        """获取 ReportModel 类（延迟导入，避免在非 PG 模式下触发依赖）"""
        from sqlalchemy.ext.declarative import DeclarativeBase

        class _ReportBase(DeclarativeBase):
            pass

        return _get_report_table(_ReportBase)

    async def _write_async(self, report: Dict) -> str:
        """异步写入 PostgreSQL（UPSERT）"""
        from sqlalchemy import select

        ReportModel = self._get_report_model()
        now_iso = datetime.now().isoformat()

        report_type = report.get("report_type", "daily")
        report_date = report.get("report_date", datetime.now().strftime("%Y-%m-%d"))

        # 拼接 full_content
        market_review = report.get("market_review", "")
        trading_record = report.get("trading_record", "")
        strategy_perf = report.get("strategy_performance", "")
        ai_insights = report.get("ai_insights", "")
        full_content = "\n".join(filter(None, [
            market_review, trading_record, strategy_perf, ai_insights,
        ]))

        metrics = report.get("metrics_json", {})
        if not isinstance(metrics, str):
            metrics = json.dumps(
                metrics, ensure_ascii=False, separators=(",", ":")
            )

        metadata = report.get("metadata_json", {})
        if not isinstance(metadata, str):
            metadata = json.dumps(
                metadata, ensure_ascii=False, separators=(",", ":")
            )

        async with self._session_factory() as session:
            # 检查是否已存在（按 user_id + report_type + report_date 唯一）
            stmt = select(ReportModel).where(
                ReportModel.user_id == self._user_id,
                ReportModel.report_type == report_type,
                ReportModel.report_date == report_date,
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            if row:
                # UPSERT: 更新已有记录
                row.report_period_start = report.get("report_period_start")
                row.report_period_end = report.get("report_period_end")
                row.market_review = market_review
                row.trading_record = trading_record
                row.strategy_performance = strategy_perf
                row.ai_insights = ai_insights
                row.full_content = full_content
                row.summary = report.get("summary", "")
                row.confidence = float(report.get("confidence", 0.8))
                row.importance_score = float(
                    report.get("importance_score", 0.5)
                )
                row.metrics_json = metrics
                row.metadata_json = metadata
                row.last_accessed_at = now_iso
                report_id = row.id
            else:
                # 新建记录
                report_id = (
                    f"rpt_{report_type}_{report_date}"
                    f"_{datetime.now().strftime('%H%M%S')}"
                )
                new_row = ReportModel(
                    id=report_id,
                    user_id=self._user_id,
                    report_type=report_type,
                    report_date=report_date,
                    report_period_start=report.get("report_period_start"),
                    report_period_end=report.get("report_period_end"),
                    market_review=market_review,
                    trading_record=trading_record,
                    strategy_performance=strategy_perf,
                    ai_insights=ai_insights,
                    full_content=full_content,
                    summary=report.get("summary", ""),
                    confidence=float(report.get("confidence", 0.8)),
                    importance_score=float(
                        report.get("importance_score", 0.5)
                    ),
                    metrics_json=metrics,
                    metadata_json=metadata,
                    created_at=now_iso,
                    last_accessed_at=now_iso,
                )
                session.add(new_row)

            await session.commit()

        # 异步计算 embedding（best-effort，不阻塞写入）
        if self._has_pgvector and full_content:
            try:
                embedding = await self._get_embedding(full_content)
                if embedding is not None:
                    await self._save_embedding(report_id, embedding)
            except Exception as exc:
                logger.debug("报告 embedding 计算失败: %s", exc)

        return report_id

    async def _save_embedding(self, report_id: str, embedding: list) -> None:
        """保存报告的向量嵌入"""
        from sqlalchemy import update

        ReportModel = self._get_report_model()
        async with self._session_factory() as session:
            await session.execute(
                update(ReportModel)
                .where(ReportModel.id == report_id)
                .values(embedding=str(embedding))
            )
            await session.commit()

    async def _get_report_async(
        self, report_type: str, date_key: str
    ) -> Optional[Dict]:
        """异步获取指定类型的报告"""
        from sqlalchemy import select

        ReportModel = self._get_report_model()
        async with self._session_factory() as session:
            if report_type == "daily":
                stmt = select(ReportModel).where(
                    ReportModel.user_id == self._user_id,
                    ReportModel.report_type == "daily",
                    ReportModel.report_date == date_key,
                )
            elif report_type == "monthly":
                # date_key = "YYYY-MM", 查找该月最后一天的 report_date
                month_end = self._get_month_end(date_key)
                stmt = select(ReportModel).where(
                    ReportModel.user_id == self._user_id,
                    ReportModel.report_type == "monthly",
                    ReportModel.report_date == month_end,
                )
            elif report_type == "annual":
                # date_key = "YYYY", 查找 report_date = "YYYY-12-31"
                stmt = select(ReportModel).where(
                    ReportModel.user_id == self._user_id,
                    ReportModel.report_type == "annual",
                    ReportModel.report_date == f"{date_key}-12-31",
                )
            else:
                return None

            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                # 刷新 last_accessed_at
                await self._touch_last_accessed_async(row.id)
                return self._row_to_dict(row)
            return None

    async def _list_reports_async(
        self,
        report_type: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict]:
        """异步列出指定类型的报告"""
        from sqlalchemy import select

        ReportModel = self._get_report_model()
        async with self._session_factory() as session:
            stmt = select(ReportModel).where(
                ReportModel.user_id == self._user_id,
                ReportModel.report_type == report_type,
            )
            if start:
                stmt = stmt.where(ReportModel.report_date >= start)
            if end:
                stmt = stmt.where(ReportModel.report_date <= end)
            stmt = (
                stmt.order_by(ReportModel.report_date.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return [self._row_to_dict(row) for row in result.scalars().all()]

    async def _search_async(
        self,
        query: str,
        report_type: str = "all",
        top_k: int = 10,
    ) -> List[Dict]:
        """异步语义检索报告

        1. 优先 pgvector 向量检索
        2. 降级 TF-IDF (sklearn)
        3. 降级关键词匹配
        4. 用 RecallScorer 重排序
        """
        from sqlalchemy import select

        ReportModel = self._get_report_model()
        async with self._session_factory() as session:
            stmt = select(ReportModel).where(
                ReportModel.user_id == self._user_id,
            )
            if report_type != "all":
                stmt = stmt.where(ReportModel.report_type == report_type)
            stmt = stmt.order_by(ReportModel.report_date.desc()).limit(top_k * 3)

            result = await session.execute(stmt)
            rows = result.scalars().all()

            if not rows:
                return []

            # pgvector 向量检索
            if self._has_pgvector:
                try:
                    vector_items = await self._search_vector(
                        session, query, report_type, top_k * 3
                    )
                    if vector_items:
                        items = self._rerank_with_scorer(
                            vector_items, query, report_type, top_k
                        )
                        return await self._batch_touch_accessed(items)
                except Exception as exc:
                    logger.warning(
                        "向量检索失败: %s，降级为关键词匹配", exc
                    )

            # 关键词匹配降级
            items = [self._row_to_dict(row) for row in rows]

            # TF-IDF 降级尝试
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity

                contents = [
                    item.get("full_content", "") or item.get("summary", "")
                    for item in items
                ]
                if contents and any(contents):
                    vectorizer = TfidfVectorizer(max_features=5000)
                    tfidf_matrix = vectorizer.fit_transform(contents + [query])
                    query_vec = tfidf_matrix[-1]
                    doc_vecs = tfidf_matrix[:-1]
                    similarities = cosine_similarity(query_vec, doc_vecs)[0]
                    for i, item in enumerate(items):
                        item["_semantic_score"] = float(similarities[i])
            except Exception:
                pass

            # RecallScorer 重排序
            items = self._rerank_with_scorer(
                items, query, report_type, top_k
            )
            return await self._batch_touch_accessed(items)

    async def _search_vector(
        self,
        session,
        query: str,
        report_type: str,
        top_k: int,
    ) -> List[Dict]:
        """pgvector 向量检索"""
        from sqlalchemy import text

        query_embedding = await self._get_embedding(query)
        if query_embedding is None:
            raise RuntimeError("Embedding 服务不可用")

        type_filter = ""
        params: Dict[str, Any] = {
            "query_vec": str(query_embedding),
            "limit": top_k,
            "user_id": self._user_id,
        }
        if report_type != "all":
            type_filter = " AND report_type = :report_type"
            params["report_type"] = report_type

        sql = f"""
            SELECT id, user_id, report_type, report_date, report_period_start,
                   report_period_end, market_review, trading_record,
                   strategy_performance, ai_insights, full_content, summary,
                   confidence, importance_score, metrics_json, metadata_json,
                   created_at, last_accessed_at,
                   embedding <=> :query_vec AS distance
            FROM {_REPORT_TABLE_NAME}
            WHERE user_id = :user_id{type_filter}
            ORDER BY embedding <=> :query_vec
            LIMIT :limit
        """
        result = await session.execute(text(sql), params)
        rows = result.fetchall()

        items = []
        for row in rows:
            items.append({
                "id": row[0],
                "user_id": row[1],
                "report_type": row[2],
                "report_date": row[3],
                "report_period_start": row[4],
                "report_period_end": row[5],
                "market_review": row[6],
                "trading_record": row[7],
                "strategy_performance": row[8],
                "ai_insights": row[9],
                "full_content": row[10],
                "summary": row[11],
                "confidence": row[12],
                "importance_score": row[13],
                "metrics": json.loads(row[14]) if row[14] else {},
                "metadata": json.loads(row[15]) if row[15] else {},
                "created_at": row[16],
                "last_accessed_at": row[17],
                "distance": row[18],
            })
        return items

    async def _batch_touch_accessed(
        self, items: List[Dict]
    ) -> List[Dict]:
        """批量刷新 last_accessed_at（best-effort）"""
        for item in items:
            try:
                await self._touch_last_accessed_async(item["id"])
            except Exception:
                pass
        return items

    async def _touch_last_accessed_async(self, report_id: str) -> None:
        """刷新 last_accessed_at"""
        from sqlalchemy import update

        ReportModel = self._get_report_model()
        async with self._session_factory() as session:
            await session.execute(
                update(ReportModel)
                .where(ReportModel.id == report_id)
                .values(last_accessed_at=datetime.now().isoformat())
            )
            await session.commit()

    def _rerank_with_scorer(
        self,
        items: List[Dict],
        query: str,
        report_type: str,
        top_k: int,
    ) -> List[Dict]:
        """用 RecallScorer 对检索结果重排序"""
        # report_type 映射到 RecallScorer tier
        tier_map = {"daily": "shallow", "monthly": "intermediate", "annual": "deep"}
        tier = tier_map.get(report_type, "shallow")

        if self._scorer is not None:
            try:
                ranked = self._scorer.rank(
                    items, query=query, tier=tier, top_k=top_k,
                )
                return [item for item, _ in ranked]
            except Exception as exc:
                logger.debug(
                    "RecallScorer 重排序失败，降级原始顺序: %s", exc
                )
        return items[:top_k]

    async def _delete_async(self, report_id: str) -> bool:
        """异步删除"""
        from sqlalchemy import delete

        ReportModel = self._get_report_model()
        async with self._session_factory() as session:
            result = await session.execute(
                delete(ReportModel).where(ReportModel.id == report_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def _clear_all_async(self) -> int:
        """异步清空所有报告"""
        from sqlalchemy import delete as sa_delete

        ReportModel = self._get_report_model()
        async with self._session_factory() as session:
            result = await session.execute(sa_delete(ReportModel))
            await session.commit()
            return result.rowcount

    async def _count_async(self, report_type: Optional[str] = None) -> int:
        """异步计数"""
        from sqlalchemy import func, select

        ReportModel = self._get_report_model()
        async with self._session_factory() as session:
            stmt = select(func.count()).select_from(ReportModel).where(
                ReportModel.user_id == self._user_id,
            )
            if report_type:
                stmt = stmt.where(ReportModel.report_type == report_type)
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def _get_dailies_for_period_async(
        self, period_start: str, period_end: str
    ) -> List[Dict]:
        """异步获取日期范围内的日报"""
        from sqlalchemy import select

        ReportModel = self._get_report_model()
        async with self._session_factory() as session:
            stmt = (
                select(ReportModel)
                .where(
                    ReportModel.user_id == self._user_id,
                    ReportModel.report_type == "daily",
                    ReportModel.report_date >= period_start,
                    ReportModel.report_date <= period_end,
                )
                .order_by(ReportModel.report_date.asc())
            )
            result = await session.execute(stmt)
            return [self._row_to_dict(row) for row in result.scalars().all()]

    async def _get_monthlies_for_period_async(
        self, period_start: str, period_end: str
    ) -> List[Dict]:
        """异步获取日期范围内的月报"""
        from sqlalchemy import select

        ReportModel = self._get_report_model()
        async with self._session_factory() as session:
            stmt = (
                select(ReportModel)
                .where(
                    ReportModel.user_id == self._user_id,
                    ReportModel.report_type == "monthly",
                    ReportModel.report_date >= period_start,
                    ReportModel.report_date <= period_end,
                )
                .order_by(ReportModel.report_date.asc())
            )
            result = await session.execute(stmt)
            return [self._row_to_dict(row) for row in result.scalars().all()]

    async def _get_embedding(self, text: str) -> Optional[list]:
        """获取文本的向量嵌入

        优先级：
        1. OpenAI text-embedding-3-small（云服务）
        2. 本地 sentence-transformers/all-MiniLM-L6-v2（离线）
        3. None（无可用 embedding）
        """
        try:
            embedding = await self._openai_embedding(text)
            if embedding is not None:
                return embedding
        except Exception as exc:
            logger.debug("OpenAI embedding 失败，尝试本地 fallback: %s", exc)

        try:
            return self._local_embedding(text)
        except Exception as exc:
            logger.debug("本地 embedding 也不可用: %s", exc)
        return None

    async def _openai_embedding(self, text: str) -> Optional[list]:
        """调用 OpenAI Embedding API"""
        try:
            from stockquant.config import get_config

            config = get_config()
            ai_config = config.get("ai", {})

            api_key = ai_config.get("api_key") or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                return None

            base_url = (
                ai_config.get("api_base")
                or os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
            )
            import httpx

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{base_url}/embeddings",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "text-embedding-3-small",
                        "input": text[:8192],
                    },
                )
                if resp.status_code == 200:
                    return resp.json()["data"][0]["embedding"]
        except Exception as exc:
            logger.debug("OpenAI Embedding 调用失败: %s", exc)
        return None

    def _local_embedding(self, text: str) -> Optional[list]:
        """本地 sentence-transformers embedding"""
        if not hasattr(self, "_local_embedder") or self._local_embedder is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._local_embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                logger.warning(
                    "sentence-transformers 未安装，本地 embedding 不可用"
                )
                self._local_embedder = None
                return None
            except Exception as exc:
                logger.warning("本地 embedding 模型加载失败: %s", exc)
                self._local_embedder = None
                return None

        try:
            embedding = self._local_embedder.encode(text[:8192])
            return embedding.tolist()
        except Exception as exc:
            logger.debug("本地 embedding 编码失败: %s", exc)
            return None

    # ── 内存降级方法 ──────────────────────────────────────────────────

    def _write_memory(self, report: Dict) -> str:
        """内存模式写入"""
        report_type = report.get("report_type", "daily")
        report_date = report.get(
            "report_date", datetime.now().strftime("%Y-%m-%d")
        )
        report_id = f"rpt_{report_type}_{report_date}"

        market_review = report.get("market_review", "")
        trading_record = report.get("trading_record", "")
        strategy_perf = report.get("strategy_performance", "")
        ai_insights = report.get("ai_insights", "")
        full_content = "\n".join(filter(None, [
            market_review, trading_record, strategy_perf, ai_insights,
        ]))

        metrics = report.get("metrics_json", {})
        if isinstance(metrics, str):
            try:
                metrics = json.loads(metrics)
            except Exception:
                metrics = {}

        metadata = report.get("metadata_json", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}

        now_iso = datetime.now().isoformat()

        # UPSERT: 检查是否已有同类型同日期的报告
        for i, existing in enumerate(self._entries):
            if (
                existing.get("user_id") == self._user_id
                and existing.get("report_type") == report_type
                and existing.get("report_date") == report_date
            ):
                # 更新已有记录
                self._entries[i].update({
                    "report_period_start": report.get("report_period_start"),
                    "report_period_end": report.get("report_period_end"),
                    "market_review": market_review,
                    "trading_record": trading_record,
                    "strategy_performance": strategy_perf,
                    "ai_insights": ai_insights,
                    "full_content": full_content,
                    "summary": report.get("summary", ""),
                    "confidence": float(report.get("confidence", 0.8)),
                    "importance_score": float(
                        report.get("importance_score", 0.5)
                    ),
                    "metrics": metrics,
                    "metadata": metadata,
                    "last_accessed_at": now_iso,
                })
                return self._entries[i]["id"]

        # 新建
        entry = {
            "id": report_id,
            "user_id": self._user_id,
            "report_type": report_type,
            "report_date": report_date,
            "report_period_start": report.get("report_period_start"),
            "report_period_end": report.get("report_period_end"),
            "market_review": market_review,
            "trading_record": trading_record,
            "strategy_performance": strategy_perf,
            "ai_insights": ai_insights,
            "full_content": full_content,
            "summary": report.get("summary", ""),
            "confidence": float(report.get("confidence", 0.8)),
            "importance_score": float(report.get("importance_score", 0.5)),
            "metrics": metrics,
            "metadata": metadata,
            "created_at": now_iso,
            "last_accessed_at": now_iso,
        }
        self._entries.append(entry)
        return report_id

    def _get_report_memory(
        self, report_type: str, date_key: str
    ) -> Optional[Dict]:
        """内存模式获取报告"""
        if report_type == "daily":
            target_date = date_key
        elif report_type == "monthly":
            target_date = self._get_month_end(date_key)
        elif report_type == "annual":
            target_date = f"{date_key}-12-31"
        else:
            return None

        for entry in self._entries:
            if (
                entry.get("user_id") == self._user_id
                and entry.get("report_type") == report_type
                and entry.get("report_date") == target_date
            ):
                entry["last_accessed_at"] = datetime.now().isoformat()
                return entry
        return None

    def _list_reports_memory(
        self,
        report_type: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict]:
        """内存模式列出报告"""
        filtered = [
            e for e in self._entries
            if e.get("user_id") == self._user_id
            and e.get("report_type") == report_type
        ]
        if start:
            filtered = [
                e for e in filtered
                if (e.get("report_date", "") or "") >= start
            ]
        if end:
            filtered = [
                e for e in filtered
                if (e.get("report_date", "") or "") <= end
            ]
        filtered.sort(key=lambda x: x.get("report_date", ""), reverse=True)
        return filtered[offset: offset + limit]

    def _search_memory(
        self,
        query: str,
        report_type: str = "all",
        top_k: int = 10,
    ) -> List[Dict]:
        """内存模式语义检索"""
        if not self._entries:
            return []

        # 按 report_type 过滤
        candidates = [
            e for e in self._entries
            if e.get("user_id") == self._user_id
            and (report_type == "all" or e.get("report_type") == report_type)
        ]

        if not candidates:
            return []

        # RecallScorer 重排序
        tier_map = {"daily": "shallow", "monthly": "intermediate", "annual": "deep"}
        tier = tier_map.get(report_type, "shallow")

        if self._scorer is not None:
            try:
                ranked = self._scorer.rank(
                    candidates, query=query, tier=tier, top_k=top_k,
                )
                items = []
                for item, _ in ranked:
                    item["last_accessed_at"] = datetime.now().isoformat()
                    items.append(item)
                return items
            except Exception as exc:
                logger.debug(
                    "RecallScorer 评分失败，降级关键词匹配: %s", exc
                )

        # 降级：TF-IDF 尝试
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            contents = [
                e.get("full_content", "") or e.get("summary", "")
                for e in candidates
            ]
            if contents and any(contents):
                vectorizer = TfidfVectorizer(max_features=5000)
                tfidf_matrix = vectorizer.fit_transform(contents + [query])
                query_vec = tfidf_matrix[-1]
                doc_vecs = tfidf_matrix[:-1]
                similarities = cosine_similarity(query_vec, doc_vecs)[0]
                scored = list(zip(candidates, similarities))
                scored.sort(key=lambda x: x[1], reverse=True)
                return [
                    item for item, _ in scored[:top_k]
                ]
        except Exception:
            pass

        # 降级：关键词匹配
        query_lower = query.lower()
        scored = []
        for item in candidates:
            content_lower = (item.get("full_content") or "").lower()
            summary_lower = (item.get("summary") or "").lower()
            score = sum(
                1 for w in query_lower.split()
                if w in content_lower or w in summary_lower
            )
            scored.append((item, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored[:top_k]]

    # ── 工具方法 ──────────────────────────────────────────────────────

    @staticmethod
    def _get_month_end(year_month: str) -> str:
        """根据 YYYY-MM 获取该月最后一天 YYYY-MM-DD"""
        try:
            year, month = year_month.split("-")
            # 下个月第 1 天减 1 天
            from datetime import date as _date

            if int(month) == 12:
                last_day = _date(int(year) + 1, 1, 1) - __import__(
                    "datetime"
                ).timedelta(days=1)
            else:
                last_day = _date(int(year), int(month) + 1, 1) - __import__(
                    "datetime"
                ).timedelta(days=1)
            return last_day.strftime("%Y-%m-%d")
        except Exception:
            # 降级：直接拼 28 日
            return f"{year_month}-28"

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        """ORM 行转字典"""
        return {
            "id": row.id,
            "user_id": row.user_id,
            "report_type": row.report_type,
            "report_date": row.report_date,
            "report_period_start": getattr(row, "report_period_start", None),
            "report_period_end": getattr(row, "report_period_end", None),
            "market_review": row.market_review,
            "trading_record": row.trading_record,
            "strategy_performance": row.strategy_performance,
            "ai_insights": row.ai_insights,
            "full_content": row.full_content,
            "summary": row.summary,
            "confidence": float(row.confidence),
            "importance_score": float(row.importance_score),
            "metrics": json.loads(row.metrics_json) if row.metrics_json else {},
            "metadata": (
                json.loads(row.metadata_json) if row.metadata_json else {}
            ),
            "created_at": row.created_at,
            "last_accessed_at": getattr(row, "last_accessed_at", None),
        }
