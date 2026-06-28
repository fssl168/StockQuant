# -*- coding: utf-8 -*-
"""F029 交易执行路由 — 下单/撤单/持仓/成交

已接入 PaperBroker 真实撮合引擎 + Portfolio 聚合模型。
- MARKET 订单：按最新行情价格即时撮合
- LIMIT 订单：进入 orderbook，后续获取行情时检查撮合
- 账户/持仓通过 Portfolio 模型管理
- 费用模型使用 engine 的 CommissionInfo
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from stockquant.api.deps import get_current_user, get_admin_user, get_trader_user
from stockquant.api.schemas import AccountSummaryResponse, PlaceOrderRequest, UserToken
from stockquant.api.routers.settings import _settings, _decrypt_value
from stockquant.engine.broker import PaperBroker, LiveBroker
from stockquant.engine.commission import CommissionInfo
from stockquant.engine.risk import RiskManager
from stockquant.ai.risk_agent import RiskAgent
from stockquant.models.bar import BarData
from stockquant.models.order import Order, OrderSide, OrderType
from stockquant.events import EventType as OrderStatus
from stockquant.models.portfolio import Portfolio
from stockquant.persistence.models import Position as PositionORM
from stockquant.persistence.models import get_engine as _get_db_engine
from stockquant.persistence.models import _default_db_url as _get_db_url

logger = logging.getLogger("stockquant.api.trading")

router = APIRouter()

# ====================================================================
# 共享交易状态 — 使用 engine 模型
# ====================================================================

# 初始资金 100 万（与 Account 默认值一致）
_initial_cash = 1_000_000.0

# Portfolio 实例（管理账户 + 持仓）
_portfolio = Portfolio(initial_cash=_initial_cash)

# PaperBroker 实例（撮合引擎）
_paper_broker = PaperBroker(
    slippage=None,  # 模拟盘不启用滑点
    limit_up_ratio=0.10,
    limit_down_ratio=0.10,
)

# 绑定 PaperBroker 与 Portfolio，使 get_positions/get_balance 返回真实数据
# （在 _orders_audit 定义后绑定）

# 佣金模型
_commission_info = CommissionInfo()

# 风控管理器
_risk_manager = RiskManager(
    max_position_pct=0.3,
    max_buy_amount=500_000.0,
    max_total_position_pct=0.9,
    max_daily_loss_pct=0.02,
    max_drawdown_pct=0.15,
    max_orders_per_minute=10,
    global_circuit_breaker_pct=0.05,
)

# 行情缓存（避免频繁网络请求）
_price_cache: dict[str, tuple[float, float]] = {}  # symbol -> (price, timestamp)
_price_cache_timeout = 60  # 缓存有效期 60 秒


# ====================================================================
# Broker 模式切换
# ====================================================================

def _get_broker():
    """根据配置返回 PaperBroker 或 LiveBroker。

    默认使用 PaperBroker（模拟盘）。
    切换实盘方式：在 settings 中设置 trading.broker = "live"，
    并配置对应券商参数（QMT_PATH / QMT_ACCOUNT / XTP / CTP 等）。

    支持的券商 API:
    - qmt: 迅投 QMT（通过 xtquant SDK）
    - xtp: 中泰证券 XTP 极速交易系统
    - ctp: 期货交易前置系统（CTP）
    """
    broker_mode = _settings.get("trading.broker", "paper")
    if broker_mode == "live":
        # 实盘模式：根据 api 类型选择券商
        api = _settings.get("trading.api", "qmt")
        if api == "qmt":
            try:
                from stockquant.execution.brokers.qmt_broker import QMTBroker
                return QMTBroker(
                    qmt_path=_settings.get("trading.qmt_path", ""),
                    account_id=_settings.get("trading.qmt_account", ""),
                )
            except ImportError:
                logger.warning("QMTBroker 导入失败，降级为 LiveBroker 骨架")
        elif api == "xtp":
            try:
                from stockquant.execution.brokers.xtp_broker import XTPBroker
                xtp_app_id = _settings.get("trading.xtp_app_id", "0")
                xtp_client_id = _settings.get("trading.xtp_client_id", "0")
                return XTPBroker(
                    user=_settings.get("trading.xtp_user", ""),
                    password=_decrypt_value(_settings.get("trading.xtp_password", "")),
                    app_id=int(xtp_app_id) if xtp_app_id else 0,
                    client_id=int(xtp_client_id) if xtp_client_id else 0,
                    server_addr=_settings.get("trading.xtp_server_addr", ""),
                    software_key=_settings.get("trading.xtp_software_key", ""),
                )
            except ImportError:
                logger.warning("XTPBroker 导入失败，降级为 LiveBroker 骨架")
        elif api == "ctp":
            try:
                from stockquant.execution.brokers.ctp_broker import CTPBroker
                return CTPBroker(
                    user=_settings.get("trading.ctp_user", ""),
                    password=_decrypt_value(_settings.get("trading.ctp_password", "")),
                    broker_id=_settings.get("trading.ctp_broker_id", ""),
                    front_addr=_settings.get("trading.ctp_front_addr", ""),
                    app_id=_settings.get("trading.ctp_app_id", ""),
                )
            except ImportError:
                logger.warning("CTPBroker 导入失败，降级为 LiveBroker 骨架")
        return LiveBroker(api=api)
    # 默认模拟盘
    return _paper_broker

# 待撮合的 LIMIT 订单簿（由 Portfolio 上的持仓管理）
# 格式: order_id -> Order（保持内存存储，因为 Order 是实时状态对象）
_pending_limit_orders: dict[str, Order] = {}

# 订单审计日志（API 层额外记录）
_orders_audit: dict[str, dict] = {}

# Unified data service reference (set by main.py)
_data_service = None


def set_data_service(ds):
    _data_service = ds


def set_storage(pending_orders_storage: dict, orders_audit_storage: dict):
    global _pending_limit_orders, _orders_audit
    # _pending_limit_orders 保持内存存储（Order 对象无法直接序列化）
    _orders_audit = orders_audit_storage

# 绑定 PaperBroker 与 Portfolio，使 get_positions/get_balance 返回真实数据
_paper_broker.bind_portfolio(_portfolio, _orders_audit)

# 幂等性键映射 — idempotency_key → order_id
_idempotency_keys: dict[str, str] = {}

# 幂等性缓存 — idempotency_key → {"result": dict, "timestamp": float}
# 缓存条目 60 秒后过期
_idempotency_cache: dict[str, dict] = {}

_IDEMPOTENCY_TTL = 60  # 秒


def _check_idempotency(key: str) -> dict | None:
    """检查幂等性缓存，命中且未过期则返回缓存结果，否则返回 None"""
    if not key or key not in _idempotency_cache:
        return None
    entry = _idempotency_cache[key]
    if time.time() - entry["timestamp"] > _IDEMPOTENCY_TTL:
        # 过期，清理
        _idempotency_cache.pop(key, None)
        _idempotency_keys.pop(key, None)
        return None
    return entry["result"]


def _store_idempotency(key: str, result: dict) -> None:
    """将订单结果存入幂等性缓存"""
    _idempotency_cache[key] = {"result": result, "timestamp": time.time()}
    # 清理过期条目
    now = time.time()
    expired = [k for k, v in _idempotency_cache.items() if now - v["timestamp"] > _IDEMPOTENCY_TTL]
    for k in expired:
        _idempotency_cache.pop(k, None)
        _idempotency_keys.pop(k, None)


# ====================================================================
# 崩溃恢复 — 持久化与恢复交易状态 (JSON)
# ====================================================================

_TRADING_STATE_PATH = Path.home() / ".stockquant" / "trading_state.json"


def _persist_trading_state() -> None:
    """将交易状态持久化到 JSON 文件，用于崩溃恢复。

    保存内容：
    - Portfolio 持仓
    - 待撮合 LIMIT 订单
    - 账户余额
    - 订单审计日志
    - 幂等性键映射
    """
    try:
        _TRADING_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

        # 持久化持仓
        positions_data = {}
        for symbol, pos in _portfolio.positions.items():
            if pos.quantity > 0:
                positions_data[symbol] = {
                    "quantity": pos.quantity,
                    "cost_price": pos.cost_price,
                    "current_price": pos.current_price,
                }

        # 持久化待撮合订单
        pending_data = {}
        for order_id, order in _pending_limit_orders.items():
            pending_data[order_id] = {
                "symbol": order.symbol,
                "side": order.side.value,
                "order_type": order.order_type.value,
                "price": order.price,
                "quantity": order.quantity,
                "order_id": order.order_id,
            }

        # 持久化账户余额
        account_data = {
            "cash": _portfolio.account.cash,
            "available_cash": _portfolio.account.available_cash,
            "initial_cash": _initial_cash,
        }

        state = {
            "positions": positions_data,
            "pending_orders": pending_data,
            "account": account_data,
            "orders_audit": _orders_audit,
            "idempotency_keys": _idempotency_keys,
        }

        tmp_path = _TRADING_STATE_PATH.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        # 原子替换
        os.replace(tmp_path, _TRADING_STATE_PATH)
        logger.debug("交易状态已持久化到 %s", _TRADING_STATE_PATH)
    except Exception as e:
        logger.warning(f"交易状态持久化失败: {e}")


def _recover_trading_state() -> None:
    """从 JSON 文件恢复交易状态（启动时调用）

    恢复内容：
    - 订单审计日志 (_orders_audit)
    - 幂等性键映射 (_idempotency_keys)
    - 账户余额
    - 持仓
    - 待撮合订单
    """
    if not _TRADING_STATE_PATH.exists():
        logger.info("交易状态文件不存在，跳过恢复")
        return

    try:
        with open(_TRADING_STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)

        # 恢复订单审计日志
        saved_audit = state.get("orders_audit", {})
        if saved_audit:
            _orders_audit.update(saved_audit)
            logger.info(f"已恢复 {len(saved_audit)} 条订单审计记录")

        # 恢复幂等性键映射
        saved_idempotency = state.get("idempotency_keys", {})
        if saved_idempotency:
            _idempotency_keys.update(saved_idempotency)
            logger.info(f"已恢复 {len(saved_idempotency)} 个幂等性键")

        # 恢复账户余额
        account_data = state.get("account", {})
        if account_data:
            _portfolio.account.cash = account_data.get("cash", _initial_cash)
            _portfolio.account.available_cash = account_data.get("available_cash", _initial_cash)
            logger.info(f"已恢复账户余额: cash={_portfolio.account.cash}")

        # 恢复持仓
        positions_data = state.get("positions", {})
        if positions_data:
            for symbol, pos_info in positions_data.items():
                _portfolio.add_fill(
                    symbol,
                    pos_info["quantity"],
                    pos_info["cost_price"],
                    is_today=True,
                )
            logger.info(f"已恢复 {len(positions_data)} 个持仓")

        # 恢复待撮合订单
        pending_data = state.get("pending_orders", {})
        if pending_data:
            for order_id, order_info in pending_data.items():
                order = Order(
                    symbol=order_info["symbol"],
                    side=OrderSide.BUY if order_info["side"] == "BUY" else OrderSide.SELL,
                    order_type=OrderType.LIMIT,
                    price=order_info["price"],
                    quantity=order_info["quantity"],
                    order_id=order_info["order_id"],
                    status=OrderStatus.ORDER_SUBMITTED.value,
                )
                _pending_limit_orders[order_id] = order
            logger.info(f"已恢复 {len(pending_data)} 个待撮合订单")

        logger.info("交易状态恢复完成")
    except Exception as e:
        logger.warning(f"交易状态恢复失败: {e}")


# 启动时恢复交易状态
_recover_trading_state()


# ====================================================================
# 工具函数
# ====================================================================

def _get_cached_price(symbol: str) -> float | None:
    """获取标的最新价格（带缓存）"""
    global _price_cache
    
    now = time.time()
    
    # 检查缓存
    if symbol in _price_cache:
        price, cached_time = _price_cache[symbol]
        if now - cached_time < _price_cache_timeout:
            return price
    
    # 缓存失效，重新获取
    try:
        bar = _get_latest_bar(symbol)
        if bar:
            _price_cache[symbol] = (bar.close, now)
            return bar.close
    except Exception as e:
        logger.warning(f"获取最新价格失败: {symbol}, {e}")
    
    return None


def _get_latest_bar(symbol: str) -> BarData | None:
    """get latest daily BarData via unified DataService layer"""
    try:
        ds = _data_service
        if ds is None:
            from stockquant.data.service import DataService
            ds = DataService()
        result = ds.get_kline(symbol, timeframe="1d", start="", end="")
        df = result.data
        if df is not None and not df.empty:
            row = df.iloc[-1]
            return BarData(
                symbol=symbol,
                datetime=row["datetime"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                turnover=float(row["turnover"] if "turnover" in df.columns else 0),
            )
    except Exception as e:
        logger.warning(f"get latest bar failed: {symbol}, {e}")
    return None


def _get_or_create_bar(symbol: str, price: float) -> BarData:
    """获取 BarData；失败时用当前价格构造一个简化 Bar"""
    bar = _get_latest_bar(symbol)
    if bar is not None:
        return bar
    logger.warning(f"行情获取失败 {symbol}，使用传入价格 {price} 构造 Bar")
    return BarData(
        symbol=symbol,
        datetime=datetime.now(),
        open=price,
        high=price,
        low=price,
        close=price,
        volume=0,
    )


def _to_order_type(ot: str) -> OrderType:
    """字符串 → OrderType"""
    mapping = {
        "MARKET": OrderType.MARKET,
        "LIMIT": OrderType.LIMIT,
        "STOP": OrderType.STOP,
        "STOP_LIMIT": OrderType.STOP_LIMIT,
    }
    return mapping.get(ot.upper(), OrderType.MARKET)


def _to_order_side(side: str) -> OrderSide:
    """字符串 → OrderSide"""
    if side.upper() in ("SELL", "SHORT"):
        return OrderSide.SELL
    return OrderSide.BUY


def _match_pending_limits(bar: BarData):
    """撮合待处理的 LIMIT 订单 — 当有新行情时调用"""
    remaining: list[str] = []
    for order_id, order in list(_pending_limit_orders.items()):
        # 涨跌停检查
        limit_up = bar.close * (1 + _paper_broker._limit_up_ratio)
        limit_down = bar.close * (1 - _paper_broker._limit_down_ratio)
        if order.price > limit_up or order.price < limit_down:
            order.update_status(OrderStatus.ORDER_REJECTED.value)
            _paper_broker.cancel_order(order)
            continue

        # 100 股整数倍
        if order.quantity % 100 != 0:
            order.update_status(OrderStatus.ORDER_REJECTED.value)
            _paper_broker.cancel_order(order)
            continue

        # 限价单撮合条件
        matched = False
        if order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY and order.price >= bar.close:
                # 买单限价 >= 市价，可以成交
                matched = True
            elif order.side == OrderSide.SELL and order.price <= bar.close:
                # 卖单限价 <= 市价，可以成交
                matched = True

        if matched:
            # 重新构建 Order（带正确 status）
            new_order = Order(
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                price=order.price,
                quantity=order.quantity,
                order_id=order.order_id,
                status=OrderStatus.ORDER_SUBMITTED.value,
            )
            trade = _paper_broker.place_order(new_order, bar)
            if trade:
                _apply_trade_to_portfolio(trade)
                _pending_limit_orders.pop(order_id)
                logger.info(f"LIMIT 订单已撮合: {order_id} {trade.side} {trade.symbol} x{trade.quantity} @ {trade.price}")
            else:
                remaining.append(order_id)
        else:
            remaining.append(order_id)

    # 清理已撮合的订单
    for order_id in list(_pending_limit_orders.keys()):
        if order_id not in remaining:
            _pending_limit_orders.pop(order_id, None)


def _apply_trade_to_portfolio(trade):
    """将 TradeData 应用到 Portfolio"""
    if trade.side == "Buy":
        _portfolio.add_fill(trade.symbol, trade.quantity, trade.price, is_today=True)
        # 扣减现金（含费用）
        cost = _commission_info.calc_buy_cost(trade.price * trade.quantity)
        _portfolio.account.deduct(cost)
    elif trade.side == "Sell":
        # 先计算卖出费用
        sell_cost = _commission_info.calc_sell_cost(trade.price * trade.quantity)
        # 从持仓扣减
        _portfolio.remove_position(trade.symbol, trade.quantity, trade.price)
        # 卖出所得现金减去费用
        net_proceeds = trade.price * trade.quantity - sell_cost
        _portfolio.account.cash += net_proceeds
        _portfolio.account.available_cash += net_proceeds


# ====================================================================
# 端点
# ====================================================================

@router.get("/trading/account", summary="账户信息")
async def get_account() -> Dict[str, Any]:
    """获取账户信息 — 从 Portfolio 模型读取"""
    acc = _portfolio.account
    positions = _portfolio.positions
    market_value = sum(p.market_value for p in positions.values() if p.quantity > 0)
    total_equity = acc.total_equity
    today_pnl = acc.unrealized_pnl
    return {
        "totalEquity": round(total_equity, 2),
        "cash": round(acc.cash, 2),
        "frozenCash": round(acc.cash - acc.available_cash, 2),
        "marketValue": round(market_value, 2),
        "availableCash": round(acc.available_cash, 2),
        "dailyPnl": round(today_pnl, 2),
        "dailyPnlPct": round(today_pnl / _initial_cash * 100, 2) if _initial_cash > 0 else 0,
        "positionValue": round(market_value, 2),  # 保留向后兼容
        "todayPnl": round(today_pnl, 2),          # 保留向后兼容
        "brokerMode": "paper",
    }


@router.post("/trading/order", summary="下单")
async def place_order(payload: PlaceOrderRequest, _user: UserToken = Depends(get_trader_user)) -> Dict[str, Any]:
    """提交订单 — 通过 PaperBroker 撮合"""
    # 幂等性检查：如果相同 idempotency_key 已提交，返回之前的订单结果
    idempotency_key = payload.idempotency_key
    if idempotency_key:
        cached = _check_idempotency(idempotency_key)
        if cached is not None:
            logger.info(f"幂等性命中: key={idempotency_key}")
            return cached

    symbol = payload.symbol
    side = payload.side
    order_type = payload.type
    price = payload.price
    quantity = payload.quantity

    if not symbol or quantity <= 0:
        raise HTTPException(status_code=400, detail="股票代码和数量不能为空")

    # A 股最小交易单位 100 股
    if int(quantity) % 100 != 0:
        raise HTTPException(status_code=400, detail="A 股交易数量必须为 100 股整数倍")

    order_side = _to_order_side(side)
    ot = _to_order_type(order_type)

    # 使用传入价格或行情价格
    if price > 0:
        exec_price = price
    else:
        bar = _get_latest_bar(symbol)
        exec_price = bar.close if bar else 0.0

    if exec_price <= 0:
        raise HTTPException(status_code=400, detail="无法获取行情价格，请检查股票代码")

    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now().isoformat()

    # 构建 Order 模型
    order = Order(
        symbol=symbol,
        side=order_side,
        order_type=ot,
        price=exec_price,
        quantity=quantity,
        order_id=order_id,
        status=OrderStatus.ORDER_SUBMITTED.value,
    )

    # 记录审计日志
    _orders_audit[order_id] = {
        "orderId": order_id,
        "id": order_id,  # 前端 rowKey="id" 期望
        "symbol": symbol,
        "side": side.upper(),
        "type": order_type.upper(),
        "price": exec_price,
        "quantity": quantity,
        "status": "SUBMITTED",
        "createdAt": now,
        "updatedAt": now,
    }

    # 记录幂等性键
    if idempotency_key:
        _idempotency_keys[idempotency_key] = order_id

    # 获取最新行情 Bar
    bar = _get_or_create_bar(symbol, exec_price)

    # LIMIT 订单：进入 orderbook 等待撮合
    if ot == OrderType.LIMIT:
        # 检查资金是否充足
        if order_side == OrderSide.BUY:
            needed_cash = exec_price * quantity + _commission_info.calc_buy_cost(exec_price * quantity)
            if needed_cash > _portfolio.account.available_cash:
                order.update_status(OrderStatus.ORDER_REJECTED.value)
                _orders_audit[order_id]["status"] = "REJECTED"
                _orders_audit[order_id]["updatedAt"] = datetime.now().isoformat()
                raise HTTPException(status_code=400, detail="可用资金不足")

        _pending_limit_orders[order_id] = order
        _orders_audit[order_id]["status"] = "SUBMITTED"
        _orders_audit[order_id]["updatedAt"] = datetime.now().isoformat()
        logger.info(f"LIMIT 订单已挂单: {order_id} {side} {symbol} x{quantity} @ {exec_price}")
        result = _orders_audit[order_id]
        if idempotency_key:
            _store_idempotency(idempotency_key, result)
        _persist_trading_state()
        return result

    # 风控检查：在撮合之前拦截不合规订单
    total_equity = _portfolio.account.total_equity
    risk_valid, risk_reason = _risk_manager.check(
        order=order,
        equity=total_equity,
        positions=_portfolio.positions,
        total_equity=total_equity,
    )
    if not risk_valid:
        _orders_audit[order_id]["status"] = "RISK_REJECTED"
        _orders_audit[order_id]["riskReason"] = risk_reason
        _orders_audit[order_id]["updatedAt"] = datetime.now().isoformat()

        # 记录到风控事件表
        try:
            from stockquant.api.routers.auth import _get_db_url
            from stockquant.persistence.repository_v2 import Repository
            _repo = Repository.instance()
            db_url = _get_db_url()
            _repo.save_risk_event(
                engine_url=db_url,
                user_id="",
                event_type="ORDER_RISK_REJECTED",
                severity="WARNING",
                detail=f"Order {order_id} rejected: {risk_reason}",
                order_id=order_id,
            )
        except Exception:
            pass

        # 如果触发熔断，自动冻结
        if "circuit breaker" in risk_reason.lower() or "drawdown" in risk_reason.lower() or "daily loss" in risk_reason.lower():
            _risk_manager.halt(risk_reason)

        logger.warning(f"订单被风控拒绝: {order_id} {risk_reason}")
        raise HTTPException(status_code=400, detail=f"风控拦截: {risk_reason}")

    # MARKET 订单：直接通过 PaperBroker 撮合
    if order_side == OrderSide.BUY:
        # 检查资金
        needed_cash = exec_price * quantity + _commission_info.calc_buy_cost(exec_price * quantity)
        if needed_cash > _portfolio.account.available_cash:
            order.update_status(OrderStatus.ORDER_REJECTED.value)
            _orders_audit[order_id]["status"] = "REJECTED"
            _orders_audit[order_id]["updatedAt"] = datetime.now().isoformat()
            raise HTTPException(status_code=400, detail="可用资金不足")

    trade = _paper_broker.place_order(order, bar)

    if trade is None:
        # 订单被拒绝（涨跌停等）
        _orders_audit[order_id]["status"] = "REJECTED"
        _orders_audit[order_id]["updatedAt"] = datetime.now().isoformat()
        result = _orders_audit[order_id]
        if idempotency_key:
            _store_idempotency(idempotency_key, result)
        return result

    # 将成交应用到 Portfolio
    _apply_trade_to_portfolio(trade)

    # 更新审计日志
    _orders_audit[order_id]["status"] = "FILLED"
    _orders_audit[order_id]["filledPrice"] = trade.price
    _orders_audit[order_id]["filledAt"] = now
    _orders_audit[order_id]["updatedAt"] = datetime.now().isoformat()

    # 持久化交易状态（崩溃恢复）
    _persist_trading_state()

    logger.info(f"订单已撮合: {order_id} {trade.side} {trade.symbol} x{trade.quantity} @ {trade.price}")
    result = _orders_audit[order_id]
    if idempotency_key:
        _store_idempotency(idempotency_key, result)
    return result


@router.delete("/trading/order/{order_id}", summary="撤单")
async def cancel_order(order_id: str, _user: UserToken = Depends(get_trader_user)) -> Dict[str, Any]:
    """撤销订单 — 从 pending limit 订单簿或订单审计中查找"""
    # 优先从 pending limit 订单簿查找
    if order_id in _pending_limit_orders:
        order = _pending_limit_orders.pop(order_id)
        _paper_broker.cancel_order(order)
        _orders_audit[order_id]["status"] = "CANCELLED"
        _orders_audit[order_id]["updatedAt"] = datetime.now().isoformat()
        _persist_trading_state()
        logger.info(f"挂单已撤销: {order_id}")
        return {"success": True, "orderId": order_id, "status": "CANCELLED"}

    # 其次从审计日志查找未成交订单
    if order_id not in _orders_audit:
        raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在")

    audit = _orders_audit[order_id]
    if audit["status"] in ("FILLED", "CANCELLED", "REJECTED"):
        raise HTTPException(status_code=400, detail=f"订单状态 {audit['status']} 不可撤单")

    audit["status"] = "CANCELLED"
    audit["updatedAt"] = datetime.now().isoformat()
    _persist_trading_state()
    logger.info(f"订单已撤销: {order_id}")
    return {"success": True, "orderId": order_id, "status": "CANCELLED"}


@router.get("/trading/positions", summary="持仓列表")
async def get_positions():
    """获取当前持仓 — 从 Portfolio 模型（内存）和 数据库 合并读取。

    内存持仓（_portfolio）由 PaperBroker 撮合产生，
    数据库持仓（Position ORM）由持久化层维护，两者合并去重返回。
    """
    result = []
    seen = set()

    # 1）内存持仓
    for symbol, pos in _portfolio.positions.items():
        if pos.quantity <= 0:
            continue
        seen.add(symbol)
        price = _get_cached_price(symbol)
        if price:
            pos.update_price(price)

        result.append({
            "symbol": pos.symbol,
            "name": pos.symbol,
            "shares": pos.quantity,
            "cost": round(pos.cost_price, 2),
            "price": round(pos.current_price, 2),
            "marketValue": round(pos.market_value, 2),
            "pnl": round(pos.pnl, 2),
            "pnlPct": round((pos.current_price - pos.cost_price) / pos.cost_price * 100, 2)
                        if pos.cost_price > 0 else 0,
        })

    # 2）数据库持仓（补充内存中未覆盖的）
    try:
        db_url = _get_db_url()
        engine = _get_db_engine(db_url)
        from sqlalchemy import select
        from sqlalchemy.orm import Session
        with Session(engine) as session:
            stmt = select(PositionORM).where(PositionORM.quantity > 0)
            rows = session.execute(stmt).scalars().all()
            for row in rows:
                if row.symbol in seen:
                    continue
                seen.add(row.symbol)
                result.append({
                    "symbol": row.symbol,
                    "name": row.symbol,
                    "shares": row.quantity,
                    "cost": round(row.cost_price, 2),
                    "price": round(row.cost_price, 2),  # DB 持仓暂无实时价格，先用成本价
                    "marketValue": round(row.quantity * row.cost_price, 2),
                    "pnl": 0.0,
                    "pnlPct": 0.0,
                })
    except Exception as e:
        logger.warning("从数据库加载持仓失败: %s", e)

    return result


@router.get("/trading/trades", summary="成交记录")
async def get_trades():
    """获取成交记录 — 从 PaperBroker trade_log 读取"""
    result = []
    for trade in _paper_broker.trade_log:
        ts = datetime.fromtimestamp(trade.timestamp).isoformat() if trade.timestamp else None
        result.append({
            "id": trade.trade_id,          # 前端 rowKey="id" 期望
            "tradeId": trade.trade_id,     # 保留：向后兼容
            "orderId": trade.order_id,
            "symbol": trade.symbol,
            "side": trade.side,
            "price": trade.price,
            "quantity": trade.quantity,
            "amount": round(trade.price * trade.quantity, 2),
            "commission": trade.commission,
            "timestamp": ts,               # 前端 dataIndex="timestamp" 期望
            "filledAt": ts,                # 保留：向后兼容
        })
    return sorted(result, key=lambda t: t.get("filledAt", "") or "", reverse=True)


@router.get("/trading/orders", summary="订单列表")
async def get_orders(_user: UserToken = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """获取订单列表 — 合并审计日志 + pending limit 订单"""
    result = list(_orders_audit.values())
    # 添加 pending limit 订单
    for order_id, order in _pending_limit_orders.items():
        if order_id not in _orders_audit:
            now = datetime.now().isoformat()
            _orders_audit[order_id] = {
                "orderId": order_id,
                "id": order_id,  # 前端 rowKey="id" 期望
                "symbol": order.symbol,
                "side": order.side.value,
                "type": order.order_type.value,
                "price": order.price,
                "quantity": order.quantity,
                "status": "SUBMITTED",
                "createdAt": now,
                "updatedAt": now,
            }
            result.append(_orders_audit[order_id])
    # 为已有订单补充 id 字段（向后兼容）
    for order in result:
        if "id" not in order:
            order["id"] = order.get("orderId", "")
    return result


@router.get("/trading/account-status", summary="账户连接状态")
async def get_account_status(_user: UserToken = Depends(get_current_user)) -> AccountSummaryResponse:
    """获取当前券商配置下的账户连接状态。

    测试当前券商配置（trading.broker + trading.api）下的连接状态，
    返回余额和持仓摘要。如果券商 SDK 未连接，显示模拟模式。
    """
    broker = _get_broker()
    broker_type = getattr(broker, "api", "paper")
    broker_name = broker_type.upper() if broker_type != "paper" else "PAPER"

    if getattr(broker, "connected", False):
        balance = broker.get_balance()
        positions = broker.get_positions()
        return {
            "connected": True,
            "brokerType": broker_type,
            "brokerName": broker_name,
            "balance": balance,
            "positions": positions,
        }
    else:
        # 判断是否为 live broker 但未连接
        broker_mode = _settings.get("trading.broker", "paper")
        is_live_config = broker_mode == "live"
        message = (
            "Broker 未连接，当前为模拟模式"
            if not is_live_config
            else "Broker 未连接（配置为实盘但 SDK 不可用或参数不正确）"
        )
        return {
            "connected": False,
            "brokerType": broker_type,
            "brokerName": broker_name,
            "message": message,
            "balance": broker.get_balance() if hasattr(broker, "get_balance") else {"live": False, "api": broker_type, "cash": 0, "frozen": 0, "equity": 0},
        }


# ====================================================================
# 风控端点
# ====================================================================

@router.get("/trading/risk/status", summary="风控状态")
async def get_risk_status(_user: UserToken = Depends(get_current_user)) -> Dict[str, Any]:
    """获取当前风控状态和历史事件。"""
    from stockquant.api.routers.auth import _get_db_url
    from stockquant.persistence.repository_v2 import Repository
    _repo = Repository.instance()

    db_url = _get_db_url()
    events = _repo.list_risk_events(db_url, user_id="", limit=20)
    return {
        "halted": _risk_manager.is_halted,
        "haltReason": _risk_manager._halt_reason if _risk_manager._halted else "",
        "config": {
            "maxPositionPct": _risk_manager._max_position_pct,
            "maxBuyAmount": _risk_manager._max_buy_amount,
            "maxTotalPositionPct": _risk_manager._max_total_position_pct,
            "maxDailyLossPct": _risk_manager._max_daily_loss_pct,
            "maxDrawdownPct": _risk_manager._max_drawdown_pct,
            "maxOrdersPerMinute": _risk_manager._max_orders_per_minute,
            "globalCircuitBreakerPct": _risk_manager._global_circuit_breaker_pct,
        },
        "recentEvents": events,
    }


@router.post("/trading/risk/resume", summary="恢复交易")
async def resume_trading(_user: UserToken = Depends(get_admin_user)) -> Dict[str, Any]:
    """恢复被熔断的交易。"""
    _risk_manager.resume()

    # 记录到风控事件表
    try:
        from stockquant.api.routers.auth import _get_db_url
        from stockquant.persistence.repository_v2 import Repository
        _repo = Repository.instance()
        db_url = _get_db_url()
        _repo.save_risk_event(
            engine_url=db_url,
            user_id="",
            event_type="TRADE_RESUMED",
            severity="INFO",
            detail="Trading resumed by admin",
        )
    except Exception:
        pass

    logger.info("Trading resumed by admin")
    return {"success": True, "message": "交易已恢复"}

@router.get("/trading/risk/report", summary="风控报告")
async def get_risk_report_endpoint(_user: UserToken = Depends(get_trader_user)) -> Dict[str, Any]:
    """获取动态风控报告 — 参数调整历史 + 异常检测 + 黑天鹅状态"""
    try:
        risk_agent = RiskAgent()
        report = risk_agent.get_risk_report()
        return report
    except ImportError as e:
        raise HTTPException(status_code=501, detail=f"风控模块不可用: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取风控报告失败: {str(e)}")
