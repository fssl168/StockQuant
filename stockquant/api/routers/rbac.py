# -*- coding: utf-8 -*-
"""RBAC 权限管理 API 路由

提供基于角色的访问控制管理端点，包括：
- 角色管理（CRUD）
- 权限查询
- 角色-权限关联管理（授予/撤销）
- 用户-角色关联管理（分配/移除）
- 权限检查

路径前缀：/api/rbac/*
"""

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_
from sqlalchemy.orm import Session

from stockquant.api.deps import get_admin_user, get_current_user, has_permission
from stockquant.api.schemas import UserToken
from stockquant.persistence.models import (
    PermissionModel,
    RoleModel,
    RolePermissionModel,
    UserRoleModel,
    get_engine,
)
from stockquant.persistence.repository import get_user

router = APIRouter(tags=["RBAC权限管理"])
logger = logging.getLogger("stockquant.api.rbac")


# ====================================================================
# 数据库会话辅助
# ====================================================================

def _get_db_url() -> str:
    """获取数据库 URL"""
    return os.environ.get("DATABASE_URL", "sqlite:///./stockquant.db")


def _get_session() -> Session:
    """获取 SQLAlchemy Session（同步）"""
    from sqlalchemy.orm import sessionmaker
    engine = get_engine(_get_db_url())
    return sessionmaker(bind=engine)()


def _serialize_role(role: RoleModel, perm_count: int = 0) -> Dict[str, Any]:
    """序列化角色对象"""
    return {
        "id": role.id,
        "name": role.name,
        "display_name": role.display_name,
        "description": role.description,
        "is_system": bool(role.is_system),
        "permission_count": perm_count,
        "created_at": role.created_at.isoformat() if role.created_at else "",
    }


def _serialize_permission(perm: PermissionModel) -> Dict[str, Any]:
    """序列化权限对象"""
    return {
        "id": perm.id,
        "code": perm.code,
        "name": perm.name,
        "module": perm.module,
        "description": perm.description,
        "created_at": perm.created_at.isoformat() if perm.created_at else "",
    }


# ====================================================================
# 角色管理
# ====================================================================

@router.get("/rbac/roles", summary="获取所有角色")
async def list_roles(
    _user: UserToken = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """获取所有角色列表（含权限数量）。"""
    session = _get_session()
    try:
        roles = session.query(RoleModel).order_by(RoleModel.id).all()
        result = []
        for role in roles:
            perm_count = session.query(RolePermissionModel).filter(
                RolePermissionModel.role_id == role.id
            ).count()
            result.append(_serialize_role(role, perm_count))
        return result
    finally:
        session.close()


@router.post("/rbac/roles", summary="创建角色（管理员）")
async def create_role(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
) -> Dict[str, Any]:
    """创建新角色。

    Body:
        {
            "name": "custom_role",
            "display_name": "自定义角色",
            "description": "角色描述"
        }
    """
    name = (payload.get("name") or "").strip()
    display_name = (payload.get("display_name") or "").strip()
    description = payload.get("description", "")

    if not name or not display_name:
        raise HTTPException(status_code=400, detail="name 和 display_name 必填")

    session = _get_session()
    try:
        existing = session.query(RoleModel).filter(RoleModel.name == name).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"角色 '{name}' 已存在")

        role = RoleModel(
            name=name,
            display_name=display_name,
            description=description,
            is_system=0,
        )
        session.add(role)
        session.commit()
        session.refresh(role)
        logger.info("角色已创建（操作者: %s）: %s", _user.sub, name)
        return _serialize_role(role, 0)
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error("创建角色失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.put("/rbac/roles/{role_id}", summary="更新角色（管理员）")
async def update_role(
    role_id: int,
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
) -> Dict[str, Any]:
    """更新角色信息（display_name, description）。系统角色 name 不可改。"""
    session = _get_session()
    try:
        role = session.query(RoleModel).filter(RoleModel.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"角色 ID {role_id} 不存在")

        if "display_name" in payload:
            role.display_name = payload["display_name"]
        if "description" in payload:
            role.description = payload["description"]

        session.commit()
        session.refresh(role)
        perm_count = session.query(RolePermissionModel).filter(
            RolePermissionModel.role_id == role.id
        ).count()
        logger.info("角色已更新（操作者: %s）: id=%d", _user.sub, role_id)
        return _serialize_role(role, perm_count)
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error("更新角色失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/rbac/roles/{role_id}", summary="删除角色（管理员）")
async def delete_role(
    role_id: int,
    _user: UserToken = Depends(get_admin_user),
) -> Dict[str, Any]:
    """删除角色。系统内置角色（is_system=1）不可删除。"""
    session = _get_session()
    try:
        role = session.query(RoleModel).filter(RoleModel.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"角色 ID {role_id} 不存在")
        if role.is_system:
            raise HTTPException(
                status_code=400,
                detail=f"系统内置角色 '{role.name}' 不可删除",
            )

        # 级联删除关联（role_permissions, user_roles）
        session.query(RolePermissionModel).filter(
            RolePermissionModel.role_id == role_id
        ).delete()
        session.query(UserRoleModel).filter(
            UserRoleModel.role_id == role_id
        ).delete()
        session.delete(role)
        session.commit()
        logger.info("角色已删除（操作者: %s）: id=%d name=%s", _user.sub, role_id, role.name)
        return {"success": True, "deleted": role_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error("删除角色失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ====================================================================
# 权限管理
# ====================================================================

@router.get("/rbac/permissions", summary="获取所有权限")
async def list_permissions(
    _user: UserToken = Depends(get_current_user),
    module: Optional[str] = Query(None, description="按模块过滤"),
) -> List[Dict[str, Any]]:
    """获取所有权限定义列表，可按模块过滤。"""
    session = _get_session()
    try:
        query = session.query(PermissionModel)
        if module:
            query = query.filter(PermissionModel.module == module)
        perms = query.order_by(PermissionModel.module, PermissionModel.id).all()
        return [_serialize_permission(p) for p in perms]
    finally:
        session.close()


# ====================================================================
# 角色-权限管理
# ====================================================================

@router.get("/rbac/roles/{role_id}/permissions", summary="获取角色权限列表")
async def get_role_permissions(
    role_id: int,
    _user: UserToken = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取指定角色拥有的所有权限。"""
    session = _get_session()
    try:
        role = session.query(RoleModel).filter(RoleModel.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"角色 ID {role_id} 不存在")

        perms = (
            session.query(PermissionModel)
            .join(RolePermissionModel, RolePermissionModel.permission_id == PermissionModel.id)
            .filter(RolePermissionModel.role_id == role_id)
            .order_by(PermissionModel.module, PermissionModel.id)
            .all()
        )
        return {
            "role": _serialize_role(role, len(perms)),
            "permissions": [_serialize_permission(p) for p in perms],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取角色权限失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/rbac/roles/{role_id}/permissions", summary="授予角色权限（管理员）")
async def grant_permission(
    role_id: int,
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
) -> Dict[str, Any]:
    """为角色授予权限。

    Body:
        {"permission_id": 5}
        或
        {"permission_code": "trade:place_order"}
    """
    permission_id = payload.get("permission_id")
    permission_code = payload.get("permission_code")

    if not permission_id and not permission_code:
        raise HTTPException(status_code=400, detail="permission_id 或 permission_code 必填")

    session = _get_session()
    try:
        role = session.query(RoleModel).filter(RoleModel.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"角色 ID {role_id} 不存在")

        if permission_code:
            perm = session.query(PermissionModel).filter(
                PermissionModel.code == permission_code
            ).first()
        else:
            perm = session.query(PermissionModel).filter(
                PermissionModel.id == permission_id
            ).first()

        if not perm:
            raise HTTPException(status_code=404, detail="权限不存在")

        # 检查是否已关联
        existing = session.query(RolePermissionModel).filter(
            and_(
                RolePermissionModel.role_id == role_id,
                RolePermissionModel.permission_id == perm.id,
            )
        ).first()
        if existing:
            return {"success": True, "message": "权限已存在，无需重复授予", "role_id": role_id, "permission_id": perm.id}

        rp = RolePermissionModel(role_id=role_id, permission_id=perm.id)
        session.add(rp)
        session.commit()
        logger.info(
            "权限已授予（操作者: %s）: role=%s permission=%s",
            _user.sub, role.name, perm.code,
        )
        return {"success": True, "role_id": role_id, "permission_id": perm.id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error("授予权限失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete(
    "/rbac/roles/{role_id}/permissions/{permission_id}",
    summary="撤销角色权限（管理员）",
)
async def revoke_permission(
    role_id: int,
    permission_id: int,
    _user: UserToken = Depends(get_admin_user),
) -> Dict[str, Any]:
    """撤销角色的指定权限。"""
    session = _get_session()
    try:
        rp = session.query(RolePermissionModel).filter(
            and_(
                RolePermissionModel.role_id == role_id,
                RolePermissionModel.permission_id == permission_id,
            )
        ).first()
        if not rp:
            raise HTTPException(status_code=404, detail="角色-权限关联不存在")

        session.delete(rp)
        session.commit()
        logger.info(
            "权限已撤销（操作者: %s）: role_id=%d permission_id=%d",
            _user.sub, role_id, permission_id,
        )
        return {"success": True, "role_id": role_id, "permission_id": permission_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error("撤销权限失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ====================================================================
# 用户-角色管理
# ====================================================================

@router.get("/rbac/users/{user_id}/roles", summary="获取用户角色列表")
async def get_user_roles(
    user_id: str,
    _user: UserToken = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取指定用户分配的所有角色。"""
    session = _get_session()
    try:
        roles = (
            session.query(RoleModel, UserRoleModel.assigned_at)
            .join(UserRoleModel, UserRoleModel.role_id == RoleModel.id)
            .filter(UserRoleModel.user_id == user_id)
            .order_by(RoleModel.id)
            .all()
        )
        role_list = []
        for role, assigned_at in roles:
            item = _serialize_role(role)
            item["assigned_at"] = assigned_at.isoformat() if assigned_at else ""
            role_list.append(item)
        return {"user_id": user_id, "roles": role_list}
    except Exception as e:
        logger.error("获取用户角色失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/rbac/users/{user_id}/roles", summary="分配用户角色（管理员）")
async def assign_role(
    user_id: str,
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
) -> Dict[str, Any]:
    """为用户分配角色。

    Body:
        {"role_id": 2}
        或
        {"role_name": "trader"}
    """
    role_id = payload.get("role_id")
    role_name = payload.get("role_name")

    if not role_id and not role_name:
        raise HTTPException(status_code=400, detail="role_id 或 role_name 必填")

    session = _get_session()
    try:
        # 验证用户是否存在
        db_url = _get_db_url()
        user_data = get_user(db_url, user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail=f"用户 '{user_id}' 不存在")

        # 查找角色
        if role_name:
            role = session.query(RoleModel).filter(RoleModel.name == role_name).first()
        else:
            role = session.query(RoleModel).filter(RoleModel.id == role_id).first()

        if not role:
            raise HTTPException(status_code=404, detail="角色不存在")

        # 检查是否已分配
        existing = session.query(UserRoleModel).filter(
            and_(
                UserRoleModel.user_id == user_id,
                UserRoleModel.role_id == role.id,
            )
        ).first()
        if existing:
            return {"success": True, "message": "角色已分配，无需重复操作", "user_id": user_id, "role_id": role.id}

        ur = UserRoleModel(user_id=user_id, role_id=role.id)
        session.add(ur)
        session.commit()
        logger.info(
            "角色已分配（操作者: %s）: user=%s role=%s",
            _user.sub, user_id, role.name,
        )
        return {"success": True, "user_id": user_id, "role_id": role.id, "role_name": role.name}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error("分配角色失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete(
    "/rbac/users/{user_id}/roles/{role_id}",
    summary="移除用户角色（管理员）",
)
async def remove_user_role(
    user_id: str,
    role_id: int,
    _user: UserToken = Depends(get_admin_user),
) -> Dict[str, Any]:
    """移除用户的指定角色。"""
    session = _get_session()
    try:
        ur = session.query(UserRoleModel).filter(
            and_(
                UserRoleModel.user_id == user_id,
                UserRoleModel.role_id == role_id,
            )
        ).first()
        if not ur:
            raise HTTPException(status_code=404, detail="用户-角色关联不存在")

        session.delete(ur)
        session.commit()
        logger.info(
            "角色已移除（操作者: %s）: user=%s role_id=%d",
            _user.sub, user_id, role_id,
        )
        return {"success": True, "user_id": user_id, "role_id": role_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error("移除用户角色失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ====================================================================
# 权限检查
# ====================================================================

@router.get("/rbac/check", summary="检查当前用户权限")
async def check_permission(
    permission: str = Query(..., description="权限代码，如 trade:place_order"),
    user: UserToken = Depends(get_current_user),
) -> Dict[str, Any]:
    """检查当前登录用户是否拥有指定权限（快速路径，不查数据库）。"""
    granted = has_permission(user, permission)
    return {
        "user_id": user.sub,
        "role": user.role,
        "permission": permission,
        "granted": granted,
    }
