# -*- coding: utf-8 -*-
"""F029 通知推送路由 — 内存 + SQLite 持久化"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from stockquant.api.deps import get_current_user, get_required_user
from stockquant.api.websocket import ws_manager
from stockquant.api.routers.settings import _settings
from stockquant.persistence.models import Notification, init_db, get_engine

logger = logging.getLogger("stockquant.api.notification")

router = APIRouter()

# ── Session 工厂（懒初始化） ──

_SessionLocal: sessionmaker | None = None


def _get_session_local() -> sessionmaker:
    """懒初始化 sessionmaker，避免模块导入时 engine 尚未就绪"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal


# ── 内存存储 ──

_notifications: list[dict] = []


def set_storage(storage: dict):
    """存储引用注入（由 main.py 调用，保持与其他路由一致）"""
    global _notifications
    _notifications = storage.get("notifications", _notifications)


# ── 辅助函数 ──

def _get_webhook_urls() -> dict:
    """从 _settings 获取 Webhook 配置"""
    return {
        "wechat_webhook": _settings.get("notification.wechat_webhook", ""),
        "dingtalk_webhook": _settings.get("notification.dingtalk_webhook", ""),
    }


def _get_smtp_config() -> dict:
    """从 _settings 获取 SMTP 配置"""
    return {
        "smtp_host": _settings.get("notification.email_smtp", ""),
        "email_to": _settings.get("notification.email_to", ""),
    }


def _persist_notification(data: dict) -> None:
    """将通知持久化到 SQLite"""
    try:
        with _get_session_local()() as session:
            session.add(Notification(
                id=data["id"],
                notification_type=data["type"],
                title=data["title"],
                message=data["message"],
                is_read=1 if data.get("read", False) else 0,
                created_at=datetime.fromisoformat(data["time"]) if data.get("time") else datetime.now(),
            ))
            session.commit()
    except Exception as exc:
        logger.warning("通知持久化失败: %s", exc)


def _load_notifications_from_db(limit: int = 500) -> List[Dict[str, Any]]:
    """从 SQLite 加载通知"""
    try:
        with _get_session_local()() as session:
            stmt = (
                select(Notification)
                .order_by(Notification.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "id": r.id,
                    "type": r.notification_type,
                    "title": r.title,
                    "message": r.message,
                    "time": r.created_at.isoformat() if r.created_at else "",
                    "read": bool(r.is_read),
                }
                for r in rows
            ]
    except Exception:
        return []


def add_notification(data: dict) -> dict:
    """添加一条通知，自动补全 id / time，并推送 WebSocket + 持久化。"""
    notification = {
        "id": data.get("id") or str(uuid.uuid4()),
        "type": data.get("type", "info"),
        "title": data.get("title", ""),
        "message": data.get("message", ""),
        "time": data.get("time") or datetime.now().isoformat(),
        "read": data.get("read", False),
    }
    _notifications.append(notification)

    # 持久化到 SQLite
    _persist_notification(notification)

    # 通过 WebSocket 推送
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(ws_manager.push("notification", notification, "notification"))
    except RuntimeError:
        try:
            asyncio.run(ws_manager.push("notification", notification, "notification"))
        except Exception as exc:
            logger.warning("WebSocket 推送通知失败: %s", exc)

    # 通过 MessageRouter 发送到配置的通知渠道
    try:
        from stockquant.execution.notifier.router import MessageRouter, Message, Priority
        from stockquant.execution.notifier import (
            DingTalkNotifier, WeChatNotifier, TelegramNotifier, EmailNotifier,
            DiscordNotifier, FeishuNotifier, PushPlusNotifier, ServerChanNotifier,
            WebhookNotifier,
        )

        router = MessageRouter()

        # 根据配置注册可用的通知器
        dingtalk_url = _settings.get("notification.dingtalk_webhook", "")
        if dingtalk_url:
            router.register_notifier("dingtalk", DingTalkNotifier(webhook=dingtalk_url))

        wechat_url = _settings.get("notification.wechat_webhook", "")
        if wechat_url:
            router.register_notifier("wechat", WeChatNotifier(webhook=wechat_url))

        tg_token = _settings.get("notification.telegram_bot_token", "")
        tg_chat = _settings.get("notification.telegram_chat_id", "")
        if tg_token and tg_chat:
            router.register_notifier("telegram", TelegramNotifier(bot_token=tg_token, chat_id=tg_chat))

        feishu_url = _settings.get("notification.feishu_webhook", "")
        if feishu_url:
            router.register_notifier("feishu", FeishuNotifier(webhook_url=feishu_url))

        discord_url = _settings.get("notification.discord_webhook", "")
        if discord_url:
            router.register_notifier("discord", DiscordNotifier(webhook_url=discord_url))

        pushplus_token = _settings.get("notification.pushplus_token", "")
        if pushplus_token:
            router.register_notifier("pushplus", PushPlusNotifier(token=pushplus_token))

        serverchan_key = _settings.get("notification.serverchan_key", "")
        if serverchan_key:
            router.register_notifier("serverchan", ServerChanNotifier(sendkey=serverchan_key))

        custom_url = _settings.get("notification.custom_webhook_url", "")
        if custom_url:
            router.register_notifier("webhook", WebhookNotifier(url=custom_url))

        email_smtp = _settings.get("notification.email_smtp", "")
        email_enabled = _settings.get("notification.email_enabled", False)
        if email_enabled and email_smtp:
            router.register_notifier("email", EmailNotifier(
                smtp_server=email_smtp,
                smtp_port=int(_settings.get("notification.email_smtp_port", "465")),
                username=_settings.get("notification.email_user", ""),
                password=_settings.get("notification.email_password", ""),
                from_addr=_settings.get("notification.email_from", ""),
                to_addrs=_settings.get("notification.email_to", "").split(",") if _settings.get("notification.email_to") else [],
            ))

        # 注册默认路由规则：所有消息发送到所有已注册渠道
        if router._notifiers:
            router.register_rule(
                "all_channels",
                lambda msg: True,
                list(router._notifiers.keys()),
            )
            priority = Priority.HIGH if notification.get("type") == "alert" else Priority.NORMAL
            msg = Message(
                title=notification["title"],
                content=notification["message"],
                priority=priority,
            )
            results = router.send(msg)
            logger.info("MessageRouter 发送结果: %s", results)
    except ImportError:
        pass  # notifier 模块不可用
    except Exception as exc:
        logger.warning("MessageRouter 发送失败: %s", exc)

    logger.info("新通知: [%s] %s", notification["type"], notification["title"])
    return notification


# ── API 端点 ──


@router.get("/notifications", summary="通知列表")
async def get_notifications(
    type: str | None = Query(None, description="按类型过滤: signal / alert / info"),
    _user=Depends(get_current_user),
):
    """获取通知列表，支持 ?type= 过滤，最新优先。"""
    # 从 SQLite 读取
    result = _load_notifications_from_db()
    if not result:
        # 降级到内存
        result = list(reversed(_notifications))
    else:
        # 合并内存中的新通知
        existing_ids = {n["id"] for n in result}
        for n in reversed(_notifications):
            if n["id"] not in existing_ids:
                result.insert(0, n)

    if type:
        result = [n for n in result if n.get("type") == type]
    return result


@router.put("/notifications/{notification_id}/read", summary="标记已读")
async def mark_as_read(notification_id: str, _user=Depends(get_required_user)):
    """标记通知为已读。"""
    for n in _notifications:
        if n["id"] == notification_id:
            n["read"] = True
            # 同步到 DB
            try:
                with _get_session_local()() as session:
                    db_item = session.get(Notification, notification_id)
                    if db_item:
                        db_item.is_read = 1
                        session.commit()
            except Exception:
                pass
            return n
    raise HTTPException(status_code=404, detail=f"通知 {notification_id} 不存在")


@router.delete("/notifications/{notification_id}", summary="删除通知")
async def delete_notification(notification_id: str, _user=Depends(get_required_user)):
    """删除指定通知。"""
    for i, n in enumerate(_notifications):
        if n["id"] == notification_id:
            _notifications.pop(i)
            # 同步从 DB 删除
            try:
                with _get_session_local()() as session:
                    db_item = session.get(Notification, notification_id)
                    if db_item:
                        session.delete(db_item)
                        session.commit()
            except Exception:
                pass
            return {"success": True, "id": notification_id}
    raise HTTPException(status_code=404, detail=f"通知 {notification_id} 不存在")
