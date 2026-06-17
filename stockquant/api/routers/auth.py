# -*- coding: utf-8 -*-
"""F029 认证路由 — JWT 登录/注册"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm

from stockquant.api.deps import get_current_user

router = APIRouter(tags=["auth"])

logger = logging.getLogger("stockquant.auth")

# JWT settings
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "stockquant-dev-secret-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


# Password hashing — 直接使用 bcrypt 库，绕过 passlib 版本兼容问题
try:
    import bcrypt as _bcrypt

    def _hash_password(password: str) -> str:
        return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

    def _verify_password(password: str, hashed: str) -> bool:
        return _bcrypt.checkpw(password.encode(), hashed.encode())

except ImportError:
    # fallback: 明文比较（仅开发环境）
    def _hash_password(password: str) -> str:  # type: ignore[misc]
        return f"plain:{password}"

    def _verify_password(password: str, hashed: str) -> bool:  # type: ignore[misc]
        if hashed.startswith("plain:"):
            return hashed[6:] == password
        return False


# MVP user storage (in-memory, replace with DB later)
_users_db: dict[str, dict] | None = None


def _init_users_db() -> dict[str, dict]:
    """Lazy-init user database."""
    global _users_db
    if _users_db is None:
        _users_db = {
            "admin": {
                "username": "admin",
                "hashed_password": _hash_password("admin123"),
                "roles": ["admin"],
                "disabled": False,
            },
        }
    return _users_db


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """创建 JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    from jose import jwt
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _verify_password(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return _hash_password(password)


@router.post("/auth/login", summary="用户登录")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """用户名密码登录，返回 JWT token"""
    users = _init_users_db()
    user = users.get(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误", headers={"WWW-Authenticate": "Bearer"})
    if user.get("disabled"):
        raise HTTPException(status_code=400, detail="账户已禁用")

    access_token = create_access_token(data={"sub": user["username"], "roles": user.get("roles", [])})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "username": user["username"],
            "roles": user.get("roles", []),
        },
    }


@router.post("/auth/register", summary="用户注册")
async def register(payload: dict):
    """注册新用户（MVP 阶段开放）"""
    users = _init_users_db()
    username = payload.get("username", "").strip()
    password = payload.get("password", "")

    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码长度至少6位")
    if username in users:
        raise HTTPException(status_code=409, detail="用户名已存在")

    users[username] = {
        "username": username,
        "hashed_password": get_password_hash(password),
        "roles": ["user"],
        "disabled": False,
    }
    logger.info("新用户注册: %s", username)
    return {"success": True, "message": "注册成功"}


@router.get("/auth/me", summary="获取当前用户信息")
async def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前登录用户信息"""
    username = current_user.get("sub", "anonymous")
    users = _init_users_db()
    user = users.get(username)
    if user:
        return {
            "username": user["username"],
            "roles": user.get("roles", []),
        }
    return {
        "username": username,
        "roles": current_user.get("roles", []),
    }
