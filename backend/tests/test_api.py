from datetime import datetime

from fastapi.testclient import TestClient

from app.config import EtfSymbolConfig, Settings
from app.main import create_app
from app.models import Candle


def candle(
    time: str,
    volume: int,
    symbol: str = "159915.SZ",
    name: str = "创业板ETF易方达",
) -> Candle:
    return Candle(
        symbol=symbol,
        name=name,
        time=datetime.fromisoformat(time),
        open=1.0,
        high=1.1,
        low=0.9,
        close=1.05,
        volume=volume,
        amount=volume * 1.0,
    )


class FakeMarketDataClient:
    def __init__(self, candles=None, error=None):
        self.candles = candles or []
        self.error = error

    def fetch_intraday_candles(self, symbol: str):
        if self.error:
            raise self.error
        return self.candles


class SymbolAwareMarketDataClient:
    def __init__(self):
        self.calls = []

    def fetch_intraday_candles(self, symbol: str):
        self.calls.append(symbol)
        names = {
            "159915.SZ": "创业板ETF易方达",
            "510310.SH": "沪深300ETF易方达",
            "588080.SH": "科创50ETF易方达",
        }
        return [
            candle("2026-07-20T09:45:00", 1000, symbol=symbol, name=names[symbol]),
            candle("2026-07-20T10:00:00", 1200, symbol=symbol, name=names[symbol]),
        ]


class RecordingNotifier:
    def __init__(self):
        self.alerts = []

    def send_alert(self, alert):
        self.alerts.append(alert)


def test_poll_creates_alert_and_snapshot_returns_current_alert(tmp_path):
    market_data = FakeMarketDataClient(
        candles=[
            candle("2026-07-20T09:45:00", 1000),
            candle("2026-07-20T10:00:00", 1000),
            candle("2026-07-20T10:15:00", 1000),
            candle("2026-07-20T10:30:00", 1000),
            candle("2026-07-20T10:45:00", 1000),
            candle("2026-07-20T11:00:00", 1000),
            candle("2026-07-20T11:15:00", 1000),
            candle("2026-07-20T11:30:00", 1000),
            candle("2026-07-20T13:15:00", 1000),
            candle("2026-07-20T13:30:00", 3600),
        ]
    )
    app = create_app(
        db_path=tmp_path / "alerts.db",
        market_data_client=market_data,
        scheduler_enabled=False,
    )
    client = TestClient(app)

    poll_response = client.post("/api/monitor/poll")
    snapshot_response = client.get("/api/monitor/snapshot?symbol=159915.SZ")
    alerts_response = client.get("/api/alerts?symbol=159915.SZ&limit=100")

    assert poll_response.status_code == 200
    assert poll_response.json()["alert"]["severity"] == "warning"
    assert snapshot_response.status_code == 200
    assert snapshot_response.json()["current_alert"]["severity"] == "warning"
    assert snapshot_response.json()["latest_candle"]["volume"] == 3600
    assert snapshot_response.json()["last_updated"] == "2026-07-20T13:30:00"
    assert alerts_response.status_code == 200
    assert len(alerts_response.json()["alerts"]) == 1


def test_symbols_endpoint_returns_configured_etfs(tmp_path):
    settings = Settings(
        symbols=[
            EtfSymbolConfig(symbol="159915.SZ", name="创业板ETF易方达"),
            EtfSymbolConfig(symbol="510310.SH", name="沪深300ETF易方达"),
            EtfSymbolConfig(symbol="588080.SH", name="科创50ETF易方达"),
        ]
    )
    app = create_app(
        db_path=tmp_path / "alerts.db",
        market_data_client=FakeMarketDataClient(),
        scheduler_enabled=False,
        settings=settings,
    )
    client = TestClient(app)

    response = client.get("/api/monitor/symbols")

    assert response.status_code == 200
    assert response.json()["symbols"] == [
        {"symbol": "159915.SZ", "name": "创业板ETF易方达"},
        {"symbol": "510310.SH", "name": "沪深300ETF易方达"},
        {"symbol": "588080.SH", "name": "科创50ETF易方达"},
    ]


def test_poll_all_polls_every_configured_symbol(tmp_path):
    market_data = SymbolAwareMarketDataClient()
    settings = Settings(
        symbols=[
            EtfSymbolConfig(symbol="159915.SZ", name="创业板ETF易方达"),
            EtfSymbolConfig(symbol="510310.SH", name="沪深300ETF易方达"),
            EtfSymbolConfig(symbol="588080.SH", name="科创50ETF易方达"),
        ]
    )
    app = create_app(
        db_path=tmp_path / "alerts.db",
        market_data_client=market_data,
        scheduler_enabled=False,
        settings=settings,
    )
    client = TestClient(app)

    response = client.post("/api/monitor/poll-all")

    assert response.status_code == 200
    assert market_data.calls == ["159915.SZ", "510310.SH", "588080.SH"]
    assert [item["symbol"] for item in response.json()["results"]] == [
        "159915.SZ",
        "510310.SH",
        "588080.SH",
    ]


def test_snapshot_uses_configured_name_for_selected_symbol(tmp_path):
    settings = Settings(
        symbols=[
            EtfSymbolConfig(symbol="159915.SZ", name="创业板ETF易方达"),
            EtfSymbolConfig(symbol="510310.SH", name="沪深300ETF易方达"),
        ]
    )
    app = create_app(
        db_path=tmp_path / "alerts.db",
        market_data_client=SymbolAwareMarketDataClient(),
        scheduler_enabled=False,
        settings=settings,
    )
    client = TestClient(app)

    response = client.get("/api/monitor/snapshot?symbol=510310.SH")

    assert response.status_code == 200
    assert response.json()["symbol"] == "510310.SH"
    assert response.json()["name"] == "沪深300ETF易方达"


def test_poll_detects_intraday_anomaly_even_when_latest_candle_is_normal(tmp_path):
    symbol = "510310.SH"
    name = "沪深300ETF易方达"
    market_data = FakeMarketDataClient(
        candles=[
            candle("2026-07-21T09:45:00", 50_000_000, symbol=symbol, name=name),
            candle("2026-07-21T10:00:00", 48_558_850, symbol=symbol, name=name),
            candle("2026-07-21T10:15:00", 37_753_800, symbol=symbol, name=name),
            candle("2026-07-21T10:30:00", 29_947_193, symbol=symbol, name=name),
            candle("2026-07-21T10:45:00", 40_176_349, symbol=symbol, name=name),
            candle("2026-07-21T11:00:00", 17_418_272, symbol=symbol, name=name),
            candle("2026-07-21T11:15:00", 20_000_000, symbol=symbol, name=name),
        ]
    )
    notifier = RecordingNotifier()
    app = create_app(
        db_path=tmp_path / "alerts.db",
        market_data_client=market_data,
        scheduler_enabled=False,
        notifier=notifier,
    )
    client = TestClient(app)

    poll_response = client.post(f"/api/monitor/poll?symbol={symbol}")
    alerts_response = client.get(f"/api/alerts?symbol={symbol}&limit=100")

    assert poll_response.status_code == 200
    assert alerts_response.status_code == 200
    alerts = alerts_response.json()["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "volume_shrink"
    assert alerts[0]["candle_time"] == "2026-07-21T11:00:00"
    assert alerts[0]["ratio"] == 0.43
    assert alerts[0]["volume"] == 17_418_272
    assert alerts[0]["prev_volume"] == 40_176_349
    assert len(notifier.alerts) == 1
    assert notifier.alerts[0].candle_time == datetime.fromisoformat(
        "2026-07-21T11:00:00"
    )


def test_poll_sends_notification_only_for_new_alerts(tmp_path):
    market_data = FakeMarketDataClient(
        candles=[
            candle("2026-07-20T09:45:00", 1000),
            candle("2026-07-20T10:00:00", 1000),
            candle("2026-07-20T10:15:00", 1000),
            candle("2026-07-20T10:30:00", 1000),
            candle("2026-07-20T10:45:00", 1000),
            candle("2026-07-20T11:00:00", 1000),
            candle("2026-07-20T11:15:00", 1000),
            candle("2026-07-20T11:30:00", 1000),
            candle("2026-07-20T13:15:00", 1000),
            candle("2026-07-20T13:30:00", 3600),
        ]
    )
    notifier = RecordingNotifier()
    app = create_app(
        db_path=tmp_path / "alerts.db",
        market_data_client=market_data,
        scheduler_enabled=False,
        notifier=notifier,
    )
    client = TestClient(app)

    first_response = client.post("/api/monitor/poll")
    second_response = client.post("/api/monitor/poll")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert len(notifier.alerts) == 1
    assert notifier.alerts[0].symbol == "159915.SZ"
    assert notifier.alerts[0].candle_time == datetime.fromisoformat(
        "2026-07-20T13:30:00"
    )


def test_snapshot_uses_cached_candles_when_market_data_source_fails(tmp_path):
    db_path = tmp_path / "alerts.db"
    healthy_app = create_app(
        db_path=db_path,
        market_data_client=FakeMarketDataClient(
            candles=[
                candle("2026-07-20T09:45:00", 1000),
                candle("2026-07-20T10:00:00", 1200),
            ]
        ),
        scheduler_enabled=False,
    )
    TestClient(healthy_app).post("/api/monitor/poll")

    degraded_app = create_app(
        db_path=db_path,
        market_data_client=FakeMarketDataClient(error=RuntimeError("akshare failed")),
        scheduler_enabled=False,
    )
    client = TestClient(degraded_app)

    response = client.get("/api/monitor/snapshot?symbol=159915.SZ")

    assert response.status_code == 200
    body = response.json()
    assert body["data_status"] == "cached"
    assert body["error"] == "akshare failed"
    assert body["current_alert"] is None
    assert body["latest_candle"]["volume"] == 1200
    assert body["last_updated"] == "2026-07-20T10:00:00"
    assert len(body["candles"]) == 2


def test_snapshot_returns_only_latest_trading_day_candles(tmp_path):
    app = create_app(
        db_path=tmp_path / "alerts.db",
        market_data_client=FakeMarketDataClient(
            candles=[
                candle("2026-07-17T14:45:00", 900),
                candle("2026-07-17T15:00:00", 950),
                candle("2026-07-20T09:45:00", 1000),
                candle("2026-07-20T10:00:00", 1200),
            ]
        ),
        scheduler_enabled=False,
    )
    client = TestClient(app)

    response = client.get("/api/monitor/snapshot?symbol=159915.SZ")

    assert response.status_code == 200
    body = response.json()
    assert [item["time"] for item in body["candles"]] == [
        "2026-07-20T09:45:00",
        "2026-07-20T10:00:00",
    ]
