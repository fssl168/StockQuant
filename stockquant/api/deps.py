# -*- coding: utf-8 -*-
"""F029 依赖注入 — 配置、认证"""

import os
from enum import Enum
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from stockquant.api.schemas import UserToken

# auto_error=False：让调用方自行决定是否要求认证
security = HTTPBearer(auto_error=False)

try:
    from jose import JWTError, jwt
    JOSE_AVAILABLE = True
except ImportError:
    JOSE_AVAILABLE = False

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "stockquant-dev-secret-change-in-prod")
ALGORITHM = "HS256"
_DEBUG_MODE = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

# 启动时强制校验 JWT_SECRET_KEY
if SECRET_KEY == "" and not _DEBUG_MODE:
    raise RuntimeError(
        "JWT_SECRET_KEY 未设置（生产环境）。请设置环境变量 JWT_SECRET_KEY，"
        "或设置 DEBUG=1 启用开发模式。"
    )


class UserRole(str, Enum):
    """用户角色枚举（四级：管理员/交易员/研究员/访客）"""
    ADMIN = "ADMIN"
    TRADER = "TRADER"
    RESEARCHER = "RESEARCHER"
    VIEWER = "VIEWER"


# ─── RBAC 权限矩阵 ──────────────────────────────────────────────────
# 快速路径：通过 JWT token 中的 role 字段直接判断权限（不查数据库）
# 管理路径：通过 RBAC API 管理细粒度权限（需要查数据库）

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "ADMIN": {"*"},  # 所有权限
    "TRADER": {
        "trade:place_order", "trade:cancel_order", "trade:view",
        "backtest:run", "backtest:view",
        "strategy:write", "strategy:view",
        "ai:chat", "data:view",
    },
    "RESEARCHER": {
        "backtest:run", "backtest:view",
        "strategy:write", "strategy:view",
        "data:view", "ai:chat",
    },
    "VIEWER": {
        "data:view", "backtest:view", "strategy:view", "ai:chat",
    },
}


def has_permission(user: UserToken, permission: str) -> bool:
    """检查用户是否拥有指定权限（快速路径 — 基于 JWT role 字段，不查数据库）。

    Args:
        user: 当前用户 token
        permission: 权限代码，如 "trade:place_order"

    Returns:
        True 如果用户拥有该权限或通配权限 "*"
    """
    role = user.role or "VIEWER"
    perms = ROLE_PERMISSIONS.get(role, set())
    return "*" in perms or permission in perms


def require_permission(permission: str):
    """创建权限检查依赖（用于 FastAPI 路由的 Depends）。

    用法::

        @router.post("/orders", dependencies=[Depends(require_permission("trade:place_order"))])
        async def place_order(...):
            ...

    或::

        @router.post("/orders")
        async def place_order(user: UserToken = Depends(require_permission("trade:place_order"))):
            ...
    """
    async def _check(user: UserToken = Depends(get_current_user)) -> UserToken:
        if not has_permission(user, permission):
            raise HTTPException(
                status_code=403,
                detail=f"权限不足：需要 {permission} 权限",
            )
        return user
    return _check


def decode_token(token: str) -> UserToken:
    """解码 JWT token"""
    if not JOSE_AVAILABLE:
        raise HTTPException(status_code=500, detail="JWT 库未安装")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return UserToken(
            sub=payload.get("sub", "anonymous"),
            roles=payload.get("roles", []),
            role=payload.get("role", UserRole.VIEWER.value),
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="无效的认证令牌")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserToken:
    """获取当前用户（需要 JWT 认证）。

    未提供 token 时一律返回 401。
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="需要提供认证令牌")

    try:
        return decode_token(credentials.credentials)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="无效的认证令牌")


async def get_required_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserToken:
    """获取当前用户（强制认证）。

    未提供 token 或 token 无效时返回 401。
    用于敏感操作：交易下单、设置修改等。
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="需要提供认证令牌")

    try:
        return decode_token(credentials.credentials)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="无效的认证令牌")


async def get_admin_user(user: UserToken = Depends(get_required_user)) -> UserToken:
    """获取管理员用户 — 要求 system:manage 权限（ADMIN 角色）

    向后兼容：基于新权限系统判断，等价于原 ADMIN 角色检查。
    """
    if not has_permission(user, "system:manage"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def get_trader_user(user: UserToken = Depends(get_current_user)) -> UserToken:
    """获取交易员用户 — 要求 trade:place_order 权限（ADMIN/TRADER 角色）。

    MVP 行为：未提供 token 时（anonymous/VIEWER）拒绝访问（403）。
    有 token 但角色不符时也拒绝（403）。
    向后兼容：基于新权限系统判断。
    """
    if not has_permission(user, "trade:place_order"):
        raise HTTPException(status_code=403, detail="需要交易员或管理员权限")
    return user


async def get_researcher_user(user: UserToken = Depends(get_current_user)) -> UserToken:
    """获取研究员用户 — 要求 backtest:run 权限（ADMIN/TRADER/RESEARCHER 角色）。

    RESEARCHER 角色可执行回测和策略研究，但不能交易。
    """
    if not has_permission(user, "backtest:run"):
        raise HTTPException(
            status_code=403,
            detail="需要研究员、交易员或管理员权限",
        )
    return user


# 配置管理
class AppSettings:
    """应用配置"""

    def __init__(self):
        self.cors_origins: list[str] = ["*"]
        self.max_backtest_workers: int = 4
        self.cache_ttl: int = 3600


def get_settings() -> AppSettings:
    return AppSettings()


async def get_request(request: Request) -> Request:
    return request
