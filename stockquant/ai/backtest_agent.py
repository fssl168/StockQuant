# -*- coding: utf-8 -*-
"""F023 AI 回测解读 Agent — 自然语言回测结果分析"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List

logger = logging.getLogger("stockquant.ai")


class BacktestAgent:
    """
    回测解读 Agent。

    回测结束后自动解读结果，用自然语言描述策略表现，指出问题，
    给出改进建议。这是规则/模板驱动的解读，不需要 LLM。

    用法:
        agent = BacktestAgent()
        report = agent.analyze(results)
        print(report.summary)    # 自然语言总结
        print(report.issues)     # 问题列表
        print(report.suggestions) # 改进建议
    """

    def __init__(self, risk_free_rate: float = 0.025):
        self._risk_free_rate = risk_free_rate

    def analyze(self, results: List[dict]) -> dict:
        """
        分析回测结果，生成自然语言解读。

        Parameters
        ----------
        results : List[dict]
            Cerebro.run() 返回的结果

        Returns
        -------
        dict
            {
                "summary": str,       # 自然语言总结
                "issues": List[str],  # 问题列表
                "suggestions": List[str],  # 改进建议
                "dimensions": Dict[str, str],  # 多维度分析
            }
        """
        if not results:
            return {
                "summary": "未提供回测结果，无法生成解读。",
                "issues": [],
                "suggestions": [],
                "dimensions": {},
            }

        all_issues = []
        all_suggestions = []
        all_dimensions = {}

        for r in results:
            strategy_name = r.get("name", "Unnamed")
            metrics = r.get("metrics", {})
            trades = r.get("trades", [])
            equity = r.get("equity_curve", [])

            # 单策略解读
            self._generate_summary(strategy_name, metrics, trades, equity)
            issues = self._identify_issues(metrics)
            suggestions = self._generate_suggestions(metrics, issues)
            dimensions = self._multi_dimension_analysis(metrics, trades)

            all_dimensions[strategy_name] = dimensions

            # 汇总
            all_issues.extend(issues)
            all_suggestions.extend(suggestions)

        # 全局总结
        global_summary = f"""
=== 回测自动解读报告 ===
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
分析策略数量: {len(results)}

--- 策略解读 ---
"""
        for name, dims in all_dimensions.items():
            global_summary += f"\n📊 {name}:\n"
            global_summary += f"  {dims.get('performance', '')}\n"
            global_summary += f"  {dims.get('risk', '')}\n"
            global_summary += f"  {dims.get('trading', '')}\n"
            global_summary += f"  {dims.get('quality', '')}\n"

        if all_issues:
            global_summary += f"\n⚠️ 发现问题 ({len(all_issues)} 个):\n"
            for i, issue in enumerate(all_issues, 1):
                global_summary += f"  {i}. {issue}\n"

        if all_suggestions:
            global_summary += f"\n💡 改进建议 ({len(all_suggestions)} 条):\n"
            for i, sug in enumerate(all_suggestions, 1):
                global_summary += f"  {i}. {sug}\n"

        return {
            "summary": global_summary.strip(),
            "issues": all_issues,
            "suggestions": all_suggestions,
            "dimensions": all_dimensions,
        }

    def _generate_summary(
        self,
        name: str,
        metrics: dict,
        trades: list,
        equity: list,
    ) -> str:
        """生成单策略自然语言总结"""
        lines = [f"策略 '{name}' 回测结果分析："]

        total_return = metrics.get("Total Return", "N/A")
        ann_return = metrics.get("Annualized Return", "N/A")
        sharpe = metrics.get("Sharpe Ratio", "N/A")
        max_dd = metrics.get("Max Drawdown", "N/A")
        win_rate = metrics.get("Win Rate", "N/A")
        total_trades = len(trades)
        profit_factor = metrics.get("Profit Factor", "N/A")

        lines.append(f"  累计收益率 {total_return}，年化收益率 {ann_return}，夏普比率 {sharpe}。")

        # 收益评价
        try:
            ann_val = float(ann_return.replace("%", "")) / 100 if "%" in str(ann_return) else float(ann_return)
            if ann_val > 0.20:
                lines.append("  ✅ 年化收益表现优秀，超过 20% 的基准要求。")
            elif ann_val > 0:
                lines.append("  ⚠️ 年化收益为正但偏低，建议优化参数或考虑其他策略。")
            else:
                lines.append("  ❌ 年化收益为负，策略需要大幅改进。")
        except (ValueError, TypeError):
            pass

        # 回撤评价
        try:
            dd_val = float(max_dd.replace("%", "")) / 100 if "%" in str(max_dd) else float(max_dd)
            if dd_val > 0.30:
                lines.append(f"  ⚠️ 最大回撤达 {max_dd}，风险偏高，建议增加止损规则。")
            elif dd_val > 0.20:
                lines.append(f"  ⚠️ 最大回撤 {max_dd}，在可接受范围内但需关注。")
            else:
                lines.append(f"  ✅ 最大回撤 {max_dd}，风险控制良好。")
        except (ValueError, TypeError):
            pass

        # 胜率评价
        lines.append(f"  共完成 {total_trades} 笔交易，胜率 {win_rate}，盈亏比 {profit_factor}。")

        # 交易活跃度
        if total_trades > 500:
            lines.append(f"  ⚠️ 交易次数过多（{total_trades} 笔），可能存在过度交易问题。")
        elif total_trades < 5:
            lines.append(f"  ⚠️ 交易次数过少（{total_trades} 笔），样本量不足，结果可能偶然。")

        return " ".join(lines)

    def _identify_issues(self, metrics: dict) -> list[str]:
        """识别回测中的问题"""
        issues = []

        # 回撤过大
        max_dd = metrics.get("Max Drawdown", "0%")
        try:
            dd_val = float(max_dd.replace("%", "")) / 100
            if dd_val > 0.30:
                issues.append(
                    f"最大回撤 {max_dd} 超过 30% 警戒线，"
                    "建议增加动态止损或降低仓位。"
                )
        except (ValueError, TypeError):
            pass

        # 胜率过低
        win_rate = metrics.get("Win Rate", "0%")
        try:
            wr_val = float(win_rate.replace("%", "")) / 100
            if wr_val < 0.40 and metrics.get("Total Trades", 0) > 20:
                issues.append(
                    f"胜率 {win_rate} 偏低，建议优化入场条件或改用趋势跟踪策略。"
                )
        except (ValueError, TypeError):
            pass

        # 夏普过低
        sharpe = metrics.get("Sharpe Ratio", "0")
        try:
            s_val = float(sharpe)
            if s_val < 0.5:
                issues.append(
                    f"夏普比率 {sharpe} 低于 0.5，风险调整后收益不佳，"
                    "考虑增加过滤条件减少虚假信号。"
                )
        except (ValueError, TypeError):
            pass

        # 过度交易
        total_trades = metrics.get("Total Trades", 0)
        try:
            if isinstance(total_trades, int) and total_trades > 500:
                issues.append(
                    f"交易次数 {total_trades} 过多，手续费可能侵蚀大部分利润，"
                    "建议增加持仓时间要求或提高信号门槛。"
                )
        except (ValueError, TypeError):
            pass

        # SQN 低
        sqn = metrics.get("SQN (System Quality Number)", "0")
        try:
            sqn_val = float(sqn)
            if sqn_val < 1.0:
                issues.append(
                    f"SQN {sqn} 低于 1.0，系统质量较差，"
                    "策略信号稳定性不足，需要更多样本验证。"
                )
        except (ValueError, TypeError):
            pass

        return issues

    def _generate_suggestions(self, metrics: dict, issues: list[str]) -> list[str]:
        """根据问题和指标生成改进方向生成建议"""
        suggestions = []

        # 基于回撤建议
        if any("回撤" in i for i in issues):
            suggestions.extend([
                "增加动态止损机制：当单笔亏损超过 5% 时自动平仓。",
                "降低仓位规模：使用更小的 FixedFraction（如 50% 仓位）。",
                "增加趋势过滤器：只在均线之上做多，避免逆势交易。",
            ])

        # 基于胜率建议
        if any("胜率" in i for i in issues):
            suggestions.extend([
                "增加确认条件：如加入成交量放大、MACD 确认等辅助过滤。",
                "改用盈亏比驱动策略：接受较低胜率但提高平均盈利。",
                "回看交易明细，找出亏损集中的交易模式并针对性优化。",
            ])

        # 基于夏普建议
        if any("夏普" in i for i in issues):
            suggestions.extend([
                "尝试不同的市场状态过滤：波动率过高时暂停交易。",
                "考虑多策略组合，降低单一策略的系统性风险。",
            ])

        # 基于交易次数建议
        if any("交易次数" in i for i in issues):
            suggestions.extend([
                "增加持仓时间要求（如至少持有 3 根 K 线以上）。",
                "提高信号触发门槛较低的入场条件。",
            ])

        # 通用建议（如果没有具体问题则提供）
        if not issues:
            suggestions.extend([
                "策略表现良好，建议进行样本外验证（out-of-sample test）。",
                "考虑进行参数敏感性分析，避免过拟合。",
                "可以尝试在模拟盘上运行验证实盘效果。",
            ])

        return suggestions[:5]  # 最多 5 条建议

    def _multi_dimension_analysis(
        self,
        metrics: dict,
        trades: list,
    ) -> dict:
        """多维度分析"""
        ann_return = metrics.get("Annualized Return", "N/A")
        max_dd = metrics.get("Max Drawdown", "N/A")
        sharpe = metrics.get("Sharpe Ratio", "N/A")
        metrics.get("Sortino Ratio", "N/A")
        metrics.get("Calmar Ratio", "N/A")
        win_rate = metrics.get("Win Rate", "N/A")
        profit_factor = metrics.get("Profit Factor", "N/A")
        total_trades = metrics.get("Total Trades", 0)
        sqn = metrics.get("SQN (System Quality Number)", "N/A")
        kelly = metrics.get("Kelly %", "N/A")
        var_95 = metrics.get("VaR (95%)", "N/A")
        beta = metrics.get("Beta", "N/A")
        alpha = metrics.get("Alpha", "N/A")

        # 收益评价
        try:
            ann_val = float(ann_return.replace("%", "")) / 100 if "%" in str(ann_return) else 0
            perf = f"年化收益 {ann_return}。"
            if ann_val > 0.25:
                perf += "收益能力优秀。"
            elif ann_val > 0.10:
                perf += "收益能力良好。"
            elif ann_val > 0:
                perf += "收益能力一般。"
            else:
                perf += "收益为负，需改进。"
        except (ValueError, TypeError):
            perf = f"年化收益 {ann_return}，无法评估。"

        # 风险评价
        try:
            dd_val = float(max_dd.replace("%", "")) / 100 if "%" in str(max_dd) else 0
            risk = f"最大回撤 {max_dd}。"
            if dd_val < 0.15:
                risk += "风险控制优秀。"
            elif dd_val < 0.25:
                risk += "风险可控。"
            else:
                risk += "风险偏高，需要关注。"
        except (ValueError, TypeError):
            risk = f"最大回撤 {max_dd}，无法评估。"

        # 交易质量
        trading = f"交易 {total_trades} 次，胜率 {win_rate}，盈亏比 {profit_factor}。"
        if float(sharpe) > 1.0 if sharpe != "N/A" else False:
            trading += "风险调整后收益良好。"
        if float(sqn) > 2.0 if sqn != "N/A" else False:
            trading += "系统质量较高。"

        # 综合质量
        quality = f"SQN {sqn}，Kelly 建议仓位 {kelly}。"
        if beta != "N/A":
            quality += f"Beta {beta}，Alpha {alpha}。"
        quality += f"VaR(95%) {var_95}。"

        return {
            "performance": perf,
            "risk": risk,
            "trading": trading,
            "quality": quality,
        }
