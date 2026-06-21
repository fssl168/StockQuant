# -*- coding: utf-8 -*-
"""Redis 客户端封装 — 用于缓存和持久化自选股等数据"""

from __future__ import annotations

import logging
import os
import redis
from typing import List, Optional

logger = logging.getLogger("stockquant.persistence")

_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """获取或创建 Redis 客户端单例"""
    global _client
    if _client is None:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _client = redis.from_url(redis_url, decode_responses=True)
    return _client


def get_watchlist() -> List[str]:
    """从 Redis 获取自选股列表"""
    client = get_redis_client()
    try:
        return client.lrange("watchlist", 0, -1) or []
    except Exception:
        return []


def add_to_watchlist(symbols: List[str]) -> None:
    """添加股票到自选股"""
    client = get_redis_client()
    try:
        for symbol in symbols:
            if symbol not in get_watchlist():
                client.rpush("watchlist", symbol)
    except Exception:
        logger.debug("Redis: failed to add to watchlist: %s", symbols)


def remove_from_watchlist(symbols: List[str]) -> None:
    """从自选股移除股票"""
    client = get_redis_client()
    try:
        for symbol in symbols:
            client.lrem("watchlist", 0, symbol)
    except Exception:
        logger.debug("Redis: failed to remove from watchlist: %s", symbols)
