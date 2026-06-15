# -*- coding: utf-8 -*-
"""F018 飞书(Lark) 通知器"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from stockquant.execution.notifier.base import Notifier

logger = logging.getLogger("stockquant.execution.notifier.feishu")


class FeishuNotifier(Notifier):
    """
    飞书 Webhook 通知器。

    用法:
        notifier = FeishuNotifier(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/xxx")
        notifier.send("回测完成: 年化收益 25%, 最大回撤 -15%", title="策略报告")
    """

    def __init__(self, webhook_url: str) -> None:
        """
        Parameters
        ----------
        webhook_url : str
            飞书自定义机器人 Webhook URL
        """
        self._webhook_url = webhook_url

    def send(self, message: str, title: Optional[str] = None) -> bool:
        """
        发送飞书消息。

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
            display_title = title or "通知"
            payload = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": display_title,
                        },
                    },
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": message,
                        },
                    ],
                },
            }

            resp = requests.post(
                self._webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 0 or result.get("StatusCode") == 0:
                    logger.debug("Feishu notification sent successfully")
                    return True
                logger.warning(f"Feishu API error: {result}")
                return False
            logger.error(f"Feishu HTTP error: {resp.status_code}")
            return False
        except Exception as e:
            logger.error(f"Feishu send failed: {e}", exc_info=True)
            return False

    def send_trade_notification(self, trade: dict) -> bool:
        """发送交易通知"""
        symbol = trade.get("symbol", "?")
        side = trade.get("side", "?")
        price = trade.get("price", 0)
        qty = trade.get("quantity", 0)

        title = f"交易通知: {symbol}"
        content = (
            f"**{'买入' if side == 'BUY' else '卖出'} {symbol}**\n\n"
            f"> 数量: {qty} 股\n"
            f"> 价格: {price:.2f}"
        )
        return self.send(content, title=title)

    def send_risk_alert(self, alert_data: dict) -> bool:
        """发送风控告警"""
        symbol = alert_data.get("symbol", "?")
        rule = alert_data.get("rule", "?")
        severity = alert_data.get("severity", "warning")
        action = alert_data.get("action", "")

        emoji = "red_circle" if severity == "critical" else "large_orange_circle"
        title = f"风控告警: {symbol}"
        content = (
            f"**{rule}**\n\n"
            f"> 严重程度: {severity}\n"
        )
        if action:
            content += f"> 建议操作: {action}\n"
        return self.send(content, title=title)
