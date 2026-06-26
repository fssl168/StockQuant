# -*- coding: utf-8 -*-
"""F020 L2 短期记忆 — PostgreSQL + asyncpg 持久化存储 + TF-IDF 语义检索"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.memory.l2")


def _default_db_url() -> str:
    """获取默认数据库 URL"""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://stockquant:stockquant_secret@localhost:5432/stockquant",
    )


class L2Store:
    """L2 短期记忆 — PostgreSQL 存储，支持 TF-IDF 语义检索和自动过期

    PostgreSQL 不可用时自动降级为内存存储。
    """

    def __init__(self, db_url: Optional[str] = None, user_id: str = "test_user") -> None:
        self._db_url = db_url or _default_db_url()
        self._user_id = user_id
        self._backend = "memory"  # 默认降级为内存
        self._engine = None
        self._session_factory = None
        self._entries: List[Dict[str, Any]] = []  # 内存降级后备
        # RecallScorer 实例（B3 集成）：L2 对应 shallow tier
        try:
            from .recall_scorer import RecallScorer
            self._scorer = RecallScorer(scene="default")
        except ImportError:
            self._scorer = None
        self._init_db()

    def _init_db(self) -> None:
        """初始化 PostgreSQL 后端，失败时降级为内存存储"""
        try:
            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
            from sqlalchemy.orm import sessionmaker

            # 确保 URL 使用 asyncpg 驱动
            url = self._db_url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql+psycopg2://"):
                url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)

            self._engine = create_async_engine(url, echo=False, pool_size=5)
            self._session_factory = sessionmaker(
                self._engine, class_=AsyncSession, expire_on_commit=False,
            )

            # 创建表并创建默认用户
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        pool.submit(lambda: asyncio.run(self._ensure_tables_and_default_user())).result()
                else:
                    loop.run_until_complete(self._ensure_tables_and_default_user())
            except RuntimeError:
                asyncio.run(self._ensure_tables_and_default_user())
            except Exception:
                raise
            self._backend = "postgresql"
            logger.info("L2 使用 PostgreSQL 后端 (url=%s)", url.split("@")[-1] if "@" in url else url)
            return
        except ImportError:
            logger.warning("asyncpg/SQLAlchemy 未安装，L2 降级为内存存储（重启后数据丢失）")
        except Exception as exc:
            logger.warning("PostgreSQL 连接失败: %s，L2 降级为内存存储（重启后数据丢失）", exc)

        self._engine = None
        self._session_factory = None
        self._backend = "memory"

    async def _ensure_tables_and_default_user(self) -> None:
        """确保表结构已创建，并创建默认测试用户"""
        from stockquant.persistence.models import Base, UserModel
        from sqlalchemy import select

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # 确保默认用户存在
        async with self._session_factory() as session:
            user = await session.execute(select(UserModel).where(UserModel.id == self._user_id))
            if user.scalar_one_or_none() is None:
                session.add(UserModel(
                    id=self._user_id,
                    username="test_user",
                    hashed_password="not_used",
                    roles='["user"]',
                    disabled=0,
                ))
                await session.commit()

    # ── 同步包装器 ──────────────────────────────────────────────────────

    def write(self, item: Dict[str, Any]) -> str:
        """写入一条 L2 记忆（同步）"""
        if self._backend == "memory":
            return self._write_memory(item)
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(self._write_sync, item).result()
            return loop.run_until_complete(self._write_async(item))
        except RuntimeError:
            return __import__("asyncio").run(self._write_async(item))

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """语义检索（同步）

        优先使用 TF-IDF（sklearn），不可用时降级为关键词匹配。
        """
        if self._backend == "memory":
            return self._search_memory(query, top_k)
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(self._search_sync, query, top_k).result()
            return loop.run_until_complete(self._search_async(query, top_k))
        except RuntimeError:
            return __import__("asyncio").run(self._search_async(query, top_k))

    def cleanup_expired(self) -> int:
        """清理过期条目"""
        if self._backend == "memory":
            now = datetime.now().isoformat()
            before = len(self._entries)
            self._entries = [
                e for e in self._entries
                if not e.get("expires_at") or e["expires_at"] >= now
            ]
            return before - len(self._entries)

        try:
            import asyncio
            now = datetime.now().isoformat()
            async def _cleanup():
                from stockquant.persistence.models import L2Memory
                from sqlalchemy import delete
                async with self._session_factory() as session:
                    result = await session.execute(
                        delete(L2Memory).where(
                            L2Memory.expires_at.isnot(None),
                            L2Memory.expires_at < now,
                        )
                    )
                    await session.commit()
                    return result.rowcount
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        return pool.submit(lambda: asyncio.run(_cleanup())).result()
                return loop.run_until_complete(_cleanup())
            except RuntimeError:
                return asyncio.run(_cleanup())
        except Exception as exc:
            logger.warning("L2 过期清理失败: %s", exc)
            return 0

    def count(self) -> int:
        """返回当前条目总数"""
        if self._backend == "memory":
            return len(self._entries)
        try:
            import asyncio
            async def _count():
                from stockquant.persistence.models import L2Memory
                from sqlalchemy import select, func
                async with self._session_factory() as session:
                    result = await session.execute(select(func.count()).select_from(L2Memory))
                    return result.scalar() or 0
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        return pool.submit(lambda: asyncio.run(_count())).result()
                return loop.run_until_complete(_count())
            except RuntimeError:
                return asyncio.run(_count())
        except Exception:
            return len(self._entries)

    def get_all(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """获取所有条目（用于压缩迁移）"""
        if self._backend == "memory":
            return self._entries[:limit]
        try:
            import asyncio
            async def _get():
                from stockquant.persistence.models import L2Memory
                from sqlalchemy import select
                async with self._session_factory() as session:
                    stmt = select(L2Memory).order_by(L2Memory.timestamp.asc()).limit(limit)
                    result = await session.execute(stmt)
                    return [self._row_to_dict(row) for row in result.scalars().all()]
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        return pool.submit(lambda: asyncio.run(_get())).result()
                return loop.run_until_complete(_get())
            except RuntimeError:
                return asyncio.run(_get())
        except Exception:
            return self._entries[:limit]

    def delete(self, item_id: str) -> bool:
        """删除指定条目"""
        if self._backend == "memory":
            before = len(self._entries)
            self._entries = [e for e in self._entries if e.get("id") != item_id]
            return len(self._entries) < before
        try:
            import asyncio
            async def _del():
                from stockquant.persistence.models import L2Memory
                from sqlalchemy import delete as sa_delete
                async with self._session_factory() as session:
                    result = await session.execute(
                        sa_delete(L2Memory).where(L2Memory.id == item_id)
                    )
                    await session.commit()
                    return result.rowcount > 0
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        return pool.submit(lambda: asyncio.run(_del())).result()
                return loop.run_until_complete(_del())
            except RuntimeError:
                return asyncio.run(_del())
        except Exception:
            return False

    def clear_all(self) -> int:
        """清空所有条目（用于测试）"""
        if self._backend == "memory":
            n = len(self._entries)
            self._entries.clear()
            return n
        try:
            import asyncio
            async def _clear():
                from stockquant.persistence.models import L2Memory
                from sqlalchemy import delete as sa_delete
                async with self._session_factory() as session:
                    result = await session.execute(sa_delete(L2Memory))
                    await session.commit()
                    return result.rowcount
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        return pool.submit(lambda: asyncio.run(_clear())).result()
                return loop.run_until_complete(_clear())
            except RuntimeError:
                return asyncio.run(_clear())
        except Exception:
            return 0

    # ── 同步降级方法 ────────────────────────────────────────────────────

    def _write_sync(self, item: Dict[str, Any]) -> str:
        return __import__("asyncio").run(self._write_async(item))

    def _search_sync(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        return __import__("asyncio").run(self._search_async(query, top_k))

    # ── 异步 PostgreSQL 操作 ─────────────────────────────────────────────

    async def _write_async(self, item: Dict[str, Any]) -> str:
        """异步写入 PostgreSQL（B3: 记录 source/sentiment/scope 到 metadata 供 RecallScorer 使用）"""
        from stockquant.persistence.models import L2Memory
        from sqlalchemy import select

        item_id = item.get("id", f"l2_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(item)}")

        async with self._session_factory() as session:
            existing = await session.execute(
                select(L2Memory).where(L2Memory.id == item_id)
            )
            row = existing.scalar_one_or_none()

            # B3: 合并 metadata + RecallScorer shallow tier 字段
            metadata = item.get("metadata", {})
            if not isinstance(metadata, str):
                metadata = dict(metadata) if isinstance(metadata, dict) else {}
                # 注入 source/sentiment/scope 到 metadata
                if item.get("source"):
                    metadata.setdefault("source", item["source"])
                if item.get("sentiment_score") is not None:
                    metadata.setdefault("sentiment_score", item["sentiment_score"])
                if item.get("scope"):
                    metadata.setdefault("scope", item["scope"])
                metadata = json.dumps(metadata, ensure_ascii=False)

            user_id = item.get("user_id") or self._user_id

            if row:
                row.symbol = item.get("symbol", "")
                row.user_id = user_id
                row.content = item.get("content", "")
                row.metadata_json = metadata
                row.timestamp = item.get("timestamp", datetime.now().isoformat())
                row.expires_at = item.get("expires_at")
                row.confidence = item.get("confidence", 1.0)
            else:
                row = L2Memory(
                    id=item_id,
                    user_id=user_id,
                    symbol=item.get("symbol", ""),
                    content=item.get("content", ""),
                    metadata_json=metadata,
                    timestamp=item.get("timestamp", datetime.now().isoformat()),
                    expires_at=item.get("expires_at"),
                    confidence=item.get("confidence", 1.0),
                )
                session.add(row)

            await session.commit()
        return item_id

    async def _search_async(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """异步语义检索（B3: 集成 RecallScorer 排序，tier=shallow）"""
        from stockquant.persistence.models import L2Memory
        from sqlalchemy import select

        async with self._session_factory() as session:
            stmt = select(L2Memory).order_by(L2Memory.timestamp.desc())
            result = await session.execute(stmt)
            rows = result.scalars().all()

            if not rows:
                return []

            items = [self._row_to_dict(row) for row in rows]

            # 优先 TF-IDF / Embedding（产生 semantic_score）
            semantic_scores: List[float] = []
            try:
                return self._tfidf_search_with_scorer(query, items, top_k)
            except ImportError:
                pass
            except Exception as exc:
                logger.debug("TF-IDF 检索失败，降级 RecallScorer 关键词模式: %s", exc)

            # B3: 直接用 RecallScorer 评分（无 semantic_score）
            if self._scorer is not None:
                try:
                    ranked = self._scorer.rank(
                        items, query=query, tier="shallow", top_k=top_k,
                    )
                    return [item for item, _ in ranked]
                except Exception as exc:
                    logger.debug("RecallScorer 评分失败，降级关键词: %s", exc)

            # 最终降级：关键词匹配
            return self._keyword_search(query, items, top_k)

    def _tfidf_search_with_scorer(
        self, query: str, items: List[Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        """TF-IDF/Embedding 检索后用 RecallScorer 重排序（B3 集成）

        步骤：
        1. 用 TF-IDF 或 Embedding 算出每条 item 的语义相似度
        2. 将相似度作为 semantic_score 传给 RecallScorer
        3. RecallScorer 综合三因子排序后返回 top_k
        """
        # 优先尝试 Embedding
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            if not hasattr(self, "_st_model"):
                self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
            contents = [item["content"] for item in items]
            doc_emb = self._st_model.encode(contents, convert_to_numpy=True, show_progress_bar=False)
            q_emb = self._st_model.encode([query], convert_to_numpy=True, show_progress_bar=False)
            sims = np.dot(doc_emb, q_emb[0]) / (
                np.linalg.norm(doc_emb, axis=1) * np.linalg.norm(q_emb[0]) + 1e-8
            )
            # 注入 semantic_score 到每条 item
            for item, sim in zip(items, sims.tolist()):
                item["_semantic_score"] = max(0.0, sim)
        except ImportError:
            raise
        except Exception as exc:
            logger.debug("Embedding 不可用，降级 TF-IDF: %s", exc)
            # TF-IDF 降级
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            corpus = [item["content"] for item in items]
            corpus.append(query)
            vectorizer = TfidfVectorizer()
            tfidf = vectorizer.fit_transform(corpus)
            sims = cosine_similarity(tfidf[-1:], tfidf[:-1]).flatten()
            for item, sim in zip(items, sims.tolist()):
                item["_semantic_score"] = max(0.0, sim)

        # B3: 用 RecallScorer 重排序
        if self._scorer is not None:
            try:
                ranked = self._scorer.rank(
                    items, query=query, tier="shallow", top_k=top_k,
                )
                # 清理临时字段
                for item, _ in ranked:
                    item.pop("_semantic_score", None)
                return [item for item, _ in ranked]
            except Exception as exc:
                logger.debug("RecallScorer 重排序失败，降级 semantic: %s", exc)

        # 降级：按 semantic_score 排序
        items.sort(key=lambda x: x.get("_semantic_score", 0.0), reverse=True)
        for item in items:
            item.pop("_semantic_score", None)
        return items[:top_k]

    # ── 内存降级方法 ────────────────────────────────────────────────────

    def _write_memory(self, item: Dict[str, Any]) -> str:
        item_id = item.get("id", f"l2_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(item)}")
        entry = {**item, "id": item_id}
        # Ensure user_id is present (required by L2Memory model)
        if "user_id" not in entry or not entry["user_id"]:
            entry["user_id"] = self._user_id
        # B3: 提取 RecallScorer shallow tier 所需字段到 entry 顶层
        # 来源：item 顶层优先，否则从 metadata 提取
        metadata = item.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        entry.setdefault("source", item.get("source") or metadata.get("source") or "unknown")
        entry.setdefault("sentiment_score", item.get("sentiment_score") or metadata.get("sentiment_score") or 0.0)
        entry.setdefault("scope", item.get("scope") or metadata.get("scope") or "individual")
        self._entries.append(entry)
        return item_id

    def _search_memory(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        if not self._entries:
            return []
        # B3: 优先 RecallScorer 评分（tier=shallow）
        if self._scorer is not None:
            try:
                ranked = self._scorer.rank(
                    self._entries[:], query=query, tier="shallow", top_k=top_k,
                )
                return [item for item, _ in ranked]
            except Exception as exc:
                logger.debug("RecallScorer 评分失败，降级关键词: %s", exc)
        return self._keyword_search(query, self._entries, top_k)

    # ── 检索算法 ────────────────────────────────────────────────────────

    def _tfidf_search(self, query: str, items: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """Embedding 向量检索（优先）→ TF-IDF（降级）"""
        # 优先尝试 Embedding 向量搜索
        try:
            return self._embedding_search(query, items, top_k)
        except ImportError:
            pass
        except Exception as exc:
            logger.debug("Embedding 检索失败，降级为 TF-IDF: %s", exc)

        # TF-IDF 降级
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        corpus = [item["content"] for item in items]
        corpus.append(query)

        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(corpus)

        query_vec = tfidf_matrix[-1:]
        doc_vecs = tfidf_matrix[:-1]
        similarities = cosine_similarity(query_vec, doc_vecs).flatten()

        scored = list(zip(items, similarities))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, score in scored[:top_k]]

    def _embedding_search(self, query: str, items: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """sentence-transformers Embedding 向量检索（语义匹配）

        使用 all-MiniLM-L6-v2 轻量模型，支持中英文语义匹配。
        无 sentence-transformers 时抛 ImportError 触发降级。
        """
        from sentence_transformers import SentenceTransformer
        import numpy as np

        # 懒加载模型（单例缓存）
        if not hasattr(self, "_st_model"):
            self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("L2 Embedding 模型加载完成: all-MiniLM-L6-v2")

        model = self._st_model

        # 编码查询和文档
        contents = [item["content"] for item in items]
        doc_embeddings = model.encode(contents, convert_to_numpy=True, show_progress_bar=False)
        query_embedding = model.encode([query], convert_to_numpy=True, show_progress_bar=False)

        # 余弦相似度
        similarities = np.dot(doc_embeddings, query_embedding[0]) / (
            np.linalg.norm(doc_embeddings, axis=1) * np.linalg.norm(query_embedding[0]) + 1e-8
        )

        scored = list(zip(items, similarities.tolist()))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, score in scored[:top_k]]

    def _keyword_search(self, query: str, items: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """关键词匹配降级检索"""
        query_lower = query.lower()
        scored = []
        for item in items:
            content_lower = item.get("content", "").lower()
            score = sum(1 for word in query_lower.split() if word in content_lower)
            scored.append((item, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, score in scored[:top_k]]

    # ── 工具方法 ────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        """ORM 行转字典（B3: 从 metadata 提取 source/sentiment/scope 供 RecallScorer 使用）"""
        metadata = json.loads(row.metadata_json) if row.metadata_json else {}
        return {
            "id": row.id,
            "symbol": row.symbol,
            "content": row.content,
            "metadata": metadata,
            "timestamp": row.timestamp,
            "expiresAt": row.expires_at,
            "confidence": row.confidence,
            # B3: 提取 RecallScorer shallow tier 所需字段到顶层
            "source": metadata.get("source") or "unknown",
            "sentiment_score": metadata.get("sentiment_score", 0.0),
            "scope": metadata.get("scope", "individual"),
        }

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
                asyncio.run(self._engine.dispose())
        self._engine = None
        self._session_factory = None
