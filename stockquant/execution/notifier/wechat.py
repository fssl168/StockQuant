# -*- coding: utf-8 -*-
"""F018 企业微信通知器"""

from __future__ import annotations

import hashlib
import hmac
import base64
import time
import logging
from typing import Optional
import requests

logger = logging.getLogger("stockquant.execution.notifier.wechat")


class WeChatNotifier:
    """
    企业微信群机器人通知器。

    用法:
        notifier = WeChatNotifier(webhook="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx")
        notifier.send("风控告警: 回撤达到 15%")
    """

    def __init__(
        self,
        webhook: str,
        secret: Optional[str] = None,
    ):
        self._webhook = webhook
        self._secret = secret

    def send(self, message: str, title: Optional[str] = None) -> bool:
        """
        发送企业微信消息。
        """
        try:
            # 如果配置了 secret，需要生成签名
            url = self._webhook
            if self._secret:
                timestamp = str(int(time.time()))
                string_to_sign = f"{timestamp}\n{self._secret}"
                hmac_code = hmac.new(
                    self._secret.encode("utf-8"),
                    string_to_sign.encode("utf-8"),
                    digestmod=hashlib.sha256,
                ).digest()
                sign = base64.urlsafe_b64encode(hmac_code).decode("utf-8")
                url = f"{url}&timestamp={timestamp}&sign={sign}"

            payload = {
                "msgtype": "text",
                "text": {
                    "content": f"{title or ''}\n{message}" if title else message,
                },
            }

            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("errcode") == 0:
                    return True
                logger.warning(f"WeChat API error: {result}")
                return False
            logger.error(f"WeChat HTTP error: {resp.status_code}")
            return False
        except Exception as e:
            logger.error(f"WeChat send failed: {e}", exc_info=True)
            return False
