# -*- coding: utf-8 -*-
"""预警规则 CRUD 路由 — 内存存储（线程安全）

对应前端 alertStore.ts 的 /api/alerts/rules 端点。
支持价格、深度变化、指数联动、板块联动四类预警规则的增删改查。
"""

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from stockquant.api.deps import get_current_user
from stockquant.api.schemas import UserToken

logger = logging.getLogger("stockquant.api.alerts")

router = APIRouter(prefix="/alerts", tags=["预警规则"])

# ── 内存存储（线程安全） ──
_rules_store: Dict[str, Dict[str, Any]] = {}
_rules_lock = threading.Lock()


# ── Pydantic 模型 ──

VALID_TYPES = {"price", "depth_change", "index_correlation", "sector_correlation"}
VALID_CHANNELS = {"dingtalk", "email", "telegram", "sound", "browser"}


class AlertRuleCreate(BaseModel):
    """创建预警规则请求体"""
    name: str = Field(..., min_length=1, max_length=100)
    type: str
    symbol: Optional[str] = None
    indexSymbol: Optional[str] = None
    sector: Optional[str] = None
    enabled: bool = True
    conditions: Optional[Dict[str, Any]] = None
    notifyVia: List[str] = Field(default_factory=list)
    soundLevel: Optional[str] = None


class AlertRuleUpdate(BaseModel):
    """更新预警规则请求体（所有字段可选）"""
    name: Optional[str] = None
    type: Optional[str] = None
    symbol: Optional[str] = None
    indexSymbol: Optional[str] = None
    sector: Optional[str] = None
    enabled: Optional[bool] = None
    conditions: Optional[Dict[str, Any]] = None
    notifyVia: Optional[List[str]] = None
    soundLevel: Optional[str] = None


def _validate_rule_fields(type_: Optional[str], notify_via: Optional[List[str]]) -> None:
    """校验规则类型和通知渠道合法性"""
    if type_ is not None and type_ not in VALID_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"无效的规则类型: {type_}，支持: {sorted(VALID_TYPES)}",
        )
    if notify_via is not None:
        invalid = set(notify_via) - VALID_CHANNELS
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"无效的通知渠道: {sorted(invalid)}，支持: {sorted(VALID_CHANNELS)}",
            )


def _now_iso() -> str:
    """返回当前 UTC 时间的 ISO8601 字符串"""
    return datetime.now(timezone.utc).isoformat()


# ── API 端点 ──

@router.get("/rules", response_model=List[Dict[str, Any]])
def list_rules(_user: UserToken = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """获取所有预警规则"""
    with _rules_lock:
        return list(_rules_store.values())


@router.post("/rules", response_model=Dict[str, Any], status_code=201)
def create_rule(
    body: AlertRuleCreate,
    _user: UserToken = Depends(get_current_user),
) -> Dict[str, Any]:
    """创建预警规则"""
    _validate_rule_fields(body.type, body.notifyVia)

    rule_id = str(uuid.uuid4())
    now = _now_iso()
    rule: Dict[str, Any] = {
        "id": rule_id,
        "name": body.name,
        "type": body.type,
        "symbol": body.symbol,
        "indexSymbol": body.indexSymbol,
        "sector": body.sector,
        "enabled": body.enabled,
        "conditions": body.conditions or {},
        "notifyVia": body.notifyVia,
        "soundLevel": body.soundLevel,
        "createdAt": now,
        "updatedAt": now,
    }
    with _rules_lock:
        _rules_store[rule_id] = rule
    logger.info("预警规则已创建: id=%s, name=%s, type=%s", rule_id, body.name, body.type)
    return rule


@router.put("/rules/{rule_id}", response_model=Dict[str, Any])
def update_rule(
    rule_id: str,
    body: AlertRuleUpdate,
    _user: UserToken = Depends(get_current_user),
) -> Dict[str, Any]:
    """更新预警规则（部分更新）"""
    _validate_rule_fields(body.type, body.notifyVia)

    with _rules_lock:
        if rule_id not in _rules_store:
            raise HTTPException(status_code=404, detail=f"预警规则不存在: {rule_id}")
        rule = _rules_store[rule_id]
        # 仅更新非 None 字段
        update_data = body.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            rule[key] = value
        rule["updatedAt"] = _now_iso()
        return rule


@router.delete("/rules/{rule_id}", response_model=Dict[str, str])
def delete_rule(
    rule_id: str,
    _user: UserToken = Depends(get_current_user),
) -> Dict[str, str]:
    """删除预警规则"""
    with _rules_lock:
        if rule_id not in _rules_store:
            raise HTTPException(status_code=404, detail=f"预警规则不存在: {rule_id}")
        del _rules_store[rule_id]
    logger.info("预警规则已删除: id=%s", rule_id)
    return {"status": "deleted", "id": rule_id}
