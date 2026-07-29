"""Clean reset: drop 7/24+7/27 alerts, re-run detection, verify, and email.

This avoids the stale-alert trap from earlier runs by issuing explicit
DELETE+INSERT and using the ``is_completed`` flag instead of relying on
upsert-side-effects.

Run from backend/:

    python scripts/clean_rerun.py
"""

from __future__ import annotations

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
from app.detector import detect_volume_spike  # noqa: E402
from app.models import AlertCreate  # noqa: E402
from app.notifier import SMTPAlertNotifier  # noqa: E402
from app.service import _daily_summary_alerts  # noqa: E402
from app.store import AlertStore  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("clean_rerun")

TARGET_DATES = (date(2026, 7, 24), date(2026, 7, 27))
ONLY_RECIPIENT = "2357694165@qq.com"


def _resolve_db_path() -> Path:
    project_root = BACKEND_DIR.parent
    raw = Path(Settings.model_fields["db_path"].default_factory())
    return raw if raw.is_absolute() else (project_root / raw).resolve()


def _delete_alerts(store: AlertStore, target_dates: Iterable[date]) -> int:
    placeholders = ",".join("?" for _ in target_dates)
    sql = (
        "DELETE FROM alerts WHERE substr(candle_time, 1, 10) IN ("
        + placeholders + ")"
    )
    iso_dates = [d.isoformat() for d in target_dates]
    with store._connect() as conn:  # noqa: SLF001
        cur = conn.execute(sql, iso_dates)
        deleted = cur.rowcount
        conn.commit()
    logger.info("deleted %d stale alerts for %s", deleted, iso_dates)
    return deleted


def _alert_from_create(alert: AlertCreate, name: str) -> tuple[int, int, float]:
    # Build a plain INSERT that uses ON CONFLICT REPLACE so the value we computed
    # wins, regardless of any stale alert sitting under (symbol, candle_time).
    return alert.candle_time.hour, alert.candle_time.minute, alert.ratio


def _upsert_alert(store: AlertStore, alert: AlertCreate, name: str) -> None:
    """Insert (or replace) the alert row using values the detector just produced.

    Bypasses AlertStore.save_alert_with_status because that path uses
    INSERT OR IGNORE and can keep stale rows whose volume/prev_volume do not
    match the live candles table.
    """
    sql = (
        "INSERT OR REPLACE INTO alerts ("
        "symbol, name, alert_type, candle_time, volume, prev_volume, ratio,"
        " threshold, severity, message"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    params = (
        alert.symbol,
        name,
        alert.alert_type,
        alert.candle_time.isoformat(),
        alert.volume,
        alert.prev_volume,
        alert.ratio,
        alert.threshold,
        alert.severity,
        alert.message,
    )
    with store._connect() as conn:  # noqa: SLF001
        conn.execute(sql, params)
        conn.commit()


def _run_detection_for_date(
    store: AlertStore,
    settings: Settings,
    summary_date: date,
    candles,
) -> int:
    """Run the detector end-to-end for one day and persist alerts via REPLACE."""
    prior = sorted(
        [c for c in candles if c.time.date() < summary_date], key=lambda c: c.time
    )
    day = sorted(
        [c for c in candles if c.time.date() == summary_date], key=lambda c: c.time
    )
    logger.info(
        "%s: day=%d prior=%d",
        summary_date.isoformat(), len(day), len(prior),
    )
    inserted = 0
    for end_index in range(1, len(day) + 1):
        slice_ = day[:end_index]
        alert = detect_volume_spike(prior + slice_, settings)
        if alert is None:
            continue
        name = settings.name_for_symbol(alert.symbol)
        _upsert_alert(store, alert, name)
        inserted += 1
    logger.info("%s: wrote %d alerts", summary_date.isoformat(), inserted)
    return inserted


def main() -> int:
    settings = Settings()
    db_path = _resolve_db_path()
    store = AlertStore(db_path)

    _delete_alerts(store, TARGET_DATES)

    symbols = settings.monitored_symbols()
    symbol_list = [cfg.symbol for cfg in symbols]

    all_candles = []
    for symbol in symbol_list:
        all_candles.extend(store.list_candles(symbol, limit=50000))
    logger.info(
        "loaded %d candles across %d symbols",
        len(all_candles), len(symbol_list),
    )

    for d in TARGET_DATES:
        _run_detection_for_date(store, settings, d, all_candles)

    original_smtp_to = settings.smtp_to
    settings.smtp_to = ONLY_RECIPIENT
    notifier = SMTPAlertNotifier(settings)
    try:
        for summary_date in TARGET_DATES:
            alerts = _daily_summary_alerts(
                store.list_alerts_for_date(summary_date)
            )
            logger.info(
                "%s: %d alerts after dedupe, sending to %s",
                summary_date.isoformat(), len(alerts), ONLY_RECIPIENT,
            )
            notifier.send_daily_summary(
                summary_date=summary_date,
                symbols=symbols,
                alerts=alerts,
                notified_at=datetime.now(tz=ZoneInfo(settings.timezone)),
            )
            logger.info("%s: send_daily_summary returned", summary_date.isoformat())
    finally:
        settings.smtp_to = original_smtp_to
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
