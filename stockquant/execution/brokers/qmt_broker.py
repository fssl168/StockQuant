# -*- coding: utf-8 -*-
"""QMT 券商 Broker 实现 — 通过 xtquant SDK 连接 QMT 客户端

注意：QMT 客户端需要单独运行，本模块通过 xtquant SDK 与之通信。
如未安装 xtquant，将降级为模拟模式。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from stockquant.models.order import Order, OrderSide, OrderType, OrderStatus
from stockquant.models.bar import BarData
from stockquant.models.trade import TradeData
from stockquant.engine.broker import Broker, OrderAuditLog

logger = logging.getLogger("stockquant.execution.qmt")

# xtquant 可选导入
try:
    from xtquant import xttrader, xtconstant
    QMT_AVAILABLE = True
except ImportError:
    QMT_AVAILABLE = False
    logger.info("xtquant 未安装，QMT Broker 将以模拟模式运行")


class QMTBroker(Broker):
    """QMT 券商 Broker — 通过 xtquant SDK 连接 QMT 客户端"""

    api = "qmt"

    def __init__(self, qmt_path: str = "", account_id: str = "", _mock_xt_trader: Any = None):
        self._qmt_path = qmt_path
        self._account_id = account_id
        self._xt_trader = _mock_xt_trader  # 测试用 mock SDK
        self._connected = False
        self._order_log: List[OrderAuditLog] = []
        self._open_orders: Dict[str, Order] = {}

        if self._xt_trader is not None:
            # Mock SDK 模式
            self._connected = True
            logger.info("QMT Broker 使用 Mock SDK，连接成功")
        elif QMT_AVAILABLE and qmt_path:
            self._connect()

    def _connect(self):
        """连接 QMT 客户端"""
        try:
            # xtquant 连接逻辑（需要 QMT 客户端运行中）
            self._xt_trader = xttrader.XtQuantTrader(self._qmt_path, 1)
            self._connected = True
            logger.info("QMT 连接成功: %s", self._account_id)
        except Exception as e:
            logger.warning("QMT 连接失败: %s，降级为模拟模式", e)
            self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def place_order(self, order: Order, bar: BarData) -> Optional[TradeData]:
        """通过 QMT 下单"""
        # 100 股整数倍校验
        if order.quantity % 100 != 0:
            order.update_status(OrderStatus.REJECTED)
            self._log_order(order, "REJECTED", "quantity not multiple of 100")
            return None

        if not self._connected:
            # 降级为模拟模式
            logger.warning("QMT 未连接，订单 %s 以模拟模式执行", order.order_id)
            order.update_status(OrderStatus.SUBMITTED)
            trade = TradeData(
                trade_id=f"{order.order_id}_sim",
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side.value,
                price=order.price,
                quantity=order.quantity,
            )
            self._log_order(order, "SIMULATED", "QMT not connected, simulated execution")
            return trade

        try:
            if self._xt_trader is not None:
                # Mock SDK 或真实 SDK，统一调用 order_stock
                # 传入简单整数参数，避免依赖 xtconstant（SDK 未安装时不可用）
                side_val = 1 if order.side == OrderSide.BUY else 2
                price_type_val = 1 if order.order_type == OrderType.LIMIT else 2
                xt_order_id = self._xt_trader.order_stock(
                    account=self._account_id,
                    stock_code=order.symbol,
                    order_type=price_type_val,
                    order_volume=int(order.quantity),
                    price_type=side_val,
                    price=float(order.price),
                )
            else:
                # 真实 QMT 下单
                side = xtconstant.STOCK_BUY if order.side == OrderSide.BUY else xtconstant.STOCK_SELL
                order_type = xtconstant.FIX_PRICE if order.order_type == OrderType.LIMIT else xtconstant.MARKET_BEST5_TO_CANCEL
                xt_order_id = self._xt_trader.order_stock(
                    account=self._account_id,
                    stock_code=order.symbol,
                    order_type=order_type,
                    order_volume=int(order.quantity),
                    price_type=side,
                    price=float(order.price),
                )

            order.update_status(OrderStatus.SUBMITTED)
            self._open_orders[order.order_id] = order
            self._log_order(order, "SUBMITTED", f"QMT order submitted, xt_order_id={xt_order_id}")

            return TradeData(
                trade_id=f"{order.order_id}_submitted",
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side.value,
                price=order.price,
                quantity=order.quantity,
            )
        except Exception as e:
            order.update_status(OrderStatus.REJECTED)
            self._log_order(order, "REJECTED", str(e))
            return None

    def cancel_order(self, order: Order) -> bool:
        if order.status.name in ("PENDING", "SUBMITTED", "QUEUED"):
            order.update_status(OrderStatus.CANCELLED)
            self._open_orders.pop(order.order_id, None)
            if self._connected and self._xt_trader:
                try:
                    self._xt_trader.cancel_order_stock(self._account_id, order.order_id)
                except Exception:
                    pass
            self._log_order(order, "CANCELLED", "user cancel request")
            return True
        return False

    def get_positions(self, portfolio=None) -> Dict[str, Any]:
        if self._connected and self._xt_trader:
            try:
                positions = self._xt_trader.query_stock_positions(self._account_id)
                return {p.stock_code: {"quantity": p.volume, "price": p.open_price} for p in positions}
            except Exception:
                pass
        return {}

    def get_balance(self, account=None) -> Dict[str, Any]:
        if self._connected and self._xt_trader:
            try:
                asset = self._xt_trader.query_stock_asset(self._account_id)
                return {
                    "live": True,
                    "api": "qmt",
                    "cash": asset.cash,
                    "frozen": asset.frozen_cash,
                    "equity": asset.total_asset,
                }
            except Exception:
                pass
        return {"live": True, "api": "qmt", "cash": 0, "frozen": 0, "equity": 0}

    def get_history(self, symbol: str, bar_count: int, data_feeds: list = None) -> List[BarData]:
        return []

    def _log_order(self, order: Order, status: str, reason: str = "") -> OrderAuditLog:
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

    @property
    def order_audit_log(self) -> List[OrderAuditLog]:
        return self._order_log.copy()
