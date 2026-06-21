# -*- coding: utf-8 -*-
"""F020 记忆系统 API — /api/memory"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query

from stockquant.api.deps import get_current_user, get_admin_user
from stockquant.api.schemas import UserToken
from stockquant.ai.memory.system import MemorySystem

router = APIRouter(tags=["记忆系统"])
logger = logging.getLogger("stockquant.api.memory")

# 模块级单例
_memory: Optional[MemorySystem] = None


def init_memory(system: MemorySystem) -> None:
    """由 main.py 在启动时注入"""
    global _memory
    _memory = system


@router.get("/memory/l1", response_model=List[Dict[str, Any]], summary="获取 L1 工作记忆")
async def get_l1(
    _user: UserToken = Depends(get_current_user),
    n: int = Query(20, ge=1, le=200, description="返回条数"),
    symbol: Optional[str] = Query(None, description="按标的过滤"),
):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    recent = _memory.get_recent(n)
    if symbol:
        recent = [r for r in recent if r.get("symbol") == symbol]
    return recent


@router.post("/memory/l1", summary="添加 L1 工作记忆")
async def add_l1(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    _memory.add_working(payload)
    return {"success": True}


@router.delete("/memory/l1", summary="清空 L1 工作记忆")
async def clear_l1(
    _user: UserToken = Depends(get_admin_user),
):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    _memory.l1.clear()
    return {"success": True, "cleared": True}


@router.get("/memory/l2", response_model=List[Dict[str, Any]], summary="获取 L2 短期记忆")
async def get_l2(
    _user: UserToken = Depends(get_current_user),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    symbol: Optional[str] = Query(None, description="按标的过滤"),
    limit: int = Query(20, ge=1, le=200, description="返回条数"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    results = _memory.search_short_term(symbol=symbol, keyword=keyword, limit=limit + offset)
    return results[offset:offset + limit]


@router.post("/memory/l2", summary="写入 L2 短期记忆")
async def add_l2(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    symbol = payload.get("symbol", "unknown")
    content = payload.get("content", "")
    metadata = payload.get("metadata", {})
    if not content:
        raise HTTPException(status_code=400, detail="content 不能为空")
    entry_id = _memory.add_short_term(symbol=symbol, content=content, metadata=metadata)
    return {"success": True, "id": entry_id}


@router.post("/memory/l2/search", response_model=List[Dict[str, Any]], summary="搜索 L2 短期记忆")
async def search_l2(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_current_user),
):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    keyword = payload.get("keyword", "")
    symbol = payload.get("symbol")
    limit = payload.get("limit", 20)
    results = _memory.search_short_term(symbol=symbol, keyword=keyword, limit=limit)
    return results


@router.delete("/memory/l2", summary="清空 L2 短期记忆")
async def clear_l2(
    _user: UserToken = Depends(get_admin_user),
):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    _memory.l2.clear_all()
    return {"success": True, "cleared": True}


@router.get("/memory/l3", response_model=List[Dict[str, Any]], summary="获取 L3 长期记忆")
async def get_l3(
    _user: UserToken = Depends(get_current_user),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    symbol: Optional[str] = Query(None, description="按标的过滤"),
    min_confidence: float = Query(0.0, ge=0, le=1, description="最低置信度"),
    limit: int = Query(20, ge=1, le=200, description="返回条数"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    results = _memory.search_long_term(
        symbol=symbol, keyword=keyword, min_confidence=min_confidence, limit=limit + offset
    )
    return results[offset:offset + limit]


@router.post("/memory/l3", summary="写入 L3 长期记忆")
async def add_l3(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    insight = payload.get("insight", "")
    if not insight:
        raise HTTPException(status_code=400, detail="insight 不能为空")
    entry_id = _memory.add_long_term(payload)
    return {"success": True, "id": entry_id}


@router.post("/memory/l3/search", response_model=List[Dict[str, Any]], summary="搜索 L3 长期记忆")
async def search_l3(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_current_user),
):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    keyword = payload.get("keyword", "")
    symbol = payload.get("symbol")
    min_confidence = payload.get("min_confidence", 0.0)
    limit = payload.get("limit", 20)
    results = _memory.search_long_term(
        symbol=symbol, keyword=keyword, min_confidence=min_confidence, limit=limit
    )
    return results


@router.delete("/memory/l3", summary="清空 L3 长期记忆")
async def clear_l3(
    _user: UserToken = Depends(get_admin_user),
):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    _memory.l3.clear_all()
    return {"success": True, "cleared": True}


@router.post("/memory/compress", summary="触发 L2→L3 记忆压缩")
async def compress_l2_to_l3(
    _user: UserToken = Depends(get_admin_user),
):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    try:
        from stockquant.ai.memory.compressor import MemoryCompressor
        compressed = MemoryCompressor.compress_l2_to_l3(
            memory_system=_memory,
        )
        return {"success": True, "compressed": compressed}
    except Exception as e:
        logger.error("记忆压缩失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/cleanup", summary="清理过期记忆")
async def cleanup_expired(
    _user: UserToken = Depends(get_admin_user),
):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    try:
        from stockquant.ai.memory.forgetting import ForgettingMechanism
        removed = ForgettingMechanism.cleanup_expired(_memory)
        return {"success": True, "removed": removed}
    except Exception as e:
        logger.error("清理失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
