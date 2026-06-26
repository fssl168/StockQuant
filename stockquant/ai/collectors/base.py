# -*- coding: utf-8 -*-
"""采集器基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .audit_log import get_audit_log


@dataclass
class RawInfoItem:
    """原始信息条目"""
    url: str = ""
    source: str = ""
    title: str = ""
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    sentiment_score: float = 0.0
    verified: bool = False
    symbol: str = ""


class BaseCollector(ABC):
    """采集器抽象基类

    F020 Phase F3：内置 _audit_log 方法，自动记录采集操作到审计日志。
    子类在 collect() 中调用 await self._audit_log(...) 即可。
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def collect(self, symbol: str = "", limit: int = 20) -> List[RawInfoItem]:
        """采集信息，返回原始条目列表"""
        ...

    def _create_item(self, url: str, source: str, title: str, content: str,
                     symbol: str = "", sentiment: float = 0.0) -> RawInfoItem:
        return RawInfoItem(
            url=url, source=source, title=title, content=content,
            symbol=symbol, sentiment_score=sentiment,
        )

    # ── F020 Phase F3: 审计日志 ────────────────────────────────────────

    async def _audit_log(
        self,
        action: str,
        source: str,
        result: str = "success",
        count: int = 0,
        error: Optional[str] = None,
        duration_ms: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录采集操作到审计日志

        子类在 collect() / verify() / writeback() 等关键操作后调用本方法。

        Args:
            action: 操作类型（如 collect / verify / writeback）
            source: 数据源（如 eastmoney / sina / sse）
            result: 结果（success | failure | partial | skipped）
            count: 处理条目数
            error: 错误信息（result=failure 时填写）
            duration_ms: 耗时毫秒
            metadata: 附加元数据（如 symbol / retry_count 等）
        """
        log = get_audit_log()
        await log.append(
            collector=self.name,
            action=action,
            source=source,
            result=result,
            count=count,
            error=error,
            duration_ms=duration_ms,
            metadata=metadata,
        )
