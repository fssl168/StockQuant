# -*- coding: utf-8 -*-
"""MatchingEngine - 统一的订单撮合引擎

用于回测和实盘的订单撮合逻辑统一：
- 回测 BacktestBroker 使用此引擎进行模拟撮合
- 实盘 LiveBroker 使用此引擎进行本地预校验

支持限价单、市价单、止损单的撮合逻辑。
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Tuple

from stockquant.events import EventType

logger = logging.getLogger("stockquant.matching")


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


# Order status aliases — map EventType values to matching engine usage
# PENDING, SUBMITTED, PARTIAL_FILLED, FILLED, CANCELLED, REJECTED


@dataclass
class Order:
    """订单数据模型"""
    order_id: str
    user_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: float
    quantity: int
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    status: str = EventType.ORDER_PENDING.value
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class Tick:
    """行情tick数据"""
    symbol: str
    timestamp: datetime
    last: float       # 最新价
    ask1: float       # 卖一价
    bid1: float       # 买一价
    ask_vol1: int     # 卖一量
    bid_vol1: int     # 买一量
    volume: int       # 成交量
    amount: float     # 成交额


class MatchingEngine:
    """订单撮合引擎
    
    统一的撮合逻辑，用于：
    1. 回测模拟撮合
    2. 实盘本地预校验
    3. 模拟实盘模式
    """
    
    def __init__(
        self,
        price_limit_ratio: float = 0.1,
        slippage: float = 0.0,
        commission_rate: float = 0.00025,
        min_commission: float = 5.0,
    ):
        self.price_limit_ratio = price_limit_ratio
        self.slippage = slippage
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        
    def check_order_validity(self, order: Order, tick: Tick) -> Tuple[bool, str]:
        """验证订单合法性
        
        Args:
            order: 订单
            tick: 当前行情
            
        Returns:
            (is_valid, error_message)
        """
        # 检查价格是否为正
        if order.price <= 0 and order.order_type != OrderType.MARKET:
            return False, "价格必须为正数"
            
        # 检查数量是否为正
        if order.quantity <= 0:
            return False, "数量必须为正数"
            
        # 检查数量是否为100的整数倍（A股）
        if order.quantity % 100 != 0:
            return False, "数量必须是100的整数倍"
            
        # 限价单价格检查
        if order.order_type == OrderType.LIMIT:
            if tick:
                # 检查是否超出涨跌幅限制
                if order.side == OrderSide.BUY:
                    max_price = tick.last * (1 + self.price_limit_ratio)
                    if order.price > max_price:
                        return False, f"买入价格超过涨停价 {max_price:.2f}"
                else:
                    min_price = tick.last * (1 - self.price_limit_ratio)
                    if order.price < min_price:
                        return False, f"卖出价格低于跌停价 {min_price:.2f}"
                        
        return True, ""
    
    def match_order(self, order: Order, tick: Tick) -> Optional[Dict]:
        """撮合订单
        
        Args:
            order: 订单
            tick: 当前行情
            
        Returns:
            成交记录 dict 或 None（未成交）
        """
        is_valid, error = self.check_order_validity(order, tick)
        if not is_valid:
            logger.warning(f"订单 {order.order_id} 校验失败: {error}")
            order.status = EventType.ORDER_REJECTED.value
            return None
            
        # 计算成交价格
        fill_price = self._calculate_fill_price(order, tick)
        
        # 成交数量（简化为全部成交）
        fill_qty = order.quantity - order.filled_quantity
        if fill_qty <= 0:
            return None
            
        # 计算手续费
        commission = self._calculate_commission(fill_price * fill_qty)
        
        # 更新订单状态
        order.filled_quantity += fill_qty
        order.avg_fill_price = (
            (order.avg_fill_price * order.filled_quantity + fill_price * fill_qty)
            / order.filled_quantity
        )
        
        if order.filled_quantity >= order.quantity:
            order.status = EventType.ORDER_FILLED.value
        else:
            order.status = EventType.ORDER_PARTIAL_FILL.value
            
        # 返回成交记录
        return {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "fill_price": fill_price,
            "fill_quantity": fill_qty,
            "commission": commission,
            "fill_time": datetime.now().isoformat(),
        }
    
    def _calculate_fill_price(self, order: Order, tick: Tick) -> float:
        """计算成交价格
        
        考虑滑点：
        - 买入时：成交价 = min(ask, order_price) * (1 + slippage)
        - 卖出时：成交价 = max(bid, order_price) * (1 - slippage)
        """
        if order.order_type == OrderType.MARKET:
            # 市价单
            if order.side == OrderSide.BUY:
                fill_price = tick.ask1
            else:
                fill_price = tick.bid1
        else:
            # 限价单
            if order.side == OrderSide.BUY:
                fill_price = min(order.price, tick.ask1)
            else:
                fill_price = max(order.price, tick.bid1)
                
        # 加上滑点
        if order.side == OrderSide.BUY:
            fill_price *= (1 + self.slippage)
        else:
            fill_price *= (1 - self.slippage)
            
        return round(fill_price, 2)
    
    def _calculate_commission(self, amount: float) -> float:
        """计算手续费"""
        commission = amount * self.commission_rate
        return max(commission, self.min_commission)
    
    def simulate_order(
        self, 
        order: Order, 
        price_history: List[float],
        start_idx: int = 0
    ) -> List[Dict]:
        """模拟订单执行（全链路回测）
        
        Args:
            order: 订单
            price_history: 价格历史
            start_idx: 开始索引
            
        Returns:
            成交记录列表
        """
        fills = []
        
        for i in range(start_idx, len(price_history)):
            price = price_history[i]
            
            # 创建模拟tick
            tick = Tick(
                symbol=order.symbol,
                timestamp=datetime.now(),
                last=price,
                ask1=price * 1.001,
                bid1=price * 0.999,
                ask_vol1=10000,
                bid_vol1=10000,
                volume=10000,
                amount=price * 10000,
            )
            
            # 尝试撮合
            result = self.match_order(order, tick)
            if result:
                fills.append(result)
                
            # 订单完成或被拒绝，退出循环
            if order.status in [EventType.ORDER_FILLED.value, EventType.ORDER_REJECTED.value, EventType.ORDER_CANCELLED.value]:
                break
                
        return fills


# 全局单例
_engine: Optional[MatchingEngine] = None


def get_matching_engine() -> MatchingEngine:
    """获取撮合引擎单例"""
    global _engine
    if _engine is None:
        from stockquant.config import get_config
        config = get_config()
        _engine = MatchingEngine(
            price_limit_ratio=config.system.price_limit_ratio,
            slippage=config.system.slippage,
            commission_rate=config.system.commission_rate,
            min_commission=config.system.min_commission,
        )
    return _engine
