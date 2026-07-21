from app import config
from app.config import Settings


def test_settings_loads_values_from_dotenv_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "ETF_SYMBOL=510300.SH\nVOLUME_RATIO_THRESHOLD=4.2\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "_ENV_LOADED", False)
    monkeypatch.delenv("ETF_SYMBOL", raising=False)
    monkeypatch.delenv("VOLUME_RATIO_THRESHOLD", raising=False)

    settings = Settings()

    assert settings.symbol == "510300.SH"
    assert settings.volume_ratio_threshold == 4.2


def test_settings_loads_smtp_values_from_dotenv_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "EMAIL_ENABLED=true",
                "SMTP_HOST=smtp.example.com",
                "SMTP_PORT=465",
                "SMTP_USERNAME=monitor@example.com",
                "SMTP_PASSWORD=secret",
                "SMTP_FROM=monitor@example.com",
                "SMTP_TO=desk@example.com,pm@example.com",
                "SMTP_USE_SSL=true",
                "SMTP_STARTTLS=false",
                "SMTP_TIMEOUT_SECONDS=8",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "_ENV_LOADED", False)
    for key in [
        "EMAIL_ENABLED",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_FROM",
        "SMTP_TO",
        "SMTP_USE_SSL",
        "SMTP_STARTTLS",
        "SMTP_TIMEOUT_SECONDS",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = Settings()

    assert settings.email_enabled is True
    assert settings.smtp_host == "smtp.example.com"
    assert settings.smtp_port == 465
    assert settings.smtp_username == "monitor@example.com"
    assert settings.smtp_password == "secret"
    assert settings.smtp_from == "monitor@example.com"
    assert settings.smtp_to == "desk@example.com,pm@example.com"
    assert settings.smtp_use_ssl is True
    assert settings.smtp_starttls is False
    assert settings.smtp_timeout_seconds == 8


def test_settings_loads_monitored_symbols_from_dotenv_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "ETF_SYMBOLS=159915.SZ:创业板ETF易方达,510310.SH:沪深300ETF易方达,588080.SH:科创50ETF易方达\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "_ENV_LOADED", False)
    monkeypatch.delenv("ETF_SYMBOLS", raising=False)

    settings = Settings()

    assert [(item.symbol, item.name) for item in settings.monitored_symbols()] == [
        ("159915.SZ", "创业板ETF易方达"),
        ("510310.SH", "沪深300ETF易方达"),
        ("588080.SH", "科创50ETF易方达"),
    ]
