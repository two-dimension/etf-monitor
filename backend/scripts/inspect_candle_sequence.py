"""Diagnostic: print the full candle sequence for one symbol on a target day so we
can see exactly which rows are 15-min and which are 5-min, and confirm the
mixing the user reported."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import sqlite3

BACKEND = Path(__file__).resolve().parents[1]
DB_PATH = (BACKEND / "data" / "etf_monitor.db").resolve()


def main() -> None:
    target_symbol = "588000.SH"
    target_date = date(2026, 7, 27)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT candle_time, open, high, low, close, volume, amount
        FROM candles
        WHERE symbol = ? AND substr(candle_time, 1, 10) = ?
        ORDER BY candle_time
        """,
        (target_symbol, target_date.isoformat()),
    ).fetchall()
    print(f"=== {target_symbol} on {target_date.isoformat()} ({len(rows)} candles) ===")
    for r in rows:
        h, m = r["candle_time"][11:16].split(":")
        delta_to_next = ""
        if int(h) == 14 and int(m) >= 30:
            delta_to_next = "  <-- late-session (5-min expected)"
        elif int(h) == 13 and int(m) == 30:
            delta_to_next = "  <-- afternoon boundary"
        print(
            f"  {r['candle_time'][11:16]}  vol={r['volume']:>12,}{delta_to_next}"
        )


if __name__ == "__main__":
    main()
