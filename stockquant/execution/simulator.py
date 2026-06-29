# -*- coding: utf-8 -*-
"""#5 P0 任务：仿真交易模拟器

管理模拟盘账户、撮合引擎、行情推送的协调器。
将 MatchingEngine 集成到 PaperBroker 的交易流程中。
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.models.bar import BarData
from stockquant.models.trade import TradeData
from stockquant.events import EventType
from stockquant.execution.matching_engine import MatchingEngine, PriceLimitCalculator

logger = logging.getLogger(__name__)


class SimulationAccount:
    """模拟盘账户

    管理虚拟资金、持仓、冻结资金。
    """

    def __init__(self, initial_cash: float = 1_000_000.0):
        self._initial_cash = initial_cash
        self._cash = initial_cash
        self._frozen_cash = 0.0
        # 持仓: {symbol: {quantity: float, avg_cost: float, available: float}}
        self._positions: Dict[str, Dict[str, float]] = {}
        # 当前行情价格（用于计算持仓市值）
        self._market_prices: Dict[str, float] = {}
        self._trade_history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    # ---------- 属性 ----------

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def available_cash(self) -> float:
        """可用资金 = 总资金 - 冻结资金"""
        return self._cash - self._frozen_cash

    @property
    def frozen_cash(self) -> float:
        return self._frozen_cash

    @property
    def total_equity(self) -> float:
        """总权益 = 现金 + 持仓市值"""
        return self._cash + self._positions_market_value

    @property
    def positions(self) -> Dict[str, Dict[str, float]]:
        return {k: dict(v) for k, v in self._positions.items()}

    @property
    def trade_history(self) -> List[Dict[str, Any]]:
        return list(self._trade_history)

    @property
    def _positions_market_value(self) -> float:
        """持仓市值"""
        total = 0.0
        for symbol, pos in self._positions.items():
            market_price = self._market_prices.get(symbol, pos["avg_cost"])
            total += pos["quantity"] * market_price
        return total

    # ---------- 资金操作 ----------

    def freeze_cash(self, amount: float) -> bool:
        """冻结资金（用于买单下单时）

        Args:
            amount: 冻结金额

        Returns:
            True 冻结成功，False 可用资金不足
        """
        with self._lock:
            if amount <= 0:
                return False
            if amount > self.available_cash:
                return False
            self._frozen_cash += amount
            return True

    def unfreeze_cash(self, amount: float) -> None:
        """解冻资金（用于撤单时）

        Args:
            amount: 解冻金额（不超过冻结资金）
        """
        with self._lock:
            if amount <= 0:
                return
            actual = min(amount, self._frozen_cash)
            self._frozen_cash -= actual

    def deduct_cash(self, amount: float) -> bool:
        """扣减资金（买入成交时）"""
        with self._lock:
            if amount > self._cash:
                return False
            self._cash -= amount
            # 成交后释放冻结资金
            self._frozen_cash = max(0, self._frozen_cash - amount)
            return True

    def add_cash(self, amount: float) -> None:
        """增加资金（卖出成交时）"""
        with self._lock:
            if amount > 0:
                self._cash += amount

    # ---------- 持仓操作 ----------

    def update_position(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> None:
        """更新持仓（成交后调用）

        Args:
            symbol: 股票代码
            side: 买/卖方向
            quantity: 成交数量
            price: 成交价格
        """
        with self._lock:
            if symbol not in self._positions:
                self._positions[symbol] = {
                    "quantity": 0.0,
                    "avg_cost": 0.0,
                    "available": 0.0,
                }

            pos = self._positions[symbol]

            if side == OrderSide.BUY.value or side == "Buy":
                # 买入：增加持仓，更新均价
                total_cost = pos["avg_cost"] * pos["quantity"] + price * quantity
                pos["quantity"] += quantity
                pos["avg_cost"] = total_cost / pos["quantity"] if pos["quantity"] > 0 else 0.0
                pos["available"] = pos["quantity"]  # 买入后 T+1 不可卖，仿真中简化为立即可卖
                self._market_prices[symbol] = price
            elif side == OrderSide.SELL.value or side == "Sell":
                # 卖出：减少持仓
                pos["quantity"] -= quantity
                pos["available"] = max(0, pos["available"] - quantity)
                self._market_prices[symbol] = price
                if pos["quantity"] <= 0:
                    pos["quantity"] = 0.0
                    pos["avg_cost"] = 0.0
                    pos["available"] = 0.0

    def get_position(self, symbol: str) -> Dict[str, float]:
        """获取指定标的持仓"""
        with self._lock:
            if symbol not in self._positions:
                return {"quantity": 0.0, "avg_cost": 0.0, "available": 0.0}
            return dict(self._positions[symbol])

    def check_buy_power(self, price: float, quantity: float) -> bool:
        """检查购买力是否足够"""
        with self._lock:
            required = price * quantity
            return required <= self.available_cash

    def check_sellable(self, symbol: str, quantity: float) -> bool:
        """检查可卖数量是否足够"""
        with self._lock:
            pos = self._positions.get(symbol)
            if not pos:
                return quantity <= 0
            return pos["available"] >= quantity

    def update_market_price(self, symbol: str, price: float) -> None:
        """更新行情价格"""
        with self._lock:
            if price > 0:
                self._market_prices[symbol] = price

    def record_trade(self, trade: TradeData) -> None:
        """记录交易历史"""
        with self._lock:
            self._trade_history.append({
                "trade_id": trade.trade_id,
                "order_id": trade.order_id,
                "symbol": trade.symbol,
                "side": trade.side,
                "price": trade.price,
                "quantity": trade.quantity,
                "commission": trade.commission,
                "slippage": trade.slippage,
                "timestamp": trade.timestamp,
            })

    def snapshot(self) -> Dict[str, Any]:
        """账户快照"""
        with self._lock:
            positions_detail = {}
            for symbol, pos in self._positions.items():
                if pos["quantity"] > 0:
                    market_price = self._market_prices.get(symbol, pos["avg_cost"])
                    positions_detail[symbol] = {
                        "quantity": pos["quantity"],
                        "avg_cost": round(pos["avg_cost"], 2),
                        "market_price": round(market_price, 2),
                        "market_value": round(pos["quantity"] * market_price, 2),
                        "pnl": round((market_price - pos["avg_cost"]) * pos["quantity"], 2),
                        "available": pos["available"],
                    }

            return {
                "initial_cash": round(self._initial_cash, 2),
                "cash": round(self._cash, 2),
                "frozen_cash": round(self._frozen_cash, 2),
                "available_cash": round(self.available_cash, 2),
                "positions_market_value": round(self._positions_market_value, 2),
                "total_equity": round(self.total_equity, 2),
                "pnl": round(self.total_equity - self._initial_cash, 2),
                "pnl_pct": round(
                    (self.total_equity - self._initial_cash) / self._initial_cash * 100
                    if self._initial_cash > 0 else 0.0,
                    2,
                ),
                "positions": positions_detail,
                "total_trades": len(self._trade_history),
            }

    def reset(self, initial_cash: float = 0.0) -> None:
        """重置账户"""
        with self._lock:
            self._cash = initial_cash if initial_cash > 0 else self._initial_cash
            self._frozen_cash = 0.0
            self._positions.clear()
            self._market_prices.clear()
            self._trade_history.clear()


class Simulator:
    """仿真交易模拟器 -- 协调器

    协调 SimulationAccount + MatchingEngine + 行情推送。
    每个标的拥有独立的 MatchingEngine 实例。

    使用方式：
        sim = Simulator(initial_cash=1_000_000.0)

        # 下单
        order = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT,
                      price=10.5, quantity=1000, order_id="buy_001")
        sim.place_order(order, prev_close=10.0)

        # 推送行情
        bar = BarData(symbol="000001", datetime=..., open=10.5, high=11.0,
                      low=10.3, close=10.8, volume=1000000)
        trades = sim.on_bar(bar)

        # 查看账户
        print(sim.get_account().snapshot())
    """

    def __init__(self, initial_cash: float = 1_000_000.0):
        self._account = SimulationAccount(initial_cash)
        self._engines: Dict[str, MatchingEngine] = {}
        self._pending_orders: Dict[str, Order] = {}
        self._prev_close_map: Dict[str, float] = {}
        self._lock = threading.Lock()

    @property
    def account(self) -> SimulationAccount:
        return self._account

    def get_engine(
        self, symbol: str, prev_close: float, name: str = ""
    ) -> MatchingEngine:
        """获取或创建指定标的的撮合引擎

        Args:
            symbol: 股票代码
            prev_close: 前收盘价
            name: 股票名称

        Returns:
            MatchingEngine 实例
        """
        with self._lock:
            if symbol not in self._engines:
                self._engines[symbol] = MatchingEngine(
                    symbol=symbol,
                    prev_close=prev_close,
                    name=name,
                )
                self._prev_close_map[symbol] = prev_close
            return self._engines[symbol]

    def place_order(
        self,
        order: Order,
        prev_close: float = 0.0,
        name: str = "",
    ) -> Tuple[bool, str]:
        """下单

        Args:
            order: 订单
            prev_close: 前收盘价（用于初始化引擎）
            name: 股票名称

        Returns:
            (是否成功, 消息)
        """
        # 前置校验：100 股整数倍
        if order.quantity % 100 != 0:
            order.update_status(EventType.ORDER_REJECTED.value)
            return (False, "quantity must be multiple of 100")

        # 获取或创建撮合引擎
        if prev_close <= 0:
            prev_close = self._prev_close_map.get(order.symbol, 0.0)
        if prev_close <= 0:
            order.update_status(EventType.ORDER_REJECTED.value)
            return (False, "prev_close is required and not provided")

        engine = self.get_engine(order.symbol, prev_close, name)

        # 如果引擎处于 closed 状态，自动进入连续竞价
        if engine.phase == MatchingEngine.PHASE_CLOSED:
            engine.enter_continuous_phase()

        # 资金/持仓校验
        if order.side == OrderSide.BUY:
            cost = order.price * order.quantity
            if not self._account.check_buy_power(order.price, order.quantity):
                order.update_status(EventType.ORDER_REJECTED.value)
                return (False, "insufficient cash")

            # 冻结资金
            if not self._account.freeze_cash(cost):
                order.update_status(EventType.ORDER_REJECTED.value)
                return (False, "failed to freeze cash")
        elif order.side == OrderSide.SELL:
            if not self._account.check_sellable(order.symbol, order.quantity):
                order.update_status(EventType.ORDER_REJECTED.value)
                return (False, "insufficient sellable quantity")

        # 涨跌停校验（限价单）
        if order.order_type == OrderType.LIMIT:
            if not PriceLimitCalculator.is_price_valid(
                order.price, engine.limit_up, engine.limit_down
            ):
                order.update_status(EventType.ORDER_REJECTED.value)
                # 买入时解冻资金
                if order.side == OrderSide.BUY:
                    self._account.unfreeze_cash(order.price * order.quantity)
                return (False, "price out of price limit range")

        # 提交到撮合引擎
        accepted = engine.accept_order(order)
        if not accepted:
            # 撤回冻结资金
            if order.side == OrderSide.BUY:
                self._account.unfreeze_cash(order.price * order.quantity)
            return (False, "engine rejected order")

        # 记录挂单
        self._pending_orders[order.order_id] = order

        return (True, "order accepted")

    def cancel_order(self, order_id: str) -> bool:
        """撤单

        Args:
            order_id: 订单 ID

        Returns:
            是否撤单成功
        """
        with self._lock:
            order = self._pending_orders.get(order_id)
            if not order:
                return False

            # 找到对应引擎撤单
            engine = self._engines.get(order.symbol)
            if not engine:
                return False

            success = engine.cancel_order(order_id)
            if success:
                order.update_status(EventType.ORDER_CANCELLED.value)
                # 买入时解冻资金
                if order.side == OrderSide.BUY:
                    self._account.unfreeze_cash(order.price * order.quantity)
                self._pending_orders.pop(order_id, None)
                return True

            return False

    def on_bar(self, bar: BarData) -> List[TradeData]:
        """推送行情，触发撮合

        Args:
            bar: K线数据

        Returns:
            成交列表
        """
        engine = self._engines.get(bar.symbol)
        if not engine:
            return []

        # 更新行情价格
        self._account.update_market_price(bar.symbol, bar.close)

        # 如果引擎还在 closed 状态，自动进入连续竞价
        if engine.phase == MatchingEngine.PHASE_CLOSED:
            engine.enter_continuous_phase()

        # 用 bar 驱动撮合
        match_results = engine.match_tick(bar)

        # 处理成交
        trades = []
        for order, trade_data in match_results:
            self._process_fill(order, trade_data)
            trades.append(trade_data)

        return trades

    def on_call_auction(
        self,
        symbol: str,
        orders: List[Order],
        prev_close: float,
        name: str = "",
    ) -> List[TradeData]:
        """执行集合竞价

        Args:
            symbol: 股票代码
            orders: 参与集合竞价的订单列表
            prev_close: 前收盘价
            name: 股票名称

        Returns:
            成交列表
        """
        engine = self.get_engine(symbol, prev_close, name)
        engine.enter_call_auction_phase()

        # 前置校验并接收订单
        for order in orders:
            # 校验
            if order.quantity % 100 != 0:
                order.update_status(EventType.ORDER_REJECTED.value)
                continue

            if order.side == OrderSide.BUY:
                cost = order.price * order.quantity
                if not self._account.check_buy_power(order.price, order.quantity):
                    order.update_status(EventType.ORDER_REJECTED.value)
                    continue
                self._account.freeze_cash(cost)
            elif order.side == OrderSide.SELL:
                if not self._account.check_sellable(symbol, order.quantity):
                    order.update_status(EventType.ORDER_REJECTED.value)
                    continue

            # 涨跌停校验
            if order.order_type == OrderType.LIMIT:
                if not PriceLimitCalculator.is_price_valid(
                    order.price, engine.limit_up, engine.limit_down
                ):
                    order.update_status(EventType.ORDER_REJECTED.value)
                    if order.side == OrderSide.BUY:
                        self._account.unfreeze_cash(order.price * order.quantity)
                    continue

            engine.accept_order(order)
            self._pending_orders[order.order_id] = order

        # 执行集合竞价撮合
        match_results = engine.resolve_call_auction()

        # 处理成交
        trades = []
        for order, trade_data in match_results:
            self._process_fill(order, trade_data)
            trades.append(trade_data)

        # 集合竞价完成后进入连续竞价阶段
        engine.enter_continuous_phase()

        return trades

    def _process_fill(self, order: Order, trade_data: TradeData) -> None:
        """处理成交：更新账户资金和持仓"""
        symbol = trade_data.symbol
        price = trade_data.price
        quantity = trade_data.quantity
        notional = price * quantity

        if trade_data.side == OrderSide.BUY.value or trade_data.side == "Buy":
            # 买入成交：扣减资金，更新持仓
            self._account.deduct_cash(notional)
            self._account.update_position(symbol, OrderSide.BUY.value, quantity, price)
        elif trade_data.side == OrderSide.SELL.value or trade_data.side == "Sell":
            # 卖出成交：增加资金，更新持仓
            self._account.add_cash(notional)
            self._account.update_position(symbol, OrderSide.SELL.value, quantity, price)

        # 记录交易
        self._account.record_trade(trade_data)

        # 如果订单完全成交，从挂单中移除
        if order.remaining <= 0:
            self._pending_orders.pop(order.order_id, None)

    def get_account(self) -> SimulationAccount:
        """获取账户引用"""
        return self._account

    def get_order_book(self, symbol: str) -> dict:
        """获取指定标的的订单簿快照"""
        engine = self._engines.get(symbol)
        if not engine:
            return {"bids": [], "asks": []}
        return engine.get_order_book()

    def get_pending_order(self, order_id: str) -> Optional[Order]:
        """获取挂单"""
        return self._pending_orders.get(order_id)

    @property
    def pending_orders(self) -> Dict[str, Order]:
        return dict(self._pending_orders)

    @property
    def statistics(self) -> Dict[str, Any]:
        """模拟器统计信息"""
        engine_stats = {}
        for symbol, engine in self._engines.items():
            engine_stats[symbol] = engine.statistics

        return {
            "account": self._account.snapshot(),
            "engines": engine_stats,
            "pending_orders": len(self._pending_orders),
        }

    def reset(self) -> None:
        """重置模拟器"""
        with self._lock:
            self._account.reset()
            self._engines.clear()
            self._pending_orders.clear()
            self._prev_close_map.clear()
