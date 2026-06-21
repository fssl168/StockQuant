# -*- coding: utf-8 -*-
"""F004 策略框架 — BaseStrategy 基类"""

from __future__ import annotations

import logging
from abc import ABC
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from stockquant.indicators.base import Indicator, IndicatorProxy
from stockquant.models.order import Order, OrderSide, OrderType, OrderStatus
from stockquant.models.bar import BarData
from stockquant.models.position import Position

if TYPE_CHECKING:
    from stockquant.engine.cerebro import Cerebro

logger = logging.getLogger("stockquant.strategy")


class BaseStrategy(ABC):
    """
    策略基类。

    用法:
        class MyStrategy(BaseStrategy):
            name = "My Dual MA"
            parameters = {"fast": 5, "slow": 20}

            def on_start(self):
                self.ma_fast = self.EMA(self.data, self.parameters["fast"])
                self.ma_slow = self.EMA(self.data, self.parameters["slow"])

            def on_bar(self, bars):
                if self.ma_fast.crossed_above(self.ma_slow):
                    self.order_market(bars["sh600519"], 100)
    """

    name: str = "Unnamed Strategy"
    parameters: Dict[str, Any] = {}

    def __init__(self, cerebro: Cerebro, **kwargs):
        # 合并参数
        for k, v in self.parameters.items():
            setattr(self, f"_param_{k}", kwargs.get(k, v))
        for k, v in kwargs.items():
            if k not in self.parameters:
                setattr(self, k, v)

        self._cerebro = cerebro
        self._indicators: Dict[str, Indicator] = {}
        self._order_id_counter = 0
        self._log_messages: List[str] = []

    def initialize(self, cerebro: Cerebro):
        """由 Cerebro 调用，注入引用"""
        self._cerebro = cerebro

    # ------------------------------------------------------------------
    # 生命周期钩子 — 由引擎调用
    # ------------------------------------------------------------------

    def on_start(self):
        """回测/实盘开始"""
        pass

    def on_bar(self, bars: Dict[str, BarData]):
        """
        每根K线触发。

        Parameters
        ----------
        bars : dict
            {symbol: BarData}
        """
        pass

    def on_tick(self, tick: Any):
        """Tick 数据触发 — 实盘/模拟盘中每个 Tick 事件调用。

        默认实现为空，策略可重写以响应 Tick 级事件。
        Tick 数据包含: symbol, price, volume, bid_price, ask_price, timestamp。
        """
        pass

    def on_order(self, order: Order):
        """订单状态变化"""
        pass

    def on_trade(self, trade: Any):
        """成交回调"""
        pass

    def on_finish(self):
        """回测/实盘结束"""
        pass

    # ------------------------------------------------------------------
    # 快捷属性 — 代理到 Cerebro
    # ------------------------------------------------------------------

    @property
    def cash(self) -> float:
        """可用资金"""
        return self._cerebro.cash

    @property
    def account(self):
        """账户对象"""
        return self._cerebro.account

    @property
    def positions(self) -> Dict[str, Position]:
        """持仓字典"""
        return self._cerebro.positions

    @property
    def portfolio(self):
        """投资组合对象"""
        return self._cerebro.portfolio

    @property
    def equity_curve(self) -> List[tuple]:
        """权益曲线"""
        return self._cerebro.equity_curve

    # ------------------------------------------------------------------
    # 指标代理
    # ------------------------------------------------------------------

    def EMA(self, data: List[float], period: int = 12) -> IndicatorProxy:
        """指数移动平均"""
        from stockquant.indicators.moving_avg import EMA as _EMA
        ind = _EMA(data, period=period)
        return ind.calculate()

    def SMA(self, data: List[float], period: int = 20) -> IndicatorProxy:
        """简单移动平均"""
        from stockquant.indicators.moving_avg import SMA as _SMA
        ind = _SMA(data, period=period)
        return ind.calculate()

    def MACD(self, data: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """MACD"""
        from stockquant.indicators.trend import MACD as _MACD
        return _MACD(data, fastperiod=fast, slowperiod=slow, signalperiod=signal).calculate()

    def RSI(self, data: List[float], period: int = 14) -> IndicatorProxy:
        """RSI"""
        from stockquant.indicators.oscillators import RSI as _RSI
        return _RSI(data, timeperiod=period).calculate()

    def BOLL(self, data: List[float], period: int = 20) -> Dict:
        """布林带"""
        from stockquant.indicators.volatility import BOLL as _BOLL
        return _BOLL(data, timeperiod=period).calculate()

    def ATR(self, high: List[float], low: List[float], close: List[float], period: int = 14) -> IndicatorProxy:
        """ATR"""
        from stockquant.indicators.volatility import ATR as _ATR
        return _ATR(high, low, close, timeperiod=period).calculate()

    def KDJ(self, high: List[float], low: List[float], close: List[float],
            fastk: int = 9, slowk: int = 3, slowd: int = 3) -> Dict:
        """KDJ"""
        from stockquant.indicators.oscillators import KDJ as _KDJ
        return _KDJ(high, low, close, fastk_period=fastk, slowk_period=slowk, slowd_period=slowd).calculate()

    # ------------------------------------------------------------------
    # 订单发送
    # ------------------------------------------------------------------

    def order_market(self, bar: BarData, quantity: int):
        """
        市价单买入。

        Parameters
        ----------
        bar : BarData
            标的K线
        quantity : int
            买入数量（100 的整数倍）
        """
        order = Order(
            symbol=bar.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            price=bar.close,
            quantity=quantity,
        )
        self._submit_order(order)

    def order_limit(self, bar: BarData, quantity: int, limit_price: float):
        """
        限价单买入。
        """
        order = Order(
            symbol=bar.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=limit_price,
            quantity=quantity,
        )
        self._submit_order(order)

    def order_sell(self, bar: BarData, quantity: int):
        """
        市价单卖出。
        """
        order = Order(
            symbol=bar.symbol,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            price=bar.close,
            quantity=quantity,
        )
        self._submit_order(order)

    def close_all(self):
        """平掉所有持仓"""
        for symbol, pos in list(self._cerebro.positions.items()):
            if pos.quantity > 0:
                bar_data = self._get_current_bar(symbol)
                if bar_data:
                    self.order_sell(bar_data, int(pos.quantity))

    def get_position(self, symbol: str) -> Any:
        """获取持仓"""
        return self._cerebro.get_position(symbol)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _submit_order(self, order: Order):
        """提交订单到 Broker"""
        bar = self._get_current_bar(order.symbol)
        if not bar:
            return

        order.order_id = f"{order.order_id}_{order.side.value}_{self._next_order_id()}" if order.order_id else f"{order.symbol}_{order.side.value}_{self._next_order_id()}"
        order.update_status(OrderStatus.SUBMITTED)

        # 风控检查
        if self._cerebro.risk_manager:
            risk_mgr = self._cerebro.risk_manager
            positions = self._cerebro.positions if hasattr(self._cerebro, 'positions') else {}
            equity = self._cerebro.cash  # 简化：无持仓时 equity ≈ cash
            if hasattr(self._cerebro, 'portfolio'):
                equity = self._cerebro.portfolio.equity
            valid, reason = risk_mgr.check(order, equity, positions, equity)
            if not valid:
                order.update_status(OrderStatus.REJECTED)
                self.log(f"Order rejected by risk manager: {reason}")
                return

        # 佣金检查：可用资金是否足够
        from stockquant.engine.commission import CommissionInfo
        comm = self._cerebro.commission or CommissionInfo()
        notional = bar.close * order.quantity
        buy_cost = comm.calc_buy_cost(notional)
        if order.side == OrderSide.BUY and (notional + buy_cost) > self._cerebro.cash:
            order.update_status(OrderStatus.REJECTED)
            self.log(f"Order rejected: insufficient cash {self._cerebro.cash:.2f} < {notional + buy_cost:.2f}")
            return

        # 通过 Broker 撮合
        trade = self._cerebro.broker.place_order(order, bar) if self._cerebro.broker else None

        if trade:
            # 记录成交到 Cerebro（用于回测报告）
            self._cerebro._trades.append(trade)

            # 更新持仓
            is_today = True  # 简化：所有成交都标记为当日
            self._cerebro.update_position_fill(order.symbol, order.quantity, trade.price, is_today)

            # 扣减资金
            total_cost = notional + buy_cost
            self._cerebro.account.deduct(total_cost)

            # 回调
            self.on_trade(trade)
            self.log(f"Filled: {order.side.value} {order.quantity} {order.symbol} @ {trade.price:.2f}")
        else:
            print(f"DEBUG _submit_order: trade={trade}, order.side={order.side}, order.qty={order.quantity}, order.price={order.price}, bar.close={bar.close}")

        self.on_order(order)

    def _get_current_bar(self, symbol: str) -> Optional[BarData]:
        """获取当前 Bar（从最近的策略状态中获取）"""
        # 简化：在 on_bar 调用时通过闭包传递
        # 这里需要一个更优雅的方式来获取最新 Bar
        # 由 on_bar 调用时设置的 _current_bars 属性
        return getattr(self, "_current_bars", {}).get(symbol)

    def _next_order_id(self) -> int:
        self._order_id_counter += 1
        return self._order_id_counter

    def log(self, message: str):
        """记录策略日志"""
        self._log_messages.append(message)
        logger.info(f"[{self.name}] {message}")

    def is_last_bar(self) -> bool:
        """是否回测最后一个 Bar"""
        return getattr(self, "_is_last_bar", False)

    def set_position(self, symbol: str, quantity: int):
        """设置某标的的仓位（简化版：直接卖出或买入至目标量）"""
        pos = self.get_position(symbol)
        if pos is None:
            return
        current = int(pos.quantity)
        if quantity > current:
            # 需要买入
            bar = self._get_current_bar(symbol)
            if bar:
                self.order_market(bar, quantity - current)
        elif quantity < current:
            # 需要卖出
            bar = self._get_current_bar(symbol)
            if bar:
                self.order_sell(bar, current - quantity)

    def on_bar_with_data(self, bars: Dict[str, BarData]):
        """内部调用：设置 _current_bars 后调用 on_bar"""
        self._current_bars = bars
        self.on_bar(bars)

    # ------------------------------------------------------------------
    # 指标可视化
    # ------------------------------------------------------------------

    def plot_indicator(
        self,
        proxy,
        name: Optional[str] = None,
        title: Optional[str] = None,
    ):
        """
        在策略中绘制指标曲线。

        参数
        ----
        proxy : IndicatorProxy 或 dict
            单条曲线传入 IndicatorProxy；多输出指标（MACD/BOLL/KDJ）可传 dict。
        name : str, 可选
            图例名称（仅单条曲线时有效）。
        title : str, 可选
            图表标题。

        Returns
        -------
        返回 plotly Figure 或 matplotlib Figure。
        """
        import logging

        logger = logging.getLogger("stockquant.strategy")

        if isinstance(proxy, dict):
            # 多输出指标：绘制每条曲线
            for k, v in proxy.items():
                if isinstance(v, IndicatorProxy):
                    logger.info(f"[plot_indicator] {self.name}: plotting '{k}'")
                    v.plot(title=title or f"{self.name} - {k}")
            return None

        if isinstance(proxy, IndicatorProxy):
            logger.info(f"[plot_indicator] {self.name}: plotting '{name or proxy._name}'")
            return proxy.plot(title=title)

        logger.warning(f"[plot_indicator] {self.name}: 不支持的类型 {type(proxy)}")
        return None
