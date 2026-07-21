from __future__ import annotations

from statistics import median

from app.config import Settings
from app.models import AlertCreate, Candle


def detect_volume_spike(candles: list[Candle], settings: Settings) -> AlertCreate | None:
    if len(candles) < 2:
        return None

    ordered_all = sorted(candles, key=lambda item: item.time)
    latest_day = ordered_all[-1].time.date()
    ordered = [item for item in ordered_all if item.time.date() == latest_day]
    if len(ordered) < 2:
        return None

    current = ordered[-1]
    previous = ordered[-2]
    if previous.volume <= 0:
        return None

    ratio = current.volume / previous.volume
    history = [item.volume for item in ordered[:-1] if item.volume > 0]
    baseline = _rolling_baseline(history, settings)

    spike = _detect_spike(current.volume, ratio, baseline, settings)
    if spike:
        return _alert(current, previous, round(ratio, 2), settings.volume_ratio_threshold, spike)

    shrink = _detect_shrink(current.volume, ratio, baseline, settings)
    if shrink:
        return _alert(
            current,
            previous,
            round(ratio, 2),
            settings.volume_shrink_ratio_threshold,
            shrink,
        )

    return None


def _rolling_baseline(history: list[int], settings: Settings) -> float | None:
    if len(history) < settings.rolling_window_min:
        return None
    window = history[-settings.rolling_window_max :]
    return float(median(window))


def _detect_spike(
    current_volume: int,
    ratio: float,
    baseline: float | None,
    settings: Settings,
) -> tuple[str, str] | None:
    if ratio < settings.volume_ratio_threshold:
        return None
    if baseline and current_volume < baseline * settings.median_multiplier_threshold:
        return None
    severity = "critical" if ratio >= settings.critical_ratio_threshold else "warning"
    return "volume_spike", severity


def _detect_shrink(
    current_volume: int,
    ratio: float,
    baseline: float | None,
    settings: Settings,
) -> tuple[str, str] | None:
    if ratio > settings.volume_shrink_ratio_threshold:
        return None
    if baseline and current_volume > baseline * settings.median_shrink_multiplier_threshold:
        return None
    severity = "critical" if ratio <= settings.critical_shrink_ratio_threshold else "warning"
    return "volume_shrink", severity


def _alert(
    current: Candle,
    previous: Candle,
    rounded_ratio: float,
    threshold: float,
    detected: tuple[str, str],
) -> AlertCreate:
    alert_type, severity = detected
    if alert_type == "volume_shrink":
        message = (
            f"{current.symbol} 15分钟成交量缩至前一根 "
            f"{rounded_ratio:.2f} 倍，当前量 {current.volume}，前一根 {previous.volume}"
        )
    else:
        message = (
            f"{current.symbol} 15分钟成交量放大 "
            f"{rounded_ratio:.2f} 倍，当前量 {current.volume}，前一根 {previous.volume}"
        )
    return AlertCreate(
        symbol=current.symbol,
        name=current.name,
        alert_type=alert_type,
        candle_time=current.time,
        volume=current.volume,
        prev_volume=previous.volume,
        ratio=rounded_ratio,
        threshold=threshold,
        severity=severity,
        message=message,
    )
