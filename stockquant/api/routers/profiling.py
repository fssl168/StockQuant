# -*- coding: utf-8 -*-
"""F020 GAP-L2 — UserProfileHistory / ProfilingManager API 路由

提供对用户风险偏好画像的查询/更新/历史追溯能力：
- 查询当前 RiskProfile + ProfileParams
- 更新风险偏好（手动覆盖）
- 查询转换历史
- 评估自动转换

路径前缀：/api/profiling/*
"""

import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from stockquant.api.deps import get_admin_user, get_current_user
from stockquant.api.schemas import UserToken

router = APIRouter(tags=["用户风险偏好"])
logger = logging.getLogger("stockquant.api.profiling")

# 模块级单例（懒加载）
_manager: Optional[Any] = None


def _get_manager():
    """获取或创建 ProfilingManager 单例

    首次调用时实例化（默认使用内存后端，避免无 DB 时启动失败）
    """
    global _manager
    if _manager is None:
        try:
            from stockquant.ai.profiling import ProfilingManager
            # 不传 db_url → 自动尝试 DATABASE_URL，失败降级为内存
            _manager = ProfilingManager()
            logger.info("ProfilingManager 已初始化（后端: %s）", _manager._backend)
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"ProfilingManager 模块未安装: {exc}",
            )
    return _manager


def _profile_to_dict(profile) -> str:
    """RiskProfile 枚举转字符串"""
    return profile.value if hasattr(profile, "value") else str(profile)


def _params_to_dict(params) -> Dict[str, Any]:
    """ProfileParams dataclass 转字典"""
    try:
        return asdict(params)
    except TypeError:
        return {
            "max_position_pct": getattr(params, "max_position_pct", 0),
            "stop_loss_pct": getattr(params, "stop_loss_pct", 0),
            "take_profit_pct": getattr(params, "take_profit_pct", 0),
            "max_drawdown_tolerance": getattr(params, "max_drawdown_tolerance", 0),
            "confidence_threshold": getattr(params, "confidence_threshold", 0),
        }


@router.get("/profiling/profile/{user_id}", summary="查询用户风险偏好")
async def get_profile(
    user_id: str,
    _user: UserToken = Depends(get_current_user),
):
    try:
        mgr = _get_manager()
        profile = mgr.get_profile(user_id=user_id)
        params = mgr.get_params(user_id=user_id)
        return {
            "user_id": user_id,
            "risk_profile": _profile_to_dict(profile),
            "params": _params_to_dict(params),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("查询用户风险偏好失败（user_id=%s）: %s", user_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/profiling/profile/{user_id}", summary="更新用户风险偏好")
async def update_profile(
    user_id: str,
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
):
    """更新用户风险偏好

    Body:
        {"risk_profile": "aggressive", "trigger": "manual"}

    risk_profile 可选值: conservative | neutral | aggressive
    trigger 可选，默认 manual
    """
    risk_profile_str = payload.get("risk_profile")
    if not risk_profile_str:
        raise HTTPException(status_code=400, detail="risk_profile 字段必填")

    try:
        from stockquant.ai.profiling import RiskProfile
        try:
            new_profile = RiskProfile(risk_profile_str)
        except ValueError:
            valid = [p.value for p in RiskProfile]
            raise HTTPException(
                status_code=400,
                detail=f"无效 risk_profile: {risk_profile_str}，可选: {', '.join(valid)}",
            )

        mgr = _get_manager()
        trigger = payload.get("trigger", "manual")
        mgr.update_profile(new_profile, user_id=user_id, trigger=trigger)
        logger.info(
            "用户风险偏好已更新（操作者: %s, user_id: %s, profile: %s, trigger: %s）",
            _user.sub, user_id, new_profile.value, trigger,
        )
        # 读取最新参数返回
        params = mgr.get_params(user_id=user_id)
        return {
            "success": True,
            "user_id": user_id,
            "risk_profile": new_profile.value,
            "params": _params_to_dict(params),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("更新用户风险偏好失败（user_id=%s）: %s", user_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/profiling/params/{user_id}", summary="查询用户决策参数")
async def get_params(
    user_id: str,
    _user: UserToken = Depends(get_current_user),
):
    try:
        mgr = _get_manager()
        params = mgr.get_params(user_id=user_id)
        return {
            "user_id": user_id,
            "params": _params_to_dict(params),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("查询用户决策参数失败（user_id=%s）: %s", user_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/profiling/history/{user_id}", summary="查询用户风险偏好转换历史")
async def get_history(
    user_id: str,
    _user: UserToken = Depends(get_current_user),
    limit: int = 50,
):
    try:
        mgr = _get_manager()
        history = mgr.get_history(user_id=user_id, limit=limit)
        return {
            "user_id": user_id,
            "count": len(history),
            "history": history,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("查询风险偏好历史失败（user_id=%s）: %s", user_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/profiling/evaluate/{user_id}", summary="评估自动转换")
async def evaluate_transition(
    user_id: str,
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
):
    """评估是否应该触发自动风险偏好转换

    Body:
        {"market_env": "crash", "recent_hit_rate": 0.2}

    Returns:
        {"transitioned": bool, "new_profile": "..." | null}
    """
    try:
        from stockquant.ai.profiling import TransitionContext
        mgr = _get_manager()

        # 构造 TransitionContext（容错：未知字段忽略）
        ctx_kwargs = {}
        for k in ("market_env", "recent_hit_rate", "consecutive_losses",
                 "user_target", "days_since_last"):
            if k in payload:
                ctx_kwargs[k] = payload[k]
        try:
            context = TransitionContext(**ctx_kwargs)
        except TypeError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"TransitionContext 构造失败: {exc}",
            )

        new_profile = mgr.evaluate_transition(context=context, user_id=user_id)
        if new_profile is None:
            return {
                "user_id": user_id,
                "transitioned": False,
                "new_profile": None,
                "message": "未触发自动转换（冷却期内或当前偏好已最保守）",
            }
        logger.info(
            "用户风险偏好自动转换（操作者: %s, user_id: %s, new_profile: %s）",
            _user.sub, user_id, new_profile.value,
        )
        return {
            "user_id": user_id,
            "transitioned": True,
            "new_profile": new_profile.value,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("评估自动转换失败（user_id=%s）: %s", user_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
