# -*- coding: utf-8 -*-
"""三角色前端重构 — 用户管理 API 路由（仅 ADMIN）

提供用户 CRUD 管理端点，包括：
- 列出所有用户
- 创建新用户
- 更新用户角色/禁用状态
- 重置密码
- 删除用户
- 切换用户禁用状态

路径前缀：/api/admin/users/*
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from stockquant.api.deps import get_admin_user
from stockquant.api.schemas import UserToken
from stockquant.persistence.repository import (
    save_user,
    get_user,
    list_users,
    delete_user,
)
from stockquant.api.routers.auth import _get_db_url, _hash_password, verify_password

router = APIRouter(tags=["用户管理 (ADMIN)"])
logger = logging.getLogger("stockquant.api.user_admin")


# ====================================================================
# 端点
# ====================================================================

@router.get("/admin/users", summary="列出所有用户", response_model=List[Dict[str, Any]])
async def get_all_users(
    _user: UserToken = Depends(get_admin_user),
    disabled: Optional[bool] = Query(None),
) -> List[Dict[str, Any]]:
    """获取所有用户列表（不含密码哈希）。"""
    try:
        db_url = _get_db_url()
        users = list_users(db_url)
        if disabled is not None:
            users = [u for u in users if u.get("disabled") == disabled]
        return users
    except Exception as e:
        logger.error("列出用户失败: %s", e, exc_info=True)
        return []


@router.get("/admin/users/{user_id}", summary="获取用户详情")
async def get_user_detail(
    user_id: str,
    _user: UserToken = Depends(get_admin_user),
) -> Dict[str, Any]:
    """获取单个用户详情。"""
    try:
        db_url = _get_db_url()
        user = get_user(db_url, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取用户详情失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/users", summary="创建新用户")
async def create_user(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
) -> Dict[str, Any]:
    """创建新用户。

    Body:
        {
            "username": "newuser",
            "password": "password123",
            "roles": ["viewer"],        // 可选: ["viewer"] | ["trader"] | ["admin"]
            "disabled": false            // 可选
        }
    """
    username = payload.get("username", "").strip()
    password = payload.get("password", "")
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码必填")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码长度至少6位")

    try:
        db_url = _get_db_url()

        # 检查用户名是否已存在
        existing = get_user(db_url, username)
        if existing:
            raise HTTPException(status_code=409, detail="用户名已存在")

        roles = payload.get("roles", ["viewer"])
        if isinstance(roles, str):
            try:
                roles = json.loads(roles) if roles.strip() else []
            except (json.JSONDecodeError, ValueError):
                roles = []
        if not isinstance(roles, list) or not roles:
            roles = ["viewer"]

        disabled = bool(payload.get("disabled", False))

        result = save_user(
            engine_url=db_url,
            user_id=username,
            username=username,
            hashed_password=_hash_password(password),
            roles=json.dumps(roles),
            disabled=disabled,
        )
        logger.info("新用户已创建（操作者: %s）: %s role=%s", _user.sub, username, roles[0])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("创建用户失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/users/{user_id}", summary="更新用户信息")
async def update_user(
    user_id: str,
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
) -> Dict[str, Any]:
    """更新用户信息（角色、禁用状态）。

    Body:
        {
            "roles": ["viewer"],         // 可选，修改角色
            "disabled": true             // 可选，修改禁用状态
        }
    """
    db_url = _get_db_url()
    existing = get_user(db_url, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")

    try:
        updates = {}
        if "roles" in payload:
            roles = payload["roles"]
            if isinstance(roles, str):
                try:
                    roles = json.loads(roles) if roles.strip() else []
                except (json.JSONDecodeError, ValueError):
                    roles = []
            if not isinstance(roles, list) or not roles:
                raise HTTPException(status_code=400, detail="roles 必须是非空列表")
            updates["roles"] = json.dumps(roles)

        if "disabled" in payload:
            updates["disabled"] = int(bool(payload["disabled"]))

        if not updates:
            raise HTTPException(status_code=400, detail="至少提供一个更新字段（roles 或 disabled）")

        # 读取现有数据 + 合并更新
        result = save_user(
            engine_url=db_url,
            user_id=user_id,
            username=existing["username"],
            hashed_password=existing["hashed_password"],  # 保留原密码
            roles=updates.get("roles", existing.get("roles", '["viewer"]')),
            disabled=updates.get("disabled", existing.get("disabled", False)),
        )
        logger.info(
            "用户已更新（操作者: %s）: user_id=%s roles=%s disabled=%s",
            _user.sub, user_id, result.get("roles"), bool(result.get("disabled")),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("更新用户失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/users/{user_id}/password", summary="重置用户密码")
async def reset_user_password(
    user_id: str,
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
) -> Dict[str, Any]:
    """重置用户密码。

    Body:
        {"new_password": "newpassword123"}
    """
    new_password = payload.get("new_password", "")
    if not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码必填且至少6位")

    db_url = _get_db_url()
    existing = get_user(db_url, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")

    try:
        result = save_user(
            engine_url=db_url,
            user_id=user_id,
            username=existing["username"],
            hashed_password=_hash_password(new_password),
            roles=existing.get("roles", '["viewer"]'),
            disabled=existing.get("disabled", False),
        )
        logger.info("用户密码已重置（操作者: %s）: %s", _user.sub, user_id)
        return {"success": True, "user_id": user_id}
    except Exception as e:
        logger.error("重置密码失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/users/{user_id}/toggle-disable", summary="切换用户禁用状态")
async def toggle_disable_user(
    user_id: str,
    _user: UserToken = Depends(get_admin_user),
) -> Dict[str, Any]:
    """切换用户启用/禁用状态。"""
    db_url = _get_db_url()
    existing = get_user(db_url, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")

    try:
        new_disabled = not existing.get("disabled", False)
        result = save_user(
            engine_url=db_url,
            user_id=user_id,
            username=existing["username"],
            hashed_password=existing["hashed_password"],
            roles=existing.get("roles", '["viewer"]'),
            disabled=new_disabled,
        )
        status = "禁用" if new_disabled else "启用"
        logger.info("用户已%s（操作者: %s）: %s", status, _user.sub, user_id)
        return {"success": True, "user_id": user_id, "disabled": new_disabled}
    except Exception as e:
        logger.error("切换用户禁用状态失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/users/{user_id}", summary="删除用户")
async def remove_user(
    user_id: str,
    _user: UserToken = Depends(get_admin_user),
) -> Dict[str, Any]:
    """删除用户。"""
    if user_id == "admin":
        raise HTTPException(status_code=400, detail="不能删除默认 admin 用户")

    db_url = _get_db_url()
    try:
        success = delete_user(db_url, user_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")
        logger.info("用户已删除（操作者: %s）: %s", _user.sub, user_id)
        return {"success": True, "deleted": user_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除用户失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/users/import", summary="导入种子用户（开发者用）")
async def seed_demo_users(
    _user: UserToken = Depends(get_admin_user),
) -> Dict[str, Any]:
    """导入演示账号（仅首次使用，重复用户跳过）。

    创建三个演示账号：
    - admin / admin123（角色: admin）
    - trader / trader123（角色: trader）
    - viewer / viewer123（角色: viewer）
    """
    db_url = _get_db_url()
    demo_users = [
        {"username": "admin", "password": "admin123", "roles": ["admin"]},
        {"username": "trader", "password": "trader123", "roles": ["trader"]},
        {"username": "viewer", "password": "viewer123", "roles": ["viewer"]},
    ]
    created = []
    skipped = []
    for u in demo_users:
        existing = get_user(db_url, u["username"])
        if existing:
            skipped.append(u["username"])
            continue
        save_user(
            engine_url=db_url,
            user_id=u["username"],
            username=u["username"],
            hashed_password=_hash_password(u["password"]),
            roles=json.dumps(u["roles"]),
            disabled=False,
        )
        created.append(u["username"])
    logger.info("种子用户导入（操作者: %s）: 创建=%s 跳过=%s", _user.sub, created, skipped)
    return {"success": True, "created": created, "skipped": skipped}
