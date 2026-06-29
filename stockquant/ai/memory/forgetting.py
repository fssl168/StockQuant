# -*- coding: utf-8 -*-
"""F020 遗忘机制 — 基于 report_type 的过期策略（日报/月报/年报三级报告体系）

改造自原有 L1/L2/L3 遗忘机制，现基于报告类型执行过期策略：
- 日报：保留 30 天后自动清理
- 月报：保留 1 年后自动清理
- 年报：永久保留

保留旧接口 forget(l2_store, l3_store) 供向后兼容。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

logger = logging.getLogger("stockquant.ai.memory.forgetting")


class ForgettingMechanism:
    """遗忘机制 — 基于 report_type 的过期策略

    报告保留策略:
    - daily: 保留 30 天（超过 30 天的日报可被清理）
    - monthly: 保留 365 天（超过 1 年的月报可被清理）
    - annual: 永久保留（不过期）

    同时保留置信度遗忘：低置信度报告也可被清理。
    """

    # 默认置信度阈值
    DEFAULT_CONFIDENCE_THRESHOLD = 0.3

    # 各类型报告保留天数
    RETENTION_DAYS = {
        "daily": 30,     # 日报保留 30 天
        "monthly": 365,  # 月报保留 1 年
        "annual": None,  # 年报永久保留
    }

    def forget(self, report_store: Any) -> Dict[str, int]:
        """执行报告过期策略

        Args:
            report_store: ReportSystem 实例（需要 report_system.store 可用）

        Returns:
            各类型删除的报告数 {"daily": n, "monthly": n, "annual": 0}
        """
        result: Dict[str, int] = {"daily": 0, "monthly": 0, "annual": 0}

        for report_type, retention_days in self.RETENTION_DAYS.items():
            if retention_days is None:
                # annual: 永不自动清理
                continue

            deleted = self._expire_by_type(report_store, report_type, retention_days)
            result[report_type] = deleted

        total = sum(result.values())
        if total > 0:
            logger.info("报告过期清理: daily=%d, monthly=%d", result["daily"], result["monthly"])

        return result

    def _expire_by_type(self, report_store: Any, report_type: str, retention_days: int) -> int:
        """清理过期报告

        Args:
            report_store: ReportSystem 实例
            report_type: 报告类型（daily/monthly）
            retention_days: 保留天数

        Returns:
            删除的报告数
        """
        if report_store is None or report_store.store is None:
            return 0

        try:
            cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
        except Exception as exc:
            logger.warning("计算过期截止日期失败: %s", exc)
            return 0

        deleted = 0
        try:
            # 获取所有该类型的报告
            if report_type == "daily":
                reports = report_store.list_daily_reports(end=cutoff_date, limit=500)
            elif report_type == "monthly":
                reports = report_store.list_monthly_reports(end=cutoff_date, limit=120)
            else:
                return 0

            for report in reports:
                report_date = report.get("report_date", "")
                if report_date and report_date < cutoff_date:
                    report_id = report.get("id")
                    if report_id:
                        try:
                            if report_store.delete_report(report_id):
                                deleted += 1
                        except Exception:
                            pass
        except Exception as exc:
            logger.warning("清理过期 %s 报告失败: %s", report_type, exc)

        return deleted

    # ── 旧接口（向后兼容） ──

    def forget_old(self, l2_store: Any, l3_store: Any) -> Dict[str, int]:
        """旧接口: L2/L3 遗忘（向后兼容）

        保留旧的签名和逻辑，供可能仍在使用旧接口的调用方使用。
        """
        result: Dict[str, int] = {"l2": 0, "l3": 0}

        # L2 遗忘
        try:
            result["l2"] += l2_store.cleanup_expired()
        except Exception as exc:
            logger.warning("L2 时间遗忘失败: %s", exc)

        # L2 置信度遗忘
        try:
            items = l2_store.get_all()
            for item in items:
                if item.get("confidence", 1.0) < self.DEFAULT_CONFIDENCE_THRESHOLD:
                    if l2_store.delete(item["id"]):
                        result["l2"] += 1
        except Exception as exc:
            logger.warning("L2 置信度遗忘失败: %s", exc)

        # L3 置信度遗忘
        try:
            items = l3_store.get_all(limit=5000)
            threshold = self.DEFAULT_CONFIDENCE_THRESHOLD * 0.5
            for item in items:
                if item.get("confidence", 1.0) < threshold:
                    if l3_store.delete(item["id"]):
                        result["l3"] += 1
        except Exception as exc:
            logger.warning("L3 置信度遗忘失败: %s", exc)

        return result

    # ── 通用方法 ──

    def redundancy_compress(self, items: List[Dict[str, Any]], similarity_threshold: float = 0.9) -> List[Dict[str, Any]]:
        """冗余压缩: 合并相似条目

        基于内容字符重叠率，将相似度超过阈值的条目合并为一条。
        """
        if not items:
            return items

        result: List[Dict[str, Any]] = []
        for item in items:
            is_dup = False
            for existing in result:
                if self._similarity(item.get("content", ""), existing.get("content", "")) > similarity_threshold:
                    # 保留置信度更高的
                    if item.get("confidence", 0) > existing.get("confidence", 0):
                        existing.update(item)
                    is_dup = True
                    break
            if not is_dup:
                result.append(item)
        return result

    def _similarity(self, a: str, b: str) -> float:
        """简单字符重叠率"""
        if not a or not b:
            return 0.0
        set_a = set(a)
        set_b = set(b)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0
