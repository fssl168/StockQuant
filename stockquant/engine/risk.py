# -*- coding: utf-8 -*-
"""F009 风险管理模块 — 拦截器模式"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from stockquant.models.order import Order, OrderSide
from stockquant.models.position import Position

logger = logging.getLogger("stockquant.engine.risk")


class RiskManager:
    """
    风险管理模块。

    在订单到达 Broker 之前自动检查风控规则，拦截不合规订单。
    """

    def __init__(
        self,
        max_position_pct: float = 0.3,
        max_buy_amount: float = 500_000.0,
        max_total_position_pct: float = 0.9,
        max_daily_loss_pct: float = 0.02,
        max_drawdown_pct: float = 0.15,
        max_orders_per_minute: int = 10,
        global_circuit_breaker_pct: float = 0.05,
    ):
        self._max_position_pct = max_position_pct
        self._max_buy_amount = max_buy_amount
        self._max_total_position_pct = max_total_position_pct
        self._max_daily_loss_pct = max_daily_loss_pct
        self._max_drawdown_pct = max_drawdown_pct
        self._max_orders_per_minute = max_orders_per_minute
        self._global_circuit_breaker_pct = global_circuit_breaker_pct

        self._order_timestamps: List[float] = []
        self._peak_equity: float = 0.0
        self._daily_start_equity: Optional[float] = None
        self._halted = False
        self._halt_reason = ""

    def set_daily_start(self, equity: float):
        """每个交易日开始时调用"""
        self._daily_start_equity = equity
        self._peak_equity = equity
        self._order_timestamps.clear()

    def check(self, order: Order, equity: float, positions: Dict[str, Position],
              total_equity: float = 0) -> Tuple[bool, str]:
        """
        检查订单是否通过风控。

        Returns
        -------
        (is_valid, reason)
        """
        if self._halted:
            return False, f"Halted: {self._halt_reason}"

        # 1. 订单频率限制
        valid, reason = self._check_order_rate(order)
        if not valid:
            return False, reason

        # 2. 单只股票仓位限制
        valid, reason = self._check_position_pct(order, positions, total_equity)
        if not valid:
            return False, reason

        # 3. 单只股票最大买入金额
        valid, reason = self._check_buy_amount(order)
        if not valid:
            return False, reason

        # 4. 总仓位上限
        valid, reason = self._check_total_position_pct(positions, total_equity)
        if not valid:
            return False, reason

        # 5. 单日最大亏损
        valid, reason = self._check_daily_loss(equity)
        if not valid:
            return False, reason

        # 6. 累计最大回撤熔断
        valid, reason = self._check_max_drawdown(equity)
        if not valid:
            return False, reason

        # 7. 全局熔断
        valid, reason = self._check_global_circuit_breaker(equity)
        if not valid:
            return False, reason

        return True, ""

    def _check_order_rate(self, order: Order) -> Tuple[bool, str]:
        now = datetime.now().timestamp()
        cutoff = now - 60
        self._order_timestamps = [t for t in self._order_timestamps if t > cutoff]
        if len(self._order_timestamps) >= self._max_orders_per_minute:
            return False, f"Order rate limit: {len(self._order_timestamps)}/{self._max_orders_per_minute} per min"
        self._order_timestamps.append(now)
        return True, ""

    def _check_position_pct(self, order: Order, positions: Dict[str, Position],
                            total_equity: float) -> Tuple[bool, str]:
        if order.side != OrderSide.BUY or total_equity <= 0:
            return True, ""
        pos = positions.get(order.symbol)
        current_mv = pos.market_value if pos and pos.quantity > 0 else 0
        new_notional = order.price * order.quantity
        new_pct = (current_mv + new_notional) / total_equity
        if new_pct > self._max_position_pct:
            return False, f"Position {order.symbol} would be {new_pct:.1%} > {self._max_position_pct:.0%}"
        return True, ""

    def _check_buy_amount(self, order: Order) -> Tuple[bool, str]:
        if order.side != OrderSide.BUY:
            return True, ""
        notional = order.price * order.quantity
        if notional > self._max_buy_amount:
            return False, f"Buy amount {notional:.0f} > {self._max_buy_amount:.0f}"
        return True, ""

    def _check_total_position_pct(self, positions: Dict[str, Position],
                                  total_equity: float) -> Tuple[bool, str]:
        if total_equity <= 0:
            return True, ""
        total_mv = sum(p.market_value for p in positions.values())
        pct = total_mv / total_equity
        if pct > self._max_total_position_pct:
            return False, f"Total position {pct:.1%} > {self._max_total_position_pct:.0%}"
        return True, ""

    def _check_daily_loss(self, equity: float) -> Tuple[bool, str]:
        if self._daily_start_equity is None or self._daily_start_equity <= 0:
            return True, ""
        loss_pct = (self._daily_start_equity - equity) / self._daily_start_equity
        if loss_pct >= self._max_daily_loss_pct:
            self.halt(f"Daily loss {loss_pct:.2%} >= {self._max_daily_loss_pct:.2%}")
            return False, f"Daily loss limit hit: {loss_pct:.2%}"
        return True, ""

    def _check_max_drawdown(self, equity: float) -> Tuple[bool, str]:
        if equity > self._peak_equity:
            self._peak_equity = equity
        if self._peak_equity <= 0:
            return True, ""
        dd = (self._peak_equity - equity) / self._peak_equity
        if dd >= self._max_drawdown_pct:
            self.halt(f"Drawdown {dd:.2%} >= {self._max_drawdown_pct:.2%}")
            return False, f"Max drawdown limit hit: {dd:.2%}"
        return True, ""

    def _check_global_circuit_breaker(self, equity: float) -> Tuple[bool, str]:
        """全局熔断：市场单日跌幅超过 5% 暂停所有交易"""
        if self._daily_start_equity is None or self._daily_start_equity <= 0:
            return True, ""
        drop = (self._daily_start_equity - equity) / self._daily_start_equity
        if drop >= self._global_circuit_breaker_pct:
            self.halt(f"Global circuit breaker: drop {drop:.2%} >= {self._global_circuit_breaker_pct:.2%}")
            return False, "Global circuit breaker triggered"
        return True, ""

    def halt(self, reason: str):
        self._halted = True
        self._halt_reason = reason
        logger.critical(f"Circuit breaker TRIGGERED: {reason}")

    def resume(self):
        self._halted = False
        self._halt_reason = ""
        logger.info("Trading resumed")

    @property
    def is_halted(self) -> bool:
        return self._halted
