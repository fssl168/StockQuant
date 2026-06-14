# -*- coding: utf-8 -*-
"""F018 钉钉通知器"""

from __future__ import annotations

import logging
from typing import Optional

from stockquant.execution.notifier.base import Notifier

import requests

logger = logging.getLogger("stockquant.execution.notifier.dingtalk")


class DingTalkNotifier(Notifier):
    """
    钉钉 Webhook 通知器。

    用法:
        notifier = DingTalkNotifier(webhook="https://oapi.dingtalk.com/robot/send?access_token=xxx")
        notifier.send("回测完成: 年化收益 25%, 最大回撤 -15%")
    """

    def __init__(self, webhook: str, secret: Optional[str] = None):
        self._webhook = webhook
        self._secret = secret

    def send(self, message: str, title: Optional[str] = None) -> bool:
        """
        发送钉钉消息。

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
            payload = {
                "msgtype": "text",
                "text": {"content": message},
            }
            if title:
                payload = {
                    "msgtype": "markdown",
                    "markdown": {"title": title, "text": f"## {title}\n\n{message}\n"},
                }

            resp = requests.post(self._webhook, json=payload, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("errcode") == 0:
                    logger.debug("DingTalk notification sent successfully")
                    return True
                logger.warning(f"DingTalk API error: {result}")
                return False
            logger.error(f"DingTalk HTTP error: {resp.status_code}")
            return False
        except Exception as e:
            logger.error(f"DingTalk send failed: {e}", exc_info=True)
            return False

    def send_ai_signal(self, signal_data: dict) -> bool:
        """发送 AI 交易信号推送"""
        symbol = signal_data.get("symbol", "?")
        side = signal_data.get("side", "?")
        confidence = signal_data.get("confidence", 0)
        reasoning = signal_data.get("reasoning", [])

        title = f"AI 信号: {symbol}"
        content = f"## {title}\n\n"
        content += f"- **方向**: {'买入' if side == 'BUY' else '卖出'}\n"
        content += f"- **置信度**: {confidence:.1%}\n"
        if signal_data.get("target_price"):
            content += f"- **目标价**: {signal_data['target_price']:.2f}\n"
        if signal_data.get("target_quantity"):
            content += f"- **数量**: {signal_data['target_quantity']}\n"
        if reasoning:
            content += f"\n**推理链**:\n"
            for i, r in enumerate(reasoning, 1):
                content += f"{i}. {r}\n"
        return self.send(content, title=title)

    def send_risk_alert(self, alert_data: dict) -> bool:
        """发送风控告警推送"""
        symbol = alert_data.get("symbol", "?")
        rule = alert_data.get("rule", "?")
        severity = alert_data.get("severity", "warning")
        action = alert_data.get("action", "")

        emoji = "🔴" if severity == "critical" else "🟡" if severity == "warning" else "⚪"
        title = f"{emoji} 风控告警: {symbol}"
        content = f"## {title}\n\n"
        content += f"- **触发规则**: {rule}\n"
        content += f"- **严重程度**: {severity}\n"
        if action:
            content += f"- **建议操作**: {action}\n"
        return self.send(content, title=title)
