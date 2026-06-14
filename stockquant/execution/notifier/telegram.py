# -*- coding: utf-8 -*-
"""F018 Telegram 通知器"""

from __future__ import annotations

import logging
from typing import Optional
import requests

logger = logging.getLogger("stockquant.execution.notifier.telegram")


class TelegramNotifier:
    """
    Telegram Bot 通知器。

    用法:
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF...",
            chat_id="-1001234567890",
        )
        notifier.send("回测完成", "年化收益 25%")
    """

    def __init__(self, bot_token: str, chat_id: str):
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._base_url = f"https://api.telegram.org/bot{bot_token}"

    def send(self, message: str, title: Optional[str] = None) -> bool:
        """
        发送 Telegram 消息。
        """
        try:
            text = f"{title or ''}\n{message}" if title else message
            url = f"{self._base_url}/sendMessage"
            payload = {
                "chat_id": self._chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }

            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    logger.debug("Telegram notification sent successfully")
                    return True
                logger.warning(f"Telegram API error: {result}")
                return False
            logger.error(f"Telegram HTTP error: {resp.status_code}")
            return False
        except Exception as e:
            logger.error(f"Telegram send failed: {e}", exc_info=True)
            return False

    def send_ai_signal(self, signal_data: dict) -> bool:
        """发送 AI 交易信号"""
        symbol = signal_data.get("symbol", "?")
        side = signal_data.get("side", "?")
        confidence = signal_data.get("confidence", 0)
        reasoning = signal_data.get("reasoning", [])

        text = f"*AI 信号: {symbol}*\n"
        text += f"方向: {'买入' if side == 'BUY' else '卖出'}\n"
        text += f"置信度: {confidence:.1%}\n"
        if signal_data.get("target_price"):
            text += f"目标价: {signal_data['target_price']:.2f}\n"
        if reasoning:
            text += "*推理链:*\n"
            for i, r in enumerate(reasoning, 1):
                text += f"{i}. {r}\n"
        return self.send(text)

    def send_risk_alert(self, alert_data: dict) -> bool:
        """发送风控告警"""
        symbol = alert_data.get("symbol", "?")
        rule = alert_data.get("rule", "?")
        severity = alert_data.get("severity", "warning")
        action = alert_data.get("action", "")

        emoji = "🔴" if severity == "critical" else "🟡"
        text = f"{emoji} *风控告警: {symbol}*\n"
        text += f"规则: {rule}\n"
        text += f"严重程度: {severity}\n"
        if action:
            text += f"建议: {action}\n"
        return self.send(text)
