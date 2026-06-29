# -*- coding: utf-8 -*-
"""F012 模拟盘账户管理器 — 虚拟资金、持仓跟踪、费用计算

管理模拟盘/仿真盘的全局账户状态，包括：
- 虚拟资金账户（现金、冻结资金、可用资金）
- 持仓跟踪（数量、成本价、市值、盈亏）
- 费用计算（手续费、印花税、佣金）
- 盈亏统计
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# 费用计算
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CommissionConfig:
    """手续费配置"""
    commission_rate: float = 0.00025    # 佣金费率（万分之二点五）
    stamp_tax_rate: float = 0.0005      # 印花税率（卖出，千分之五）
    transfer_fee_rate: float = 0.00001  # 过户费率（十万分之一）
    regulatory_fee_rate: float = 0.000002  # 监管费率（十万分之二）
    min_commission: float = 5.0         # 最低佣金（元）


class FeeCalculator:
    """A 股费用计算器

    费用项目:
    - 佣金：双向收取，最低 5 元
    - 印花税：仅卖出收取，税率 0.05%
    - 过户费：双向收取，税率 0.001%
    - 监管费：双向收取，税率 0.0002%
    """

    def __init__(self, config: Optional[CommissionConfig] = None):
        self._config = config or CommissionConfig()

    @property
    def config(self) -> CommissionConfig:
        return self._config

    def calculate_buy_cost(self, price: float, quantity: float) -> Dict[str, float]:
        """计算买入总费用

        Returns:
            {
                "commission": float,
                "transfer_fee": float,
                "regulatory_fee": float,
                "total_fee": float,
                "notional": float,
            }
        """
        notional = price * quantity
        commission = max(notional * self._config.commission_rate, self._config.min_commission)
        transfer_fee = notional * self._config.transfer_fee_rate
        regulatory_fee = notional * self._config.regulatory_fee_rate
        total_fee = commission + transfer_fee + regulatory_fee

        return {
            "notional": round(notional, 2),
            "commission": round(commission, 4),
            "transfer_fee": round(transfer_fee, 4),
            "regulatory_fee": round(regulatory_fee, 4),
            "total_fee": round(total_fee, 4),
            "buy_total": round(notional + total_fee, 2),
        }

    def calculate_sell_cost(self, price: float, quantity: float) -> Dict[str, float]:
        """计算卖出总费用

        Returns:
            {
                "commission": float,
                "stamp_tax": float,
                "transfer_fee": float,
                "regulatory_fee": float,
                "total_fee": float,
                "notional": float,
            }
        """
        notional = price * quantity
        commission = max(notional * self._config.commission_rate, self._config.min_commission)
        stamp_tax = notional * self._config.stamp_tax_rate
        transfer_fee = notional * self._config.transfer_fee_rate
        regulatory_fee = notional * self._config.regulatory_fee_rate
        total_fee = commission + stamp_tax + transfer_fee + regulatory_fee

        return {
            "notional": round(notional, 2),
            "commission": round(commission, 4),
            "stamp_tax": round(stamp_tax, 4),
            "transfer_fee": round(transfer_fee, 4),
            "regulatory_fee": round(regulatory_fee, 4),
            "total_fee": round(total_fee, 4),
            "sell_total": round(notional - total_fee, 2),
        }

    def calculate_total_cost(self, price: float, quantity: float, side: str) -> Dict[str, float]:
        """计算单笔交易总费用"""
        if side == "buy":
            return self.calculate_buy_cost(price, quantity)
        elif side == "sell":
            return self.calculate_sell_cost(price, quantity)
        return {}


# ═══════════════════════════════════════════════════════════════════
# 持仓信息
# ═══════════════════════════════════════════════════════════════════

@dataclass
class PositionInfo:
    """持仓信息"""
    symbol: str
    quantity: float = 0.0
    available: float = 0.0          # 可用数量（T+1 约束）
    cost_price: float = 0.0         # 成本价
    current_price: float = 0.0      # 当前价
    today_bought: float = 0.0       # 今日买入数量（T+1 不可卖）
    realized_pnl: float = 0.0       # 已实现盈亏
    commission_paid: float = 0.0    # 已付手续费

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        if self.quantity == 0:
            return 0.0
        return (self.current_price - self.cost_price) * self.quantity

    @property
    def total_pnl(self) -> float:
        return self.unrealized_pnl + self.realized_pnl

    @property
    def pnl_pct(self) -> float:
        if self.cost_price == 0 or self.quantity == 0:
            return 0.0
        return (self.current_price / self.cost_price - 1) * 100


# ═══════════════════════════════════════════════════════════════════
# 模拟盘账户
# ═══════════════════════════════════════════════════════════════════

class PaperAccount:
    """模拟盘账户 — 虚拟资金、持仓跟踪

    管理单个模拟交易账户的全局状态。
    """

    def __init__(
        self,
        account_id: str = "default",
        initial_cash: float = 1_000_000.0,
        fee_config: Optional[CommissionConfig] = None,
        state_file: Optional[str] = None,
    ):
        self._account_id = account_id
        self._initial_cash = initial_cash
        self._cash = initial_cash
        self._frozen_cash = 0.0
        self._fee_config = fee_config or CommissionConfig()
        self._calculator = FeeCalculator(fee_config)

        # 持仓
        self._positions: Dict[str, PositionInfo] = {}

        # 交易统计
        self._total_trades: int = 0
        self._total_buy_count: int = 0
        self._total_sell_count: int = 0
        self._total_commission: float = 0.0
        self._total_stamp_tax: float = 0.0
        self._total_buy_value: float = 0.0
        self._total_sell_value: float = 0.0
        self._total_realized_pnl: float = 0.0

        # 成交历史
        self._trade_history: List[Dict[str, Any]] = []

        # 事件日志
        self._event_log: List[Dict[str, Any]] = []

        # 自动加载上次的崩溃恢复状态
        if state_file:
            self.load_state(state_file)

    # ── 只读属性 ────────────────────────────────────────────────────

    @property
    def account_id(self) -> str:
        return self._account_id

    @property
    def initial_cash(self) -> float:
        return self._initial_cash

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def frozen_cash(self) -> float:
        return self._frozen_cash

    @property
    def available_cash(self) -> float:
        return self._cash - self._frozen_cash

    @property
    def positions(self) -> Dict[str, PositionInfo]:
        return dict(self._positions)

    @property
    def total_equity(self) -> float:
        """总权益 = 现金 + 冻结资金 + 持仓市值"""
        market_value = self.market_value
        return self._cash + self._frozen_cash + market_value

    @property
    def market_value(self) -> float:
        """持仓总市值"""
        return sum(p.market_value for p in self._positions.values())

    @property
    def total_pnl(self) -> float:
        """总盈亏 = 总权益 - 初始资金"""
        return self.total_equity - self._initial_cash

    @property
    def total_pnl_pct(self) -> float:
        """总盈亏百分比"""
        return (self.total_pnl / self._initial_cash * 100) if self._initial_cash > 0 else 0

    @property
    def max_drawdown(self) -> float:
        """最大回撤"""
        peak = self._initial_cash
        max_dd = 0.0
        for trade in self._trade_history:
            eq = trade.get("equity", peak)
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        return max_dd

    @property
    def total_trades(self) -> int:
        return self._total_trades

    @property
    def trade_history(self) -> List[Dict[str, Any]]:
        return self._trade_history.copy()

    @property
    def fee_config(self) -> CommissionConfig:
        return self._fee_config

    # ── 资金操作 ────────────────────────────────────────────────────

    def freeze_cash(self, amount: float, order_id: str = "") -> bool:
        """冻结资金（下单时）

        Returns:
            True 如果冻结成功，False 如果资金不足
        """
        if amount > self._cash:
            self._log_event("CASH_FREEZE_FAILED",
                            f"order={order_id} amount={amount:.2f} available={self._cash:.2f}")
            return False

        self._cash -= amount
        self._frozen_cash += amount
        self._log_event("CASH_FROZEN",
                        f"order={order_id} amount={amount:.2f} remaining={self._cash:.2f}")
        return True

    def release_cash(self, amount: float, order_id: str = "") -> None:
        """释放资金（撤单时）"""
        self._frozen_cash = max(0, self._frozen_cash - amount)
        self._cash += amount
        self._log_event("CASH_RELEASED",
                        f"order={order_id} amount={amount:.2f}")

    def deduct_fees(self, fees: Dict[str, float]) -> None:
        """扣减费用"""
        total_fee = sum(fees.values())
        self._cash -= total_fee
        self._total_commission += fees.get("commission", 0)
        self._total_stamp_tax += fees.get("stamp_tax", 0)

    def add_funds(self, amount: float) -> None:
        """追加资金"""
        self._cash += amount
        self._log_event("FUND_DEPOSIT", f"amount={amount:.2f}")

    def withdraw_funds(self, amount: float) -> bool:
        """提取资金"""
        if amount > self._cash:
            return False
        self._cash -= amount
        self._log_event("FUND_WITHDRAW", f"amount={amount:.2f}")
        return True

    # ── 持仓操作 ────────────────────────────────────────────────────

    def handle_buy_fill(
        self,
        symbol: str,
        quantity: float,
        price: float,
        fees: Dict[str, float],
        order_id: str = "",
    ) -> PositionInfo:
        """处理买入成交

        Returns:
            更新后的持仓信息
        """
        # 扣减资金（含费用）
        buy_cost = self._calculator.calculate_buy_cost(price, quantity)
        total_cost = buy_cost["buy_total"]
        self._cash -= total_cost

        # 更新持仓
        if symbol not in self._positions:
            self._positions[symbol] = PositionInfo(symbol=symbol)

        pos = self._positions[symbol]
        total_cost_basis = pos.cost_price * pos.quantity + price * quantity
        pos.quantity += quantity
        pos.available = pos.quantity - pos.today_bought
        pos.cost_price = total_cost_basis / pos.quantity if pos.quantity > 0 else 0
        pos.current_price = price
        pos.today_bought += quantity
        pos.commission_paid += fees.get("total_fee", 0)

        # 更新统计
        self._total_buy_count += 1
        self._total_buy_value += price * quantity

        # 记录成交
        self._record_trade(symbol, "BUY", quantity, price, fees)

        return pos

    def handle_sell_fill(
        self,
        symbol: str,
        quantity: float,
        price: float,
        fees: Dict[str, float],
        order_id: str = "",
    ) -> Optional[PositionInfo]:
        """处理卖出成交

        Returns:
            更新后的持仓信息（清仓后返回 None）
        """
        if symbol not in self._positions:
            return None

        pos = self._positions[symbol]
        if pos.quantity < quantity:
            quantity = pos.quantity

        # 计算已实现盈亏
        realized = (price - pos.cost_price) * quantity
        pos.realized_pnl += realized
        self._total_realized_pnl += realized

        # 扣减资金（含费用）
        sell_cost = self._calculator.calculate_sell_cost(price, quantity)
        net_proceeds = sell_cost["sell_total"]
        self._cash += net_proceeds

        # 更新持仓
        pos.quantity -= quantity
        pos.available = pos.quantity - pos.today_bought
        if pos.quantity > 0:
            pos.current_price = price
        else:
            pos.cost_price = 0.0
            pos.current_price = 0.0
            pos.today_bought = 0.0
            pos.commission_paid = 0.0
            pos.realized_pnl = 0.0

        # 更新统计
        self._total_sell_count += 1
        self._total_sell_value += price * quantity

        # 记录成交
        self._record_trade(symbol, "SELL", quantity, price, fees)

        # 清仓后移除
        if pos.quantity <= 0:
            del self._positions[symbol]
            return None

        return pos

    # ── T+1 处理 ───────────────────────────────────────────────────

    def unlock_today_frozen(self) -> int:
        """解除今日买入的冻结（次日调用）

        Returns:
            解锁的持仓数量
        """
        unlocked = 0
        for pos in self._positions.values():
            unlocked += pos.today_bought
            pos.available = pos.quantity
            pos.today_bought = 0.0
        return unlocked

    # ── 行情更新 ───────────────────────────────────────────────────

    def update_price(self, symbol: str, price: float) -> None:
        """更新标的当前价格"""
        if symbol in self._positions:
            self._positions[symbol].current_price = price
        self._log_event("PRICE_UPDATE", f"{symbol}={price}")

    def update_all_prices(self, prices: Dict[str, float]) -> None:
        """批量更新价格"""
        for symbol, price in prices.items():
            self.update_price(symbol, price)

    # ── 查询 ────────────────────────────────────────────────────────

    def get_position(self, symbol: str) -> Optional[PositionInfo]:
        """获取单个标的持仓"""
        return self._positions.get(symbol)

    def get_position_list(self) -> List[PositionInfo]:
        """获取所有持仓列表"""
        return list(self._positions.values())

    def get_total_commission(self) -> float:
        """累计手续费"""
        return self._total_commission

    def get_total_stamp_tax(self) -> float:
        """累计印花税"""
        return self._total_stamp_tax

    def summary(self) -> Dict[str, Any]:
        """账户摘要"""
        return {
            "account_id": self._account_id,
            "initial_cash": self._initial_cash,
            "cash": round(self._cash, 2),
            "frozen_cash": round(self._frozen_cash, 2),
            "available_cash": round(self.available_cash, 2),
            "market_value": round(self.market_value, 2),
            "total_equity": round(self.total_equity, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_pnl_pct": round(self.total_pnl_pct, 2),
            "max_drawdown": round(self.max_drawdown, 4),
            "num_positions": len(self._positions),
            "total_trades": self._total_trades,
            "total_buy_count": self._total_buy_count,
            "total_sell_count": self._total_sell_count,
            "total_buy_value": round(self._total_buy_value, 2),
            "total_sell_value": round(self._total_sell_value, 2),
            "total_commission": round(self._total_commission, 4),
            "total_stamp_tax": round(self._total_stamp_tax, 4),
            "positions": {
                sym: {
                    "quantity": p.quantity,
                    "available": p.available,
                    "cost_price": round(p.cost_price, 4),
                    "current_price": round(p.current_price, 4),
                    "market_value": round(p.market_value, 2),
                    "unrealized_pnl": round(p.unrealized_pnl, 2),
                    "realized_pnl": round(p.realized_pnl, 2),
                    "pnl_pct": round(p.pnl_pct, 2),
                }
                for sym, p in self._positions.items()
            },
        }

    # ── 内部 ────────────────────────────────────────────────────────

    def _record_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        fees: Dict[str, float],
    ) -> None:
        """记录成交详情"""
        self._total_trades += 1
        self._trade_history.append({
            "trade_id": self._total_trades,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "fees": fees,
            "equity": self.total_equity,
            "timestamp": datetime.now().isoformat(),
        })

    def _log_event(self, event_type: str, detail: str = "") -> None:
        """记录事件"""
        self._event_log.append({
            "type": event_type,
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        })

    # ── 状态持久化 ──────────────────────────────────────────────────

    def save_state(self, filepath: str) -> None:
        """持久化账户状态"""
        state = {
            "account_id": self._account_id,
            "initial_cash": self._initial_cash,
            "cash": self._cash,
            "frozen_cash": self._frozen_cash,
            "positions": {
                sym: {
                    "quantity": p.quantity,
                    "available": p.available,
                    "cost_price": p.cost_price,
                    "current_price": p.current_price,
                    "today_bought": p.today_bought,
                    "realized_pnl": p.realized_pnl,
                    "commission_paid": p.commission_paid,
                }
                for sym, p in self._positions.items()
            },
            "total_trades": self._total_trades,
            "total_buy_count": self._total_buy_count,
            "total_sell_count": self._total_sell_count,
            "total_commission": self._total_commission,
            "total_stamp_tax": self._total_stamp_tax,
            "total_buy_value": self._total_buy_value,
            "total_sell_value": self._total_sell_value,
            "total_realized_pnl": self._total_realized_pnl,
        }
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.info(f"模拟盘账户状态已保存到 {filepath}")
        except Exception as e:
            logger.warning(f"保存模拟盘账户状态失败: {e}")

    def load_state(self, filepath: str) -> bool:
        """加载账户状态"""
        try:
            p = Path(filepath)
            if not p.exists():
                return False
            with open(filepath, "r", encoding="utf-8") as f:
                state = json.load(f)

            self._account_id = state.get("account_id", self._account_id)
            self._initial_cash = state.get("initial_cash", self._initial_cash)
            self._cash = state.get("cash", self._cash)
            self._frozen_cash = state.get("frozen_cash", 0.0)
            self._total_trades = state.get("total_trades", 0)
            self._total_buy_count = state.get("total_buy_count", 0)
            self._total_sell_count = state.get("total_sell_count", 0)
            self._total_commission = state.get("total_commission", 0.0)
            self._total_stamp_tax = state.get("total_stamp_tax", 0.0)
            self._total_buy_value = state.get("total_buy_value", 0.0)
            self._total_sell_value = state.get("total_sell_value", 0.0)
            self._total_realized_pnl = state.get("total_realized_pnl", 0.0)

            # 恢复持仓
            for sym, pdata in state.get("positions", {}).items():
                self._positions[sym] = PositionInfo(
                    symbol=sym,
                    quantity=pdata.get("quantity", 0.0),
                    available=pdata.get("available", 0.0),
                    cost_price=pdata.get("cost_price", 0.0),
                    current_price=pdata.get("current_price", 0.0),
                    today_bought=pdata.get("today_bought", 0.0),
                    realized_pnl=pdata.get("realized_pnl", 0.0),
                    commission_paid=pdata.get("commission_paid", 0.0),
                )

            logger.info(
                f"已从 {filepath} 恢复模拟盘账户状态: cash={self._cash:.2f}, "
                f"positions={len(self._positions)}, trades={self._total_trades}"
            )
            return True
        except Exception as e:
            logger.warning(f"加载模拟盘账户状态失败: {e}")
            return False
