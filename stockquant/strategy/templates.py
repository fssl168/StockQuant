# -*- coding: utf-8 -*-
"""F014 内置策略模板库 — 7 套开箱即用策略"""

from stockquant.strategy.base import BaseStrategy
from stockquant.engine.sizer import FixedFractionSizer


# ========================================================================
# 1. Dual MACrossoverStrategy（保留已有）
# ========================================================================

class DualMACrossoverStrategy(BaseStrategy):
    """
    双均线交叉策略。

    EMA(5) 上穿 EMA(20) → 买入
    EMA(5) 下穿 EMA(20) → 卖出
    """

    name = "Dual MA Crossover"
    parameters = {
        "fast_period": 5,
        "slow_period": 20,
        "position_size": 0.95,
    }

    def on_start(self):
        self._sizer = FixedFractionSizer(self.parameters["position_size"])
        self._last_cross = None
        # 价格历史累积
        self._price_history = {}
        self._trade_count = 0

    def on_bar(self, bars):
        for symbol, bar in bars.items():
            # 累积价格历史
            if symbol not in self._price_history:
                self._price_history[symbol] = []
            self._price_history[symbol].append(bar.close)

            # 取最近 N 根收盘价
            closes = self._price_history[symbol]
            fast_p = self.parameters["fast_period"]
            slow_p = self.parameters["slow_period"]

            if len(closes) < slow_p:
                continue

            fast_ind = self.EMA(closes, fast_p)
            slow_ind = self.EMA(closes, slow_p)

            # Debug print
            if len(closes) == slow_p or len(closes) % 50 == 0:
                print(f"DEBUG strategy: symbol={symbol}, closes={len(closes)}, "
                      f"fast[-1]={fast_ind[-1]:.2f}, slow[-1]={slow_ind[-1]:.2f}")

            # 金叉
            if fast_ind[-1] > slow_ind[-1] and fast_ind[-2] <= slow_ind[-2]:
                if self._last_cross != "golden":
                    self._last_cross = "golden"
                    qty = self._sizer.calculate(
                        self.cash, bar.close, self.account.total_equity
                    )
                    if qty > 0:
                        self.order_market(bar, qty)
                        self._trade_count += 1
                        print(f"DEBUG: Order placed (trade #{self._trade_count}), qty={qty}")
                        self.log(f"GOLDEN CROSS: BUY {symbol}")

            # 死叉
            elif fast_ind[-1] < slow_ind[-1] and fast_ind[-2] >= slow_ind[-2]:
                if self._last_cross != "death":
                    self._last_cross = "death"
                    self.close_all()
                    self._trade_count += 1
                    print(f"DEBUG: Close all placed (trade #{self._trade_count})")
                    self.log("DEATH CROSS: SELL ALL")

    def on_finish(self):
        """回测结束时打印交易计数"""
        print(f"DEBUG on_finish: total trades attempted={self._trade_count}")


# ========================================================================
# 2. RSIReversalStrategy（保留已有）
# ========================================================================

class RSIReversalStrategy(BaseStrategy):
    """
    RSI 超买超卖反转策略。

    RSI < 30（超卖）→ 买入
    RSI > 70（超买）→ 卖出
    """

    name = "RSI Reversal"
    parameters = {
        "rsi_period": 14,
        "oversold": 30,
        "overbought": 70,
    }

    def on_start(self):
        self._last_signal = None
        self._price_history = {}

    def on_bar(self, bars):
        for symbol, bar in bars.items():
            if symbol not in self._price_history:
                self._price_history[symbol] = []
            self._price_history[symbol].append(bar.close)

            closes = self._price_history[symbol]
            if len(closes) < self.parameters["rsi_period"]:
                return

            rsi = self.RSI(closes, self.parameters["rsi_period"])
            current_rsi = rsi[-1]

            if current_rsi < self.parameters["oversold"] and self._last_signal != "buy":
                self._last_signal = "buy"
                self.order_market(bar, 100)
                self.log(f"RSI oversold ({current_rsi:.1f}): BUY {symbol}")

            elif current_rsi > self.parameters["overbought"] and self._last_signal != "sell":
                self._last_signal = "sell"
                self.order_sell(bar, 100)
                self.log(f"RSI overbought ({current_rsi:.1f}): SELL {symbol}")


# ========================================================================
# 3. BollingerBounceStrategy（保留已有）
# ========================================================================

class BollingerBounceStrategy(BaseStrategy):
    """
    布林带反弹策略。

    价格触及下轨 → 买入
    价格触及上轨 → 卖出
    """

    name = "Bollinger Bounce"
    parameters = {
        "boll_period": 20,
        "boll_std": 2,
    }

    def on_start(self):
        self._last_signal = None
        self._price_history = {}

    def on_bar(self, bars):
        for symbol, bar in bars.items():
            if symbol not in self._price_history:
                self._price_history[symbol] = []
            self._price_history[symbol].append(bar.close)

            closes = self._price_history[symbol]
            if len(closes) < self.parameters["boll_period"]:
                return

            boll = self.BOLL(closes, self.parameters["boll_period"])
            upper = boll["upperband"][-1]
            lower = boll["lowerband"][-1]

            if bar.close <= lower and self._last_signal != "buy":
                self._last_signal = "buy"
                self.order_market(bar, 100)
                self.log(f"Price hit lower BB ({lower:.2f}): BUY {symbol}")

            elif bar.close >= upper and self._last_signal != "sell":
                self._last_signal = "sell"
                self.close_all()
                self.log(f"Price hit upper BB ({upper:.2f}): SELL {symbol}")


# ========================================================================
# 4. MACDDivergenceStrategy（新增）
# ========================================================================

class MACDDivergenceStrategy(BaseStrategy):
    """
    MACD 背离策略。

    价格创新低但 MACD 未创新低 → 底背离 → 买入
    价格创新高但 MACD 未创新高 → 顶背离 → 卖出
    """

    name = "MACD Divergence"
    parameters = {
        "fast_period": 12,
        "slow_period": 26,
        "signal_period": 9,
        "lookback": 20,  # 背离检测回溯窗口
    }

    def on_start(self):
        self._price_history = {}
        self._macd_history = {}
        self._last_signal = None

    def on_bar(self, bars):
        for symbol, bar in bars.items():
            if symbol not in self._price_history:
                self._price_history[symbol] = []
                self._macd_history[symbol] = []
            self._price_history[symbol].append(bar.close)

            closes = self._price_history[symbol]
            macd_params = self.parameters
            min_needed = max(macd_params["slow_period"] + macd_params["signal_period"], 30)

            if len(closes) < min_needed:
                return

            macd = self.MACD(
                closes,
                fast=macd_params["fast_period"],
                slow=macd_params["slow_period"],
                signal=macd_params["signal_period"],
            )
            self._macd_history[symbol].append({
                "dif": macd["dif"][-1],
                "dea": macd["dea"][-1],
                "hist": macd["macd"][-1],
            })

            # 背离检测
            lb = macd_params["lookback"]
            prices = closes[-lb:]
            macds = self._macd_history[symbol][-lb:]

            if len(prices) < 5 or len(macds) < 5:
                return

            # 底背离：价格新低 + MACD 未新低
            price_min_idx = prices.index(min(prices))
            macd_min_idx = min(range(len(macds)), key=lambda i: macds[i]["dif"])

            if (prices[price_min_idx] < prices[price_min_idx - 1] and
                    macds[macd_min_idx]["dif"] > macds[macd_min_idx - 1]["dif"] and
                    self._last_signal != "buy"):
                self._last_signal = "buy"
                self.order_market(bar, 100)
                self.log(f"MACD BULLISH DIVERGENCE detected: BUY {symbol}")

            # 顶背离：价格新高 + MACD 未新高
            price_max_idx = prices.index(max(prices))
            macd_max_idx = max(range(len(macds)), key=lambda i: macds[i]["dif"])

            if (prices[price_max_idx] > prices[price_max_idx - 1] and
                    macds[macd_max_idx]["dif"] < macds[macd_max_idx - 1]["dif"] and
                    self._last_signal != "sell"):
                self._last_signal = "sell"
                self.close_all()
                self.log("MACD BEARISH DIVERGENCE detected: SELL ALL")


# ========================================================================
# 5. DualThrustStrategy（新增）
# ========================================================================

class DualThrustStrategy(BaseStrategy):
    """
    Dual Thrust 突破策略。

    基于过去 N 日最高/最低价计算上下轨，突破上轨买入，跌破下轨卖出。
    """

    name = "Dual Thrust"
    parameters = {
        "lookback": 4,  # 回溯天数
        "k1": 0.5,      # 上轨系数
        "k2": 0.5,      # 下轨系数
    }

    def on_start(self):
        self._price_history = {}
        self._last_signal = None

    def on_bar(self, bars):
        for symbol, bar in bars.items():
            if symbol not in self._price_history:
                self._price_history[symbol] = []
            self._price_history[symbol].append(bar)

            hist = self._price_history[symbol]
            lb = self.parameters["lookback"]

            if len(hist) < lb + 1:
                return

            # 计算范围（H/N - L/N + C/N - O/N）
            range_values = []
            for h in hist[-lb:]:
                h_val = max(h.high, h.close - h.open)
                l_val = min(h.low, h.open - h.close)
                range_values.append(h_val - l_val)

            if not range_values:
                return

            h = max(range_values)
            o = max(abs(hist[-1].open - hist[-lb].close), 0)
            c = hist[-1].close
            base = max(h - o, c - min(bar.low for bar in hist[-lb:]))

            if base <= 0:
                return

            k1 = self.parameters["k1"]
            k2 = self.parameters["k2"]

            upper_bound = c + k1 * base
            lower_bound = c - k2 * base

            # 突破上轨买入
            if bar.close > upper_bound and self._last_signal != "buy":
                if bar.close > upper_bound and self._last_signal != "buy":
                    self._last_signal = "buy"
                    self.order_market(bar, 100)
                    self.log(f"DUAL THRUST BREAKOUT UP: BUY {symbol} @ {bar.close:.2f}")

            # 跌破下轨卖出
            elif bar.close < lower_bound and self._last_signal != "sell":
                self._last_signal = "sell"
                self.close_all()
                self.log("DUAL THRUST BREAKDOWN: SELL ALL")


# ========================================================================
# 6. MeanReversionStrategy（新增）
# ========================================================================

class MeanReversionStrategy(BaseStrategy):
    """
    均值回归策略。

    价格偏离均线超过 2 个标准差 → 反向交易
    """

    name = "Mean Reversion"
    parameters = {
        "ma_period": 20,
        "std_threshold": 2.0,
        "position_size": 0.3,
    }

    def on_start(self):
        self._price_history = {}
        self._last_signal = None
        self._sizer = FixedFractionSizer(self.parameters["position_size"])

    def on_bar(self, bars):
        for symbol, bar in bars.items():
            if symbol not in self._price_history:
                self._price_history[symbol] = []
            self._price_history[symbol].append(bar.close)

            closes = self._price_history[symbol]
            period = self.parameters["ma_period"]

            if len(closes) < period + 1:
                return

            # 计算均值和标准差
            recent = closes[-period:]
            ma = sum(recent) / len(recent)
            variance = sum((x - ma) ** 2 for x in recent) / (len(recent) - 1)
            std = variance ** 0.5

            if std == 0:
                return

            threshold = self.parameters["std_threshold"]

            # 价格低于下轨 → 买入（预期回归均值）
            if bar.close < ma - threshold * std and self._last_signal != "buy":
                self._last_signal = "buy"
                qty = self._sizer.calculate(
                    self.cash, bar.close, self.account.total_equity
                )
                if qty > 0:
                    self.order_market(bar, qty)
                self.log(f"MEAN REVERSION BUY: price {bar.close:.2f} < MA-{ma:.2f} (2σ)")

            # 价格高于上轨 → 卖出（预期回归均值）
            elif bar.close > ma + threshold * std and self._last_signal != "sell":
                self._last_signal = "sell"
                self.close_all()
                self.log(f"MEAN REVERSION SELL: price {bar.close:.2f} > MA-{ma:.2f} (2σ)")

            # 回归到均值附近平仓
            elif abs(bar.close - ma) < std * 0.5 and self._last_signal == "buy":
                self.close_all()
                self._last_signal = None
                self.log("MEAN REVERSION EXIT: price converged to MA")


# ========================================================================
# 7. MomentumStrategy（新增）
# ========================================================================

class MomentumStrategy(BaseStrategy):
    """
    动量策略。

    ROC > 0 且持续放大 + MACD 金叉 → 买入
    ROC < 0 且 MACD 死叉 → 卖出
    """

    name = "Momentum"
    parameters = {
        "roc_period": 10,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "roc_threshold": 5.0,  # ROC 百分比阈值
    }

    def on_start(self):
        self._price_history = {}
        self._last_signal = None

    def on_bar(self, bars):
        for symbol, bar in bars.items():
            if symbol not in self._price_history:
                self._price_history[symbol] = []
            self._price_history[symbol].append(bar.close)

            closes = self._price_history[symbol]

            # ROC 计算
            roc_period = self.parameters["roc_period"]
            if len(closes) < roc_period + 1:
                return

            roc_val = (closes[-1] - closes[-roc_period - 1]) / closes[-roc_period - 1] * 100

            # MACD 计算
            macd_fast = self.parameters["macd_fast"]
            macd_slow = self.parameters["macd_slow"]
            macd_signal = self.parameters["macd_signal"]
            min_needed = macd_slow + macd_signal

            if len(closes) < min_needed:
                return

            macd = self.MACD(
                closes,
                fast=macd_fast,
                slow=macd_slow,
                signal=macd_signal,
            )

            dif = macd["dif"][-1]
            prev_dif = macd["dif"][-2]
            dea = macd["dea"][-1]
            prev_dea = macd["dea"][-2]

            roc_threshold = self.parameters["roc_threshold"]

            # 买入条件：ROC 超过阈值 + MACD 金叉
            if (roc_val > roc_threshold and
                    prev_dif <= prev_dea and dif > dea and
                    self._last_signal != "buy"):
                self._last_signal = "buy"
                self.order_market(bar, 100)
                self.log(f"MOMENTUM BUY: ROC={roc_val:.2f}%, MACD golden cross")

            # 卖出条件：ROC < 0 + MACD 死叉
            elif (roc_val < 0 and
                  prev_dif >= prev_dea and dif < dea and
                  self._last_signal != "sell"):
                self._last_signal = "sell"
                self.close_all()
                self.log(f"MOMENTUM SELL: ROC={roc_val:.2f}%, MACD death cross")
