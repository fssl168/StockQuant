# -*- coding: utf-8 -*-
"""F029 数据管理路由 — 数据源/缓存/K线

已接入 BaoStockFeed 真实数据源。
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from stockquant.api.routers.settings import _settings

logger = logging.getLogger("stockquant.api.data")

router = APIRouter()

# 内存存储
_sources: list[dict] = [
    {"provider": "alphafeed", "name": "AlphaFeed", "enabled": True, "priority": 1, "api_key": "", "api_url": ""},
    {"provider": "baostock", "name": "BaoStock", "enabled": True, "priority": 2, "api_key": "", "api_url": ""},
    {"provider": "akshare", "name": "AkShare (降级)", "enabled": True, "priority": 3, "api_key": "", "api_url": ""},
    {"provider": "csv", "name": "CSV 文件", "enabled": False, "priority": 4, "api_key": "", "api_url": ""},
]

# 数据源健康状态
_source_health: dict = {
    "alphafeed": {"healthy": True, "last_check": "", "error": ""},
    "baostock": {"healthy": True, "last_check": "", "error": ""},
    "akshare": {"healthy": True, "last_check": "", "error": ""},
    "csv": {"healthy": True, "last_check": "", "error": ""},
}

# 采集任务
_collect_tasks: dict = {}


# ====================================================================
# 辅助函数
# ====================================================================

def _get_cache_dir() -> Path:
    """获取缓存目录"""
    cache_dir = _settings.get("system.data_dir", "")
    if not cache_dir:
        cache_dir = os.environ.get("CACHE_DIR", "")
    if cache_dir:
        p = Path(cache_dir).expanduser()
    else:
        p = Path.home() / ".stockquant" / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _calculate_cache_stats() -> dict:
    """计算真实缓存统计"""
    cache_dir = _get_cache_dir()
    total_size = 0
    symbol_count = 0
    csv_files = list(cache_dir.glob("*.csv"))

    for f in csv_files:
        total_size += f.stat().st_size

    # 统计不同 symbol 数量
    symbols = set()
    for f in csv_files:
        # 文件名格式: symbol_timeframe_start_end.csv
        parts = f.stem.split("_")
        if parts:
            symbols.add(parts[0])
    symbol_count = len(symbols)

    return {
        "size_mb": round(total_size / (1024 * 1024), 2),
        "hit_rate": 0.0,  # 缓存命中率需要额外跟踪
        "symbol_count": symbol_count,
        "last_update": datetime.now().isoformat(),
    }


def _fetch_kline_sync(symbol: str, start: str, end: str, timeframe: str = "1d") -> list[dict]:
    """同步获取 K 线数据 — AlphaFeed 优先，BaoStock 降级"""
    from stockquant.data.providers.alphafeed_feed import AlphaFeedFeed

    feed = AlphaFeedFeed(
        symbols=[symbol],
        timeframe=timeframe,
        start=start,
        end=end,
        cache_dir=str(_get_cache_dir()),
    )
    feed.start()
    df = feed.get_dataframe()
    feed.stop()

    if df is None or df.empty:
        return []

    # DataFrame 转为前端格式
    kline_data = []
    for idx, row in df.iterrows():
        kline_data.append({
            "date": str(idx) if not isinstance(idx, str) else idx,
            "open": round(float(row.get("open", 0)), 2),
            "high": round(float(row.get("high", 0)), 2),
            "low": round(float(row.get("low", 0)), 2),
            "close": round(float(row.get("close", 0)), 2),
            "volume": int(row.get("volume", 0)),
        })

    return kline_data


# ====================================================================
# 端点
# ====================================================================

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
    return _calculate_cache_stats()


@router.delete("/data/cache", summary="清除缓存")
async def clear_cache():
    """清除所有缓存数据"""
    cache_dir = _get_cache_dir()
    deleted_count = 0
    for f in cache_dir.glob("*.csv"):
        try:
            f.unlink()
            deleted_count += 1
        except Exception as e:
            logger.warning(f"删除缓存文件失败: {f}, {e}")

    logger.info(f"缓存已清除: 删除 {deleted_count} 个文件")
    return {"success": True, "deleted_files": deleted_count}


@router.get("/data/kline", summary="K线数据查询")
async def get_kline(
    symbol: str = Query(..., description="股票代码"),
    start: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end: str = Query(..., description="结束日期 YYYY-MM-DD"),
    timeframe: str = Query("1d", description="时间框架"),
):
    """获取K线数据 (OHLCV) — AlphaFeed 优先，BaoStock 降级"""
    try:
        loop = asyncio.get_event_loop()
        kline_data = await loop.run_in_executor(
            None, _fetch_kline_sync, symbol, start, end, timeframe
        )

        # 更新数据源健康状态
        _source_health["alphafeed"]["healthy"] = True
        _source_health["alphafeed"]["last_check"] = datetime.now().isoformat()

        return {"symbol": symbol, "start": start, "end": end, "data": kline_data}

    except Exception as e:
        logger.error(f"K线数据获取失败: {symbol}, {e}", exc_info=True)
        _source_health["alphafeed"]["healthy"] = False
        _source_health["alphafeed"]["last_check"] = datetime.now().isoformat()
        _source_health["alphafeed"]["error"] = str(e)

        return {"symbol": symbol, "start": start, "end": end, "data": [], "error": str(e)}


@router.post("/data/collect", summary="手动触发数据采集")
async def collect_data(payload: dict):
    """手动触发数据采集/下载"""
    symbol = payload.get("symbol", "")
    source = payload.get("source", "baostock")
    start = payload.get("start", "")
    end = payload.get("end", "")

    if not symbol:
        raise HTTPException(status_code=400, detail="股票代码不能为空")

    task_id = f"COL-{uuid.uuid4().hex[:8].upper()}"
    _collect_tasks[task_id] = {
        "task_id": task_id,
        "symbol": symbol,
        "source": source,
        "status": "collecting",
        "created_at": datetime.now().isoformat(),
    }

    # 异步执行采集
    async def _do_collect():
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, _fetch_kline_sync, symbol, start, end
            )
            _collect_tasks[task_id].update({
                "status": "completed",
                "count": len(data),
                "updated_at": datetime.now().isoformat(),
            })
        except Exception as e:
            _collect_tasks[task_id].update({
                "status": "failed",
                "error": str(e),
                "updated_at": datetime.now().isoformat(),
            })

    asyncio.create_task(_do_collect())

    return {"task_id": task_id, "status": "collecting", "symbol": symbol}


@router.get("/data/health", summary="数据源健康状态")
async def get_data_health():
    """获取各数据源健康状态"""
    result = []
    for source in _sources:
        provider = source["provider"]
        health = _source_health.get(provider, {"healthy": True, "last_check": "", "error": ""})
        result.append({
            "provider": provider,
            "name": source["name"],
            "enabled": source["enabled"],
            "healthy": health["healthy"],
            "last_check": health["last_check"],
            "error": health["error"],
        })
    return result
