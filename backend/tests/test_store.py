from datetime import datetime

from app.models import AlertCreate, Candle
from app.store import AlertStore


def candle(time: str, volume: int) -> Candle:
    return Candle(
        symbol="159915.SZ",
        name="创业板ETF易方达",
        time=datetime.fromisoformat(time),
        open=1.0,
        high=1.1,
        low=0.9,
        close=1.05,
        volume=volume,
        amount=volume * 1.0,
    )


def alert(candle_time: datetime) -> AlertCreate:
    return AlertCreate(
        symbol="159915.SZ",
        name="创业板ETF易方达",
        candle_time=candle_time,
        volume=4200,
        prev_volume=1200,
        ratio=3.5,
        threshold=3.0,
        severity="warning",
        message="159915.SZ 15分钟成交量放大 3.50 倍",
    )


def test_store_deduplicates_alerts_by_symbol_and_candle_time(tmp_path):
    store = AlertStore(tmp_path / "alerts.db")
    candle_time = datetime.fromisoformat("2026-07-21T13:30:00")

    first = store.save_alert(alert(candle_time))
    second = store.save_alert(alert(candle_time))

    alerts = store.list_alerts("159915.SZ", limit=10)
    assert first.id == second.id
    assert len(alerts) == 1
    assert alerts[0].candle_time == candle_time


def test_store_reports_whether_alert_was_newly_inserted(tmp_path):
    store = AlertStore(tmp_path / "alerts.db")
    candle_time = datetime.fromisoformat("2026-07-21T13:30:00")

    first, first_inserted = store.save_alert_with_status(alert(candle_time))
    second, second_inserted = store.save_alert_with_status(alert(candle_time))

    assert first_inserted is True
    assert second_inserted is False
    assert first.id == second.id


def test_store_upserts_and_lists_cached_candles_by_symbol(tmp_path):
    store = AlertStore(tmp_path / "alerts.db")

    store.save_candles(
        [
            candle("2026-07-21T09:45:00", 1000),
            candle("2026-07-21T10:00:00", 1200),
        ]
    )
    store.save_candles(
        [
            candle("2026-07-21T10:00:00", 1500),
            candle("2026-07-21T10:15:00", 1600),
        ]
    )

    candles = store.list_candles("159915.SZ", limit=10)
    assert [item.time for item in candles] == [
        datetime.fromisoformat("2026-07-21T09:45:00"),
        datetime.fromisoformat("2026-07-21T10:00:00"),
        datetime.fromisoformat("2026-07-21T10:15:00"),
    ]
    assert [item.volume for item in candles] == [1000, 1500, 1600]
