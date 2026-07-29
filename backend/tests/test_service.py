from datetime import datetime

from app.config import EtfSymbolConfig, Settings
from app.models import Candle
from app.service import MonitorService


def candle(time: str, volume: int, symbol: str, name: str) -> Candle:
    return Candle(
        symbol=symbol,
        name=name,
        time=datetime.fromisoformat(time),
        open=1.0,
        high=1.1,
        low=0.9,
        close=1.0,
        volume=volume,
        amount=float(volume),
    )


class FakeMarketDataClient:
    def fetch_intraday_candles(self, symbol: str) -> list[Candle]:
        return []


def test_detect_and_save_keeps_each_symbols_volume_sequence_separate(tmp_path):
    settings = Settings(
        symbols=[
            EtfSymbolConfig(symbol="159915.SZ", name="ETF A"),
            EtfSymbolConfig(symbol="510300.SH", name="ETF B"),
        ],
        volume_ratio_threshold=1.5,
    )
    service = MonitorService(
        settings=settings,
        market_data_client=FakeMarketDataClient(),
        db_path=tmp_path / "alerts.db",
    )
    candles = [
        candle("2026-07-28T09:45:00", 1000, "159915.SZ", "ETF A"),
        candle("2026-07-28T09:45:00", 100_000, "510300.SH", "ETF B"),
        candle("2026-07-28T10:00:00", 2000, "159915.SZ", "ETF A"),
        candle("2026-07-28T10:00:00", 100_000, "510300.SH", "ETF B"),
    ]

    result = service._detect_and_save(candles, send_notifications=False)

    assert len(result.inserted_alerts) == 1
    alert = result.inserted_alerts[0]
    assert alert.symbol == "159915.SZ"
    assert alert.candle_time == datetime.fromisoformat("2026-07-28T10:00:00")
    assert alert.prev_volume == 1000
    assert alert.ratio == 2.0
