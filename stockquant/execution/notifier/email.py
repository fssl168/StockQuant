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

    def send_ai_signal(self, signal_data: dict) -> bool:
        """发送 AI 交易信号"""
        symbol = signal_data.get("symbol", "?")
        side = signal_data.get("side", "?")
        confidence = signal_data.get("confidence", 0)
        reasoning = signal_data.get("reasoning", [])

        subject = f"AI 信号: {symbol} {'买入' if side == 'BUY' else '卖出'}"
        html = f"""
        <h3>AI 交易信号建议</h3>
        <table border="1" cellpadding="5">
        <tr><td><b>标的</b></td><td>{symbol}</td></tr>
        <tr><td><b>方向</b></td><td>{'买入' if side == 'BUY' else '卖出'}</td></tr>
        <tr><td><b>置信度</b></td><td>{confidence:.1%}</td></tr>
        """
        if signal_data.get("target_price"):
            html += f"<tr><td><b>目标价</b></td><td>{signal_data['target_price']:.2f}</td></tr>"
        if signal_data.get("target_quantity"):
            html += f"<tr><td><b>数量</b></td><td>{signal_data['target_quantity']}</td></tr>"
        if reasoning:
            html += "<tr><td><b>推理链</b></td><td><ol>"
            for r in reasoning:
                html += f"<li>{r}</li>"
            html += "</ol></td></tr>"
        html += "</table>"
        return self.send(html, title=subject)

    def send_daily_report(self, report: dict) -> bool:
        """发送每日收盘总结"""
        date = report.get("date", "")
        strategies = report.get("strategies", [])
        top_signals = report.get("top_signals", [])
        risk_status = report.get("risk_status", "正常")

        subject = f"StockQuant 日终报告 {date}"
        html = f"<h3>StockQuant 日终报告 — {date}</h3>"
        html += f"<p>风控状态: <b>{risk_status}</b></p>"
        if strategies:
            html += "<h4>策略表现</h4><table border='1' cellpadding='5'>"
            html += "<tr><th>策略</th><th>收益率</th><th>夏普</th><th>回撤</th></tr>"
            for s in strategies:
                html += f"<tr><td>{s.get('name','?')}</td><td>{s.get('return','?')}</td>"
                html += f"<td>{s.get('sharpe','?')}</td><td>{s.get('drawdown','?')}</td></tr>"
            html += "</table>"
        if top_signals:
            html += "<h4>今日 AI 信号</h4><ul>"
            for sig in top_signals:
                html += f"<li>{sig.get('symbol','?')} {sig.get('side','?')} conf={sig.get('confidence',0):.0%}</li>"
            html += "</ul>"
        return self.send(html, title=subject)
