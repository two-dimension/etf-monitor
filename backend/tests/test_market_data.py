import pandas as pd

from app.config import Settings
from app.market_data import AkShareMarketDataClient


def test_akshare_client_falls_back_to_sina_minute_data_when_eastmoney_fails(monkeypatch):
    import akshare as ak

    calls: list[tuple[str, str]] = []

    def failing_eastmoney(*args, **kwargs):
        raise RuntimeError("eastmoney unavailable")

    def working_sina(symbol: str, period: str, adjust: str):
        calls.append((symbol, period))
        return pd.DataFrame(
            [
                {
                    "day": "2026-07-21 11:15:00",
                    "open": 3.568,
                    "high": 3.630,
                    "low": 3.567,
                    "close": 3.595,
                    "volume": 367796290,
                    "amount": 1324330357.1699,
                },
                {
                    "day": "2026-07-21 11:30:00",
                    "open": 3.596,
                    "high": 3.647,
                    "low": 3.589,
                    "close": 3.644,
                    "volume": 241405916,
                    "amount": 872506583.0357,
                },
            ]
        )

    monkeypatch.setattr(ak, "fund_etf_hist_min_em", failing_eastmoney)
    monkeypatch.setattr(ak, "stock_zh_a_minute", working_sina)

    client = AkShareMarketDataClient(Settings())

    candles = client.fetch_intraday_candles("159915.SZ")

    assert calls == [("sz159915", "15")]
    assert len(candles) == 2
    assert candles[-1].time.isoformat() == "2026-07-21T11:30:00"
    assert candles[-1].open == 3.596
    assert candles[-1].close == 3.644
    assert candles[-1].volume == 241405916
