"""Dump the 588000.SH candles around 14:30-15:00 on 7/27 and the corresponding
alert row to figure out where the volume mismatch comes from."""
from __future__ import annotations
from pathlib import Path
import sqlite3

BACKEND = Path(__file__).resolve().parents[1]
DB_PATH = (BACKEND / "data" / "etf_monitor.db").resolve()


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    print("=== 588000.SH candles 13:00-15:05 on 7/27 ===")
    for r in conn.execute(
        """
        SELECT candle_time, volume FROM candles
        WHERE symbol='588000.SH' AND substr(candle_time,1,10)='2026-07-27'
          AND time(candle_time) >= '13:00:00' AND time(candle_time) <= '15:05:00'
        ORDER BY candle_time
        """
    ):
        print(f"  {r['candle_time']}  vol={r['volume']:>14,}")
    print()
    print("=== alert 14:35 raw row ===")
    for r in conn.execute(
        """
        SELECT * FROM alerts
        WHERE symbol='588000.SH' AND substr(candle_time,1,10)='2026-07-27'
          AND time(candle_time)='14:35:00'
        """
    ):
        for k in r.keys():
            print(f"  {k}: {r[k]}")


if __name__ == "__main__":
    main()
