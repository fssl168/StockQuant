# -*- coding: utf-8 -*-
"""F018 消息推送模块 — 通知器抽象基类"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger("stockquant.execution.notifier")


class Notifier(ABC):
    """通知器抽象基类"""

    @abstractmethod
    def send(self, message: str, title: Optional[str] = None) -> bool:
        """
        发送消息。

        Parameters
        ----------
        message : str
            消息内容
        title : str or None
            消息标题（可选）

        Returns
        -------
        bool
            是否发送成功
        """
        ...

    def send_alert(self, message: str, level: str = "warning") -> bool:
        """发送告警消息"""
        full_msg = f"[{level.upper()}] {message}"
        return self.send(full_msg)

    def send_trade_notification(self, trade: Dict[str, Any]) -> bool:
        """
        发送交易通知。

        Parameters
        ----------
        trade : dict
            成交记录
        """
        symbol = trade.get("symbol", "?")
        side = trade.get("side", "?")
        price = trade.get("price", 0)
        qty = trade.get("quantity", 0)
        msg = f"{'买入' if side == 'BUY' else '卖出'} {symbol}: {qty}股 @ {price:.2f}"
        return self.send(msg, title=f"交易通知: {symbol}")

    def send_backtest_complete(self, strategy_name: str, metrics: Dict[str, Any]) -> bool:
        """发送回测完成通知"""
        lines = [f"回测完成: {strategy_name}"]
        for k, v in list(metrics.items())[:10]:
            if isinstance(v, float):
                lines.append(f"  {k}: {v:.4f}")
            else:
                lines.append(f"  {k}: {v}")
        return self.send("\n".join(lines), title="回测完成")

    def send_ai_signal(self, signal_data: Dict[str, Any]) -> bool:
        """发送 AI 交易信号（默认空实现，子类可覆盖）"""
        return False

    def send_daily_report(self, report: Dict[str, Any]) -> bool:
        """发送每日收盘总结（默认空实现，子类可覆盖）"""
        return False

    def send_risk_alert(self, alert_data: Dict[str, Any]) -> bool:
        """发送风控告警（默认空实现，子类可覆盖）"""
        return False
