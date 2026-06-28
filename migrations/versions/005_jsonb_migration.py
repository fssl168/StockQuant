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
# 兼容不同版本的 schema：旧版用 metrics/trades_summary，新版用 trades
_JSONB_COLUMNS = [
    ("backtest_results", "metrics"),
    ("backtest_results", "equity_curve"),
    ("backtest_results", "trades_summary"),
    ("backtest_results", "trades"),
]


def upgrade() -> None:
    bind = op.get_bind()
    # 仅 PostgreSQL 执行 JSONB 迁移；SQLite 等方言跳过
    if bind.dialect.name != 'postgresql':
        print(f"[005_jsonb_migration] dialect={bind.dialect.name}, skip JSONB migration")
        return

    from sqlalchemy.dialects import postgresql

    # 先检查表中实际存在哪些 text 列
    inspector = sa.inspect(bind)
    existing_text_columns = set()
    for table, _ in _JSONB_COLUMNS:
        if table in inspector.get_table_names():
            cols = inspector.get_columns(table)
            for col in cols:
                col_type = col['type'].sqltype if hasattr(col['type'], 'sqltype') else col['type']
                type_name = str(col_type).lower()
                if 'text' in type_name or 'varchar' in type_name or 'character' in type_name:
                    existing_text_columns.add((table, col['name']))

    for table, column in _JSONB_COLUMNS:
        if (table, column) not in existing_text_columns:
            print(f"[005_jsonb_migration] {table}.{column} does not exist or not text type, skip")
            continue
        # 使用 savepoint 隔离每个操作，避免单个失败导致整个事务回滚
        try:
            op.execute(f"SAVEPOINT sp_{table}_{column}")
            op.alter_column(
                table,
                column,
                type_=postgresql.JSONB(astext_type=sa.Text()),
                postgresql_using=f"{column}::jsonb",
            )
            op.execute(f"RELEASE SAVEPOINT sp_{table}_{column}")
            print(f"[005_jsonb_migration] {table}.{column} -> JSONB OK")
        except Exception as exc:
            try:
                op.execute(f"ROLLBACK TO SAVEPOINT sp_{table}_{column}")
            except Exception:
                pass
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
