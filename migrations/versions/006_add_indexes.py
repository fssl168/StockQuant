# -*- coding: utf-8 -*-
"""Add composite indexes for performance optimization

Revision ID: 006_add_indexes
Revises: 005_jsonb_migration
Create Date: 2025-06-24 00:01:00

新增复合索引以优化高频查询场景：
- orders(user_id, status): 按用户筛选特定状态订单
- positions(user_id, symbol): 唯一约束已存在于模型，此处仅添加非唯一索引作为查询优化

注意：positions 表已有 UniqueConstraint("user_id", "symbol") (uq_position_user_symbol)，
本迁移只添加 orders 复合索引，避免重复创建。
"""
from __future__ import annotations

from alembic import op


revision = '006_add_indexes'
down_revision = '005_jsonb_migration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    import sqlalchemy as sa
    bind = op.get_bind()

    # 先检查索引是否已存在
    inspector = sa.inspect(bind)
    existing_indexes = set()
    if "orders" in inspector.get_table_names():
        for idx in inspector.get_indexes("orders"):
            existing_indexes.add(idx["name"])

    # orders 表复合索引 (user_id, status) — 优化按用户筛选特定状态订单的查询
    if "ix_orders_user_status" in existing_indexes:
        print("[006_add_indexes] ix_orders_user_status already exists, skip")
    else:
        try:
            op.execute("SAVEPOINT sp_orders_user_status")
            op.create_index(
                "ix_orders_user_status",
                "orders",
                ["user_id", "status"],
            )
            op.execute("RELEASE SAVEPOINT sp_orders_user_status")
            print("[006_add_indexes] ix_orders_user_status created")
        except Exception as exc:
            try:
                op.execute("ROLLBACK TO SAVEPOINT sp_orders_user_status")
            except Exception:
                pass
            print(f"[006_add_indexes] ix_orders_user_status skipped: {exc}")

    # positions 表已有 uq_position_user_symbol 唯一约束，无需重复创建
    # 如需额外非唯一索引可在此添加，但目前唯一约束已覆盖 (user_id, symbol) 查询


def downgrade() -> None:
    try:
        op.execute("SAVEPOINT sp_drop_idx")
        op.drop_index("ix_orders_user_status", table_name="orders")
        op.execute("RELEASE SAVEPOINT sp_drop_idx")
    except Exception:
        try:
            op.execute("ROLLBACK TO SAVEPOINT sp_drop_idx")
        except Exception:
            pass
