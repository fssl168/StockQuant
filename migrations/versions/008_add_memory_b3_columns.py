# -*- coding: utf-8 -*-
"""Add B3 enhancement columns to l2_memory and l3_memory tables

Revision ID: 008_add_memory_b3_columns
Revises: 007_add_user_risk_profile
Create Date: 2026-06-27 01:00:00

为 F020 FinMem Memory 模块 B3 增强补齐数据库 schema：

l2_memory 表：
- expires_at: 过期时间（String(30), NULL）

l3_memory 表：
- tier: 分层（shallow/intermediate/deep/working），NOT NULL DEFAULT 'intermediate'
- period_type: 周期类型（quarterly/annual/ad_hoc），NULL
- importance_score: 重要性评分 0.0-1.0，NOT NULL DEFAULT 0.5
- last_accessed_at: 最后访问时间 ISO 字符串，NULL

新增索引：
- ix_l3_tier: 按 tier 检索
- ix_l3_symbol_tier: 按 (symbol, tier) 复合检索

兼容性：
- PostgreSQL：使用 ALTER TABLE ADD COLUMN IF NOT EXISTS
- SQLite：使用 try/except 容错已存在列
- 已存在的 l3_memory 行会被回填 tier='intermediate' / importance_score=0.5
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '008_add_memory_b3_columns'
down_revision = '007_add_user_risk_profile'
branch_labels = None
depends_on = None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    """检查列是否已存在（跨方言兼容）"""
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in columns


def _index_exists(bind, index_name: str) -> bool:
    """检查索引是否已存在"""
    inspector = sa.inspect(bind)
    for table_name in inspector.get_table_names():
        indexes = inspector.get_indexes(table_name)
        for idx in indexes:
            if idx['name'] == index_name:
                return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    print(f"[008_add_memory_b3_columns] dialect={dialect}")

    # ─── 1. l2_memory 添加 expires_at 字段 ────────────────────────
    if not _column_exists(bind, 'l2_memory', 'expires_at'):
        try:
            op.add_column(
                'l2_memory',
                sa.Column('expires_at', sa.String(length=30), nullable=True),
            )
            print("[008_add_memory_b3_columns] l2_memory.expires_at column added")
        except Exception as exc:
            print(f"[008_add_memory_b3_columns] l2_memory.expires_at skipped: {exc}")
    else:
        print("[008_add_memory_b3_columns] l2_memory.expires_at already exists, skip")

    # ─── 2. l3_memory 添加 tier 字段 ───────────────────────────────
    if not _column_exists(bind, 'l3_memory', 'tier'):
        try:
            op.add_column(
                'l3_memory',
                sa.Column(
                    'tier',
                    sa.String(length=20),
                    nullable=False,
                    server_default='intermediate',
                ),
            )
            print("[008_add_memory_b3_columns] l3_memory.tier column added (default='intermediate')")
        except Exception as exc:
            print(f"[008_add_memory_b3_columns] l3_memory.tier skipped: {exc}")
    else:
        print("[008_add_memory_b3_columns] l3_memory.tier already exists, skip")

    # ─── 3. l3_memory 添加 period_type 字段 ────────────────────────
    if not _column_exists(bind, 'l3_memory', 'period_type'):
        try:
            op.add_column(
                'l3_memory',
                sa.Column('period_type', sa.String(length=20), nullable=True),
            )
            print("[008_add_memory_b3_columns] l3_memory.period_type column added")
        except Exception as exc:
            print(f"[008_add_memory_b3_columns] l3_memory.period_type skipped: {exc}")
    else:
        print("[008_add_memory_b3_columns] l3_memory.period_type already exists, skip")

    # ─── 4. l3_memory 添加 importance_score 字段 ───────────────────
    if not _column_exists(bind, 'l3_memory', 'importance_score'):
        try:
            op.add_column(
                'l3_memory',
                sa.Column(
                    'importance_score',
                    sa.Float,
                    nullable=False,
                    server_default='0.5',
                ),
            )
            print("[008_add_memory_b3_columns] l3_memory.importance_score column added (default=0.5)")
        except Exception as exc:
            print(f"[008_add_memory_b3_columns] l3_memory.importance_score skipped: {exc}")
    else:
        print("[008_add_memory_b3_columns] l3_memory.importance_score already exists, skip")

    # ─── 5. l3_memory 添加 last_accessed_at 字段 ──────────────────
    if not _column_exists(bind, 'l3_memory', 'last_accessed_at'):
        try:
            op.add_column(
                'l3_memory',
                sa.Column('last_accessed_at', sa.String(length=30), nullable=True),
            )
            print("[008_add_memory_b3_columns] l3_memory.last_accessed_at column added")
        except Exception as exc:
            print(f"[008_add_memory_b3_columns] l3_memory.last_accessed_at skipped: {exc}")
    else:
        print("[008_add_memory_b3_columns] l3_memory.last_accessed_at already exists, skip")

    # ─── 6. 回填已存在 l3_memory 行的默认值（仅 PostgreSQL） ─────────
    if dialect == 'postgresql':
        try:
            bind.execute(sa.text("UPDATE l3_memory SET tier='intermediate' WHERE tier IS NULL OR tier=''"))
            bind.execute(sa.text("UPDATE l3_memory SET importance_score=0.5 WHERE importance_score IS NULL"))
            print("[008_add_memory_b3_columns] backfilled l3_memory defaults")
        except Exception as exc:
            print(f"[008_add_memory_b3_columns] backfill skipped: {exc}")

    # ─── 7. 创建索引 ───────────────────────────────────────────────
    if not _index_exists(bind, 'ix_l3_tier'):
        try:
            op.create_index('ix_l3_tier', 'l3_memory', ['tier'])
            print("[008_add_memory_b3_columns] ix_l3_tier created")
        except Exception as exc:
            print(f"[008_add_memory_b3_columns] ix_l3_tier skipped: {exc}")

    if not _index_exists(bind, 'ix_l3_symbol_tier'):
        try:
            op.create_index('ix_l3_symbol_tier', 'l3_memory', ['symbol', 'tier'])
            print("[008_add_memory_b3_columns] ix_l3_symbol_tier created")
        except Exception as exc:
            print(f"[008_add_memory_b3_columns] ix_l3_symbol_tier skipped: {exc}")


def downgrade() -> None:
    # 删除索引
    try:
        op.drop_index('ix_l3_symbol_tier', table_name='l3_memory')
    except Exception:
        pass
    try:
        op.drop_index('ix_l3_tier', table_name='l3_memory')
    except Exception:
        pass

    # 删除 l3_memory 字段
    for col in ['last_accessed_at', 'importance_score', 'period_type', 'tier']:
        try:
            op.drop_column('l3_memory', col)
        except Exception:
            pass

    # 删除 l2_memory 字段
    try:
        op.drop_column('l2_memory', 'expires_at')
    except Exception:
        pass
