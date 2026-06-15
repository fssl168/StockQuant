# -*- coding: utf-8 -*-
"""F018 Server 酱通知器"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from stockquant.execution.notifier.base import Notifier

logger = logging.getLogger("stockquant.execution.notifier.serverchan")


class ServerChanNotifier(Notifier):
    """
    Server 酱推送通知器。

    用法:
        notifier = ServerChanNotifier(sendkey="SCR_123456")
        notifier.send("回测完成: 年化收益 25%, 最大回撤 -15%", title="策略报告")
    """

    API_URL = "https://sctapi.ftqq.com/"

    def __init__(self, sendkey: str) -> None:
        """
        Parameters
        ----------
        sendkey : str
            Server 酱 sendkey
        """
        self._sendkey = sendkey

    def send(self, message: str, title: Optional[str] = None) -> bool:
        """
        发送 Server 酱推送。

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
            payload: dict = {"title": title or "StockQuant 通知", "desp": message}

            resp = requests.post(
                f"{self.API_URL}{self._sendkey}.send",
                data=payload,
                timeout=10,
            )
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 0 or result.get("code") == 10000:
                    logger.debug("ServerChan notification sent successfully")
                    return True
                logger.warning(f"ServerChan API error: {result}")
                return False
            logger.error(f"ServerChan HTTP error: {resp.status_code}")
            return False
        except Exception as e:
            logger.error(f"ServerChan send failed: {e}", exc_info=True)
            return False
