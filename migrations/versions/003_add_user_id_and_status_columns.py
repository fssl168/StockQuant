# -*- coding: utf-8 -*-
"""Add user_id columns and missing status fields to all tables

Revision ID: 003_add_user_id_and_status_columns
Revises: 002_kline_unique_index
Create Date: 2024-06-25 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '003_add_user_id_and_status_columns'
down_revision = '002_kline_unique_index'
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = [
        "backtest_tasks", "strategies", "collect_tasks", "optimize_tasks",
        "comparison_history", "pending_orders", "orders_audit",
        "monitor_alerts", "scheduler_tasks", "notifications",
        "l2_memory", "l3_memory", "watchlist", "equity_snapshots",
    ]
    for table in tables:
        try:
            op.add_column(table, sa.Column("user_id", sa.String(50), nullable=True))
            op.create_index(f"ix_{table}_user_id", table, ["user_id"])
        except Exception:
            pass
    try:
        op.add_column("orders_audit", sa.Column("from_status", sa.String(20), nullable=True))
        op.add_column("orders_audit", sa.Column("to_status", sa.String(20), nullable=True))
    except Exception:
        pass


def downgrade() -> None:
    pass
