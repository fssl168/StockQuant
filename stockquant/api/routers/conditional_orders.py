# -*- coding: utf-8 -*-
"""条件单 CRUD 路由 — 内存存储（线程安全）

对应前端 conditionalOrderStore.ts 的 /api/conditional-orders 端点。
支持突破买入、回调卖出两类条件单的创建、更新、取消、删除。
"""

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from stockquant.api.deps import get_current_user, get_required_user
from stockquant.api.schemas import UserToken

logger = logging.getLogger("stockquant.api.conditional_orders")

router = APIRouter(prefix="/conditional-orders", tags=["条件单"])

# ── 内存存储（线程安全） ──
_orders_store: Dict[str, Dict[str, Any]] = {}
_orders_lock = threading.Lock()


# ── 常量与校验 ──

VALID_TYPES = {"breakout_buy", "pullback_sell"}
VALID_STATUSES = {"active", "triggered", "expired", "cancelled"}
VALID_LOGIC = {"AND", "OR"}
VALID_CONDITION_FIELDS = {"price", "volume", "indicator", "time"}
VALID_CONDITION_OPERATORS = {"gt", "lt", "gte", "lte", "cross_above", "cross_below"}
VALID_ACTION_SIDES = {"BUY", "SELL"}
VALID_ACTION_ORDER_TYPES = {"MARKET", "LIMIT"}


# ── Pydantic 模型 ──

class ConditionalOrderCondition(BaseModel):
    id: str
    field: str
    operator: str
    value: Any  # number | string
    label: Optional[str] = None


class ConditionalOrderAction(BaseModel):
    side: str  # 'BUY' | 'SELL'
    quantity: float
    orderType: str  # 'MARKET' | 'LIMIT'
    limitOffset: Optional[float] = None


class ConditionalOrderCreate(BaseModel):
    """创建条件单请求体"""
    name: str = Field(..., min_length=1, max_length=100)
    type: str
    symbol: str = Field(..., min_length=1)
    conditions: List[ConditionalOrderCondition] = Field(default_factory=list)
    logic: str = "AND"
    action: ConditionalOrderAction
    validUntil: Optional[str] = None
    templateId: Optional[str] = None


class ConditionalOrderUpdate(BaseModel):
    """更新条件单请求体（所有字段可选）"""
    name: Optional[str] = None
    type: Optional[str] = None
    symbol: Optional[str] = None
    conditions: Optional[List[ConditionalOrderCondition]] = None
    logic: Optional[str] = None
    action: Optional[ConditionalOrderAction] = None
    status: Optional[str] = None
    validUntil: Optional[str] = None
    templateId: Optional[str] = None


def _validate_order_fields(
    type_: Optional[str] = None,
    logic: Optional[str] = None,
    status: Optional[str] = None,
    conditions: Optional[List[ConditionalOrderCondition]] = None,
    action: Optional[ConditionalOrderAction] = None,
) -> None:
    """校验条件单字段合法性"""
    if type_ is not None and type_ not in VALID_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"无效的条件单类型: {type_}，支持: {sorted(VALID_TYPES)}",
        )
    if logic is not None and logic not in VALID_LOGIC:
        raise HTTPException(
            status_code=422,
            detail=f"无效的逻辑类型: {logic}，支持: {sorted(VALID_LOGIC)}",
        )
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"无效的状态: {status}，支持: {sorted(VALID_STATUSES)}",
        )
    if conditions is not None:
        for cond in conditions:
            if cond.field not in VALID_CONDITION_FIELDS:
                raise HTTPException(
                    status_code=422,
                    detail=f"无效的条件字段: {cond.field}，支持: {sorted(VALID_CONDITION_FIELDS)}",
                )
            if cond.operator not in VALID_CONDITION_OPERATORS:
                raise HTTPException(
                    status_code=422,
                    detail=f"无效的比较运算符: {cond.operator}，支持: {sorted(VALID_CONDITION_OPERATORS)}",
                )
    if action is not None:
        if action.side not in VALID_ACTION_SIDES:
            raise HTTPException(
                status_code=422,
                detail=f"无效的交易方向: {action.side}，支持: {sorted(VALID_ACTION_SIDES)}",
            )
        if action.orderType not in VALID_ACTION_ORDER_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"无效的订单类型: {action.orderType}，支持: {sorted(VALID_ACTION_ORDER_TYPES)}",
            )


def _now_iso() -> str:
    """返回当前 UTC 时间的 ISO8601 字符串"""
    return datetime.now(timezone.utc).isoformat()


# ── API 端点 ──

@router.get("", response_model=List[Dict[str, Any]])
def list_orders(_user: UserToken = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """获取所有条件单"""
    with _orders_lock:
        return list(_orders_store.values())


@router.post("", response_model=Dict[str, Any], status_code=201)
def create_order(
    body: ConditionalOrderCreate,
    _user: UserToken = Depends(get_required_user),
) -> Dict[str, Any]:
    """创建条件单"""
    _validate_order_fields(
        type_=body.type, logic=body.logic, conditions=body.conditions, action=body.action
    )

    order_id = str(uuid.uuid4())
    now = _now_iso()
    order: Dict[str, Any] = {
        "id": order_id,
        "name": body.name,
        "type": body.type,
        "symbol": body.symbol,
        "conditions": [c.model_dump() for c in body.conditions],
        "logic": body.logic,
        "action": body.action.model_dump(),
        "status": "active",
        "validUntil": body.validUntil,
        "templateId": body.templateId,
        "createdAt": now,
        "updatedAt": now,
    }
    with _orders_lock:
        _orders_store[order_id] = order
    logger.info("条件单已创建: id=%s, name=%s, symbol=%s, type=%s", order_id, body.name, body.symbol, body.type)
    return order


@router.put("/{order_id}", response_model=Dict[str, Any])
def update_order(
    order_id: str,
    body: ConditionalOrderUpdate,
    _user: UserToken = Depends(get_required_user),
) -> Dict[str, Any]:
    """更新条件单（部分更新）"""
    _validate_order_fields(
        type_=body.type,
        logic=body.logic,
        status=body.status,
        conditions=body.conditions,
        action=body.action,
    )

    with _orders_lock:
        if order_id not in _orders_store:
            raise HTTPException(status_code=404, detail=f"条件单不存在: {order_id}")
        order = _orders_store[order_id]
        update_data = body.model_dump(exclude_unset=True)
        # Pydantic 嵌套模型需手动转换为 dict
        if "conditions" in update_data and update_data["conditions"] is not None:
            update_data["conditions"] = [
                c if isinstance(c, dict) else c.model_dump()
                for c in update_data["conditions"]
            ]
        if "action" in update_data and update_data["action"] is not None:
            action = update_data["action"]
            update_data["action"] = action if isinstance(action, dict) else action.model_dump()
        for key, value in update_data.items():
            order[key] = value
        order["updatedAt"] = _now_iso()
        return order


@router.post("/{order_id}/cancel", response_model=Dict[str, Any])
def cancel_order(
    order_id: str,
    _user: UserToken = Depends(get_required_user),
) -> Dict[str, Any]:
    """取消条件单（将状态置为 cancelled）"""
    with _orders_lock:
        if order_id not in _orders_store:
            raise HTTPException(status_code=404, detail=f"条件单不存在: {order_id}")
        order = _orders_store[order_id]
        if order["status"] in ("triggered", "expired", "cancelled"):
            raise HTTPException(
                status_code=409,
                detail=f"条件单状态为 {order['status']}，无法取消",
            )
        order["status"] = "cancelled"
        order["updatedAt"] = _now_iso()
        logger.info("条件单已取消: id=%s", order_id)
        return order


@router.delete("/{order_id}", response_model=Dict[str, str])
def delete_order(
    order_id: str,
    _user: UserToken = Depends(get_required_user),
) -> Dict[str, str]:
    """删除条件单"""
    with _orders_lock:
        if order_id not in _orders_store:
            raise HTTPException(status_code=404, detail=f"条件单不存在: {order_id}")
        del _orders_store[order_id]
    logger.info("条件单已删除: id=%s", order_id)
    return {"status": "deleted", "id": order_id}
