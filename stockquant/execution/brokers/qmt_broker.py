# -*- coding: utf-8 -*-
"""QMT 券商 Gateway 实现 -- 通过 xtquant SDK 连接 QMT 客户端

注意：QMT 客户端需要单独运行，本模块通过 xtquant SDK 与之通信。
如未安装 xtquant，将降级为模拟模式。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.events import EventType
from stockquant.execution.gateway_base import (
    BaseGateway,
    GatewayConfig,
    GatewayEvent,
    GatewayState,
)

logger = logging.getLogger("stockquant.execution.qmt")

# xtquant 可选导入
try:
    from xtquant import xttrader, xtconstant
    QMT_AVAILABLE = True
except ImportError:
    QMT_AVAILABLE = False
    logger.info("xtquant 未安装，QMT Broker 将以模拟模式运行")


class QMTBroker(BaseGateway):
    """QMT 券商 Gateway -- 通过 xtquant SDK 连接 QMT 客户端

    继承 BaseGateway，实现统一的生命周期管理（状态机、心跳、重连、订单同步）。
    """

    api = "qmt"

    def __init__(
        self,
        qmt_path: str = "",
        account_id: str = "",
        config: GatewayConfig = None,
        _mock_xt_trader: Any = None,
        **kwargs,
    ):
        """
        Args:
            qmt_path: QMT 客户端数据目录路径
            account_id: QMT 交易账户 ID
            config: Gateway 配置，默认使用 GatewayConfig()
            _mock_xt_trader: 测试用 Mock SDK，注入后直接进入 LOGGED_IN 状态
            **kwargs: 额外参数（保留扩展）
        """
        self._qmt_path = qmt_path
        self._account_id = account_id
        self._xt_trader = _mock_xt_trader  # 测试用 mock SDK

        super().__init__(config=config, **kwargs)

        if self._xt_trader is not None:
            # Mock SDK 模式：直接设为 LOGGED_IN
            self._transition(GatewayState.LOGGED_IN)
            logger.info("QMT Gateway 使用 Mock SDK，已进入 LOGGED_IN 状态")

    # ── 抽象方法实现 ────────────────────────────────────────────────

    def _do_connect(self) -> bool:
        """连接 QMT 客户端

        Returns:
            True 连接成功
        """
        if not QMT_AVAILABLE:
            logger.warning("xtquant 未安装，无法连接 QMT 客户端")
            return False

        if not self._qmt_path:
            logger.warning("QMT 客户端路径未配置")
            return False

        try:
            self._xt_trader = xttrader.XtQuantTrader(self._qmt_path, 1)
            logger.info("QMT 连接成功: %s", self._account_id)
            return True
        except Exception as e:
            logger.warning("QMT 连接失败: %s", e)
            return False

    def _do_disconnect(self) -> None:
        """断开 QMT 客户端连接"""
        try:
            if self._xt_trader is not None:
                # xtquant SDK 没有显式断开方法，释放引用即可
                self._xt_trader = None
            logger.info("QMT 已断开连接: %s", self._account_id)
        except Exception as e:
            logger.warning("QMT 断开异常: %s", e)

    def _do_login(self) -> bool:
        """QMT 登录

        QMT 客户端通过本地 IPC 通信，xtquant 连接即表示客户端已登录。
        无需额外登录步骤。

        Returns:
            True 登录成功
        """
        if self._xt_trader is not None:
            logger.info("QMT 登录成功: %s", self._account_id)
            return True
        logger.warning("QMT 登录失败: xt_trader 未初始化")
        return False

    def _do_heartbeat(self) -> None:
        """心跳保活

        QMT 心跳通过查询资产实现（query_stock_asset），确认连接有效。
        """
        if self._xt_trader is not None:
            try:
                self._xt_trader.query_stock_asset(self._account_id)
                logger.debug("QMT 心跳正常")
            except Exception as e:
                logger.warning("QMT 心跳失败: %s", e)
                raise
        else:
            logger.debug("QMT 心跳跳过: xt_trader 不可用")

    # ── 可选方法覆盖 ────────────────────────────────────────────────

    def _do_place_order(self, order: Order) -> tuple:
        """通过 QMT 下单

        包含 100 股整数倍校验逻辑。

        Args:
            order: 订单

        Returns:
            (xt_order_id: str, True) 成功
            (xt_order_id, False) 失败
        """
        # 100 股整数倍校验
        if order.quantity % 100 != 0:
            logger.warning(
                "订单 %s 数量 %d 不是 100 的整数倍，已拒绝",
                order.order_id, order.quantity,
            )
            return ("", False)

        if not self.logged_in or self._xt_trader is None:
            logger.warning("QMT 未登录或 xt_trader 不可用，订单 %s 无法提交", order.order_id)
            return ("", False)

        try:
            if not QMT_AVAILABLE:
                # Mock SDK 或无 SDK 模式，使用简单整数参数
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
                # 真实 QMT SDK，使用 xtconstant 常量
                side = xtconstant.STOCK_BUY if order.side == OrderSide.BUY else xtconstant.STOCK_SELL
                order_type = (
                    xtconstant.FIX_PRICE
                    if order.order_type == OrderType.LIMIT
                    else xtconstant.MARKET_BEST5_TO_CANCEL
                )
                xt_order_id = self._xt_trader.order_stock(
                    account=self._account_id,
                    stock_code=order.symbol,
                    order_type=order_type,
                    order_volume=int(order.quantity),
                    price_type=side,
                    price=float(order.price),
                )

            logger.info(
                "QMT 订单已提交: order_id=%s, xt_order_id=%s",
                order.order_id, xt_order_id,
            )
            return (str(xt_order_id), True)

        except Exception as e:
            logger.error("QMT 下单异常: %s", e, exc_info=True)
            return ("", False)

    def _do_cancel_order(self, order: Order) -> bool:
        """通过 QMT 撤单

        Args:
            order: 要撤销的订单

        Returns:
            True 撤单成功
        """
        if not self.logged_in or self._xt_trader is None:
            logger.warning("QMT 未登录，无法撤单: %s", order.order_id)
            return False

        try:
            self._xt_trader.cancel_order_stock(self._account_id, order.order_id)
            logger.info("QMT 撤单请求已发送: %s", order.order_id)
            return True
        except Exception as e:
            logger.error("QMT 撤单异常: %s", e, exc_info=True)
            return False

    def _do_query_positions(self) -> dict:
        """查询 QMT 持仓

        Returns:
            持仓字典 {stock_code: {quantity, price}}
        """
        if not self.logged_in or self._xt_trader is None:
            return {}

        try:
            positions = self._xt_trader.query_stock_positions(self._account_id)
            return {
                p.stock_code: {"quantity": p.volume, "price": p.open_price}
                for p in positions
            }
        except Exception as e:
            logger.error("QMT 查询持仓异常: %s", e, exc_info=True)
            return {}

    def _do_query_balance(self) -> dict:
        """查询 QMT 资产

        Returns:
            资产字典 {cash, frozen, equity, ...}
        """
        if not self.logged_in or self._xt_trader is None:
            return {}

        try:
            asset = self._xt_trader.query_stock_asset(self._account_id)
            return {
                "live": True,
                "api": "qmt",
                "cash": asset.cash,
                "frozen": asset.frozen_cash,
                "equity": asset.total_asset,
            }
        except Exception as e:
            logger.error("QMT 查询资产异常: %s", e, exc_info=True)
            return {}

    def _do_query_orders(self) -> list:
        """查询 QMT 挂单

        通过 query_stock_orders 查询当前挂单状态。

        Returns:
            挂单列表 [{order_id, status, ...}]
        """
        if not self.logged_in or self._xt_trader is None:
            return []

        try:
            xt_orders = self._xt_trader.query_stock_orders(self._account_id)
            result = []
            for xt_order in xt_orders:
                # 将 xtconstant 状态映射到 EventType 状态
                if QMT_AVAILABLE:
                    status = self._map_xt_status(xt_order.order_status)
                else:
                    status = xt_order.order_status

                result.append({
                    "order_id": str(xt_order.order_id),
                    "status": status,
                    "symbol": xt_order.stock_code,
                    "price": xt_order.price,
                    "quantity": xt_order.order_volume,
                    "filled_quantity": xt_order.traded_volume,
                })
            return result
        except Exception as e:
            logger.error("QMT 查询挂单异常: %s", e, exc_info=True)
            return []

    def _do_logout(self) -> None:
        """QMT 登出

        QMT 通过 IPC 通信，无需显式登出。
        """
        logger.info("QMT 登出: %s", self._account_id)

    # ── 内部辅助 ────────────────────────────────────────────────────

    @staticmethod
    def _map_xt_status(xt_status: int) -> str:
        """将 xtconstant 订单状态映射到 EventType 订单状态

        Args:
            xt_status: xtconstant 订单状态值

        Returns:
            EventType 订单状态字符串
        """
        if not QMT_AVAILABLE:
            return str(xt_status)

        try:
            if xt_status == xtconstant.ORDER_UNKOWN:
                return EventType.ORDER_PENDING.value
            elif xt_status == xtconstant.ORDER_NOT_REPORTED:
                return EventType.ORDER_SUBMITTED.value
            elif xt_status == xtconstant.ORDER_WAIT_REPORTING:
                return EventType.ORDER_SUBMITTED.value
            elif xt_status == xtconstant.ORDER_REPORTED:
                return EventType.ORDER_SUBMITTED.value
            elif xt_status == xtconstant.ORDER_PART_CANCEL:
                return EventType.ORDER_PARTIAL_FILL.value
            elif xt_status == xtconstant.ORDER_ALL_CANCEL:
                return EventType.ORDER_CANCELLED.value
            elif xt_status == xtconstant.ORDER_REJECTED:
                return EventType.ORDER_REJECTED.value
            else:
                return str(xt_status)
        except Exception:
            return str(xt_status)

    # ── 兼容旧接口（保持向后兼容） ──────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"QMTBroker(state={self._state.value}, "
            f"account={self._account_id}, "
            f"orders={len(self._open_orders)}, "
            f"stats={self._stats})"
        )

