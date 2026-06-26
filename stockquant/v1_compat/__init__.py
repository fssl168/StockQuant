# -*- coding: utf-8 -*-
"""v1 兼容层 — 让 v1 策略跑在 v2 Cerebro 引擎上。

v1 策略用手动循环模式：

    class Strategy:
        def __init__(self):
            self.trade = Trade(symbol="sh512980")
            kline = Market.kline("sh512980", "1d")
            for i in range(10, len(kline)):
                bt.initialize(kline[:i+1])
                # ... 交易逻辑

v2 策略用事件驱动模式：

    class MyStrategy(BaseStrategy):
        def on_bar(self, bars):
            if self.ma_fast.crossed_above(self.ma_slow):
                self.order_market(bars["sh512980"], 100)

本模块通过 V1CompatStrategy + wrap_v1_strategy() 让 v1 策略
无需重写即可在 v2 引擎中运行。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type, TYPE_CHECKING

from stockquant.strategy.base import BaseStrategy
from stockquant.models.bar import BarData

if TYPE_CHECKING:
    from stockquant.engine.cerebro import Cerebro

logger = logging.getLogger("stockquant.v1_compat")

# ---------------------------------------------------------------------------
# 内置适配器：把 v1 的 self.buy() / self.sell() 映射到 v2 调用
# ---------------------------------------------------------------------------


class _V1OrderAdapter:
    """拦截 v1 策略的 self.buy() / self.sell() 调用，转发到 v2 订单系统。"""

    def __init__(self, strategy: V1CompatStrategy):
        self._strategy = strategy
        # 让 hasattr 检测通过（v1 策略可能用 getattr(self, "buy")）
        self.buy = self._buy
        self.sell = self._sell

    def _buy(self, symbol: str, quantity: int, price: Optional[float] = None):
        bars = getattr(self._strategy, "_current_bars", {})
        bar = bars.get(symbol)
        if bar is None:
            # 尝试用策略保存的 symbol
            bar = bars.get(getattr(self._strategy, "_symbol", ""))
        if bar is None:
            logger.warning(f"buy({symbol}, {quantity}): no bar data available, skipping")
            return
        use_price = price if price else bar.close
        # 通过 _current_bars 构造一个 BarData 用于 order_market
        order_bar = _PriceBar(bar, close=use_price)
        self._strategy.order_market(order_bar, quantity)

    def _sell(self, symbol: str, quantity: int, price: Optional[float] = None):
        bars = getattr(self._strategy, "_current_bars", {})
        bar = bars.get(symbol)
        if bar is None:
            bar = bars.get(getattr(self._strategy, "_symbol", ""))
        if bar is None:
            logger.warning(f"sell({symbol}, {quantity}): no bar data available, skipping")
            return
        use_price = price if price else bar.close
        order_bar = _PriceBar(bar, close=use_price)
        self._strategy.order_market(order_bar, quantity)

    # close_all 对应 v1 平仓
    def close_all(self):
        self._strategy.close_all()


class _PriceBar:
    """包装 BarData，允许覆盖单个字段（如 close 价格）"""

    __slots__ = ("_src", "close")

    def __init__(self, src: BarData, close: Optional[float] = None):
        self._src = src
        self.close = close if close is not None else src.close

    def __getattr__(self, name: str) -> Any:
        return getattr(self._src, name)


# ---------------------------------------------------------------------------
# V1CompatStrategy
# ---------------------------------------------------------------------------


class V1CompatStrategy(BaseStrategy):
    """
    v1 策略适配包装器。

    把一个 v1 风格的策略类实例化后包装进 v2 BaseStrategy，
    让 v1 策略的方法在 v2 引擎的 on_bar 循环中被逐 Bar 调用。

    Parameters
    ----------
    v1_class : Type
        v1 策略类，构造函数接受 **kwargs
    initial_cash : float, 可选
        初始资金（传给 Cerebro 而非策略）
    symbol : str, 可选
        标的代码（v1 通常只做单标的）
    **kwargs
        额外参数，透传给 v1_class.__init__()

    v1 策略支持的回调方法（按优先级检测）：
        - on_bar(index, bar)       -- 最常见
        - handle_bar(bar, index)   -- 备选
        - update(bar)              -- 兜底

    示例
    ----
    >>> class MyV1Strategy:
    ...     def __init__(self, fast=5, slow=20):
    ...         self.fast = fast
    ...         self.slow = slow
    ...     def on_bar(self, i, bar):
    ...         if i > self.slow:
    ...             if self.need_buy(i, bar):
    ...                 self.buy("sh512980", 100)
    >>> compat = V1CompatStrategy(MyV1Strategy, fast=5, slow=20, symbol="sh512980")
    """

    name: str = "V1Compat"

    def __init__(
        self,
        v1_class: Type,
        cerebro: Cerebro = None,
        initial_cash: float = 1_000_000.0,
        symbol: str = "",
        **kwargs,
    ):
        self._v1_class = v1_class
        self._v1_kwargs = kwargs
        self._symbol = symbol
        self._order_adapter: Optional[_V1OrderAdapter] = None

        # 检测 v1 策略使用的方法
        self._bar_callback: Optional[str] = None
        if hasattr(v1_class, "on_bar"):
            self._bar_callback = "on_bar"
        elif hasattr(v1_class, "handle_bar"):
            self._bar_callback = "handle_bar"
        elif hasattr(v1_class, "update"):
            self._bar_callback = "update"
        else:
            raise TypeError(
                f"v1 strategy class {v1_class.__name__} has no recognized "
                f"bar method: on_bar, handle_bar, or update"
            )

        super().__init__(cerebro, **kwargs)

    def on_start(self):
        # 实例化 v1 策略对象
        self._v1_instance = self._v1_class(**self._v1_kwargs)
        # 注入 buy / sell 适配器
        self._order_adapter = _V1OrderAdapter(self)
        if self._symbol:
            self._v1_instance.symbol = self._symbol
        if hasattr(self._v1_instance, "trade"):
            # 如果 v1 策略初始化了 self.trade，记录日志提醒
            logger.info(
                f"[V1Compat] Strategy {self._v1_class.__name__} has a self.trade "
                f"attribute — trades will be routed through v2 order system"
            )

        # 允许 v1 策略有 init() 钩子（对应 v2 on_start）
        if hasattr(self._v1_instance, "init"):
            self._v1_instance.init()

        super().on_start()

    def on_bar(self, bars: Dict[str, BarData]):
        if self._v1_instance is None:
            return

        # 当前 bar 的索引
        index = getattr(self, "_bar_index", 0)
        self._bar_index = index + 1

        # 取当前标的对应的 bar
        current_bar = bars.get(self._symbol)
        if current_bar is None and bars:
            # 取第一个 bar 作为默认
            current_bar = next(iter(bars.values()), None)

        if current_bar is None:
            return

        # 设置 _current_bars 让 _PriceBar / close_all 能获取 bar
        self._current_bars = bars

        # 判断是否最后一个 bar（用于 v1 策略的结束逻辑）
        self._is_last_bar = super().is_last_bar()

        # 调用 v1 策略的 bar 回调
        try:
            method = getattr(self._v1_instance, self._bar_callback)
            # 检测签名以决定传参方式
            import inspect
            sig = inspect.signature(method)
            params = list(sig.parameters.keys())

            if "bar" in params and "index" in params:
                method(index, current_bar)
            elif "bar" in params:
                method(current_bar)
            elif "index" in params:
                method(index)
            else:
                # 无命名参数，按位置传
                method(index, current_bar)
        except Exception as e:
            logger.error(
                f"[V1Compat] Error calling {self._bar_callback} on "
                f"{self._v1_class.__name__}: {e}",
                exc_info=True,
            )


# ---------------------------------------------------------------------------
# wrap_v1_strategy — 工厂函数
# ---------------------------------------------------------------------------


def wrap_v1_strategy(
    v1_class: Type,
    initial_cash: float = 1_000_000.0,
    symbol: str = "",
    **kwargs,
) -> Type[V1CompatStrategy]:
    """
    工厂函数：把 v1 策略类包装成 V1CompatStrategy 子类。

    用法:
        MyV2Strategy = wrap_v1_strategy(
            MyV1Strategy,
            initial_cash=1_000_000,
            symbol="sh512980",
            fast=5,
            slow=20,
        )

        cerebro = Cerebro(cash=initial_cash)
        cerebro.add_data(DataFeed.baostock(symbols=[symbol], ...))
        cerebro.add_strategy(MyV2Strategy)
        cerebro.run()

    Parameters
    ----------
    v1_class : Type
        v1 策略类
    initial_cash : float
        初始资金
    symbol : str
        交易标的
    **kwargs
        传给 v1_class.__init__() 的参数

    Returns
    -------
    Type[V1CompatStrategy]
        包装后的策略类（可直接传给 cerebro.add_strategy()）
    """

    class WrappedStrategy(V1CompatStrategy):
        name = v1_class.__name__

    # 把参数绑定到包装类，V1CompatStrategy.__init__ 会自动处理
    WrappedStrategy._v1_class = v1_class
    WrappedStrategy._v1_initial_cash = initial_cash
    WrappedStrategy._v1_symbol = symbol
    WrappedStrategy._v1_kwargs = kwargs

    # 重写 __init__ 以注入这些参数
    original_init = V1CompatStrategy.__init__

    def patched_init(self, cerebro=None, **extra):
        kwargs_merged = {**kwargs, **extra}
        original_init(
            self,
            v1_class,
            cerebro=cerebro,
            initial_cash=initial_cash,
            symbol=symbol,
            **kwargs_merged,
        )

    WrappedStrategy.__init__ = patched_init

    # 添加类级别的 run() 快捷方法
    def run(
        cerebro_cash: float = initial_cash,
        data_feed=None,
        commission=None,
        broker=None,
        show_report: bool = True,
    ) -> list:
        """
        一键运行包装策略。

        cerebro_cash: 初始资金
        data_feed: DataFeed 实例（必须）
        commission: 佣金信息（可选）
        broker: Broker 实例（可选）
        show_report: 是否打印回测报告
        """
        from stockquant.engine.cerebro import Cerebro

        cerebro = Cerebro(cash=cerebro_cash, broker=broker, commission=commission)
        if data_feed is not None:
            cerebro.add_data(data_feed)
        cerebro.add_strategy(WrappedStrategy)
        results = cerebro.run()
        if show_report:
            cerebro.show_report(results)
        return results

    WrappedStrategy.run = staticmethod(run)
    WrappedStrategy.run.__doc__ = f"运行 {v1_class.__name__} 策略回测。"

    return WrappedStrategy


# ---------------------------------------------------------------------------
# MigrationGuide — 完整的 v1 → v2 迁移指南
# ---------------------------------------------------------------------------

try:
    from pathlib import Path
    _migration_guide_path = Path(__file__).parent / "v1_migration_guide.md"
    MIGRATION_GUIDE = _migration_guide_path.read_text(encoding="utf-8")
except (ImportError, FileNotFoundError):
    MIGRATION_GUIDE = "See docs/v1_migration_guide.md for migration details."
