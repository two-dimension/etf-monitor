from __future__ import annotations

import smtplib
from email import policy
from email.message import EmailMessage
from typing import Protocol

from app.config import Settings
from app.models import AlertLog


class AlertNotifier(Protocol):
    def send_alert(self, alert: AlertLog) -> None:
        ...


class NoopAlertNotifier:
    def send_alert(self, alert: AlertLog) -> None:
        return None


class SMTPAlertNotifier:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send_alert(self, alert: AlertLog) -> None:
        if not self._should_send():
            return

        message = self._message(alert)
        if self.settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.settings.smtp_timeout_seconds,
            ) as client:
                self._send_message(client, message)
            return

        with smtplib.SMTP(
            self.settings.smtp_host,
            self.settings.smtp_port,
            timeout=self.settings.smtp_timeout_seconds,
        ) as client:
            if self.settings.smtp_starttls:
                client.starttls()
            self._send_message(client, message)

    def _should_send(self) -> bool:
        return (
            self.settings.email_enabled
            and bool(self.settings.smtp_host)
            and bool(self.settings.smtp_from)
            and bool(_recipients(self.settings.smtp_to))
        )

    def _send_message(self, client, message: EmailMessage) -> None:
        if self.settings.smtp_username and self.settings.smtp_password:
            client.login(self.settings.smtp_username, self.settings.smtp_password)
        client.send_message(message)

    def _message(self, alert: AlertLog) -> EmailMessage:
        recipients = _recipients(self.settings.smtp_to)
        message = EmailMessage(policy=policy.SMTP)
        message["Subject"] = _subject(alert)
        message["From"] = self.settings.smtp_from
        message["To"] = ", ".join(recipients)
        message.set_content(_body(alert), charset="utf-8", cte="base64")
        return message


def _recipients(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _subject(alert: AlertLog) -> str:
    return (
        f"ETF Monitor 告警 | {alert.severity} | {alert.name} ({alert.symbol}) | "
        f"{_alert_type_label(alert.alert_type)} | {alert.candle_time:%Y-%m-%d %H:%M}"
    )


def _body(alert: AlertLog) -> str:
    return "\n".join(
        [
            "ETF Monitor 告警通知",
            "",
            f"标的: {alert.name} ({alert.symbol})",
            f"告警类型: {_alert_type_label(alert.alert_type)}异动",
            f"告警级别: {alert.severity}",
            f"K线时间: {alert.candle_time:%Y-%m-%d %H:%M:%S}",
            f"成交量: {alert.volume}",
            f"前一根成交量: {alert.prev_volume}",
            f"比例: {alert.ratio:.2f}",
            f"阈值: {alert.threshold}",
            "",
            f"说明: {alert.message}",
            f"记录时间: {alert.created_at:%Y-%m-%d %H:%M:%S}",
        ]
    )


def _alert_type_label(alert_type: str) -> str:
    if alert_type == "volume_shrink":
        return "缩量"
    return "放量"
