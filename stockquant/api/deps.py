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
    """用户角色枚举"""
    ADMIN = "ADMIN"
    TRADER = "TRADER"
    VIEWER = "VIEWER"


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
    """获取管理员用户 — 要求 ADMIN 角色"""
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def get_trader_user(user: UserToken = Depends(get_current_user)) -> UserToken:
    """获取交易员用户 — 要求 ADMIN 或 TRADER 角色。

    MVP 行为：未提供 token 时（anonymous/VIEWER）拒绝访问（403）。
    有 token 但角色不符时也拒绝（403）。
    """
    if user.role not in (UserRole.ADMIN.value, UserRole.TRADER.value):
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
