# -*- coding: utf-8 -*-
"""F018 邮件通知器"""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger("stockquant.execution.notifier.email")


class EmailNotifier:
    """
    SMTP 邮件通知器。

    用法:
        notifier = EmailNotifier(
            smtp_server="smtp.qq.com",
            smtp_port=465,
            username="your_email@qq.com",
            password="your_password",
            from_addr="your_email@qq.com",
            to_addrs=["recipient@example.com"],
        )
        notifier.send("回测完成", "年化收益 25%")
    """

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int = 465,
        username: str = "",
        password: str = "",
        from_addr: str = "",
        to_addrs: list[str] | None = None,
        use_ssl: bool = True,
    ):
        self._smtp_server = smtp_server
        self._smtp_port = smtp_port
        self._username = username
        self._password = password
        self._from_addr = from_addr or username
        self._to_addrs = to_addrs or []
        self._use_ssl = use_ssl

    def send(self, message: str, title: Optional[str] = None) -> bool:
        """
        发送邮件。
        """
        try:
            subject = title or "StockQuant 通知"
            body = f"<h3>{subject}</h3><br/><pre>{message}</pre>"

            msg = MIMEText(body, "html", "utf-8")
            msg["Subject"] = subject
            msg["From"] = self._from_addr
            msg["To"] = ", ".join(self._to_addrs)

            if self._use_ssl:
                server = smtplib.SMTP_SSL(self._smtp_server, self._smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(self._smtp_server, self._smtp_port, timeout=10)
                server.starttls()

            if self._username and self._password:
                server.login(self._username, self._password)

            server.sendmail(self._from_addr, self._to_addrs, msg.as_string())
            server.quit()

            logger.debug("Email notification sent successfully")
            return True
        except Exception as e:
            logger.error(f"Email send failed: {e}", exc_info=True)
            return False
