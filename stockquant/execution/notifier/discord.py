# -*- coding: utf-8 -*-
"""F018 Discord 通知器"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from stockquant.execution.notifier.base import Notifier

logger = logging.getLogger("stockquant.execution.notifier.discord")


class DiscordNotifier(Notifier):
    """
    Discord Webhook 通知器。

    用法:
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/xxx/yyy")
        notifier.send("回测完成: 年化收益 25%, 最大回撤 -15%", title="策略报告")
    """

    _DISCORD_BLUE = 5814783

    def __init__(self, webhook_url: str) -> None:
        """
        Parameters
        ----------
        webhook_url : str
            Discord Webhook URL
        """
        self._webhook_url = webhook_url

    def send(self, message: str, title: Optional[str] = None) -> bool:
        """
        发送消息到 Discord。

        Parameters
        ----------
        message : str
            消息内容
        title : str or None
            消息标题

        Returns
        -------
        bool
            是否发送成功
        """
        try:
            if title:
                embed: dict = {
                    "title": title,
                    "description": message,
                    "color": self._DISCORD_BLUE,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                payload = {"embeds": [embed]}
            else:
                payload = {"content": message}

            resp = requests.post(
                self._webhook_url, json=payload, headers={
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if resp.status_code == 204:
                logger.debug("Discord notification sent successfully")
                return True
            logger.warning(f"Discord API error ({resp.status_code}): {resp.text}")
            return False
        except Exception as e:
            logger.error(f"Discord send failed: {e}", exc_info=True)
            return False

    def send_trade_notification(self, trade: dict) -> bool:
        """发送交易通知（Discord embed 格式）"""
        symbol = trade.get("symbol", "?")
        side = trade.get("side", "?")
        price = trade.get("price", 0)
        qty = trade.get("quantity", 0)

        emoji = "✅" if side == "BUY" else "❌"
        title = f"{emoji} 交易通知: {symbol}"
        color = self._DISCORD_BLUE if side == "BUY" else 12597383

        embed = {
            "title": title,
            "description": f"{'买入' if side == 'BUY' else '卖出'} {symbol}: {qty} 股 @ {price:.2f}",
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fields": [
                {"name": "方向", "value": "买入" if side == "BUY" else "卖出", "inline": True},
                {"name": "价格", "value": f"{price:.2f}", "inline": True},
                {"name": "数量", "value": str(qty), "inline": True},
            ],
        }
        try:
            resp = requests.post(
                self._webhook_url,
                json={"embeds": [embed]},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            return resp.status_code == 204
        except Exception as e:
            logger.error(f"Discord trade notification failed: {e}", exc_info=True)
            return False
