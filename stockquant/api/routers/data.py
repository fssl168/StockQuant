# -*- coding: utf-8 -*-
"""F029 数据管理路由 — 数据源/缓存/K线"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("stockquant.api.data")

router = APIRouter()

# 内存存储
_sources: list[dict] = [
    {"provider": "baostock", "name": "BaoStock", "enabled": True, "priority": 1, "api_key": "", "api_url": ""},
    {"provider": "akshare", "name": "AkShare", "enabled": True, "priority": 2, "api_key": "", "api_url": ""},
    {"provider": "csv", "name": "CSV 文件", "enabled": False, "priority": 3, "api_key": "", "api_url": ""},
]
_cache_stats: dict = {
    "size_mb": 256.3,
    "hit_rate": 0.87,
    "symbol_count": 152,
    "last_update": datetime.now().isoformat(),
}


@router.get("/data/sources", summary="获取数据源列表")
async def get_sources():
    """获取所有数据源配置"""
    return _sources


@router.post("/data/sources", summary="更新数据源配置")
async def update_source(payload: dict):
    """更新数据源配置"""
    provider = payload.get("provider")
    for i, s in enumerate(_sources):
        if s["provider"] == provider:
            _sources[i].update(payload)
            return {"success": True, "provider": provider}
    raise HTTPException(status_code=404, detail=f"数据源 {provider} 不存在")


@router.get("/data/cache", summary="缓存统计")
async def get_cache_stats():
    """获取缓存统计信息"""
    return _cache_stats


@router.delete("/data/cache", summary="清除缓存")
async def clear_cache():
    """清除所有缓存数据"""
    _cache_stats["size_mb"] = 0
    _cache_stats["hit_rate"] = 0
    _cache_stats["symbol_count"] = 0
    _cache_stats["last_update"] = datetime.now().isoformat()
    return {"success": True, "message": "缓存已清除"}


@router.get("/data/kline", summary="K线数据查询")
async def get_kline(
    symbol: str = Query(..., description="股票代码"),
    start: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    """获取K线数据 (OHLCV)"""
    # MVP: 生成模拟 K 线数据
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    dates = []
    current = start_dt
    while current <= end_dt:
        if current.weekday() < 5:  # 跳过周末
            dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    base_price = random.uniform(10, 200)
    kline_data = []
    for d in dates:
        open_p = base_price + random.uniform(-2, 2)
        close_p = open_p + random.uniform(-3, 3)
        high_p = max(open_p, close_p) + random.uniform(0, 2)
        low_p = min(open_p, close_p) - random.uniform(0, 2)
        volume = int(random.uniform(100000, 5000000))
        kline_data.append({
            "date": d,
            "open": round(open_p, 2),
            "close": round(close_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "volume": volume,
        })
        base_price = close_p

    return {"symbol": symbol, "start": start, "end": end, "data": kline_data}
