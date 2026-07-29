from __future__ import annotations

"""Re-send the daily-summary email for 2026-07-24 and 2026-07-27 to a single
recipient, without writing anything to ``notification_events`` (this is a
re-run, not a fresh poll-cycle notification).

Run from backend/:

    python scripts/resend_daily_summary.py
"""

import logging
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings  # noqa: E402
from app.notifier import SMTPAlertNotifier  # noqa: E402
from app.service import _daily_summary_alerts  # noqa: E402
from app.store import AlertStore  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("resend_summary")

TARGET_DATES = (date(2026, 7, 24), date(2026, 7, 27))
ONLY_RECIPIENT = "2357694165@qq.com"


def _resolve_db_path() -> Path:
    project_root = BACKEND_DIR.parent
    raw_db_path = Path(Settings.model_fields["db_path"].default_factory())
    if raw_db_path.is_absolute():
        return raw_db_path
    return (project_root / raw_db_path).resolve()


def _resolve_alerts(store: AlertStore, summary_date: date):
    raw_alerts = store.list_alerts_for_date(summary_date)
    return _daily_summary_alerts(raw_alerts)


def main() -> int:
    settings = Settings()
    db_path = _resolve_db_path()
    store = AlertStore(db_path)

    symbols = settings.monitored_symbols()
    monitored_ids = {cfg.symbol for cfg in symbols}

    original_smtp_to = settings.smtp_to
    settings.smtp_to = ONLY_RECIPIENT
    notifier = SMTPAlertNotifier(settings)

    timezone = ZoneInfo(settings.timezone)
    try:
        for summary_date in TARGET_DATES:
            alerts = [a for a in _resolve_alerts(store, summary_date) if a.symbol in monitored_ids]
            logger.info(
                "%s: %d alerts after dedupe, sending to %s",
                summary_date, len(alerts), ONLY_RECIPIENT,
            )
            notified_at = datetime.now(tz=timezone)
            notifier.send_daily_summary(
                summary_date=summary_date,
                symbols=symbols,
                alerts=alerts,
                notified_at=notified_at,
            )
            logger.info("%s: send_daily_summary returned", summary_date)
    finally:
        settings.smtp_to = original_smtp_to
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
