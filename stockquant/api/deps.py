# -*- coding: utf-8 -*-
"""F029 依赖注入 — 配置、认证（MVP 存根）"""

from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# JWT 认证（MVP 存根，暂不启用）
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = security,
) -> dict:
    """
    获取当前用户（MVP 存根）。

    未来接入 JWT 认证时在此实现 token 验证逻辑。
    当前直接返回空用户字典，不拦截任何请求。
    """
    # TODO: 接入 JWT 验证
    # if not credentials:
    #     raise HTTPException(status_code=401, detail="未提供认证令牌")
    # payload = decode_jwt(credentials.credentials)
    # return {"sub": payload.get("sub"), "roles": payload.get("roles", [])}
    return {"sub": "anonymous", "roles": []}


# 配置管理（MVP 存根）
class AppSettings:
    """应用配置（MVP 存根）"""

    def __init__(self):
        self.cors_origins: list[str] = ["*"]
        self.max_backtest_workers: int = 4
        self.cache_ttl: int = 3600  # 秒


def get_settings() -> AppSettings:
    """获取应用配置"""
    return AppSettings()


async def get_request(request: Request) -> Request:
    """获取当前请求对象"""
    return request
