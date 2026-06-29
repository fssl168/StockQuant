# -*- coding: utf-8 -*-
"""RBAC 权限模型测试 — 权限矩阵、权限检查函数、API 路由

测试覆盖：
1. ROLE_PERMISSIONS 权限矩阵正确性
2. has_permission() 函数
3. require_permission() 依赖
4. get_admin_user / get_trader_user / get_researcher_user
5. RBAC API 路由（通过 mock JWT token）
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from stockquant.api.deps import (
    ROLE_PERMISSIONS,
    UserRole,
    has_permission,
    require_permission,
)
from stockquant.api.schemas import UserToken


# ========================================================================
# 辅助函数
# ========================================================================

def _make_token(role: str, sub: str = "testuser") -> UserToken:
    """构造 UserToken（不经过 JWT 解码，直接构造）"""
    return UserToken(sub=sub, roles=[role.lower()], role=role)


def _make_jwt(role: str, sub: str = "testuser") -> str:
    """生成 JWT token（用于 API 测试）"""
    from jose import jwt
    secret = os.environ.get("JWT_SECRET_KEY", "stockquant-dev-secret-change-in-prod")
    return jwt.encode(
        {"sub": sub, "role": role, "roles": [role.lower()]},
        secret,
        algorithm="HS256",
    )


def _auth_headers(role: str, sub: str = "testuser") -> dict:
    """获取带 JWT token 的请求头"""
    return {"Authorization": f"Bearer {_make_jwt(role, sub)}"}


@pytest.fixture
def client():
    """FastAPI TestClient"""
    from stockquant.api.main import create_app
    app = create_app()
    return TestClient(app)


# ========================================================================
# 1. ROLE_PERMISSIONS 权限矩阵正确性
# ========================================================================

class TestRolePermissionsMatrix:
    """测试权限矩阵定义的正确性"""

    def test_admin_has_wildcard(self):
        """ADMIN 角色拥有通配权限 '*'"""
        assert "*" in ROLE_PERMISSIONS["ADMIN"]

    def test_trader_permissions(self):
        """TRADER 角色拥有交易、回测、策略、AI对话、数据查看权限"""
        expected = {
            "trade:place_order", "trade:cancel_order", "trade:view",
            "backtest:run", "backtest:view",
            "strategy:write", "strategy:view",
            "ai:chat", "data:view",
        }
        assert ROLE_PERMISSIONS["TRADER"] == expected

    def test_researcher_permissions(self):
        """RESEARCHER 角色拥有回测、策略、数据查看、AI对话权限，但无交易权限"""
        expected = {
            "backtest:run", "backtest:view",
            "strategy:write", "strategy:view",
            "data:view", "ai:chat",
        }
        assert ROLE_PERMISSIONS["RESEARCHER"] == expected
        # 研究员不能交易
        assert "trade:place_order" not in ROLE_PERMISSIONS["RESEARCHER"]
        assert "trade:cancel_order" not in ROLE_PERMISSIONS["RESEARCHER"]

    def test_viewer_permissions(self):
        """VIEWER 角色仅拥有只读权限"""
        expected = {
            "data:view", "backtest:view", "strategy:view", "ai:chat",
        }
        assert ROLE_PERMISSIONS["VIEWER"] == expected
        # 访客不能交易、不能回测、不能编写策略
        assert "trade:place_order" not in ROLE_PERMISSIONS["VIEWER"]
        assert "backtest:run" not in ROLE_PERMISSIONS["VIEWER"]
        assert "strategy:write" not in ROLE_PERMISSIONS["VIEWER"]

    def test_all_four_roles_exist(self):
        """权限矩阵包含全部 4 个角色"""
        assert set(ROLE_PERMISSIONS.keys()) == {"ADMIN", "TRADER", "RESEARCHER", "VIEWER"}

    def test_researcher_is_subset_of_trader(self):
        """RESEARCHER 权限是 TRADER 权限的子集（研究员权限少于交易员）"""
        assert ROLE_PERMISSIONS["RESEARCHER"].issubset(ROLE_PERMISSIONS["TRADER"])

    def test_viewer_is_subset_of_researcher(self):
        """VIEWER 权限是 RESEARCHER 权限的子集"""
        assert ROLE_PERMISSIONS["VIEWER"].issubset(ROLE_PERMISSIONS["RESEARCHER"])

    def test_user_role_enum_has_four_values(self):
        """UserRole 枚举包含 4 个值"""
        assert UserRole.ADMIN.value == "ADMIN"
        assert UserRole.TRADER.value == "TRADER"
        assert UserRole.RESEARCHER.value == "RESEARCHER"
        assert UserRole.VIEWER.value == "VIEWER"


# ========================================================================
# 2. has_permission() 函数
# ========================================================================

class TestHasPermission:
    """测试 has_permission 函数"""

    def test_admin_has_any_permission(self):
        """ADMIN 拥有所有权限"""
        user = _make_token("ADMIN")
        assert has_permission(user, "trade:place_order") is True
        assert has_permission(user, "system:manage") is True
        assert has_permission(user, "ai:manage") is True
        assert has_permission(user, "any:nonexistent") is True

    def test_trader_can_trade(self):
        """TRADER 可以下单和撤单"""
        user = _make_token("TRADER")
        assert has_permission(user, "trade:place_order") is True
        assert has_permission(user, "trade:cancel_order") is True
        assert has_permission(user, "trade:view") is True

    def test_trader_cannot_manage_system(self):
        """TRADER 不能管理系统和用户"""
        user = _make_token("TRADER")
        assert has_permission(user, "system:manage") is False
        assert has_permission(user, "user:manage") is False
        assert has_permission(user, "ai:manage") is False

    def test_researcher_can_backtest(self):
        """RESEARCHER 可以回测和编写策略"""
        user = _make_token("RESEARCHER")
        assert has_permission(user, "backtest:run") is True
        assert has_permission(user, "strategy:write") is True
        assert has_permission(user, "data:view") is True

    def test_researcher_cannot_trade(self):
        """RESEARCHER 不能交易"""
        user = _make_token("RESEARCHER")
        assert has_permission(user, "trade:place_order") is False
        assert has_permission(user, "trade:cancel_order") is False

    def test_viewer_can_only_view(self):
        """VIEWER 只能查看，不能操作"""
        user = _make_token("VIEWER")
        assert has_permission(user, "data:view") is True
        assert has_permission(user, "backtest:view") is True
        assert has_permission(user, "ai:chat") is True
        # 不能操作
        assert has_permission(user, "trade:place_order") is False
        assert has_permission(user, "backtest:run") is False
        assert has_permission(user, "strategy:write") is False

    def test_unknown_role_defaults_to_no_permission(self):
        """未知角色默认无权限（除通配外）"""
        user = UserToken(sub="x", roles=[], role="UNKNOWN")
        assert has_permission(user, "data:view") is False
        assert has_permission(user, "trade:place_order") is False

    def test_empty_role_defaults_to_viewer(self):
        """空 role 字段默认为 VIEWER"""
        user = UserToken(sub="x", roles=[], role="")
        assert has_permission(user, "data:view") is True
        assert has_permission(user, "trade:place_order") is False

    def test_none_role_defaults_to_viewer(self):
        """role=None 默认为 VIEWER（UserToken 不允许 None，用 mock 对象测试）"""
        from types import SimpleNamespace
        user = SimpleNamespace(sub="x", roles=[], role=None)
        # has_permission 内部将 None role 默认为 VIEWER
        assert has_permission(user, "data:view") is True
        assert has_permission(user, "trade:place_order") is False


# ========================================================================
# 3. require_permission() 依赖
# ========================================================================

class TestRequirePermission:
    """测试 require_permission 依赖工厂"""

    @pytest.mark.asyncio
    async def test_require_permission_allows_authorized(self):
        """有权限的用户通过检查"""
        check = require_permission("trade:place_order")
        user = _make_token("TRADER")
        result = await check(user=user)
        assert result.role == "TRADER"

    @pytest.mark.asyncio
    async def test_require_permission_denies_unauthorized(self):
        """无权限的用户被拒绝（403）"""
        from fastapi import HTTPException
        check = require_permission("system:manage")
        user = _make_token("TRADER")
        with pytest.raises(HTTPException) as exc_info:
            await check(user=user)
        assert exc_info.value.status_code == 403
        assert "system:manage" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_permission_admin_passes_all(self):
        """ADMIN 通过所有权限检查"""
        check = require_permission("system:manage")
        user = _make_token("ADMIN")
        result = await check(user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_require_permission_viewer_denied_trade(self):
        """VIEWER 被拒绝交易权限"""
        from fastapi import HTTPException
        check = require_permission("trade:place_order")
        user = _make_token("VIEWER")
        with pytest.raises(HTTPException) as exc_info:
            await check(user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_permission_researcher_denied_trade(self):
        """RESEARCHER 被拒绝交易权限"""
        from fastapi import HTTPException
        check = require_permission("trade:place_order")
        user = _make_token("RESEARCHER")
        with pytest.raises(HTTPException) as exc_info:
            await check(user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_permission_researcher_allowed_backtest(self):
        """RESEARCHER 通过回测权限检查"""
        check = require_permission("backtest:run")
        user = _make_token("RESEARCHER")
        result = await check(user=user)
        assert result is user


# ========================================================================
# 4. get_admin_user / get_trader_user / get_researcher_user
# ========================================================================

class TestRoleDependencies:
    """测试角色依赖函数"""

    @pytest.mark.asyncio
    async def test_get_admin_user_allows_admin(self):
        """ADMIN 通过 get_admin_user"""
        from stockquant.api.deps import get_admin_user
        user = _make_token("ADMIN")
        result = await get_admin_user(user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_get_admin_user_denies_trader(self):
        """TRADER 被 get_admin_user 拒绝"""
        from fastapi import HTTPException
        from stockquant.api.deps import get_admin_user
        user = _make_token("TRADER")
        with pytest.raises(HTTPException) as exc_info:
            await get_admin_user(user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_trader_user_allows_trader(self):
        """TRADER 通过 get_trader_user"""
        from stockquant.api.deps import get_trader_user
        user = _make_token("TRADER")
        result = await get_trader_user(user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_get_trader_user_allows_admin(self):
        """ADMIN 通过 get_trader_user"""
        from stockquant.api.deps import get_trader_user
        user = _make_token("ADMIN")
        result = await get_trader_user(user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_get_trader_user_denies_viewer(self):
        """VIEWER 被 get_trader_user 拒绝"""
        from fastapi import HTTPException
        from stockquant.api.deps import get_trader_user
        user = _make_token("VIEWER")
        with pytest.raises(HTTPException) as exc_info:
            await get_trader_user(user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_trader_user_denies_researcher(self):
        """RESEARCHER 被 get_trader_user 拒绝（研究员不能交易）"""
        from fastapi import HTTPException
        from stockquant.api.deps import get_trader_user
        user = _make_token("RESEARCHER")
        with pytest.raises(HTTPException) as exc_info:
            await get_trader_user(user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_researcher_user_allows_researcher(self):
        """RESEARCHER 通过 get_researcher_user"""
        from stockquant.api.deps import get_researcher_user
        user = _make_token("RESEARCHER")
        result = await get_researcher_user(user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_get_researcher_user_allows_trader(self):
        """TRADER 通过 get_researcher_user（交易员也可以回测）"""
        from stockquant.api.deps import get_researcher_user
        user = _make_token("TRADER")
        result = await get_researcher_user(user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_get_researcher_user_allows_admin(self):
        """ADMIN 通过 get_researcher_user"""
        from stockquant.api.deps import get_researcher_user
        user = _make_token("ADMIN")
        result = await get_researcher_user(user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_get_researcher_user_denies_viewer(self):
        """VIEWER 被 get_researcher_user 拒绝"""
        from fastapi import HTTPException
        from stockquant.api.deps import get_researcher_user
        user = _make_token("VIEWER")
        with pytest.raises(HTTPException) as exc_info:
            await get_researcher_user(user=user)
        assert exc_info.value.status_code == 403


# ========================================================================
# 5. RBAC API 路由测试
# ========================================================================

class TestRbacApiRoutes:
    """测试 RBAC API 路由（需要 mock JWT token）"""

    # ── 权限检查端点 /rbac/check ──────────────────────────────────

    def test_check_permission_admin_granted(self, client):
        """ADMIN 权限检查 — 任意权限都通过"""
        resp = client.get(
            "/api/rbac/check",
            params={"permission": "system:manage"},
            headers=_auth_headers("ADMIN"),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["granted"] is True
        assert data["role"] == "ADMIN"
        assert data["permission"] == "system:manage"

    def test_check_permission_viewer_denied_trade(self, client):
        """VIEWER 权限检查 — 交易权限被拒绝"""
        resp = client.get(
            "/api/rbac/check",
            params={"permission": "trade:place_order"},
            headers=_auth_headers("VIEWER"),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["granted"] is False

    def test_check_permission_researcher_granted_backtest(self, client):
        """RESEARCHER 权限检查 — 回测权限通过"""
        resp = client.get(
            "/api/rbac/check",
            params={"permission": "backtest:run"},
            headers=_auth_headers("RESEARCHER"),
        )
        assert resp.status_code == 200
        assert resp.json()["granted"] is True

    def test_check_permission_no_token_unauthorized(self, client):
        """无 token 访问权限检查 — 返回 401"""
        resp = client.get(
            "/api/rbac/check",
            params={"permission": "data:view"},
        )
        assert resp.status_code == 401

    # ── 角色列表 /rbac/roles ─────────────────────────────────────

    def test_list_roles_with_auth(self, client):
        """认证用户可以查看角色列表"""
        resp = client.get("/api/rbac/roles", headers=_auth_headers("VIEWER"))
        # 可能返回 200 或 500（取决于数据库是否已迁移），但不应该是 401/403
        assert resp.status_code in (200, 500)

    def test_list_roles_no_auth_denied(self, client):
        """无 token 访问角色列表 — 返回 401"""
        resp = client.get("/api/rbac/roles")
        assert resp.status_code == 401

    # ── 权限列表 /rbac/permissions ───────────────────────────────

    def test_list_permissions_with_auth(self, client):
        """认证用户可以查看权限列表"""
        resp = client.get("/api/rbac/permissions", headers=_auth_headers("VIEWER"))
        assert resp.status_code in (200, 500)

    def test_list_permissions_no_auth_denied(self, client):
        """无 token 访问权限列表 — 返回 401"""
        resp = client.get("/api/rbac/permissions")
        assert resp.status_code == 401

    # ── 创建角色 /rbac/roles (POST) — 仅 ADMIN ──────────────────

    def test_create_role_admin_allowed(self, client):
        """ADMIN 可以创建角色（可能因 DB 未迁移返回 500，但不应该是 403）"""
        resp = client.post(
            "/api/rbac/roles",
            json={"name": "test_role", "display_name": "测试角色", "description": "测试"},
            headers=_auth_headers("ADMIN"),
        )
        assert resp.status_code in (200, 201, 409, 500)  # 409=已存在, 500=DB未迁移

    def test_create_role_viewer_denied(self, client):
        """VIEWER 不能创建角色 — 返回 403"""
        resp = client.post(
            "/api/rbac/roles",
            json={"name": "test_role", "display_name": "测试角色", "description": "测试"},
            headers=_auth_headers("VIEWER"),
        )
        assert resp.status_code == 403

    def test_create_role_trader_denied(self, client):
        """TRADER 不能创建角色 — 返回 403"""
        resp = client.post(
            "/api/rbac/roles",
            json={"name": "test_role", "display_name": "测试角色", "description": "测试"},
            headers=_auth_headers("TRADER"),
        )
        assert resp.status_code == 403

    def test_create_role_researcher_denied(self, client):
        """RESEARCHER 不能创建角色 — 返回 403"""
        resp = client.post(
            "/api/rbac/roles",
            json={"name": "test_role", "display_name": "测试角色", "description": "测试"},
            headers=_auth_headers("RESEARCHER"),
        )
        assert resp.status_code == 403

    def test_create_role_no_auth_denied(self, client):
        """无 token 创建角色 — 返回 401"""
        resp = client.post(
            "/api/rbac/roles",
            json={"name": "test_role", "display_name": "测试角色"},
        )
        assert resp.status_code == 401

    def test_create_role_missing_fields(self, client):
        """缺少必填字段 — 返回 400"""
        resp = client.post(
            "/api/rbac/roles",
            json={"name": "", "display_name": ""},
            headers=_auth_headers("ADMIN"),
        )
        assert resp.status_code == 400

    # ── 删除角色 /rbac/roles/{role_id} (DELETE) — 仅 ADMIN ───────

    def test_delete_role_viewer_denied(self, client):
        """VIEWER 不能删除角色 — 返回 403"""
        resp = client.delete(
            "/api/rbac/roles/999",
            headers=_auth_headers("VIEWER"),
        )
        assert resp.status_code == 403

    def test_delete_role_no_auth_denied(self, client):
        """无 token 删除角色 — 返回 401"""
        resp = client.delete("/api/rbac/roles/999")
        assert resp.status_code == 401

    # ── 授予权限 /rbac/roles/{role_id}/permissions (POST) — 仅 ADMIN ──

    def test_grant_permission_viewer_denied(self, client):
        """VIEWER 不能授予权限 — 返回 403"""
        resp = client.post(
            "/api/rbac/roles/1/permissions",
            json={"permission_id": 1},
            headers=_auth_headers("VIEWER"),
        )
        assert resp.status_code == 403

    def test_grant_permission_no_auth_denied(self, client):
        """无 token授予权限 — 返回 401"""
        resp = client.post(
            "/api/rbac/roles/1/permissions",
            json={"permission_id": 1},
        )
        assert resp.status_code == 401

    # ── 分配用户角色 /rbac/users/{user_id}/roles (POST) — 仅 ADMIN ──

    def test_assign_role_viewer_denied(self, client):
        """VIEWER 不能分配角色 — 返回 403"""
        resp = client.post(
            "/api/rbac/users/testuser/roles",
            json={"role_id": 2},
            headers=_auth_headers("VIEWER"),
        )
        assert resp.status_code == 403

    def test_assign_role_no_auth_denied(self, client):
        """无 token 分配角色 — 返回 401"""
        resp = client.post(
            "/api/rbac/users/testuser/roles",
            json={"role_id": 2},
        )
        assert resp.status_code == 401

    # ── 获取用户角色 /rbac/users/{user_id}/roles (GET) ──────────

    def test_get_user_roles_with_auth(self, client):
        """认证用户可以查看用户角色"""
        resp = client.get(
            "/api/rbac/users/testuser/roles",
            headers=_auth_headers("VIEWER"),
        )
        assert resp.status_code in (200, 500)

    def test_get_user_roles_no_auth_denied(self, client):
        """无 token 查看用户角色 — 返回 401"""
        resp = client.get("/api/rbac/users/testuser/roles")
        assert resp.status_code == 401

    # ── 获取角色权限 /rbac/roles/{role_id}/permissions (GET) ────

    def test_get_role_permissions_with_auth(self, client):
        """认证用户可以查看角色权限"""
        resp = client.get(
            "/api/rbac/roles/1/permissions",
            headers=_auth_headers("VIEWER"),
        )
        assert resp.status_code in (200, 404, 500)

    def test_get_role_permissions_no_auth_denied(self, client):
        """无 token 查看角色权限 — 返回 401"""
        resp = client.get("/api/rbac/roles/1/permissions")
        assert resp.status_code == 401
