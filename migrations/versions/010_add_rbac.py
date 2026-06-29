# -*- coding: utf-8 -*-
"""Add RBAC tables (roles, permissions, role_permissions, user_roles)

Revision ID: 010_add_rbac
Revises: 009_add_reports_table
Create Date: 2026-06-29 12:00:00

为 RBAC（基于角色的访问控制）创建 4 张表并插入初始数据：

表结构：
1. rbac_roles          — 角色定义（id, name, display_name, description, is_system, created_at）
2. rbac_permissions     — 权限定义（id, code, name, module, description, created_at）
3. rbac_role_permissions — 角色-权限关联（role_id, permission_id, UNIQUE）
4. rbac_user_roles      — 用户-角色关联（user_id, role_id, assigned_at, UNIQUE）

初始数据：
- 4 个系统角色：admin(管理员), trader(交易员), researcher(研究员), viewer(访客)
- 12 个权限定义（按模块：system/user/trade/backtest/strategy/ai/data）
- 角色权限矩阵：
  - admin: 所有权限
  - trader: trade:*, backtest:*, strategy:*, ai:chat, data:view
  - researcher: backtest:*, strategy:*, data:view, ai:chat
  - viewer: data:view, backtest:view, strategy:view, ai:chat

兼容性：
- PostgreSQL / SQLite 均可执行
- 幂等：表已存在时跳过创建
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '010_add_rbac'
down_revision = '009_add_reports_table'
branch_labels = None
depends_on = None


# ─── 初始数据定义 ───────────────────────────────────────────────────

# 4 个系统角色
_ROLES = [
    {"name": "admin",      "display_name": "管理员", "description": "系统管理员，拥有所有权限", "is_system": 1},
    {"name": "trader",     "display_name": "交易员", "description": "可执行交易、回测、策略管理", "is_system": 1},
    {"name": "researcher", "display_name": "研究员", "description": "可执行回测、策略研究、数据查看", "is_system": 1},
    {"name": "viewer",     "display_name": "访客",   "description": "仅可查看数据和只读资源", "is_system": 1},
]

# 12 个权限定义（按模块）
_PERMISSIONS = [
    # system 模块
    {"code": "system:manage",    "name": "系统管理",       "module": "system", "description": "管理系统配置、全局参数"},
    {"code": "user:manage",      "name": "用户管理",       "module": "system", "description": "管理用户账户、角色分配"},
    # trade 模块
    {"code": "trade:place_order", "name": "下单",          "module": "trade",  "description": "提交买入/卖出订单"},
    {"code": "trade:cancel_order","name": "撤单",          "module": "trade",  "description": "撤销未成交订单"},
    {"code": "trade:view",       "name": "查看交易",       "module": "trade",  "description": "查看订单、成交记录、持仓"},
    # backtest 模块
    {"code": "backtest:run",     "name": "回测执行",       "module": "backtest","description": "提交和执行回测任务"},
    {"code": "backtest:view",    "name": "查看回测",       "module": "backtest","description": "查看回测结果和历史"},
    # strategy 模块
    {"code": "strategy:write",   "name": "策略编写",       "module": "strategy","description": "创建、编辑、删除策略"},
    {"code": "strategy:view",    "name": "查看策略",       "module": "strategy","description": "查看策略列表和详情"},
    # ai 模块
    {"code": "ai:chat",          "name": "AI对话",         "module": "ai",     "description": "使用 AI 对话功能"},
    {"code": "ai:manage",        "name": "AI管理",         "module": "ai",     "description": "管理 AI 模型配置和管线"},
    # data 模块
    {"code": "data:view",        "name": "数据查看",       "module": "data",   "description": "查看行情数据和历史数据"},
]

# 角色权限矩阵
_ROLE_PERMISSIONS = {
    "admin": "*",  # 所有权限
    "trader": [
        "trade:place_order", "trade:cancel_order", "trade:view",
        "backtest:run", "backtest:view",
        "strategy:write", "strategy:view",
        "ai:chat", "data:view",
    ],
    "researcher": [
        "backtest:run", "backtest:view",
        "strategy:write", "strategy:view",
        "data:view", "ai:chat",
    ],
    "viewer": [
        "data:view", "backtest:view", "strategy:view", "ai:chat",
    ],
}


# ─── 辅助函数 ───────────────────────────────────────────────────────

def _table_exists(bind, table_name: str) -> bool:
    """检查表是否已存在"""
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _row_exists(bind, table_name: str, where_clause: str) -> bool:
    """检查某行是否已存在"""
    result = bind.execute(sa.text(f"SELECT 1 FROM {table_name} WHERE {where_clause} LIMIT 1"))
    return result.scalar() is not None


# ─── 迁移逻辑 ───────────────────────────────────────────────────────

def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    print(f"[010_add_rbac] dialect={dialect}")

    # 1. 创建 rbac_roles 表
    if not _table_exists(bind, 'rbac_roles'):
        op.create_table(
            'rbac_roles',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('name', sa.String(50), nullable=False, unique=True),
            sa.Column('display_name', sa.String(100), nullable=False),
            sa.Column('description', sa.Text, nullable=False, server_default=''),
            sa.Column('is_system', sa.Integer, nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
        print("[010_add_rbac] rbac_roles table created")
    else:
        print("[010_add_rbac] rbac_roles table already exists, skip")

    # 2. 创建 rbac_permissions 表
    if not _table_exists(bind, 'rbac_permissions'):
        op.create_table(
            'rbac_permissions',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('code', sa.String(100), nullable=False, unique=True),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('module', sa.String(50), nullable=False),
            sa.Column('description', sa.Text, nullable=False, server_default=''),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
        print("[010_add_rbac] rbac_permissions table created")
    else:
        print("[010_add_rbac] rbac_permissions table already exists, skip")

    # 3. 创建 rbac_role_permissions 表
    if not _table_exists(bind, 'rbac_role_permissions'):
        op.create_table(
            'rbac_role_permissions',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('role_id', sa.Integer,
                      sa.ForeignKey('rbac_roles.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('permission_id', sa.Integer,
                      sa.ForeignKey('rbac_permissions.id', ondelete='CASCADE'),
                      nullable=False),
            sa.UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),
        )
        op.create_index('ix_rbac_role_permissions_role_id',
                        'rbac_role_permissions', ['role_id'])
        op.create_index('ix_rbac_role_permissions_permission_id',
                        'rbac_role_permissions', ['permission_id'])
        print("[010_add_rbac] rbac_role_permissions table created")
    else:
        print("[010_add_rbac] rbac_role_permissions table already exists, skip")

    # 4. 创建 rbac_user_roles 表
    if not _table_exists(bind, 'rbac_user_roles'):
        op.create_table(
            'rbac_user_roles',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('user_id', sa.String(50),
                      sa.ForeignKey('users.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('role_id', sa.Integer,
                      sa.ForeignKey('rbac_roles.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('assigned_at', sa.DateTime, nullable=False,
                      server_default=sa.func.now()),
            sa.UniqueConstraint('user_id', 'role_id', name='uq_user_role'),
        )
        op.create_index('ix_rbac_user_roles_user_id',
                        'rbac_user_roles', ['user_id'])
        op.create_index('ix_rbac_user_roles_role_id',
                        'rbac_user_roles', ['role_id'])
        print("[010_add_rbac] rbac_user_roles table created")
    else:
        print("[010_add_rbac] rbac_user_roles table already exists, skip")

    # 5. 插入初始角色数据
    for role in _ROLES:
        if not _row_exists(bind, 'rbac_roles', f"name = '{role['name']}'"):
            bind.execute(sa.text(
                "INSERT INTO rbac_roles (name, display_name, description, is_system) "
                "VALUES (:name, :display_name, :description, :is_system)"
            ), role)
            print(f"[010_add_rbac] role inserted: {role['name']}")
        else:
            print(f"[010_add_rbac] role already exists: {role['name']}")

    # 6. 插入初始权限数据
    for perm in _PERMISSIONS:
        if not _row_exists(bind, 'rbac_permissions', f"code = '{perm['code']}'"):
            bind.execute(sa.text(
                "INSERT INTO rbac_permissions (code, name, module, description) "
                "VALUES (:code, :name, :module, :description)"
            ), perm)
            print(f"[010_add_rbac] permission inserted: {perm['code']}")
        else:
            print(f"[010_add_rbac] permission already exists: {perm['code']}")

    # 7. 插入角色-权限关联数据
    # 获取所有权限 code -> id 映射
    perm_rows = bind.execute(sa.text("SELECT id, code FROM rbac_permissions")).fetchall()
    perm_map = {row[1]: row[0] for row in perm_rows}

    # 获取所有角色 name -> id 映射
    role_rows = bind.execute(sa.text("SELECT id, name FROM rbac_roles")).fetchall()
    role_map = {row[1]: row[0] for row in role_rows}

    for role_name, perm_codes in _ROLE_PERMISSIONS.items():
        role_id = role_map.get(role_name)
        if role_id is None:
            print(f"[010_add_rbac] WARNING: role '{role_name}' not found, skip")
            continue

        if perm_codes == "*":
            # admin: 关联所有权限
            perm_ids = list(perm_map.values())
        else:
            perm_ids = [perm_map[c] for c in perm_codes if c in perm_map]

        for perm_id in perm_ids:
            # 检查关联是否已存在
            existing = bind.execute(sa.text(
                "SELECT 1 FROM rbac_role_permissions "
                "WHERE role_id = :role_id AND permission_id = :perm_id LIMIT 1"
            ), {"role_id": role_id, "perm_id": perm_id}).scalar()
            if not existing:
                bind.execute(sa.text(
                    "INSERT INTO rbac_role_permissions (role_id, permission_id) "
                    "VALUES (:role_id, :perm_id)"
                ), {"role_id": role_id, "perm_id": perm_id})

        print(f"[010_add_rbac] role '{role_name}' linked to {len(perm_ids)} permissions")

    print("[010_add_rbac] migration completed")


def downgrade() -> None:
    # 按依赖反序删除表
    for table_name in ['rbac_user_roles', 'rbac_role_permissions',
                       'rbac_permissions', 'rbac_roles']:
        try:
            op.drop_table(table_name)
            print(f"[010_add_rbac] {table_name} dropped")
        except Exception as exc:
            print(f"[010_add_rbac] {table_name} drop failed: {exc}")
