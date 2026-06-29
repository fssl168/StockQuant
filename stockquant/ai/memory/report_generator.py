# -*- coding: utf-8 -*-
"""F020 报告生成器 -- AI 自动生成日报/月报/年报

使用 LLM 从系统数据（持仓、交易记录、策略表现等）自动生成结构化报告。
"""
from __future__ import annotations

import json
import logging
import re
from calendar import monthrange
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger("stockquant.ai.memory.report_generator")


# ─── LLM Prompt 模板 ────────────────────────────────────────────────


_DAILY_REPORT_PROMPT = """\
你是一位资深的 A 股量化交易分析师。请根据以下数据生成今日交易日报。

## 今日市场数据
{market_data}

## 今日交易记录
{trading_data}

## 今日策略表现
{strategy_data}

## AI 分析洞察
{ai_insights}

请按以下格式输出（JSON）：
{{
  "market_review": "市场回顾（200-500字，包括大盘走势、行业表现、重要新闻）",
  "trading_record": "交易记录（100-300字，包括交易明细、持仓变化、盈亏情况）",
  "strategy_performance": "策略表现（100-300字，包括各策略收益率、回撤、信号触发情况）",
  "ai_insights": "AI洞察（100-300字，包括市场分析、风险评估、后续建议）",
  "summary": "一句话总结今日市场（50字内）",
  "importance_score": 0.5,
  "metrics": {{
    "market_trend": "up/down/flat",
    "total_pnl": 0,
    "win_rate": 0,
    "max_drawdown": 0
  }}
}}
"""

_MONTHLY_REPORT_PROMPT = """\
你是一位资深的 A 股量化交易分析师。请根据以下当月日报数据生成月度报告。

## 当月日报摘要
{daily_summaries}

请按以下格式输出（JSON）：
{{
  "market_review": "月度市场回顾（500-1000字）",
  "trading_record": "月度交易总结（300-500字）",
  "strategy_performance": "月度策略表现（300-500字）",
  "ai_insights": "月度AI洞察（200-400字）",
  "summary": "一句话总结本月（80字内）",
  "importance_score": 0.7,
  "metrics": {{
    "monthly_return": 0,
    "sharpe_ratio": 0,
    "max_drawdown": 0,
    "total_trades": 0,
    "win_rate": 0
  }}
}}
"""

_ANNUAL_REPORT_PROMPT = """\
你是一位资深的 A 股量化交易分析师。请根据以下当年月报数据生成年度报告。

## 当年月报摘要
{monthly_summaries}

请按以下格式输出（JSON）：
{{
  "market_review": "年度市场回顾（1000-2000字）",
  "trading_record": "年度交易总结（500-800字）",
  "strategy_performance": "年度策略表现（500-800字）",
  "ai_insights": "年度AI洞察与展望（300-500字）",
  "summary": "一句话总结本年度（100字内）",
  "importance_score": 0.9,
  "metrics": {{
    "annual_return": 0,
    "annual_sharpe": 0,
    "max_drawdown": 0,
    "total_trades": 0,
    "best_month": "",
    "worst_month": ""
  }}
}}
"""


# ─── 日期工具 ───────────────────────────────────────────────────────


def _get_month_end(year: int, month: int) -> str:
    """获取指定月份最后一天的日期字符串 YYYY-MM-DD"""
    _, last_day = monthrange(year, month)
    return f"{year:04d}-{month:02d}-{last_day:02d}"


def _get_month_start(year: int, month: int) -> str:
    """获取指定月份第一天的日期字符串 YYYY-MM-DD"""
    return f"{year:04d}-{month:02d}-01"


# ─── 占位数据（数据未接入时的 fallback） ────────────────────────────


def _placeholder_market_data(date: str) -> str:
    """生成占位市场数据"""
    return (
        f"日期：{date}\n"
        "上证指数：未接入（数据未接入）\n"
        "深证成指：未接入（数据未接入）\n"
        "创业板指：未接入（数据未接入）\n"
        "行业表现：未接入（数据未接入）\n"
        "重要新闻：未接入（数据未接入）"
    )


def _placeholder_trading_data(date: str) -> str:
    """生成占位交易数据"""
    return (
        f"日期：{date}\n"
        "交易明细：暂无交易记录（数据未接入）\n"
        "持仓变化：未接入（数据未接入）\n"
        "盈亏情况：未接入（数据未接入）"
    )


def _placeholder_strategy_data(date: str) -> str:
    """生成占位策略数据"""
    return (
        f"日期：{date}\n"
        "策略收益率：未接入（数据未接入）\n"
        "回撤情况：未接入（数据未接入）\n"
        "信号触发：未接入（数据未接入）"
    )


def _placeholder_ai_insights(date: str) -> str:
    """生成占位 AI 洞察"""
    return (
        f"日期：{date}\n"
        "市场分析：待系统接入后自动生成\n"
        "风险评估：待系统接入后自动生成\n"
        "后续建议：待系统接入后自动生成"
    )


# ─── ReportGenerator ────────────────────────────────────────────────


class ReportGenerator:
    """AI 报告生成器

    日报：每日市场收盘后自动生成
    月报：每月第一个交易日聚合当月所有日报
    年报：每年第一个交易日聚合当年所有月报
    """

    def __init__(
        self,
        llm_adapter: Optional[Any] = None,
        store: Optional[Any] = None,
    ) -> None:
        self._llm = llm_adapter
        self._store = store
        # RecallScorer 用于评分
        try:
            from .recall_scorer import RecallScorer
            self._scorer = RecallScorer(scene="review")
        except ImportError:
            self._scorer = None

    # ── 日报生成 ────────────────────────────────────────────────────

    def generate_daily(
        self,
        date: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """生成日报

        数据来源（从系统数据采集）：
        1. 市场回顾：当日大盘走势、行业表现、个股异动
        2. 交易记录：当日交易明细、持仓变化、盈亏
        3. 策略表现：各策略收益率、回撤、信号触发
        4. AI 洞察：Agent 对市场的分析判断

        通过 LLM 聚合为结构化报告，写入 ReportStore。

        参数:
            date: 日期字符串 YYYY-MM-DD，默认当天
            context_data: 外部传入的上下文数据，包含：
                - market_data: 市场数据文本
                - trading_data: 交易数据文本
                - strategy_data: 策略数据文本
                - ai_insights: AI 洞察文本

        返回: 报告 ID
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        ctx = context_data or {}
        market_data = ctx.get("market_data") or _placeholder_market_data(date)
        trading_data = ctx.get("trading_data") or _placeholder_trading_data(date)
        strategy_data = ctx.get("strategy_data") or _placeholder_strategy_data(date)
        ai_insights = ctx.get("ai_insights") or _placeholder_ai_insights(date)

        # 构建 prompt
        prompt = _DAILY_REPORT_PROMPT.format(
            market_data=market_data,
            trading_data=trading_data,
            strategy_data=strategy_data,
            ai_insights=ai_insights,
        )

        # 调用 LLM 生成报告
        result = self._call_llm(prompt)

        # 解析 LLM 返回的 JSON
        report_data = self._parse_llm_result(result, fallback_date=date)

        # 组装完整报告记录
        report = {
            "report_type": "daily",
            "report_date": date,
            "report_period_start": date,
            "report_period_end": date,
            **report_data,
        }

        # 写入 ReportStore
        report_id = self._write_to_store(report)
        logger.info("日报已生成: id=%s, date=%s", report_id, date)
        return report_id

    # ── 月报生成 ────────────────────────────────────────────────────

    def generate_monthly(
        self,
        year_month: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """生成月报（聚合当月所有日报）

        1. 从 ReportStore 获取当月所有日报
        2. 用 LLM 聚合为月度总结
        3. 写入 ReportStore

        参数:
            year_month: 年月字符串 YYYY-MM，默认当月
            context_data: 外部传入的上下文数据（可选，覆盖 Store 数据）

        返回: 报告 ID
        """
        now = datetime.now()
        if year_month is None:
            year_month = now.strftime("%Y-%m")

        year, month = year_month.split("-")
        year, month = int(year), int(month)

        period_start = _get_month_start(year, month)
        period_end = _get_month_end(year, month)
        report_date = period_end  # 月报日期设为月末最后一天

        # 获取当月日报摘要
        daily_summaries = self._collect_daily_summaries(
            period_start, period_end, context_data
        )

        # 构建 prompt
        prompt = _MONTHLY_REPORT_PROMPT.format(
            daily_summaries=daily_summaries,
        )

        # 调用 LLM 生成月报
        result = self._call_llm(prompt)

        # 解析 LLM 返回的 JSON
        report_data = self._parse_llm_result(
            result, fallback_date=report_date, is_monthly=True
        )

        # 组装完整报告记录
        report = {
            "report_type": "monthly",
            "report_date": report_date,
            "report_period_start": period_start,
            "report_period_end": period_end,
            **report_data,
        }

        # 写入 ReportStore
        report_id = self._write_to_store(report)
        logger.info("月报已生成: id=%s, period=%s", report_id, year_month)
        return report_id

    # ── 年报生成 ────────────────────────────────────────────────────

    def generate_annual(
        self,
        year: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """生成年报（聚合当年所有月报）

        1. 从 ReportStore 获取当年所有月报
        2. 用 LLM 聚合为年度总结
        3. 写入 ReportStore

        参数:
            year: 年份字符串 YYYY，默认当年
            context_data: 外部传入的上下文数据（可选，覆盖 Store 数据）

        返回: 报告 ID
        """
        if year is None:
            year = datetime.now().strftime("%Y")

        year_int = int(year)
        period_start = f"{year_int:04d}-01-01"
        period_end = f"{year_int:04d}-12-31"
        report_date = period_end  # 年报日期设为 12-31

        # 获取当年月报摘要
        monthly_summaries = self._collect_monthly_summaries(
            period_start, period_end, context_data
        )

        # 构建 prompt
        prompt = _ANNUAL_REPORT_PROMPT.format(
            monthly_summaries=monthly_summaries,
        )

        # 调用 LLM 生成年报
        result = self._call_llm(prompt)

        # 解析 LLM 返回的 JSON
        report_data = self._parse_llm_result(
            result, fallback_date=report_date, is_annual=True
        )

        # 组装完整报告记录
        report = {
            "report_type": "annual",
            "report_date": report_date,
            "report_period_start": period_start,
            "report_period_end": period_end,
            **report_data,
        }

        # 写入 ReportStore
        report_id = self._write_to_store(report)
        logger.info("年报已生成: id=%s, year=%s", report_id, year)
        return report_id

    # ── 内部方法 ────────────────────────────────────────────────────

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM 生成文本

        如果 llm_adapter 不可用，返回简化的文本报告。
        """
        if self._llm is not None:
            try:
                # 尝试调用 LLM adapter
                # 支持两种接口：
                # 1. adapter.chat(prompt) -> str
                # 2. adapter.generate(prompt) -> str
                if hasattr(self._llm, "chat"):
                    return str(self._llm.chat(prompt))
                elif hasattr(self._llm, "generate"):
                    return str(self._llm.generate(prompt))
                elif callable(self._llm):
                    return str(self._llm(prompt))
            except Exception as exc:
                logger.warning("LLM 调用失败: %s，降级为文本报告", exc)

        # 无 LLM 降级：生成简化的文本报告
        return self._generate_fallback_text(prompt)

    def _generate_fallback_text(self, prompt: str) -> str:
        """无 LLM 时的降级文本报告

        根据 prompt 内容判断报告类型，生成简化文本。
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        if "日报" in prompt or "今日" in prompt:
            return json.dumps({
                "market_review": (
                    f"（{now}，数据未接入）"
                    "市场回顾：今日 A 股市场整体表现待数据接入后分析。"
                ),
                "trading_record": (
                    "交易记录：暂无交易记录，系统数据尚未接入。"
                ),
                "strategy_performance": (
                    "策略表现：各策略运行状态待数据接入后评估。"
                ),
                "ai_insights": (
                    "AI 洞察：待系统数据接入后，AI 将自动分析市场走势"
                    "并提供投资建议。"
                ),
                "summary": "数据未接入，报告为占位内容。",
                "importance_score": 0.3,
                "metrics": {
                    "market_trend": "flat",
                    "total_pnl": 0,
                    "win_rate": 0,
                    "max_drawdown": 0,
                },
            }, ensure_ascii=False)

        if "月报" in prompt or "当月" in prompt:
            return json.dumps({
                "market_review": (
                    f"（{now}，数据未接入）"
                    "月度市场回顾：本月 A 股市场整体走势待数据接入后分析。"
                ),
                "trading_record": (
                    "月度交易总结：暂无月度交易汇总数据。"
                ),
                "strategy_performance": (
                    "月度策略表现：各策略月度收益待数据接入后评估。"
                ),
                "ai_insights": (
                    "月度 AI 洞察：待系统数据接入后进行月度分析。"
                ),
                "summary": "月度数据未接入，报告为占位内容。",
                "importance_score": 0.5,
                "metrics": {
                    "monthly_return": 0,
                    "sharpe_ratio": 0,
                    "max_drawdown": 0,
                    "total_trades": 0,
                    "win_rate": 0,
                },
            }, ensure_ascii=False)

        if "年报" in prompt or "当年" in prompt or "年度" in prompt:
            return json.dumps({
                "market_review": (
                    f"（{now}，数据未接入）"
                    "年度市场回顾：本年度 A 股市场整体走势待数据接入后分析。"
                ),
                "trading_record": (
                    "年度交易总结：暂无年度交易汇总数据。"
                ),
                "strategy_performance": (
                    "年度策略表现：各策略年度收益待数据接入后评估。"
                ),
                "ai_insights": (
                    "年度 AI 洞察与展望：待系统数据接入后进行年度分析"
                    "与下一年度展望。"
                ),
                "summary": "年度数据未接入，报告为占位内容。",
                "importance_score": 0.7,
                "metrics": {
                    "annual_return": 0,
                    "annual_sharpe": 0,
                    "max_drawdown": 0,
                    "total_trades": 0,
                    "best_month": "",
                    "worst_month": "",
                },
            }, ensure_ascii=False)

        # 通用降级
        return json.dumps({
            "market_review": "数据未接入，暂无分析。",
            "trading_record": "暂无交易记录。",
            "strategy_performance": "暂无策略表现数据。",
            "ai_insights": "待数据接入后自动生成分析。",
            "summary": "数据未接入。",
            "importance_score": 0.3,
            "metrics": {},
        }, ensure_ascii=False)

    def _parse_llm_result(
        self,
        result: str,
        fallback_date: str = "",
        is_monthly: bool = False,
        is_annual: bool = False,
    ) -> Dict[str, Any]:
        """解析 LLM 返回的 JSON 结果

        尝试从 LLM 输出中提取 JSON，失败时降级为结构化文本。

        返回可直接写入 ReportStore 的字段字典。
        """
        # 尝试提取 JSON（兼容 markdown 代码块包裹）
        parsed = self._extract_json(result)

        if parsed and isinstance(parsed, dict):
            # 提取标准字段
            market_review = parsed.get("market_review", "")
            trading_record = parsed.get("trading_record", "")
            strategy_performance = parsed.get("strategy_performance", "")
            ai_insights = parsed.get("ai_insights", "")
            summary = parsed.get("summary", "")
            importance_score = float(parsed.get("importance_score", 0.5))
            metrics = parsed.get("metrics", {})

            # 设置默认 importance_score（按报告类型）
            if is_annual:
                importance_score = max(importance_score, 0.9)
            elif is_monthly:
                importance_score = max(importance_score, 0.7)
            else:
                importance_score = max(importance_score, 0.5)

            return {
                "market_review": market_review,
                "trading_record": trading_record,
                "strategy_performance": strategy_performance,
                "ai_insights": ai_insights,
                "summary": summary,
                "importance_score": importance_score,
                "metrics_json": metrics,
                "confidence": 0.8,
                "metadata_json": {
                    "generated_by": "report_generator",
                    "generated_at": datetime.now().isoformat(),
                    "data_source": "llm" if self._llm else "fallback",
                },
            }

        # JSON 解析失败，降级为结构化文本
        logger.warning("LLM 返回的 JSON 解析失败，降级为结构化文本")
        return {
            "market_review": result[:2000] if result else "LLM 返回为空",
            "trading_record": "",
            "strategy_performance": "",
            "ai_insights": "",
            "summary": (
                f"报告生成于 {fallback_date}（LLM 输出格式异常，内容已原文保存）"
            ),
            "importance_score": 0.5 if not is_monthly and not is_annual else (
                0.7 if is_monthly else 0.9
            ),
            "metrics_json": {},
            "confidence": 0.5,
            "metadata_json": {
                "generated_by": "report_generator",
                "generated_at": datetime.now().isoformat(),
                "data_source": "llm_fallback",
                "parse_error": True,
            },
        }

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        """从 LLM 输出中提取 JSON

        支持以下格式：
        1. 纯 JSON 文本
        2. Markdown 代码块包裹的 JSON (```json ... ``` 或 ``` ... ```)
        3. JSON 前后有其他文本
        """
        if not text:
            return None

        text = text.strip()

        # 尝试提取 markdown 代码块中的 JSON
        code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
        match = re.search(code_block_pattern, text, re.DOTALL)
        if match:
            text = match.group(1).strip()

        # 尝试找到最外层的 JSON 对象
        # 查找第一个 { 和最后一个 } 之间的内容
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = text[start: end + 1]
            try:
                result = json.loads(json_str)
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        return None

    def _collect_daily_summaries(
        self,
        period_start: str,
        period_end: str,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """收集当月日报摘要，供月报 prompt 使用

        如果 context_data 中提供了 daily_summaries，直接使用；
        否则从 ReportStore 获取当月日报。
        """
        ctx = context_data or {}

        # 优先使用外部传入的摘要
        if "daily_summaries" in ctx:
            return str(ctx["daily_summaries"])

        # 从 Store 获取
        if self._store is not None:
            try:
                dailies = self._store.get_dailies_for_period(
                    period_start, period_end
                )
                if dailies:
                    summaries = []
                    for d in dailies:
                        date = d.get("report_date", "")
                        summary = d.get("summary", "")
                        market = (
                            d.get("market_review", "")[:200]
                        )
                        pnl = d.get("metrics", {}).get("total_pnl", "N/A")
                        summaries.append(
                            f"### {date}\n"
                            f"摘要：{summary}\n"
                            f"市场回顾：{market}...\n"
                            f"盈亏：{pnl}\n"
                        )
                    return "\n\n".join(summaries)
            except Exception as exc:
                logger.warning("从 Store 获取日报失败: %s", exc)

        return (
            f"期间：{period_start} 至 {period_end}\n"
            "暂无日报数据（数据未接入），月报将为占位内容。"
        )

    def _collect_monthly_summaries(
        self,
        period_start: str,
        period_end: str,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """收集当年月报摘要，供年报 prompt 使用

        如果 context_data 中提供了 monthly_summaries，直接使用；
        否则从 ReportStore 获取当年月报。
        """
        ctx = context_data or {}

        # 优先使用外部传入的摘要
        if "monthly_summaries" in ctx:
            return str(ctx["monthly_summaries"])

        # 从 Store 获取
        if self._store is not None:
            try:
                monthlies = self._store.get_monthlies_for_period(
                    period_start, period_end
                )
                if monthlies:
                    summaries = []
                    for m in monthlies:
                        date = m.get("report_date", "")
                        summary = m.get("summary", "")
                        market = (
                            m.get("market_review", "")[:300]
                        )
                        ret = m.get("metrics", {}).get(
                            "monthly_return", "N/A"
                        )
                        summaries.append(
                            f"### {date}\n"
                            f"摘要：{summary}\n"
                            f"市场回顾：{market}...\n"
                            f"月度收益率：{ret}\n"
                        )
                    return "\n\n".join(summaries)
            except Exception as exc:
                logger.warning("从 Store 获取月报失败: %s", exc)

        return (
            f"期间：{period_start} 至 {period_end}\n"
            "暂无月报数据（数据未接入），年报将为占位内容。"
        )

    def _write_to_store(self, report: Dict) -> str:
        """将报告写入 ReportStore

        如果 store 不可用，返回占位 ID。
        """
        if self._store is not None:
            try:
                return self._store.write(report)
            except Exception as exc:
                logger.error("报告写入 Store 失败: %s", exc)

        # Store 不可用时返回占位 ID
        report_type = report.get("report_type", "unknown")
        report_date = report.get("report_date", "")
        report_id = f"rpt_{report_type}_{report_date}_no_store"
        logger.warning(
            "ReportStore 不可用，报告未持久化: id=%s", report_id
        )
        return report_id
