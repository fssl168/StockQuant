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
    op.drop_index("ix_pending_order_user_id", table_name="pending_orders")
    op.drop_table("pending_orders")


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
