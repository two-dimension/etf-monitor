"""Replace the 7/24 and 7/27 candle cache with all-5-minute rows so the detector
no longer mixes 15-min and 5-min K-lines on the same day.

Run from backend/:

    python scripts/replace_day_with_5min.py
"""

import logging
import sys
from datetime import date, datetime
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
logger = logging.getLogger("replace_5min")

TARGET_DATES = (date(2026, 7, 24), date(2026, 7, 27))


def _resolve_db_path() -> Path:
    project_root = BACKEND_DIR.parent
    raw_db_path = Path(Settings.model_fields["db_path"].default_factory())
    if raw_db_path.is_absolute():
        return raw_db_path
    return (project_root / raw_db_path).resolve()


def _fetch_all_day_5min(ak, normalized_symbol: str, sina: str):
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
    frame = ak.stock_zh_a_minute(symbol=sina, period="5", adjust="")
    if frame is None or getattr(frame, "empty", True):
        return None, None
    return frame, "stock"


def _row_to_candle(row, symbol: str, name: str) -> Candle:
    time_value = _first_present(row, ["时间", "日期", "datetime", "time", "day"])
    open_ = float(_first_present(row, ["开盘", "open"]))
    high = float(_first_present(row, ["最高", "high"]))
    low = float(_first_present(row, ["最低", "low"]))
    close = float(_first_present(row, ["收盘", "close"]))
    amount = float(_first_present(row, ["成交额", "amount"], default=0.0))
    volume = _normalized_volume(row, close, amount)
    parsed = time_value if isinstance(time_value, datetime) else datetime.fromisoformat(str(time_value))
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


def _delete_target_candles(store: AlertStore, target_dates) -> dict:
    if not target_dates:
        return {}
    placeholders = ",".join("?" for _ in target_dates)
    sql = (
        "DELETE FROM candles WHERE substr(candle_time, 1, 10) IN ("
        + placeholders + ")"
    )
    iso_dates = [d.isoformat() for d in target_dates]
    with store._connect() as conn:  # noqa: SLF001
        cursor = conn.execute(sql, iso_dates)
        deleted = cursor.rowcount
        conn.commit()
    logger.info("deleted %d existing candles for %s", deleted, iso_dates)
    return {d: 0 for d in target_dates}


def replace_symbol(store: AlertStore, settings: Settings, symbol: str) -> dict:
    import akshare as ak

    name = settings.name_for_symbol(symbol)
    normalized = normalize_symbol(symbol)
    sina = sina_symbol(symbol)
    logger.info("fetching all-day 5min for %s (%s) via sina=%s", symbol, name, sina)
    frame, source = _fetch_all_day_5min(ak, normalized, sina)
    if frame is None:
        return {"symbol": symbol, "status": "fetch_error"}

    candles_by_date: dict[date, list[Candle]] = {d: [] for d in TARGET_DATES}
    for row in frame.to_dict("records"):
        parsed = _first_present(row, ["时间", "日期", "datetime", "time", "day"])
        candle_time = parsed if isinstance(parsed, datetime) else datetime.fromisoformat(str(parsed))
        if candle_time.date() not in TARGET_DATES:
            continue
        candles_by_date[candle_time.date()].append(
            _row_to_candle(row, symbol, name)
        )

    summary = {"symbol": symbol, "source": source, "by_date": {}}
    for d, rows in candles_by_date.items():
        if not rows:
            summary["by_date"][d.isoformat()] = 0
            continue
        rows.sort(key=lambda c: c.time)
        store.upsert_candles(rows)
        summary["by_date"][d.isoformat()] = len(rows)
    logger.info("%s: %s", symbol, summary["by_date"])
    return summary


def main() -> int:
    settings = Settings()
    db_path = _resolve_db_path()
    store = AlertStore(db_path)

    _delete_target_candles(store, TARGET_DATES)

    summary = []
    for cfg in settings.monitored_symbols():
        summary.append(replace_symbol(store, settings, cfg.symbol))
    for entry in summary:
        logger.info("RESULT %s", entry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
