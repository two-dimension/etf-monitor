from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Protocol

from app.config import Settings
from app.models import Candle


TIME_COLUMNS = ["时间", "日期", "datetime", "time", "day"]
OPEN_COLUMNS = ["开盘", "open"]
HIGH_COLUMNS = ["最高", "high"]
LOW_COLUMNS = ["最低", "low"]
CLOSE_COLUMNS = ["收盘", "close"]
VOLUME_COLUMNS = ["成交量", "volume"]
AMOUNT_COLUMNS = ["成交额", "amount"]


class MarketDataClient(Protocol):
    def fetch_intraday_candles(self, symbol: str) -> list[Candle]:
        ...


class AkShareMarketDataClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch_intraday_candles(self, symbol: str) -> list[Candle]:
        import akshare as ak

        normalized_symbol = normalize_symbol(symbol)
        sina = sina_symbol(symbol)

        now = datetime.now(ZoneInfo(self.settings.timezone))
        main_frame = _safe_fetch_frame(ak, normalized_symbol, sina, self.settings.kline_period)
        frames = []
        if main_frame is not None:
            if self.settings.is_late_session(now):
                frames.append(
                    (
                        _filter_frame_by_time(
                            main_frame, end_at=self.settings.late_session_start_time
                        ),
                        self.settings.kline_period,
                    )
                )
            else:
                frames.append((main_frame, self.settings.kline_period))

        if self.settings.is_late_session(now):
            late_frame = _safe_fetch_frame(
                ak,
                normalized_symbol,
                sina,
                self.settings.late_session_kline_period,
            )
            if late_frame is not None:
                frames.append(
                    (
                        _filter_frame_by_time(
                            late_frame,
                            start_at=self.settings.late_session_start_time,
                            end_at=time(15, 0),
                        ),
                        self.settings.late_session_kline_period,
                    )
                )

        if not frames:
            return []

        candles: list[Candle] = []
        for frame, period in frames:
            if frame is None or frame.empty:
                continue
            for _, row in frame.iterrows():
                time_value = _first_present(row, TIME_COLUMNS)
                close = float(_first_present(row, CLOSE_COLUMNS))
                amount = float(_first_present(row, AMOUNT_COLUMNS, default=0.0))
                candles.append(
                    Candle(
                        symbol=symbol,
                        name=self.settings.name_for_symbol(symbol),
                        time=_parse_time(time_value),
                        open=float(_first_present(row, OPEN_COLUMNS)),
                        high=float(_first_present(row, HIGH_COLUMNS)),
                        low=float(_first_present(row, LOW_COLUMNS)),
                        close=close,
                        volume=_normalized_volume(row, close, amount),
                        amount=amount,
                        kline_period=period,
                    )
                )
        return sorted(candles, key=lambda item: (item.time, int(item.kline_period)))


def normalize_symbol(symbol: str) -> str:
    return symbol.split(".")[0]


def sina_symbol(symbol: str) -> str:
    code = normalize_symbol(symbol)
    suffix = symbol.split(".")[-1].upper() if "." in symbol else ""
    if suffix == "SH" or code.startswith(("5", "6", "9")):
        return f"sh{code}"
    return f"sz{code}"


def _first_present(row, names: list[str], default=None):
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    if default is not None:
        return default
    raise KeyError(f"missing any of columns: {', '.join(names)}")


def _normalized_volume(row, close: float, amount: float) -> int:
    volume = int(float(_first_present(row, VOLUME_COLUMNS)))
    if volume <= 0 or close <= 0 or amount <= 0:
        return volume

    implied_multiplier = amount / (close * volume)
    if 50 <= implied_multiplier <= 150:
        return volume * 100
    return volume


def _parse_time(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _filter_frame_by_time(
    frame,
    start_at: time | None = None,
    start_after: time | None = None,
    end_at: time | None = None,
    end_before: time | None = None,
):
    keep = []
    for _, row in frame.iterrows():
        candle_time = _parse_time(_first_present(row, TIME_COLUMNS)).time()
        if start_at is not None and candle_time < start_at:
            keep.append(False)
            continue
        if start_after is not None and candle_time <= start_after:
            keep.append(False)
            continue
        if end_at is not None and candle_time > end_at:
            keep.append(False)
            continue
        if end_before is not None and candle_time >= end_before:
            keep.append(False)
            continue
        keep.append(True)
    return frame.loc[keep]


def _safe_fetch_frame(ak, normalized_symbol: str, sina: str, period: str):
    try:
        frame = ak.fund_etf_hist_min_em(
            symbol=normalized_symbol,
            period=period,
            adjust="",
        )
    except Exception:
        try:
            frame = ak.stock_zh_a_minute(
                symbol=sina,
                period=period,
                adjust="",
            )
        except Exception:
            return None
    if frame is None or frame.empty:
        return None
    return frame


def _concat_frames(frames):
    import pandas as pd

    parts = [frame for frame in frames if frame is not None and not frame.empty]
    if not parts:
        return None
    return pd.concat(parts, ignore_index=True).drop_duplicates()
