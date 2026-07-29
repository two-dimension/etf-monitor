import pandas as pd

from app.config import Settings
from app.market_data import AkShareMarketDataClient


def test_akshare_client_pulls_only_15m_during_main_session(monkeypatch):
    import akshare as ak

    # Pin the clock to the main session (before late_session_start_time).
    monkeypatch.setattr(Settings, "is_late_session", lambda self, candle_time: False)

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


def test_akshare_client_combines_15m_main_session_with_5m_late_session(monkeypatch):
    import akshare as ak

    # Pin the clock to the late session (at or after late_session_start_time).
    monkeypatch.setattr(Settings, "is_late_session", lambda self, candle_time: True)

    calls: list[tuple[str, str]] = []

    def working_eastmoney(symbol: str, period: str, adjust: str):
        calls.append((symbol, period))
        if period == "15":
            return pd.DataFrame(
                [
                    {
                        "datetime": "2026-07-28 14:15:00",
                        "open": 1.0,
                        "high": 1.1,
                        "low": 0.9,
                        "close": 1.0,
                        "volume": 1500,
                        "amount": 1500.0,
                    },
                    {
                        "datetime": "2026-07-28 14:30:00",
                        "open": 1.0,
                        "high": 1.1,
                        "low": 0.9,
                        "close": 1.0,
                        "volume": 3000,
                        "amount": 3000.0,
                    },
                ]
            )
        return pd.DataFrame(
            [
                {
                    "datetime": "2026-07-28 14:25:00",
                    "open": 1.0,
                    "high": 1.0,
                    "low": 1.0,
                    "close": 1.0,
                    "volume": 2500,
                    "amount": 2500.0,
                },
                {
                    "datetime": "2026-07-28 14:30:00",
                    "open": 1.0,
                    "high": 1.0,
                    "low": 1.0,
                    "close": 1.0,
                    "volume": 500,
                    "amount": 500.0,
                },
                {
                    "datetime": "2026-07-28 14:35:00",
                    "open": 1.0,
                    "high": 1.0,
                    "low": 1.0,
                    "close": 1.0,
                    "volume": 1000,
                    "amount": 1000.0,
                }
            ]
        )

    monkeypatch.setattr(ak, "fund_etf_hist_min_em", working_eastmoney)

    client = AkShareMarketDataClient(Settings())

    candles = client.fetch_intraday_candles("510300.SH")

    assert calls == [("510300", "15"), ("510300", "5")]
    assert [
        (candle.time.isoformat(), candle.volume, candle.kline_period)
        for candle in candles
    ] == [
        ("2026-07-28T14:15:00", 1500, "15"),
        ("2026-07-28T14:30:00", 500, "5"),
        ("2026-07-28T14:30:00", 3000, "15"),
        ("2026-07-28T14:35:00", 1000, "5"),
    ]


def test_akshare_client_normalizes_lot_based_minute_volume(monkeypatch):
    import akshare as ak

    def eastmoney_with_lot_volume(*args, **kwargs):
        return pd.DataFrame(
            [
                {
                    "datetime": "2026-07-22 14:45:00",
                    "open": 1.998,
                    "high": 2.001,
                    "low": 1.995,
                    "close": 2.000,
                    "volume": 300321,
                    "amount": 60064200.0,
                }
            ]
        )

    monkeypatch.setattr(ak, "fund_etf_hist_min_em", eastmoney_with_lot_volume)

    client = AkShareMarketDataClient(Settings())

    candles = client.fetch_intraday_candles("510310.SH")

    assert candles[0].volume == 30032100
