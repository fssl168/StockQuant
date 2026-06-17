# -*- coding: utf-8 -*-
"""F029 依赖注入 — 配置、认证"""

from __future__ import annotations

import os
from enum import Enum
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# auto_error=False：让调用方自行决定是否要求认证
security = HTTPBearer(auto_error=False)

try:
    from jose import JWTError, jwt
    JOSE_AVAILABLE = True
except ImportError:
    JOSE_AVAILABLE = False

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "stockquant-dev-secret-change-in-prod")
ALGORITHM = "HS256"


class UserRole(str, Enum):
    """用户角色枚举"""
    ADMIN = "ADMIN"
    TRADER = "TRADER"
    VIEWER = "VIEWER"

# 启动时警告：生产环境必须设置 JWT_SECRET_KEY
if SECRET_KEY == "stockquant-dev-secret-change-in-prod":
    import warnings
    warnings.warn(
        "JWT_SECRET_KEY 未设置，使用开发默认值。生产环境必须设置环境变量 JWT_SECRET_KEY！",
        RuntimeWarning,
        stacklevel=2,
    )


def decode_token(token: str) -> dict:
    """解码 JWT token"""
    if not JOSE_AVAILABLE:
        raise HTTPException(status_code=500, detail="JWT 库未安装")
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="无效的认证令牌")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """获取当前用户（实现 JWT 验证）。

    MVP 行为：未提供 token 时允许匿名访问（可选认证）。
    但 token 验证失败时不再静默放行 —— 抛 401。
    """
    if not credentials:
        # MVP: 未提供 token 时仍允许匿名访问
        return {"sub": "anonymous", "roles": [], "role": UserRole.VIEWER.value}

    try:
        payload = decode_token(credentials.credentials)
        return {
            "sub": payload.get("sub", "anonymous"),
            "roles": payload.get("roles", []),
            "role": payload.get("role", UserRole.VIEWER.value),
        }
    except HTTPException:
        raise
    except Exception:
        # token 格式错误/过期 → 401，不再静默降级为匿名
        raise HTTPException(status_code=401, detail="无效的认证令牌")


async def get_required_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """获取当前用户（强制认证）。

    未提供 token 或 token 无效时返回 401。
    用于敏感操作：交易下单、设置修改等。
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="需要提供认证令牌")

    try:
        payload = decode_token(credentials.credentials)
        return {
            "sub": payload.get("sub", "anonymous"),
            "roles": payload.get("roles", []),
            "role": payload.get("role", UserRole.VIEWER.value),
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="无效的认证令牌")


async def get_admin_user(user: dict = Depends(get_required_user)) -> dict:
    """获取管理员用户 — 要求 ADMIN 角色"""
    if user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def get_trader_user(user: dict = Depends(get_required_user)) -> dict:
    """获取交易员用户 — 要求 ADMIN 或 TRADER 角色"""
    if user.get("role") not in (UserRole.ADMIN.value, UserRole.TRADER.value):
        raise HTTPException(status_code=403, detail="需要交易员或管理员权限")
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
