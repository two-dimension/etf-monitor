from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo

from app.config import Settings
from app.detector import detect_volume_spike
from app.market_data import MarketDataClient
from app.models import (
    AlertLog,
    Candle,
    DataStatus,
    MonitorSnapshot,
    PollResponse,
    SymbolInfo,
)
from app.notifier import AlertNotifier, NoopAlertNotifier
from app.store import AlertStore


logger = logging.getLogger(__name__)
ALERT_BATCH_SYMBOL = "__alert_batch__"
DAILY_SUMMARY_SYMBOL = "__all__"
DAILY_SUMMARY_TIME = time(15, 0)
FIRST_COMPLETED_CANDLE_TIME = time(9, 45)
DAILY_SUMMARY_EXCLUDED_ALERT_TIMES = {FIRST_COMPLETED_CANDLE_TIME}


@dataclass
class DetectionResult:
    latest_inserted_alert: AlertLog | None
    inserted_alerts: list[AlertLog]
    latest_candle: Candle | None


class MonitorService:
    def __init__(
        self,
        settings: Settings,
        market_data_client: MarketDataClient,
        db_path: str | Path,
        notifier: AlertNotifier | None = None,
    ):
        self.settings = settings
        self.market_data_client = market_data_client
        self.alert_store = AlertStore(db_path)
        self.candle_cache = self.alert_store
        self.notifier = notifier or NoopAlertNotifier()
        self.last_error: str | None = None
        self.last_status: DataStatus = "empty"

    def poll(self, symbol: str | None = None) -> PollResponse:
        requested_symbol = symbol or self.settings.symbol
        response, _ = self._poll_symbol(
            requested_symbol,
            notify_no_anomaly=True,
            send_notifications=True,
        )
        return response

    def poll_all(self) -> list[PollResponse]:
        results: list[PollResponse] = []
        latest_candles: list[Candle] = []

        for item in self.settings.monitored_symbols():
            response, detection = self._poll_symbol(
                item.symbol,
                notify_no_anomaly=False,
                send_notifications=False,
            )
            results.append(response)
            if detection.latest_candle is not None:
                latest_candles.append(detection.latest_candle)

        self._send_batch_notifications_if_all_symbols_ready(results, latest_candles)

        self._send_daily_summary_if_market_closed(latest_candles)
        return results

    def snapshot(self, symbol: str | None = None) -> MonitorSnapshot:
        requested_symbol = symbol or self.settings.symbol
        try:
            candles = self._fetch_live_candles(requested_symbol)
            self.candle_cache.upsert_candles(candles)
            candles = _snapshot_candles(candles, self.settings)
            self.last_error = None
            data_status: DataStatus = "live" if candles else "empty"
        except Exception as exc:
            candles = self.candle_cache.list_candles(requested_symbol)
            candles = _snapshot_candles(candles, self.settings)
            self.last_error = str(exc)
            data_status = "cached" if candles else "degraded"

        latest_candle = candles[-1] if candles else None
        return MonitorSnapshot(
            symbol=requested_symbol,
            name=self.settings.name_for_symbol(requested_symbol),
            data_status=data_status,
            latest_candle=latest_candle,
            candles=candles[-80:],
            current_alert=self._current_alert(requested_symbol, latest_candle),
            last_updated=latest_candle.time if latest_candle else None,
            error=self.last_error if data_status in {"cached", "degraded"} else None,
        )

    def list_alerts(
        self, symbol: str | None = None, limit: int = 100
    ) -> list[AlertLog]:
        requested_symbol = symbol or self.settings.symbol
        return self.alert_store.list_alerts(
            requested_symbol, limit=max(1, min(limit, 500))
        )

    def list_symbols(self) -> list[SymbolInfo]:
        return [
            SymbolInfo(symbol=item.symbol, name=item.name)
            for item in self.settings.monitored_symbols()
        ]

    def health(self) -> tuple[DataStatus, datetime | None, str | None]:
        cached = self.candle_cache.list_candles(self.settings.symbol, limit=1)
        last_updated = cached[-1].time if cached else None
        return self.last_status, last_updated, self.last_error

    def _fetch_live_candles(self, symbol: str) -> list[Candle]:
        candles = self.market_data_client.fetch_intraday_candles(symbol)
        return _completed_candles(candles)

    def _poll_symbol(
        self,
        requested_symbol: str,
        notify_no_anomaly: bool,
        send_notifications: bool,
    ) -> tuple[PollResponse, DetectionResult]:
        try:
            candles = self._fetch_live_candles(requested_symbol)
            self.candle_cache.upsert_candles(candles)
            latest_day_candles = _latest_trading_day_candles(candles)
            self.last_error = None
            self.last_status = "live" if latest_day_candles else "empty"
            detection = self._detect_and_save(
                candles,
                notify_no_anomaly=notify_no_anomaly,
                send_notifications=send_notifications,
            )
            return (
                PollResponse(
                    symbol=requested_symbol,
                    data_status=self.last_status,
                    candle_count=len(latest_day_candles),
                    alert=detection.latest_inserted_alert,
                ),
                detection,
            )
        except Exception as exc:
            cached = self.candle_cache.list_candles(requested_symbol, limit=500)
            latest_day_cached = _latest_trading_day_candles(cached)
            self.last_error = str(exc)
            self.last_status = "cached" if latest_day_cached else "degraded"
            detection = (
                self._detect_and_save(
                    cached,
                    send_notifications=send_notifications,
                )
                if latest_day_cached
                else DetectionResult(None, [], None)
            )
            return (
                PollResponse(
                    symbol=requested_symbol,
                    data_status=self.last_status,
                    candle_count=len(latest_day_cached),
                    alert=detection.latest_inserted_alert,
                    error=str(exc),
                ),
                detection,
            )

    def _detect_and_save(
        self,
        candles: Sequence[Candle],
        notify_no_anomaly: bool = False,
        send_notifications: bool = True,
    ) -> DetectionResult:
        ordered = sorted(candles, key=lambda item: item.time)
        if not ordered:
            return DetectionResult(None, [], None)

        latest_date = ordered[-1].time.date()
        latest_inserted_alert: AlertLog | None = None
        inserted_alerts: list[AlertLog] = []
        latest_day_candles = [
            candle for candle in ordered if candle.time.date() == latest_date
        ]
        latest_candle = latest_day_candles[-1] if latest_day_candles else None
        latest_candle_has_alert = False
        for symbol in sorted({candle.symbol for candle in ordered}):
            symbol_candles = [candle for candle in ordered if candle.symbol == symbol]
            historical_candles = [
                candle for candle in symbol_candles if candle.time.date() < latest_date
            ]
            symbol_latest_day_candles = [
                candle for candle in symbol_candles if candle.time.date() == latest_date
            ]
            for end_index in range(1, len(symbol_latest_day_candles) + 1):
                alert = detect_volume_spike(
                    historical_candles + symbol_latest_day_candles[:end_index],
                    self.settings,
                )
                if alert is None:
                    continue
                if latest_candle is not None and alert.candle_time == latest_candle.time:
                    latest_candle_has_alert = True
                saved_alert, inserted = self.alert_store.save_alert_with_status(alert)
                if inserted:
                    inserted_alerts.append(saved_alert)
                    if send_notifications:
                        self._send_alert_notification(saved_alert)
                    latest_inserted_alert = saved_alert

        if (
            notify_no_anomaly
            and latest_candle is not None
            and not latest_candle_has_alert
            and not inserted_alerts
            and send_notifications
        ):
            self._send_no_anomaly_notification(latest_candle)
        return DetectionResult(latest_inserted_alert, inserted_alerts, latest_candle)

    def _send_alert_notification(self, alert: AlertLog) -> None:
        try:
            self.notifier.send_alert(alert)
        except Exception:
            logger.exception("failed to send alert notification")

    def _send_alert_notifications(self, alerts: Sequence[AlertLog]) -> None:
        if not alerts:
            return
        try:
            self.notifier.send_alerts(alerts)
        except Exception:
            logger.exception("failed to send alert notifications")

    def _send_no_anomaly_notification(self, candle: Candle) -> None:
        notified_at, inserted = self.alert_store.save_notification_event_with_status(
            symbol=candle.symbol,
            candle_time=candle.time,
            event_type="no_anomaly",
        )
        if not inserted:
            return
        try:
            self.notifier.send_no_anomaly(candle, notified_at)
        except Exception:
            logger.exception("failed to send no-anomaly notification")

    def _send_no_anomaly_notifications(self, candles: Sequence[Candle]) -> None:
        notified_at: datetime | None = None
        new_candles: list[Candle] = []
        for candle in candles:
            event_time, inserted = self.alert_store.save_notification_event_with_status(
                symbol=candle.symbol,
                candle_time=candle.time,
                event_type="no_anomaly",
            )
            if inserted:
                notified_at = event_time
                new_candles.append(candle)
        if not new_candles or notified_at is None:
            return
        try:
            self.notifier.send_no_anomalies(new_candles, notified_at)
        except Exception:
            logger.exception("failed to send no-anomaly notifications")

    def _send_batch_notifications_if_all_symbols_ready(
        self,
        results: Sequence[PollResponse],
        latest_candles: Sequence[Candle],
    ) -> None:
        monitored_count = len(self.settings.monitored_symbols())
        if len(results) < monitored_count or len(latest_candles) < monitored_count:
            return
        if any(response.error is not None for response in results):
            return

        latest_time = max(candle.time for candle in latest_candles)
        if any(candle.time != latest_time for candle in latest_candles):
            return

        _, inserted = self.alert_store.save_notification_event_with_status(
            symbol=ALERT_BATCH_SYMBOL,
            candle_time=latest_time,
            event_type="alert_batch",
        )
        if not inserted:
            return

        alerts = self.alert_store.list_alerts_for_candle_time(latest_time)
        if alerts:
            self._send_alert_notifications(alerts)
        else:
            self._send_no_anomaly_notifications(latest_candles)

    def _send_daily_summary_if_market_closed(
        self, latest_candles: Sequence[Candle]
    ) -> None:
        monitored_count = len(self.settings.monitored_symbols())
        if len(latest_candles) < monitored_count:
            return

        latest_date = max(candle.time.date() for candle in latest_candles)
        if any(candle.time.date() != latest_date for candle in latest_candles):
            return
        if any(candle.time.time() < DAILY_SUMMARY_TIME for candle in latest_candles):
            return

        notified_at, inserted = self.alert_store.save_notification_event_with_status(
            symbol=DAILY_SUMMARY_SYMBOL,
            candle_time=datetime.combine(latest_date, DAILY_SUMMARY_TIME),
            event_type="daily_summary",
        )
        if not inserted:
            return

        alerts = _daily_summary_alerts(
            self.alert_store.list_alerts_for_date(latest_date)
        )
        try:
            self.notifier.send_daily_summary(
                latest_date,
                self.settings.monitored_symbols(),
                alerts,
                notified_at,
            )
        except Exception:
            logger.exception("failed to send daily summary notification")

    def _current_alert(
        self, symbol: str, latest_candle: Candle | None
    ) -> AlertLog | None:
        alert = self.alert_store.latest_alert(symbol)
        if alert is None or latest_candle is None:
            return None
        return alert if alert.candle_time == latest_candle.time else None


def _completed_candles(candles: list[Candle]) -> list[Candle]:
    now = datetime.now()
    completed: list[Candle] = []
    for candle in sorted(candles, key=lambda item: item.time):
        if candle.time <= now:
            completed.append(candle)
    return completed or sorted(candles, key=lambda item: item.time)


def _latest_trading_day_candles(candles: Sequence[Candle]) -> list[Candle]:
    ordered = sorted(candles, key=lambda item: item.time)
    if not ordered:
        return []
    latest_date = ordered[-1].time.date()
    return [candle for candle in ordered if candle.time.date() == latest_date]


def _snapshot_candles(candles: Sequence[Candle], settings: Settings) -> list[Candle]:
    latest_day_candles = _latest_trading_day_candles(candles)
    if not latest_day_candles:
        return []

    now = datetime.now(ZoneInfo(settings.timezone))
    latest_date = latest_day_candles[-1].time.date()
    if (
        latest_date == _previous_business_day(now.date())
        and now.weekday() < 5
        and now.time() < FIRST_COMPLETED_CANDLE_TIME
    ):
        return []
    return latest_day_candles


def _daily_summary_alerts(alerts: Sequence[AlertLog]) -> list[AlertLog]:
    return [
        alert
        for alert in alerts
        if alert.candle_time.time() not in DAILY_SUMMARY_EXCLUDED_ALERT_TIMES
    ]


def _previous_business_day(day: date) -> date:
    previous = day - timedelta(days=1)
    while previous.weekday() >= 5:
        previous -= timedelta(days=1)
    return previous
