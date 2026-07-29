from __future__ import annotations
from pathlib import Path
import sqlite3

BACKEND = Path(__file__).resolve().parents[1]
DB_PATH = (BACKEND / "data" / "etf_monitor.db").resolve()


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    print("=== alerts on 2026-07-24 (raw, incl. 9:45) ===")
    for r in conn.execute(
        """
        SELECT candle_time, symbol, alert_type, ratio, threshold, severity
        FROM alerts
        WHERE substr(candle_time,1,10)='2026-07-24'
        ORDER BY candle_time, symbol
        """
    ):
        print(
            f'  {r["candle_time"][11:16]} {r["symbol"]} '
            f'type={r["alert_type"]} ratio={r["ratio"]} thr={r["threshold"]} {r["severity"]}'
        )
    print("\n=== alerts on 2026-07-27 (raw, incl. 9:45) ===")
    for r in conn.execute(
        """
        SELECT candle_time, symbol, alert_type, ratio, threshold, severity
        FROM alerts
        WHERE substr(candle_time,1,10)='2026-07-27'
        ORDER BY candle_time, symbol
        """
    ):
        print(
            f'  {r["candle_time"][11:16]} {r["symbol"]} '
            f'type={r["alert_type"]} ratio={r["ratio"]} thr={r["threshold"]} {r["severity"]}'
        )


if __name__ == "__main__":
    main()
