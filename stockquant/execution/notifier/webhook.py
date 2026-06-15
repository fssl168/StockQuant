# -*- coding: utf-8 -*-
"""F018 通用 Webhook 通知器"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

from stockquant.execution.notifier.base import Notifier

logger = logging.getLogger("stockquant.execution.notifier.webhook")


class WebhookNotifier(Notifier):
    """
    通用 HTTP Webhook 通知器。

    用法:
        notifier = WebhookNotifier(
            url="https://hooks.example.com/notify",
            payload_template={"text": "{title}: {message}"},
        )
        notifier.send("回测完成", title="策略报告")
    """

    def __init__(
        self,
        url: str,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        payload_template: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Parameters
        ----------
        url : str
            Webhook URL
        method : str
            HTTP method (GET / POST / PUT)
        headers : dict | None
            自定义请求头
        payload_template : dict | None
            消息模板，支持 {title} 和 {message} 占位符
        """
        self._url = url
        self._method = method.upper()
        self._headers = headers or {}
        self._payload_template = payload_template or {
            "title": "{title}",
            "message": "{message}",
        }

    def send(self, message: str, title: Optional[str] = None) -> bool:
        """
        发送 webhook 请求。

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
            resolved_title = title or "StockQuant 通知"
            payload = {
                k: (v.format(title=resolved_title, message=message) if isinstance(v, str) else v)
                for k, v in self._payload_template.items()
            }

            method = self._method
            if method == "GET":
                query = "&".join(f"{k}={v}" for k, v in payload.items())
                url = f"{self._url}?{query}" if query else self._url
                resp = requests.get(url, headers=self._headers, timeout=10)
            elif method == "PUT":
                resp = requests.put(
                    self._url, json=payload, headers=self._headers, timeout=10
                )
            else:
                resp = requests.post(
                    self._url, json=payload, headers=self._headers, timeout=10
                )

            if 200 <= resp.status_code < 300:
                logger.debug("Webhook notification sent successfully")
                return True
            logger.warning(f"Webhook HTTP error ({resp.status_code}): {resp.text}")
            return False
        except Exception as e:
            logger.error(f"Webhook send failed: {e}", exc_info=True)
            return False
