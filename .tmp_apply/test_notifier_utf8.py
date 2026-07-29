import smtplib
from pathlib import Path
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser

from app.config import Settings
from app.models import AlertLog, Candle
from app.notifier import SMTPAlertNotifier
from app.store import AlertStore


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


def first_candle_alert_log() -> AlertLog:
    return alert_log().model_copy(
        update={
            "candle_time": datetime.fromisoformat("2026-07-21T09:45:00"),
            "created_at": datetime.fromisoformat("2026-07-21T09:46:00"),
            "message": "159915.SZ 创业板ETF易方达 15分钟放量异动：成交量同比放大 3.60 倍",
        }
    )


def monday_first_candle_alert_log() -> AlertLog:
    return alert_log().model_copy(
        update={
            "id": 1528,
            "symbol": "510310.SH",
            "name": "沪深300ETF易方达",
            "candle_time": datetime.fromisoformat("2026-07-27T09:45:00"),
            "volume": 40667694,
            "prev_volume": 20150900,
            "ratio": 2.02,
            "created_at": datetime(2026, 7, 27, 1, 45, 30, tzinfo=UTC),
            "message": "510310.SH 15分钟成交量同比放大 2.02 倍，当前量 40667694，昨天09:45 20150900",
        }
    )


def normal_candle() -> Candle:
    return Candle(
        symbol="159915.SZ",
        name="创业板ETF易方达",
        time=datetime.fromisoformat("2026-07-20T10:15:00"),
        open=1.0,
        high=1.1,
        low=0.9,
        close=1.05,
        volume=1050,
        amount=1050.0,
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


def test_smtp_notifier_sends_alert_email_to_configured_recipients(
    monkeypatch, tmp_path
):
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
        db_path=_seed_candles_for_alert(tmp_path, monday_first_candle_alert_log()),
    )
    notifier = SMTPAlertNotifier(settings)

    notifier.send_alert(monday_first_candle_alert_log())

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
    assert "510310.SH" in message["Subject"]
    assert "warning" in message["Subject"]
    content = message.get_body(preferencelist=("plain",)).get_content()
    assert "ETF Monitor 告警通知" in content
    assert "交易日：2026-07-27" in content
    assert "监控标的：沪深300ETF易方达 (510310.SH)" in content
    assert "时间\t标的代码\t标的名称\t成交量\t日环比" in content
    assert "7/24/26 09:45\t510310\t沪深300ETF易方达\t20,150,900\t——" in content
    assert "7/27/26 09:45\t510310\t沪深300ETF易方达\t40,667,694\t102%" in content
    assert "告警触发时间：2026-07-27 09:45" in content
    assert "记录时间：2026-07-27 09:45:30 (Asia/Shanghai)" in content
    assert "| K线时间 |" not in content
    assert "| --- |" not in content
    image_parts = [part for part in message.walk() if part.get_content_type() == "image/png"]
    assert len(image_parts) == 1
    assert image_parts[0].get("Content-Disposition", "").startswith("inline")
    html_content = message.get_body(preferencelist=("html",)).get_content()
    assert 'src="cid:alert-table-510310-0945"' in html_content
    assert message.get_body(preferencelist=("plain",)).get_content_charset() == "utf-8"

    raw_message = message.as_bytes()
    parsed_message = BytesParser(policy=policy.default).parsebytes(raw_message)
    assert "沪深300ETF易方达" in str(parsed_message["Subject"])
    assert "沪深300ETF易方达" in parsed_message.get_body(("plain",)).get_content()


def test_smtp_notifier_sends_alert_batch_in_one_email(monkeypatch, tmp_path):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    second_alert = alert_log().model_copy(
        update={
            "id": 2,
            "symbol": "510310.SH",
            "name": "沪深300ETF易方达",
            "candle_time": datetime.fromisoformat("2026-07-20T13:45:00"),
        }
    )
    settings = Settings(
        email_enabled=True,
        smtp_host="smtp.example.com",
        smtp_from="monitor@example.com",
        smtp_to="desk@example.com",
        timezone="Asia/Shanghai",
        db_path=_seed_candles_for_alerts(tmp_path, [alert_log(), second_alert]),
    )

    SMTPAlertNotifier(settings).send_alerts([alert_log(), second_alert])

    assert len(FakeSMTP.instances) == 1
    message = FakeSMTP.instances[0].sent_messages[0]
    assert "2 个异动" in message["Subject"]
    content = message.get_body(preferencelist=("plain",)).get_content()
    assert "ETF Monitor 告警通知" in content
    assert "共 2 个异动" in content
    assert (
        "监控标的：创业板ETF易方达 (159915.SZ)、沪深300ETF易方达 (510310.SH)"
    ) in content
    assert "时间\t标的代码\t标的名称\t成交量\t日内环比" in content
    assert "7/20/26 13:15\t159915\t创业板ETF易方达\t1,000\t——" in content
    assert "7/20/26 13:30\t159915\t创业板ETF易方达\t3,600\t260%" in content
    assert "7/20/26 13:30\t510310\t沪深300ETF易方达\t1,000\t——" in content
    assert "7/20/26 13:45\t510310\t沪深300ETF易方达\t3,600\t260%" in content
    image_parts = [part for part in message.walk() if part.get_content_type() == "image/png"]
    assert len(image_parts) == 2
    assert all(
        part.get("Content-Disposition", "").startswith("inline")
        for part in image_parts
    )
    html_content = message.get_body(preferencelist=("html",)).get_content()
    assert 'src="cid:alert-table-159915-1330"' in html_content
    assert 'src="cid:alert-table-510310-1345"' in html_content


def test_smtp_notifier_formats_record_time_in_configured_timezone(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    settings = Settings(
        email_enabled=True,
        smtp_host="smtp.example.com",
        smtp_from="monitor@example.com",
        smtp_to="desk@example.com",
        timezone="Asia/Shanghai",
    )
    alert = alert_log().model_copy(
        update={"created_at": datetime(2026, 7, 21, 5, 30, 53, tzinfo=UTC)}
    )

    SMTPAlertNotifier(settings).send_alert(alert)

    content = FakeSMTP.instances[0].sent_messages[0].get_body(
        preferencelist=("plain",)
    ).get_content()
    assert "记录时间：2026-07-21 13:30:53 (Asia/Shanghai)" in content


def test_smtp_notifier_sends_no_anomaly_email(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    settings = Settings(
        email_enabled=True,
        smtp_host="smtp.example.com",
        smtp_from="monitor@example.com",
        smtp_to="desk@example.com",
        timezone="Asia/Shanghai",
    )

    SMTPAlertNotifier(settings).send_no_anomaly(
        normal_candle(), datetime(2026, 7, 20, 2, 16, 3, tzinfo=UTC)
    )

    assert len(FakeSMTP.instances) == 1
    message = FakeSMTP.instances[0].sent_messages[0]
    assert "ETF Monitor 更新" in message["Subject"]
    assert "无异动" in message["Subject"]
    assert "创业板ETF易方达 (159915.SZ)" in message["Subject"]
    assert "K线时间: 2026-07-20 10:15:00" in message.get_content()
    assert "本次K线更新未检测到异动。" in message.get_content()
    assert "记录时间: 2026-07-20 10:16:03 (Asia/Shanghai)" in message.get_content()
    assert message.get_content_charset() == "utf-8"
    assert message["Content-Transfer-Encoding"] == "base64"


def test_smtp_notifier_sends_daily_summary_without_alerts(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    settings = Settings(
        email_enabled=True,
        smtp_host="smtp.example.com",
        smtp_from="monitor@example.com",
        smtp_to="desk@example.com",
        timezone="Asia/Shanghai",
    )

    SMTPAlertNotifier(settings).send_daily_summary(
        datetime.fromisoformat("2026-07-20").date(),
        settings.monitored_symbols(),
        [],
        datetime(2026, 7, 20, 7, 1, 0, tzinfo=UTC),
    )

    message = FakeSMTP.instances[0].sent_messages[0]
    assert "收盘总结" in message["Subject"]
    assert "无异动" in message["Subject"]
    assert "交易日：2026-07-20" in message.get_content()
    assert "今日异动: 无" in message.get_content()


def test_smtp_notifier_sends_daily_summary_alerts_as_inline_excel_images(
    monkeypatch, tmp_path
):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    alert = monday_first_candle_alert_log()
    settings = Settings(
        email_enabled=True,
        smtp_host="smtp.example.com",
        smtp_from="monitor@example.com",
        smtp_to="desk@example.com",
        timezone="Asia/Shanghai",
        db_path=_seed_candles_for_alert(tmp_path, alert),
    )

    SMTPAlertNotifier(settings).send_daily_summary(
        datetime.fromisoformat("2026-07-27").date(),
        settings.monitored_symbols(),
        [alert],
        datetime(2026, 7, 27, 7, 1, 0, tzinfo=UTC),
    )

    message = FakeSMTP.instances[0].sent_messages[0]
    assert "收盘总结" in message["Subject"]
    assert "1 个异动" in message["Subject"]
    content = message.get_body(preferencelist=("plain",)).get_content()
    assert "ETF Monitor 收盘总结" in content
    assert "交易日：2026-07-27" in content
    assert "今日异动：" in content
    assert "时间\t标的代码\t标的名称\t成交量\t日环比" in content
    assert "7/24/26 09:45\t510310\t沪深300ETF易方达\t20,150,900\t——" in content
    assert "7/27/26 09:45\t510310\t沪深300ETF易方达\t40,667,694\t102%" in content
    image_parts = [part for part in message.walk() if part.get_content_type() == "image/png"]
    assert len(image_parts) == 1
    assert image_parts[0].get("Content-Disposition", "").startswith("inline")
    html_content = message.get_body(preferencelist=("html",)).get_content()
    assert 'src="cid:alert-table-510310-0945"' in html_content


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


def _seed_candles_for_alert(tmp_path: Path, alert: AlertLog) -> Path:
    db_path = tmp_path / "alerts.db"
    store = AlertStore(db_path)
    store.save_candles(
        [
            Candle(
                symbol=alert.symbol,
                name=alert.name,
                time=datetime.fromisoformat("2026-07-24T09:45:00"),
                open=1,
                high=1,
                low=1,
                close=1,
                volume=alert.prev_volume,
                amount=1,
            ),
            Candle(
                symbol=alert.symbol,
                name=alert.name,
                time=alert.candle_time,
                open=1,
                high=1,
                low=1,
                close=1,
                volume=alert.volume,
                amount=1,
            ),
        ]
    )
    return db_path


def _seed_candles_for_alerts(tmp_path: Path, alerts: list[AlertLog]) -> Path:
    db_path = tmp_path / "alerts.db"
    store = AlertStore(db_path)
    candles = []
    for alert in alerts:
        candles.extend(
            [
                Candle(
                    symbol=alert.symbol,
                    name=alert.name,
                    time=alert.candle_time.replace(minute=alert.candle_time.minute - 15),
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    volume=alert.prev_volume,
                    amount=1,
                ),
                Candle(
                    symbol=alert.symbol,
                    name=alert.name,
                    time=alert.candle_time,
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    volume=alert.volume,
                    amount=1,
                ),
            ]
        )
    store.save_candles(candles)
    return db_path
