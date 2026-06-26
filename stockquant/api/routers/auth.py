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
from stockquant.persistence.repository import get_user as db_get_user, save_user as db_save_user

router = APIRouter(tags=["auth"])

logger = logging.getLogger("stockquant.auth")

# JWT settings
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "stockquant-dev-secret-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def _get_db_url() -> str:
    """获取数据库 URL"""
    return os.environ.get("DATABASE_URL", "sqlite:///./stockquant.db")


# Password hashing — 直接使用 bcrypt 库，绕过 passlib 版本兼容问题
try:
    import bcrypt as _bcrypt

    def _hash_password(password: str) -> str:
        return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

    def _verify_password(password: str, hashed_password: str) -> bool:
        return _bcrypt.checkpw(password.encode(), hashed_password.encode())

except ImportError:
    # fallback: 明文比较（仅开发环境）
    def _hash_password(password: str) -> str:  # type: ignore[misc]
        return f"plain:{password}"

    def _verify_password(password: str, hashed_password: str) -> bool:  # type: ignore[misc]
        if hashed_password.startswith("plain:"):
            return hashed_password[6:] == password
        return False


def _ensure_default_admin(db_url: str) -> None:
    """确保 admin 用户在数据库中已存在（首次启动自动创建）。"""
    existing = db_get_user(db_url, "admin")
    if existing is None:
        try:
            db_save_user(
                engine_url=db_url,
                user_id="admin",
                username="admin",
                hashed_password=_hash_password("admin123"),
                roles='["admin"]',
                disabled=False,
            )
            logger.info("自动创建默认 admin 用户")
        except Exception as e:
            logger.warning("创建默认 admin 用户失败（非致命）: %s", e)


# MVP user storage (in-memory, 作为 DB 不可用时的 fallback)
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
    db_url = _get_db_url()
    _ensure_default_admin(db_url)

    # 优先从数据库查询
    user_data = db_get_user(db_url, form_data.username)
    if user_data:
        user = {
            "username": user_data["username"],
            "hashed_password": user_data["hashed_password"],
            "roles": user_data.get("roles", '["user"]'),
            "disabled": bool(user_data.get("disabled", False)),
        }
    else:
        # 如果数据库中没有，退回到内存默认用户（兼容模式）
        users = _init_users_db()
        user = users.get(form_data.username)

    if not user or not _verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误", headers={"WWW-Authenticate": "Bearer"})
    if isinstance(user.get("disabled"), str):
        user["disabled"] = user["disabled"].lower() in ("true", "1", "True")
    if user.get("disabled"):
        raise HTTPException(status_code=400, detail="账户已禁用")

    roles = user.get("roles", '["user"]')
    if isinstance(roles, str):
        import json
        try:
            roles = json.loads(roles)
        except (json.JSONDecodeError, TypeError):
            roles = ["user"]

    access_token = create_access_token(data={
        "sub": user["username"],
        "roles": roles,
        # role 字段须与 deps.UserRole 枚举值（大写）对齐，get_admin_user 据此鉴权
        "role": (roles[0] if roles else "viewer").upper(),
    })
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "username": user["username"],
            "roles": roles,
        },
    }


@router.post("/auth/register", summary="用户注册")
async def register(payload: dict):
    """注册新用户 — 数据持久化到数据库"""
    db_url = _get_db_url()
    username = payload.get("username", "").strip()
    password = payload.get("password", "")

    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码长度至少6位")
    if db_get_user(db_url, username) is not None:
        raise HTTPException(status_code=409, detail="用户名已存在")

    import uuid
    db_save_user(
        engine_url=db_url,
        user_id=username,
        username=username,
        hashed_password=get_password_hash(password),
        roles='["user"]',
        disabled=False,
    )
    logger.info("新用户注册: %s", username)
    return {"success": True, "message": "注册成功"}


@router.get("/auth/me", summary="获取当前用户信息")
async def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前登录用户信息 — 从数据库读取"""
    username = current_user.get("sub", "anonymous")
    db_url = _get_db_url()
    user_data = db_get_user(db_url, username)
    if user_data:
        roles = user_data.get("roles", '["user"]')
        if isinstance(roles, str):
            import json
            try:
                roles = json.loads(roles)
            except (json.JSONDecodeError, TypeError):
                roles = ["user"]
        return {
            "username": user_data["username"],
            "roles": roles,
        }
    return {
        "username": username,
        "roles": current_user.get("roles", []),
    }
