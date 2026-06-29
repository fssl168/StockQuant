# -*- coding: utf-8 -*-
"""F020 报告系统 API — /api/reports（日报/月报/年报）

同时保留旧的 /api/memory/* 路由作为兼容层，内部映射到新的报告系统接口。
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query

from stockquant.api.deps import get_current_user, get_admin_user
from stockquant.api.schemas import UserToken

router = APIRouter(tags=["报告系统"])
logger = logging.getLogger("stockquant.api.memory")

# 模块级单例
_reports: Optional[Any] = None


# ── 初始化注入 ──────────────────────────────────────────────

def init_reports(system) -> None:
    """由 main.py 在启动时注入 ReportSystem 实例"""
    global _reports
    _reports = system


def init_memory(system) -> None:
    """兼容旧接口（main.py 仍使用此名称）"""
    init_reports(system)


def _ensure_initialized() -> Any:
    """检查系统是否已初始化，未初始化则抛出 503"""
    if _reports is None:
        raise HTTPException(status_code=503, detail="报告系统未初始化")
    return _reports


# ========================================================================
# 新路由：/reports/* — 日报 / 月报 / 年报
# ========================================================================

# ── 日报 ────────────────────────────────────────────────────

@router.get("/reports/daily", response_model=List[Dict[str, Any]], summary="获取日报列表")
async def list_daily_reports(
    _user: UserToken = Depends(get_current_user),
    start: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="截止日期 YYYY-MM-DD"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    sys = _ensure_initialized()
    try:
        results = sys.list_daily_reports(start=start, end=end)
        return results[offset:offset + limit]
    except AttributeError:
        # ReportSystem 尚未实现此方法，降级返回空列表
        logger.warning("list_daily_reports 方法未实现")
        return []
    except Exception as e:
        logger.error("获取日报列表失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/daily/{date}", response_model=Dict[str, Any], summary="获取指定日报")
async def get_daily_report(
    date: str,
    _user: UserToken = Depends(get_current_user),
):
    sys = _ensure_initialized()
    try:
        report = sys.get_daily_report(date=date)
        if report is None:
            raise HTTPException(status_code=404, detail=f"日报 {date} 不存在")
        return report
    except HTTPException:
        raise
    except AttributeError:
        logger.warning("get_daily_report 方法未实现")
        raise HTTPException(status_code=404, detail=f"日报 {date} 不存在")
    except Exception as e:
        logger.error("获取日报失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/daily/generate", summary="AI 生成日报")
async def generate_daily_report(
    _user: UserToken = Depends(get_admin_user),
):
    sys = _ensure_initialized()
    try:
        report = sys.generate_daily_report()
        return {"success": True, "report": report}
    except AttributeError:
        logger.warning("generate_daily_report 方法未实现")
        raise HTTPException(status_code=501, detail="日报生成功能尚未实现")
    except Exception as e:
        logger.error("生成日报失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── 月报 ────────────────────────────────────────────────────

@router.get("/reports/monthly", response_model=List[Dict[str, Any]], summary="获取月报列表")
async def list_monthly_reports(
    _user: UserToken = Depends(get_current_user),
    start: Optional[str] = Query(None, description="起始月份 YYYY-MM"),
    end: Optional[str] = Query(None, description="截止月份 YYYY-MM"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    sys = _ensure_initialized()
    try:
        results = sys.list_monthly_reports(start=start, end=end)
        return results[offset:offset + limit]
    except AttributeError:
        logger.warning("list_monthly_reports 方法未实现")
        return []
    except Exception as e:
        logger.error("获取月报列表失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/monthly/{year_month}", response_model=Dict[str, Any], summary="获取指定月报")
async def get_monthly_report(
    year_month: str,
    _user: UserToken = Depends(get_current_user),
):
    sys = _ensure_initialized()
    try:
        report = sys.get_monthly_report(year_month=year_month)
        if report is None:
            raise HTTPException(status_code=404, detail=f"月报 {year_month} 不存在")
        return report
    except HTTPException:
        raise
    except AttributeError:
        logger.warning("get_monthly_report 方法未实现")
        raise HTTPException(status_code=404, detail=f"月报 {year_month} 不存在")
    except Exception as e:
        logger.error("获取月报失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/monthly/generate", summary="AI 生成月报")
async def generate_monthly_report(
    _user: UserToken = Depends(get_admin_user),
):
    sys = _ensure_initialized()
    try:
        report = sys.generate_monthly_report()
        return {"success": True, "report": report}
    except AttributeError:
        logger.warning("generate_monthly_report 方法未实现")
        raise HTTPException(status_code=501, detail="月报生成功能尚未实现")
    except Exception as e:
        logger.error("生成月报失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── 年报 ────────────────────────────────────────────────────

@router.get("/reports/annual", response_model=List[Dict[str, Any]], summary="获取年报列表")
async def list_annual_reports(
    _user: UserToken = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    sys = _ensure_initialized()
    try:
        results = sys.list_annual_reports()
        return results[offset:offset + limit]
    except AttributeError:
        logger.warning("list_annual_reports 方法未实现")
        return []
    except Exception as e:
        logger.error("获取年报列表失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/annual/{year}", response_model=Dict[str, Any], summary="获取指定年报")
async def get_annual_report(
    year: str,
    _user: UserToken = Depends(get_current_user),
):
    sys = _ensure_initialized()
    try:
        report = sys.get_annual_report(year=year)
        if report is None:
            raise HTTPException(status_code=404, detail=f"年报 {year} 不存在")
        return report
    except HTTPException:
        raise
    except AttributeError:
        logger.warning("get_annual_report 方法未实现")
        raise HTTPException(status_code=404, detail=f"年报 {year} 不存在")
    except Exception as e:
        logger.error("获取年报失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/annual/generate", summary="AI 生成年报")
async def generate_annual_report(
    _user: UserToken = Depends(get_admin_user),
):
    sys = _ensure_initialized()
    try:
        report = sys.generate_annual_report()
        return {"success": True, "report": report}
    except AttributeError:
        logger.warning("generate_annual_report 方法未实现")
        raise HTTPException(status_code=501, detail="年报生成功能尚未实现")
    except Exception as e:
        logger.error("生成年报失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── 统一检索 ────────────────────────────────────────────────

@router.post("/reports/search", summary="检索报告")
async def search_reports(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_current_user),
):
    sys = _ensure_initialized()
    try:
        keyword = payload.get("keyword", "")
        report_type = payload.get("type", "")  # daily / monthly / annual / ""
        start = payload.get("start")
        end = payload.get("end")
        limit = payload.get("limit", 20)
        results = sys.search_reports(
            keyword=keyword,
            report_type=report_type,
            start=start,
            end=end,
            limit=limit,
        )
        return results
    except AttributeError:
        logger.warning("search_reports 方法未实现，降级为空搜索")
        return []
    except Exception as e:
        logger.error("检索报告失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── CRUD ────────────────────────────────────────────────────

@router.post("/reports", summary="写入报告")
async def add_report(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
):
    sys = _ensure_initialized()
    try:
        report_type = payload.get("type", "daily")
        content = payload.get("content", "")
        if not content:
            raise HTTPException(status_code=400, detail="content 不能为空")
        entry_id = sys.add_report(payload)
        return {"success": True, "id": entry_id}
    except AttributeError:
        logger.warning("add_report 方法未实现")
        raise HTTPException(status_code=501, detail="写入报告功能尚未实现")
    except Exception as e:
        logger.error("写入报告失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/reports/{report_id}", summary="删除报告")
async def delete_report(
    report_id: str,
    _user: UserToken = Depends(get_admin_user),
):
    sys = _ensure_initialized()
    try:
        sys.delete_report(report_id)
        return {"success": True, "id": report_id}
    except AttributeError:
        logger.warning("delete_report 方法未实现")
        raise HTTPException(status_code=501, detail="删除报告功能尚未实现")
    except Exception as e:
        logger.error("删除报告失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ========================================================================
# 旧路由兼容层：/memory/* — 内部映射到新报告系统
# ========================================================================

@router.get("/memory/l1", response_model=List[Dict[str, Any]], summary="[兼容] 获取 L1 工作记忆 → 日报")
async def get_l1(
    _user: UserToken = Depends(get_current_user),
    n: int = Query(20, ge=1, le=200, description="返回条数"),
    symbol: Optional[str] = Query(None, description="按标的过滤"),
):
    """旧接口兼容：L1 工作记忆 → 日报"""
    sys = _ensure_initialized()
    try:
        # 优先使用新方法
        if hasattr(sys, "list_daily_reports"):
            results = sys.list_daily_reports()
            if symbol:
                results = [r for r in results if r.get("symbol") == symbol]
            return results[:n]
        # 降级：旧 MemorySystem.get_recent
        recent = sys.get_recent(n)
        if symbol:
            recent = [r for r in recent if r.get("symbol") == symbol]
        return recent
    except Exception as e:
        logger.error("[兼容] 获取 L1 失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/l1", summary="[兼容] 添加 L1 工作记忆 → 写入日报")
async def add_l1(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
):
    """旧接口兼容：L1 添加 → 写入日报"""
    sys = _ensure_initialized()
    try:
        if hasattr(sys, "add_report"):
            payload.setdefault("type", "daily")
            entry_id = sys.add_report(payload)
            return {"success": True, "id": entry_id}
        # 降级：旧 MemorySystem.add_working
        sys.add_working(payload)
        return {"success": True}
    except Exception as e:
        logger.error("[兼容] 添加 L1 失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memory/l1", summary="[兼容] 清空 L1 工作记忆 → 清理日报")
async def clear_l1(
    _user: UserToken = Depends(get_admin_user),
):
    """旧接口兼容：L1 清空 → 清理日报"""
    sys = _ensure_initialized()
    try:
        if hasattr(sys, "cleanup_daily_reports"):
            sys.cleanup_daily_reports()
            return {"success": True, "cleared": True}
        # 降级：旧 MemorySystem.l1.clear()
        sys.l1.clear()
        return {"success": True, "cleared": True}
    except Exception as e:
        logger.error("[兼容] 清空 L1 失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/l2", response_model=List[Dict[str, Any]], summary="[兼容] 获取 L2 短期记忆 → 月报")
async def get_l2(
    _user: UserToken = Depends(get_current_user),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    symbol: Optional[str] = Query(None, description="按标的过滤"),
    limit: int = Query(20, ge=1, le=200, description="返回条数"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """旧接口兼容：L2 短期记忆 → 月报"""
    sys = _ensure_initialized()
    try:
        if hasattr(sys, "search_reports"):
            results = sys.search_reports(
                keyword=keyword, report_type="monthly", limit=limit + offset
            )
            if symbol:
                results = [r for r in results if r.get("symbol") == symbol]
            return results[offset:offset + limit]
        # 降级：旧 MemorySystem.search_short_term
        results = sys.search_short_term(symbol=symbol, keyword=keyword, limit=limit + offset)
        return results[offset:offset + limit]
    except Exception as e:
        logger.error("[兼容] 获取 L2 失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/l2", summary="[兼容] 写入 L2 短期记忆 → 写入月报")
async def add_l2(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
):
    """旧接口兼容：L2 写入 → 写入月报"""
    sys = _ensure_initialized()
    try:
        if hasattr(sys, "add_report"):
            payload.setdefault("type", "monthly")
            entry_id = sys.add_report(payload)
            return {"success": True, "id": entry_id}
        # 降级：旧 MemorySystem.add_short_term
        symbol = payload.get("symbol", "unknown")
        content = payload.get("content", "")
        metadata = payload.get("metadata", {})
        if not content:
            raise HTTPException(status_code=400, detail="content 不能为空")
        entry_id = sys.add_short_term(symbol=symbol, content=content, metadata=metadata)
        return {"success": True, "id": entry_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[兼容] 添加 L2 失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/l2/search", response_model=List[Dict[str, Any]], summary="[兼容] 搜索 L2 短期记忆 → 搜索月报")
async def search_l2(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_current_user),
):
    """旧接口兼容：L2 搜索 → 搜索月报"""
    sys = _ensure_initialized()
    try:
        keyword = payload.get("keyword", "")
        symbol = payload.get("symbol")
        limit = payload.get("limit", 20)
        if hasattr(sys, "search_reports"):
            results = sys.search_reports(
                keyword=keyword, report_type="monthly", limit=limit
            )
            if symbol:
                results = [r for r in results if r.get("symbol") == symbol]
            return results
        # 降级：旧 MemorySystem.search_short_term
        results = sys.search_short_term(symbol=symbol, keyword=keyword, limit=limit)
        return results
    except Exception as e:
        logger.error("[兼容] 搜索 L2 失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memory/l2", summary="[兼容] 清空 L2 短期记忆 → 清理月报")
async def clear_l2(
    _user: UserToken = Depends(get_admin_user),
):
    """旧接口兼容：L2 清空 → 清理月报"""
    sys = _ensure_initialized()
    try:
        if hasattr(sys, "cleanup_monthly_reports"):
            sys.cleanup_monthly_reports()
            return {"success": True, "cleared": True}
        # 降级：旧 MemorySystem.l2.clear_all()
        sys.l2.clear_all()
        return {"success": True, "cleared": True}
    except Exception as e:
        logger.error("[兼容] 清空 L2 失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/l3", response_model=List[Dict[str, Any]], summary="[兼容] 获取 L3 长期记忆 → 年报")
async def get_l3(
    _user: UserToken = Depends(get_current_user),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    symbol: Optional[str] = Query(None, description="按标的过滤"),
    min_confidence: float = Query(0.0, ge=0, le=1, description="最低置信度"),
    limit: int = Query(20, ge=1, le=200, description="返回条数"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """旧接口兼容：L3 长期记忆 → 年报"""
    sys = _ensure_initialized()
    try:
        if hasattr(sys, "search_reports"):
            results = sys.search_reports(
                keyword=keyword, report_type="annual", limit=limit + offset
            )
            if symbol:
                results = [r for r in results if r.get("symbol") == symbol]
            if min_confidence > 0:
                results = [r for r in results if r.get("confidence", 0) >= min_confidence]
            return results[offset:offset + limit]
        # 降级：旧 MemorySystem.search_long_term
        results = sys.search_long_term(
            symbol=symbol, keyword=keyword, min_confidence=min_confidence, limit=limit + offset
        )
        return results[offset:offset + limit]
    except Exception as e:
        logger.error("[兼容] 获取 L3 失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/l3", summary="[兼容] 写入 L3 长期记忆 → 写入年报")
async def add_l3(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_admin_user),
):
    """旧接口兼容：L3 写入 → 写入年报"""
    sys = _ensure_initialized()
    try:
        if hasattr(sys, "add_report"):
            payload.setdefault("type", "annual")
            entry_id = sys.add_report(payload)
            return {"success": True, "id": entry_id}
        # 降级：旧 MemorySystem.add_long_term
        insight = payload.get("insight", "")
        if not insight:
            raise HTTPException(status_code=400, detail="insight 不能为空")
        entry_id = sys.add_long_term(payload)
        return {"success": True, "id": entry_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[兼容] 添加 L3 失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/l3/search", response_model=List[Dict[str, Any]], summary="[兼容] 搜索 L3 长期记忆 → 搜索年报")
async def search_l3(
    payload: Dict[str, Any],
    _user: UserToken = Depends(get_current_user),
):
    """旧接口兼容：L3 搜索 → 搜索年报"""
    sys = _ensure_initialized()
    try:
        keyword = payload.get("keyword", "")
        symbol = payload.get("symbol")
        min_confidence = payload.get("min_confidence", 0.0)
        limit = payload.get("limit", 20)
        if hasattr(sys, "search_reports"):
            results = sys.search_reports(
                keyword=keyword, report_type="annual", limit=limit
            )
            if symbol:
                results = [r for r in results if r.get("symbol") == symbol]
            if min_confidence > 0:
                results = [r for r in results if r.get("confidence", 0) >= min_confidence]
            return results
        # 降级：旧 MemorySystem.search_long_term
        results = sys.search_long_term(
            symbol=symbol, keyword=keyword, min_confidence=min_confidence, limit=limit
        )
        return results
    except Exception as e:
        logger.error("[兼容] 搜索 L3 失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memory/l3", summary="[兼容] 清空 L3 长期记忆 → 清理年报")
async def clear_l3(
    _user: UserToken = Depends(get_admin_user),
):
    """旧接口兼容：L3 清空 → 清理年报"""
    sys = _ensure_initialized()
    try:
        if hasattr(sys, "cleanup_annual_reports"):
            sys.cleanup_annual_reports()
            return {"success": True, "cleared": True}
        # 降级：旧 MemorySystem.l3.clear_all()
        sys.l3.clear_all()
        return {"success": True, "cleared": True}
    except Exception as e:
        logger.error("[兼容] 清空 L3 失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/compress", summary="[兼容] L2→L3 压缩 → 月报/年报生成")
async def compress_l2_to_l3(
    _user: UserToken = Depends(get_admin_user),
):
    """旧接口兼容：记忆压缩 → 月报/年报生成"""
    sys = _ensure_initialized()
    try:
        if hasattr(sys, "generate_monthly_report"):
            monthly = sys.generate_monthly_report()
            annual = None
            if hasattr(sys, "generate_annual_report"):
                try:
                    annual = sys.generate_annual_report()
                except Exception as e:
                    logger.warning("年报生成跳过: %s", e)
            return {
                "success": True,
                "monthly_report": monthly,
                "annual_report": annual,
            }
        # 降级：旧 MemoryCompressor
        from stockquant.ai.memory.compressor import MemoryCompressor
        compressed = MemoryCompressor.compress_l2_to_l3(memory_system=sys)
        return {"success": True, "compressed": compressed}
    except Exception as e:
        logger.error("[兼容] 记忆压缩失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/cleanup", summary="[兼容] 清理过期记忆 → 日报清理")
async def cleanup_expired(
    _user: UserToken = Depends(get_admin_user),
):
    """旧接口兼容：清理过期记忆 → 日报清理"""
    sys = _ensure_initialized()
    try:
        if hasattr(sys, "cleanup_daily_reports"):
            removed = sys.cleanup_daily_reports()
            return {"success": True, "removed": removed}
        # 降级：旧 ForgettingMechanism
        from stockquant.ai.memory.forgetting import ForgettingMechanism
        removed = ForgettingMechanism.cleanup_expired(sys)
        return {"success": True, "removed": removed}
    except Exception as e:
        logger.error("[兼容] 清理失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
