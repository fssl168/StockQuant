# -*- coding: utf-8 -*-
"""F018 PushPlus 通知器"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from stockquant.execution.notifier.base import Notifier

logger = logging.getLogger("stockquant.execution.notifier.pushplus")


class PushPlusNotifier(Notifier):
    """
    PushPlus 推送通知器。

    用法:
        notifier = PushPlusNotifier(token="your_token")
        notifier.send("回测完成: 年化收益 25%, 最大回撤 -15%", title="策略报告")
    """

    API_URL = "https://www.pushplus.plus/send"

    def __init__(
        self,
        token: str,
        topic: str = "",
        channel: str = "wechat",
        template: str = "html",
    ) -> None:
        """
        Parameters
        ----------
        token : str
            PushPlus token
        topic : str
            推送主题（群组编码）
        channel : str
            推送渠道：wechat / email / sms
        template : str
            模板：html / json / markdown / text
        """
        self._token = token
        self._topic = topic
        self._channel = channel
        self._template = template

    def send(self, message: str, title: Optional[str] = None) -> bool:
        """
        发送 PushPlus 推送。

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
            payload: dict = {
                "token": self._token,
                "content": message,
                "template": self._template,
            }
            if title:
                payload["title"] = title
            if self._topic:
                payload["topic"] = self._topic
            if self._channel:
                payload["channel"] = self._channel

            resp = requests.post(self.API_URL, json=payload, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 0:
                    logger.debug("PushPlus notification sent successfully")
                    return True
                logger.warning(f"PushPlus API error: {result}")
                return False
            logger.error(f"PushPlus HTTP error: {resp.status_code}")
            return False
        except Exception as e:
            logger.error(f"PushPlus send failed: {e}", exc_info=True)
            return False
