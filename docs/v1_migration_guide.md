# v1 -> v2 迁移指南

方式一：使用 V1CompatStrategy（零代码修改，直接运行）
------------------------------------------------------
无需重写 v1 策略，通过兼容层直接运行：

    from stockquant.v1_compat import wrap_v1_strategy
    from stockquant.engine import Cerebro
    from stockquant.data.providers.baostock_feed import BaoStockFeed

    # v1 策略（无需修改）
    class MyV1Strategy:
        def __init__(self, fast=5, slow=20):
            self.fast = fast
            self.slow = slow

        def on_bar(self, i, bar):
            if i > self.slow:
                if self._should_buy(i):
                    self.buy("sh512980", 100)

    # 包装并运行
    StrategyClass = wrap_v1_strategy(
        MyV1Strategy,
        initial_cash=1_000_000,
        symbol="sh512980",
        fast=5,
        slow=20,
    )

    feed = BaoStockFeed(
        symbols=["sh512980"],
        timeframe="1d",
        start="2020-01-01",
        end="2024-12-31",
    )

    cerebro = Cerebro(cash=1_000_000)
    cerebro.add_data(feed)
    cerebro.add_strategy(StrategyClass)
    results = cerebro.run()
    cerebro.show_report(results)

方式二：手动迁移到 v2（推荐，功能更全）
---------------------------------------

v1 代码:
    from stockquant.quant import *
    config.loads("config.json")

    class Strategy:
        def __init__(self):
            self.trade = Trade(config_file="config.json", symbol="sh512980")
            kline = Market.kline("sh512980", "1d")
            bt = BackTest()
            for i in range(10, len(kline)):
                bt.initialize(kline[:i+1])
                if self._should_buy(kline[i]):
                    self.trade.buy(symbol="sh512980", volume=100)

v2 代码:
    from stockquant.strategy import BaseStrategy
    from stockquant.engine import Cerebro
    from stockquant.data.providers.baostock_feed import BaoStockFeed

    class MyStrategy(BaseStrategy):
        name = "My Dual MA"
        parameters = {"fast": 5, "slow": 20}

        def on_start(self):
            # 在 on_start 中初始化指标
            self._fast_val = None
            self._slow_val = None

        def on_bar(self, bars):
            bar = bars["sh512980"]
            closes = [bars["sh512980"].close for bars_list in []]  # 使用 self.EMA 等
            # 简化示例：
            if self._should_buy(bar):
                self.order_market(bar, 100)

        def _should_buy(self, bar):
            # 你的买入逻辑
            return False

    cerebro = Cerebro(cash=1_000_000)
    cerebro.add_data(BaoStockFeed(
        symbols=["sh512980"],
        timeframe="1d",
        start="2020-01-01",
        end="2024-12-31",
    ))
    cerebro.add_strategy(MyStrategy)
    results = cerebro.run()
    cerebro.show_report(results)

API 映射表
----------
v1 API                              | v2 API
------------------------------------|-------------------------------------
Trade(config_file=..., symbol=...)  | 不再需要 — 由 Cerebro 管理订单
Market.kline(symbol, timeframe)     | DataFeed.baostock(symbols=[...])
for i in range(10, len(kline)):     | 不再需要 — Cerebro 自动逐 Bar 驱动
  bt.initialize(kline[:i+1])         |   on_bar 自动接收当前 Bar
self.trade.buy(symbol, volume)      | self.order_market(bar, quantity)
self.trade.sell(symbol, volume)     | self.order_sell(bar, quantity)
self.trade.close_all()              | self.close_all()
config.loads("config.json")         | 直接传参或从环境变量读取
BackTest()                          | Cerebro(cash=...)
bt.run()                            | cerebro.run()

v1 策略回调方法
---------------
v1 策略可定义以下任一方法（按优先级检测）：
    on_bar(index, bar)       -- 最常见：接收索引和当前 K 线
    handle_bar(bar, index)   -- Backtrader 风格
    update(bar)              -- 简单风格：只接收当前 Bar

v1 的 buy/sell 自动映射：
    self.buy("sh512980", 100)   -> self.order_market(bar, 100)
    self.sell("sh512980", 100)  -> self.order_sell(bar, 100)

v2 内置指标（直接 self.xxx() 调用）：
    self.EMA(data, period=12)
    self.SMA(data, period=20)
    self.MACD(data, fast=12, slow=26, signal=9)
    self.RSI(data, period=14)
    self.BOLL(data, period=20)
    self.ATR(high, low, close, period=14)
    self.KDJ(high, low, close, fastk=9, slowk=3, slowd=3)

限制
----
- 仅支持单标的（single-symbol）回测
- 仅支持日线数据（daily timeframe）
- 仅支持回测模式（非实盘/模拟盘）
- 不支持 v1 Trade 对象的复杂属性（如手续费率、滑点等）
- 技术指标需手动替换为 v2 的 self.xxx() 方法
- Market.kline 的历史数据不会被自动拉取，需通过 DataFeed 提供
