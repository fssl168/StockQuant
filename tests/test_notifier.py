# -*- coding: utf-8 -*-
"""F018 消息推送测试"""

from unittest.mock import patch, MagicMock


class TestDingTalkNotifier:
    """钉钉通知器测试"""

    def test_send_success(self):
        """发送成功"""
        with patch("stockquant.execution.notifier.dingtalk.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"errcode": 0}
            mock_post.return_value = mock_resp

            from stockquant.execution.notifier.dingtalk import DingTalkNotifier

            notifier = DingTalkNotifier(
                webhook="https://oapi.dingtalk.com/robot/send?access_token=xxx"
            )
            result = notifier.send("测试消息", title="测试标题")
            assert result is True
            mock_post.assert_called_once()

    def test_send_failure(self):
        """发送失败"""
        with patch("stockquant.execution.notifier.dingtalk.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_post.return_value = mock_resp

            from stockquant.execution.notifier.dingtalk import DingTalkNotifier

            notifier = DingTalkNotifier(
                webhook="https://oapi.dingtalk.com/robot/send?access_token=xxx"
            )
            result = notifier.send("测试消息")
            assert result is False

    def test_trade_notification(self):
        """交易通知"""
        with patch("stockquant.execution.notifier.dingtalk.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"errcode": 0}
            mock_post.return_value = mock_resp

            from stockquant.execution.notifier.dingtalk import DingTalkNotifier

            notifier = DingTalkNotifier(
                webhook="https://oapi.dingtalk.com/robot/send?access_token=xxx"
            )
            result = notifier.send_trade_notification({
                "symbol": "sh600519",
                "side": "BUY",
                "price": 1800.0,
                "quantity": 100,
            })
            assert result is True


class TestEmailNotifier:
    """邮件通知器测试"""

    def test_send_success(self):
        """发送邮件成功"""
        mock_server = MagicMock()

        with patch("stockquant.execution.notifier.email.smtplib.SMTP_SSL", return_value=mock_server):
            from stockquant.execution.notifier.email import EmailNotifier

            notifier = EmailNotifier(
                smtp_server="smtp.qq.com",
                username="test@qq.com",
                password="test",
                to_addrs=["recipient@example.com"],
            )
            result = notifier.send("测试内容", title="测试邮件")
            assert result is True
            mock_server.sendmail.assert_called_once()

    def test_send_smtp_exception(self):
        """SMTP 异常"""
        with patch(
            "stockquant.execution.notifier.email.smtplib.SMTP_SSL",
            side_effect=Exception("Connection refused"),
        ):
            from stockquant.execution.notifier.email import EmailNotifier

            notifier = EmailNotifier(
                smtp_server="smtp.qq.com",
                username="test@qq.com",
                password="test",
                to_addrs=["recipient@example.com"],
            )
            result = notifier.send("测试内容")
            assert result is False


class TestWeChatNotifier:
    """企业微信通知器测试"""

    def test_send_success(self):
        """发送成功"""
        with patch("stockquant.execution.notifier.wechat.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}
            mock_post.return_value = mock_resp

            from stockquant.execution.notifier.wechat import WeChatNotifier

            notifier = WeChatNotifier(
                webhook="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
            )
            result = notifier.send("测试消息")
            assert result is True

    def test_send_with_secret(self):
        """带签名的发送"""
        with patch("stockquant.execution.notifier.wechat.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}
            mock_post.return_value = mock_resp

            from stockquant.execution.notifier.wechat import WeChatNotifier

            notifier = WeChatNotifier(
                webhook="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
                secret="my_secret",
            )
            result = notifier.send("测试消息")
            assert result is True
            call_args = mock_post.call_args
            url = call_args[0][0]
            assert "timestamp=" in url
            assert "sign=" in url


class TestTelegramNotifier:
    """Telegram 通知器测试"""

    def test_send_success(self):
        """发送成功"""
        with patch("stockquant.execution.notifier.telegram.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"ok": True}
            mock_post.return_value = mock_resp

            from stockquant.execution.notifier.telegram import TelegramNotifier

            notifier = TelegramNotifier(
                bot_token="123456:ABC-DEF",
                chat_id="-1001234567890",
            )
            result = notifier.send("测试消息", title="测试")
            assert result is True

    def test_send_failure(self):
        """发送失败"""
        with patch("stockquant.execution.notifier.telegram.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 403
            mock_post.return_value = mock_resp

            from stockquant.execution.notifier.telegram import TelegramNotifier

            notifier = TelegramNotifier(
                bot_token="123456:ABC-DEF",
                chat_id="-1001234567890",
            )
            result = notifier.send("测试消息")
            assert result is False
