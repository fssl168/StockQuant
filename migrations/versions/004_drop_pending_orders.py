# -*- coding: utf-8 -*-
"""Drop pending_orders table (deprecated, functionality merged into orders)

Revision ID: 004_drop_pending_orders
Revises: 003_add_user_id_and_status_columns
Create Date: 2025-06-23 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '004_drop_pending_orders'
down_revision = '003_add_user_id_and_status_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # 检查表是否存在
    inspector = sa.inspect(bind)
    if "pending_orders" not in inspector.get_table_names():
        print("[004_drop_pending_orders] pending_orders table does not exist, skip")
        return

    # 获取现有索引并删除
    indexes = inspector.get_indexes("pending_orders")
    for idx in indexes:
        idx_name = idx["name"]
        # 跳过主键索引
        if idx.get("unique") and idx.get("name", "").endswith("_pkey"):
            continue
        try:
            op.drop_index(idx_name, table_name="pending_orders")
            print(f"[004_drop_pending_orders] dropped index: {idx_name}")
        except Exception as exc:
            print(f"[004_drop_pending_orders] drop index {idx_name} skipped: {exc}")

    # 删除表
    try:
        op.drop_table("pending_orders")
        print("[004_drop_pending_orders] dropped table: pending_orders")
    except Exception as exc:
        print(f"[004_drop_pending_orders] drop table skipped: {exc}")


def downgrade() -> None:
    op.create_table(
        "pending_orders",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(50), nullable=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pending_order_user_id", "pending_orders", ["user_id"])
