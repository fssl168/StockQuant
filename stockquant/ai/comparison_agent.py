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

    def optimize_portfolio(self, strategy_results: list) -> dict:
        """F027 策略组合优化 — 相关性+最优权重。

        计算策略间相关性矩阵，使用均值-方差模型推荐最优权重（最小化组合回撤）。

        Parameters
        ----------
        strategy_results : list[dict]
            每个元素包含策略的回测指标和 equity_curve

        Returns
        -------
        dict
            weights, expected_return, expected_volatility, expected_sharpe,
            max_drawdown, correlation_matrix
        """
        n = len(strategy_results)
        if n == 0:
            return {
                "weights": {},
                "expected_return": 0.0,
                "expected_volatility": 0.0,
                "expected_sharpe": 0.0,
                "max_drawdown": 0.0,
                "correlation_matrix": {},
            }

        strategy_names = [
            r.get("strategy", r.get("strategy_name", f"Strategy {i+1}"))
            for i, r in enumerate(strategy_results)
        ]

        # ── 提取收益率序列 ──
        return_series: Dict[str, List[float]] = {}
        for i, r in enumerate(strategy_results):
            name = strategy_names[i]
            equity = r.get("equity_curve")
            if isinstance(equity, list) and len(equity) >= 2:
                try:
                    if isinstance(equity[0], (list, tuple)) and len(equity[0]) >= 2:
                        values = [float(p[1]) for p in equity]
                    else:
                        values = [float(v) for v in equity]
                    rets = []
                    for j in range(1, len(values)):
                        prev = values[j - 1]
                        if abs(prev) > 1e-10:
                            rets.append((values[j] - prev) / abs(prev))
                        else:
                            rets.append(0.0)
                    return_series[name] = rets
                except (ValueError, TypeError, IndexError):
                    return_series[name] = [0.0]
            else:
                # 退化：从年化收益估算日收益
                try:
                    ann_ret = r.get("Annualized Return", 0)
                    if isinstance(ann_ret, str):
                        ann_ret = float(ann_ret.replace("%", "")) / 100
                    return_series[name] = [float(ann_ret) / 252] * 10
                except (ValueError, TypeError):
                    return_series[name] = [0.0]

        # ── 计算相关性矩阵 ──
        corr_matrix: Dict[str, Dict[str, float]] = {}
        try:
            names_list = list(return_series.keys())
            # 对齐长度：取最短序列
            min_len = min(len(return_series[nm]) for nm in names_list)
            if min_len < 2:
                min_len = 2
            aligned = np.array([
                (return_series[nm][:min_len] if len(return_series[nm]) >= min_len
                 else return_series[nm] + [0.0] * (min_len - len(return_series[nm])))
                for nm in names_list
            ])
            corr_np = np.corrcoef(aligned)
            for i, ni in enumerate(names_list):
                corr_matrix[ni] = {}
                for j, nj in enumerate(names_list):
                    val = corr_np[i, j] if not np.isnan(corr_np[i, j]) else 0.0
                    corr_matrix[ni][nj] = round(float(val), 3)
        except Exception:
            # numpy 不可用时，相关性矩阵置零
            for ni in strategy_names:
                corr_matrix[ni] = {nj: (1.0 if ni == nj else 0.0) for nj in strategy_names}

        # ── 计算各策略统计量 ──
        stats: Dict[str, Dict[str, float]] = {}
        for name in strategy_names:
            rets = return_series.get(name, [0.0])
            arr = np.array(rets) if len(rets) > 1 else np.array([0.0])
            mean_ret = float(np.mean(arr))
            vol = float(np.std(arr)) if len(arr) > 1 else 0.01
            # 最大回撤
            cum = np.cumprod(1 + arr)
            peak = np.maximum.accumulate(cum)
            dd_arr = (cum - peak) / np.maximum(peak, 1e-10)
            mdd = float(np.min(dd_arr)) if len(dd_arr) > 0 else 0.0
            stats[name] = {
                "mean_return": mean_ret,
                "volatility": vol,
                "max_drawdown": abs(mdd),
            }

        # ── 均值-方差优化：最小化组合最大回撤 ──
        # 使用网格搜索 + 相关性惩罚
        best_weights: Dict[str, float] = {}
        best_score = -float("inf")

        try:
            # 生成候选权重组合
            step = 0.05
            n_strat = len(strategy_names)

            if n_strat <= 5:
                # 小规模：网格搜索
                from itertools import product as _product

                grid_vals = [round(v * step, 2) for v in range(1, int(1.0 / step) + 1)]
                # 限制候选数量
                candidates = []
                for combo in _product(grid_vals, repeat=n_strat):
                    if abs(sum(combo) - 1.0) < 1e-6:
                        candidates.append(combo)
                    if len(candidates) >= 2000:
                        break

                for combo in candidates:
                    w = {strategy_names[i]: combo[i] for i in range(n_strat)}
                    score = self._portfolio_score(w, stats, corr_matrix, strategy_names)
                    if score > best_score:
                        best_score = score
                        best_weights = dict(w)

        except Exception:
            pass

        # 退路：等权或基于 Sharpe 的权重
        if not best_weights:
            sharpes = []
            for name in strategy_names:
                s = stats[name]
                sharpe = s["mean_return"] / max(s["volatility"], 1e-6)
                sharpes.append(max(sharpe, 0.0))
            total = sum(sharpes)
            if total > 0:
                best_weights = {
                    name: round(sharpes[i] / total, 3)
                    for i, name in enumerate(strategy_names)
                }
            else:
                best_weights = {
                    name: round(1.0 / n, 3) for name in strategy_names
                }

        # 归一化
        total_w = sum(best_weights.values())
        if total_w > 0:
            best_weights = {k: round(v / total_w, 3) for k, v in best_weights.items()}

        # ── 计算组合期望指标 ──
        exp_return = 0.0
        exp_vol = 0.0
        for name in strategy_names:
            w = best_weights.get(name, 0.0)
            exp_return += w * stats[name]["mean_return"] * 252
            exp_vol += (w * stats[name]["volatility"]) ** 2
        # 加入协方差项
        for i, ni in enumerate(strategy_names):
            for j, nj in enumerate(strategy_names):
                if i < j:
                    corr_val = corr_matrix.get(ni, {}).get(nj, 0.0)
                    wi = best_weights.get(ni, 0.0)
                    wj = best_weights.get(nj, 0.0)
                    exp_vol += 2 * wi * wj * corr_val * stats[ni]["volatility"] * stats[nj]["volatility"]
        exp_vol = float(np.sqrt(max(exp_vol, 0.0))) * np.sqrt(252)
        exp_sharpe = exp_return / max(exp_vol, 1e-6)

        # 组合最大回撤（加权近似）
        port_mdd = 0.0
        for name in strategy_names:
            w = best_weights.get(name, 0.0)
            port_mdd += w * stats[name]["max_drawdown"]

        # 相关性矩阵扁平化输出（兼容旧格式）
        flat_corr: Dict[str, float] = {}
        for i, ni in enumerate(strategy_names):
            for j, nj in enumerate(strategy_names):
                if i < j:
                    flat_corr[str((ni, nj))] = corr_matrix.get(ni, {}).get(nj, 0.0)

        return {
            "weights": best_weights,
            "expected_return": round(float(exp_return), 4),
            "expected_volatility": round(float(exp_vol), 4),
            "expected_sharpe": round(float(exp_sharpe), 2),
            "max_drawdown": round(float(port_mdd), 4),
            "correlation_matrix": corr_matrix,
        }

    @staticmethod
    def _portfolio_score(
        weights: Dict[str, float],
        stats: Dict[str, Dict[str, float]],
        corr_matrix: Dict[str, Dict[str, float]],
        names: List[str],
    ) -> float:
        """评估一组权重的组合得分（越高越好）。

        目标：最大化 Sharpe - 回撤惩罚 - 相关性惩罚
        """
        exp_ret = sum(weights.get(n, 0) * stats[n]["mean_return"] for n in names) * 252
        exp_vol_sq = sum((weights.get(n, 0) * stats[n]["volatility"]) ** 2 for n in names)
        for i, ni in enumerate(names):
            for j, nj in enumerate(names):
                if i < j:
                    corr_val = corr_matrix.get(ni, {}).get(nj, 0.0)
                    exp_vol_sq += 2 * weights.get(ni, 0) * weights.get(nj, 0) * corr_val * stats[ni]["volatility"] * stats[nj]["volatility"]
        exp_vol = float(np.sqrt(max(exp_vol_sq, 0.0))) * np.sqrt(252)
        sharpe = exp_ret / max(exp_vol, 1e-6)

        # 回撤惩罚
        mdd = sum(weights.get(n, 0) * stats[n]["max_drawdown"] for n in names)
        mdd_penalty = mdd * 2.0

        # 高相关性惩罚
        corr_penalty = 0.0
        for i, ni in enumerate(names):
            for j, nj in enumerate(names):
                if i < j:
                    c = corr_matrix.get(ni, {}).get(nj, 0.0)
                    if c > 0.7:
                        corr_penalty += (c - 0.7) * 0.5

        return sharpe - mdd_penalty - corr_penalty

    def lifecycle_advice(self, strategy_id: str, recent_performance: dict = None) -> dict:
        """F027 策略生命周期建议 — 启用/停用建议。

        基于近 30 天表现（收益、Sharpe、最大回撤）给出启用/停用/调整建议。

        Parameters
        ----------
        strategy_id : str
            策略 ID
        recent_performance : dict | None
            近期表现指标，包含 recent_return, recent_sharpe, recent_max_drawdown

        Returns
        -------
        dict
            strategy_id, advice, reason, metrics, suggestions
        """
        if recent_performance is None:
            recent_performance = {}

        recent_return = recent_performance.get("recent_return", 0.0)
        recent_sharpe = recent_performance.get("recent_sharpe", 0.0)
        recent_max_drawdown = recent_performance.get("recent_max_drawdown", 0.0)

        # 确保数值类型
        try:
            recent_return = float(recent_return)
        except (ValueError, TypeError):
            recent_return = 0.0
        try:
            recent_sharpe = float(recent_sharpe)
        except (ValueError, TypeError):
            recent_sharpe = 0.0
        try:
            recent_max_drawdown = abs(float(recent_max_drawdown))
        except (ValueError, TypeError):
            recent_max_drawdown = 0.0

        # ── 决策逻辑 ──
        advice = "enable"
        reason = ""
        suggestions: List[str] = []

        if recent_sharpe < 0.5 and recent_return < 0:
            advice = "disable"
            reason = (
                f"近30天夏普比率降至 {recent_sharpe:.2f}（低于0.5），"
                f"收益为 {recent_return:.2%}，策略表现持续恶化，建议停用。"
            )
            suggestions = [
                "暂停该策略，避免进一步亏损",
                "重新审视策略逻辑和市场适应性",
                "考虑更换策略参数或标的",
            ]
        elif recent_sharpe < 1.0 and recent_max_drawdown > 0.10:
            advice = "adjust"
            reason = (
                f"近30天夏普比率 {recent_sharpe:.2f}（低于1.0），"
                f"最大回撤 {recent_max_drawdown:.2%}（超过10%），建议调整仓位或参数。"
            )
            suggestions = [
                "考虑减少仓位大小",
                "检查策略参数是否需要优化",
                "增加止损保护机制",
            ]
        else:
            advice = "enable"
            if recent_sharpe >= 1.5:
                reason = (
                    f"近30天夏普比率 {recent_sharpe:.2f}，表现优秀，建议继续运行。"
                )
                suggestions = [
                    "维持当前策略配置",
                    "可适当增加仓位",
                ]
            else:
                reason = (
                    f"近30天夏普比率 {recent_sharpe:.2f}，收益 {recent_return:.2%}，"
                    f"策略运行正常，建议维持。"
                )
                suggestions = [
                    "维持当前策略配置",
                    "持续监控表现趋势",
                ]

        return {
            "strategy_id": strategy_id,
            "advice": advice,
            "reason": reason,
            "metrics": {
                "recent_return": round(recent_return, 4),
                "recent_sharpe": round(recent_sharpe, 2),
                "recent_max_drawdown": round(recent_max_drawdown, 4),
            },
            "suggestions": suggestions,
        }

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
