# -*- coding: utf-8 -*-
"""F029 投资组合路由 — 持仓/行业/盈亏"""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger("stockquant.api.portfolio")

router = APIRouter()

# 内存存储 (MVP)
_portfolio_data: dict = {
    "summary": {
        "total_value": 1234567.89,
        "total_cost": 1180000.0,
        "total_pnl": 54567.89,
        "total_pnl_pct": 4.62,
        "position_count": 3,
    },
    "positions": [
        {"symbol": "sh600519", "name": "贵州茅台", "shares": 100, "cost": 1680.0, "price": 1725.5, "pnl": 4550.0, "pnl_pct": 2.71, "sector": "白酒"},
        {"symbol": "sz000858", "name": "五粮液", "shares": 500, "cost": 152.0, "price": 148.3, "pnl": -1850.0, "pnl_pct": -2.43, "sector": "白酒"},
        {"symbol": "sh601318", "name": "中国平安", "shares": 300, "cost": 45.5, "price": 47.8, "pnl": 690.0, "pnl_pct": 5.05, "sector": "保险"},
    ],
    "sector_distribution": [
        {"sector": "白酒", "value": 246950.0, "weight": 0.6},
        {"sector": "保险", "value": 14340.0, "weight": 0.2},
        {"sector": "其他", "value": 10000.0, "weight": 0.2},
    ],
    "pnl_analysis": {
        "win_count": 2,
        "loss_count": 1,
        "win_rate": 0.667,
        "avg_win": 2620.0,
        "avg_loss": -1850.0,
        "profit_factor": 1.41,
    },
}


@router.get("/portfolio/positions", summary="持仓列表")
async def get_positions():
    """获取持仓列表"""
    return _portfolio_data["positions"]


@router.get("/portfolio/account", summary="账户汇总")
async def get_account():
    """获取账户汇总信息"""
    return _portfolio_data["summary"]


@router.get("/portfolio/sector", summary="行业分布")
async def get_sector():
    """获取行业分布"""
    return _portfolio_data["sector_distribution"]


@router.get("/portfolio/pnl", summary="盈亏分析")
async def get_pnl():
    """获取盈亏分析"""
    return _portfolio_data["pnl_analysis"]
