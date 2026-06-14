# -*- coding: utf-8 -*-
"""F019 信号管线系统测试"""

import pytest
from datetime import datetime, timedelta

from stockquant.strategy.signal import (
    Signal,
    SignalSide,
    SignalSource,
    SignalManager,
    SignalAuditLog,
    convert_ai_to_strategy,
    LOT_SIZE,
    MAIN_BOARD_LIMIT,
    CHINEXT_LIMIT,
    COMMISSION_RATE,
    STAMP_TAX_RATE,
    TRANSFER_FEE_RATE,
)


class TestPriceLimits:
    def test_main_board_buy_above_limit(self):
        """主板：买入价超过涨停板 → 无效"""
        sig = Signal(symbol="sh600519", side=SignalSide.BUY, target_price=1800.0)
        assert not sig.is_valid(prev_close=1600.0)  # 涨停 = 1760.0

    def test_main_board_sell_below_limit(self):
        """主板：卖出价低于跌停板 → 无效"""
        sig = Signal(symbol="sh600519", side=SignalSide.SELL, target_price=100.0)
        assert not sig.is_valid(prev_close=164.0)  # 跌停价 = 164*0.9 = 147.6

    def test_chinext_buy_above_limit(self):
        """创业板：买入价超过 ±20% 涨停板 → 无效"""
        sig = Signal(symbol="sz300750", side=SignalSide.BUY, target_price=100.0)
        assert not sig.is_valid(prev_close=75.0)  # 涨停 = 90.0

    def test_valid_buy_within_limit(self):
        """买入价在涨停范围内 → 有效"""
        sig = Signal(symbol="sh600519", side=SignalSide.BUY, target_price=180.0)
        assert sig.is_valid(prev_close=164.0)  # 180 < 180.4


class TestLotValidation:
    def test_not_multiple(self):
        """数量不是 100 的整数倍 → 无效"""
        sig = Signal(symbol="sh600519", side=SignalSide.BUY, target_quantity=150)
        assert not sig.is_valid()

    def test_exact_lot(self):
        """恰好 100 股 → 有效"""
        sig = Signal(symbol="sh600519", side=SignalSide.BUY, target_quantity=100)
        assert sig.is_valid()

    def test_500_shares(self):
        """500 股 → 有效"""
        sig = Signal(symbol="sh600519", side=SignalSide.BUY, target_quantity=500)
        assert sig.is_valid()


class TestFeeEstimation:
    def test_buy_fees(self):
        """买入费用估算：佣金(最低5) + 过户费"""
        sig = Signal(symbol="sh600519", side=SignalSide.BUY)
        fee = sig._estimate_fee(price=100.0, quantity=100, side="BUY")
        assert fee["amount"] == 10000.0
        assert fee["commission"] == 5.0  # 最低 5 元
        assert fee["stamp_tax"] == 0.0  # 买方无印花税
        assert fee["transfer_fee"] == 0.1  # 0.001% * 10000

    def test_sell_fees(self):
        """卖出费用估算：佣金 + 印花税 + 过户费"""
        sig = Signal(symbol="sh600519", side=SignalSide.SELL)
        fee = sig._estimate_fee(price=100.0, quantity=100, side="SELL")
        assert fee["stamp_tax"] == 5.0  # 0.05% * 10000

    def test_zero_quantity(self):
        """零数量 → 零费用"""
        sig = Signal(symbol="sh600519", side=SignalSide.BUY)
        fee = sig._estimate_fee(price=100.0, quantity=0, side="BUY")
        assert fee["total"] == 0


class TestSignalExpiry:
    def test_not_expired(self):
        """无过期时间 → 不过期"""
        sig = Signal(symbol="sh600519", side=SignalSide.BUY)
        assert not sig.is_expired()

    def test_expired(self):
        """过期时间 < 当前时间 → 已过期"""
        sig = Signal(symbol="sh600519", side=SignalSide.BUY, expires_at=datetime.now() - timedelta(minutes=5))
        assert sig.is_expired()

    def test_not_expired_yet(self):
        """过期时间 > 当前时间 → 未过期"""
        sig = Signal(symbol="sh600519", side=SignalSide.BUY, expires_at=datetime.now() + timedelta(hours=1))
        assert not sig.is_expired()


class TestDeduplication:
    def test_deduplicate_same_side_high_confidence(self):
        """同一标的、同一方向、高相似度 → 去重"""
        mgr = SignalManager()
        s1 = Signal(symbol="sh600519", side=SignalSide.BUY, confidence=0.8)
        s2 = Signal(symbol="sh600519", side=SignalSide.BUY, confidence=0.75)
        mgr.add_signal(s1)
        mgr.add_signal(s2)

        removed = mgr.deduplicate("sh600519")
        assert len(removed) >= 1

    def test_no_dedup_different_sides(self):
        """不同方向 → 不去重"""
        mgr = SignalManager()
        s1 = Signal(symbol="sh600519", side=SignalSide.BUY, confidence=0.8)
        s2 = Signal(symbol="sh600519", side=SignalSide.SELL, confidence=0.8)
        mgr.add_signal(s1)
        mgr.add_signal(s2)

        removed = mgr.deduplicate("sh600519")
        assert len(removed) == 0


class TestConflictResolution:
    def test_conservative_ai_hold(self):
        """保守模式：AI 建议 HOLD → 暂停"""
        mgr = SignalManager(conflict_resolution="conservative")
        s1 = Signal(symbol="sh600519", side=SignalSide.BUY, confidence=0.7, source=SignalSource.TRADITIONAL)
        s2 = Signal(symbol="sh600519", side=SignalSide.HOLD, confidence=0.6, source=SignalSource.AI_DECISION)
        mgr.add_signal(s1)
        mgr.add_signal(s2)

        result = mgr.resolve_conflicts("sh600519")
        assert result.side == SignalSide.HOLD
        assert result.source == SignalSource.AI_DECISION

    def test_aggressive_ai_override(self):
        """激进模式：AI 建议覆盖传统策略"""
        mgr = SignalManager(conflict_resolution="aggressive")
        s1 = Signal(symbol="sh600519", side=SignalSide.BUY, confidence=0.7, source=SignalSource.TRADITIONAL)
        s2 = Signal(symbol="sh600519", side=SignalSide.HOLD, confidence=0.6, source=SignalSource.AI_DECISION)
        s3 = Signal(symbol="sh600519", side=SignalSide.SELL, confidence=0.7, source=SignalSource.AI_DECISION)
        mgr.add_signal(s1)
        mgr.add_signal(s2)
        mgr.add_signal(s3)

        result = mgr.resolve_conflicts("sh600519")
        assert result.side == SignalSide.SELL  # AI 建议 SELL 覆盖
        assert result.source == SignalSource.AI_DECISION

    def test_no_conflict(self):
        """无冲突 → 返回最高优先级信号"""
        mgr = SignalManager()
        s1 = Signal(symbol="sh600519", side=SignalSide.BUY, confidence=0.7)
        s2 = Signal(symbol="sh600519", side=SignalSide.BUY, confidence=0.8)
        mgr.add_signal(s1)
        mgr.add_signal(s2)

        result = mgr.resolve_conflicts("sh600519")
        assert result.side == SignalSide.BUY


class TestConvertAiToStrategy:
    def test_valid_conversion(self):
        """有效 AI 信号 → 成功转换"""
        ai_signal = {
            "symbol": "sh600519",
            "side": "BUY",
            "confidence": 0.75,
            "reasoning": ["MACD 金叉", "东方财富情绪转好"],
            "target_price": 150.0,
            "target_quantity": 200,
            "expires_minutes": 30,
        }
        signal, warnings = convert_ai_to_strategy(ai_signal)
        assert signal.symbol == "sh600519"
        assert signal.side == SignalSide.BUY
        assert signal.confidence == 0.75
        assert signal.source == SignalSource.AI_DECISION
        assert signal.expires_at is not None

    def test_invalid_quantity_warning(self):
        """非 100 整数倍数量 → 警告"""
        ai_signal = {
            "symbol": "sh600519",
            "side": "BUY",
            "target_quantity": 150,
        }
        signal, warnings = convert_ai_to_strategy(ai_signal)
        assert len(warnings) >= 1
        assert any("150" in w for w in warnings)

    def test_missing_symbol(self):
        """缺少 symbol → 抛出 ValueError"""
        ai_signal = {"side": "BUY", "confidence": 0.5}
        with pytest.raises(ValueError):
            convert_ai_to_strategy(ai_signal)

    def test_unknown_side_defaults_to_hold(self):
        """未知方向 → 默认 HOLD"""
        ai_signal = {
            "symbol": "sh600519",
            "side": "FORWARD",
        }
        signal, warnings = convert_ai_to_strategy(ai_signal)
        assert signal.side == SignalSide.HOLD
        assert len(warnings) >= 1


class TestCleanupExpired:
    def test_cleanup_removes_expired(self):
        """清理过期信号 → 返回清理数量"""
        mgr = SignalManager()
        now = datetime.now()
        expired = Signal(symbol="sh600519", side=SignalSide.BUY, expires_at=now - timedelta(hours=1))
        active = Signal(symbol="sh600519", side=SignalSide.HOLD, expires_at=now + timedelta(hours=1))
        mgr.add_signal(expired)
        mgr.add_signal(active)

        removed = mgr.cleanup_expired()
        assert removed == 1
        assert mgr.signal_count == 1


class TestOrderParamsConversion:
    def test_to_order_params_rounds_lots(self):
        """to_order_params 将数量向下取整到 100 的倍数"""
        sig = Signal(symbol="sh600519", side=SignalSide.BUY, target_quantity=350)
        params = sig.to_order_params()
        assert params["quantity"] == 300  # 350 → 300

    def test_to_order_params_includes_fees(self):
        """to_order_params 包含费用估算"""
        sig = Signal(symbol="sh600519", side=SignalSide.BUY, target_price=100.0, target_quantity=100)
        params = sig.to_order_params()
        assert params["estimated_fees"]["amount"] == 10000.0
        assert "commission" in params["estimated_fees"]
        assert "stamp_tax" in params["estimated_fees"]


class TestSignalManagerAuxiliary:
    def test_get_highest_confidence(self):
        """获取最高置信度信号"""
        mgr = SignalManager()
        s1 = Signal(symbol="sh600519", side=SignalSide.BUY, confidence=0.6)
        s2 = Signal(symbol="sh600519", side=SignalSide.BUY, confidence=0.9)
        mgr.add_signal(s1)
        mgr.add_signal(s2)

        result = mgr.get_highest_confidence("sh600519")
        assert result.confidence == 0.9

    def test_get_signals_by_source(self):
        """按来源过滤信号"""
        mgr = SignalManager()
        s1 = Signal(symbol="sh600519", side=SignalSide.BUY, source=SignalSource.TRADITIONAL)
        s2 = Signal(symbol="sh600519", side=SignalSide.BUY, source=SignalSource.AI_DECISION)
        mgr.add_signal(s1)
        mgr.add_signal(s2)

        traditional = mgr.get_signals_by_source(SignalSource.TRADITIONAL)
        ai_signals = mgr.get_signals_by_source(SignalSource.AI_DECISION)
        assert len(traditional) == 1
        assert len(ai_signals) == 1

    def test_audit_log(self):
        """审计日志记录"""
        mgr = SignalManager()
        s = Signal(symbol="sh600519", side=SignalSide.BUY, confidence=0.7)
        mgr.add_signal(s)
        mgr.add_signal(s)

        log = mgr.get_audit_log()
        assert len(log) >= 2
        assert log[0].action == "created"
        assert log[1].action == "created"
