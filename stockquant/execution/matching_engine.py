# -*- coding: utf-8 -*-
"""#5 P0 任务：A 股仿真撮合引擎（增强版）

模拟沪深交易所的真实撮合规则：
- 集合竞价（9:15-9:25 开盘 / 14:57-15:00 收盘）
- 连续竞价（价格优先 + 时间优先）
- 涨跌停价格计算（主板 10% / 创业板科创板 20% / ST 5% / 北交所 30%）
- 部分成交处理
- 最小成交单位 100 股

本模块保留原有 F005/F012 的 SimulationMatchingEngine 等类（向后兼容），
新增 PriceLimitCalculator / MatchingOrder / MatchingQueue / MatchingEngine
以满足更细粒度的仿真需求。
"""

from __future__ import annotations

import json
import logging
import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.models.bar import BarData
from stockquant.models.trade import TradeData
from stockquant.events import EventType

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# 涨跌停计算（原有，保留）
# ═══════════════════════════════════════════════════════════════════

# A 股各板块涨跌停比例（根据股票代码前缀识别）
LIMIT_UP_RATIOS: Dict[str, float] = {
    "00": 0.10,       # 深交所主板
    "01": 0.10,       # 深交所主板
    "03": 0.20,       # 创业板（300开头）
    "30": 0.20,       # 创业板
    "60": 0.10,       # 上交所主板
    "68": 0.20,       # 科创板（688开头）
    "83": 0.30,       # 北交所
    "87": 0.30,
    "43": 0.30,
    "8": 0.30,        # 北交所（8开头）
}

DEFAULT_LIMIT_UP_RATIO = 0.10


class ASharePriceLimit:
    """A 股涨跌停价格计算

    根据股票代码前缀自动识别板块，返回涨跌停价格。
    """

    @staticmethod
    def get_ratio(symbol: str) -> float:
        """根据股票代码获取涨跌停比例"""
        if not symbol:
            return DEFAULT_LIMIT_UP_RATIO
        # 优先精确匹配 2 位前缀
        prefix2 = symbol[:2] if len(symbol) >= 2 else symbol
        if prefix2 in LIMIT_UP_RATIOS:
            return LIMIT_UP_RATIOS[prefix2]
        # 回退到 1 位前缀
        prefix1 = symbol[0]
        if prefix1 in LIMIT_UP_RATIOS:
            return LIMIT_UP_RATIOS[prefix1]
        return DEFAULT_LIMIT_UP_RATIO

    @staticmethod
    def calculate_limits(previous_close: float, symbol: str = "") -> Tuple[float, float]:
        """计算涨跌停价格（四舍五入到分）

        Returns:
            (limit_up_price, limit_down_price)
        """
        if previous_close <= 0:
            return (float('inf'), float('-inf'))
        ratio = ASharePriceLimit.get_ratio(symbol)
        up = round(previous_close * (1 + ratio), 2)
        down = round(previous_close * (1 - ratio), 2)
        return (up, down)

    @staticmethod
    def is_within_limits(price: float, previous_close: float, symbol: str = "") -> bool:
        """检查价格是否在涨跌停范围内"""
        if previous_close <= 0:
            return True
        up, down = ASharePriceLimit.calculate_limits(previous_close, symbol)
        return down <= price <= up


# ═══════════════════════════════════════════════════════════════════
# 新增：PriceLimitCalculator — 增强版涨跌停价格计算器
# ═══════════════════════════════════════════════════════════════════

class PriceLimitCalculator:
    """A 股涨跌停价格计算

    规则：
    - 主板（60xxxx/00xxxx 非 ST）：±10%
    - 创业板（30xxxx）：±20%
    - 科创板（688xxx）：±20%
    - ST/*ST（名称含 ST）：±5%
    - 北交所（8xxxxx/4xxxxx）：±30%
    - 新股上市首日（注册制）：无涨跌停（或 ±20% 取决板块）

    基于前收盘价计算涨跌停价格，四舍五入到 0.01 元。
    """

    # 各板块涨跌停比例
    _BOARD_RATIOS: Dict[str, float] = {
        "main_board": 0.10,    # 主板
        "gem": 0.20,           # 创业板
        "star": 0.20,          # 科创板
        "st": 0.05,            # ST
        "bse": 0.30,           # 北交所
    }

    @staticmethod
    def calculate(
        prev_close: float,
        symbol: str,
        name: str = "",
        is_new_ipo: bool = False,
        board_type: str = "",
    ) -> Tuple[float, float, float]:
        """计算涨跌停价格

        Args:
            prev_close: 前收盘价
            symbol: 股票代码
            name: 股票名称（用于检测 ST）
            is_new_ipo: 是否新股上市首日
            board_type: 板块类型（如已指定则跳过自动检测）

        Returns:
            (limit_up_price, limit_down_price, limit_ratio)
        """
        if prev_close <= 0:
            return (float('inf'), float('-inf'), 0.0)

        # 自动检测板块
        if not board_type:
            board_type = PriceLimitCalculator.detect_board_type(symbol, name)

        # 新股上市首日：注册制板块无涨跌停
        if is_new_ipo:
            if board_type in ("gem", "star"):
                return (float('inf'), 0.01, 0.0)

        ratio = PriceLimitCalculator._BOARD_RATIOS.get(board_type, 0.10)

        limit_up = round(prev_close * (1 + ratio), 2)
        limit_down = round(prev_close * (1 - ratio), 2)

        # 涨跌停价格不低于 0.01 元
        limit_down = max(limit_down, 0.01)

        return (limit_up, limit_down, ratio)

    @staticmethod
    def detect_board_type(symbol: str, name: str = "") -> str:
        """根据代码和名称判断板块类型

        Args:
            symbol: 股票代码
            name: 股票名称（用于 ST 检测）

        Returns:
            板块类型字符串: main_board / gem / star / st / bse
        """
        # ST 检测优先
        if name and ("ST" in name.upper()):
            return "st"

        if not symbol or len(symbol) < 1:
            return "main_board"

        # 科创板：688xxx
        if symbol.startswith("688"):
            return "star"

        # 创业板：30xxxx
        if symbol.startswith("30"):
            return "gem"

        # 北交所：8xxxxx / 4xxxxx
        if symbol.startswith("8") or symbol.startswith("4"):
            return "bse"

        # 主板
        return "main_board"

    @staticmethod
    def is_price_valid(price: float, limit_up: float, limit_down: float) -> bool:
        """检查价格是否在涨跌停范围内"""
        return limit_down <= price <= limit_up

    @staticmethod
    def round_to_tick(price: float, symbol: str = "") -> float:
        """价格取整到最小价格变动单位

        A 股规则：
        - 价格 < 1 元：最小变动 0.01 元（暂按 0.01 统一处理）
        - 价格 >= 1 元：< 10 元最小变动 0.01；>= 10 元最小变动 0.01
        简化：统一取整到 0.01 元（A股实际规则不同价位最小价位不同，仿真中统一0.01）
        """
        return round(price, 2)


# ═══════════════════════════════════════════════════════════════════
# 撮合队列原子单元（原有，保留）
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OrderEntry:
    """订单条目 — 撮合队列中的原子单元"""
    order_id: str
    symbol: str
    side: OrderSide
    price: float
    quantity: float
    timestamp: float
    filled_quantity: float = 0.0

    @property
    def remaining(self) -> float:
        """剩余可成交数量"""
        return max(0.0, self.quantity - self.filled_quantity)

    @property
    def filled_ratio(self) -> float:
        """已成交比例"""
        if self.quantity <= 0:
            return 1.0
        return self.filled_quantity / self.quantity

    def mark_filled(self, quantity: float) -> float:
        """标记部分成交，返回实际成交数量"""
        actual = min(quantity, self.remaining)
        self.filled_quantity += actual
        return actual


class OrderBook:
    """订单簿 — 价格优先 + 时间优先的限价订单簿"""

    def __init__(self):
        self._buy_orders: List[OrderEntry] = []    # 买单（价格降序）
        self._sell_orders: List[OrderEntry] = []   # 卖单（价格升序）
        self._order_map: Dict[str, OrderEntry] = {}
        self._by_symbol: Dict[str, Dict[str, OrderEntry]] = {}  # symbol -> {order_id: entry}

    @property
    def buy_count(self) -> int:
        return len([o for o in self._buy_orders if o.remaining > 0])

    @property
    def sell_count(self) -> int:
        return len([o for o in self._sell_orders if o.remaining > 0])

    @property
    def total_quantity(self) -> Dict[str, float]:
        """各价格档位的剩余数量（买降序 / 卖升序）"""
        buy = defaultdict(float)
        sell = defaultdict(float)
        for o in self._buy_orders:
            if o.remaining > 0:
                buy[o.price] += o.remaining
        for o in self._sell_orders:
            if o.remaining > 0:
                sell[o.price] += o.remaining
        return {
            "buy": dict(sorted(buy.items(), reverse=True)),
            "sell": dict(sorted(sell.items())),
        }

    @property
    def best_bid(self) -> Optional[float]:
        """最优买价（买一）"""
        for o in self._buy_orders:
            if o.remaining > 0:
                return o.price
        return None

    @property
    def best_ask(self) -> Optional[float]:
        """最优卖价（卖一）"""
        for o in self._sell_orders:
            if o.remaining > 0:
                return o.price
        return None

    def add_order(self, entry: OrderEntry) -> None:
        """添加订单到订单簿"""
        self._order_map[entry.order_id] = entry
        self._by_symbol.setdefault(entry.symbol, {})[entry.order_id] = entry
        if entry.side == OrderSide.BUY:
            self._insert_buy(entry)
        else:
            self._insert_sell(entry)

    def remove_order(self, order_id: str) -> Optional[OrderEntry]:
        """从订单簿移除订单（完全移除，非减少数量）"""
        entry = self._order_map.pop(order_id, None)
        if entry:
            self._by_symbol.get(entry.symbol, {}).pop(order_id, None)
            if entry.side == OrderSide.BUY:
                self._buy_orders = [o for o in self._buy_orders if o.order_id != order_id]
            else:
                self._sell_orders = [o for o in self._sell_orders if o.order_id != order_id]
        return entry

    def partial_cancel(self, order_id: str, cancel_quantity: float) -> bool:
        """部分撤单：取消指定数量"""
        entry = self._order_map.get(order_id)
        if not entry:
            return False
        if cancel_quantity >= entry.remaining:
            self.remove_order(order_id)
            return True
        entry.filled_quantity += cancel_quantity
        return True

    def get_order(self, order_id: str) -> Optional[OrderEntry]:
        """获取订单条目"""
        return self._order_map.get(order_id)

    def get_symbol_orders(self, symbol: str) -> Dict[str, OrderEntry]:
        """获取指定股票的所有订单"""
        return self._by_symbol.get(symbol, {}).copy()

    def clear_symbol(self, symbol: str) -> None:
        """清空指定股票的订单簿"""
        orders = self._by_symbol.pop(symbol, {})
        for order_id in orders:
            self._order_map.pop(order_id, None)
            if orders[order_id].side == OrderSide.BUY:
                self._buy_orders = [o for o in self._buy_orders if o.order_id != order_id]
            else:
                self._sell_orders = [o for o in self._sell_orders if o.order_id != order_id]

    def clear(self) -> None:
        """清空所有订单簿"""
        self._buy_orders.clear()
        self._sell_orders.clear()
        self._order_map.clear()
        self._by_symbol.clear()

    def _insert_buy(self, entry: OrderEntry) -> None:
        """插入买单（价格降序，价格相同时间优先）"""
        i = 0
        while i < len(self._buy_orders) and self._buy_orders[i].remaining > 0:
            if (self._buy_orders[i].price < entry.price or
                (self._buy_orders[i].price == entry.price and self._buy_orders[i].timestamp > entry.timestamp)):
                break
            i += 1
        self._buy_orders.insert(i, entry)

    def _insert_sell(self, entry: OrderEntry) -> None:
        """插入卖单（价格升序，价格相同时间优先）"""
        i = 0
        while i < len(self._sell_orders) and self._sell_orders[i].remaining > 0:
            if (self._sell_orders[i].price > entry.price or
                (self._sell_orders[i].price == entry.price and self._sell_orders[i].timestamp > entry.timestamp)):
                break
            i += 1
        self._sell_orders.insert(i, entry)


# ═══════════════════════════════════════════════════════════════════
# 新增：MatchingOrder — 撮合引擎内部订单
# ═══════════════════════════════════════════════════════════════════

@dataclass
class MatchingOrder:
    """撮合引擎内部订单"""
    order: Order                    # 原始订单
    priority_price: float           # 优先价格
    priority_time: float            # 优先时间（时间戳）
    is_buy: bool                    # 买/卖方向


# ═══════════════════════════════════════════════════════════════════
# 新增：MatchingQueue — 撮合队列
# ═══════════════════════════════════════════════════════════════════

class MatchingQueue:
    """价格-时间优先撮合队列

    买入：价格越高越优先（价格降序），同价格时间越早越优先
    卖出：价格越低越优先（价格升序），同价格时间越早越优先
    """

    def __init__(self, side: str):
        self._side = side  # "buy" or "sell"
        self._orders: List[MatchingOrder] = []

    def enqueue(self, order: Order) -> None:
        """入队（按价格+时间排序插入）"""
        mo = MatchingOrder(
            order=order,
            priority_price=order.price,
            priority_time=order.timestamps.get("created", datetime.now()).timestamp()
            if isinstance(order.timestamps.get("created"), datetime)
            else time.time(),
            is_buy=(order.side == OrderSide.BUY),
        )

        if self._side == "buy":
            # 买入：价格降序，同价格时间升序
            i = 0
            while i < len(self._orders):
                existing = self._orders[i]
                if (mo.priority_price > existing.priority_price or
                    (mo.priority_price == existing.priority_price and
                     mo.priority_time < existing.priority_time)):
                    break
                i += 1
            self._orders.insert(i, mo)
        else:
            # 卖出：价格升序，同价格时间升序
            i = 0
            while i < len(self._orders):
                existing = self._orders[i]
                if (mo.priority_price < existing.priority_price or
                    (mo.priority_price == existing.priority_price and
                     mo.priority_time < existing.priority_time)):
                    break
                i += 1
            self._orders.insert(i, mo)

    def dequeue(self) -> Optional[Order]:
        """出队最优订单"""
        while self._orders:
            mo = self._orders.pop(0)
            if mo.order.remaining > 0:
                return mo.order
        return None

    def peek(self) -> Optional[Order]:
        """查看但不移除最优订单"""
        for mo in self._orders:
            if mo.order.remaining > 0:
                return mo.order
        return None

    def remove(self, order_id: str) -> bool:
        """撤单"""
        for i, mo in enumerate(self._orders):
            if mo.order.order_id == order_id:
                self._orders.pop(i)
                return True
        return False

    def match(self, price: float, side: str, quantity: float) -> list:
        """在给定价格下撮合，返回 [(order, matched_qty), ...]

        Args:
            price: 撮合价格
            side: 吃单方向 "buy" 或 "sell"
            quantity: 吃单数量

        Returns:
            [(Order, matched_qty), ...]
        """
        results: list = []
        remaining = quantity

        for mo in list(self._orders):
            if remaining <= 0:
                break
            order = mo.order
            if order.remaining <= 0:
                continue

            if side == "buy":
                # 买入吃单：卖方报价 <= 买入价格才能成交
                if order.price > price:
                    continue
            else:
                # 卖出吃单：买方报价 >= 卖出价格才能成交
                if order.price < price:
                    continue

            matched = min(remaining, order.remaining)
            results.append((order, matched))
            remaining -= matched

        return results

    @property
    def size(self) -> int:
        return len(self._orders)

    def get_orders(self) -> list:
        return list(self._orders)

    def clear(self) -> None:
        self._orders.clear()


# ═══════════════════════════════════════════════════════════════════
# 集合竞价引擎（原有，保留）
# ═══════════════════════════════════════════════════════════════════

class CallAuctionEngine:
    """集合竞价引擎（开盘 + 收盘）"""

    OPEN_AUCTION_START = dt_time(9, 15, 0)
    OPEN_AUCTION_END = dt_time(9, 25, 0)
    CLOSE_AUCTION_START = dt_time(14, 57, 0)
    CLOSE_AUCTION_END = dt_time(15, 0, 0)

    @staticmethod
    def is_in_open_auction(current_time: dt_time) -> bool:
        """是否处于开盘集合竞价时段"""
        return CallAuctionEngine.OPEN_AUCTION_START <= current_time < CallAuctionEngine.OPEN_AUCTION_END

    @staticmethod
    def is_in_close_auction(current_time: dt_time) -> bool:
        """是否处于收盘集合竞价时段"""
        return CallAuctionEngine.CLOSE_AUCTION_START <= current_time < CallAuctionEngine.CLOSE_AUCTION_END

    @staticmethod
    def calculate_implementation_price(
        buy_orders: List[OrderEntry],
        sell_orders: List[OrderEntry],
    ) -> Optional[float]:
        """计算集合竞价成交价（最大成交量原则）"""
        if not buy_orders or not sell_orders:
            return None

        price_candidates = set()
        for o in buy_orders:
            if o.remaining > 0:
                price_candidates.add(o.price)
        for o in sell_orders:
            if o.remaining > 0:
                price_candidates.add(o.price)

        if not price_candidates:
            return None

        best_price = None
        best_volume = 0

        for price in sorted(price_candidates):
            buy_volume = sum(o.remaining for o in buy_orders if o.remaining > 0 and o.price >= price)
            sell_volume = sum(o.remaining for o in sell_orders if o.remaining > 0 and o.price <= price)
            volume = min(buy_volume, sell_volume)

            if volume > best_volume:
                best_volume = volume
                best_price = price
            elif volume == best_volume and price < best_price:
                best_price = price

        if best_volume <= 0:
            return None

        return round(best_price, 2)

    @staticmethod
    def execute_call_auction(
        buy_orders: List[OrderEntry],
        sell_orders: List[OrderEntry],
        auction_price: float,
    ) -> List[Tuple[OrderEntry, float]]:
        """执行集合竞价撮合"""
        if auction_price <= 0:
            return []

        filled: List[Tuple[OrderEntry, float]] = []

        for entry in buy_orders:
            if entry.remaining <= 0 or entry.side != OrderSide.BUY:
                continue
            if entry.price >= auction_price:
                executed = entry.mark_filled(entry.remaining)
                if executed > 0:
                    filled.append((entry, executed))

        for entry in sell_orders:
            if entry.remaining <= 0 or entry.side != OrderSide.SELL:
                continue
            if entry.price <= auction_price:
                executed = entry.mark_filled(entry.remaining)
                if executed > 0:
                    filled.append((entry, executed))

        return filled


# ═══════════════════════════════════════════════════════════════════
# 连续竞价撮合（原有，保留）
# ═══════════════════════════════════════════════════════════════════

class ContinuousMatchingEngine:
    """连续竞价撮合引擎"""

    def __init__(
        self,
        order_book: Optional[OrderBook] = None,
        slippage: float = 0.0,
        commission_rate: float = 0.00025,
        stamp_tax_rate: float = 0.0005,
        min_commission: float = 5.0,
    ):
        self._book = order_book or OrderBook()
        self._slippage = slippage
        self._commission_rate = commission_rate
        self._stamp_tax_rate = stamp_tax_rate
        self._min_commission = min_commission
        self._trade_log: List[TradeData] = []
        self._order_status: Dict[str, str] = {}
        self._next_trade_seq: int = 0

    @property
    def trade_log(self) -> List[TradeData]:
        return self._trade_log.copy()

    @property
    def book(self) -> OrderBook:
        return self._book

    @property
    def trade_count(self) -> int:
        return len(self._trade_log)

    @property
    def commission_rate(self) -> float:
        return self._commission_rate

    @property
    def stamp_tax_rate(self) -> float:
        return self._stamp_tax_rate

    def submit_order(
        self,
        order: Order,
        symbol: str,
        previous_close: float = 0.0,
    ) -> bool:
        """提交订单到撮合引擎（前置校验）"""
        if order.quantity % 100 != 0:
            self._order_status[order.order_id] = EventType.ORDER_REJECTED.value
            return False

        if previous_close > 0:
            if not ASharePriceLimit.is_within_limits(order.price, previous_close, symbol):
                self._order_status[order.order_id] = EventType.ORDER_REJECTED.value
                return False

        if order.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT, OrderType.STOP):
            if order.price <= 0:
                self._order_status[order.order_id] = EventType.ORDER_REJECTED.value
                return False

        self._order_status[order.order_id] = EventType.ORDER_SUBMITTED.value
        return True

    def match_order(
        self,
        new_order: Order,
        symbol: str,
        previous_close: float = 0.0,
    ) -> List[TradeData]:
        """将新订单与现有订单簿撮合"""
        side = new_order.side
        price = new_order.price
        remaining_qty = new_order.quantity

        trades: List[TradeData] = []

        if new_order.order_type == OrderType.MARKET:
            if side == OrderSide.BUY:
                trades = self._match_market_buy(symbol, remaining_qty, previous_close)
            else:
                trades = self._match_market_sell(symbol, remaining_qty, previous_close)

        elif new_order.order_type == OrderType.LIMIT:
            if side == OrderSide.BUY:
                trades = self._match_limit_buy(price, symbol, remaining_qty, previous_close)
            else:
                trades = self._match_limit_sell(price, symbol, remaining_qty, previous_close)

        elif new_order.order_type in (OrderType.STOP, OrderType.STOP_LIMIT):
            trades = self._match_limit_buy(price, symbol, remaining_qty, previous_close)

        if trades:
            total_filled = sum(t.quantity for t in trades)
            remaining_qty -= total_filled

            if remaining_qty <= 0:
                self._order_status[new_order.order_id] = EventType.ORDER_FILLED.value
            else:
                entry = OrderEntry(
                    order_id=new_order.order_id,
                    symbol=symbol,
                    side=side,
                    price=price,
                    quantity=remaining_qty,
                    timestamp=time.time(),
                )
                self._book.add_order(entry)
                self._order_status[new_order.order_id] = EventType.ORDER_PARTIAL_FILL.value
        else:
            entry = OrderEntry(
                order_id=new_order.order_id,
                symbol=symbol,
                side=side,
                price=price,
                quantity=remaining_qty,
                timestamp=time.time(),
            )
            self._book.add_order(entry)
            self._order_status[new_order.order_id] = EventType.ORDER_PENDING.value

        return trades

    def _match_limit_buy(
        self,
        limit_price: float,
        symbol: str,
        qty: float,
        previous_close: float,
    ) -> List[TradeData]:
        """限价买入：与卖单簿中价格 <= 限价的所有订单撮合"""
        trades: List[TradeData] = []
        remaining = qty

        for entry in list(self._book._sell_orders):
            if remaining <= 0 or entry.remaining <= 0:
                break
            if entry.price <= limit_price:
                if previous_close > 0:
                    up, _ = ASharePriceLimit.calculate_limits(previous_close, symbol)
                    if entry.price > up:
                        continue

                executed = entry.mark_filled(remaining)
                if executed > 0:
                    trade = self._create_trade(entry, executed, entry.price, symbol, OrderSide.BUY)
                    trades.append(trade)
                    remaining -= executed
                    if entry.remaining <= 0:
                        self._book.remove_order(entry.order_id)

        return trades

    def _match_limit_sell(
        self,
        limit_price: float,
        symbol: str,
        qty: float,
        previous_close: float,
    ) -> List[TradeData]:
        """限价卖出：与买单簿中价格 >= 限价的所有订单撮合"""
        trades: List[TradeData] = []
        remaining = qty

        for entry in list(self._book._buy_orders):
            if remaining <= 0 or entry.remaining <= 0:
                break
            if entry.price >= limit_price:
                if previous_close > 0:
                    _, down = ASharePriceLimit.calculate_limits(previous_close, symbol)
                    if entry.price < down:
                        continue

                executed = entry.mark_filled(remaining)
                if executed > 0:
                    trade = self._create_trade(entry, executed, limit_price, symbol)
                    trades.append(trade)
                    remaining -= executed
                    if entry.remaining <= 0:
                        self._book.remove_order(entry.order_id)

        return trades

    def _match_market_buy(
        self,
        symbol: str,
        qty: float,
        previous_close: float,
    ) -> List[TradeData]:
        """市价买入：与卖单簿中所有订单撮合（受涨跌停限制）"""
        trades: List[TradeData] = []
        remaining = qty

        for entry in list(self._book._sell_orders):
            if remaining <= 0 or entry.remaining <= 0:
                break
            if previous_close > 0:
                up, _ = ASharePriceLimit.calculate_limits(previous_close, symbol)
                if entry.price > up:
                    continue
            executed = entry.mark_filled(remaining)
            if executed > 0:
                trade = self._create_trade(entry, executed, entry.price, symbol)
                trades.append(trade)
                remaining -= executed
                if entry.remaining <= 0:
                    self._book.remove_order(entry.order_id)

        return trades

    def _match_market_sell(
        self,
        symbol: str,
        qty: float,
        previous_close: float,
    ) -> List[TradeData]:
        """市价卖出：与买单簿中所有订单撮合"""
        trades: List[TradeData] = []
        remaining = qty

        for entry in list(self._book._buy_orders):
            if remaining <= 0 or entry.remaining <= 0:
                break
            if previous_close > 0:
                _, down = ASharePriceLimit.calculate_limits(previous_close, symbol)
                if entry.price < down:
                    continue
            executed = entry.mark_filled(remaining)
            if executed > 0:
                trade = self._create_trade(entry, executed, entry.price, symbol)
                trades.append(trade)
                remaining -= executed
                if entry.remaining <= 0:
                    self._book.remove_order(entry.order_id)

        return trades

    def _create_trade(
        self,
        entry: OrderEntry,
        executed_qty: float,
        exec_price: float,
        symbol: str,
        side: OrderSide = None,
    ) -> TradeData:
        """创建成交记录"""
        self._next_trade_seq += 1
        trade = TradeData(
            trade_id=f"{symbol}_t{self._next_trade_seq}",
            order_id=entry.order_id,
            symbol=symbol,
            side=(side or entry.side).value,
            price=exec_price,
            quantity=executed_qty,
            commission=self._calculate_commission(exec_price * executed_qty),
            timestamp=time.time(),
        )
        self._trade_log.append(trade)
        return trade

    def _calculate_commission(self, amount: float) -> float:
        """计算手续费"""
        commission = amount * self._commission_rate
        return max(commission, self._min_commission)

    def cancel_order(self, order_id: str) -> bool:
        """完全撤单"""
        entry = self._book.remove_order(order_id)
        if entry:
            self._order_status[order_id] = EventType.ORDER_CANCELLED.value
            return True
        return False

    def partial_cancel_order(
        self, order_id: str, cancel_quantity: float
    ) -> bool:
        """部分撤单：取消指定数量"""
        entry = self._book.get_order(order_id)
        if not entry or cancel_quantity <= 0:
            return False

        if cancel_quantity >= entry.remaining:
            return self.cancel_order(order_id)

        return self._book.partial_cancel(order_id, cancel_quantity)

    def get_order_status(self, order_id: str) -> str:
        """获取订单状态"""
        return self._order_status.get(order_id, EventType.ORDER_PENDING.value)

    def clear(self, symbol: str = None) -> None:
        """清空订单簿"""
        if symbol:
            self._book.clear_symbol(symbol)
        else:
            self._book.clear()
            self._order_status.clear()


# ═══════════════════════════════════════════════════════════════════
# 新增：MatchingEngine — 撮合引擎主体
# ═══════════════════════════════════════════════════════════════════

class MatchingEngine:
    """A 股仿真撮合引擎

    支持两种撮合模式：
    1. 集合竞价（Call Auction）：收集所有订单，计算开盘/收盘价
    2. 连续竞价（Continuous Matching）：逐笔撮合，价格优先+时间优先

    使用方式：
        engine = MatchingEngine(symbol="000001", prev_close=10.0)

        # 集合竞价阶段
        engine.enter_call_auction_phase()
        engine.accept_order(order1)
        engine.accept_order(order2)
        trades = engine.resolve_call_auction()  # 计算开盘价并撮合

        # 连续竞价阶段
        engine.enter_continuous_phase()
        trades = engine.match_tick(bar)  # 用最新 tick/bar 撮合
    """

    # 阶段常量
    PHASE_CLOSED = "closed"
    PHASE_CALL_AUCTION = "call_auction"
    PHASE_CONTINUOUS = "continuous"

    def __init__(self, symbol: str, prev_close: float, name: str = "", board_type: str = ""):
        self._symbol = symbol
        self._prev_close = prev_close
        self._name = name
        self._board_type = board_type or PriceLimitCalculator.detect_board_type(symbol, name)

        # 涨跌停价格
        self._limit_up, self._limit_down, self._limit_ratio = PriceLimitCalculator.calculate(
            prev_close, symbol, name, board_type=self._board_type
        )

        # 阶段
        self._phase = self.PHASE_CLOSED

        # 撮合队列
        self._buy_queue = MatchingQueue("buy")
        self._sell_queue = MatchingQueue("sell")

        # 集合竞价暂存
        self._auction_buy_orders: List[MatchingOrder] = []
        self._auction_sell_orders: List[MatchingOrder] = []

        # 成交记录
        self._trades: List[Tuple[Order, TradeData]] = []
        self._trade_seq: int = 0

        # 统计
        self._total_trades = 0
        self._total_volume = 0.0
        self._total_turnover = 0.0

        # 线程锁
        self._lock = threading.Lock()

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def limit_up(self) -> float:
        return self._limit_up

    @property
    def limit_down(self) -> float:
        return self._limit_down

    @property
    def limit_ratio(self) -> float:
        return self._limit_ratio

    @property
    def statistics(self) -> dict:
        """撮合统计信息"""
        return {
            "symbol": self._symbol,
            "phase": self._phase,
            "prev_close": self._prev_close,
            "limit_up": self._limit_up,
            "limit_down": self._limit_down,
            "limit_ratio": self._limit_ratio,
            "board_type": self._board_type,
            "total_trades": self._total_trades,
            "total_volume": self._total_volume,
            "total_turnover": round(self._total_turnover, 2),
            "buy_queue_size": self._buy_queue.size,
            "sell_queue_size": self._sell_queue.size,
        }

    def enter_call_auction_phase(self) -> None:
        """进入集合竞价阶段"""
        with self._lock:
            self._phase = self.PHASE_CALL_AUCTION
            self._auction_buy_orders.clear()
            self._auction_sell_orders.clear()

    def enter_continuous_phase(self) -> None:
        """进入连续竞价阶段"""
        with self._lock:
            self._phase = self.PHASE_CONTINUOUS
            # 将集合竞价未成交订单转入连续竞价队列
            for mo in self._auction_buy_orders:
                if mo.order.remaining > 0:
                    self._buy_queue.enqueue(mo.order)
            for mo in self._auction_sell_orders:
                if mo.order.remaining > 0:
                    self._sell_queue.enqueue(mo.order)
            self._auction_buy_orders.clear()
            self._auction_sell_orders.clear()

    def accept_order(self, order: Order) -> bool:
        """接收订单（根据当前阶段处理）

        Returns:
            True 如果订单被接受，False 如果被拒绝
        """
        with self._lock:
            # 基本校验
            if not self._validate_order(order):
                return False

            if self._phase == self.PHASE_CALL_AUCTION:
                self._accept_auction_order(order)
            elif self._phase == self.PHASE_CONTINUOUS:
                self._accept_continuous_order(order)
            else:
                return False

            return True

    def _validate_order(self, order: Order) -> bool:
        """订单基本校验"""
        # 100 股整数倍
        if order.quantity % 100 != 0:
            order.update_status(EventType.ORDER_REJECTED.value)
            return False

        # 限价单价格校验
        if order.order_type == OrderType.LIMIT:
            if order.price <= 0:
                order.update_status(EventType.ORDER_REJECTED.value)
                return False

            # 涨跌停校验
            if not PriceLimitCalculator.is_price_valid(
                order.price, self._limit_up, self._limit_down
            ):
                order.update_status(EventType.ORDER_REJECTED.value)
                return False

        # 市价单无需价格校验
        if order.order_type == OrderType.MARKET:
            pass

        order.update_status(EventType.ORDER_SUBMITTED.value)
        return True

    def _accept_auction_order(self, order: Order) -> None:
        """集合竞价阶段接收订单"""
        ts = time.time()
        mo = MatchingOrder(
            order=order,
            priority_price=order.price,
            priority_time=ts,
            is_buy=(order.side == OrderSide.BUY),
        )

        if order.side == OrderSide.BUY:
            self._auction_buy_orders.append(mo)
        else:
            self._auction_sell_orders.append(mo)

    def _accept_continuous_order(self, order: Order) -> None:
        """连续竞价阶段接收订单"""
        # 市价单立即撮合
        if order.order_type == OrderType.MARKET:
            self._match_market_order(order)
        else:
            # 限价单入队
            if order.side == OrderSide.BUY:
                self._buy_queue.enqueue(order)
            else:
                self._sell_queue.enqueue(order)
            order.update_status(EventType.ORDER_PENDING.value)

    def resolve_call_auction(self) -> list:
        """集合竞价撮合 — 计算开盘/收盘价并撮合

        原则：
        1. 可实现最大成交量的价格
        2. 高于该价格的买单和低于该价格的卖单全部成交
        3. 至少有一方全部成交
        4. 如有多个满足条件的价格，取使未成交量最小的
        5. 如仍有多个，取使买卖双方累积成交量最小的（最近成交量）

        Returns:
            [(order, trade_data), ...]
        """
        with self._lock:
            if self._phase != self.PHASE_CALL_AUCTION:
                return []

            if not self._auction_buy_orders or not self._auction_sell_orders:
                return []

            # 收集所有可能的价格点
            price_candidates = set()
            for mo in self._auction_buy_orders:
                if mo.order.remaining > 0:
                    price_candidates.add(mo.order.price)
            for mo in self._auction_sell_orders:
                if mo.order.remaining > 0:
                    price_candidates.add(mo.order.price)

            if not price_candidates:
                return []

            # 计算每个价格的可成交量
            price_volumes: Dict[float, int] = {}
            for price in sorted(price_candidates):
                buy_vol = sum(
                    mo.order.remaining for mo in self._auction_buy_orders
                    if mo.order.remaining > 0 and mo.order.price >= price
                )
                sell_vol = sum(
                    mo.order.remaining for mo in self._auction_sell_orders
                    if mo.order.remaining > 0 and mo.order.price <= price
                )
                price_volumes[price] = min(buy_vol, sell_vol)

            # 最大成交量
            max_vol = max(price_volumes.values()) if price_volumes else 0
            if max_vol <= 0:
                return []

            # 筛选最大成交量对应的价格
            best_prices = [p for p, v in price_volumes.items() if v == max_vol]

            # 取中间价（更接近前收盘价）
            auction_price = best_prices[0]
            if len(best_prices) > 1:
                # 原则4：取未成交量最小的
                def _unmatched_volume(p):
                    buy_unmatched = sum(
                        mo.order.remaining for mo in self._auction_buy_orders
                        if mo.order.remaining > 0 and mo.order.price >= p
                    )
                    sell_unmatched = sum(
                        mo.order.remaining for mo in self._auction_sell_orders
                        if mo.order.remaining > 0 and mo.order.price <= p
                    )
                    return abs(buy_unmatched - sell_unmatched)

                best_prices.sort(key=_unmatched_volume)
                auction_price = best_prices[0]

            auction_price = PriceLimitCalculator.round_to_tick(auction_price, self._symbol)

            # 按开盘价撮合
            results = []
            for mo in self._auction_buy_orders:
                order = mo.order
                if order.remaining <= 0:
                    continue
                if order.price >= auction_price:
                    filled_qty = min(order.remaining, auction_price)
                    # 实际可成交数量
                    trade = self._create_trade(order, filled_qty, auction_price)
                    order.add_fill(filled_qty, auction_price)
                    results.append((order, trade))

            for mo in self._auction_sell_orders:
                order = mo.order
                if order.remaining <= 0:
                    continue
                if order.price <= auction_price:
                    filled_qty = min(order.remaining, auction_price)
                    trade = self._create_trade(order, filled_qty, auction_price)
                    order.add_fill(filled_qty, auction_price)
                    results.append((order, trade))

            return results

    def match_tick(self, bar: BarData) -> list:
        """连续竞价撮合 — 用最新行情逐笔撮合

        1. 检查所有挂单是否在涨跌停范围内
        2. 市价单立即以当前最优价格撮合
        3. 限价单按价格+时间优先撮合
        4. 支持部分成交
        5. 返回成交列表 [(order, trade), ...]
        """
        with self._lock:
            if self._phase != self.PHASE_CONTINUOUS:
                return []

            results = []

            # 更新涨跌停（用 bar.close 作为新基准）
            if bar.close > 0:
                self._limit_up, self._limit_down, self._limit_ratio = PriceLimitCalculator.calculate(
                    self._prev_close, self._symbol, self._name, board_type=self._board_type
                )

            # 用 bar 的 high/low/close 来驱动撮合
            # 使用 close 作为基准价格撮合限价单
            current_price = PriceLimitCalculator.round_to_tick(bar.close, self._symbol)

            # 检查买单队列：如果 current_price <= 买单价格，尝试撮合
            results.extend(self._match_buy_orders(current_price))

            # 检查卖单队列：如果 current_price >= 卖单价格，尝试撮合
            results.extend(self._match_sell_orders(current_price))

            return results

    def _match_market_order(self, order: Order) -> list:
        """撮合市价单（立即以最优价格成交）"""
        results = []
        remaining = order.quantity

        if order.side == OrderSide.BUY:
            # 吃卖单队列
            for mo in list(self._sell_queue.get_orders()):
                if remaining <= 0:
                    break
                if mo.order.remaining <= 0:
                    continue
                matched = min(remaining, mo.order.remaining)
                trade = self._create_trade(mo.order, matched, mo.order.price)
                mo.order.add_fill(matched, mo.order.price)
                order.add_fill(matched, mo.order.price)
                results.append((mo.order, trade))
                remaining -= matched
                if mo.order.remaining <= 0:
                    self._sell_queue.remove(mo.order.order_id)

            # 未成交部分：市价单不挂单，标记为已完成或部分成交
            if remaining > 0:
                order.update_status(EventType.ORDER_PARTIAL_FILL.value)
            else:
                order.update_status(EventType.ORDER_FILLED.value)
        else:
            # 吃买单队列
            for mo in list(self._buy_queue.get_orders()):
                if remaining <= 0:
                    break
                if mo.order.remaining <= 0:
                    continue
                matched = min(remaining, mo.order.remaining)
                trade = self._create_trade(mo.order, matched, mo.order.price)
                mo.order.add_fill(matched, mo.order.price)
                order.add_fill(matched, mo.order.price)
                results.append((mo.order, trade))
                remaining -= matched
                if mo.order.remaining <= 0:
                    self._buy_queue.remove(mo.order.order_id)

            if remaining > 0:
                order.update_status(EventType.ORDER_PARTIAL_FILL.value)
            else:
                order.update_status(EventType.ORDER_FILLED.value)

        return results

    def _match_buy_orders(self, current_price: float) -> list:
        """撮合买单队列（当市场价格 <= 买单限价时成交）"""
        results = []

        for mo in list(self._buy_queue.get_orders()):
            order = mo.order
            if order.remaining <= 0:
                continue

            # 买单价格 >= 当前市场价格 -> 可以成交
            if order.price >= current_price:
                matched = order.remaining  # 全部成交
                trade = self._create_trade(order, matched, current_price)
                order.add_fill(matched, current_price)
                results.append((order, trade))

                self._buy_queue.remove(order.order_id)
                order.update_status(EventType.ORDER_FILLED.value)

        return results

    def _match_sell_orders(self, current_price: float) -> list:
        """撮合卖单队列（当市场价格 >= 卖单限价时成交）"""
        results = []

        for mo in list(self._sell_queue.get_orders()):
            order = mo.order
            if order.remaining <= 0:
                continue

            # 卖单价格 <= 当前市场价格 -> 可以成交
            if order.price <= current_price:
                matched = order.remaining  # 全部成交
                trade = self._create_trade(order, matched, current_price)
                order.add_fill(matched, current_price)
                results.append((order, trade))

                self._sell_queue.remove(order.order_id)
                order.update_status(EventType.ORDER_FILLED.value)

        return results

    def _create_trade(self, order: Order, quantity: float, price: float) -> TradeData:
        """创建成交记录"""
        self._trade_seq += 1
        self._total_trades += 1
        self._total_volume += quantity
        self._total_turnover += price * quantity

        trade = TradeData(
            trade_id=f"{self._symbol}_me{self._trade_seq}",
            order_id=order.order_id,
            symbol=self._symbol,
            side=order.side.value,
            price=round(price, 2),
            quantity=quantity,
            timestamp=time.time(),
        )
        self._trades.append((order, trade))
        return trade

    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        with self._lock:
            # 连续竞价队列撤单
            if self._buy_queue.remove(order_id):
                return True
            if self._sell_queue.remove(order_id):
                return True

            # 集合竞价撤单
            for mo in self._auction_buy_orders:
                if mo.order.order_id == order_id:
                    self._auction_buy_orders.remove(mo)
                    return True
            for mo in self._auction_sell_orders:
                if mo.order.order_id == order_id:
                    self._auction_sell_orders.remove(mo)
                    return True

            return False

    def get_order_book(self) -> dict:
        """获取订单簿快照 {bids: [{price, qty, count}], asks: [...]}"""
        with self._lock:
            bids = defaultdict(lambda: {"qty": 0.0, "count": 0})
            asks = defaultdict(lambda: {"qty": 0.0, "count": 0})

            for mo in self._buy_queue.get_orders():
                if mo.order.remaining > 0:
                    key = mo.order.price
                    bids[key]["qty"] += mo.order.remaining
                    bids[key]["count"] += 1

            for mo in self._sell_queue.get_orders():
                if mo.order.remaining > 0:
                    key = mo.order.price
                    asks[key]["qty"] += mo.order.remaining
                    asks[key]["count"] += 1

            bid_list = [
                {"price": p, "qty": round(v["qty"], 2), "count": v["count"]}
                for p, v in sorted(bids.items(), reverse=True)
            ]
            ask_list = [
                {"price": p, "qty": round(v["qty"], 2), "count": v["count"]}
                for p, v in sorted(asks.items())
            ]

            return {"bids": bid_list, "asks": ask_list}


# ═══════════════════════════════════════════════════════════════════
# 仿真撮合引擎 — 统一入口（原有，保留）
# ═══════════════════════════════════════════════════════════════════

class SimulationMatchingEngine:
    """仿真撮合引擎 — 统一入口类"""

    def __init__(
        self,
        initial_cash: float = 1_000_000.0,
        slippage: float = 0.0,
        commission_rate: float = 0.00025,
        stamp_tax_rate: float = 0.0005,
        min_commission: float = 5.0,
        state_file: Optional[str] = None,
    ):
        self._continuous = ContinuousMatchingEngine(
            slippage=slippage,
            commission_rate=commission_rate,
            stamp_tax_rate=stamp_tax_rate,
            min_commission=min_commission,
        )
        self._auction = CallAuctionEngine()
        self._call_auction_book: Dict[str, Tuple[List[OrderEntry], List[OrderEntry]]] = {}
        self._cash = initial_cash
        self._frozen_cash = 0.0
        self._initial_cash = initial_cash
        self._positions: Dict[str, Dict[str, Any]] = {}
        self._trade_log: List[TradeData] = []
        self._event_log: List[Dict[str, Any]] = []
        self._previous_close_map: Dict[str, float] = {}
        if state_file:
            self.load_state(state_file)

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def initial_cash(self) -> float:
        return self._initial_cash

    @property
    def frozen_cash(self) -> float:
        return self._frozen_cash

    @property
    def available_cash(self) -> float:
        return self._cash - self._frozen_cash

    @property
    def positions(self) -> Dict[str, Dict[str, Any]]:
        return {k: dict(v) for k, v in self._positions.items()}

    @property
    def trade_log(self) -> List[TradeData]:
        return self._trade_log.copy()

    @property
    def book(self) -> OrderBook:
        return self._continuous.book

    @property
    def previous_close_map(self) -> Dict[str, float]:
        return self._previous_close_map.copy()

    def submit_order(
        self,
        order: Order,
        symbol: str,
        previous_close: float = 0.0,
    ) -> bool:
        """提交订单（前置校验 + 资金冻结）"""
        if previous_close > 0:
            if not ASharePriceLimit.is_within_limits(order.price, previous_close, symbol):
                self._log_event(order.order_id, symbol, "REJECTED",
                                f"price {order.price} out of limits [{previous_close}]")
                return False

        if order.quantity % 100 != 0:
            self._log_event(order.order_id, symbol, "REJECTED",
                            "quantity not multiple of 100")
            return False

        if order.side == OrderSide.BUY:
            required = order.price * order.quantity
            if required > self._cash:
                self._log_event(order.order_id, symbol, "REJECTED",
                                f"insufficient cash: need {required:.2f}, have {self._cash:.2f}")
                return False
            self._frozen_cash += required

        self._previous_close_map.setdefault(symbol, previous_close)
        self._log_event(order.order_id, symbol, "SUBMITTED",
                        f"{order.side.value} {order.quantity} @ {order.price}")
        return True

    def match_continuous(
        self,
        order: Order,
        symbol: str,
        previous_close: float = 0.0,
    ) -> List[TradeData]:
        """执行连续竞价撮合"""
        if previous_close > 0:
            self._previous_close_map[symbol] = previous_close

        trades = self._continuous.match_order(order, symbol, previous_close)

        for trade in trades:
            self._process_fill(trade)

        self._trade_log.extend(trades)
        return trades

    def add_auction_order(
        self,
        order_id: str,
        symbol: str,
        side: OrderSide,
        price: float,
        quantity: float,
    ) -> None:
        """添加集合竞价订单到临时队列"""
        entry = OrderEntry(
            order_id=order_id,
            symbol=symbol,
            side=side,
            price=price,
            quantity=quantity,
            timestamp=time.time(),
        )

        if symbol not in self._call_auction_book:
            self._call_auction_book[symbol] = ([], [])

        buys, sells = self._call_auction_book[symbol]
        if side == OrderSide.BUY:
            buys.append(entry)
        else:
            sells.append(entry)

    def execute_call_auction(self, symbol: str) -> Optional[List[TradeData]]:
        """执行指定股票的集合竞价撮合"""
        if symbol not in self._call_auction_book:
            return None

        buys, sells = self._call_auction_book[symbol]
        if not buys or not sells:
            return None

        auction_price = self._auction.calculate_implementation_price(buys, sells)
        if auction_price is None:
            return None

        filled = self._auction.execute_call_auction(buys, sells, auction_price)
        if not filled:
            return None

        trades: List[TradeData] = []
        for entry, executed_qty in filled:
            trade = TradeData(
                trade_id=f"{symbol}_auction_{entry.order_id}",
                order_id=entry.order_id,
                symbol=symbol,
                side=entry.side.value,
                price=auction_price,
                quantity=executed_qty,
                timestamp=time.time(),
            )
            trades.append(trade)
            self._process_fill(trade)

        self._trade_log.extend(trades)
        self._call_auction_book.pop(symbol, None)
        return trades

    def clear_auction_book(self, symbol: str = None) -> None:
        """清空集合竞价订单簿"""
        if symbol:
            self._call_auction_book.pop(symbol, None)
        else:
            self._call_auction_book.clear()

    def cancel_order(self, order_id: str) -> bool:
        """撤单（完全撤单）"""
        if self._continuous.cancel_order(order_id):
            entry = self._book.get_order(order_id)
            if entry and entry.side == OrderSide.BUY:
                self._frozen_cash = max(0, self._frozen_cash - entry.price * entry.remaining)
            self._log_event(order_id, entry.symbol if entry else "", "CANCELLED", "")
            return True

        if order_id in str(self._call_auction_book):
            for symbol in list(self._call_auction_book.keys()):
                buys, sells = self._call_auction_book[symbol]
                for o_list in (buys, sells):
                    original_len = len(o_list)
                    o_list[:] = [e for e in o_list if e.order_id != order_id]
                    if len(o_list) < original_len:
                        self._log_event(order_id, symbol, "CANCELLED", "from auction")
                        return True

        return False

    def partial_cancel(
        self, order_id: str, cancel_quantity: float
    ) -> bool:
        """部分撤单"""
        entry = self._book.get_order(order_id)
        if not entry or cancel_quantity <= 0 or cancel_quantity > entry.remaining:
            return False

        if cancel_quantity >= entry.remaining:
            return self.cancel_order(order_id)

        remaining = entry.remaining - cancel_quantity
        self._continuous._book.partial_cancel(order_id, cancel_quantity)

        if entry.side == OrderSide.BUY:
            self._frozen_cash = max(0, self._frozen_cash - entry.price * cancel_quantity)

        self._log_event(order_id, entry.symbol, "PARTIAL_CANCEL",
                        f"cancelled {cancel_quantity} of {remaining + cancel_quantity}")
        return True

    def on_bar(self, bar: BarData) -> List[TradeData]:
        """接收K线数据，处理挂单撮合"""
        symbol = bar.symbol
        trades: List[TradeData] = []

        self._previous_close_map[symbol] = bar.close

        current_time = bar.datetime.time() if bar.datetime else None

        if current_time:
            if not CallAuctionEngine.is_in_open_auction(current_time) and not CallAuctionEngine.is_in_close_auction(current_time):
                symbol_orders = self._book.get_symbol_orders(symbol)
                for order_id, entry in list(symbol_orders.items()):
                    if entry.remaining <= 0:
                        continue
                    if entry.side == OrderSide.BUY and entry.price >= bar.low:
                        new_order = Order(
                            symbol=symbol,
                            side=OrderSide.BUY,
                            order_type=OrderType.LIMIT,
                            price=entry.price,
                            quantity=entry.remaining,
                            order_id=order_id,
                        )
                        t = self._continuous.match_order(new_order, symbol, bar.close)
                        for trade in t:
                            trade.order_id = order_id
                            trades.append(trade)
                            self._process_fill(trade)
                    elif entry.side == OrderSide.SELL and entry.price <= bar.high:
                        new_order = Order(
                            symbol=symbol,
                            side=OrderSide.SELL,
                            order_type=OrderType.LIMIT,
                            price=entry.price,
                            quantity=entry.remaining,
                            order_id=order_id,
                        )
                        t = self._continuous.match_order(new_order, symbol, bar.close)
                        for trade in t:
                            trade.order_id = order_id
                            trades.append(trade)
                            self._process_fill(trade)

        self._trade_log.extend(trades)
        return trades

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """获取投资组合摘要"""
        market_value = sum(
            p.get("market_value", 0.0) for p in self._positions.values()
        )
        total_equity = self._cash + self._frozen_cash + market_value
        pnl = total_equity - self._initial_cash
        pnl_pct = (pnl / self._initial_cash * 100) if self._initial_cash > 0 else 0

        return {
            "initial_cash": self._initial_cash,
            "available_cash": self._cash,
            "frozen_cash": self._frozen_cash,
            "total_cash": self._cash + self._frozen_cash,
            "market_value": market_value,
            "total_equity": total_equity,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "num_positions": len([p for p in self._positions.values() if p.get("quantity", 0) > 0]),
            "total_trades": len(self._trade_log),
            "num_buy_trades": len([t for t in self._trade_log if t.side == OrderSide.BUY.value]),
            "num_sell_trades": len([t for t in self._trade_log if t.side == OrderSide.SELL.value]),
            "positions": {
                sym: {
                    "quantity": p.get("quantity", 0),
                    "cost_price": p.get("cost_price", 0),
                    "current_price": p.get("current_price", 0),
                    "market_value": p.get("market_value", 0),
                    "unrealized_pnl": p.get("unrealized_pnl", 0),
                }
                for sym, p in self._positions.items()
            },
        }

    def _process_fill(self, trade: TradeData) -> None:
        """处理成交后的资金和持仓变动"""
        if trade.side == OrderSide.BUY.value:
            cost = trade.price * trade.quantity
            self._cash -= cost

            if trade.symbol not in self._positions:
                self._positions[trade.symbol] = {
                    "quantity": 0.0,
                    "cost_price": 0.0,
                    "current_price": 0.0,
                    "unrealized_pnl": 0.0,
                }

            pos = self._positions[trade.symbol]
            total_cost = pos["cost_price"] * pos["quantity"] + cost
            pos["quantity"] += trade.quantity
            pos["cost_price"] = total_cost / pos["quantity"] if pos["quantity"] > 0 else 0
            pos["current_price"] = trade.price
            pos["market_value"] = pos["quantity"] * pos["current_price"]
            pos["unrealized_pnl"] = (pos["current_price"] - pos["cost_price"]) * pos["quantity"]

        elif trade.side == OrderSide.SELL.value:
            revenue = trade.price * trade.quantity
            self._cash += revenue

            if trade.symbol in self._positions:
                pos = self._positions[trade.symbol]
                realized = (trade.price - pos["cost_price"]) * min(trade.quantity, pos["quantity"])
                pos["quantity"] -= trade.quantity
                if pos["quantity"] > 0:
                    pos["current_price"] = trade.price
                    pos["market_value"] = pos["quantity"] * pos["current_price"]
                    pos["unrealized_pnl"] = (pos["current_price"] - pos["cost_price"]) * pos["quantity"]
                else:
                    pos["unrealized_pnl"] = realized
                    pos["market_value"] = 0

    def _log_event(
        self,
        order_id: str,
        symbol: str,
        event_type: str,
        detail: str = "",
    ) -> None:
        """记录撮合事件"""
        event = {
            "order_id": order_id,
            "symbol": symbol,
            "type": event_type,
            "detail": detail,
            "timestamp": time.time(),
        }
        self._event_log.append(event)

    def save_state(self, filepath: str) -> None:
        """持久化撮合引擎状态"""
        state = {
            "cash": self._cash,
            "frozen_cash": self._frozen_cash,
            "initial_cash": self._initial_cash,
            "previous_close_map": self._previous_close_map,
            "positions": self._positions,
            "trade_count": len(self._trade_log),
            "event_count": len(self._event_log),
        }
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.info(f"撮合引擎状态已保存到 {filepath}")
        except Exception as e:
            logger.warning(f"保存撮合引擎状态失败: {e}")

    def load_state(self, filepath: str) -> bool:
        """加载撮合引擎状态"""
        try:
            p = Path(filepath)
            if not p.exists():
                return False
            with open(filepath, "r", encoding="utf-8") as f:
                state = json.load(f)

            self._cash = state.get("cash", self._initial_cash)
            self._frozen_cash = state.get("frozen_cash", 0.0)
            self._previous_close_map = state.get("previous_close_map", {})
            self._positions = state.get("positions", {})
            logger.info(
                f"已从 {filepath} 恢复状态: cash={self._cash:.2f}, "
                f"positions={len(self._positions)}"
            )
            return True
        except Exception as e:
            logger.warning(f"加载撮合引擎状态失败: {e}")
            return False
