# -*- coding: utf-8 -*-
"""Migrate backtest_results JSON columns from TEXT to JSONB (PostgreSQL only)

Revision ID: 005_jsonb_migration
Revises: 004_drop_pending_orders
Create Date: 2025-06-24 00:00:00

将 backtest_results 表的 metrics / equity_curve / trades_summary 列
从 TEXT 迁移为 PostgreSQL JSONB 类型，以获得原生 JSON 查询与索引能力。
SQLite 等非 PostgreSQL 方言自动跳过（保持 TEXT 不变）。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '005_jsonb_migration'
down_revision = '004_drop_pending_orders'
branch_labels = None
depends_on = None


# 需要迁移的 (表名, 列名) 列表
_JSONB_COLUMNS = [
    ("backtest_results", "metrics"),
    ("backtest_results", "equity_curve"),
    ("backtest_results", "trades_summary"),
]


def upgrade() -> None:
    bind = op.get_bind()
    # 仅 PostgreSQL 执行 JSONB 迁移；SQLite 等方言跳过
    if bind.dialect.name != 'postgresql':
        print(f"[005_jsonb_migration] dialect={bind.dialect.name}, skip JSONB migration")
        return

    from sqlalchemy.dialects import postgresql

    for table, column in _JSONB_COLUMNS:
        try:
            op.alter_column(
                table,
                column,
                type_=postgresql.JSONB(astext_type=sa.Text()),
                postgresql_using=f"{column}::jsonb",
            )
            print(f"[005_jsonb_migration] {table}.{column} -> JSONB OK")
        except Exception as exc:
            print(f"[005_jsonb_migration] {table}.{column} skipped: {exc}")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    for table, column in _JSONB_COLUMNS:
        try:
            op.alter_column(table, column, type_=sa.Text())
        except Exception:
            pass
