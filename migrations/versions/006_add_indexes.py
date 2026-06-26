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
    # orders 表复合索引 (user_id, status) — 优化按用户筛选特定状态订单的查询
    try:
        op.create_index(
            "ix_orders_user_status",
            "orders",
            ["user_id", "status"],
        )
        print("[006_add_indexes] ix_orders_user_status created")
    except Exception as exc:
        print(f"[006_add_indexes] ix_orders_user_status skipped: {exc}")

    # positions 表已有 uq_position_user_symbol 唯一约束，无需重复创建
    # 如需额外非唯一索引可在此添加，但目前唯一约束已覆盖 (user_id, symbol) 查询


def downgrade() -> None:
    try:
        op.drop_index("ix_orders_user_status", table_name="orders")
    except Exception:
        pass
