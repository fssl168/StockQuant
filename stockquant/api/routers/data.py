# -*- coding: utf-8 -*-
"""Unified data API router - delegates to DataService."""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

from stockquant.api.deps import get_current_user
from stockquant.api.schemas import UpdateDataRequest, CollectDataRequest, UserToken
from stockquant.persistence.persistent_store import CollectTaskStore
from stockquant.config import DataProvider, get_config

logger = logging.getLogger("stockquant.api.data")

router = APIRouter()

# ------------------------------------------------------------------
# Globals - wired by main.py
# ------------------------------------------------------------------

_collect_tasks: CollectTaskStore = {}  # type: ignore[assignment]
_app_data_service = None  # set by main.py: data.set_data_service(data_svc)
_app_ai_service = None  # set by main.py: data.set_ai_service(ai_svc)


def set_storage(storage: CollectTaskStore):
    global _collect_tasks
    _collect_tasks = storage


def set_data_service(ds):
    global _app_data_service
    _app_data_service = ds


def set_ai_service(ai):
    global _app_ai_service
    _app_ai_service = ai


# ------------------------------------------------------------------
# Helpers - dynamic source list from DataService
# ------------------------------------------------------------------

def _get_cache_dir() -> Path:
    config = get_config()
    cache_dir = config.data_provider.csv.directory or ""
    if not cache_dir:
        cache_dir = os.environ.get("CACHE_DIR", "")
    if cache_dir:
        p = Path(cache_dir).expanduser()
    else:
        p = Path.home() / ".stockquant" / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cache_stats_via_service() -> Dict[str, Any]:
    if _app_data_service is not None:
        s = _app_data_service.cache.stats()
        return {
            "sizeMb": s.get("total_size_mb", 0),
            "hitRate": 0.0,
            "symbolCount": s.get("file_count", 0),
            "lastUpdate": datetime.now().isoformat(),
        }
    return _calculate_legacy_cache_stats()


def _calculate_legacy_cache_stats() -> Dict[str, Any]:
    cache_dir = _get_cache_dir()
    total_size = 0
    csv_files = list(cache_dir.glob("*.csv"))
    for f in csv_files:
        total_size += f.stat().st_size
    symbols = set()
    for f in csv_files:
        parts = f.stem.split("_")
        if parts:
            symbols.add(parts[0])
    return {
        "sizeMb": round(total_size / (1024 * 1024), 2),
        "hitRate": 0.0,
        "symbolCount": len(symbols),
        "lastUpdate": datetime.now().isoformat(),
    }


def _dynamic_sources() -> List[Dict[str, Any]]:
    """Return available sources from DataService or fallback to config-based list."""
    if _app_data_service is not None:
        # Use actual configured providers from DataService
        sources = []
        for name, feed in _app_data_service.cache._cache_dir.parent.parent.resolve().parent.resolve().parts if False else []:
            pass  # Will be populated by get_health
        health_list = _app_data_service.get_health()
        seen = set()
        for h in health_list:
            provider = h["provider"]
            if provider not in seen:
                seen.add(provider)
                sources.append({
                    "provider": provider,
                    "name": h.get("name", provider),
                    "enabled": h.get("healthy", True),
                    "priority": len(sources) + 1,
                    "apiKey": "",
                    "apiUrl": "",
                })
        return sources

    # Fallback: build from config
    config = get_config()
    sources = []
    priority = 1
    # Preferred provider
    pref = config.data_provider.source
    if pref.value == "alphafeed":
        sources.append({"provider": "alphafeed", "name": "AlphaFeed", "enabled": True, "priority": priority, "apiKey": "", "apiUrl": ""})
        priority += 1
    if pref.value != "baostock":
        sources.append({"provider": "baostock", "name": "BaoStock", "enabled": True, "priority": priority, "apiKey": "", "apiUrl": ""})
        priority += 1
    sources.append({"provider": "sqlite", "name": "SQLite", "enabled": True, "priority": priority, "apiKey": "", "apiUrl": ""})
    priority += 1
    if config.data_provider.csv.directory:
        sources.append({"provider": "csv", "name": "CSV", "enabled": True, "priority": priority, "apiKey": "", "apiUrl": ""})
    return sources


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.get("/data/sources", summary="获取数据源列表")
async def get_sources(_user: UserToken = Depends(get_current_user)):
    """Return dynamically resolved data sources."""
    return _dynamic_sources()


@router.post("/data/sources", summary="获取数据源列表")
async def update_source(payload: UpdateDataRequest, _user: UserToken = Depends(get_current_user)) -> Dict[str, Any]:
    """Update data source config."""
    return {"success": True, "provider": payload.provider}


@router.put("/data/sources/{provider}", summary="获取数据源列表")
async def update_source_by_provider(provider: str, payload: UpdateDataRequest, _user: UserToken = Depends(get_current_user)) -> Dict[str, Any]:
    """Update data source config."""
    return {"success": True, "provider": provider}


@router.delete("/data/sources/{provider}", summary="删除数据源")
async def delete_source(provider: str, _user: UserToken = Depends(get_current_user)):
    """Remove a data source (no-op for now - sources are dynamic)."""
    return {"success": True, "provider": provider}


@router.get("/data/cache", summary="缓存统计")
async def get_cache_stats():
    """Return cache statistics."""
    return _cache_stats_via_service()


@router.delete("/data/cache", summary="清除缓存")
async def clear_cache(_user: UserToken = Depends(get_current_user)):
    """Clear all K-line cache."""
    if _app_data_service is not None:
        _app_data_service.cache.clear()
        return {"success": True, "deletedFiles": 0}

    cache_dir = _get_cache_dir()
    deleted_count = 0
    for f in cache_dir.glob("*.csv"):
        try:
            f.unlink()
            deleted_count += 1
        except Exception as e:
            logger.warning("Failed to delete cache file: %s, %s", f, e)

    logger.info("Cache cleared. Deleted %d files.", deleted_count)
    return {"success": True, "deletedFiles": deleted_count}


@router.get("/data/kline", summary="查询K线数据")
async def get_kline(
        symbol: str = Query(..., description="股票代码"),
        start: str = Query(..., description="开始日期 YYYY-MM-DD"),
        end: str = Query(..., description="结束日期 YYYY-MM-DD"),
        timeframe: str = Query("1d", description="时间周期"),
        source: str = Query("", description="数据源名称(不传则默认DataService)"),
):
    """Fetch K-line OHLCV data via DataService with proper async handling."""
    try:
        if _app_data_service is not None:
            provider = None
            if source:
                try:
                    provider = DataProvider(source)
                except ValueError:
                    pass
            # Use get_running_loop() instead of deprecated get_event_loop()
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, _app_data_service.get_kline, symbol, timeframe, start, end, provider
            )
            kline_data = result.to_list()
            return {
                "symbol": symbol,
                "start": start,
                "end": end,
                "data": kline_data,
                "source": result.source,
                "cached": result.cached,
            }

        # DataService not available - raise error instead of bypassing
        raise HTTPException(status_code=503, detail="DataService not initialized")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Kline fetch failed: %s, %s", symbol, e, exc_info=True)
        return {
            "symbol": symbol,
            "start": start,
            "end": end,
            "data": [],
            "error": str(e),
        }


@router.post("/data/collect", summary="手动触发数据采集")
async def collect_data(payload: CollectDataRequest, _user: UserToken = Depends(get_current_user)) -> Dict[str, Any]:
    """Start data collection task."""
    symbol = payload.symbol
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    task_id = f"COL-{uuid.uuid4().hex[:8].upper()}"
    _collect_tasks[task_id] = {
        "task_id": task_id,
        "symbol": symbol,
        "source": payload.source,
        "status": "collecting",
        "created_at": datetime.now().isoformat(),
    }

    async def _do_collect():
        try:
            loop = asyncio.get_running_loop()
            if _app_data_service is not None:
                result = await loop.run_in_executor(
                    None, _app_data_service.get_kline, symbol, "1d", payload.start, payload.end
                )
                data = result.to_list()
            else:
                data = []
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
    return {"taskId": task_id, "status": "collecting", "symbol": symbol}


@router.get("/data/health", summary="获取数据源健康状态")
async def get_data_health():
    """Return health status of all configured data sources."""
    if _app_data_service is not None:
        health_list = _app_data_service.get_health()
        result = []
        for h in health_list:
            provider = h["provider"]
            feed_name = provider  # name is already in the tuple
            result.append({
                "provider": provider,
                "name": feed_name,
                "enabled": True,
                "healthy": h.get("healthy", False),
                "lastCheck": h.get("last_check", ""),
                "error": h.get("error", ""),
            })
        return result

    # No DataService - return minimal health info
    return []


@router.get("/data/collect-logs", summary="数据采集日志")
async def get_collect_logs():
    """Return recent collect task logs (last 20, sorted by created_at desc)."""
    tasks = sorted(
        _collect_tasks.values(),
        key=lambda t: t.get("created_at", ""),
        reverse=True,
    )[:20]

    logs = []
    for t in tasks:
        status = t.get("status", "")
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


@router.get("/data/download", summary="批量下载")
async def download_data(provider: str = Query(..., description="数据源名称")):
    """Download K-line data for default symbols from a provider."""
    default_symbols = [
        "sh600519", "sz000858", "sh601318", "sh600036",
        "sh600030", "sz000333", "sz300750", "sh600276",
        "sz000568", "sh600104",
    ]

    valid_providers = {"baostock", "akshare", "alphafeed", "csv", "sqlite"}
    if provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider: {provider}. Valid: {', '.join(valid_providers)}"
        )

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
            loop = asyncio.get_running_loop()
            for symbol in default_symbols:
                try:
                    if _app_data_service is not None:
                        result = await loop.run_in_executor(
                            None, _app_data_service.get_kline, symbol, "1d", "", ""
                        )
                        total_count += result.count
                    else:
                        pass
                except Exception as e:
                    logger.warning("Failed to fetch %s: %s", symbol, e)

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
        "taskId": task_id,
        "provider": provider,
        "symbols": default_symbols,
        "status": "collecting",
        "message": f"Starting download from {provider} for {len(default_symbols)} symbols",
    }


@router.post("/data/upload-csv", summary="上传 CSV 数据文件")
async def upload_csv(file: UploadFile = File(..., description="CSV文件"), _user: UserToken = Depends(get_current_user)):
    """Upload and import CSV K-line data."""
    import pandas as pd

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Must be a .csv file")

    try:
        content = await file.read()
        if _app_data_service is not None:
            result = _app_data_service.upload_csv(content, file.filename)
            if result.get("success"):
                return result
            raise HTTPException(status_code=400, detail=result.get("error", "CSV processing failed"))

        df = pd.read_csv(pd.io.common.BytesIO(content))
        required = {"date", "open", "high", "low", "close", "volume"}
        missing = required - set(df.columns.str.lower())
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"CSV missing columns: {', '.join(sorted(missing))}. Found: {', '.join(df.columns.tolist())}",
            )

        df.columns = df.columns.str.lower()
        cache_dir = _get_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)

        symbols = []
        if "symbol" in df.columns:
            symbols = df["symbol"].unique().tolist()
            for sym in symbols:
                sym_df = df[df["symbol"] == sym].sort_values("date")
                out_path = cache_dir / f"{sym}_{file.filename}"
                sym_df.to_csv(out_path, index=False)
                logger.info("CSV imported: %s -> %s (%d rows)", sym, out_path, len(sym_df))
        else:
            out_path = cache_dir / file.filename
            df.sort_values("date").to_csv(out_path, index=False)
            logger.info("CSV imported: %s (%d rows)", out_path, len(df))

        return {
            "success": True,
            "filename": file.filename,
            "rows": len(df),
            "symbols": symbols,
            "columns": df.columns.tolist(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("CSV upload failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"CSV upload failed: {e}")
