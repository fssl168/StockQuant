# -*- coding: utf-8 -*-
"""F020 Phase F3 — 采集器审计日志

设计原则：
- 单例 CollectorAuditLog，全局共享一份日志
- 内存环形缓冲（默认 1000 条），溢出后丢弃最旧条目
- 可选 DB 持久化（hook 注入，避免硬依赖）
- 线程安全（threading.Lock）
- 支持按 collector / action / source / 时间范围 查询
- 支持导出与统计

使用方式::

    from stockquant.ai.collectors.audit_log import get_audit_log

    log = get_audit_log()
    await log.append("news_collector", "collect", "eastmoney", "success", count=15)

    # 查询最近 10 条
    entries = log.query(limit=10)

    # 按采集器查询
    news_logs = log.query_by_collector("news_collector")

集成到 BaseCollector::

    class BaseCollector:
        async def _audit_log(self, action, source, result, count=0, error=None):
            log = get_audit_log()
            await log.append(self.name, action, source, result, count, error)
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.collectors.audit_log")


# ── 数据结构 ──────────────────────────────────────────────────────────────


@dataclass
class AuditEntry:
    """审计日志条目

    Attributes:
        collector: 采集器名（如 news / research / financial）
        action: 操作类型（如 collect / verify / writeback）
        source: 数据源（如 eastmoney / sina / sse）
        result: 结果（success / failure / partial / skipped）
        count: 处理条目数
        error: 错误信息（result=failure 时填写）
        timestamp: ISO 字符串时间戳
        duration_ms: 耗时毫秒
        metadata: 附加元数据
    """
    collector: str = ""
    action: str = ""
    source: str = ""
    result: str = ""
    count: int = 0
    error: Optional[str] = None
    timestamp: str = ""
    duration_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── 主审计日志 ──────────────────────────────────────────────────────────


# 持久化回调签名：persist_fn(entries: List[AuditEntry]) -> None
PersistFn = Callable[[List["AuditEntry"]], None]


class CollectorAuditLog:
    """采集器审计日志

    内存环形缓冲 + 可选持久化回调。

    用法::

        log = CollectorAuditLog(max_size=500)
        log.append_sync("news", "collect", "eastmoney", "success", count=10)
        entries = log.query(limit=20)
    """

    # 支持的 result 取值
    VALID_RESULTS = {"success", "failure", "partial", "skipped"}

    def __init__(self, max_size: int = 1000) -> None:
        if max_size < 1:
            raise ValueError(f"max_size 必须 ≥1，收到 {max_size}")
        self._max_size = max_size
        self._entries: List[AuditEntry] = []
        self._lock = threading.Lock()
        self._persist_fn: Optional[PersistFn] = None
        self._stats: Dict[str, int] = {
            "total": 0,
            "success": 0,
            "failure": 0,
            "partial": 0,
            "skipped": 0,
        }

    # ── 配置 ────────────────────────────────────────────────────────────

    def set_persist_fn(self, fn: Optional[PersistFn]) -> None:
        """设置持久化回调（每次 append 后调用）

        Args:
            fn: 回调函数，接受 AuditEntry 列表；None 表示禁用持久化
        """
        self._persist_fn = fn

    @property
    def max_size(self) -> int:
        return self._max_size

    @property
    def size(self) -> int:
        """当前内存中条目数"""
        with self._lock:
            return len(self._entries)

    # ── 写入 ────────────────────────────────────────────────────────────

    def append_sync(
        self,
        collector: str,
        action: str,
        source: str,
        result: str = "success",
        count: int = 0,
        error: Optional[str] = None,
        duration_ms: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """同步追加审计条目（线程安全）

        Args:
            collector: 采集器名
            action: 操作类型
            source: 数据源
            result: 结果（success|failure|partial|skipped）
            count: 处理条目数
            error: 错误信息
            duration_ms: 耗时毫秒
            metadata: 附加元数据

        Returns:
            创建的 AuditEntry
        """
        if result not in self.VALID_RESULTS:
            logger.warning("未知 result=%s，已规范化为 failure", result)
            result = "failure"

        entry = AuditEntry(
            collector=collector,
            action=action,
            source=source,
            result=result,
            count=count,
            error=error,
            timestamp=datetime.now().isoformat(),
            duration_ms=duration_ms,
            metadata=dict(metadata) if metadata else {},
        )

        with self._lock:
            self._entries.append(entry)
            # 环形缓冲：超限时丢弃最旧的
            while len(self._entries) > self._max_size:
                self._entries.pop(0)
            # 更新统计
            self._stats["total"] += 1
            if result in self._stats:
                self._stats[result] += 1

        # 持久化回调（在锁外执行，避免阻塞）
        if self._persist_fn is not None:
            try:
                self._persist_fn([entry])
            except Exception as exc:
                logger.error("持久化审计日志失败: %s", exc)

        logger.debug(
            "审计条目: %s/%s/%s result=%s count=%d",
            collector, action, source, result, count,
        )
        return entry

    async def append(
        self,
        collector: str,
        action: str,
        source: str,
        result: str = "success",
        count: int = 0,
        error: Optional[str] = None,
        duration_ms: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """异步追加审计条目（与同步版本相同）

        提供 async 接口以便 BaseCollector._audit_log 直接 await。
        """
        return self.append_sync(
            collector=collector,
            action=action,
            source=source,
            result=result,
            count=count,
            error=error,
            duration_ms=duration_ms,
            metadata=metadata,
        )

    # ── 查询 ────────────────────────────────────────────────────────────

    def query(
        self,
        limit: int = 100,
        offset: int = 0,
        collector: Optional[str] = None,
        action: Optional[str] = None,
        source: Optional[str] = None,
        result: Optional[str] = None,
    ) -> List[AuditEntry]:
        """查询审计条目（按时间倒序）

        Args:
            limit: 最多返回条目数
            offset: 跳过前 N 条
            collector: 仅返回该采集器的条目（None=不限）
            action: 仅返回该操作的条目
            source: 仅返回该数据源的条目
            result: 仅返回该结果的条目

        Returns:
            AuditEntry 列表（最新在前）
        """
        with self._lock:
            entries = list(self._entries)

        # 过滤
        if collector:
            entries = [e for e in entries if e.collector == collector]
        if action:
            entries = [e for e in entries if e.action == action]
        if source:
            entries = [e for e in entries if e.source == source]
        if result:
            entries = [e for e in entries if e.result == result]

        # 倒序（最新在前）
        entries.reverse()

        # 分页
        return entries[offset:offset + limit]

    def query_by_collector(self, collector: str, limit: int = 100) -> List[AuditEntry]:
        """按采集器查询"""
        return self.query(limit=limit, collector=collector)

    def query_by_source(self, source: str, limit: int = 100) -> List[AuditEntry]:
        """按数据源查询"""
        return self.query(limit=limit, source=source)

    def query_failures(self, limit: int = 100) -> List[AuditEntry]:
        """查询所有失败条目"""
        return self.query(limit=limit, result="failure")

    def latest(self, n: int = 1) -> List[AuditEntry]:
        """获取最新 N 条"""
        return self.query(limit=n)

    # ── 统计 ────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, int]:
        """返回统计信息"""
        with self._lock:
            return dict(self._stats)

    def count_by_collector(self) -> Dict[str, int]:
        """按采集器统计条目数"""
        with self._lock:
            counts: Dict[str, int] = {}
            for e in self._entries:
                counts[e.collector] = counts.get(e.collector, 0) + 1
            return counts

    def count_by_source(self) -> Dict[str, int]:
        """按数据源统计条目数"""
        with self._lock:
            counts: Dict[str, int] = {}
            for e in self._entries:
                counts[e.source] = counts.get(e.source, 0) + 1
            return counts

    def success_rate(self) -> float:
        """成功率（0.0~1.0）"""
        with self._lock:
            total = self._stats["total"]
            if total == 0:
                return 0.0
            return self._stats["success"] / total

    # ── 管理 ────────────────────────────────────────────────────────────

    def clear(self) -> int:
        """清空所有条目，返回清除的数量"""
        with self._lock:
            n = len(self._entries)
            self._entries.clear()
            # 不清 stats，保留累计统计
            return n

    def to_dict_list(self, limit: int = 100) -> List[Dict[str, Any]]:
        """导出为字典列表"""
        return [e.to_dict() for e in self.query(limit=limit)]

    def summary(self) -> Dict[str, Any]:
        """返回审计日志摘要"""
        with self._lock:
            return {
                "size": len(self._entries),
                "max_size": self._max_size,
                "stats": dict(self._stats),
                "success_rate": (
                    self._stats["success"] / self._stats["total"]
                    if self._stats["total"] > 0 else 0.0
                ),
                "collectors": list(set(e.collector for e in self._entries)),
                "sources": list(set(e.source for e in self._entries)),
            }


# ── 单例 ─────────────────────────────────────────────────────────────────


_audit_log_instance: Optional[CollectorAuditLog] = None
_instance_lock = threading.Lock()


def get_audit_log() -> CollectorAuditLog:
    """获取全局审计日志单例"""
    global _audit_log_instance
    if _audit_log_instance is None:
        with _instance_lock:
            if _audit_log_instance is None:
                _audit_log_instance = CollectorAuditLog()
    return _audit_log_instance


def reset_audit_log(max_size: int = 1000) -> CollectorAuditLog:
    """重置单例（测试用），返回新实例"""
    global _audit_log_instance
    with _instance_lock:
        _audit_log_instance = CollectorAuditLog(max_size=max_size)
    return _audit_log_instance
