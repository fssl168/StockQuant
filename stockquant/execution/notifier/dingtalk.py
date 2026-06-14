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
