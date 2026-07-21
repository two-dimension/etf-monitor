from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.config import Settings
from app.models import Candle


class MarketDataClient(Protocol):
    def fetch_intraday_candles(self, symbol: str) -> list[Candle]:
        ...


class AkShareMarketDataClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch_intraday_candles(self, symbol: str) -> list[Candle]:
        import akshare as ak

        normalized_symbol = normalize_symbol(symbol)
        try:
            frame = ak.fund_etf_hist_min_em(
                symbol=normalized_symbol,
                period=self.settings.kline_period,
                adjust="",
            )
        except Exception:
            frame = ak.stock_zh_a_minute(
                symbol=sina_symbol(symbol),
                period=self.settings.kline_period,
                adjust="",
            )
        if frame is None or frame.empty:
            return []

        candles: list[Candle] = []
        for _, row in frame.iterrows():
            time_value = _first_present(row, ["时间", "日期", "datetime", "time", "day"])
            candles.append(
                Candle(
                    symbol=symbol,
                    name=self.settings.name_for_symbol(symbol),
                    time=_parse_time(time_value),
                    open=float(_first_present(row, ["开盘", "open"])),
                    high=float(_first_present(row, ["最高", "high"])),
                    low=float(_first_present(row, ["最低", "low"])),
                    close=float(_first_present(row, ["收盘", "close"])),
                    volume=int(float(_first_present(row, ["成交量", "volume"]))),
                    amount=float(_first_present(row, ["成交额", "amount"], default=0.0)),
                )
            )
        return sorted(candles, key=lambda item: item.time)


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


def _parse_time(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))
