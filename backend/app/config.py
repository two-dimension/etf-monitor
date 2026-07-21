from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


DEFAULT_SYMBOLS = (
    "159915.SZ:创业板ETF易方达,"
    "510310.SH:沪深300ETF易方达,"
    "588080.SH:科创50ETF易方达"
)
_ENV_LOADED = False


def _ensure_env_loaded() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    for path in _env_file_candidates():
        if path.is_file():
            _load_env_file(path)
    _ENV_LOADED = True


def _env_file_candidates() -> list[Path]:
    project_root = Path(__file__).resolve().parents[2]
    candidates = [Path.cwd() / ".env", Path.cwd().parent / ".env", project_root / ".env"]
    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _load_env_file(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _float_env(name: str, default: float) -> float:
    _ensure_env_loaded()
    value = os.getenv(name)
    return default if value is None or value == "" else float(value)


def _int_env(name: str, default: int) -> int:
    _ensure_env_loaded()
    value = os.getenv(name)
    return default if value is None or value == "" else int(value)


def _str_env(name: str, default: str) -> str:
    _ensure_env_loaded()
    value = os.getenv(name)
    return default if value is None or value == "" else value


def _bool_env(name: str, default: bool) -> bool:
    _ensure_env_loaded()
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.lower() in {"1", "true", "yes", "on"}


class EtfSymbolConfig(BaseModel):
    symbol: str
    name: str


def _symbols_env() -> list[EtfSymbolConfig]:
    raw_symbols = _str_env("ETF_SYMBOLS", DEFAULT_SYMBOLS)
    symbols: list[EtfSymbolConfig] = []
    seen: set[str] = set()
    for raw_item in raw_symbols.split(","):
        item = raw_item.strip()
        if not item:
            continue
        if ":" in item:
            raw_symbol, raw_name = item.split(":", 1)
        else:
            raw_symbol, raw_name = item, item
        symbol = raw_symbol.strip().upper()
        name = raw_name.strip() or symbol
        if symbol and symbol not in seen:
            symbols.append(EtfSymbolConfig(symbol=symbol, name=name))
            seen.add(symbol)
    return symbols


class Settings(BaseModel):
    symbol: str = Field(default_factory=lambda: _str_env("ETF_SYMBOL", "159915.SZ"))
    symbol_name: str = Field(default_factory=lambda: _str_env("ETF_NAME", "创业板ETF易方达"))
    symbols: list[EtfSymbolConfig] = Field(default_factory=_symbols_env)
    kline_period: str = Field(default_factory=lambda: _str_env("KLINE_PERIOD", "15"))
    timezone: str = Field(default_factory=lambda: _str_env("APP_TIMEZONE", "Asia/Shanghai"))
    db_path: Path = Field(
        default_factory=lambda: Path(_str_env("DB_PATH", "backend/data/etf_monitor.db"))
    )
    poll_interval_seconds: int = Field(
        default_factory=lambda: _int_env("POLL_INTERVAL_SECONDS", 60)
    )
    volume_ratio_threshold: float = Field(
        default_factory=lambda: _float_env("VOLUME_RATIO_THRESHOLD", 2.0)
    )
    volume_shrink_ratio_threshold: float = Field(
        default_factory=lambda: _float_env("VOLUME_SHRINK_RATIO_THRESHOLD", 0.5)
    )
    median_multiplier_threshold: float = Field(
        default_factory=lambda: _float_env("MEDIAN_MULTIPLIER_THRESHOLD", 1.8)
    )
    median_shrink_multiplier_threshold: float = Field(
        default_factory=lambda: _float_env("MEDIAN_SHRINK_MULTIPLIER_THRESHOLD", 0.5)
    )
    critical_ratio_threshold: float = Field(
        default_factory=lambda: _float_env("CRITICAL_RATIO_THRESHOLD", 5.0)
    )
    critical_shrink_ratio_threshold: float = Field(
        default_factory=lambda: _float_env("CRITICAL_SHRINK_RATIO_THRESHOLD", 0.2)
    )
    rolling_window_min: int = Field(
        default_factory=lambda: _int_env("ROLLING_WINDOW_MIN", 8)
    )
    rolling_window_max: int = Field(
        default_factory=lambda: _int_env("ROLLING_WINDOW_MAX", 20)
    )
    scheduler_enabled: bool = Field(
        default_factory=lambda: _bool_env("SCHEDULER_ENABLED", True)
    )
    cors_origin: str = Field(
        default_factory=lambda: _str_env("CORS_ORIGIN", "http://localhost:5173")
    )
    email_enabled: bool = Field(
        default_factory=lambda: _bool_env("EMAIL_ENABLED", False)
    )
    smtp_host: str = Field(default_factory=lambda: _str_env("SMTP_HOST", ""))
    smtp_port: int = Field(default_factory=lambda: _int_env("SMTP_PORT", 465))
    smtp_username: str = Field(default_factory=lambda: _str_env("SMTP_USERNAME", ""))
    smtp_password: str = Field(default_factory=lambda: _str_env("SMTP_PASSWORD", ""))
    smtp_from: str = Field(default_factory=lambda: _str_env("SMTP_FROM", ""))
    smtp_to: str = Field(default_factory=lambda: _str_env("SMTP_TO", ""))
    smtp_use_ssl: bool = Field(
        default_factory=lambda: _bool_env("SMTP_USE_SSL", True)
    )
    smtp_starttls: bool = Field(
        default_factory=lambda: _bool_env("SMTP_STARTTLS", False)
    )
    smtp_timeout_seconds: int = Field(
        default_factory=lambda: _int_env("SMTP_TIMEOUT_SECONDS", 10)
    )

    def monitored_symbols(self) -> list[EtfSymbolConfig]:
        if self.symbols:
            return self.symbols
        return [EtfSymbolConfig(symbol=self.symbol.upper(), name=self.symbol_name)]

    def name_for_symbol(self, symbol: str) -> str:
        normalized = symbol.upper()
        for item in self.monitored_symbols():
            if item.symbol.upper() == normalized:
                return item.name
        if normalized == self.symbol.upper():
            return self.symbol_name
        return symbol
