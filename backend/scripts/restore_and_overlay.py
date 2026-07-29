"""Restore 7/24 and 7/27 candles to 15-min granularity, then overlay 5-min rows
only for the 14:30-15:00 late-session window so the morning/afternoon data
stays untouched.

Run from backend/:

    python scripts/restore_and_overlay.py
"""

import logging
import sys
from datetime import date, datetime, time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings  # noqa: E402
from app.market_data import (  # noqa: E402
    _normalized_volume,
    _first_present,
    normalize_symbol,
    sina_symbol,
)
from app.models import Candle  # noqa: E402
from app.store import AlertStore  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("restore_overlay")

TARGET_DATES = (date(2026, 7, 24), date(2026, 7, 27))
LATE_WINDOW_START = time(14, 30)
LATE_WINDOW_END = time(15, 0)  # inclusive


def _resolve_db_path() -> Path:
    project_root = BACKEND_DIR.parent
    raw_db_path = Path(Settings.model_fields["db_path"].default_factory())
    if raw_db_path.is_absolute():
        return raw_db_path
    return (project_root / raw_db_path).resolve()


def _row_to_candle(row, symbol: str, name: str) -> Candle:
    time_value = _first_present(row, ["时间", "日期", "datetime", "time", "day"])
    parsed = time_value if isinstance(time_value, datetime) else datetime.fromisoformat(str(time_value))
    open_ = float(_first_present(row, ["开盘", "open"]))
    high = float(_first_present(row, ["最高", "high"]))
    low = float(_first_present(row, ["最低", "low"]))
    close = float(_first_present(row, ["收盘", "close"]))
    amount = float(_first_present(row, ["成交额", "amount"], default=0.0))
    volume = _normalized_volume(row, close, amount)
    return Candle(
        symbol=symbol,
        name=name,
        time=parsed,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=amount,
    )


def _fetch_frame(ak, normalized_symbol: str, sina: str, period: str):
    """Prefer the fund endpoint; fall back to the stock minute endpoint."""
    try:
        frame = ak.fund_etf_hist_min_em(
            symbol=normalized_symbol, period=period, adjust=""
        )
    except Exception:
        logger.warning("fund_etf_hist_min_em failed for %s, falling back", sina)
        frame = None
    if frame is not None and not getattr(frame, "empty", True):
        return frame, "fund"
    frame = ak.stock_zh_a_minute(symbol=sina, period=period, adjust="")
    if frame is None or getattr(frame, "empty", True):
        return None, None
    return frame, "stock"


def _candles_for_window(frame, period: str) -> dict[date, list[Candle]]:
    """Group rows into per-date lists, filtered by period-specific window."""
    by_date: dict[date, list[Candle]] = {d: [] for d in TARGET_DATES}
    for row in frame.to_dict("records"):
        parsed = _first_present(row, ["时间", "日期", "datetime", "time", "day"])
        candle_time = parsed if isinstance(parsed, datetime) else datetime.fromisoformat(str(parsed))
        if candle_time.date() not in TARGET_DATES:
            continue
        # ``symbol`` and ``name`` are filled in by the caller via _row_to_candle wrapper.
        by_date[candle_time.date()].append((candle_time, row))
    return by_date


def _delete_target_candles(store: AlertStore) -> int:
    placeholders = ",".join("?" for _ in TARGET_DATES)
    sql = (
        "DELETE FROM candles WHERE substr(candle_time, 1, 10) IN ("
        + placeholders + ")"
    )
    iso_dates = [d.isoformat() for d in TARGET_DATES]
    with store._connect() as conn:  # noqa: SLF001
        cursor = conn.execute(sql, iso_dates)
        deleted = cursor.rowcount
        conn.commit()
    logger.info("deleted %d existing candles for %s", deleted, iso_dates)
    return deleted


def restore_symbol(store: AlertStore, settings: Settings, symbol: str) -> dict:
    import akshare as ak

    name = settings.name_for_symbol(symbol)
    normalized = normalize_symbol(symbol)
    sina = sina_symbol(symbol)
    summary = {"symbol": symbol, "by_date": {}}

    # Step 1: 15-min for the full day.
    frame, source = _fetch_frame(ak, normalized, sina, "15")
    if frame is None:
        return {"symbol": symbol, "status": "fetch_error"}
    by_date = _candles_for_window(frame, "15")
    for d, rows in by_date.items():
        rows.sort(key=lambda item: item[0])
        candles = [_row_to_candle(row, symbol, name) for _, row in rows]
        if candles:
            store.upsert_candles(candles)
        summary["by_date"][d.isoformat()] = {"15min": len(candles), "5min_late": 0}
    logger.info("%s 15min upserted: %s (source=%s)", symbol, summary["by_date"], source)

    # Step 2: 5-min only for 14:30-15:00, which overwrites the matching 15-min rows.
    frame, source = _fetch_frame(ak, normalized, sina, "5")
    if frame is None:
        return {"symbol": symbol, "status": "fetch_error_5min"}
    by_date = _candles_for_window(frame, "5")
    for d, rows in by_date.items():
        late_rows = [
            (parsed, row)
            for parsed, row in rows
            if LATE_WINDOW_START <= parsed.time() <= LATE_WINDOW_END
        ]
        late_rows.sort(key=lambda item: item[0])
        candles = [_row_to_candle(row, symbol, name) for _, row in late_rows]
        if candles:
            store.upsert_candles(candles)
        summary["by_date"][d.isoformat()]["5min_late"] = len(candles)
    logger.info("%s 5min late-window overlay: %s", symbol, summary["by_date"])
    return summary


def main() -> int:
    settings = Settings()
    db_path = _resolve_db_path()
    store = AlertStore(db_path)

    _delete_target_candles(store)

    summary = [restore_symbol(store, settings, cfg.symbol) for cfg in settings.monitored_symbols()]
    for entry in summary:
        logger.info("RESULT %s", entry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
