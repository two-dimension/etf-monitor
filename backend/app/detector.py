from __future__ import annotations

from datetime import timedelta

from app.config import Settings
from app.models import AlertCreate, Candle


def detect_volume_spike(candles: list[Candle], settings: Settings) -> AlertCreate | None:
    if len(candles) < 2:
        return None

    ordered_all = sorted(candles, key=lambda item: item.time)
    latest_day = ordered_all[-1].time.date()
    ordered = [item for item in ordered_all if item.time.date() == latest_day]
    if not ordered:
        return None

    current = ordered[-1]
    if settings.is_opening_candle(current.time):
        previous = _previous_trading_day_same_slot_candle(ordered_all, current, settings)
        return _detect_spike_against_previous(current, previous, settings)

    same_day_previous = _previous_same_day_candle(ordered, current, settings)
    alert = _detect_spike_against_previous(current, same_day_previous, settings)
    if alert is not None:
        return alert

    previous_day_same_slot = _previous_trading_day_same_slot_candle(
        ordered_all, current, settings
    )
    return _detect_spike_against_previous(current, previous_day_same_slot, settings)


def _detect_spike_against_previous(
    current: Candle,
    previous: Candle | None,
    settings: Settings,
) -> AlertCreate | None:
    if previous is None or previous.amount <= 0:
        return None

    ratio = current.amount / previous.amount

    spike = _detect_spike(ratio, settings, current.time)
    if spike:
        _, severity = spike
        threshold = (
            settings.critical_ratio_threshold_for(current.time)
            if severity == "critical"
            else settings.volume_ratio_threshold_for(current.time)
        )
        return _alert(current, previous, round(ratio, 2), threshold, spike, settings)

    return None


def _detect_spike(
    ratio: float,
    settings: Settings,
    candle_time,
) -> tuple[str, str] | None:
    volume_threshold = settings.volume_ratio_threshold_for(candle_time)
    if ratio < volume_threshold:
        return None
    critical_threshold = settings.critical_ratio_threshold_for(candle_time)
    severity = "critical" if ratio >= critical_threshold else "warning"
    return "volume_spike", severity


def _alert(
    current: Candle,
    previous: Candle,
    rounded_ratio: float,
    threshold: float,
    detected: tuple[str, str],
    settings: Settings,
) -> AlertCreate:
    alert_type, severity = detected
    period_label = f"{_effective_kline_period(current, settings)}分钟"
    current_period = _kline_period_label(current, settings)
    previous_period = _kline_period_label(previous, settings)
    if current.time.date() != previous.time.date():
        previous_label = f"前一交易日同一时间点 {previous.time:%H:%M}"
    else:
        previous_label = f"前一根 {previous.time:%H:%M}"
    if alert_type == "volume_shrink":
        message = (
            f"{current.symbol} {period_label}（{current_period}）成交额缩至{previous_label} "
            f"{rounded_ratio:.2f} 倍，当前额 {current.amount}，{previous_label}（{previous_period}） {previous.amount}"
        )
    else:
        message = (
            f"{current.symbol} {period_label}（{current_period}）成交额放大 "
            f"{rounded_ratio:.2f} 倍，当前额 {current.amount}，{previous_label}（{previous_period}） {previous.amount}"
        )
    return AlertCreate(
        symbol=current.symbol,
        name=current.name,
        alert_type=alert_type,
        candle_time=current.time,
        volume=current.amount,
        prev_volume=previous.amount,
        ratio=rounded_ratio,
        threshold=threshold,
        severity=severity,
        message=message,
    )


def _previous_trading_day_same_slot_candle(
    candles,
    current,
    settings: Settings,
):
    """Find the same time on the most recent prior trading day."""
    previous_dates = sorted(
        {item.time.date() for item in candles if item.time.date() < current.time.date()},
        reverse=True,
    )
    if not previous_dates:
        return None
    previous_date = previous_dates[0]
    matches = [
        item
        for item in candles
        if item.time.date() == previous_date and item.time.time() == current.time.time()
        and _same_effective_kline_period(item, current, settings)
    ]
    if not matches:
        return None
    return matches[-1]


def _previous_same_day_candle(candles, current, settings: Settings):
    matches = [
        item
        for item in candles
        if item.time.date() == current.time.date()
        and item.time < current.time
        and _same_effective_kline_period(item, current, settings)
    ]
    if not matches:
        return None
    return matches[-1]


def _kline_period_label(candle: Candle, settings: Settings) -> str:
    period = int(_effective_kline_period(candle, settings))
    end_time = candle.time + timedelta(minutes=period)
    return f"{candle.time:%H:%M}-{end_time:%H:%M}"


def _same_effective_kline_period(left: Candle, right: Candle, settings: Settings) -> bool:
    return _effective_kline_period(left, settings) == _effective_kline_period(
        right, settings
    )


def _effective_kline_period(candle: Candle, settings: Settings) -> str:
    expected_period = settings.kline_period_for(candle.time)
    if candle.time.time() == settings.late_session_start_time:
        return candle.kline_period
    return expected_period
