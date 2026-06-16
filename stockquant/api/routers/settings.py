# -*- coding: utf-8 -*-
"""F029 设置管理路由 — 配置读写/白名单"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

logger = logging.getLogger("stockquant.api.settings")

router = APIRouter()

# 默认配置
_DEFAULT_SETTINGS: Dict[str, Any] = {
    "trading.broker": "paper",
    "trading.admin_token": "",
    "trading.auto_confirm": False,
    "data_provider.source": "baostock",
    "data_provider.api_key": "",
    "data_provider.api_url": "",
    "backtest.default_cash": 1000000,
    "backtest.commission_type": "ashare",
    "backtest.slippage_type": "none",
    "risk.max_position_pct": 0.3,
    "risk.max_daily_loss_pct": 0.05,
    "risk.max_drawdown_pct": 0.15,
    "ai.model": "gpt-4o",
    "ai.temperature": 0.7,
    "ai.max_tokens": 4096,
    "notification.dingtalk_webhook": "",
    "notification.email_smtp": "",
    "notification.email_to": "",
    "system.log_level": "INFO",
    "system.data_dir": "~/.stockquant/data",
}

# 内存存储 (MVP)
_settings: Dict[str, Any] = dict(_DEFAULT_SETTINGS)
_admin_whitelist: list[str] = ["admin"]


@router.get("/settings", summary="获取全部配置")
async def get_settings():
    """获取所有配置项"""
    return {"settings": _settings, "count": len(_settings)}


@router.post("/settings/save", summary="保存配置")
async def save_settings(payload: dict):
    """批量保存配置"""
    updates = payload.get("settings", {})
    if not isinstance(updates, dict):
        raise HTTPException(status_code=400, detail="settings 必须是字典")

    _settings.update(updates)
    logger.info(f"配置已更新: {list(updates.keys())}")
    return {"success": True, "updated_keys": list(updates.keys())}


@router.delete("/settings/{key:path}", summary="恢复配置默认值")
async def reset_setting(key: str):
    """恢复单个配置项为默认值"""
    if key not in _DEFAULT_SETTINGS:
        raise HTTPException(status_code=404, detail=f"配置项 {key} 不存在")

    _settings[key] = _DEFAULT_SETTINGS[key]
    return {"success": True, "key": key, "value": _DEFAULT_SETTINGS[key]}


@router.get("/settings/whitelist", summary="获取管理员白名单")
async def get_whitelist():
    """获取管理员白名单"""
    return {"whitelist": _admin_whitelist}
