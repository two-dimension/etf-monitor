from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.models import AlertCreate, AlertLog, Candle


class AlertStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    alert_type TEXT NOT NULL DEFAULT 'volume_spike',
                    candle_time TEXT NOT NULL,
                    volume INTEGER NOT NULL,
                    prev_volume INTEGER NOT NULL,
                    ratio REAL NOT NULL,
                    threshold REAL NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, candle_time)
                )
                """
            )
            _ensure_column(
                connection,
                table_name="alerts",
                column_name="alert_type",
                ddl="ALTER TABLE alerts ADD COLUMN alert_type TEXT NOT NULL DEFAULT 'volume_spike'",
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS candles (
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    candle_time TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    cached_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(symbol, candle_time)
                )
                """
            )

    def save_alert(self, alert: AlertCreate) -> AlertLog:
        saved_alert, _ = self.save_alert_with_status(alert)
        return saved_alert

    def save_alert_with_status(self, alert: AlertCreate) -> tuple[AlertLog, bool]:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO alerts (
                    symbol, name, alert_type, candle_time, volume, prev_volume, ratio,
                    threshold, severity, message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.symbol,
                    alert.name,
                    alert.alert_type,
                    alert.candle_time.isoformat(),
                    alert.volume,
                    alert.prev_volume,
                    alert.ratio,
                    alert.threshold,
                    alert.severity,
                    alert.message,
                ),
            )
            inserted = cursor.rowcount > 0
            row = connection.execute(
                """
                SELECT * FROM alerts
                WHERE symbol = ? AND candle_time = ?
                """,
                (alert.symbol, alert.candle_time.isoformat()),
            ).fetchone()
        if row is None:
            raise RuntimeError("failed to persist alert")
        return _alert_from_row(row), inserted

    def list_alerts(self, symbol: str, limit: int = 100) -> list[AlertLog]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM alerts
                WHERE symbol = ?
                ORDER BY candle_time DESC
                LIMIT ?
                """,
                (symbol, limit),
            ).fetchall()
        return [_alert_from_row(row) for row in rows]

    def latest_alert(self, symbol: str) -> AlertLog | None:
        alerts = self.list_alerts(symbol, limit=1)
        return alerts[0] if alerts else None

    def save_candles(self, candles: list[Candle]) -> None:
        self.upsert_candles(candles)

    def upsert_candles(self, candles: list[Candle]) -> None:
        if not candles:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO candles (
                    symbol, name, candle_time, open, high, low, close, volume, amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, candle_time) DO UPDATE SET
                    name = excluded.name,
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    amount = excluded.amount,
                    cached_at = CURRENT_TIMESTAMP
                """,
                [
                    (
                        candle.symbol,
                        candle.name,
                        candle.time.isoformat(),
                        candle.open,
                        candle.high,
                        candle.low,
                        candle.close,
                        candle.volume,
                        candle.amount,
                    )
                    for candle in candles
                ],
            )

    def list_candles(self, symbol: str, limit: int = 120) -> list[Candle]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM (
                    SELECT * FROM candles
                    WHERE symbol = ?
                    ORDER BY candle_time DESC
                    LIMIT ?
                )
                ORDER BY candle_time ASC
                """,
                (symbol, limit),
            ).fetchall()
        return [_candle_from_row(row) for row in rows]

    def latest_update(self, symbol: str) -> datetime | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT MAX(cached_at) AS cached_at FROM candles WHERE symbol = ?
                """,
                (symbol,),
            ).fetchone()
        if row is None or row["cached_at"] is None:
            return None
        return _parse_datetime(row["cached_at"])


class CandleCache:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS candles (
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    candle_time TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    cached_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(symbol, candle_time)
                )
                """
            )

    def upsert_candles(self, candles: list[Candle]) -> None:
        if not candles:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO candles (
                    symbol, name, candle_time, open, high, low, close, volume, amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, candle_time) DO UPDATE SET
                    name = excluded.name,
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    amount = excluded.amount,
                    cached_at = CURRENT_TIMESTAMP
                """,
                [
                    (
                        candle.symbol,
                        candle.name,
                        candle.time.isoformat(),
                        candle.open,
                        candle.high,
                        candle.low,
                        candle.close,
                        candle.volume,
                        candle.amount,
                    )
                    for candle in candles
                ],
            )

    def list_candles(self, symbol: str, limit: int = 120) -> list[Candle]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM (
                    SELECT * FROM candles
                    WHERE symbol = ?
                    ORDER BY candle_time DESC
                    LIMIT ?
                )
                ORDER BY candle_time ASC
                """,
                (symbol, limit),
            ).fetchall()
        return [_candle_from_row(row) for row in rows]

    def latest_update(self, symbol: str) -> datetime | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT MAX(cached_at) AS cached_at FROM candles WHERE symbol = ?
                """,
                (symbol,),
            ).fetchone()
        if row is None or row["cached_at"] is None:
            return None
        return _parse_datetime(row["cached_at"])


def _alert_from_row(row: sqlite3.Row) -> AlertLog:
    return AlertLog(
        id=row["id"],
        symbol=row["symbol"],
        name=row["name"],
        alert_type=row["alert_type"],
        candle_time=_parse_datetime(row["candle_time"]),
        volume=row["volume"],
        prev_volume=row["prev_volume"],
        ratio=row["ratio"],
        threshold=row["threshold"],
        severity=row["severity"],
        message=row["message"],
        created_at=_parse_datetime(row["created_at"]),
    )


def _candle_from_row(row: sqlite3.Row) -> Candle:
    return Candle(
        symbol=row["symbol"],
        name=row["name"],
        time=_parse_datetime(row["candle_time"]),
        open=row["open"],
        high=row["high"],
        low=row["low"],
        close=row["close"],
        volume=row["volume"],
        amount=row["amount"],
    )


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    ddl: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(ddl)
