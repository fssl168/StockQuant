# -*- coding: utf-8 -*-
"""F020 记忆压缩器 — 日报/月报/年报聚合升级器

改造自原有 L2→L3 压缩迁移器，现实现"日报→月报→年报"的聚合升级。
- generate_monthly_from_dailies: 聚合当月所有日报生成月报
- generate_annual_from_monthlies: 聚合当年所有月报生成年报

保留旧接口 compress_l2_to_l3 供向后兼容。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.memory.compressor")


class MemoryCompressor:
    """记忆压缩器 — 日报/月报/年报聚合升级器

    将低级别报告聚合升级为高级别报告：
    - 日报 → 月报：聚合当月所有日报，使用 LLM 提取关键信息
    - 月报 → 年报：聚合当年所有月报，使用 LLM 提取年度关键事件

    Args:
        llm_adapter: 可选 LLM 适配器，需支持 `.chat(message, system_prompt=...)` 或 `.chat(messages)` 接口
                     未传入时降级为截断式摘要
    """

    # 日报保留天数，超过此天数的日报可被聚合为月报
    DEFAULT_DAILY_RETENTION_DAYS = 30

    # 每次聚合的最大报告数
    BATCH_SIZE = 50

    def __init__(self, llm_adapter: Any = None) -> None:
        self._llm = llm_adapter

    def compress(self, report_system: Any) -> int:
        """执行聚合升级（供 MemoryManager 调用）

        流程:
        1. 检查是否有可聚合的日报 → 月报
        2. 检查是否有可聚合的月报 → 年报
        3. 返回聚合的报告数

        Args:
            report_system: ReportSystem 实例

        Returns:
            聚合的报告数
        """
        total = 0
        try:
            total += self.generate_monthly_from_dailies(report_system)
        except Exception as exc:
            logger.debug("日报→月报聚合失败: %s", exc)
        try:
            total += self.generate_annual_from_monthlies(report_system)
        except Exception as exc:
            logger.debug("月报→年报聚合失败: %s", exc)
        return total

    # ── 新接口：日报→月报聚合 ──

    def generate_monthly_from_dailies(self, report_system: Any, year_month: Optional[str] = None) -> int:
        """聚合当月所有日报生成月报

        流程:
        1. 获取当月所有日报
        2. 用 LLM 聚合四大板块
        3. 写入月报

        Args:
            report_system: ReportSystem 实例
            year_month: 年月 YYYY-MM，默认当前月

        Returns:
            生成的月报数
        """
        if report_system is None or report_system.store is None:
            return 0

        if year_month is None:
            year_month = datetime.now().strftime("%Y-%m")

        try:
            # 获取当月日报
            month_start = f"{year_month}-01"
            # 计算月末日期
            year, month = year_month.split("-")
            last_day = self._get_month_last_day(int(year), int(month))
            month_end = f"{year_month}-{last_day:02d}"

            dailies = report_system.list_daily_reports(start=month_start, end=month_end, limit=self.BATCH_SIZE)
        except Exception as exc:
            logger.warning("获取日报列表失败: %s", exc)
            return 0

        if not dailies:
            return 0

        # 检查是否已存在该月报
        existing = report_system.get_monthly_report(year_month)
        if existing is not None:
            logger.debug("月报 %s 已存在，跳过聚合", year_month)
            return 0

        # 聚合四大板块
        monthly_report = self._aggregate_reports(dailies, target_type="monthly", period=year_month)

        try:
            report_system.add_report(monthly_report)
            logger.info("日报→月报聚合完成: %s（%d 篇日报）", year_month, len(dailies))
            return 1
        except Exception as exc:
            logger.warning("写入月报失败: %s", exc)
            return 0

    # ── 新接口：月报→年报聚合 ──

    def generate_annual_from_monthlies(self, report_system: Any, year: Optional[str] = None) -> int:
        """聚合当年所有月报生成年报

        流程:
        1. 获取当年所有月报
        2. 用 LLM 聚合四大板块
        3. 写入年报

        Args:
            report_system: ReportSystem 实例
            year: 年份 YYYY，默认当前年

        Returns:
            生成的年报数
        """
        if report_system is None or report_system.store is None:
            return 0

        if year is None:
            year = datetime.now().strftime("%Y")

        try:
            monthlies = report_system.list_monthly_reports(
                start=f"{year}-01", end=f"{year}-12", limit=12
            )
        except Exception as exc:
            logger.warning("获取月报列表失败: %s", exc)
            return 0

        if not monthlies:
            return 0

        # 检查是否已存在该年报
        existing = report_system.get_annual_report(year)
        if existing is not None:
            logger.debug("年报 %s 已存在，跳过聚合", year)
            return 0

        # 聚合四大板块
        annual_report = self._aggregate_reports(monthlies, target_type="annual", period=year)

        try:
            report_system.add_report(annual_report)
            logger.info("月报→年报聚合完成: %s（%d 篇月报）", year, len(monthlies))
            return 1
        except Exception as exc:
            logger.warning("写入年报失败: %s", exc)
            return 0

    # ── 旧接口（向后兼容） ──

    def compress_l2_to_l3(self, l2_store: Any, l3_store: Any) -> int:
        """旧接口: L2→L3 压缩迁移（向后兼容）

        现在降级为空操作。新的聚合由 generate_monthly_from_dailies / generate_annual_from_monthlies 替代。
        """
        logger.info("compress_l2_to_l3 已废弃，请使用 generate_monthly_from_dailies / generate_annual_from_monthlies")
        return 0

    # ── 内部方法 ──

    def _aggregate_reports(
        self,
        reports: List[Dict[str, Any]],
        target_type: str,
        period: str,
    ) -> Dict[str, Any]:
        """将多篇报告聚合为一条高级别报告

        Args:
            reports: 子报告列表
            target_type: 目标类型（monthly 或 annual）
            period: 目标周期（YYYY-MM 或 YYYY）

        Returns:
            聚合后的报告字典
        """
        # 提取四大板块
        market_reviews = [r.get("market_review", "") for r in reports]
        trading_records = [r.get("trading_record", "") for r in reports]
        strategy_performances = [r.get("strategy_performance", "") for r in reports]
        ai_insights = [r.get("ai_insights", "") for r in reports]

        # 用 LLM 聚合
        if self._llm is not None:
            market_summary = self._llm_summarize_section(
                market_reviews, "市场回顾", target_type
            )
            trading_summary = self._llm_summarize_section(
                trading_records, "交易记录", target_type
            )
            strategy_summary = self._llm_summarize_section(
                strategy_performances, "策略表现", target_type
            )
            insights_summary = self._llm_summarize_section(
                ai_insights, "AI 洞察", target_type
            )
        else:
            # 降级：拼接
            market_summary = self._concat_sections(market_reviews)
            trading_summary = self._concat_sections(trading_records)
            strategy_summary = self._concat_sections(strategy_performances)
            insights_summary = self._concat_sections(ai_insights)

        # 计算时间范围
        dates = [r.get("report_date", "") for r in reports if r.get("report_date")]
        period_start = min(dates) if dates else period
        period_end = max(dates) if dates else period

        if target_type == "monthly":
            report_date = f"{period}-{self._get_month_last_day(int(period[:4]), int(period[5:7])):02d}"
        else:  # annual
            report_date = f"{period}-12-31"

        full_content = f"{market_summary}\n{trading_summary}\n{strategy_summary}\n{insights_summary}"
        summary = self._generate_summary(full_content)

        return {
            "report_type": target_type,
            "report_date": report_date,
            "report_period_start": period_start,
            "report_period_end": period_end,
            "market_review": market_summary,
            "trading_record": trading_summary,
            "strategy_performance": strategy_summary,
            "ai_insights": insights_summary,
            "metrics_json": "{}",
            "metadata_json": f'{{"source_count": {len(reports)}, "aggregated_at": "{datetime.now().isoformat()}"}}',
            "full_content": full_content,
            "summary": summary,
            "confidence": 1.0,
            "importance_score": 0.7 if target_type == "monthly" else 0.9,
        }

    def _llm_summarize_section(
        self,
        sections: List[str],
        section_name: str,
        target_type: str,
    ) -> str:
        """用 LLM 聚合报告板块"""
        content = "\n---\n".join(s for s in sections if s)

        period_desc = "月度" if target_type == "monthly" else "年度"

        try:
            system_prompt = (
                f"你是金融领域的{period_desc}报告撰写专家。"
                f"请将以下多条报告的「{section_name}」部分聚合为一段连贯的{period_desc}{section_name}，"
                "保留核心数据、关键事件和趋势判断，去除重复信息。"
                "直接输出聚合后的文本，不要解释。"
            )
            user_prompt = f"请聚合以下{len(sections)}篇报告的{section_name}部分（共{len(content)}字）：\n\n{content[:4000]}"

            try:
                summary = self._llm.chat(user_prompt, system_prompt=system_prompt)
            except TypeError:
                summary = self._llm.chat([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ])

            if isinstance(summary, str) and summary.strip():
                return summary.strip().strip('"').strip("'")
        except Exception as exc:
            logger.debug("LLM 板块聚合失败，降级拼接: %s", exc)

        return self._concat_sections(sections)

    @staticmethod
    def _concat_sections(sections: List[str]) -> str:
        """降级拼接"""
        parts = [s for s in sections if s]
        if not parts:
            return ""
        return "\n".join(parts)[:2000]

    def _generate_summary(self, content: str) -> str:
        """生成摘要"""
        if len(content) <= 200:
            return content

        if self._llm is not None:
            try:
                system_prompt = (
                    "你是金融摘要专家。请将给定的报告内容压缩为不超过200字的摘要，"
                    "保留核心事实，直接输出。"
                )
                user_prompt = f"请压缩以下内容（{len(content)} 字）为不超过200字的摘要：\n\n{content[:4000]}"

                try:
                    summary = self._llm.chat(user_prompt, system_prompt=system_prompt)
                except TypeError:
                    summary = self._llm.chat([
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ])

                if isinstance(summary, str) and summary.strip() and len(summary) <= 500:
                    return summary.strip().strip('"').strip("'")
            except Exception as exc:
                logger.debug("LLM 摘要失败，降级截断: %s", exc)

        return content[:200] + "..."

    @staticmethod
    def _get_month_last_day(year: int, month: int) -> int:
        """获取某月的最后一天"""
        import calendar
        return calendar.monthrange(year, month)[1]
