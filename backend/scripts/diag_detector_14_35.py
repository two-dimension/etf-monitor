"""Trace what the detector actually sees for 7/27 14:35 to figure out where the
prev_volume=9,060,000 came from."""
from __future__ import annotations
from datetime import date, time
from pathlib import Path
import sqlite3

BACKEND = Path(__file__).resolve().parents[1]
sys_path_insert = str(BACKEND)
import sys
if sys_path_insert not in sys.path:
    sys.path.insert(0, sys_path_insert)

from app.config import Settings  # noqa: E402
from app.detector import detect_volume_spike  # noqa: E402
from app.store import AlertStore  # noqa: E402


def main() -> None:
    settings = Settings()
    db_path = BACKEND / "data" / "etf_monitor.db"
    store = AlertStore(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    print("=== raw candles for 588000.SH 7/27 from DB ===")
    for r in conn.execute(
        """
        SELECT candle_time, volume FROM candles
        WHERE symbol='588000.SH' AND substr(candle_time,1,10)='2026-07-27'
        ORDER BY candle_time
        """
    ):
        print(f"  {r['candle_time']}  vol={r['volume']:>14,}")

    print("\n=== alert 14:35 row ===")
    for r in conn.execute(
        """
        SELECT * FROM alerts
        WHERE symbol='588000.SH' AND candle_time='2026-07-27T14:35:00'
        """
    ):
        for k in r.keys():
            print(f"  {k}: {r[k]}")

    print("\n=== running detect_volume_spike for 14:35 manually ===")
    candles = store.list_candles("588000.SH", limit=5000)
    print(f"loaded {len(candles)} candles")
    alert = detect_volume_spike(candles, settings)
    if alert:
        print(
            f"  current={alert.candle_time:%H:%M} vol={alert.volume} "
            f"prev_vol={alert.prev_volume} ratio={alert.ratio} "
            f"severity={alert.severity}"
        )
    else:
        print("  no alert")


if __name__ == "__main__":
    main()
