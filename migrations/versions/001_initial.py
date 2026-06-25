"""Initial migration - create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-06-21

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table first (foreign key target)
    op.create_table('users',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('username', sa.String(100), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(200), nullable=False),
        sa.Column('roles', sa.String(200), nullable=False, default='VIEWER'),
        sa.Column('disabled', sa.Boolean, nullable=False, default=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    
    # Create backtest_results table
    op.create_table('backtest_results',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(50), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('strategy_name', sa.String(100), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('start_date', sa.String(10), nullable=False),
        sa.Column('end_date', sa.String(10), nullable=False),
        sa.Column('initial_cash', sa.Float, nullable=False, default=1_000_000.0),
        sa.Column('final_equity', sa.Float, nullable=False, default=0.0),
        sa.Column('metrics', sa.Text, nullable=False),
        sa.Column('equity_curve', sa.Text, nullable=False),
        sa.Column('trades_summary', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_backtest_strategy', 'backtest_results', ['strategy_name'])
    op.create_index('ix_backtest_user_id', 'backtest_results', ['user_id'])
    
    # Create kline_data table
    op.create_table('kline_data',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('timeframe', sa.String(8), nullable=False, default='1d'),
        sa.Column('datetime', sa.DateTime, nullable=False, index=True),
        sa.Column('open', sa.Float, nullable=False),
        sa.Column('high', sa.Float, nullable=False),
        sa.Column('low', sa.Float, nullable=False),
        sa.Column('close', sa.Float, nullable=False),
        sa.Column('volume', sa.Integer, nullable=False, default=0),
        sa.Column('amount', sa.Float, nullable=False, default=0.0),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_kline_symbol_timeframe', 'kline_data', ['symbol', 'timeframe'])
    op.create_index('ix_kline_symbol_datetime', 'kline_data', ['symbol', 'datetime'])
    op.create_unique_constraint('uq_kline_symbol_tf_dt', 'kline_data', ['symbol', 'timeframe', 'datetime'])
    
    # Create strategies table
    op.create_table('strategies',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(50), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('code', sa.Text, nullable=False),
        sa.Column('parameters', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=sa.func.now()),
    )
    op.create_index('ix_strategy_name', 'strategies', ['name'])
    op.create_index('ix_strategy_user_id', 'strategies', ['user_id'])
    
    # Create trading_accounts table
    op.create_table('trading_accounts',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(50), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('cash', sa.Float, nullable=False, default=1_000_000.0),
        sa.Column('frozen_cash', sa.Float, nullable=False, default=0.0),
        sa.Column('available_cash', sa.Float, nullable=False, default=1_000_000.0),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=sa.func.now()),
    )
    op.create_index('ix_trading_account_user_id', 'trading_accounts', ['user_id'])
    
    # Create positions table
    op.create_table('positions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(50), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('symbol', sa.String(16), nullable=False),
        sa.Column('quantity', sa.Integer, nullable=False, default=0),
        sa.Column('available_quantity', sa.Integer, nullable=False, default=0),
        sa.Column('cost_price', sa.Float, nullable=False, default=0.0),
        sa.Column('frozen_quantity', sa.Integer, nullable=False, default=0),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=sa.func.now()),
    )
    op.create_unique_constraint('uq_position_user_symbol', 'positions', ['user_id', 'symbol'])
    op.create_index('ix_position_user_id', 'positions', ['user_id'])
    
    # Create orders table
    op.create_table('orders',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(50), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('symbol', sa.String(16), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('order_type', sa.String(20), nullable=False),
        sa.Column('price', sa.Float, nullable=False, default=0.0),
        sa.Column('quantity', sa.Integer, nullable=False),
        sa.Column('filled_quantity', sa.Integer, nullable=False, default=0),
        sa.Column('avg_fill_price', sa.Float, nullable=False, default=0.0),
        sa.Column('status', sa.String(20), nullable=False, default='PENDING'),
        sa.Column('broker_order_id', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=sa.func.now()),
    )
    op.create_index('ix_order_user_id', 'orders', ['user_id'])
    op.create_index('ix_order_status', 'orders', ['status'])
    
    # Create cash_flows table
    op.create_table('cash_flows',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(50), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('amount', sa.Float, nullable=False),
        sa.Column('balance_after', sa.Float, nullable=False),
        sa.Column('related_order_id', sa.String(64), nullable=True),
        sa.Column('remark', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, default=sa.func.now()),
    )
    op.create_index('ix_cash_flow_user_id', 'cash_flows', ['user_id'])
    op.create_index('ix_cash_flow_created_at', 'cash_flows', ['created_at'])
    
    # Create position_snapshots table
    op.create_table('position_snapshots',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(50), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('symbol', sa.String(16), nullable=False),
        sa.Column('quantity', sa.Integer, nullable=False),
        sa.Column('cost_price', sa.Float, nullable=False),
        sa.Column('market_value', sa.Float, nullable=False, default=0.0),
        sa.Column('snapshot_date', sa.String(10), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, default=sa.func.now()),
    )
    op.create_unique_constraint('uq_pos_snap_user_sym_date', 'position_snapshots', ['user_id', 'symbol', 'snapshot_date'])
    op.create_index('ix_pos_snap_user_id', 'position_snapshots', ['user_id'])
    
    # Create risk_events table
    op.create_table('risk_events',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(50), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(10), nullable=False, default='WARNING'),
        sa.Column('detail', sa.Text, nullable=True),
        sa.Column('order_id', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, default=sa.func.now()),
    )
    op.create_index('ix_risk_event_user_id', 'risk_events', ['user_id'])
    op.create_index('ix_risk_event_severity', 'risk_events', ['severity'])
    
    # Create op_audit_logs table
    op.create_table('op_audit_logs',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(50), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.String(64), nullable=True),
        sa.Column('detail', sa.Text, nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, default=sa.func.now()),
    )
    op.create_index('ix_op_audit_user_id', 'op_audit_logs', ['user_id'])
    op.create_index('ix_op_audit_action', 'op_audit_logs', ['action'])
    op.create_index('ix_op_audit_created_at', 'op_audit_logs', ['created_at'])


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_table('op_audit_logs')
    op.drop_table('risk_events')
    op.drop_table('position_snapshots')
    op.drop_table('cash_flows')
    op.drop_table('orders')
    op.drop_table('positions')
    op.drop_table('trading_accounts')
    op.drop_table('strategies')
    op.drop_table('kline_data')
    op.drop_table('backtest_results')
    op.drop_table('users')
