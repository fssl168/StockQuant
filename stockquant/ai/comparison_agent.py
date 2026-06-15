# -*- coding: utf-8 -*-
"""F027 AI 策略回测对比 Agent — 多策略横向对比 + 组合优化"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("stockquant.ai")


@dataclass
class StrategyComparison:
    """策略对比结果"""

    strategies: List[str] = field(default_factory=list)
    rankings: Dict[str, List[tuple]] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    portfolio_weights: Dict[str, float] = field(default_factory=dict)
    correlation_matrix: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class ComparisonAgent:
    """F027 AI 策略回测对比 Agent。

    横向对比多个策略的优劣，推荐最优组合比例。

    Parameters
    ----------
    metrics : list[str] | None
        要对比的回测指标列表
    """

    DEFAULT_METRICS: List[str] = [
        "Annualized Return", "Max Drawdown", "Sharpe Ratio",
        "Win Rate", "SQN (System Quality Number)", "Total Trades",
        "Sortino Ratio", "Calmar Ratio",
    ]

    def __init__(self, metrics: Optional[List[str]] = None) -> None:
        self._metrics = metrics or self.DEFAULT_METRICS
        self._comparisons: List[StrategyComparison] = []

    @property
    def metrics(self) -> List[str]:
        return self._metrics

    def compare(
        self,
        results: List[Dict[str, Any]],
        strategy_names: Optional[List[str]] = None,
    ) -> StrategyComparison:
        """对比多个策略的回测结果。

        Parameters
        ----------
        results : list[dict]
            每个元素包含策略的 backtest metrics
        strategy_names : list[str] | None
            策略名称，与 results 一一对应

        Returns
        -------
        StrategyComparison
        """
        if strategy_names is None:
            strategy_names = [f"Strategy {i+1}" for i in range(len(results))]

        if len(results) != len(strategy_names):
            raise ValueError("results 和 strategy_names 长度必须一致")

        # 计算排名
        rankings: Dict[str, List[tuple]] = {}
        for metric in self._metrics:
            entries: List[tuple] = []
            for i, r in enumerate(results):
                val = r.get(metric)
                if val is not None:
                    entries.append((strategy_names[i], self._normalize_metric(metric, val)))
            if entries:
                reverse = self._metric_is_better_lower(metric)
                entries.sort(key=lambda x: x[1], reverse=not reverse)
                rankings[metric] = entries

        # 综合排名
        total_scores: Dict[str, int] = {name: 0 for name in strategy_names}
        for metric_entries in rankings.values():
            for rank_idx, (name, _) in enumerate(metric_entries):
                total_scores[name] += len(metric_entries) - rank_idx

        ranked_strategies = sorted(total_scores.items(), key=lambda x: x[1], reverse=True)

        # 相关性分析
        correlation_matrix = self._compute_correlation(results)

        # 组合优化
        portfolio_weights = self._optimize_weights(results, correlation_matrix)

        # 生成建议（含近期表现）
        recent_perf = self._compute_recent_performance(results)
        recommendations = self._generate_recommendations(ranked_strategies, portfolio_weights, recent_perf)

        comparison = StrategyComparison(
            strategies=strategy_names,
            rankings=rankings,
            recommendations=recommendations,
            portfolio_weights=portfolio_weights,
            correlation_matrix=correlation_matrix,
        )

        self._comparisons.append(comparison)
        return comparison

    def get_comparisons(self, limit: int = 20) -> List[StrategyComparison]:
        return self._comparisons[-limit:]

    # ── 私有方法 ──

    @staticmethod
    def _normalize_metric(metric: str, value: Any) -> float:
        """将不同指标归一化到 0-1 范围"""
        try:
            if isinstance(value, str):
                value = float(value.replace("%", "")) / 100
            else:
                value = float(value)
        except (ValueError, TypeError):
            return 0.0

        if metric in ("Annualized Return",):
            return max(0.0, min(1.0, value / 0.5 + 0.5))
        if metric in ("Sharpe Ratio",):
            return max(0.0, min(1.0, (value + 2) / 4))
        if metric in ("Sortino Ratio",):
            return max(0.0, min(1.0, (value + 1) / 3))
        if metric in ("Calmar Ratio",):
            return max(0.0, min(1.0, (value + 1) / 2))
        if metric in ("SQN (System Quality Number)",):
            return max(0.0, min(1.0, (value + 2) / 4))
        if metric in ("Win Rate",):
            return max(0.0, min(1.0, value / 100))
        if metric in ("Max Drawdown",):
            dd = float(value) if isinstance(value, str) else value
            return max(0.0, min(1.0, 1.0 - abs(dd)))
        return max(0.0, min(1.0, abs(value)))

    @staticmethod
    def _metric_is_better_lower(metric: str) -> bool:
        return metric in ("Max Drawdown",)

    def _compute_correlation(
        self, results: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """计算策略间的收益相关性（使用逐日收益率序列计算 Pearson 相关系数）"""
        if len(results) < 2:
            return {}

        import pandas as pd

        # 从 equity_curve 提取逐日收益率
        series_map: Dict[str, pd.Series] = {}
        for i, r in enumerate(results):
            name = r.get("strategy", f"Strategy {i+1}")
            equity = r.get("equity_curve")
            if isinstance(equity, list) and len(equity) >= 2:
                # equity_curve 格式: [[date, value], ...] 或 [value, ...]
                try:
                    if isinstance(equity[0], (list, tuple)) and len(equity[0]) >= 2:
                        values = [float(p[1]) for p in equity]
                    else:
                        values = [float(v) for v in equity]
                    series_map[name] = pd.Series(values).pct_change().dropna()
                except (ValueError, TypeError, IndexError):
                    series_map[name] = pd.Series([0.0])
            else:
                # 退化：从汇总指标估算
                try:
                    ann_return = r.get("Annualized Return", 0)
                    if isinstance(ann_return, str):
                        ann_return = float(ann_return.replace("%", "")) / 100
                    vals = [float(ann_return) / 252] * 5
                    series_map[name] = pd.Series(vals)
                except (ValueError, TypeError):
                    series_map[name] = pd.Series([0.0])

        if len(series_map) < 2:
            return {}

        corr_df = pd.DataFrame(series_map).corr(method="pearson")
        result: Dict[str, float] = {}
        names = list(series_map.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                c = corr_df.loc[names[i], names[j]]
                if pd.isna(c):
                    c = 0.0
                key = (names[i], names[j])
                result[str(key)] = round(float(c), 3)

        return result

    def _compute_recent_performance(
        self, results: List[Dict[str, Any]], window: int = 20
    ) -> Dict[str, Dict[str, float]]:
        """计算策略近期表现（最近 N 天的收益/回撤趋势）"""
        perf: Dict[str, Dict[str, float]] = {}
        for i, r in enumerate(results):
            name = r.get("strategy", f"Strategy {i+1}")
            equity = r.get("equity_curve")
            recent: Dict[str, float] = {}
            if isinstance(equity, list) and len(equity) >= 2:
                try:
                    if isinstance(equity[0], (list, tuple)):
                        values = [float(p[1]) for p in equity]
                    else:
                        values = [float(v) for v in equity]
                    n = len(values)
                    recent_window = values[-window:] if n >= window else values
                    if len(recent_window) >= 2:
                        ret = (recent_window[-1] - recent_window[0]) / max(abs(recent_window[0]), 1)
                        peak = max(recent_window)
                        dd = (recent_window[-1] - peak) / max(abs(peak), 1)
                        recent["recent_return"] = round(ret * 100, 2)
                        recent["recent_drawdown"] = round(dd * 100, 2)
                    else:
                        recent["recent_return"] = 0.0
                        recent["recent_drawdown"] = 0.0
                except (ValueError, TypeError, IndexError):
                    recent["recent_return"] = 0.0
                    recent["recent_drawdown"] = 0.0
            else:
                recent["recent_return"] = 0.0
                recent["recent_drawdown"] = 0.0
            perf[name] = recent
        return perf

    def _optimize_weights(
        self,
        results: List[Dict[str, Any]],
        correlation_matrix: Dict[str, float],
    ) -> Dict[str, float]:
        """基于风险和收益优化权重分配"""
        n = len(results)
        if n == 0:
            return {}
        if n == 1:
            return {results[0].get("strategy", "Strategy 1"): 1.0}

        scores: List[float] = []
        for r in results:
            try:
                sharpe = float(r.get("Sharpe Ratio", 0))
                dd = float(r.get("Max Drawdown", 0))
                if dd == 0:
                    dd = -0.1
                score = sharpe / abs(dd) if abs(dd) > 0.01 else 1.0
            except (ValueError, TypeError):
                score = 0.0
            scores.append(score)

        total_score = sum(scores)
        if total_score <= 0:
            weights = [1.0 / n] * n
        else:
            weights = [s / total_score for s in scores]

        strategy_names = [r.get("strategy", f"Strategy {i+1}") for i, r in enumerate(results)]
        weighted: Dict[str, float] = {}
        for i, name in enumerate(strategy_names):
            penalty = 1.0
            for j in range(n):
                if i != j:
                    key = (
                        results[i].get("strategy", ""),
                        results[j].get("strategy", ""),
                    )
                    corr = correlation_matrix.get(str(key), 0)
                    if corr > 0:
                        penalty -= corr * 0.1
            weighted[name] = round(max(0.05, weights[i] * penalty), 3)

        # 归一化
        total_w = sum(weighted.values())
        if total_w > 0:
            weighted = {k: round(v / total_w, 3) for k, v in weighted.items()}

        return weighted

    @staticmethod
    def _generate_recommendations(
        ranked: List[tuple],
        weights: Dict[str, float],
        recent_perf: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> List[str]:
        """生成对比建议（含近期表现与生命周期建议）"""
        recs: List[str] = []

        if ranked:
            best = ranked[0][0]
            recs.append(f"优策略: {best}（综合排名第 1）")

        if ranked and len(ranked) > 1:
            parts = [f"{name}({w*100:.0f}%)" for name, w in weights.items()]
            recs.append(f"建议组合: {' + '.join(parts)}")

        for name, w in weights.items():
            if w >= 0.4:
                recs.append(f"  {name} 建议高配 ({w*100:.0f}%)")
            elif w <= 0.1:
                recs.append(f"  {name} 建议低配或停用 ({w*100:.0f}%)")

        # 近期表现分析 → 生命周期建议
        if recent_perf:
            for name, perf in recent_perf.items():
                ret = perf.get("recent_return", 0)
                dd = perf.get("recent_drawdown", 0)
                if ret < -10 and dd < -15:
                    recs.append(f"  ⚠ {name} 近期表现不佳（收益 {ret}%，回撤 {dd}%），建议暂停或重构")
                elif ret > 5 and abs(dd) < 5:
                    recs.append(f"  ✓ {name} 近期表现稳健（收益 {ret}%），建议维持")
                elif ret < 0:
                    recs.append(f"  ~ {name} 近期小幅回撤（收益 {ret}%），建议观察")

        if not recs:
            recs.append("暂无足够数据进行对比分析")

        return recs

    def compare_with_json(self, json_strings: List[str]) -> str:
        """传入 JSON 字符串进行对比"""
        results = [json.loads(j) if isinstance(j, str) else j for j in json_strings]
        names = [f"Strategy {i+1}" for i in range(len(results))]
        comparison = self.compare(results, names)
        return json.dumps({
            "strategies": comparison.strategies,
            "rankings": {
                k: [(n, round(v, 3)) for n, v in entries]
                for k, entries in comparison.rankings.items()
            },
            "recommendations": comparison.recommendations,
            "portfolio_weights": comparison.portfolio_weights,
        }, ensure_ascii=False, default=str)
