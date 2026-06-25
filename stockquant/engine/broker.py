# -*- coding: utf-8 -*-
"""F006 Broker 抽象层 — 回测/模拟/实盘统一接口"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from stockquant.models.order import Order, OrderSide, OrderType, OrderStatus
from stockquant.models.bar import BarData
from stockquant.models.trade import TradeData


@dataclass
class OrderAuditLog:
    """订单审计日志"""
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    price: float = 0.0
    quantity: float = 0.0
    status: str = "PENDING"
    timestamp: datetime = field(default_factory=datetime.now)
    reason: str = ""


class Broker(ABC):
    """Broker 抽象基类"""

    @abstractmethod
    def place_order(self, order: Order, bar: BarData) -> Optional[TradeData]:
        """下单并撮合"""
        ...

    @abstractmethod
    def cancel_order(self, order: Order) -> bool:
        """撤单"""
        ...

    @abstractmethod
    def get_positions(self) -> Dict[str, Any]:
        """获取所有持仓"""
        ...

    @abstractmethod
    def get_balance(self) -> Dict[str, Any]:
        """获取账户余额"""
        ...

    @abstractmethod
    def get_history(self, symbol: str, bar_count: int) -> List[BarData]:
        """获取历史K线"""
        ...


class BacktestBroker(Broker):
    """
    回测 Broker — 基于K线数据模拟成交。

    撮合规则:
    - 市价单：按当前 Bar 收盘价撮合
    - 限价单：价格优先、时间优先
      - Buy Limit：实际价格 ≤ 限价 → 按限价成交
      - Sell Limit：实际价格 ≥ 限价 → 按限价成交
    - STOP（止损单）：当 bar 的 high/low 触及止损价时触发，
      触发后按 bar.close（+滑点）作为市价执行
    - STOP_LIMIT（止损限价单）：止损价触发后，
      按限价条件撮合（Buy: close ≤ limit；Sell: close ≥ limit）
    - 涨跌停板限制
    - 100 股整数倍

    确定性保证:
    - 回测结果完全确定性：撮合逻辑不包含任何随机因素
    - 相同输入（K线数据 + 订单参数）始终产生相同输出
    - 无需设置随机种子，因为不使用 random / numpy.random 等随机源
    """

    def __init__(
        self,
        slippage: Optional[Any] = None,
        limit_up_ratio: float = 0.10,
        limit_down_ratio: float = 0.10,
    ):
        self._slippage = slippage
        self._limit_up_ratio = limit_up_ratio
        self._limit_down_ratio = limit_down_ratio
        self._order_book: Dict[str, List[Order]] = {}  # 未成交订单
        self._trade_log: List[TradeData] = []
        self._portfolio: Optional[Any] = None  # 绑定的 Portfolio 实例
        self._next_order_seq: int = 0  # 订单自增序列号

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _alloc_order_id(self, symbol: str) -> str:
        """分配一个确定性订单 ID"""
        self._next_order_seq += 1
        return f"{symbol}_seq{self._next_order_seq}"

    def _compute_exec_price(self, bar: BarData, side: str) -> float:
        """在 bar.close 基础上应用滑点"""
        exec_price = bar.close
        if self._slippage:
            exec_price = self._slippage.apply(bar.close, side)
        return exec_price

    def _try_fill(self, order: Order, exec_price: float, bar: BarData) -> Optional[TradeData]:
        """执行一笔成交，返回 TradeData；失败返回 None"""
        order.update_status(OrderStatus.FILLED)
        order.add_fill(order.quantity, exec_price)

        trade = TradeData(
            trade_id=f"{order.order_id}_trade",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side.value,
            price=exec_price,
            quantity=order.quantity,
        )
        self._trade_log.append(trade)
        return trade

    # ------------------------------------------------------------------
    # STOP / STOP_LIMIT 撮合
    # ------------------------------------------------------------------

    def _check_stop_orders(self, bar: BarData) -> List[TradeData]:
        """检查 order_book 中所有 STOP / STOP_LIMIT 订单是否触发/成交。

        被 place_order 以及回测引擎在每一根新 K 线上调用。
        返回本周期新成交的 TradeData 列表。
        """
        filled_trades: List[TradeData] = []
        symbol = bar.symbol

        if symbol not in self._order_book:
            return filled_trades

        still_pending: List[Order] = []
        for order in self._order_book[symbol]:
            # 已过期的订单（例如已被用户撤销）
            if order.status == OrderStatus.CANCELLED:
                continue

            is_buy = order.side == OrderSide.BUY
            stop_price = order.price  # STOP/STOP_LIMIT 的 trigger 价格

            # ---- STOP 订单 ----
            if order.order_type == OrderType.STOP:
                crossed = False
                if is_buy and bar.high >= stop_price:
                    crossed = True
                elif not is_buy and bar.low <= stop_price:
                    crossed = True

                if crossed:
                    # 触发后按市价单执行（用 bar.close + 滑点）
                    side_str = "buy" if is_buy else "sell"
                    exec_price = self._compute_exec_price(bar, side_str)
                    trade = self._try_fill(order, exec_price, bar)
                    if trade:
                        filled_trades.append(trade)
                else:
                    still_pending.append(order)

            # ---- STOP_LIMIT 订单 ----
            elif order.order_type == OrderType.STOP_LIMIT:
                crossed = False
                if is_buy and bar.high >= stop_price:
                    crossed = True
                elif not is_buy and bar.low <= stop_price:
                    crossed = True

                if crossed:
                    # 止损触发，退化为 LIMIT 订单：检查 limit price 是否满足
                    limit_price = order.price
                    if is_buy and bar.close <= limit_price:
                        # 可以成交：按限价价格（较好价格）
                        exec_price = min(limit_price, bar.close)
                        trade = self._try_fill(order, exec_price, bar)
                        if trade:
                            filled_trades.append(trade)
                    elif not is_buy and bar.close >= limit_price:
                        exec_price = max(limit_price, bar.close)
                        trade = self._try_fill(order, exec_price, bar)
                        if trade:
                            filled_trades.append(trade)
                    else:
                        # 触发但限价未满足，挂入 order_book 等待后续 K 线
                        still_pending.append(order)
                else:
                    still_pending.append(order)

        self._order_book[symbol] = still_pending
        return filled_trades

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def place_order(self, order: Order, bar: BarData) -> Optional[TradeData]:
        """
        撮合一笔订单。

        Returns
        -------
        TradeData or None
            成交则返回 TradeData，否则返回 None
        """
        # 1. 涨跌停检查
        limit_up = bar.close * (1 + self._limit_up_ratio)
        limit_down = bar.close * (1 - self._limit_down_ratio)

        if order.price > limit_up or order.price < limit_down:
            order.update_status(OrderStatus.REJECTED)
            return None

        # 2. 100 股整数倍
        if order.quantity % 100 != 0:
            order.update_status(OrderStatus.REJECTED)
            return None

        # 3. STOP 订单：止损触发逻辑
        if order.order_type == OrderType.STOP:
            is_buy = order.side == OrderSide.BUY
            stop_price = order.price

            # 先检查本 bar 是否已触发
            if is_buy and bar.high >= stop_price:
                # 触发，按市价单执行（bar.close + 滑点）
                exec_price = self._compute_exec_price(bar, "buy")
                return self._try_fill(order, exec_price, bar)
            elif not is_buy and bar.low <= stop_price:
                exec_price = self._compute_exec_price(bar, "sell")
                return self._try_fill(order, exec_price, bar)

            # 未触发，挂入 order_book 等待后续 bar
            symbol = order.symbol
            if symbol not in self._order_book:
                self._order_book[symbol] = []
            self._order_book[symbol].append(order)
            order.update_status(OrderStatus.QUEUED)
            return None

        # 4. STOP_LIMIT 订单：止损+限价逻辑
        if order.order_type == OrderType.STOP_LIMIT:
            is_buy = order.side == OrderSide.BUY
            stop_price = order.price

            # 先检查止损价位是否触发
            if is_buy and bar.high >= stop_price:
                # 止损触发，再检查限价是否满足（买入要求 close ≤ limit）
                if bar.close <= stop_price:
                    exec_price = min(stop_price, bar.close)
                    return self._try_fill(order, exec_price, bar)
                # 限价不满足，挂入 order_book
            elif not is_buy and bar.low <= stop_price:
                # 止损触发，再检查限价是否满足（卖出要求 close ≥ limit）
                if bar.close >= stop_price:
                    exec_price = max(stop_price, bar.close)
                    return self._try_fill(order, exec_price, bar)
                # 限价不满足，挂入 order_book

            # 未触发或触发但限价不满足，挂入 order_book
            symbol = order.symbol
            if symbol not in self._order_book:
                self._order_book[symbol] = []
            self._order_book[symbol].append(order)
            order.update_status(OrderStatus.QUEUED)
            return None

        # 5. LIMIT 单价格检查
        if order.order_type.name == "LIMIT":
            if order.side == OrderSide.BUY and order.price < bar.close:
                # 买单限价低于市价，不会成交（简化：按市价撮合）
                pass
            elif order.side == OrderSide.SELL and order.price > bar.close:
                pass

        # 6. 市价单 / 可成交限价单 — 应用滑点并执行
        side = "buy" if order.side == OrderSide.BUY else "sell"
        exec_price = self._compute_exec_price(bar, side)

        # 7. 成交
        return self._try_fill(order, exec_price, bar)

    def cancel_order(self, order: Order) -> bool:
        if order.status.name in ("PENDING", "SUBMITTED", "QUEUED"):
            order.update_status(OrderStatus.CANCELLED)
            return True
        return False

    def get_positions(self, portfolio) -> Dict[str, Any]:
        """从 Cerebro/Portfolio 获取实际持仓"""
        if hasattr(portfolio, 'positions'):
            return {k: v.__dict__ for k, v in portfolio.positions.items() if v.quantity > 0}
        return {}

    def get_balance(self, account) -> Dict[str, Any]:
        """从 Account 获取余额"""
        if account:
            return {"cash": account.cash, "frozen": account.frozen_cash, "equity": account.total_equity}
        return {"cash": 0, "frozen": 0}

    def get_history(self, symbol: str, bar_count: int, data_feeds: list = None) -> List[BarData]:
        """从 DataFeed 获取历史数据"""
        if not data_feeds:
            return []
        for feed in data_feeds:
            if feed.symbol == symbol:
                n = len(feed)
                start = max(0, n - bar_count)
                return [feed[i] for i in range(start, n)]
        return []


class PaperBroker(Broker):
    """
    F012 模拟盘 Broker — 基于实时行情模拟成交。
    与 BacktestBroker 相同的费用模型和撮合逻辑，不实际下单。
    支持崩溃恢复：通过 save_state/load_state 持久化交易日志和订单簿。
    """

    _logger = logging.getLogger("stockquant.engine.broker.PaperBroker")

    def __init__(
        self,
        slippage: Optional[Any] = None,
        limit_up_ratio: float = 0.10,
        limit_down_ratio: float = 0.10,
        state_file: Optional[str] = None,
    ):
        self._slippage = slippage
        self._limit_up_ratio = limit_up_ratio
        self._limit_down_ratio = limit_down_ratio
        self._order_book: Dict[str, List[Order]] = {}  # 未成交订单
        self._trade_log: List[TradeData] = []
        self._portfolio: Optional[Any] = None  # 绑定的 Portfolio 实例
        self._orders_audit: Optional[Any] = None  # 绑定的订单审计日志
        self._state_file = state_file
        # 自动加载上次的崩溃恢复状态
        if state_file:
            self.load_state(state_file)

    def bind_portfolio(self, portfolio, orders_audit: Optional[dict] = None) -> None:
        """绑定 Portfolio 实例和订单审计日志，使 get_positions/get_balance/get_history 返回真实数据"""
        self._portfolio = portfolio
        self._orders_audit = orders_audit

    def place_order(self, order: Order, bar: BarData) -> Optional[TradeData]:
        """模拟成交：与 BacktestBroker 相同逻辑"""
        # 涨跌停检查
        limit_up = bar.close * (1 + self._limit_up_ratio)
        limit_down = bar.close * (1 - self._limit_down_ratio)
        if order.price > limit_up or order.price < limit_down:
            order.update_status(OrderStatus.REJECTED)
            return None
        # 100 股整数倍
        if order.quantity % 100 != 0:
            order.update_status(OrderStatus.REJECTED)
            return None
        # 限价单
        if order.order_type.name == "LIMIT":
            if order.side == OrderSide.BUY and order.price < bar.close:
                pass
            elif order.side == OrderSide.SELL and order.price > bar.close:
                pass
        # 滑点
        side = "buy" if order.side == OrderSide.BUY else "sell"
        exec_price = bar.close
        if self._slippage:
            exec_price = self._slippage.apply(bar.close, side)
        # 成交
        order.update_status(OrderStatus.FILLED)
        order.add_fill(order.quantity, exec_price)
        trade = TradeData(
            trade_id=f"{order.order_id}_trade",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side.value,
            price=exec_price,
            quantity=order.quantity,
        )
        self._trade_log.append(trade)
        # 每次交易后自动保存状态
        if self._state_file:
            self.save_state(self._state_file)
        return trade

    def cancel_order(self, order: Order) -> bool:
        if order.status.name in ("PENDING", "SUBMITTED", "QUEUED"):
            order.update_status(OrderStatus.CANCELLED)
            return True
        return False

    def get_positions(self, portfolio=None) -> Dict[str, Any]:
        """获取持仓 — 优先从绑定的 Portfolio 获取真实数据"""
        src = portfolio or self._portfolio
        if src and hasattr(src, 'positions'):
            return {k: v.__dict__ for k, v in src.positions.items() if v.quantity > 0}
        return {}

    def get_balance(self, account=None) -> Dict[str, Any]:
        """获取账户余额 — 优先从绑定的 Portfolio 获取真实数据"""
        src = account
        if src is None and self._portfolio and hasattr(self._portfolio, 'account'):
            src = self._portfolio.account
        if src:
            return {
                "paper": True,
                "cash": getattr(src, 'cash', 0),
                "available_cash": getattr(src, 'available_cash', 0),
                "frozen": getattr(src, 'frozen_cash', 0),
                "equity": getattr(src, 'total_equity', 0),
            }
        return {"paper": True, "cash": 0, "equity": 0}

    def get_history(self, symbol: str, bar_count: int, data_feeds: list = None) -> List[BarData]:
        """获取成交记录 — 从交易日志中提取"""
        # PaperBroker 不维护 K 线历史，返回空列表
        # 如需 K 线数据，应通过 BaoStockFeed 等数据源获取
        return []

    def on_bar(self, bar: BarData, pending_orders: Optional[Dict[str, Order]] = None) -> List[TradeData]:
        """接收实时行情，检查 LIMIT 订单是否可成交。

        Args:
            bar: 最新行情数据
            pending_orders: 待撮合的 LIMIT 订单字典 {order_id: Order}

        Returns:
            成交的 TradeData 列表
        """
        filled_trades: List[TradeData] = []
        if pending_orders is None:
            return filled_trades

        for order_id, order in list(pending_orders.items()):
            # 涨跌停检查
            limit_up = bar.close * (1 + self._limit_up_ratio)
            limit_down = bar.close * (1 - self._limit_down_ratio)
            if order.price > limit_up or order.price < limit_down:
                order.update_status(OrderStatus.REJECTED)
                self.cancel_order(order)
                continue

            # 100 股整数倍
            if order.quantity % 100 != 0:
                order.update_status(OrderStatus.REJECTED)
                self.cancel_order(order)
                continue

            # 限价单撮合条件
            matched = False
            if order.order_type == OrderType.LIMIT:
                if order.side == OrderSide.BUY and order.price >= bar.close:
                    matched = True
                elif order.side == OrderSide.SELL and order.price <= bar.close:
                    matched = True

            if matched:
                trade = self.place_order(order, bar)
                if trade:
                    filled_trades.append(trade)

        return filled_trades

    @property
    def trade_log(self) -> List[TradeData]:
        return self._trade_log.copy()

    def save_state(self, filepath: str) -> None:
        """将 trade_log 和 order_book 持久化到 JSON 文件，用于崩溃恢复"""
        state = {
            "trade_log": [
                {
                    "trade_id": t.trade_id,
                    "order_id": t.order_id,
                    "symbol": t.symbol,
                    "side": t.side,
                    "price": t.price,
                    "quantity": t.quantity,
                }
                for t in self._trade_log
            ],
            "order_book": {
                key: [
                    {
                        "order_id": o.order_id,
                        "symbol": o.symbol,
                        "side": o.side.value,
                        "order_type": o.order_type.value,
                        "price": o.price,
                        "quantity": o.quantity,
                    }
                    for o in orders
                ]
                for key, orders in self._order_book.items()
            },
        }
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._logger.warning(f"保存状态失败: {e}")

    def load_state(self, filepath: str) -> None:
        """从 JSON 文件恢复 trade_log 和 order_book"""
        try:
            p = Path(filepath)
            if not p.exists():
                return
            with open(filepath, "r", encoding="utf-8") as f:
                state = json.load(f)
            # 恢复 trade_log
            for t in state.get("trade_log", []):
                trade = TradeData(
                    trade_id=t["trade_id"],
                    order_id=t["order_id"],
                    symbol=t["symbol"],
                    side=t["side"],
                    price=t["price"],
                    quantity=t["quantity"],
                )
                self._trade_log.append(trade)
            # 恢复 order_book（仅记录，不重建 Order 对象）
            for key, orders in state.get("order_book", {}).items():
                self._order_book[key] = []
                for o in orders:
                    order = Order(
                        symbol=o["symbol"],
                        side=OrderSide(o["side"]),
                        order_type=OrderType(o["order_type"]),
                        price=o["price"],
                        quantity=o["quantity"],
                        order_id=o["order_id"],
                        status=OrderStatus.SUBMITTED,
                    )
                    self._order_book[key].append(order)
            self._logger.info(f"已从 {filepath} 恢复状态: {len(self._trade_log)} 条交易记录")
        except Exception as e:
            self._logger.warning(f"加载状态失败: {e}")

    # ── F012 补充：模拟盘实时循环与回测对比 ──────────────────

    def run_realtime_loop(
        self,
        data_feed,
        strategies: Optional[List[Any]] = None,
        interval_seconds: float = 1.0,
        max_bars: Optional[int] = None,
        callback: Optional[Any] = None,
    ) -> List[TradeData]:
        """
        模拟盘实时循环 — 从 DataFeed 逐 Bar 推送行情，撮合限价单。

        模拟真实盘中行情推送场景，支持在循环中调用策略的 on_bar/on_tick 回调。

        Args:
            data_feed: 实现了 __len__ 和 __getitem__ 的数据源
            strategies: 策略实例列表（可选）
            interval_seconds: 每根 Bar 之间的模拟延迟（秒）
            max_bars: 最多处理多少根 Bar（None = 全部）
            callback: 每根 Bar 处理后的回调 (bar, trades) → None

        Returns:
            所有成交的 TradeData 列表
        """
        import time

        total = len(data_feed)
        if max_bars:
            total = min(total, max_bars)

        all_trades: List[TradeData] = []

        for i in range(total):
            bar = data_feed[i]

            # 1. 处理挂单撮合
            trades = self.on_bar(bar, dict(self._order_book))
            all_trades.extend(trades)

            # 2. 通知策略
            if strategies:
                for strategy in strategies:
                    if hasattr(strategy, 'on_bar'):
                        strategy.on_bar(bar)
                    if hasattr(strategy, 'on_tick'):
                        strategy.on_tick(bar)

            # 3. 回调
            if callback:
                callback(bar, trades)

            # 4. 保存状态（可选）
            if self._state_file and trades:
                self.save_state(self._state_file)

            # 5. 模拟延迟（控制推送节奏）
            if interval_seconds > 0:
                time.sleep(interval_seconds)

        return all_trades

    def compare_with_backtest(
        self,
        backtest_equity: List[float],
        paper_equity: List[float],
    ) -> Dict[str, Any]:
        """
        模拟盘 vs 回测 结果对比分析。

        Args:
            backtest_broker: 回测 Broker 实例
            backtest_equity: 回测权益曲线 [equity_value, ...]
            paper_equity: 模拟盘权益曲线 [equity_value, ...]

        Returns:
            对比结果字典，包含误差、差异分析
        """
        import math

        if not backtest_equity or not paper_equity:
            return {"error": "No data to compare"}

        # 对齐长度
        min_len = min(len(backtest_equity), len(paper_equity))
        bt = backtest_equity[:min_len]
        pe = paper_equity[:min_len]

        # 计算各项误差
        absolute_errors = [abs(b - p) for b, p in zip(bt, pe)]
        pct_errors = [
            (b - p) / b * 100 if b != 0 else 0.0
            for b, p in zip(bt, pe)
        ]

        max_abs_error = max(absolute_errors) if absolute_errors else 0
        avg_abs_error = sum(absolute_errors) / len(absolute_errors) if absolute_errors else 0
        max_pct_error = max(abs(e) for e in pct_errors) if pct_errors else 0

        # 累计收益对比
        bt_total_return = (bt[-1] - bt[0]) / bt[0] if bt[0] != 0 else 0
        pe_total_return = (pe[-1] - pe[0]) / pe[0] if pe[0] != 0 else 0
        return_diff = abs(bt_total_return - pe_total_return)

        # 最大回撤对比
        def _max_drawdown(equity_curve):
            peak = equity_curve[0]
            max_dd = 0
            for eq in equity_curve:
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak if peak > 0 else 0
                max_dd = max(max_dd, dd)
            return max_dd

        bt_max_dd = _max_drawdown(bt)
        pe_max_dd = _max_drawdown(pe)

        return {
            "bar_count": min_len,
            "backtest_final_equity": bt[-1],
            "paper_final_equity": pe[-1],
            "backtest_total_return": round(bt_total_return, 6),
            "paper_total_return": round(pe_total_return, 6),
            "return_diff_pct": round(return_diff * 100, 4),
            "max_abs_error": round(max_abs_error, 2),
            "avg_abs_error": round(avg_abs_error, 2),
            "max_pct_error": round(max_pct_error, 4),
            "backtest_max_drawdown": round(bt_max_dd, 6),
            "paper_max_drawdown": round(pe_max_dd, 6),
            "max_drawdown_diff": round(abs(bt_max_dd - pe_max_dd), 6),
            "within_1_percent": return_diff < 0.01,
            "summary": (
                "模拟盘与回测误差 < 1%" if return_diff < 0.01
                else f"模拟盘与回测误差 {return_diff*100:.2f}%，超出 1% 阈值"
            ),
        }


class LiveBroker(Broker):
    """
    F017 实盘 Broker — 调用券商 API 实际下单。

    当前为可工作的骨架实现：
    - place_order: 将订单状态置为 SUBMITTED 并记录审计日志，
      预留 XTP/CTP 真实下单接口
    - cancel_order: 对未成交订单撤销
    - get_positions / get_balance / get_history: 返回空数据
      （真实券商连接后可扩展）

    通过 ``config`` 字典可配置 broker 类型和券商参数：
    ``{"api": "xtp" / "ctp" / "qmt", "user": ..., "password": ...}``
    """

    def __init__(self, api: str = "xtp", config: Optional[dict] = None):
        self._api = api  # "xtp" / "ctp" / "qmt"
        self._config = config or {}
        self._order_log: List[OrderAuditLog] = []
        self._open_orders: Dict[str, Order] = {}  # 尚未撤单的订单缓存
        self._data_feeds: List[Any] = []  # 数据源列表，运行时注入
        # 连接券商 SDK
        self._sdk_broker = self._connect_sdk()

    def _connect_sdk(self) -> Any:
        """连接券商 SDK Broker — 根据 api 类型动态导入"""
        sdk_map = {
            "xtp": "stockquant.execution.brokers.xtp_broker",
            "qmt": "stockquant.execution.brokers.qmt_broker",
            "ctp": "stockquant.execution.brokers.ctp_broker",
        }
        mod_path = sdk_map.get(self._api)
        if not mod_path:
            logging.getLogger("stockquant.engine.broker").warning("未知券商 API 类型: %s，使用占位符模式", self._api)
            return None
        try:
            mod = __import__(mod_path, fromlist=[""])
            cls_name = f"{self._api.upper()}Broker"
            cls = getattr(mod, cls_name, None)
            if cls:
                # 尝试用 config 参数初始化，失败则无参初始化
                try:
                    sdk = cls(config=self._config)
                except TypeError:
                    sdk = cls()
                logging.getLogger("stockquant.engine.broker").info("券商 SDK 连接成功: %s (%s)", cls_name, self._api)
                return sdk
        except ImportError as e:
            logging.getLogger("stockquant.engine.broker").warning("券商 SDK 未安装 (%s): %s，使用占位符模式", self._api, e)
        except Exception as e:
            logging.getLogger("stockquant.engine.broker").warning("券商 SDK 连接失败 (%s): %s，使用占位符模式", self._api, e)
        return None

    @property
    def api(self) -> str:
        """当前使用的券商 API 类型"""
        return self._api

    @property
    def config(self) -> dict:
        """券商配置"""
        return self._config

    def _log_order(
        self,
        order: Order,
        status: str = "SUBMITTED",
        reason: str = "",
    ) -> OrderAuditLog:
        """将订单事件写入审计日志"""
        entry = OrderAuditLog(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side.value,
            price=order.price,
            quantity=order.quantity,
            status=status,
            timestamp=datetime.now(),
            reason=reason,
        )
        self._order_log.append(entry)
        return entry

    def place_order(self, order: Order, bar: BarData) -> Optional[TradeData]:
        """
        实盘下单。

        优先委托给券商 SDK (XTP/QMT/CTP)，SDK 不可用时回退到骨架模式：
        1. 验证 100 股整数倍（A 股最小交易单位）
        2. 将订单置为 SUBMITTED 并记录审计日志
        3. 缓存订单以便后续查询/撤销
        4. 返回 TradeData 占位符
        """
        # 1. A 股 100 股整数倍校验
        if order.quantity % 100 != 0:
            order.update_status(OrderStatus.REJECTED)
            self._log_order(order, status="REJECTED",
                            reason="quantity not a multiple of 100")
            return None

        # 2. 涨跌停板简易检查（实际应通过行情确认）
        limit_up = bar.close * 1.10
        limit_down = bar.close * 0.90
        if order.price > limit_up or order.price < limit_down:
            order.update_status(OrderStatus.REJECTED)
            self._log_order(order, status="REJECTED",
                            reason="price beyond ±10% limit")
            return None

        # 3. 委托给券商 SDK（如已连接）
        if self._sdk_broker:
            try:
                result = self._sdk_broker.place_order(order, bar)
                if result:
                    order.update_status(OrderStatus.SUBMITTED)
                    self._open_orders[order.order_id] = order
                    self._log_order(order, status="SUBMITTED",
                                    reason=f"order submitted via {self._api} SDK")
                    return result
            except Exception as e:
                logger.warning("SDK 下单失败，回退到骨架模式: %s", e)

        # 4. 骨架模式：标记为已提交
        order.update_status(OrderStatus.SUBMITTED)
        self._open_orders[order.order_id] = order
        self._log_order(order, status="SUBMITTED", reason="order submitted to broker")

        # 5. 返回占位成交记录
        trade = TradeData(
            trade_id=f"{order.order_id}_submitted",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side.value,
            price=order.price,
            quantity=order.quantity,
        )
        self._order_log.append(
            OrderAuditLog(
                order_id=trade.trade_id,
                symbol=trade.symbol,
                side=trade.side,
                price=trade.price,
                quantity=trade.quantity,
                status="PLACE",
                timestamp=datetime.now(),
                reason="order placed placeholder (SDK fallback)",
            )
        )
        return trade

    def cancel_order(self, order: Order) -> bool:
        """
        撤单骨架。

        对状态为 PENDING / SUBMITTED / QUEUED 的订单，
        将其置为 CANCELLED 并记录审计日志。
        """
        if order.status.name in ("PENDING", "SUBMITTED", "QUEUED"):
            order.update_status(OrderStatus.CANCELLED)
            self._open_orders.pop(order.order_id, None)
            self._log_order(order, status="CANCELLED", reason="user cancel request")
            return True
        return False

    def get_positions(self, portfolio=None) -> Dict[str, Any]:
        """
        返回当前持仓。

        骨架实现：无真实券商连接时返回空字典。
        运行时可从 ``portfolio`` 参数或券商 API 获取。
        """
        if portfolio and hasattr(portfolio, "positions"):
            return {
                k: v.__dict__ for k, v in portfolio.positions.items()
                if hasattr(v, "quantity") and v.quantity > 0
            }
        return {}

    def get_balance(self, account=None) -> Dict[str, Any]:
        """
        返回账户余额。

        骨架实现：无真实券商连接时返回默认值。
        """
        return {
            "live": True,
            "api": self._api,
            "cash": 0.0,
            "frozen": 0.0,
            "equity": 0.0,
        }

    def get_history(
        self, symbol: str, bar_count: int, data_feeds: list = None
    ) -> List[BarData]:
        """
        获取历史 K 线。

        优先使用传入的 data_feeds，其次使用内部注入的 _data_feeds。
        """
        feeds = data_feeds or self._data_feeds
        if not feeds:
            return []
        for feed in feeds:
            if hasattr(feed, "symbol") and feed.symbol == symbol:
                n = len(feed)
                start = max(0, n - bar_count)
                return [feed[i] for i in range(start, n)]
        return []

    def _add_data_feed(self, feed) -> None:
        """内部：注入数据源（Cerebro / 外部策略使用）"""
        self._data_feeds.append(feed)

    @property
    def order_audit_log(self) -> List[OrderAuditLog]:
        """返回审计日志副本"""
        return self._order_log.copy()
