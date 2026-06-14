# -*- coding: utf-8 -*-
"""F026 AI 动态风控 Agent — 基于市场环境自适应调整风控参数"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import numpy as np


class MarketEnvironment(Enum):
    """市场环境"""
    BULL = "bull"            # 牛市 — 放宽风控
    BEAR = "bear"            # 熊市 — 收紧风控
    SIDEWAYS = "sideways"    # 震荡 — 中等风控
    CRASH = "crash"          # 暴跌 — 极端保守


@dataclass
class DynamicRiskParams:
    """可动态调整的风控参数"""
    max_position_pct: float = 0.30       # 单只股票最大仓位
    max_total_position_pct: float = 0.90 # 总仓位上限
    max_daily_loss_pct: float = 0.02     # 单日最大亏损
    max_drawdown_pct: float = 0.15       # 最大回撤熔断
    max_buy_amount_pct: float = 0.10     # 单笔最大买入金额
    order_rate_limit: int = 10           # 每分钟最大下单数


@dataclass
class RiskAdjustment:
    """风控参数调整记录"""
    timestamp: datetime
    market_env: MarketEnvironment
    original_params: dict
    adjusted_params: dict
    reason: str


class MarketEnvDetector:
    """
    检测当前市场环境。

    判断逻辑：
    - 暴跌: 单日跌幅 < -5% 或 3 日累计 < -10%
    - 牛市: 价格 > MA(200) AND MA(20) > MA(60)
    - 熊市: 价格 < MA(200) AND MA(20) < MA(60)
    - 震荡: 其他情况
    """

    def __init__(self, ma_long: int = 200, ma_mid: int = 60, ma_short: int = 20):
        self.ma_long = ma_long
        self.ma_mid = ma_mid
        self.ma_short = ma_short

    def _ma(self, data: np.ndarray, period: int) -> Optional[float]:
        """计算移动平均"""
        if len(data) < period:
            return None
        return float(np.mean(data[-period:]))

    def detect(self, close: np.ndarray,
               benchmark: Optional[np.ndarray] = None) -> MarketEnvironment:
        """
        检测市场环境。

        Parameters
        ----------
        close : np.ndarray
            标的收盘价
        benchmark : np.ndarray, optional
            基准（如沪深 300）收盘价

        Returns
        -------
        MarketEnvironment
        """
        if len(close) < 10:
            return MarketEnvironment.SIDEWAYS

        # 1. 暴跌检测（优先）
        if self._is_crash(close):
            return MarketEnvironment.CRASH

        # 2. 均线系统判断
        ma_short = self._ma(close, self.ma_short)
        ma_mid = self._ma(close, self.ma_mid)
        ma_long = self._ma(close, self.ma_long)

        if ma_short is None or ma_mid is None or ma_long is None:
            return MarketEnvironment.SIDEWAYS

        current = float(np.mean(close[-self.ma_short:]))

        if benchmark is not None and len(benchmark) >= self.ma_long:
            bm_ma_long = np.mean(benchmark[-self.ma_long:])
            if bm_ma_long > 0 and current < bm_ma_long * 0.95:
                return MarketEnvironment.BEAR
            if bm_ma_long > 0 and current > bm_ma_long * 1.05:
                return MarketEnvironment.BULL

        if ma_long > 0 and current > ma_long * 1.02 and ma_short > ma_mid:
            return MarketEnvironment.BULL
        if ma_long > 0 and current < ma_long * 0.98 and ma_short < ma_mid:
            return MarketEnvironment.BEAR

        return MarketEnvironment.SIDEWAYS

    @staticmethod
    def _is_crash(data: np.ndarray) -> bool:
        """检测是否暴跌"""
        if len(data) < 3:
            return False
        # 单日跌幅 > 5%
        daily_returns = np.diff(data) / data[:-1]
        if np.any(daily_returns < -0.05):
            return True
        # 3 日累计跌幅 > 10%
        if len(data) >= 4:
            three_day_return = (data[-1] - data[-4]) / data[-4]
            if three_day_return < -0.10:
                return True
        return False


class DynamicRiskAdjuster:
    """
    根据市场环境动态调整风控参数。

    所有调整因子都是可审计的公开值，不是黑盒。
    """

    # 市场环境 → 参数调整因子
    ADJUSTMENT_FACTORS = {
        MarketEnvironment.BULL: {
            "max_position_pct": 1.33,      # 0.30 → 0.40
            "max_total_position_pct": 1.11, # 0.90 → 1.00
            "max_daily_loss_pct": 1.5,     # 0.02 → 0.03
            "max_drawdown_pct": 1.33,      # 0.15 → 0.20
            "max_buy_amount_pct": 1.25,    # 0.10 → 0.125
            "order_rate_limit": 1.5,       # 10 → 15
        },
        MarketEnvironment.BEAR: {
            "max_position_pct": 0.67,      # 0.30 → 0.20
            "max_total_position_pct": 0.67, # 0.90 → 0.60
            "max_daily_loss_pct": 0.5,     # 0.02 → 0.01
            "max_drawdown_pct": 0.67,      # 0.15 → 0.10
            "max_buy_amount_pct": 0.5,     # 0.10 → 0.05
            "order_rate_limit": 0.5,       # 10 → 5
        },
        MarketEnvironment.CRASH: {
            "max_position_pct": 0.33,      # 0.30 → 0.10
            "max_total_position_pct": 0.33, # 0.90 → 0.30
            "max_daily_loss_pct": 0.25,    # 0.02 → 0.005
            "max_drawdown_pct": 0.5,       # 0.15 → 0.075
            "max_buy_amount_pct": 0.2,     # 0.10 → 0.02
            "order_rate_limit": 0.1,       # 10 → 1
        },
        MarketEnvironment.SIDEWAYS: {
            # 无调整
            "max_position_pct": 1.0,
            "max_total_position_pct": 1.0,
            "max_daily_loss_pct": 1.0,
            "max_drawdown_pct": 1.0,
            "max_buy_amount_pct": 1.0,
            "order_rate_limit": 1.0,
        },
    }

    ENV_REASON_MAP = {
        MarketEnvironment.BULL: "市场处于上升趋势，放宽风控参数",
        MarketEnvironment.BEAR: "市场处于下降趋势，收紧风控参数",
        MarketEnvironment.SIDEWAYS: "市场震荡，维持标准风控参数",
        MarketEnvironment.CRASH: "市场暴跌，极端保守风控模式",
    }

    def adjust(self, base_params: DynamicRiskParams,
               market_env: MarketEnvironment) -> tuple[DynamicRiskParams, RiskAdjustment]:
        """
        根据市场环境调整风控参数。

        Returns
        -------
        (adjusted_params, adjustment_record)
        """
        factors = self.ADJUSTMENT_FACTORS.get(market_env, self.ADJUSTMENT_FACTORS[MarketEnvironment.SIDEWAYS])

        adjusted = DynamicRiskParams(
            max_position_pct=round(base_params.max_position_pct * factors["max_position_pct"], 4),
            max_total_position_pct=round(base_params.max_total_position_pct * factors["max_total_position_pct"], 4),
            max_daily_loss_pct=round(base_params.max_daily_loss_pct * factors["max_daily_loss_pct"], 4),
            max_drawdown_pct=round(base_params.max_drawdown_pct * factors["max_drawdown_pct"], 4),
            max_buy_amount_pct=round(base_params.max_buy_amount_pct * factors["max_buy_amount_pct"], 4),
            order_rate_limit=max(1, int(round(base_params.order_rate_limit * factors["order_rate_limit"]))),
        )

        original = {
            "max_position_pct": base_params.max_position_pct,
            "max_total_position_pct": base_params.max_total_position_pct,
            "max_daily_loss_pct": base_params.max_daily_loss_pct,
            "max_drawdown_pct": base_params.max_drawdown_pct,
            "max_buy_amount_pct": base_params.max_buy_amount_pct,
            "order_rate_limit": base_params.order_rate_limit,
        }

        record = RiskAdjustment(
            timestamp=datetime.now(),
            market_env=market_env,
            original_params=original,
            adjusted_params={
                "max_position_pct": adjusted.max_position_pct,
                "max_total_position_pct": adjusted.max_total_position_pct,
                "max_daily_loss_pct": adjusted.max_daily_loss_pct,
                "max_drawdown_pct": adjusted.max_drawdown_pct,
                "max_buy_amount_pct": adjusted.max_buy_amount_pct,
                "order_rate_limit": adjusted.order_rate_limit,
            },
            reason=self.ENV_REASON_MAP.get(market_env, ""),
        )

        return adjusted, record

    def apply_to_risk_manager(self, risk_manager, adjusted_params: DynamicRiskParams):
        """
        将调整后的参数应用到 RiskManager 实例。

        RiskManager 属性名与 DynamicRiskParams 对应：
        - max_position_pct → _max_position_pct
        - max_total_position_pct → _max_total_position_pct
        - max_daily_loss_pct → _max_daily_loss_pct
        - max_drawdown_pct → _max_drawdown_pct
        - max_buy_amount_pct → _max_buy_amount（转换为绝对值）
        - order_rate_limit → _max_orders_per_minute
        """
        risk_manager._max_position_pct = adjusted_params.max_position_pct
        risk_manager._max_total_position_pct = adjusted_params.max_total_position_pct
        risk_manager._max_daily_loss_pct = adjusted_params.max_daily_loss_pct
        risk_manager._max_drawdown_pct = adjusted_params.max_drawdown_pct
        risk_manager._max_orders_per_minute = adjusted_params.order_rate_limit


class AnomalyDetector:
    """
    检测异常交易模式。
    """

    def detect_order_flood(self, orders: list[dict]) -> bool:
        """
        检测频繁下单（同方向短时间密集）。

        如果 1 分钟内有超过 5 笔同方向订单，标记为异常。
        """
        if len(orders) < 6:
            return False

        timestamps = sorted([o.get("timestamp", datetime.now()) for o in orders])
        for i in range(len(timestamps) - 5):
            delta = (timestamps[i + 5] - timestamps[i]).total_seconds()
            if delta <= 60:
                return True
        return False

    def detect_large_order(self, order_value: float, avg_order_value: float,
                           threshold: float = 3.0) -> bool:
        """
        检测异常大额下单（> 3 倍平均）。
        """
        if avg_order_value <= 0:
            return False
        return order_value > avg_order_value * threshold

    def detect_same_direction_streak(self, orders: list[dict],
                                     streak: int = 5) -> bool:
        """
        检测同向连续下单。

        如果连续 N 笔订单为同一方向，标记为异常。
        """
        if len(orders) < streak:
            return False

        sides = [o.get("side", "") for o in orders]
        count = 1
        for i in range(1, len(sides)):
            if sides[i] == sides[i - 1]:
                count += 1
                if count >= streak:
                    return True
            else:
                count = 1
        return False


class CorrelationEntry:
    """相关性监控条目"""
    symbol: str
    returns: np.ndarray

    def __init__(self, symbol: str, returns: np.ndarray):
        self.symbol = symbol
        self.returns = returns


class CorrelationMonitor:
    """
    监控持仓标的相关性，防止过度集中。
    """

    def calculate_correlation_matrix(self, entries: list[CorrelationEntry]) -> dict:
        """
        计算持仓标的相关性矩阵。

        Returns
        -------
        dict — {(symbol1, symbol2): correlation_coefficient}
        """
        result = {}
        symbols = [e.symbol for e in entries]
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                r1 = entries[i].returns
                r2 = entries[j].returns
                # 对齐长度
                min_len = min(len(r1), len(r2))
                if min_len < 10:
                    result[(symbols[i], symbols[j])] = 0.0
                    continue
                corr = np.corrcoef(r1[:min_len], r2[:min_len])[0, 1]
                result[(symbols[i], symbols[j])] = round(float(corr), 4) if not np.isnan(corr) else 0.0
        return result

    def get_concentration_risk(self, entries: list[CorrelationEntry]) -> str:
        """
        判断持仓集中度风险。

        Returns
        -------
        "low" / "medium" / "high"
        """
        if len(entries) < 2:
            return "low"

        matrix = self.calculate_correlation_matrix(entries)
        max_corr = max(abs(v) for v in matrix.values()) if matrix else 0.0

        if max_corr > 0.8:
            return "high"
        if max_corr > 0.6:
            return "medium"
        return "low"


class RiskAgent:
    """
    AI 动态风控 Agent — 主入口。
    """

    def __init__(self):
        self._env_detector = MarketEnvDetector()
        self._adjuster = DynamicRiskAdjuster()
        self._anomaly = AnomalyDetector()
        self._correlation = CorrelationMonitor()
        self._adjustment_log: list[RiskAdjustment] = []

    def assess_and_adjust(self, close: np.ndarray, base_params: DynamicRiskParams,
                          benchmark: Optional[np.ndarray] = None) -> tuple[DynamicRiskParams, str]:
        """
        完整风控评估流程。
        1. 检测市场环境 2. 调整风控参数 3. 记录调整 4. 返回调整后的参数和原因
        """
        env = self._env_detector.detect(close, benchmark)
        adjusted, record = self._adjuster.adjust(base_params, env)
        self._adjustment_log.append(record)
        return adjusted, record.reason

    def check_anomalies(self, orders: list[dict]) -> list[str]:
        """
        运行所有异常检测，返回警告消息列表。
        """
        warnings = []

        if self._anomaly.detect_order_flood(orders):
            warnings.append("⚠️ 检测到频繁下单（1 分钟内 > 5 笔）")

        if len(orders) >= 2:
            avg_value = np.mean([o.get("value", 0) for o in orders[:-1]])
            last_value = orders[-1].get("value", 0)
            if self._anomaly.detect_large_order(last_value, avg_value):
                warnings.append(f"⚠️ 检测到异常大额下单 ({last_value:.0f} vs 平均 {avg_value:.0f})")

        if self._anomaly.detect_same_direction_streak(orders):
            warnings.append("⚠️ 检测到同向连续下单（连续 5 笔以上）")

        return warnings

    def assess_concentration(self, holdings: list[CorrelationEntry]) -> str:
        """
        评估持仓集中度风险
        """
        return self._correlation.get_concentration_risk(holdings)

    def get_risk_report(self) -> dict:
        """
        生成风控评估报告
        """
        return {
            "total_adjustments": len(self._adjustment_log),
            "recent_adjustments": [
                {
                    "timestamp": adj.timestamp.isoformat(),
                    "market_env": adj.market_env.value,
                    "reason": adj.reason,
                }
                for adj in self._adjustment_log[-10:]
            ],
        }
