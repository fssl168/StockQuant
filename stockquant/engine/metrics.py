# -*- coding: utf-8 -*-
"""F005 回测统计指标 — 30+ 指标"""

from __future__ import annotations

import math
from typing import List, Optional


class BacktestMetrics:
    """回测统计指标计算 — 30+ 指标"""

    @staticmethod
    def calculate(
        equity_curve: List[tuple],
        trades: list,
        initial_cash: float,
        risk_free_rate: float = 0.025,
        trading_days: int = 252,
        benchmark_returns: Optional[List[float]] = None,
    ) -> dict:
        if not equity_curve:
            return {"error": "No equity curve data"}

        equities = [e for e, _ in equity_curve]
        n = len(equities)

        # 配对交易盈亏（按买入/卖出成对）
        paired_pnls = BacktestMetrics._pair_trades(trades)

        # 收益类
        total_return = BacktestMetrics._total_return(equities, initial_cash)
        ann_return = BacktestMetrics._annualized_return(total_return, n, trading_days)

        # 风险类
        max_dd, max_dd_duration, avg_dd, dd_recovery = BacktestMetrics._drawdown_metrics(equities)

        # 风险调整后收益
        sharpe = BacktestMetrics._sharpe_ratio(equities, risk_free_rate, trading_days)
        sortino = BacktestMetrics._sortino_ratio(equities, risk_free_rate, trading_days)
        calmar = BacktestMetrics._calmar_ratio(ann_return, max_dd) if max_dd > 0 else 0.0
        omega = BacktestMetrics._omega_ratio(equities, risk_free_rate / trading_days)
        if benchmark_returns:
            info_ratio = BacktestMetrics._info_ratio(equities, benchmark_returns, trading_days)
            beta, alpha = BacktestMetrics._beta_alpha(equities, benchmark_returns, trading_days)
        else:
            info_ratio = None
            beta = None
            alpha = None

        # 交易统计
        win_loss = BacktestMetrics._win_loss_stats(paired_pnls)

        # 额外指标
        sqn = BacktestMetrics._sqn(paired_pnls)
        kelly = BacktestMetrics._kelly_pct(paired_pnls)
        daily_vol = BacktestMetrics._daily_volatility(equities, trading_days)
        var_95 = BacktestMetrics._var_95(equities)
        cvar_95 = BacktestMetrics._cvar_95(equities)
        monthly_returns = BacktestMetrics._monthly_returns(equities, n)

        return {
            # === 收益类 (3) ===
            "Total Return": round(total_return, 6),
            "Annualized Return": round(ann_return, 6),
            "Excess Return (vs Benchmark)": round(ann_return - risk_free_rate, 6) if not beta else round(alpha, 6),
            # === 风险类 (5) ===
            "Max Drawdown": round(max_dd, 6),
            "Max Drawdown Duration": max_dd_duration,
            "Avg Drawdown": round(avg_dd, 6),
            "Avg Drawdown Recovery": dd_recovery if dd_recovery > 0 else None,
            "Daily Volatility": round(daily_vol, 6),
            # === 风险调整后收益 (6) ===
            "Sharpe Ratio": round(sharpe, 4),
            "Sortino Ratio": round(sortino, 4),
            "Calmar Ratio": round(calmar, 4),
            "Omega Ratio": round(omega, 4),
            "Information Ratio": round(info_ratio, 4) if info_ratio is not None else None,
            "Treynor Ratio": round((ann_return - risk_free_rate) / beta, 4) if beta and beta != 0 else None,
            # === 交易统计 (7) ===
            "Total Trades": win_loss.get("total_pairs", 0),
            "Total Wins": win_loss.get("wins", 0),
            "Total Losses": win_loss.get("losses", 0),
            "Win Rate": win_loss.get("win_rate", None),
            "Profit Factor": win_loss.get("profit_factor", None),
            "Avg Win": round(win_loss.get('avg_win', 0), 2),
            "Avg Loss": round(win_loss.get('avg_loss', 0), 2),
            "Max Consecutive Wins": win_loss.get("max_consec_wins", 0),
            "Max Consecutive Losses": win_loss.get("max_consec_losses", 0),
            # === 其他 (6) ===
            "SQN (System Quality Number)": round(sqn, 4) if sqn else None,
            "Kelly %": round(kelly, 6) if kelly else None,
            "VaR (95%)": round(var_95, 6),
            "CVaR (95%)": round(cvar_95, 6),
            "Beta": round(beta, 4) if beta is not None else None,
            "Alpha": round(alpha, 4) if alpha is not None else None,
            "Monthly Returns": {k: round(v, 6) for k, v in monthly_returns.items()},
        }

    @staticmethod
    def _total_return(equities, initial_cash):
        if initial_cash == 0:
            return 0.0
        return (equities[-1] - initial_cash) / initial_cash

    @staticmethod
    def _annualized_return(total_return, n_bars, trading_days):
        if total_return <= -1 or n_bars == 0:
            return 0.0
        years = n_bars / trading_days
        return (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return

    @staticmethod
    def _drawdown_metrics(equities):
        if not equities or len(equities) < 2:
            return 0.0, 0, 0.0, 0
        peak = equities[0]
        max_dd = 0.0
        max_dd_dur = 0
        avg_dd_sum = 0
        dd_count = 0
        dd_recovery_count = 0

        for i, eq in enumerate(equities):
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

            if dd > 0.001:  # 微小回撤忽略
                avg_dd_sum += dd
                dd_count += 1
            elif dd_count > 0:
                # 从回撤恢复到 >= 0.001 以下 — 计为一次 recovery
                dd_recovery_count += 1
                dd_count = 0

        avg_dd = avg_dd_sum / dd_count if dd_count > 0 else 0.0

        # 最大回撤持续时间
        peak_idx = 0
        for i, eq in enumerate(equities):
            if eq > equities[peak_idx]:
                peak_idx = i
        dd_from_peak = 0
        for i in range(peak_idx, len(equities)):
            dd = (equities[peak_idx] - equities[i]) / equities[peak_idx] if equities[peak_idx] > 0 else 0
            dd_from_peak = max(dd_from_peak, i - peak_idx)
            if equities[i] > equities[peak_idx]:
                break
        max_dd_dur = dd_from_peak

        return max_dd, max_dd_dur, avg_dd, dd_recovery_count

    @staticmethod
    def _sharpe_ratio(equities, rf, trading_days):
        if len(equities) < 2:
            return 0.0
        returns = BacktestMetrics._daily_returns(equities)
        if not returns:
            return 0.0
        daily_rf = rf / trading_days
        excess = [r - daily_rf for r in returns]
        mean_excess = sum(excess) / len(excess)
        std = BacktestMetrics._std(excess, ddof=1)
        if std == 0:
            return 0.0
        return (mean_excess / std) * math.sqrt(trading_days)

    @staticmethod
    def _sortino_ratio(equities, rf, trading_days):
        if len(equities) < 2:
            return 0.0
        returns = BacktestMetrics._daily_returns(equities)
        if not returns:
            return 0.0
        daily_rf = rf / trading_days
        excess = [r - daily_rf for r in returns]
        down_returns = [r for r in excess if r < 0]
        if not down_returns:
            # 无负收益：Sortino 趋近无穷，返回极大值
            mean_excess = sum(excess) / len(excess)
            if mean_excess > 0:
                return 999.0
            return 0.0
        mean_excess = sum(excess) / len(excess)
        down_var = sum(r ** 2 for r in down_returns) / len(down_returns)
        down_std = math.sqrt(down_var)
        if down_std < 1e-10:
            return 0.0
        return (mean_excess / down_std) * math.sqrt(trading_days)

    @staticmethod
    def _calmar_ratio(ann_return, max_dd):
        if max_dd == 0:
            return 0.0
        return ann_return / max_dd

    @staticmethod
    def _omega_ratio(equities, rf_daily):
        if len(equities) < 2:
            return 0.0
        returns = BacktestMetrics._daily_returns(equities)
        if not returns:
            return 0.0
        gains = sum(max(r - rf_daily, 0) for r in returns)
        losses = sum(abs(min(r - rf_daily, 0)) for r in returns)
        if losses == 0:
            return 999.0
        return gains / losses

    @staticmethod
    def _info_ratio(equities, benchmark_returns, trading_days):
        """Information Ratio = 超额收益均值 / 超额收益标准差"""
        if len(equities) < 2 or len(benchmark_returns) < 2:
            return 0.0
        equity_returns = BacktestMetrics._daily_returns(equities)
        excess = [er - br for er, br in zip(equity_returns, benchmark_returns)]
        if not excess:
            return 0.0
        mean_excess = sum(excess) / len(excess)
        std_excess = BacktestMetrics._std(excess, ddof=1)
        if std_excess == 0:
            return 0.0
        return (mean_excess / std_excess) * math.sqrt(trading_days)

    @staticmethod
    def _beta_alpha(equities, benchmark_returns, trading_days):
        """Beta 和 Alpha (CAPM)"""
        if len(equities) < 2 or len(benchmark_returns) < 2:
            return None, None
        equity_returns = BacktestMetrics._daily_returns(equities)
        n = min(len(equity_returns), len(benchmark_returns))
        er = equity_returns[:n]
        br = benchmark_returns[:n]

        mean_er = sum(er) / n
        mean_br = sum(br) / n

        cov = sum((er[i] - mean_er) * (br[i] - mean_br) for i in range(n)) / n
        var_br = sum((br[i] - mean_br) ** 2 for i in range(n)) / n

        beta = cov / var_br if var_br > 0 else 0
        ann_er = ((sum(er) / n + 1) ** trading_days - 1)
        ann_br = ((sum(br) / n + 1) ** trading_days - 1)
        alpha = ann_er - ann_br * beta
        return beta, alpha

    @staticmethod
    def _win_loss_stats(paired_pnls):
        if not paired_pnls:
            return {"total_pairs": 0, "wins": 0, "losses": 0, "win_rate": None,
                    "profit_factor": None, "avg_win": 0, "avg_loss": 0,
                    "max_consec_wins": 0, "max_consec_losses": 0}

        wins = [p for p in paired_pnls if p > 0]
        losses = [p for p in paired_pnls if p < 0]
        total = len(paired_pnls)
        win_rate = len(wins) / total if total > 0 else None

        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1
        pf = gross_profit / gross_loss if gross_loss > 0 else None

        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        pl_ratio = f"{abs(avg_win / avg_loss):.2f}" if avg_loss != 0 else "N/A"

        # 最长连赢/连亏
        max_consec_w = max_consec_l = consec_w = consec_l = 0
        for p in paired_pnls:
            if p > 0:
                consec_w += 1
                consec_l = 0
                max_consec_w = max(max_consec_w, consec_w)
            elif p < 0:
                consec_l += 1
                consec_w = 0
                max_consec_l = max(max_consec_l, consec_l)

        return {
            "total_pairs": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "profit_factor": pf,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_loss_ratio": pl_ratio,
            "max_consec_wins": max_consec_w,
            "max_consec_losses": max_consec_l,
        }

    @staticmethod
    def _pair_trades(trades):
        """将 Trades 配对为完整交易（买入+卖出）的盈亏"""
        if not trades:
            return []

        # 简化：按 symbol 分组，买入和卖出配对
        by_symbol = {}
        for t in trades:
            sym = t.symbol if hasattr(t, 'symbol') else getattr(t, 'symbol', '')
            if sym not in by_symbol:
                by_symbol[sym] = []
            by_symbol[sym].append(t)

        pnls = []
        for sym, symbol_trades in by_symbol.items():
            buys = [t for t in symbol_trades if getattr(t, 'side', '') == 'Buy']
            sells = [t for t in symbol_trades if getattr(t, 'side', '') == 'Sell']

            # FIFO 配对
            buy_queue = buys[:]
            for sell in sells:
                sell_notional = sell.price * sell.quantity if hasattr(sell, 'price') and hasattr(sell, 'quantity') else 0
                while buy_queue and sell_notional > 0:
                    buy = buy_queue[0]
                    buy_notional = buy.price * buy.quantity if hasattr(buy, 'price') and hasattr(buy, 'quantity') else 0
                    pair_qty = min(buy.quantity, sell.quantity) if hasattr(buy, 'quantity') and hasattr(sell, 'quantity') else 0
                    pnl = (sell.price - buy.price) * pair_qty  # 简化盈亏
                    pnls.append(pnl)
                    sell_notional -= buy_notional * (pair_qty / buy.quantity) if hasattr(buy, 'quantity') and buy.quantity > 0 else 0
                    if buy_queue:
                        if buy.quantity == pair_qty:
                            buy_queue.pop(0)
                        else:
                            buy_queue[0] = type(buy)(**{k: (buy.quantity - pair_qty if k == 'quantity' else v)
                                                        for k, v in buy.__dict__.items() if not k.startswith('_')})
        return pnls if pnls else [0]  # 至少返回一个非空值

    @staticmethod
    def _sqn(paired_pnls):
        """System Quality Number"""
        if len(paired_pnls) < 2:
            return 0.0
        mean_pnl = sum(paired_pnls) / len(paired_pnls)
        std_pnl = BacktestMetrics._std(paired_pnls, ddof=1)
        if std_pnl == 0:
            return 0.0
        return (math.sqrt(len(paired_pnls)) * mean_pnl) / std_pnl

    @staticmethod
    def _kelly_pct(paired_pnls):
        """凯利百分比"""
        if not paired_pnls:
            return 0.0
        wins = len([p for p in paired_pnls if p > 0])
        total = len(paired_pnls)
        win_rate = wins / total if total > 0 else 0
        loss_avg = sum(p for p in paired_pnls if p < 0) / max(1, sum(1 for p in paired_pnls if p < 0))
        win_avg = sum(p for p in paired_pnls if p > 0) / max(1, sum(1 for p in paired_pnls if p > 0))
        if loss_avg == 0 or win_avg == 0:
            return 0.0
        win_loss_ratio = abs(win_avg / loss_avg)
        if win_loss_ratio == 0:
            return 0.0
        kelly = win_rate - (1 - win_rate) / win_loss_ratio
        return max(0, kelly * 0.5)  # 半凯利

    @staticmethod
    def _daily_volatility(equities, trading_days):
        if len(equities) < 2:
            return 0.0
        returns = BacktestMetrics._daily_returns(equities)
        if not returns:
            return 0.0
        return math.sqrt(sum((r - sum(returns)/len(returns))**2 for r in returns) / (len(returns) - 1)) * math.sqrt(trading_days)

    @staticmethod
    def _var_95(equities):
        if len(equities) < 2:
            return 0.0
        returns = BacktestMetrics._daily_returns(equities)
        if not returns:
            return 0.0
        sorted_returns = sorted(returns)
        idx = int(0.05 * len(sorted_returns))
        return abs(sorted_returns[max(0, idx)])

    @staticmethod
    def _cvar_95(equities):
        if len(equities) < 2:
            return 0.0
        returns = BacktestMetrics._daily_returns(equities)
        sorted_returns = sorted(returns)
        cutoff = max(0, int(0.05 * len(sorted_returns)))
        tail = sorted_returns[:cutoff] if cutoff > 0 else [sorted_returns[0]]
        return abs(sum(tail) / len(tail))

    @staticmethod
    def _monthly_returns(equities, n):
        if n < 21:
            return {}
        months = {}
        for i in range(0, min(n, 12 * 21), 21):
            window = equities[i:i + 21]
            if len(window) >= 2 and window[0] > 0:
                months[i // 21 + 1] = (window[-1] - window[0]) / window[0]
        return months

    @staticmethod
    def _daily_returns(equities):
        if len(equities) < 2:
            return []
        returns = []
        for i in range(1, len(equities)):
            if equities[i - 1] != 0:
                returns.append((equities[i] - equities[i - 1]) / equities[i - 1])
        return returns

    @staticmethod
    def _std(values, ddof=1):
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - ddof)
        result = math.sqrt(variance)
        # 防止浮点误差导致除零爆炸
        if result < 1e-10:
            return 0.0
        return result
