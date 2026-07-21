from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Sequence

from app.config import Settings
from app.detector import detect_volume_spike
from app.market_data import MarketDataClient
from app.models import AlertLog, Candle, DataStatus, MonitorSnapshot, PollResponse, SymbolInfo
from app.notifier import AlertNotifier, NoopAlertNotifier
from app.store import AlertStore


logger = logging.getLogger(__name__)


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
        try:
            candles = self._fetch_live_candles(requested_symbol)
            self.candle_cache.upsert_candles(candles)
            latest_day_candles = _latest_trading_day_candles(candles)
            self.last_error = None
            self.last_status = "live" if latest_day_candles else "empty"
            alert = self._detect_and_save(latest_day_candles)
            return PollResponse(
                symbol=requested_symbol,
                data_status=self.last_status,
                candle_count=len(latest_day_candles),
                alert=alert,
            )
        except Exception as exc:
            cached = self.candle_cache.list_candles(requested_symbol)
            latest_day_cached = _latest_trading_day_candles(cached)
            self.last_error = str(exc)
            self.last_status = "cached" if latest_day_cached else "degraded"
            alert = self._detect_and_save(latest_day_cached) if latest_day_cached else None
            return PollResponse(
                symbol=requested_symbol,
                data_status=self.last_status,
                candle_count=len(latest_day_cached),
                alert=alert,
                error=str(exc),
            )

    def poll_all(self) -> list[PollResponse]:
        return [self.poll(item.symbol) for item in self.settings.monitored_symbols()]

    def snapshot(self, symbol: str | None = None) -> MonitorSnapshot:
        requested_symbol = symbol or self.settings.symbol
        try:
            candles = self._fetch_live_candles(requested_symbol)
            self.candle_cache.upsert_candles(candles)
            candles = _latest_trading_day_candles(candles)
            self.last_error = None
            data_status: DataStatus = "live" if candles else "empty"
        except Exception as exc:
            candles = self.candle_cache.list_candles(requested_symbol)
            candles = _latest_trading_day_candles(candles)
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

    def list_alerts(self, symbol: str | None = None, limit: int = 100) -> list[AlertLog]:
        requested_symbol = symbol or self.settings.symbol
        return self.alert_store.list_alerts(requested_symbol, limit=max(1, min(limit, 500)))

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

    def _detect_and_save(self, candles: Sequence[Candle]) -> AlertLog | None:
        ordered = sorted(candles, key=lambda item: item.time)
        latest_inserted_alert: AlertLog | None = None
        for end_index in range(2, len(ordered) + 1):
            alert = detect_volume_spike(ordered[:end_index], self.settings)
            if alert is None:
                continue
            saved_alert, inserted = self.alert_store.save_alert_with_status(alert)
            if inserted:
                self._send_alert_notification(saved_alert)
                latest_inserted_alert = saved_alert
        return latest_inserted_alert

    def _send_alert_notification(self, alert: AlertLog) -> None:
        try:
            self.notifier.send_alert(alert)
        except Exception:
            logger.exception("failed to send alert notification")

    def _current_alert(self, symbol: str, latest_candle: Candle | None) -> AlertLog | None:
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
