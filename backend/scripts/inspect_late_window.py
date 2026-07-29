"""Diagnostic: print 14:30-15:00 coverage for the two candidate DB files so we can
see where the backfill actually landed."""
from __future__ import annotations
from pathlib import Path
import sqlite3

BACKEND = Path(__file__).resolve().parents[1]
CANDIDATES = [
    ("outer", BACKEND / "data" / "etf_monitor.db"),
    ("inner", BACKEND / "backend" / "data" / "etf_monitor.db"),
]


def inspect(label: str, path: Path) -> None:
    print(f"=== {label} {path} exists={path.exists()} size={path.stat().st_size if path.exists() else 0} ===")
    if not path.exists():
        return
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        symbols = [dict(r) for r in conn.execute(
            "SELECT DISTINCT symbol, name FROM candles ORDER BY symbol"
        )]
        print("symbols:", symbols)
        for row in conn.execute(
            """
            SELECT symbol, date(candle_time) AS d, GROUP_CONCAT(time(candle_time), ',') AS times
            FROM candles
            WHERE date(candle_time) IN ('2026-07-24','2026-07-27')
              AND time(candle_time) >= '14:30:00' AND time(candle_time) <= '15:00:00'
            GROUP BY symbol, d
            ORDER BY symbol, d
            """
        ):
            times = row["times"].split(",") if row["times"] else []
            print("  %-10s %s (%d candles) %s" % (row["symbol"], row["d"], len(times), times))
    finally:
        conn.close()


if __name__ == "__main__":
    for label, path in CANDIDATES:
        inspect(label, path)
