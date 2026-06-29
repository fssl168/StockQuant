# -*- coding: utf-8 -*-
"""Add reports table for daily/monthly/annual report system

Revision ID: 009_add_reports_table
Revises: 008_add_memory_b3_columns
Create Date: 2026-06-29 10:00:00

为 F020 报告系统（日报/月报/年报）创建 reports 表。

字段说明：
- id: 报告唯一标识（String(100), PK）
- user_id: 用户 ID（FK → users.id, indexed）
- report_type: 报告类型（daily/monthly/annual, NOT NULL）
- report_date: 报告日期 YYYY-MM-DD（NOT NULL）
- report_period_start/end: 报告覆盖的起止日期（NOT NULL）
- market_review: 市场回顾文本
- trading_record: 交易记录文本
- strategy_performance: 策略表现文本
- ai_insights: AI 洞察文本
- metrics_json: 关键指标 JSON
- metadata_json: 扩展元数据 JSON
- full_content: 四大板块拼接全文（用于语义检索）
- summary: 摘要
- embedding: pgvector 向量（若可用）
- confidence: 置信度 0.0-1.0
- importance_score: 重要性评分 0.0-1.0
- last_accessed_at: 最后访问时间
- created_at: 创建时间（NOT NULL）
- updated_at: 更新时间

索引：
- ix_report_type_date: (report_type, report_date) 复合索引
- ix_report_user_id: user_id 单列索引
- ix_report_period: (report_period_start, report_period_end) 复合索引

兼容性：
- PostgreSQL + pgvector: embedding 使用 Vector(1536) 类型
- PostgreSQL 无 pgvector: embedding 使用 Text 类型
- SQLite: embedding 使用 Text 类型
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '009_add_reports_table'
down_revision = '008_add_memory_b3_columns'
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    """检查表是否已存在"""
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    """检查列是否已存在"""
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


def _pgvector_available(bind) -> bool:
    """检查 pgvector 扩展是否可用"""
    try:
        if bind.dialect.name != 'postgresql':
            return False
        result = bind.execute(sa.text(
            "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
        ))
        return result.scalar() is not None
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    print(f"[009_add_reports_table] dialect={dialect}")

    if _table_exists(bind, 'reports'):
        print("[009_add_reports_table] reports table already exists, skip")
        return

    # 确定 embedding 列类型
    use_pgvector = _pgvector_available(bind)

    # 创建 reports 表
    columns = [
        sa.Column('id', sa.String(length=100), primary_key=True),
        sa.Column('user_id', sa.String(length=50),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('report_type', sa.String(length=10), nullable=False,
                  comment='daily/monthly/annual'),
        sa.Column('report_date', sa.String(length=10), nullable=False,
                  comment='YYYY-MM-DD'),
        sa.Column('report_period_start', sa.String(length=10), nullable=False),
        sa.Column('report_period_end', sa.String(length=10), nullable=False),
        sa.Column('market_review', sa.Text, nullable=False, server_default=''),
        sa.Column('trading_record', sa.Text, nullable=False, server_default=''),
        sa.Column('strategy_performance', sa.Text, nullable=False,
                  server_default=''),
        sa.Column('ai_insights', sa.Text, nullable=False, server_default=''),
        sa.Column('metrics_json', sa.Text, nullable=False, server_default='{}'),
        sa.Column('metadata_json', sa.Text, nullable=False, server_default='{}'),
        sa.Column('full_content', sa.Text, nullable=False, server_default=''),
        sa.Column('summary', sa.Text, nullable=False, server_default=''),
        sa.Column('confidence', sa.Float, nullable=False, server_default='1.0'),
        sa.Column('importance_score', sa.Float, nullable=False,
                  server_default='0.5'),
        sa.Column('last_accessed_at', sa.String(length=30), nullable=True),
        sa.Column('created_at', sa.String(length=30), nullable=False),
        sa.Column('updated_at', sa.String(length=30), nullable=True),
    ]

    if use_pgvector:
        try:
            columns.append(
                sa.Column('embedding', sa.LargeBinary(), nullable=True)
            )
        except Exception:
            # pgvector Vector 类型不可用，降级为 Text
            columns.append(
                sa.Column('embedding', sa.Text(), nullable=True)
            )
    else:
        columns.append(
            sa.Column('embedding', sa.Text(), nullable=True)
        )

    try:
        op.create_table(
            'reports',
            *columns,
        )
        print("[009_add_reports_table] reports table created")
    except Exception as exc:
        print(f"[009_add_reports_table] reports table creation failed: {exc}")
        raise

    # 创建索引
    indexes = [
        ('ix_report_type_date', 'reports', ['report_type', 'report_date']),
        ('ix_report_user_id', 'reports', ['user_id']),
        ('ix_report_period', 'reports',
         ['report_period_start', 'report_period_end']),
    ]

    for idx_name, table_name, idx_cols in indexes:
        if not _index_exists(bind, idx_name):
            try:
                op.create_index(idx_name, table_name, idx_cols)
                print(
                    f"[009_add_reports_table] {idx_name} index created"
                )
            except Exception as exc:
                print(
                    f"[009_add_reports_table] {idx_name} skipped: {exc}"
                )


def downgrade() -> None:
    bind = op.get_bind()

    # 删除索引
    for idx_name in [
        'ix_report_period', 'ix_report_user_id', 'ix_report_type_date'
    ]:
        try:
            op.drop_index(idx_name, table_name='reports')
        except Exception:
            pass

    # 删除表
    try:
        op.drop_table('reports')
        print("[009_add_reports_table] reports table dropped")
    except Exception as exc:
        print(f"[009_add_reports_table] reports table drop failed: {exc}")
