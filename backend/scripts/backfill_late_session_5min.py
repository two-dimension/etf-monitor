from __future__ import annotations

"""One-shot backfill for the 14:30-15:00 5-minute K-line window.

Picks up where the live poller left off: 7/24 and 7/27 late-session candles
were only ever persisted at the 15-minute granularity, so the 14:35/14:40/14:50/
14:55 slots and finer-grained 14:30/14:45/15:00 prints are missing.

Mirrors the production fallback chain: prefer ``fund_etf_hist_min_em`` and fall
back to ``stock_zh_a_minute`` so this script keeps working when East Money
rate-limits the ETF endpoint.

Run from the backend/ directory so the relative DB_PATH resolves:

    cd backend
    python scripts/backfill_late_session_5min.py
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
logger = logging.getLogger("backfill_5min")

WINDOW_START = time(14, 30)
WINDOW_END = time(15, 0)  # inclusive upper bound for the 15:00 slot
TARGET_DATES = (date(2026, 7, 24), date(2026, 7, 27))


def _fetch_5min_frame(ak, normalized_symbol: str, sina: str):
    """Try the ETF endpoint first, then fall back to the A-share minute endpoint."""
    try:
        frame = ak.fund_etf_hist_min_em(
            symbol=normalized_symbol,
            period="5",
            adjust="",
        )
    except Exception:
        logger.warning("fund_etf_hist_min_em failed for %s, falling back", sina)
        frame = None
    if frame is not None and not getattr(frame, "empty", True):
        return frame, "fund"
    try:
        frame = ak.stock_zh_a_minute(symbol=sina, period="5", adjust="")
    except Exception:
        logger.exception("stock_zh_a_minute failed for %s", sina)
        return None, None
    if frame is None or getattr(frame, "empty", True):
        return None, None
    return frame, "stock"


def _parse_time(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _row_to_candle(row, symbol: str, name: str) -> Candle:
    time_value = _first_present(row, ["时间", "日期", "datetime", "time", "day"])
    open_ = float(_first_present(row, ["开盘", "open"]))
    high = float(_first_present(row, ["最高", "high"]))
    low = float(_first_present(row, ["最低", "low"]))
    close = float(_first_present(row, ["收盘", "close"]))
    amount = float(_first_present(row, ["成交额", "amount"], default=0.0))
    volume = _normalized_volume(row, close, amount)
    return Candle(
        symbol=symbol,
        name=name,
        time=_parse_time(time_value),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=amount,
    )


def _filter_window(rows):
    """Keep only rows whose time falls inside the late-session window on a target date."""
    kept = []
    for row in rows:
        parsed = _parse_time(_first_present(row, ["时间", "日期", "datetime", "time", "day"]))
        if parsed.date() not in TARGET_DATES:
            continue
        t = parsed.time()
        if t < WINDOW_START or t > WINDOW_END:
            continue
        kept.append((parsed, row))
    return kept


def backfill_symbol(store: AlertStore, settings: Settings, symbol: str) -> dict:
    import akshare as ak  # imported lazily so missing optional deps fail loudly per symbol

    name = settings.name_for_symbol(symbol)
    normalized = normalize_symbol(symbol)
    sina = sina_symbol(symbol)
    logger.info("fetching 5min K-line for %s (%s) via sina=%s", symbol, name, sina)
    frame, source = _fetch_5min_frame(ak, normalized, sina)
    if frame is None:
        return {"symbol": symbol, "status": "fetch_error"}

    rows = list(frame.to_dict("records"))
    window_rows = _filter_window(rows)
    if not window_rows:
        logger.warning("no rows inside window for %s", symbol)
        return {"symbol": symbol, "status": "no_window_rows", "source": source}

    candles = [_row_to_candle(row, symbol, name) for _, row in window_rows]
    store.upsert_candles(candles)

    by_date = {}
    for candle in candles:
        by_date.setdefault(candle.time.date().isoformat(), []).append(
            candle.time.strftime("%H:%M")
        )
    logger.info(
        "upserted %d candles for %s (source=%s) -> %s",
        len(candles), symbol, source, by_date,
    )
    return {
        "symbol": symbol,
        "status": "ok",
        "source": source,
        "count": len(candles),
        "by_date": by_date,
    }


def main() -> int:
    # The configured DB_PATH may be relative (default ``backend/data/etf_monitor.db``);
    # resolve it against the project root so we always land in the real DB instead
    # of accidentally creating ``backend/backend/data/etf_monitor.db``.
    project_root = BACKEND_DIR.parent
    raw_db_path = Path(Settings.model_fields["db_path"].default_factory())
    settings = Settings()
    db_path = raw_db_path if raw_db_path.is_absolute() else (project_root / raw_db_path).resolve()
    store = AlertStore(db_path)
    # Backfill both the configured monitored symbols and any other ETFs the
    # dashboard has already cached, so we never miss a row the user expects to
    # see in the UI.
    with store._connect() as connection:  # noqa: SLF001
        rows = connection.execute(
            "SELECT DISTINCT symbol, name FROM candles"
        ).fetchall()
    db_symbols = {row["symbol"]: row["name"] for row in rows}
    monitored = {cfg.symbol: cfg.name for cfg in settings.monitored_symbols()}
    ordered = list(monitored.items()) + [
        (symbol, name)
        for symbol, name in sorted(db_symbols.items())
        if symbol not in monitored
    ]
    summary = [backfill_symbol(store, settings, symbol) for symbol, _ in ordered]
    for entry in summary:
        logger.info("RESULT %s", entry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
