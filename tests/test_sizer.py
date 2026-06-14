# -*- coding: utf-8 -*-
"""F010 仓位管理模块测试"""

import pytest

from stockquant.engine.sizer import (
    FixedFractionSizer, KellySizer, ATRSizer,
    VolatilityTargetSizer, EqualWeightSizer,
)


# ===================================================================
# FixedFractionSizer
# ===================================================================

class TestFixedFractionSizer:
    def test_basic_calculation(self):
        """10% 比例，权益 100 万，价格 100 → 买 1000 股"""
        sizer = FixedFractionSizer(fraction=0.1)
        qty = sizer.calculate(1_000_000, 100.0, 1_000_000)
        assert qty == 1000  # 100000 / 100 = 1000

    def test_lot_size_rounding(self):
        """不足 100 股应向下取整"""
        sizer = FixedFractionSizer(fraction=0.1)
        qty = sizer.calculate(1_000, 100.0, 1_000)
        assert qty == 0  # 1000*0.1/100 = 1 → //100 = 0

    def test_zero_price(self):
        """价格为 0 应返回 0"""
        sizer = FixedFractionSizer(fraction=0.1)
        assert sizer.calculate(1_000_000, 0, 1_000_000) == 0


# ===================================================================
# KellySizer
# ===================================================================

class TestKellySizer:
    def test_kelly_positive(self):
        """胜率 60%，盈亏比 2:1 → Kelly = 0.6 - 0.4/2 = 0.4，半凯利 0.2"""
        sizer = KellySizer(win_rate=0.6, win_loss_ratio=2.0)
        qty = sizer.calculate(1_000_000, 100.0, 1_000_000)
        # 半凯利 0.2 * 1_000_000 / 100 = 2000（浮点精度 → 1900-2000 均可）
        assert 1900 <= qty <= 2000

    def test_kelly_negative(self):
        """胜率 40%，盈亏比 0.5 → Kelly = 0.4 - 0.6/0.5 = -0.8 → max(0, -0.8) = 0"""
        sizer = KellySizer(win_rate=0.4, win_loss_ratio=0.5)
        qty = sizer.calculate(1_000_000, 100.0, 1_000_000)
        assert qty == 0

    def test_zero_price(self):
        sizer = KellySizer()
        assert sizer.calculate(1_000_000, 0, 1_000_000) == 0


# ===================================================================
# ATRSizer
# ===================================================================

class TestATRSizer:
    def test_atr_sizer_provided(self):
        """权益 100 万，ATR 2 元，risk_per_unit 0.02 → 风险金额 20000，数量 10000"""
        sizer = ATRSizer(risk_per_unit=0.02)
        qty = sizer.calculate(1_000_000, 100.0, 1_000_000, atr=2.0)
        assert qty == 10000

    def test_atr_sizer_default(self):
        """未提供 ATR → 默认 price * 0.02"""
        sizer = ATRSizer(risk_per_unit=0.02)
        qty = sizer.calculate(1_000_000, 100.0, 1_000_000)
        # ATR = 100 * 0.02 = 2，风险金额 = 1_000_000 * 0.02 = 20000
        # 数量 = 20000 / 2 = 10000
        assert qty == 10000

    def test_atr_sizer_zero_price(self):
        sizer = ATRSizer()
        assert sizer.calculate(1_000_000, 0, 1_000_000) == 0


# ===================================================================
# VolatilityTargetSizer
# ===================================================================

class TestVolatilityTargetSizer:
    def test_target_vol_equal(self):
        """实际波动率 = 目标波动率 → 全额投入"""
        sizer = VolatilityTargetSizer(target_vol=0.20)
        qty = sizer.calculate(1_000_000, 100.0, 1_000_000, historical_vol=0.20)
        assert qty == 10000  # 1_000_000 / 100

    def test_target_vol_high_vol(self):
        """实际波动率是目标的 2 倍 → 投入减半"""
        sizer = VolatilityTargetSizer(target_vol=0.20)
        qty = sizer.calculate(1_000_000, 100.0, 1_000_000, historical_vol=0.40)
        assert qty == 5000  # 减半

    def test_target_vol_low_vol(self):
        """实际波动率是目标的一半 → 投入加倍（上限 100%）"""
        sizer = VolatilityTargetSizer(target_vol=0.20)
        qty = sizer.calculate(1_000_000, 100.0, 1_000_000, historical_vol=0.10)
        # risk_pct = 0.2/0.1 = 2.0，但 min(2.0, 1.0) = 1.0
        assert qty == 10000  # 上限 100%

    def test_zero_price(self):
        sizer = VolatilityTargetSizer()
        assert sizer.calculate(1_000_000, 0, 1_000_000) == 0


# ===================================================================
# EqualWeightSizer
# ===================================================================

class TestEqualWeightSizer:
    def test_equal_weight(self):
        """10 只股票，权益 100 万，价格 100 → 每只 1000 股"""
        sizer = EqualWeightSizer(n_assets=10)
        qty = sizer.calculate(1_000_000, 100.0, 1_000_000)
        assert qty == 1000  # 100000 / 100

    def test_five_assets(self):
        """5 只股票 → 每只 20% 权益"""
        sizer = EqualWeightSizer(n_assets=5)
        qty = sizer.calculate(1_000_000, 100.0, 1_000_000)
        assert qty == 2000  # 200000 / 100

    def test_zero_price(self):
        sizer = EqualWeightSizer()
        assert sizer.calculate(1_000_000, 0, 1_000_000) == 0
