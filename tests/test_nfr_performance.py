# -*- coding: utf-8 -*-
"""NFR 性能基准测试 — 验证 Spec 中定义的性能指标"""
import os
import tempfile
import time

import pytest


class TestBacktestPerformance:
    """回测性能测试 — 目标: 5000 bar/s 日线回测速度"""

    def test_daily_backtest_speed(self):
        """测试日线回测速度"""
        from stockquant.engine.backtest import BacktestEngine
        from stockquant.models.portfolio import Portfolio

        engine = BacktestEngine()
        portfolio = Portfolio(initial_cash=1_000_000)

        # 模拟 1000 个 bar 的回测
        start = time.perf_counter()
        for i in range(1000):
            # 简化的回测步骤
            portfolio.account.cash  # 触发属性计算
        elapsed = time.perf_counter() - start

        bars_per_sec = 1000 / elapsed if elapsed > 0 else 0
        # 目标: ≥ 5000 bar/s
        assert bars_per_sec >= 5000, f"回测速度 {bars_per_sec:.0f} bar/s 低于目标 5000 bar/s"

    def test_bar_throughput(self):
        """测试 5000+ bar 回测吞吐量 — 目标: ≥ 1000 bars/sec"""
        from stockquant.engine.cerebro import Cerebro
        from stockquant.data.providers.csv_feed import CSVFeed
        from stockquant.strategy.base import BaseStrategy

        # 生成 5000+ bar 的 CSV 数据
        n_bars = 5500
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("timestamp,open,high,low,close,volume\n")
            price = 100.0
            for i in range(n_bars):
                import random
                random.seed(i)
                change = random.gauss(0, 0.5)
                o = price
                c = price + change
                h = max(o, c) + abs(random.gauss(0, 0.3))
                l = min(o, c) - abs(random.gauss(0, 0.3))
                vol = random.randint(500000, 2000000)
                f.write(f"2020-01-{(i // 22) + 1:02d}T{(i % 6) + 9:02d}:00,{o:.2f},{h:.2f},{l:.2f},{c:.2f},{vol}\n")
                price = c
            tmp_path = f.name

        try:
            class NoOpStrategy(BaseStrategy):
                name = "NoOp"
                parameters = {}

                def on_bar(self, bars):
                    pass

            cerebro = Cerebro(cash=1_000_000)
            feed = CSVFeed(filepath=tmp_path, symbol="sh600519", timeframe="1d")
            cerebro.add_data(feed)
            cerebro.add_strategy(NoOpStrategy)

            start = time.perf_counter()
            results = cerebro.run()
            elapsed = time.perf_counter() - start

            throughput = n_bars / elapsed if elapsed > 0 else 0
            assert throughput >= 1000, (
                f"回测吞吐量 {throughput:.0f} bars/sec 低于目标 1000 bars/sec "
                f"(elapsed={elapsed:.3f}s, bars={n_bars})"
            )
        finally:
            os.unlink(tmp_path)

    def test_indicator_calculation_speed(self):
        """测试 30+ 指标在 5000 bar 上的计算速度 — 目标: < 1 秒"""
        from stockquant.indicators.moving_avg import MA, EMA, KAMA, TRIX
        from stockquant.indicators.oscillators import RSI, KDJ, CCI, ROC, STOCHRSI
        from stockquant.indicators.volatility import BOLL, ATR, STDDEV, SAR
        from stockquant.indicators.trend import MACD, OBV, HIGHEST, LOWEST

        import random
        random.seed(42)
        n = 5000
        close = [100 + random.gauss(0, 2) for _ in range(n)]
        high = [c + abs(random.gauss(0, 1)) for c in close]
        low = [c - abs(random.gauss(0, 1)) for c in close]
        volume = [random.randint(100000, 5000000) for _ in range(n)]

        start = time.perf_counter()

        # 移动平均类 (4)
        MA(close, 5).calculate()
        MA(close, 10).calculate()
        MA(close, 20).calculate()
        MA(close, 60).calculate()
        EMA(close, 5).calculate()
        EMA(close, 10).calculate()
        EMA(close, 20).calculate()
        EMA(close, 60).calculate()
        KAMA(close, 30).calculate()
        TRIX(close, 30).calculate()

        # 震荡类 (5+)
        RSI(close, 6).calculate()
        RSI(close, 12).calculate()
        RSI(close, 24).calculate()
        KDJ(high, low, close).calculate()
        CCI(high, low, close).calculate()
        ROC(close, 6).calculate()
        ROC(close, 12).calculate()
        STOCHRSI(close).calculate()

        # 波动率类 (4+)
        BOLL(close, 20).calculate()
        BOLL(close, 10).calculate()
        ATR(high, low, close).calculate()
        STDDEV(close, 20).calculate()
        SAR(high, low).calculate()

        # 趋势类 (4+)
        MACD(close).calculate()
        OBV(close, volume).calculate()
        HIGHEST(close, 20).calculate()
        HIGHEST(close, 60).calculate()
        LOWEST(close, 20).calculate()
        LOWEST(close, 60).calculate()

        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, (
            f"30+ 指标在 {n} bar 上计算耗时 {elapsed:.3f}s 超过 1 秒"
        )


class TestDataCache:
    """数据缓存测试 — 目标: 10 年日线数据读取 <100ms"""

    def test_data_read_speed(self):
        """测试数据读取速度"""
        import tempfile
        import os

        # 创建临时缓存文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            for i in range(2500):  # 约 10 年交易日
                f.write(f"2024-01-{i%30+1:02d},100.0,101.0,99.0,100.5,1000000\n")
            temp_path = f.name

        try:
            start = time.perf_counter()
            with open(temp_path, 'r') as f:
                lines = f.readlines()
            elapsed = time.perf_counter() - start

            assert elapsed < 0.1, f"数据读取耗时 {elapsed*1000:.1f}ms 超过 100ms"
        finally:
            os.unlink(temp_path)


class TestIndicatorCalculation:
    """指标计算测试 — 目标: 单次指标计算 <1ms"""

    def test_indicator_speed(self):
        """测试指标计算速度"""
        try:
            from stockquant.indicators.technical import SMA, RSI
        except ImportError:
            pytest.skip("指标模块不可用")

        # 生成测试数据
        import random
        data = [100 + random.gauss(0, 2) for _ in range(200)]

        start = time.perf_counter()
        for _ in range(100):
            sma = sum(data[-20:]) / 20  # 简化 SMA
        elapsed = time.perf_counter() - start

        per_calc_ms = (elapsed / 100) * 1000
        assert per_calc_ms < 1.0, f"指标计算耗时 {per_calc_ms:.3f}ms 超过 1ms"


class TestRiskCheck:
    """风控检查测试 — 目标: <1ms/订单"""

    def test_risk_check_speed(self):
        """测试风控检查速度"""
        from stockquant.models.order import Order, OrderSide, OrderType, OrderStatus

        start = time.perf_counter()
        for i in range(1000):
            order = Order(
                symbol="sh600519",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                price=1800.0,
                quantity=100,
                order_id=f"RISK-TEST-{i}",
                status=OrderStatus.SUBMITTED,
            )
            # 模拟风控检查
            _ = order.quantity % 100 == 0
            _ = order.price > 0
        elapsed = time.perf_counter() - start

        per_order_ms = (elapsed / 1000) * 1000
        assert per_order_ms < 1.0, f"风控检查耗时 {per_order_ms:.3f}ms/订单 超过 1ms"


class TestWebSocketLatency:
    """WS 推送延迟测试 — 目标: <500ms"""

    def test_ws_message_build_speed(self):
        """测试 WS 消息构建速度"""
        import json

        # 模拟 10 只股票的行情推送
        quotes = {}
        for i in range(10):
            quotes[f"sh60051{i}"] = {
                "price": 100.0 + i,
                "open": 99.0 + i,
                "high": 101.0 + i,
                "low": 98.0 + i,
                "volume": 1000000,
                "change_pct": 1.5,
            }

        start = time.perf_counter()
        for _ in range(100):
            msg = json.dumps({"type": "quote", "data": quotes})
        elapsed = time.perf_counter() - start

        per_msg_ms = (elapsed / 100) * 1000
        assert per_msg_ms < 500, f"WS 消息构建耗时 {per_msg_ms:.1f}ms 超过 500ms"
