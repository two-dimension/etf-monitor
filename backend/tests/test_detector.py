from datetime import datetime

from app.config import Settings
from app.detector import detect_volume_spike
from app.models import Candle


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


def test_does_not_alert_when_current_volume_is_below_ratio_threshold():
    settings = Settings(volume_ratio_threshold=3.0, median_multiplier_threshold=1.8)
    candles = [
        candle("2026-07-21T09:45:00", 1200),
        candle("2026-07-21T10:00:00", 2500),
    ]

    alert = detect_volume_spike(candles, settings)

    assert alert is None


def test_alerts_when_current_volume_exceeds_ratio_and_history_thresholds():
    settings = Settings(volume_ratio_threshold=3.0, median_multiplier_threshold=1.8)
    candles = [
        candle("2026-07-21T09:45:00", 1000),
        candle("2026-07-21T10:00:00", 1100),
        candle("2026-07-21T10:15:00", 950),
        candle("2026-07-21T10:30:00", 1050),
        candle("2026-07-21T10:45:00", 1025),
        candle("2026-07-21T11:00:00", 990),
        candle("2026-07-21T11:15:00", 1010),
        candle("2026-07-21T11:30:00", 980),
        candle("2026-07-21T13:15:00", 1200),
        candle("2026-07-21T13:30:00", 4200),
    ]

    alert = detect_volume_spike(candles, settings)

    assert alert is not None
    assert alert.symbol == "159915.SZ"
    assert alert.candle_time == datetime.fromisoformat("2026-07-21T13:30:00")
    assert alert.volume == 4200
    assert alert.prev_volume == 1200
    assert alert.ratio == 3.5
    assert alert.severity == "warning"


def test_marks_critical_when_volume_ratio_exceeds_critical_threshold():
    settings = Settings(
        volume_ratio_threshold=3.0,
        median_multiplier_threshold=1.8,
        critical_ratio_threshold=5.0,
    )
    candles = [
        candle("2026-07-21T09:45:00", 1000),
        candle("2026-07-21T10:00:00", 1000),
        candle("2026-07-21T10:15:00", 1000),
        candle("2026-07-21T10:30:00", 1000),
        candle("2026-07-21T10:45:00", 1000),
        candle("2026-07-21T11:00:00", 1000),
        candle("2026-07-21T11:15:00", 1000),
        candle("2026-07-21T11:30:00", 1000),
        candle("2026-07-21T13:15:00", 1000),
        candle("2026-07-21T13:30:00", 5100),
    ]

    alert = detect_volume_spike(candles, settings)

    assert alert is not None
    assert alert.ratio == 5.1
    assert alert.severity == "critical"


def test_does_not_alert_when_previous_volume_is_zero():
    settings = Settings(volume_ratio_threshold=3.0, median_multiplier_threshold=1.8)
    candles = [
        candle("2026-07-21T09:45:00", 0),
        candle("2026-07-21T10:00:00", 5000),
    ]

    alert = detect_volume_spike(candles, settings)

    assert alert is None


def test_does_not_compare_first_candle_of_day_with_previous_trading_day():
    settings = Settings(volume_ratio_threshold=3.0, median_multiplier_threshold=1.8)
    candles = [
        candle("2026-07-20T14:45:00", 100),
        candle("2026-07-21T09:45:00", 1000),
    ]

    alert = detect_volume_spike(candles, settings)

    assert alert is None


def test_does_not_alert_when_rolling_median_filter_rejects_low_base_spike():
    settings = Settings(volume_ratio_threshold=3.0, median_multiplier_threshold=1.8)
    candles = [
        candle("2026-07-21T09:45:00", 5000),
        candle("2026-07-21T10:00:00", 4800),
        candle("2026-07-21T10:15:00", 5100),
        candle("2026-07-21T10:30:00", 4900),
        candle("2026-07-21T10:45:00", 5000),
        candle("2026-07-21T11:00:00", 4700),
        candle("2026-07-21T11:15:00", 5200),
        candle("2026-07-21T11:30:00", 5050),
        candle("2026-07-21T13:15:00", 1000),
        candle("2026-07-21T13:30:00", 3200),
    ]

    alert = detect_volume_spike(candles, settings)

    assert alert is None


def test_alerts_when_current_volume_contracts_below_ratio_and_history_thresholds():
    settings = Settings(
        volume_shrink_ratio_threshold=0.35,
        median_shrink_multiplier_threshold=0.5,
    )
    candles = [
        candle("2026-07-21T09:45:00", 5000),
        candle("2026-07-21T10:00:00", 5200),
        candle("2026-07-21T10:15:00", 4800),
        candle("2026-07-21T10:30:00", 5100),
        candle("2026-07-21T10:45:00", 5000),
        candle("2026-07-21T11:00:00", 4900),
        candle("2026-07-21T11:15:00", 5300),
        candle("2026-07-21T11:30:00", 5000),
        candle("2026-07-21T13:15:00", 6000),
        candle("2026-07-21T13:30:00", 1800),
    ]

    alert = detect_volume_spike(candles, settings)

    assert alert is not None
    assert alert.alert_type == "volume_shrink"
    assert alert.ratio == 0.3
    assert alert.threshold == 0.35
    assert alert.severity == "warning"


def test_marks_critical_when_current_volume_contracts_below_critical_threshold():
    settings = Settings(
        volume_shrink_ratio_threshold=0.35,
        median_shrink_multiplier_threshold=0.5,
        critical_shrink_ratio_threshold=0.2,
    )
    candles = [
        candle("2026-07-21T09:45:00", 5000),
        candle("2026-07-21T10:00:00", 5000),
        candle("2026-07-21T10:15:00", 5000),
        candle("2026-07-21T10:30:00", 5000),
        candle("2026-07-21T10:45:00", 5000),
        candle("2026-07-21T11:00:00", 5000),
        candle("2026-07-21T11:15:00", 5000),
        candle("2026-07-21T11:30:00", 5000),
        candle("2026-07-21T13:15:00", 5000),
        candle("2026-07-21T13:30:00", 900),
    ]

    alert = detect_volume_spike(candles, settings)

    assert alert is not None
    assert alert.alert_type == "volume_shrink"
    assert alert.ratio == 0.18
    assert alert.severity == "critical"
