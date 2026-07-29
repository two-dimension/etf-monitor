from __future__ import annotations

"""Re-run volume-spike detection for 2026-07-24 and 2026-07-27 against the now
complete 5-minute K-line cache, then send a daily-summary email to a single
recipient so the operator can review the fresh results.

Behavior:
* Wipes the existing alerts for the two target dates so stale 15-min-derived
  rows are replaced with detection output computed on the 5-minute candles.
* Calls ``MonitorService._detect_and_save`` for each monitored symbol so the
  severity/threshold/message fields match the current detector implementation.
* Sends a single daily-summary email per date to ``ONLY_RECIPIENT`` without
  writing to ``notification_events`` (this is a one-shot review, not a poll).

Run from backend/:

    python scripts/rerun_detection.py
"""

import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings  # noqa: E402
from app.market_data import AkShareMarketDataClient  # noqa: E402
from app.models import Candle  # noqa: E402
from app.notifier import SMTPAlertNotifier  # noqa: E402
from app.service import MonitorService, _daily_summary_alerts  # noqa: E402
from app.store import AlertStore  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("rerun_detection")

TARGET_DATES: tuple[date, ...] = (date(2026, 7, 24), date(2026, 7, 27))
ONLY_RECIPIENT = "2357694165@qq.com"


def _resolve_db_path() -> Path:
    project_root = BACKEND_DIR.parent
    raw_db_path = Path(Settings.model_fields["db_path"].default_factory())
    if raw_db_path.is_absolute():
        return raw_db_path
    return (project_root / raw_db_path).resolve()


def _load_candles(store: AlertStore, symbols: Iterable[str]) -> list[Candle]:
    out: list[Candle] = []
    for symbol in symbols:
        out.extend(store.list_candles(symbol, limit=5000))
    return out


def _clear_alerts_for_dates(store: AlertStore, target_dates: Iterable[date]) -> None:
    target_dates = list(target_dates)
    if not target_dates:
        return
    placeholders = ",".join("?" * len(target_dates))
    sql = (
        "DELETE FROM alerts "
        "WHERE substr(candle_time, 1, 10) IN ("
        + ",".join(
            "?" for _ in target_dates
        )
        + ")"
    )
    iso_dates = [d.isoformat() for d in target_dates]
    with store._connect() as conn:  # noqa: SLF001
        cursor = conn.execute(sql, iso_dates)
        logger.info("cleared %d stale alerts for %s", cursor.rowcount, iso_dates)
        conn.commit()


def main() -> int:
    settings = Settings()
    db_path = _resolve_db_path()
    store = AlertStore(db_path)
    market_client = AkShareMarketDataClient(settings)
    service = MonitorService(
        settings=settings,
        market_data_client=market_client,
        db_path=db_path,
        notifier=NoopNotifier(),
    )

    symbols = settings.monitored_symbols()
    symbol_list = [cfg.symbol for cfg in symbols]

    _clear_alerts_for_dates(store, TARGET_DATES)

    candles = _load_candles(store, symbol_list)
    logger.info("loaded %d candles across %d symbols", len(candles), len(symbol_list))

    for summary_date in TARGET_DATES:
        prior_candles = [c for c in candles if c.time.date() < summary_date]
        day_candles = [c for c in candles if c.time.date() == summary_date]
        logger.info(
            "%s: running detection on %d day candles (+%d historical)",
            summary_date.isoformat(), len(day_candles), len(prior_candles),
        )
        service._detect_and_save(  # noqa: SLF001
            prior_candles + day_candles,
            notify_no_anomaly=False,
            send_notifications=False,
        )

    original_smtp_to = settings.smtp_to
    settings.smtp_to = ONLY_RECIPIENT
    notifier = SMTPAlertNotifier(settings)
    timezone = ZoneInfo(settings.timezone)
    try:
        for summary_date in TARGET_DATES:
            alerts = _daily_summary_alerts(store.list_alerts_for_date(summary_date))
            logger.info(
                "%s: %d alerts after dedupe, sending to %s",
                summary_date.isoformat(), len(alerts), ONLY_RECIPIENT,
            )
            notified_at = datetime.now(tz=timezone)
            notifier.send_daily_summary(
                summary_date=summary_date,
                symbols=symbols,
                alerts=alerts,
                notified_at=notified_at,
            )
            logger.info("%s: send_daily_summary returned", summary_date.isoformat())
    finally:
        settings.smtp_to = original_smtp_to
    return 0


class NoopNotifier:
    def send_alert(self, alert):  # pragma: no cover - never invoked
        return None

    def send_alerts(self, alerts):
        return None

    def send_no_anomaly(self, candle, notified_at):
        return None

    def send_no_anomalies(self, candles, notified_at):
        return None

    def send_daily_summary(self, summary_date, symbols, alerts, notified_at):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
