"""Diagnostic: dump alerts + notification_events for 2026-07-24 and 2026-07-27."""
from __future__ import annotations
from pathlib import Path
import sqlite3

BACKEND = Path(__file__).resolve().parents[1]
DB_PATH = (BACKEND / "data" / "etf_monitor.db").resolve()


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    print("=== alerts schema ===")
    for row in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='alerts'"
    ):
        print(row["sql"])
    print("\n=== alerts for 2026-07-24 / 2026-07-27 ===")
    for row in conn.execute(
        """
        SELECT id, symbol, name, alert_type, candle_time, volume, prev_volume, ratio,
               threshold, severity, created_at
        FROM alerts
        WHERE date(candle_time) IN ('2026-07-24','2026-07-27')
        ORDER BY candle_time, symbol
        """
    ):
        print(dict(row))
    print("\n=== latest notification_events ===")
    for row in conn.execute(
        """
        SELECT id, symbol, candle_time, event_type, created_at
        FROM notification_events
        ORDER BY created_at DESC
        LIMIT 30
        """
    ):
        print(dict(row))


if __name__ == "__main__":
    main()
