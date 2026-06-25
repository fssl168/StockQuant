# -*- coding: utf-8 -*-
"""F029 ?????? ? ??? / ?? / K?

??? DataService ??????
? DataService ?????????? _fetch_kline_baostock ???
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, File

from stockquant.api.routers.settings import _settings, _decrypt_value
from stockquant.api.schemas import UpdateDataRequest, CollectDataRequest
from stockquant.persistence.persistent_store import CollectTaskStore
from stockquant.config import DataProvider

logger = logging.getLogger("stockquant.api.data")

router = APIRouter()

# ------------------------------------------------------------------
# ???? & ????
# ------------------------------------------------------------------

_collect_tasks: CollectTaskStore = {}  # type: ignore[assignment]
_app_data_service = None  # set by main.py: data.set_data_service(data_svc)


def set_storage(storage: CollectTaskStore):
    global _collect_tasks
    _collect_tasks = storage


def set_data_service(ds):
    global _app_data_service
    _app_data_service = ds


# ???????????????
_sources: list[dict] = [
    {"provider": "alphafeed", "name": "AlphaFeed", "enabled": True, "priority": 1, "api_key": "", "api_url": ""},
    {"provider": "baostock", "name": "BaoStock", "enabled": True, "priority": 2, "api_key": "", "api_url": ""},
    {"provider": "akshare", "name": "AkShare (??)", "enabled": True, "priority": 3, "api_key": "", "api_url": ""},
    {"provider": "csv", "name": "CSV ??", "enabled": False, "priority": 4, "api_key": "", "api_url": ""},
]

# AI ????????
_collector_sources: list[dict] = [
    {"provider": "eastmoney", "name": "??????", "enabled": True, "category": "??", "description": "7x24 ??????"},
    {"provider": "xueqiu", "name": "????", "enabled": True, "category": "????", "description": "????????"},
    {"provider": "cls", "name": "?????", "enabled": True, "category": "??", "description": "?????????"},
    {"provider": "akshare_news", "name": "AkShare ??", "enabled": True, "category": "??", "description": "AkShare ??????"},
    {"provider": "alphafeed_news", "name": "AlphaFeed ??", "enabled": True, "category": "??", "description": "AlphaFeed ?????? API Key?"},
]

# ???????
_source_health: dict = {
    "alphafeed": {"healthy": True, "last_check": "", "error": ""},
    "baostock": {"healthy": True, "last_check": "", "error": ""},
    "akshare": {"healthy": True, "last_check": "", "error": ""},
    "csv": {"healthy": True, "last_check": "", "error": ""},
}


# ====================================================================
# ????
# ====================================================================

def _get_cache_dir() -> Path:
    cache_dir = _settings.get("system.data_dir", "")
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
        # ???????
        return {
            "size_mb": s.get("total_size_mb", 0),
            "hit_rate": 0.0,
            "symbol_count": s.get("file_count", 0),
            "last_update": datetime.now().isoformat(),
        }
    return _calculate_legacy_cache_stats()


def _calculate_legacy_cache_stats() -> Dict[str, Any]:
    cache_dir = _get_cache_dir()
    total_size = 0
    symbol_count = 0
    csv_files = list(cache_dir.glob("*.csv"))
    for f in csv_files:
        total_size += f.stat().st_size
    symbols = set()
    for f in csv_files:
        parts = f.stem.split("_")
        if parts:
            symbols.add(parts[0])
    return {
        "size_mb": round(total_size / (1024 * 1024), 2),
        "hit_rate": 0.0,
        "symbol_count": len(symbols),
        "last_update": datetime.now().isoformat(),
    }


def _fetch_kline_baostock(symbol: str, start: str, end: str, timeframe: str = "1d") -> List[Dict[str, Any]]:
    """BaoStock ???? K ???????????"""
    import baostock as bs
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


def _fetch_kline_fallback(symbol: str, start: str, end: str, timeframe: str = "1d") -> List[Dict[str, Any]]:
    """?? fetch ???AlphaFeed ? BaoStock ????? DataService ???????"""
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
        kline_data = []
        for _, row in df.iterrows():
            date_val = row.get("datetime", row.get("date", str(_)))
            if hasattr(date_val, "strftime"):
                date_val = date_val.strftime("%Y-%m-%d")
            elif isinstance(date_val, (int, float)):
                from datetime import datetime as _dt
                date_val = _dt.fromtimestamp(date_val / 1000 if date_val > 1e12 else date_val).strftime("%Y-%m-%d")
            elif isinstance(date_val, str) and date_val.isdigit() and "date" in row.index:
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

    logger.info(f"AlphaFeed/AkShare ??????? BaoStock ?? {symbol}")
    return _fetch_kline_baostock(symbol, start, end, timeframe)


# ====================================================================
# ??
# ====================================================================

@router.get("/data/sources", summary="???????")
async def get_sources():
    """?????????"""
    return _sources


@router.post("/data/sources", summary="???????")
async def update_source(payload: UpdateDataRequest) -> Dict[str, Any]:
    """???????"""
    provider = payload.provider
    for i, s in enumerate(_sources):
        if s["provider"] == provider:
            _sources[i].update(payload.model_dump())
            return {"success": True, "provider": provider}
    raise HTTPException(status_code=404, detail=f"??? {provider} ???")


@router.put("/data/sources/{provider}", summary="?????????")
async def update_source_by_provider(provider: str, payload: UpdateDataRequest) -> Dict[str, Any]:
    """?????????"""
    for i, s in enumerate(_sources):
        if s["provider"] == provider:
            _sources[i].update(payload.model_dump())
            return {"success": True, "provider": provider}
    raise HTTPException(status_code=404, detail=f"??? {provider} ???")


@router.delete("/data/sources/{provider}", summary="?????")
async def delete_source(provider: str):
    """?????????"""
    original_len = len(_sources)
    _sources[:] = [s for s in _sources if s["provider"] != provider]
    if len(_sources) == original_len:
        raise HTTPException(status_code=404, detail=f"??? {provider} ???")
    return {"success": True, "provider": provider}


@router.get("/data/cache", summary="????")
async def get_cache_stats():
    """????????"""
    return _cache_stats_via_service()


@router.delete("/data/cache", summary="????")
async def clear_cache():
    """????????"""
    if _app_data_service is not None:
        _app_data_service.cache.clear()
        return {"success": True, "deleted_files": 0}

    cache_dir = _get_cache_dir()
    deleted_count = 0
    for f in cache_dir.glob("*.csv"):
        try:
            f.unlink()
            deleted_count += 1
        except Exception as e:
            logger.warning(f"????????: {f}, {e}")

    logger.info(f"?????. ?? {deleted_count} ???")
    return {"success": True, "deleted_files": deleted_count}


@router.get("/data/kline", summary="K?????")
async def get_kline(
    symbol: str = Query(..., description="????"),
    start: str = Query(..., description="???? YYYY-MM-DD"),
    end: str = Query(..., description="???? YYYY-MM-DD"),
    timeframe: str = Query("1d", description="????"),
    source: str = Query("", description="?????????????? DataService?"),
):
    """??K??? (OHLCV) ? DataService ?????????"""
    try:
        if _app_data_service is not None:
            provider = None
            if source:
                try:
                    provider = DataProvider(source)
                except ValueError:
                    pass
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, _app_data_service.get_kline, symbol, timeframe, start, end, provider
            )
            kline_data = result.to_list()
            _source_health["alphafeed"]["healthy"] = True
            _source_health["alphafeed"]["last_check"] = datetime.now().isoformat()
            return {"symbol": symbol, "start": start, "end": end, "data": kline_data,
                    "source": result.source, "cached": result.cached}

        # ??????? fetch ??
        loop = asyncio.get_event_loop()
        kline_data = await loop.run_in_executor(
            None, _fetch_kline_fallback, symbol, start, end, timeframe
        )
        _source_health["alphafeed"]["healthy"] = True
        _source_health["alphafeed"]["last_check"] = datetime.now().isoformat()
        return {"symbol": symbol, "start": start, "end": end, "data": kline_data}

    except Exception as e:
        logger.error(f"K???????: {symbol}, {e}", exc_info=True)
        _source_health["alphafeed"]["healthy"] = False
        _source_health["alphafeed"]["last_check"] = datetime.now().isoformat()
        _source_health["alphafeed"]["error"] = str(e)
        return {"symbol": symbol, "start": start, "end": end, "data": [], "error": str(e)}


@router.post("/data/collect", summary="????????")
async def collect_data(payload: CollectDataRequest) -> Dict[str, Any]:
    """????????/??"""
    symbol = payload.symbol
    source = payload.source
    start = payload.start
    end = payload.end

    if not symbol:
        raise HTTPException(status_code=400, detail="????????")

    task_id = f"COL-{uuid.uuid4().hex[:8].upper()}"
    _collect_tasks[task_id] = {
        "task_id": task_id,
        "symbol": symbol,
        "source": source,
        "status": "collecting",
        "created_at": datetime.now().isoformat(),
    }

    async def _do_collect():
        try:
            loop = asyncio.get_event_loop()
            if _app_data_service is not None:
                result = await loop.run_in_executor(
                    None, _app_data_service.get_kline, symbol, "1d", start, end
                )
                data = result.to_list()
            else:
                data = await loop.run_in_executor(
                    None, _fetch_kline_fallback, symbol, start, end
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


@router.get("/data/health", summary="???????")
async def get_data_health():
    """??????????"""
    if _app_data_service is not None:
        # ?? DataService ????
        health_list = _app_data_service.get_health()
        result = []
        for h in health_list:
            result.append({
                "provider": h["provider"],
                "name": next((s["name"] for s in _sources if s["provider"] == h["provider"]), h["provider"]),
                "enabled": True,
                "healthy": h["healthy"],
                "last_check": h["last_check"],
                "error": h.get("error", ""),
            })
        return result

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


@router.get("/data/collect-logs", summary="??????")
async def get_collect_logs():
    """?????????????

    ????? _collect_tasks ???? 20 ??????
    ? created_at ?????
    """
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


@router.get("/data/download", summary="??????")
async def download_data(provider: str = Query(..., description="?????")):
    """?????????????

    ??????????300????10??????????
    """
    default_symbols = [
        "sh600519", "sz000858", "sh601318", "sh600036",
        "sh600030", "sz000333", "sz300750", "sh600276",
        "sz000568", "sh600104",
    ]

    valid_providers = {"baostock", "akshare", "alphafeed", "csv"}
    if provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"???????: {provider}, ??: {', '.join(valid_providers)}"
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
            loop = asyncio.get_event_loop()
            for symbol in default_symbols:
                try:
                    if _app_data_service is not None:
                        result = await loop.run_in_executor(
                            None, _app_data_service.get_kline, symbol, "1d", "", ""
                        )
                        total_count += result.count
                    else:
                        data = await loop.run_in_executor(
                            None, _fetch_kline_fallback, symbol, "", "", "1d"
                        )
                        total_count += len(data)
                except Exception as e:
                    logger.warning(f"?? {symbol} ??: {e}")

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
        "message": f"??? {provider} ???????? {len(default_symbols)} ???",
    }


@router.post("/data/upload-csv", summary="?? CSV ????")
async def upload_csv(file: UploadFile = File(..., description="CSV ??")):
    """?? CSV ???????????????????

    CSV ?????
    - ?????: date, open, high, low, close, volume
    - ???: symbol?? symbol ????????????????
    - ????: YYYY-MM-DD
    """
    import pandas as pd

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="??? .csv ??")

    try:
        content = await file.read()
        if _app_data_service is not None:
            result = _app_data_service.upload_csv(content, file.filename)
            if result.get("success"):
                return result
            raise HTTPException(status_code=400, detail=result.get("error", "CSV????"))

        df = pd.read_csv(pd.io.common.BytesIO(content))
        required = {"date", "open", "high", "low", "close", "volume"}
        missing = required - set(df.columns.str.lower())
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"CSV ?????: {', '.join(sorted(missing))}????: {', '.join(df.columns.tolist())}",
            )

        df.columns = df.columns.str.lower()
        cache_dir = Path(_settings.get("data.cache_dir", "data/cache"))
        cache_dir.mkdir(parents=True, exist_ok=True)

        symbols = []
        if "symbol" in df.columns:
            symbols = df["symbol"].unique().tolist()
            for sym in symbols:
                sym_df = df[df["symbol"] == sym].sort_values("date")
                out_path = cache_dir / f"{sym}_{file.filename}"
                sym_df.to_csv(out_path, index=False)
                logger.info("CSV ??: %s -> %s (%d rows)", sym, out_path, len(sym_df))
        else:
            out_path = cache_dir / file.filename
            df.sort_values("date").to_csv(out_path, index=False)
            logger.info("CSV ??: %s (%d rows)", out_path, len(df))

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
        logger.error("CSV ????: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"CSV ????: {e}")
