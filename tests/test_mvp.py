# -*- coding: utf-8 -*-
"""集成测试 — 验证 MVP 核心链路"""

import unittest
import os
import tempfile
from datetime import datetime

import numpy as np

# ---- 测试指标计算 ----

class TestIndicators(unittest.TestCase):
    """18 个指标单元测试"""

    def setUp(self):
        """生成模拟价格数据"""
        np.random.seed(42)
        prices = [100.0]
        for _ in range(200):
            prices.append(prices[-1] * (1 + np.random.randn() * 0.02))
        highs = [p * (1 + abs(np.random.randn()) * 0.01) for p in prices]
        lows = [p * (1 - abs(np.random.randn()) * 0.01) for p in prices]
        volumes = [1000000 * (1 + abs(np.random.randn()) * 0.5) for _ in prices]
        self.prices = prices
        self.highs = highs
        self.lows = lows
        self.volumes = volumes

    def test_ema(self):
        from stockquant.indicators import EMA
        result = EMA(self.prices, period=12).calculate()
        self.assertEqual(len(list(result)), 201)
        self.assertGreater(result[-1], 0)

    def test_sma(self):
        from stockquant.indicators import MA
        result = MA(self.prices, period=20).calculate()
        self.assertEqual(len(list(result)), 201)

    def test_macd(self):
        from stockquant.indicators import MACD
        result = MACD(self.prices, 12, 26, 9).calculate()
        self.assertIn("dif", result)
        self.assertIn("dea", result)
        self.assertIn("macd", result)
        self.assertEqual(len(list(result["dif"])), 201)

    def test_rsi(self):
        from stockquant.indicators import RSI
        result = RSI(self.prices, 14).calculate()
        self.assertEqual(len(list(result)), 201)
        # RSI 应在 0-100 之间
        vals = list(result)
        non_nan = [v for v in vals if v == v]  # NaN check
        if non_nan:
            self.assertGreaterEqual(min(non_nan), 0)
            self.assertLessEqual(max(non_nan), 100)

    def test_boll(self):
        from stockquant.indicators import BOLL
        result = BOLL(self.prices, 20).calculate()
        self.assertIn("upperband", result)
        self.assertIn("middleband", result)
        self.assertIn("lowerband", result)
        # 上轨应大于中轨
        for i in range(20, len(self.prices)):
            if result["middleband"][i] and result["middleband"][i] > 0:
                self.assertGreater(result["upperband"][i], result["middleband"][i])

    def test_atr(self):
        from stockquant.indicators import ATR
        result = ATR(self.highs, self.lows, self.prices, 14).calculate()
        self.assertEqual(len(list(result)), 201)

    def test_kdj(self):
        from stockquant.indicators import KDJ
        result = KDJ(self.highs, self.lows, self.prices, 9, 3, 3).calculate()
        self.assertIn("k", result)
        self.assertIn("d", result)

    def test_cci(self):
        from stockquant.indicators import CCI
        result = CCI(self.highs, self.lows, self.prices, 20).calculate()
        self.assertEqual(len(list(result)), 201)

    def test_roc(self):
        from stockquant.indicators import ROC
        result = ROC(self.prices, 12).calculate()
        self.assertEqual(len(list(result)), 201)

    def test_stochrsi(self):
        from stockquant.indicators import STOCHRSI
        result = STOCHRSI(self.prices, 14, 5, 3).calculate()
        self.assertIn("stochrsi", result)
        self.assertIn("fastk", result)

    def test_sar(self):
        from stockquant.indicators import SAR
        result = SAR(self.highs, self.lows).calculate()
        self.assertEqual(len(list(result)), 201)

    def test_stddev(self):
        from stockquant.indicators import STDDEV
        result = STDDEV(self.prices, 20).calculate()
        self.assertEqual(len(list(result)), 201)

    def test_kama(self):
        from stockquant.indicators import KAMA
        result = KAMA(self.prices, 30).calculate()
        self.assertEqual(len(list(result)), 201)

    def test_trix(self):
        from stockquant.indicators import TRIX
        result = TRIX(self.prices, 15).calculate()
        self.assertEqual(len(list(result)), 201)

    def test_obv(self):
        from stockquant.indicators import OBV
        result = OBV(self.prices, self.volumes).calculate()
        self.assertEqual(len(list(result)), 201)

    def test_highest(self):
        from stockquant.indicators import HIGHEST
        result = HIGHEST(self.prices, 20).calculate()
        self.assertEqual(len(list(result)), 201)

    def test_lowest(self):
        from stockquant.indicators import LOWEST
        result = LOWEST(self.prices, 20).calculate()
        self.assertEqual(len(list(result)), 201)

    def test_indicator_cross(self):
        """测试指标交叉检测"""
        from stockquant.indicators import EMA
        from stockquant.indicators.base import IndicatorProxy

        # 构造一个简单测试：快速EMA从下方穿过慢速EMA
        short_data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        long_data = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5]
        short = IndicatorProxy(short_data)
        long = IndicatorProxy(long_data)

        # 最后一根都=10，倒数第二根分别=9和8.5
        # 9/8.5 = 0.5 diff, 10/9.5 = 0.5 diff → 没有交叉
        self.assertFalse(short.crossed_above(long))

        # 构造交叉：在最后一根发生上穿
        above = IndicatorProxy([1, 2, 3, 5])  # 1→2→3→5
        below = IndicatorProxy([4, 4, 4, 4])  # 恒为4
        # 3<4, 5>4 — 上穿发生在最后两根
        self.assertTrue(above.crossed_above(below))


class TestCommission(unittest.TestCase):
    """佣金模型测试"""

    def test_buy_cost(self):
        from stockquant.engine.commission import CommissionInfo
        comm = CommissionInfo()
        # 买入 10000 元
        cost = comm.calc_buy_cost(10000)
        commission = max(10000 * 0.00025, 5)  # 5 元（最低）
        transfer = 10000 * 0.00001  # 0.1 元
        expected = commission + transfer
        self.assertAlmostEqual(cost, expected, places=4)

    def test_sell_cost(self):
        from stockquant.engine.commission import CommissionInfo
        comm = CommissionInfo()
        cost = comm.calc_sell_cost(10000)
        commission = max(10000 * 0.00025, 5)
        stamp = 10000 * 0.0005
        transfer = 10000 * 0.00001
        expected = commission + stamp + transfer
        self.assertAlmostEqual(cost, expected, places=4)

    def test_small_trade_min_commission(self):
        """小额交易最低佣金 5 元"""
        from stockquant.engine.commission import CommissionInfo
        comm = CommissionInfo()
        cost = comm.calc_buy_cost(100)  # 100 元
        expected = 5 + 100 * 0.00001  # 最低佣金 5 + 过户费
        self.assertAlmostEqual(cost, expected, places=4)


class TestSlippage(unittest.TestCase):
    """滑点模型测试"""

    def test_fixed_slippage_buy(self):
        from stockquant.engine.commission import FixedSlippage
        slip = FixedSlippage(0.01)
        price = slip.apply(100.0, "buy")
        self.assertAlmostEqual(price, 100.01, places=4)

    def test_fixed_slippage_sell(self):
        from stockquant.engine.commission import FixedSlippage
        slip = FixedSlippage(0.01)
        price = slip.apply(100.0, "sell")
        self.assertAlmostEqual(price, 99.99, places=4)

    def test_percent_slippage(self):
        from stockquant.engine.commission import PercentSlippage
        slip = PercentSlippage(0.001)  # 0.1%
        price = slip.apply(100.0, "buy")
        self.assertAlmostEqual(price, 100.1, places=4)


class TestMetrics(unittest.TestCase):
    """回测指标计算测试"""

    def setUp(self):
        """生成模拟权益曲线"""
        np.random.seed(123)
        equity = [1_000_000.0]
        for _ in range(500):
            equity.append(equity[-1] * (1 + np.random.randn() * 0.01))
        self.equity_curve = list(zip(equity, range(len(equity))))

    def test_sharpe_ratio(self):
        from stockquant.engine.metrics import BacktestMetrics
        metrics = BacktestMetrics.calculate(
            equity_curve=self.equity_curve,
            trades=[],
            initial_cash=1_000_000,
        )
        self.assertIn("Sharpe Ratio", metrics)
        sharpe_val = float(metrics["Sharpe Ratio"])
        # Sharpe 应在合理范围内（不为 0，因为数据有趋势）
        self.assertNotEqual(sharpe_val, 0)

    def test_max_drawdown(self):
        from stockquant.engine.metrics import BacktestMetrics
        metrics = BacktestMetrics.calculate(
            equity_curve=self.equity_curve,
            trades=[],
            initial_cash=1_000_000,
        )
        self.assertIn("Max Drawdown", metrics)
        # Drawdown is formatted as string like "32.14%"
        dd_str = metrics["Max Drawdown"]
        self.assertIn("%", dd_str)

    def test_total_return(self):
        from stockquant.engine.metrics import BacktestMetrics
        metrics = BacktestMetrics.calculate(
            equity_curve=self.equity_curve,
            trades=[],
            initial_cash=1_000_000,
        )
        self.assertIn("Total Return", metrics)


class TestOrder(unittest.TestCase):
    """订单数据模型测试"""

    def test_order_creation(self):
        from stockquant.models.order import Order, OrderSide, OrderType, OrderStatus
        order = Order(
            symbol="sh600519",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=1800.0,
            quantity=100,
        )
        self.assertIsNotNone(order.order_id)
        self.assertEqual(order.status, OrderStatus.PENDING)
        self.assertEqual(order.remaining, 100)

    def test_order_fill(self):
        from stockquant.models.order import Order, OrderSide, OrderType
        order = Order(
            symbol="sh600519",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=1800.0,
            quantity=500,
        )
        order.add_fill(300, 1800.0)
        self.assertEqual(order.filled_quantity, 300)
        self.assertEqual(order.status.value, "Partial")
        self.assertEqual(order.remaining, 200)

        order.add_fill(200, 1800.5)
        self.assertEqual(order.filled_quantity, 500)
        self.assertEqual(order.status.value, "Filled")

    def test_order_rejected(self):
        from stockquant.models.order import Order, OrderSide, OrderType, OrderStatus
        order = Order(
            symbol="sh600519",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=1800.0,
            quantity=100,
        )
        order.update_status(OrderStatus.REJECTED)
        self.assertEqual(order.status, OrderStatus.REJECTED)


class TestPosition(unittest.TestCase):
    """持仓数据模型测试"""

    def test_position_add(self):
        from stockquant.models.position import Position
        pos = Position(symbol="sh600519")
        pos.add_fill(100, 50.0)
        self.assertEqual(pos.quantity, 100)
        self.assertEqual(pos.cost_price, 50.0)
        self.assertEqual(pos.today_frozen, 100)
        self.assertEqual(pos.available, 0)  # 今日买入不可卖

    def test_position_unlock(self):
        from stockquant.models.position import Position
        pos = Position(symbol="sh600519")
        pos.add_fill(100, 50.0)
        pos.unlock_today_frozen()
        self.assertEqual(pos.available, 100)
        self.assertEqual(pos.today_frozen, 0)

    def test_position_update_price(self):
        from stockquant.models.position import Position
        pos = Position(symbol="sh600519")
        pos.add_fill(100, 50.0)
        pos.update_price(55.0)
        self.assertAlmostEqual(pos.pnl, 500.0)  # (55-50) * 100

    def test_position_market_value(self):
        from stockquant.models.position import Position
        pos = Position(symbol="sh600519")
        pos.add_fill(200, 30.0)
        pos.update_price(30.0)  # 设置当前价等于成本价
        self.assertEqual(pos.market_value, 6000.0)


class TestBroker(unittest.TestCase):
    """BacktestBroker 撮合测试"""

    def test_market_order(self):
        from stockquant.engine import BacktestBroker
        from stockquant.models.order import Order, OrderSide, OrderType
        from stockquant.models.bar import BarData

        broker = BacktestBroker()
        order = Order(
            symbol="sh600519",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            price=100.0,
            quantity=100,
        )
        bar = BarData(
            symbol="sh600519",
            datetime=datetime.now(),
            open=99.0, high=101.0, low=98.0, close=100.0, volume=1000000,
        )
        trade = broker.place_order(order, bar)
        self.assertIsNotNone(trade)
        self.assertAlmostEqual(trade.price, 100.0, places=2)
        self.assertEqual(order.status.value, "Filled")

    def test_lot_size_rejection(self):
        """非 100 整数倍被拒绝"""
        from stockquant.engine import BacktestBroker
        from stockquant.models.order import Order, OrderSide, OrderType
        from stockquant.models.bar import BarData

        broker = BacktestBroker()
        order = Order(
            symbol="sh600519",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            price=100.0,
            quantity=50,  # 不是 100 的倍数
        )
        bar = BarData(
            symbol="sh600519",
            datetime=datetime.now(),
            open=99.0, high=101.0, low=98.0, close=100.0, volume=1000000,
        )
        trade = broker.place_order(order, bar)
        self.assertIsNone(trade)
        self.assertEqual(order.status.value, "Rejected")


class TestCSVFeed(unittest.TestCase):
    """CSV 数据源测试"""

    def test_csv_feed(self):
        # 创建临时 CSV 文件
        csv_content = "timestamp,open,high,low,close,volume\n"
        for i in range(100):
            from datetime import datetime, timedelta
            dt = (datetime(2024, 1, 1) + timedelta(days=i)).strftime('%Y-%m-%d')
            price = 100 + i * 0.1
            csv_content += f"{dt},{price:.2f},{price+1:.2f},{price-1:.2f},{price:.2f},{1000000}\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()
            csv_path = f.name

        try:
            from stockquant.data import CSVFeed
            feed = CSVFeed(csv_path, symbol="test", timeframe="1d")
            self.assertEqual(feed.symbol, "test")
            self.assertEqual(len(feed), 100)

            bar = feed[0]
            self.assertEqual(bar.symbol, "test")
            self.assertAlmostEqual(bar.open, 100.0, places=1)
            self.assertAlmostEqual(bar.close, 100.0, places=1)

            bar_last = feed[99]
            self.assertAlmostEqual(bar_last.close, 109.9, places=1)
        finally:
            os.unlink(csv_path)


class TestCerebro(unittest.TestCase):
    """Cerebro 主引擎集成测试"""

    def test_cerebro_run_with_csv(self):
        """完整回测：CSV 数据 + 策略 + 引擎"""
        # 创建测试 CSV（确保每天唯一日期）
        csv_content = "timestamp,open,high,low,close,volume\n"
        prices = [100.0]
        for i in range(250):
            prices.append(prices[-1] * (1 + np.random.randn() * 0.01))
        for i, p in enumerate(prices):
            from datetime import datetime, timedelta
            dt = (datetime(2023, 1, 1) + timedelta(days=i)).strftime('%Y-%m-%d')
            csv_content += f"{dt},{p:.2f},{p+1:.2f},{p-1:.2f},{p:.2f},{1000000}\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            csv_path = f.name

        try:
            from stockquant import Cerebro, BacktestBroker, CSVFeed, CommissionInfo
            from stockquant.engine.sizer import FixedFractionSizer

            feed = CSVFeed(csv_path, symbol="test", timeframe="1d")
            cerebro = Cerebro(cash=1_000_000, broker=BacktestBroker(), commission=CommissionInfo())
            cerebro.add_data(feed)

            # 添加一个简单策略
            from stockquant.strategy.base import BaseStrategy
            class DummyStrategy(BaseStrategy):
                name = "Dummy"
                def on_bar(self, bars):
                    pass

            cerebro.add_strategy(DummyStrategy)

            results = cerebro.run()
            self.assertEqual(len(results), 1)
            self.assertIn("metrics", results[0])
            self.assertIn("Total Return", results[0]["metrics"])
            print(f"\nCerebro test passed: {results[0]['metrics']}")
        finally:
            os.unlink(csv_path)


class TestSignal(unittest.TestCase):
    """信号管线测试"""

    def test_signal_expiry(self):
        from stockquant.strategy.signal import Signal, SignalSide, SignalSource
        from datetime import datetime, timedelta

        sig = Signal(
            symbol="sh600519",
            side=SignalSide.BUY,
            confidence=0.8,
            source=SignalSource.AI_DECISION,
            expires_at=datetime.now() - timedelta(minutes=1),
        )
        self.assertTrue(sig.is_expired())

        sig2 = Signal(
            symbol="sh600519",
            side=SignalSide.BUY,
            confidence=0.8,
            source=SignalSource.AI_DECISION,
            expires_at=datetime.now() + timedelta(hours=1),
        )
        self.assertFalse(sig2.is_expired())

    def test_signal_conflict_resolution(self):
        from stockquant.strategy.signal import Signal, SignalSide, SignalSource, SignalManager

        manager = SignalManager(conflict_resolution="conservative")

        manager.add_signal(Signal(symbol="sh600519", side=SignalSide.BUY, source=SignalSource.TRADITIONAL))
        manager.add_signal(Signal(symbol="sh600519", side=SignalSide.SELL, source=SignalSource.AI_DECISION))

        resolved = manager.resolve_conflicts("sh600519")
        # 传统策略优先级更高
        self.assertEqual(resolved.source, SignalSource.TRADITIONAL)


class TestPortfolio(unittest.TestCase):
    """投资组合测试"""

    def test_account_update(self):
        from stockquant.models.account import Account
        acc = Account(initial_cash=1_000_000, cash=1_000_000, available_cash=1_000_000)
        acc.update_equity(500_000)
        self.assertEqual(acc.total_equity, 1_500_000)
        self.assertEqual(acc.market_value, 500_000)

    def test_freeze_release(self):
        from stockquant.models.account import Account
        acc = Account(initial_cash=1_000_000, cash=1_000_000, available_cash=1_000_000)
        acc.freeze_cash(100_000)
        self.assertEqual(acc.cash, 900_000)
        self.assertEqual(acc.frozen_cash, 100_000)
        self.assertEqual(acc.available_cash, 900_000)

        acc.release_cash(100_000)
        self.assertEqual(acc.cash, 1_000_000)
        self.assertEqual(acc.frozen_cash, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
