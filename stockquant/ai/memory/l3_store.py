# -*- coding: utf-8 -*-
"""F020 L3 长期记忆 — PostgreSQL + pgvector 向量存储，降级到内存"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.memory.l3")


def _default_db_url() -> str:
    """获取默认数据库 URL"""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://stockquant:stockquant_secret@localhost:5432/stockquant",
    )


class L3Store:
    """L3 长期记忆 — PostgreSQL + pgvector 向量存储

    优先使用 PostgreSQL + pgvector 进行向量语义检索，
    pgvector 不可用时降级为 TF-IDF + 关键词匹配，
    PostgreSQL 不可用时降级为内存存储。
    """

    # 默认 tier（兼容旧调用方）
    DEFAULT_TIER = "shallow"
    DEFAULT_PERIOD_TYPE = "unspecified"

    def __init__(
        self,
        db_url: Optional[str] = None,
        embedding_dim: int = 1536,
        user_id: str = "test_user",
    ) -> None:
        self._db_url = db_url or _default_db_url()
        self._embedding_dim = embedding_dim
        self._user_id = user_id
        self._backend = "memory"  # 默认降级为内存
        self._engine = None
        self._session_factory = None
        self._has_pgvector = False
        self._entries: List[Dict[str, Any]] = []  # 内存降级后备
        # RecallScorer 实例（B3 集成）：默认使用 default 场景权重
        try:
            from .recall_scorer import RecallScorer
            self._scorer = RecallScorer(scene="default")
        except ImportError:
            self._scorer = None
        self._init_backend()

    def _init_backend(self) -> None:
        """初始化存储后端，优先 PostgreSQL + pgvector"""
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

            # 检测 pgvector 扩展是否可用
            self._check_pgvector()
            self._backend = "postgresql"
            logger.info(
                "L3 使用 PostgreSQL 后端 (pgvector=%s, url=%s)",
                self._has_pgvector, url.split("@")[-1] if "@" in url else url,
            )
            return
        except ImportError:
            logger.warning("asyncpg/SQLAlchemy 未安装，L3 降级为内存存储（重启后数据丢失）")
        except Exception as exc:
            logger.warning("PostgreSQL 连接失败: %s，L3 降级为内存存储（重启后数据丢失）", exc)

        self._engine = None
        self._session_factory = None
        self._backend = "memory"

    def _check_pgvector(self) -> None:
        """检测 pgvector 扩展是否可用"""
        try:
            import asyncio
            asyncio.get_event_loop().run_until_complete(self._ensure_pgvector())
        except Exception as exc:
            logger.warning("PostgreSQL 表创建失败: %s，L3 降级为内存存储", exc)
            raise

    async def _ensure_pgvector(self) -> None:
        """确保 pgvector 扩展已安装，并创建表结构和默认用户"""
        from stockquant.persistence.models import Base, UserModel
        from sqlalchemy import select

        async with self._engine.begin() as conn:
            # 尝试创建 pgvector 扩展
            try:
                await conn.execute(
                    __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
                )
                self._has_pgvector = True
                logger.info("pgvector 扩展已启用")
            except Exception as exc:
                logger.warning("pgvector 扩展不可用: %s，向量检索将降级为关键词匹配", exc)
                self._has_pgvector = False

        # 创建表（如果不存在）
        async with self._engine.begin() as conn:
            try:
                await conn.run_sync(Base.metadata.create_all)
            except Exception:
                # 表已存在或索引冲突，视为 PostgreSQL 后端不可靠，重抛让 _init_backend 降级
                raise

        # 确保默认用户存在
        try:
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
        except Exception as exc:
            logger.warning("L3 默认用户创建失败: %s，降级为内存存储", exc)
            raise

    # ── 同步包装器 ──────────────────────────────────────────────────────

    def write(self, item: Dict[str, Any]) -> str:
        """写入一条 L3 记忆（同步）"""
        if self._backend == "memory":
            return self._write_memory(item)
        try:
            loop = __import__("asyncio").get_event_loop()
            if loop.is_running():
                # 如果已在异步上下文中，创建任务
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(self._write_sync, item).result()
            return loop.run_until_complete(self._write_async(item))
        except RuntimeError:
            loop = __import__("asyncio").new_event_loop()
            return loop.run_until_complete(self._write_async(item))

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """语义检索（同步）"""
        if self._backend == "memory":
            return self._search_memory(query, top_k)
        try:
            loop = __import__("asyncio").get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(self._search_sync, query, top_k).result()
            return loop.run_until_complete(self._search_async(query, top_k))
        except RuntimeError:
            loop = __import__("asyncio").new_event_loop()
            return loop.run_until_complete(self._search_async(query, top_k))

    def count(self) -> int:
        """返回当前条目总数"""
        if self._backend == "memory":
            return len(self._entries)
        try:
            loop = __import__("asyncio").get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(self._count_sync).result()
            return loop.run_until_complete(self._count_async())
        except RuntimeError:
            loop = __import__("asyncio").new_event_loop()
            return loop.run_until_complete(self._count_async())

    def delete(self, item_id: str) -> bool:
        """删除指定条目"""
        if self._backend == "memory":
            before = len(self._entries)
            self._entries = [e for e in self._entries if e.get("id") != item_id]
            return len(self._entries) < before
        try:
            loop = __import__("asyncio").get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(self._delete_sync, item_id).result()
            return loop.run_until_complete(self._delete_async(item_id))
        except RuntimeError:
            loop = __import__("asyncio").new_event_loop()
            return loop.run_until_complete(self._delete_async(item_id))

    def clear_all(self) -> int:
        """清空所有条目（用于测试）"""
        if self._backend == "memory":
            n = len(self._entries)
            self._entries.clear()
            return n
        try:
            loop = __import__("asyncio").get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(self._clear_all_sync).result()
            return loop.run_until_complete(self._clear_all_async())
        except RuntimeError:
            loop = __import__("asyncio").new_event_loop()
            return loop.run_until_complete(self._clear_all_async())

    def _clear_all_sync(self) -> int:
        loop = __import__("asyncio").new_event_loop()
        try:
            return loop.run_until_complete(self._clear_all_async())
        finally:
            loop.close()

    def get_all(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """获取所有条目（用于遗忘机制）"""
        if self._backend == "memory":
            return self._entries[:limit]
        try:
            loop = __import__("asyncio").get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(self._get_all_sync, limit).result()
            return loop.run_until_complete(self._get_all_async(limit))
        except RuntimeError:
            loop = __import__("asyncio").new_event_loop()
            return loop.run_until_complete(self._get_all_async(limit))

    # ── B3: 分层检索接口 ───────────────────────────────────────────────

    def search_by_tier(
        self,
        query: str,
        tier: str = "shallow",
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """按 tier 检索（B3 新增）

        Args:
            query: 查询关键词
            tier: 记忆层级 (shallow|intermediate|deep|working)
                  - shallow: 浅层-市场新闻（3天半衰期）
                  - intermediate: 中层-季报（90天半衰期）
                  - deep: 深层-年报（365天半衰期）
                  - working: 工作记忆（1天半衰期，通常不入 L3）
            top_k: 返回最大条目数

        Returns:
            按 RecallScorer 综合评分降序排列的条目列表
        """
        if self._backend == "memory":
            items = [e for e in self._entries if e.get("tier", "shallow") == tier]
            if self._scorer is not None:
                try:
                    ranked = self._scorer.rank(
                        items, query=query, tier=tier, top_k=top_k,
                    )
                    return [self._refresh_last_accessed(item) for item, _ in ranked]
                except Exception as exc:
                    logger.debug("RecallScorer 评分失败，降级时间排序: %s", exc)
            # 降级：时间倒序
            items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return items[:top_k]

        # PostgreSQL 后端
        try:
            loop = __import__("asyncio").get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(
                        self._search_by_tier_sync, query, tier, top_k
                    ).result()
            return loop.run_until_complete(self._search_by_tier_async(query, tier, top_k))
        except RuntimeError:
            loop = __import__("asyncio").new_event_loop()
            return loop.run_until_complete(self._search_by_tier_async(query, tier, top_k))

    def _search_by_tier_sync(
        self, query: str, tier: str, top_k: int
    ) -> List[Dict[str, Any]]:
        loop = __import__("asyncio").new_event_loop()
        try:
            return loop.run_until_complete(self._search_by_tier_async(query, tier, top_k))
        finally:
            loop.close()

    async def _search_by_tier_async(
        self, query: str, tier: str, top_k: int
    ) -> List[Dict[str, Any]]:
        """异步按 tier 检索（B3）"""
        from stockquant.persistence.models import L3Memory
        from sqlalchemy import select

        async with self._session_factory() as session:
            stmt = (
                select(L3Memory)
                .where(L3Memory.tier == tier)
                .order_by(L3Memory.timestamp.desc())
                .limit(top_k * 3)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            items = [self._row_to_dict(row) for row in rows]

            if not items:
                return []

            # 用 RecallScorer 评分排序
            if self._scorer is not None:
                try:
                    ranked = self._scorer.rank(
                        items, query=query, tier=tier, top_k=top_k,
                    )
                    refreshed = []
                    for item, _ in ranked:
                        # 异步刷新 last_accessed_at（best-effort，不阻塞返回）
                        try:
                            await self._touch_last_accessed_async(item["id"])
                        except Exception:
                            pass
                        refreshed.append(item)
                    return refreshed
                except Exception as exc:
                    logger.debug("RecallScorer 评分失败，降级关键词: %s", exc)

            # 降级：关键词评分
            query_lower = query.lower()
            scored = []
            for item in items:
                content_lower = (item.get("content") or "").lower()
                summary_lower = (item.get("summary") or "").lower()
                score = sum(
                    1 for w in query_lower.split()
                    if w in content_lower or w in summary_lower
                )
                scored.append((item, score))
            scored.sort(key=lambda x: x[1], reverse=True)
            return [item for item, _ in scored[:top_k]]

    async def _touch_last_accessed_async(self, item_id: str) -> None:
        """刷新 last_accessed_at 字段（B3 新增）

        实现 FinMem 论文 §3.3 的"访问即刷新"机制：
        被检索到的记忆，其 last_accessed_at 应被更新为当前时间，
        使得 recency_score 计算时 age 更小（更新鲜）。
        """
        from stockquant.persistence.models import L3Memory
        from sqlalchemy import update

        async with self._session_factory() as session:
            await session.execute(
                update(L3Memory)
                .where(L3Memory.id == item_id)
                .values(last_accessed_at=datetime.now().isoformat())
            )
            await session.commit()

    def _refresh_last_accessed(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """内存模式下的 last_accessed_at 刷新（B3 新增）"""
        item["last_accessed_at"] = datetime.now().isoformat()
        return item

    # ── 同步降级方法 ────────────────────────────────────────────────────

    def _write_sync(self, item: Dict[str, Any]) -> str:
        if self._backend == "memory":
            return self._write_memory(item)
        loop = __import__("asyncio").new_event_loop()
        try:
            return loop.run_until_complete(self._write_async(item))
        finally:
            loop.close()

    def _search_sync(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        if self._backend == "memory":
            return self._search_memory(query, top_k)
        loop = __import__("asyncio").new_event_loop()
        try:
            return loop.run_until_complete(self._search_async(query, top_k))
        finally:
            loop.close()

    def _count_sync(self) -> int:
        if self._backend == "memory":
            return len(self._entries)
        loop = __import__("asyncio").new_event_loop()
        try:
            return loop.run_until_complete(self._count_async())
        finally:
            loop.close()

    def _delete_sync(self, item_id: str) -> bool:
        if self._backend == "memory":
            before = len(self._entries)
            self._entries = [e for e in self._entries if e.get("id") != item_id]
            return len(self._entries) < before
        loop = __import__("asyncio").new_event_loop()
        try:
            return loop.run_until_complete(self._delete_async(item_id))
        finally:
            loop.close()

    def _get_all_sync(self, limit: int) -> List[Dict[str, Any]]:
        if self._backend == "memory":
            return self._entries[:limit]
        loop = __import__("asyncio").new_event_loop()
        try:
            return loop.run_until_complete(self._get_all_async(limit))
        finally:
            loop.close()

    # ── 异步 PostgreSQL 操作 ─────────────────────────────────────────────

    async def _write_async(self, item: Dict[str, Any]) -> str:
        """异步写入 PostgreSQL（B3: 支持 tier/period_type/importance_score）"""
        from stockquant.persistence.models import L3Memory
        from sqlalchemy import select

        item_id = item.get("id", f"l3_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(item)}")

        async with self._session_factory() as session:
            # 检查是否已存在
            existing = await session.execute(
                select(L3Memory).where(L3Memory.id == item_id)
            )
            row = existing.scalar_one_or_none()

            metadata = item.get("metadata", {})
            if not isinstance(metadata, str):
                metadata = json.dumps(metadata, ensure_ascii=False)

            user_id = item.get("user_id") or self._user_id
            now_iso = datetime.now().isoformat()

            # B3: 默认 tier=shallow（兼容旧调用方）；支持新字段 period_type/importance_score
            tier = item.get("tier") or self.DEFAULT_TIER
            period_type = item.get("period_type") or self.DEFAULT_PERIOD_TYPE
            importance_score = float(item.get("importance_score", 0.5))

            if row:
                row.symbol = item.get("symbol", "")
                row.user_id = user_id
                row.content = item.get("content", "")
                row.summary = item.get("summary", "")
                row.metadata_json = metadata
                row.timestamp = item.get("timestamp", now_iso)
                row.confidence = item.get("confidence", 1.0)
                # B3: 更新分层字段（仅当新值非默认时覆盖，避免重写覆盖已有 tier）
                if item.get("tier"):
                    row.tier = tier
                if item.get("period_type"):
                    row.period_type = period_type
                if "importance_score" in item:
                    row.importance_score = importance_score
                # 写入即访问：刷新 last_accessed_at
                row.last_accessed_at = now_iso
            else:
                row = L3Memory(
                    id=item_id,
                    user_id=user_id,
                    symbol=item.get("symbol", ""),
                    content=item.get("content", ""),
                    summary=item.get("summary", ""),
                    metadata_json=metadata,
                    timestamp=item.get("timestamp", now_iso),
                    confidence=item.get("confidence", 1.0),
                    tier=tier,
                    period_type=period_type,
                    importance_score=importance_score,
                    last_accessed_at=now_iso,
                )
                session.add(row)

            await session.commit()
        return item_id

    async def _search_async(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """异步语义检索（B3: 集成 RecallScorer 排序）

        优先使用 pgvector 向量检索，降级为关键词匹配，
        最终通过 RecallScorer 进行三因子融合评分排序。
        """
        from stockquant.persistence.models import L3Memory
        from sqlalchemy import select

        async with self._session_factory() as session:
            # pgvector 向量检索（返回距离后转换为相似度）
            if self._has_pgvector:
                try:
                    items = await self._search_vector(session, query, top_k * 3)
                    if items:
                        return self._rerank_with_scorer(items, query, "shallow", top_k)
                except Exception as exc:
                    logger.warning("向量检索失败: %s，降级为关键词匹配", exc)

            # 关键词匹配降级
            stmt = select(L3Memory).order_by(L3Memory.timestamp.desc()).limit(top_k * 3)
            result = await session.execute(stmt)
            rows = result.scalars().all()

            if not rows:
                return []

            items = [self._row_to_dict(row) for row in rows]
            return self._rerank_with_scorer(items, query, "shallow", top_k)

    def _rerank_with_scorer(
        self,
        items: List[Dict[str, Any]],
        query: str,
        tier: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """用 RecallScorer 对检索结果重排序（B3 集成）"""
        if self._scorer is not None:
            try:
                ranked = self._scorer.rank(
                    items, query=query, tier=tier, top_k=top_k,
                )
                return [item for item, _ in ranked]
            except Exception as exc:
                logger.debug("RecallScorer 重排序失败，降级原始顺序: %s", exc)
        return items[:top_k]

    async def _search_vector(self, session, query: str, top_k: int) -> List[Dict[str, Any]]:
        """pgvector 向量检索（需要 Embedding 服务）"""
        from sqlalchemy import text

        # 尝试获取查询向量（如果有 embedding 服务）
        query_embedding = await self._get_embedding(query)
        if query_embedding is None:
            # 没有 embedding 服务，降级为关键词匹配
            raise RuntimeError("Embedding 服务不可用")

        # 使用 pgvector 余弦距离检索
        stmt = text("""
            SELECT id, symbol, content, summary, metadata_json, timestamp, confidence,
                   embedding <=> :query_vec AS distance
            FROM l3_memory
            ORDER BY embedding <=> :query_vec
            LIMIT :limit
        """)
        result = await session.execute(
            stmt, {"query_vec": str(query_embedding), "limit": top_k}
        )
        rows = result.fetchall()

        items = []
        for row in rows:
            items.append({
                "id": row[0],
                "symbol": row[1],
                "content": row[2],
                "summary": row[3],
                "metadata": json.loads(row[4]) if row[4] else {},
                "timestamp": row[5],
                "confidence": row[6],
                "distance": row[7],
            })
        return items

    async def _get_embedding(self, text: str) -> Optional[list]:
        """获取文本的向量嵌入（B6.2: OpenAI + 本地 fallback）

        优先级：
        1. OpenAI text-embedding-3-small（云服务，质量最佳）
        2. 本地 sentence-transformers/all-MiniLM-L6-v2（降级方案，离线可用）
        3. None（无可用 embedding 服务）
        """
        # 优先尝试 OpenAI
        try:
            embedding = await self._openai_embedding(text)
            if embedding is not None:
                return embedding
        except Exception as exc:
            logger.debug("OpenAI embedding 失败，尝试本地 fallback: %s", exc)

        # 降级到本地 sentence-transformers
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

            base_url = ai_config.get("api_base") or os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{base_url}/embeddings",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": "text-embedding-3-small", "input": text[:8192]},
                )
                if resp.status_code == 200:
                    return resp.json()["data"][0]["embedding"]
        except Exception as exc:
            logger.debug("OpenAI Embedding 调用失败: %s", exc)
        return None

    def _local_embedding(self, text: str) -> Optional[list]:
        """本地 sentence-transformers embedding（B6.2 fallback）

        使用 all-MiniLM-L6-v2 模型（384 维），离线可用。
        模型在首次调用时加载（懒加载），后续缓存在实例上。
        """
        if not hasattr(self, "_local_embedder") or self._local_embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                # all-MiniLM-L6-v2: 384 维，模型大小约 80MB
                self._local_embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                logger.warning("sentence-transformers 未安装，本地 embedding 不可用")
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

    # ── B6.3: 噪音模式库 + 已证伪事实库 ──────────────────────────────────

    def get_noise_patterns(self) -> List[str]:
        """获取已知噪音模式（B6.3）

        查询 L3 中存储的噪音模式（标题党/营销号模板），供 DenoiseStage Step 4 使用。

        Returns:
            噪音模式字符串列表（去重）
        """
        try:
            records = self._query_l3_by_metadata_type("noise_pattern", limit=100)
            patterns: List[str] = []
            for r in records:
                content = r.get("content", "")
                if content:
                    patterns.append(content[:80])
            # 去重保序
            return list(dict.fromkeys(patterns))
        except Exception as exc:
            logger.debug("get_noise_patterns 失败: %s", exc)
            return []

    def get_disproved_facts(self, symbol: Optional[str] = None) -> List[str]:
        """获取已证伪事实（B6.3）

        查询 L3 中存储的已证伪事实，供 DenoiseStage Step 5 使用。

        Args:
            symbol: 可选，按 symbol 过滤

        Returns:
            已证伪事实字符串列表
        """
        try:
            records = self._query_l3_by_metadata_type(
                "disproved_fact", limit=100, symbol=symbol,
            )
            facts: List[str] = []
            for r in records:
                content = r.get("content", "")
                if content:
                    facts.append(content[:120])
            return list(dict.fromkeys(facts))
        except Exception as exc:
            logger.debug("get_disproved_facts 失败: %s", exc)
            return []

    def _query_l3_by_metadata_type(
        self,
        type_value: str,
        limit: int = 100,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """按 metadata.type 字段查询 L3（B6.3 内部辅助）

        Args:
            type_value: metadata.type 字段值（如 'noise_pattern' / 'disproved_fact'）
            limit: 返回最大条目数
            symbol: 可选 symbol 过滤
        """
        if self._backend == "memory":
            results: List[Dict[str, Any]] = []
            for entry in self._entries:
                metadata = entry.get("metadata", {})
                if not isinstance(metadata, dict):
                    try:
                        import json as _json
                        metadata = _json.loads(metadata) if metadata else {}
                    except Exception:
                        metadata = {}
                # 检查 metadata.type 或顶层 type 字段
                entry_type = metadata.get("type") or entry.get("type")
                if entry_type != type_value:
                    continue
                if symbol and entry.get("symbol") != symbol:
                    continue
                results.append(entry)
                if len(results) >= limit:
                    break
            return results

        # PostgreSQL 后端
        try:
            loop = __import__("asyncio").get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(
                        self._query_l3_by_metadata_type_sync,
                        type_value, limit, symbol,
                    ).result()
            return loop.run_until_complete(
                self._query_l3_by_metadata_type_async(type_value, limit, symbol)
            )
        except RuntimeError:
            loop = __import__("asyncio").new_event_loop()
            return loop.run_until_complete(
                self._query_l3_by_metadata_type_async(type_value, limit, symbol)
            )

    def _query_l3_by_metadata_type_sync(
        self,
        type_value: str,
        limit: int,
        symbol: Optional[str],
    ) -> List[Dict[str, Any]]:
        loop = __import__("asyncio").new_event_loop()
        try:
            return loop.run_until_complete(
                self._query_l3_by_metadata_type_async(type_value, limit, symbol)
            )
        finally:
            loop.close()

    async def _query_l3_by_metadata_type_async(
        self,
        type_value: str,
        limit: int,
        symbol: Optional[str],
    ) -> List[Dict[str, Any]]:
        """异步按 metadata.type 查询 L3（B6.3）"""
        from stockquant.persistence.models import L3Memory
        from sqlalchemy import select

        async with self._session_factory() as session:
            # metadata_json 是 JSON 字段，用 LIKE 简单匹配
            # 生产环境可改用 JSONB 查询操作符
            stmt = (
                select(L3Memory)
                .where(L3Memory.metadata_json.like(f'%"type":"{type_value}"%'))
                .order_by(L3Memory.timestamp.desc())
                .limit(limit)
            )
            if symbol:
                stmt = stmt.where(L3Memory.symbol == symbol)

            result = await session.execute(stmt)
            return [self._row_to_dict(row) for row in result.scalars().all()]

    async def _count_async(self) -> int:
        """异步计数"""
        from stockquant.persistence.models import L3Memory
        from sqlalchemy import select, func

        async with self._session_factory() as session:
            result = await session.execute(select(func.count()).select_from(L3Memory))
            return result.scalar() or 0

    async def _delete_async(self, item_id: str) -> bool:
        """异步删除"""
        from stockquant.persistence.models import L3Memory
        from sqlalchemy import delete

        async with self._session_factory() as session:
            result = await session.execute(
                delete(L3Memory).where(L3Memory.id == item_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def _get_all_async(self, limit: int) -> List[Dict[str, Any]]:
        """异步获取所有条目"""
        from stockquant.persistence.models import L3Memory
        from sqlalchemy import select

        async with self._session_factory() as session:
            stmt = select(L3Memory).order_by(L3Memory.timestamp.asc()).limit(limit)
            result = await session.execute(stmt)
            return [self._row_to_dict(row) for row in result.scalars().all()]

    async def _clear_all_async(self) -> int:
        """异步清空所有条目"""
        from stockquant.persistence.models import L3Memory
        from sqlalchemy import delete as sa_delete

        async with self._session_factory() as session:
            result = await session.execute(sa_delete(L3Memory))
            await session.commit()
            return result.rowcount

    # ── 内存降级方法 ────────────────────────────────────────────────────

    def _write_memory(self, item: Dict[str, Any]) -> str:
        item_id = item.get("id", f"l3_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(item)}")
        entry = {**item, "id": item_id}
        # Ensure user_id is present (required by L3Memory model)
        if "user_id" not in entry or not entry["user_id"]:
            entry["user_id"] = self._user_id
        # B3: 内存模式补充 tier/period_type/importance_score/last_accessed_at
        entry.setdefault("tier", self.DEFAULT_TIER)
        entry.setdefault("period_type", self.DEFAULT_PERIOD_TYPE)
        entry.setdefault("importance_score", 0.5)
        entry["last_accessed_at"] = datetime.now().isoformat()
        self._entries.append(entry)
        return item_id

    def _search_memory(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        if not self._entries:
            return []
        # B3: 用 RecallScorer 评分排序（tier=shallow 默认）
        if self._scorer is not None:
            try:
                items = self._entries[:]
                ranked = self._scorer.rank(
                    items, query=query, tier="shallow", top_k=top_k,
                )
                return [item for item, _ in ranked]
            except Exception as exc:
                logger.debug("RecallScorer 评分失败，降级关键词匹配: %s", exc)
        # 降级：关键词匹配
        query_lower = query.lower()
        scored = []
        for item in self._entries:
            content_lower = item.get("content", "").lower()
            summary_lower = item.get("summary", "").lower()
            score = sum(1 for word in query_lower.split()
                        if word in content_lower or word in summary_lower)
            scored.append((item, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, score in scored[:top_k]]

    # ── 工具方法 ────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        """ORM 行转字典（B3: 含 tier/period_type/importance_score/last_accessed_at）"""
        return {
            "id": row.id,
            "symbol": row.symbol,
            "content": row.content,
            "summary": row.summary,
            "metadata": json.loads(row.metadata_json) if row.metadata_json else {},
            "timestamp": row.timestamp,
            "confidence": row.confidence,
            # B3: 新增分层字段
            "tier": getattr(row, "tier", "shallow"),
            "period_type": getattr(row, "period_type", "unspecified"),
            "importance_score": float(getattr(row, "importance_score", 0.5) or 0.5),
            "last_accessed_at": getattr(row, "last_accessed_at", None),
        }

    def close(self) -> None:
        """关闭连接"""
        if self._engine:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 不能在运行中的 loop 里 close，安排清理
                    loop.create_task(self._engine.dispose())
                else:
                    loop.run_until_complete(self._engine.dispose())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self._engine.dispose())
        self._engine = None
        self._session_factory = None
