# -*- coding: utf-8 -*-
"""Add user risk_profile columns and user_profile_history table

Revision ID: 007_add_user_risk_profile
Revises: 006_add_indexes
Create Date: 2026-06-27 00:00:00

为 F020 FinMem Profiling 模块补齐数据库 schema：
1. users 表新增 risk_profile 字段（String(20), NOT NULL, default 'neutral'）
2. users 表新增 profile_updated_at 字段（DateTime, NULL）
3. 创建 user_profile_history 表（风险偏好转换历史）
4. 创建 ix_user_profile_history_timestamp 索引

兼容性：
- PostgreSQL：使用 ALTER TABLE ADD COLUMN IF NOT EXISTS
- SQLite：使用 try/except 容错已存在列
- 已存在的 users 行会被回填 risk_profile='neutral'
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '007_add_user_risk_profile'
down_revision = '006_add_indexes'
branch_labels = None
depends_on = None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    """检查列是否已存在（跨方言兼容）"""
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in columns


def _table_exists(bind, table_name: str) -> bool:
    """检查表是否已存在"""
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    print(f"[007_add_user_risk_profile] dialect={dialect}")

    # ─── 1. users 表添加 risk_profile 字段 ─────────────────────────
    if not _column_exists(bind, 'users', 'risk_profile'):
        try:
            op.add_column(
                'users',
                sa.Column(
                    'risk_profile',
                    sa.String(length=20),
                    nullable=False,
                    server_default='neutral',
                ),
            )
            print("[007_add_user_risk_profile] users.risk_profile column added (default='neutral')")
        except Exception as exc:
            print(f"[007_add_user_risk_profile] users.risk_profile skipped: {exc}")
    else:
        print("[007_add_user_risk_profile] users.risk_profile already exists, skip")

    # ─── 2. users 表添加 profile_updated_at 字段 ───────────────────
    if not _column_exists(bind, 'users', 'profile_updated_at'):
        try:
            op.add_column(
                'users',
                sa.Column(
                    'profile_updated_at',
                    sa.DateTime,
                    nullable=True,
                ),
            )
            print("[007_add_user_risk_profile] users.profile_updated_at column added")
        except Exception as exc:
            print(f"[007_add_user_risk_profile] users.profile_updated_at skipped: {exc}")
    else:
        print("[007_add_user_risk_profile] users.profile_updated_at already exists, skip")

    # ─── 3. 回填已存在 users 行的 risk_profile='neutral'（仅 PostgreSQL） ───
    # SQLite 在 add_column 时已通过 server_default 自动回填
    if dialect == 'postgresql':
        try:
            bind.execute(sa.text("UPDATE users SET risk_profile='neutral' WHERE risk_profile IS NULL OR risk_profile=''"))
            print("[007_add_user_risk_profile] backfilled existing rows with risk_profile='neutral'")
        except Exception as exc:
            print(f"[007_add_user_risk_profile] backfill skipped: {exc}")

    # ─── 4. 创建 user_profile_history 表 ───────────────────────────
    if not _table_exists(bind, 'user_profile_history'):
        try:
            op.create_table(
                'user_profile_history',
                sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
                sa.Column(
                    'user_id',
                    sa.String(length=50),
                    sa.ForeignKey('users.id'),
                    nullable=False,
                ),
                sa.Column('from_profile', sa.String(length=20), nullable=False),
                sa.Column('to_profile', sa.String(length=20), nullable=False),
                sa.Column('trigger', sa.String(length=50), nullable=False),
                sa.Column('context_json', sa.Text, nullable=False, server_default='{}'),
                sa.Column(
                    'timestamp',
                    sa.DateTime,
                    nullable=False,
                    server_default=sa.func.now(),
                ),
            )
            print("[007_add_user_risk_profile] user_profile_history table created")
        except Exception as exc:
            print(f"[007_add_user_risk_profile] user_profile_history creation skipped: {exc}")
    else:
        print("[007_add_user_risk_profile] user_profile_history already exists, skip")

    # ─── 5. 创建索引 ───────────────────────────────────────────────
    # user_profile_history.user_id 索引
    try:
        op.create_index(
            'ix_user_profile_history_user_id',
            'user_profile_history',
            ['user_id'],
        )
        print("[007_add_user_risk_profile] ix_user_profile_history_user_id created")
    except Exception as exc:
        print(f"[007_add_user_risk_profile] ix_user_profile_history_user_id skipped: {exc}")

    # user_profile_history.timestamp 索引
    try:
        op.create_index(
            'ix_user_profile_history_timestamp',
            'user_profile_history',
            ['timestamp'],
        )
        print("[007_add_user_risk_profile] ix_user_profile_history_timestamp created")
    except Exception as exc:
        print(f"[007_add_user_risk_profile] ix_user_profile_history_timestamp skipped: {exc}")


def downgrade() -> None:
    # 删除 user_profile_history 表（含索引）
    try:
        op.drop_table('user_profile_history')
        print("[007_add_user_risk_profile] user_profile_history table dropped")
    except Exception:
        pass

    # 删除 users.profile_updated_at 字段
    try:
        op.drop_column('users', 'profile_updated_at')
        print("[007_add_user_risk_profile] users.profile_updated_at dropped")
    except Exception:
        pass

    # 删除 users.risk_profile 字段
    try:
        op.drop_column('users', 'risk_profile')
        print("[007_add_user_risk_profile] users.risk_profile dropped")
    except Exception:
        pass
