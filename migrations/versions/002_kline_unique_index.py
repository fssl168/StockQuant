# -*- coding: utf-8 -*-
"""Add unique index to KlineData table

Revision ID: 002_kline_unique_index
Revises: 001_initial
Create Date: 2024-01-01 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_kline_unique_index'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unique index on (symbol, timeframe, datetime) for KlineData
    op.create_index(
        'uq_kline_symbol_tf_dt',
        'kline_data',
        ['symbol', 'timeframe', 'datetime'],
        unique=True
    )


def downgrade() -> None:
    op.drop_index('uq_kline_symbol_tf_dt', table_name='kline_data')
