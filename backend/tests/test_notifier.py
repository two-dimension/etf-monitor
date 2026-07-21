import smtplib
from datetime import datetime
from email import policy
from email.parser import BytesParser

from app.config import Settings
from app.models import AlertLog
from app.notifier import SMTPAlertNotifier


def alert_log() -> AlertLog:
    return AlertLog(
        id=1,
        symbol="159915.SZ",
        name="创业板ETF易方达",
        alert_type="volume_spike",
        candle_time=datetime.fromisoformat("2026-07-20T13:30:00"),
        volume=3600,
        prev_volume=1000,
        ratio=3.6,
        threshold=2.0,
        severity="warning",
        message="159915.SZ 创业板ETF易方达 15分钟放量异动：成交量为前一根的 3.60 倍",
        created_at=datetime.fromisoformat("2026-07-20T13:31:00"),
    )


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.logged_in = None
        self.sent_messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def login(self, username, password):
        self.logged_in = (username, password)

    def send_message(self, message):
        self.sent_messages.append(message)


def test_smtp_notifier_sends_alert_email_to_configured_recipients(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    settings = Settings(
        email_enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_username="monitor@example.com",
        smtp_password="secret",
        smtp_from="monitor@example.com",
        smtp_to="desk@example.com,pm@example.com",
        smtp_use_ssl=True,
        smtp_timeout_seconds=8,
    )
    notifier = SMTPAlertNotifier(settings)

    notifier.send_alert(alert_log())

    assert len(FakeSMTP.instances) == 1
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.example.com"
    assert smtp.port == 465
    assert smtp.timeout == 8
    assert smtp.logged_in == ("monitor@example.com", "secret")
    assert len(smtp.sent_messages) == 1
    message = smtp.sent_messages[0]
    assert message["From"] == "monitor@example.com"
    assert message["To"] == "desk@example.com, pm@example.com"
    assert "159915.SZ" in message["Subject"]
    assert "warning" in message["Subject"]
    assert "ETF Monitor 告警通知" in message.get_content()
    assert "标的: 创业板ETF易方达 (159915.SZ)" in message.get_content()
    assert "告警类型: 放量异动" in message.get_content()
    assert "成交量: 3600" in message.get_content()
    assert message.get_content_charset() == "utf-8"
    assert message["Content-Transfer-Encoding"] == "base64"

    raw_message = message.as_bytes()
    parsed_message = BytesParser(policy=policy.default).parsebytes(raw_message)
    assert "创业板ETF易方达" in str(parsed_message["Subject"])
    assert "创业板ETF易方达" in parsed_message.get_content()


def test_smtp_notifier_skips_when_email_is_disabled(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("SMTP should not be opened when email is disabled")

    monkeypatch.setattr(smtplib, "SMTP_SSL", fail_if_called)
    settings = Settings(
        email_enabled=False,
        smtp_host="smtp.example.com",
        smtp_from="monitor@example.com",
        smtp_to="desk@example.com",
    )

    SMTPAlertNotifier(settings).send_alert(alert_log())
