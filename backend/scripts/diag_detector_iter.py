"""Trace what detector iterates for 7/27 14:35 and 14:30, and what alert values
are produced at each step."""
from __future__ import annotations
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402
from app.detector import detect_volume_spike  # noqa: E402
from app.store import AlertStore  # noqa: E402
from datetime import date


def main() -> None:
    settings = Settings()
    store = AlertStore(BACKEND / "data" / "etf_monitor.db")

    all_candles = store.list_candles("588000.SH", limit=5000)
    target = date(2026, 7, 27)
    day = sorted([c for c in all_candles if c.time.date() == target], key=lambda c: c.time)
    print(f"loaded {len(day)} candles for 7/27 (sorted)")
    for c in day:
        print(f"  {c.time:%H:%M}  vol={c.volume:>14,}")

    prior = sorted([c for c in all_candles if c.time.date() < target], key=lambda c: c.time)
    print(f"\nprior {len(prior)} candles")

    print("\n--- detector iterations ---")
    for end_index in range(1, len(day) + 1):
        slice_ = day[:end_index]
        alert = detect_volume_spike(prior + slice_, settings)
        if alert is None:
            continue
        cur = slice_[-1]
        prev_pos = end_index - 2
        prev = slice_[prev_pos] if prev_pos >= 0 else None
        print(
            f"  iter={end_index:2d} current={cur.time:%H:%M} "
            f"vol={cur.volume:>14,} prev={prev.time:%H:%M} "
            f"vol={prev.volume:>14,} ratio={alert.ratio} thr={alert.threshold} {alert.severity}"
        )


if __name__ == "__main__":
    main()
