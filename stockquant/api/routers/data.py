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

from stockquant.api.routers.settings import _settings, _decrypt_value

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


def set_storage(storage: dict):
    global _collect_tasks
    _collect_tasks = storage


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


def _fetch_kline_baostock(symbol: str, start: str, end: str, timeframe: str = "1d") -> list[dict]:
    """使用 BaoStock 获取 K 线数据（最终降级方案）"""
    import baostock as bs

    # BaoStock 全局只有一个登录会话，确保干净状态
    try:
        bs.logout()
    except Exception:
        pass

    rs = bs.login()
    if rs.error_code != "0":
        logger.error(f"BaoStock login failed: {rs.error_msg}")
        return []

    try:
        fields = "date,open,high,low,close,volume"

        upper_s = symbol.upper()
        if upper_s.startswith("SH"):
            bs_symbol = f"sh.{symbol[2:]}"
        elif upper_s.startswith("SZ"):
            bs_symbol = f"sz.{symbol[2:]}"
        elif upper_s.startswith("BJ"):
            bs_symbol = f"bj.{symbol[2:]}"
        elif len(symbol) == 6 and symbol[0] in ("6", "5", "9"):
            bs_symbol = f"sh.{symbol}"
        elif len(symbol) == 6 and symbol[0] in ("0", "3", "1"):
            bs_symbol = f"sz.{symbol}"
        else:
            bs_symbol = symbol

        bs_start = start[:10] if len(start) >= 10 else start
        bs_end = end[:10] if len(end) >= 10 else end

        freq_map = {"1d": "d", "1w": "w", "1M": "d", "1m": "5", "5m": "5", "15m": "15", "30m": "30", "60m": "60"}
        freq = freq_map.get(timeframe, "d")

        kdata = bs.query_history_k_data_plus(
            bs_symbol, fields,
            start_date=bs_start, end_date=bs_end,
            frequency=freq, adjustflag="2",
        )

        if kdata.error_code != "0":
            logger.error(f"BaoStock query failed for {symbol}: {kdata.error_msg}")
            return []

        rows = []
        while kdata.error_code == "0" and kdata.next():
            rows.append(kdata.get_row_data())

        kline_data = []
        for r in rows:
            if len(r) >= 6:
                kline_data.append({
                    "date": r[0],
                    "open": round(float(r[1]), 2),
                    "high": round(float(r[2]), 2),
                    "low": round(float(r[3]), 2),
                    "close": round(float(r[4]), 2),
                    "volume": int(float(r[5])),
                })

        logger.info(f"BaoStock: fetched {len(kline_data)} bars for {symbol}")
        return kline_data

    finally:
        try:
            bs.logout()
        except Exception:
            pass


def _fetch_kline_sync(symbol: str, start: str, end: str, timeframe: str = "1d") -> list[dict]:
    """同步获取 K 线数据 — AlphaFeed 优先，AkShare 降级，BaoStock 兜底"""
    # 优先尝试 AlphaFeed/AkShare
    from stockquant.data.providers.alphafeed_feed import AlphaFeedFeed

    _alphafeed_key = _decrypt_value(_settings.get("data_provider.alphafeed_key", ""))

    feed = AlphaFeedFeed(
        symbols=[symbol],
        timeframe=timeframe,
        start=start,
        end=end,
        cache_dir=str(_get_cache_dir()),
        api_key=_alphafeed_key or None,
    )
    feed.start()
    df = feed.get_dataframe()
    feed.stop()

    if df is not None and not df.empty:
        # DataFrame 转为前端格式 — 兼容多种列名格式
        kline_data = []
        for _, row in df.iterrows():
            # 优先使用 datetime 列，其次 date
            date_val = row.get("datetime", row.get("date", str(_)))
            if hasattr(date_val, "strftime"):
                date_val = date_val.strftime("%Y-%m-%d")
            elif isinstance(date_val, (int, float)):
                from datetime import datetime as _dt
                date_val = _dt.fromtimestamp(date_val / 1000 if date_val > 1e12 else date_val).strftime("%Y-%m-%d")
            elif isinstance(date_val, str):
                # 如果是数字字符串（索引），跳过用 date 列
                if date_val.isdigit() and "date" in row.index:
                    date_val = row["date"]
            kline_data.append({
                "date": str(date_val),
                "open": round(float(row.get("open", 0)), 2),
                "high": round(float(row.get("high", 0)), 2),
                "low": round(float(row.get("low", 0)), 2),
                "close": round(float(row.get("close", 0)), 2),
                "volume": int(row.get("volume", 0)),
            })
        return kline_data

    # AlphaFeed/AkShare 失败，降级到 BaoStock
    logger.info(f"AlphaFeed/AkShare 无数据，降级到 BaoStock 获取 {symbol}")
    return _fetch_kline_baostock(symbol, start, end, timeframe)


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
    source = payload.get("source", "alphafeed")
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


@router.get("/data/collect-logs", summary="数据采集日志")
async def get_collect_logs():
    """获取数据采集任务历史日志。

    从内存中的 _collect_tasks 返回最近 20 条采集记录，
    按 created_at 倒序排列。
    """
    tasks = sorted(
        _collect_tasks.values(),
        key=lambda t: t.get("created_at", ""),
        reverse=True,
    )[:20]

    logs = []
    for t in tasks:
        status = t.get("status", "")
        # 状态映射：collecting → warning, completed → success, failed → error
        status_label = "warning" if status == "collecting" else (
            "success" if status == "completed" else "error"
        )
        logs.append({
            "key": t.get("task_id", ""),
            "time": t.get("created_at", ""),
            "source": t.get("source", ""),
            "symbol": t.get("symbol", ""),
            "status": status_label,
            "records": t.get("count", 0),
            "note": t.get("error", "") if status == "failed" else "",
        })

    return logs


@router.get("/data/download", summary="批量下载数据")
async def download_data(provider: str = Query(..., description="数据源名称")):
    """触发指定数据源的批量下载。

    下载默认股票池（沪深300成分股前10只）的最新日线数据。
    """
    # 默认股票池（沪深300前10只成分股）
    default_symbols = [
        "sh600519", "sz000858", "sh601318", "sh600036",
        "sh600030", "sz000333", "sz300750", "sh600276",
        "sz000568", "sh600104",
    ]

    # 验证 provider
    valid_providers = {"baostock", "akshare", "alphafeed", "csv"}
    if provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的数据源: {provider}, 支持: {', '.join(valid_providers)}"
        )

    # 生成下载任务
    task_id = f"DL-{uuid.uuid4().hex[:8].upper()}"
    _collect_tasks[task_id] = {
        "task_id": task_id,
        "symbol": ",".join(default_symbols[:3]) + "...",
        "source": provider,
        "status": "collecting",
        "created_at": datetime.now().isoformat(),
    }

    total_count = 0

    async def _do_download():
        nonlocal total_count
        try:
            loop = asyncio.get_event_loop()
            for symbol in default_symbols:
                try:
                    data = await loop.run_in_executor(
                        None, _fetch_kline_sync, symbol, "", "", "1d"
                    )
                    total_count += len(data)
                except Exception as e:
                    logger.warning(f"下载 {symbol} 失败: {e}")

            _collect_tasks[task_id].update({
                "status": "completed",
                "count": total_count,
                "updated_at": datetime.now().isoformat(),
            })
        except Exception as e:
            _collect_tasks[task_id].update({
                "status": "failed",
                "error": str(e),
                "updated_at": datetime.now().isoformat(),
            })

    asyncio.create_task(_do_download())

    return {
        "success": True,
        "task_id": task_id,
        "provider": provider,
        "symbols": default_symbols,
        "status": "collecting",
        "message": f"已启动 {provider} 数据下载任务，共 {len(default_symbols)} 只股票",
    }
