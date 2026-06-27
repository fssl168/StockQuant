# -*- coding: utf-8 -*-
"""事件总线 — 跨模块事件驱动架构

提供基于 Redis Pub/Sub 的事件分发，支持同进程异步事件和跨进程分布式事件。
"""

import asyncio
import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from stockquant.config import get_config
from stockquant.persistence.redis_client import get_redis_client

logger = logging.getLogger("stockquant.api")


class EventType(str, Enum):
    """事件类型枚举 — 统一订单/持仓/账户事件

    合并了原 OrderStatus 的 PENDING/SUBMITTED/QUEUED/PARTIAL/FILLED/CANCELLED/REJECTED
    为统一的 EventType 订单状态值。
    """
    # 订单状态（合并 ORDER_CREATED + PENDING/SUBMITTED）
    ORDER_PENDING = "ORDER_PENDING"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_PARTIAL_FILL = "ORDER_PARTIAL_FILL"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    # 持仓/账户
    POSITION_CLOSED = "POSITION_CLOSED"
    ACCOUNT_BALANCE_UPDATE = "ACCOUNT_BALANCE_UPDATE"
    # 原有事件
    RISK_ALERT = "RISK_ALERT"
    SIGNAL_GENERATED = "SIGNAL_GENERATED"
    PRICE_UPDATE = "PRICE_UPDATE"
    POSITION_UPDATE = "POSITION_UPDATE"


class EventBus:
    """事件总线单例
    
    支持两种事件分发模式：
    1. 同进程内使用 asyncio.Event 做快速分发
    2. 跨进程使用 Redis Pub/Sub 做分布式分发
    """
    
    _instance: Optional['EventBus'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._local_queue: asyncio.Queue = asyncio.Queue()
        self._redis = None
        self._pubsub = None
        self._running = False
        self._config = get_config()
        
        # 尝试初始化 Redis
        try:
            self._redis = get_redis_client()
            logger.info("EventBus: Redis 客户端已初始化")
        except Exception as e:
            logger.warning(f"EventBus: Redis 连接失败，将使用本地事件模式: {e}")
    
    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """订阅事件
        
        Args:
            event_type: 事件类型
            callback: 回调函数，签名为 (event_type: EventType, data: dict) -> None
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
            logger.debug(f"EventBus: 订阅事件 {event_type}, callback={callback.__name__}")
    
    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """取消订阅"""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(callback)
            logger.debug(f"EventBus: 取消订阅事件 {event_type}")
    
    async def publish(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """发布事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        event_data = {
            "type": event_type.value,
            "data": data,
        }
        
        # 本地同步分发
        await self._dispatch_local(event_type, event_data)
        
        # 跨进程分发（如果 Redis 可用）
        if self._redis:
            try:
                channel = f"stockquant:events:{event_type.value}"
                self._redis.publish(channel, str(event_data))
            except Exception as e:
                logger.warning(f"EventBus: Redis 发布失败: {e}")
    
    async def _dispatch_local(self, event_type: EventType, event_data: dict) -> None:
        """本地事件分发"""
        if event_type not in self._subscribers:
            return
        
        for callback in self._subscribers[event_type]:
            try:
                # 如果是异步回调
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, event_data.get("data", {}))
                else:
                    callback(event_type, event_data.get("data", {}))
            except Exception as e:
                logger.error(f"EventBus: 事件处理失败 {event_type}: {e}")
    
    async def start(self) -> None:
        """启动事件总线（启动 Redis 订阅监听）"""
        if self._running:
            return
        
        self._running = True
        
        if self._redis:
            try:
                self._pubsub = self._redis.pubsub()
                # 订阅所有事件频道
                for event_type in EventType:
                    channel = f"stockquant:events:{event_type.value}"
                    self._pubsub.subscribe(channel)
                    logger.info(f"EventBus: 订阅 Redis 频道 {channel}")
                
                # 启动监听协程
                asyncio.create_task(self._listen_redis())
            except Exception as e:
                logger.warning(f"EventBus: Redis 订阅监听启动失败: {e}")
        
        logger.info("EventBus: 事件总线已启动")
    
    async def stop(self) -> None:
        """停止事件总线"""
        self._running = False
        
        if self._pubsub:
            try:
                self._pubsub.unsubscribe()
                self._pubsub.close()
            except Exception as e:
                logger.warning(f"EventBus: Redis 取消订阅失败: {e}")
        
        logger.info("EventBus: 事件总线已停止")
    
    async def _listen_redis(self) -> None:
        """监听 Redis 消息"""
        if not self._pubsub:
            return
        
        try:
            for message in self._pubsub.listen():
                if not self._running:
                    break
                
                if message["type"] != "message":
                    continue
                
                # 解析事件并触发本地处理
                try:
                    # 消息格式: {"type": "ORDER_CREATED", "data": {...}}
                    channel = message["channel"]
                    event_type_str = channel.replace("stockquant:events:", "")
                    event_type = EventType(event_type_str)
                    
                    # 从 Redis 接收的事件数据
                    event_data = eval(message["data"]) if message["data"] else {}
                    
                    await self._dispatch_local(event_type, event_data)
                except Exception as e:
                    logger.error(f"EventBus: 处理 Redis 消息失败: {e}")
        except Exception as e:
            logger.error(f"EventBus: Redis 监听异常: {e}")
    
    def get_subscriber_count(self, event_type: EventType) -> int:
        """获取事件订阅者数量"""
        return len(self._subscribers.get(event_type, []))


# 全局单例
event_bus = EventBus()


# ============ 便捷函数 ============

async def publish_order_submitted(order_data: dict) -> None:
    """发布订单提交事件（替代原 publish_order_created）"""
    await event_bus.publish(EventType.ORDER_SUBMITTED, order_data)


async def publish_order_partially_filled(order_data: dict) -> None:
    """发布订单部分成交事件"""
    await event_bus.publish(EventType.ORDER_PARTIAL_FILL, order_data)


async def publish_order_filled(order_data: dict) -> None:
    """发布订单全部成交事件"""
    await event_bus.publish(EventType.ORDER_FILLED, order_data)


async def publish_order_cancelled(order_id: str, reason: str = "") -> None:
    """发布订单取消事件"""
    await event_bus.publish(EventType.ORDER_CANCELLED, {"order_id": order_id, "reason": reason})


async def publish_order_rejected(order_id: str, reason: str = "") -> None:
    """发布订单拒绝事件"""
    await event_bus.publish(EventType.ORDER_REJECTED, {"order_id": order_id, "reason": reason})


async def publish_position_closed(position_data: dict) -> None:
    """发布持仓平仓事件"""
    await event_bus.publish(EventType.POSITION_CLOSED, position_data)


async def publish_account_balance_update(balance_data: dict) -> None:
    """发布账户余额变动事件（替代原 publish_account_update）"""
    await event_bus.publish(EventType.ACCOUNT_BALANCE_UPDATE, balance_data)


async def publish_risk_alert(alert_data: dict) -> None:
    """发布风控告警事件"""
    await event_bus.publish(EventType.RISK_ALERT, alert_data)


async def publish_signal_generated(signal_data: dict) -> None:
    """发布信号生成事件"""
    await event_bus.publish(EventType.SIGNAL_GENERATED, signal_data)


async def publish_price_update(price_data: dict) -> None:
    """发布价格更新事件"""
    await event_bus.publish(EventType.PRICE_UPDATE, price_data)
