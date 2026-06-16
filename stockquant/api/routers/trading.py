# -*- coding: utf-8 -*-
"""F029 交易执行路由 — 下单/撤单/持仓/成交"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("stockquant.api.trading")

router = APIRouter()

# 内存存储 (MVP)
_orders: dict = {}
_trades: list[dict] = []
_positions: list[dict] = [
    {"symbol": "sh600519", "name": "贵州茅台", "shares": 100, "cost": 1680.0, "price": 1725.5, "pnl": 4550.0, "pnl_pct": 2.71},
    {"symbol": "sz000858", "name": "五粮液", "shares": 500, "cost": 152.0, "price": 148.3, "pnl": -1850.0, "pnl_pct": -2.43},
    {"symbol": "sh601318", "name": "中国平安", "shares": 300, "cost": 45.5, "price": 47.8, "pnl": 690.0, "pnl_pct": 5.05},
]
_account: dict = {
    "total_equity": 1234567.89,
    "available_cash": 456789.01,
    "position_value": 777778.88,
    "today_pnl": 12345.67,
    "broker_mode": "paper",
}


@router.get("/trading/account", summary="账户信息")
async def get_account():
    """获取账户信息"""
    return _account


@router.post("/trading/order", summary="下单")
async def place_order(payload: dict):
    """提交订单"""
    symbol = payload.get("symbol", "")
    side = payload.get("side", "BUY")
    order_type = payload.get("type", "MARKET")
    price = payload.get("price", 0)
    quantity = payload.get("quantity", 0)

    if not symbol or quantity <= 0:
        raise HTTPException(status_code=400, detail="股票代码和数量不能为空")

    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now().isoformat()

    order = {
        "order_id": order_id,
        "symbol": symbol,
        "side": side.upper(),
        "type": order_type.upper(),
        "price": price,
        "quantity": quantity,
        "status": "FILLED" if order_type.upper() == "MARKET" else "SUBMITTED",
        "created_at": now,
        "updated_at": now,
    }

    _orders[order_id] = order

    # MARKET 订单自动成交
    if order_type.upper() == "MARKET":
        trade = {
            "trade_id": f"TRD-{uuid.uuid4().hex[:8].upper()}",
            "order_id": order_id,
            "symbol": symbol,
            "side": side.upper(),
            "price": price or 100.0,  # MVP: 使用当前价
            "quantity": quantity,
            "amount": (price or 100.0) * quantity,
            "commission": round((price or 100.0) * quantity * 0.0003, 2),
            "filled_at": now,
        }
        _trades.append(trade)

    logger.info(f"订单已提交: {order_id} {side} {symbol} x{quantity}")
    return order


@router.delete("/trading/order/{order_id}", summary="撤单")
async def cancel_order(order_id: str):
    """撤销订单"""
    if order_id not in _orders:
        raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在")

    order = _orders[order_id]
    if order["status"] in ("FILLED", "CANCELLED"):
        raise HTTPException(status_code=400, detail=f"订单状态 {order['status']} 不可撤单")

    order["status"] = "CANCELLED"
    order["updated_at"] = datetime.now().isoformat()
    logger.info(f"订单已撤销: {order_id}")
    return {"success": True, "order_id": order_id, "status": "CANCELLED"}


@router.get("/trading/positions", summary="持仓列表")
async def get_positions():
    """获取当前持仓"""
    return _positions


@router.get("/trading/trades", summary="成交记录")
async def get_trades():
    """获取成交记录"""
    return sorted(_trades, key=lambda t: t.get("filled_at", ""), reverse=True)


@router.get("/trading/orders", summary="订单列表")
async def get_orders():
    """获取订单列表"""
    return list(_orders.values())
