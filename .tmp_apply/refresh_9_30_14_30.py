import os
import sys
from datetime import date, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BACKEND = os.path.join(ROOT, 'backend')
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
os.environ['DB_PATH'] = os.path.join(BACKEND, 'data', 'etf_monitor.db')
os.environ['EMAIL_ENABLED'] = 'true'
import akshare as ak
from app.config import Settings
from app.detector import detect_volume_spike
from app.models import Candle
from app.notifier import SMTPAlertNotifier
from app.store import AlertStore
from app.market_data import (
    TIME_COLUMNS, OPEN_COLUMNS, HIGH_COLUMNS, LOW_COLUMNS, CLOSE_COLUMNS,
    VOLUME_COLUMNS, AMOUNT_COLUMNS, _first_present, _normalized_volume, _parse_time,
    sina_symbol,
)
from pathlib import Path
settings = Settings()
store = AlertStore(settings.db_path)
TARGET_DATES = [date(2026, 7, 27), date(2026, 7, 24)]
print('=== Refetching 9:30-14:30 15-min from AkShare ===')
for sym_cfg in settings.monitored_symbols():
    sym = sym_cfg.symbol
    for target_date in TARGET_DATES:
        try:
            df = ak.stock_zh_a_minute(symbol=sina_symbol(sym), period='15', adjust='')
        except Exception as e:
            print(sym, target_date, 'fetch failed:', e)
            continue
        if df is None or df.empty:
            print(sym, target_date, 'empty')
            continue
        time_col = next((c for c in df.columns if c in TIME_COLUMNS), df.columns[0])
        df['_t'] = df[time_col].astype(str)
        rows = df[df['_t'].str.startswith(str(target_date))]
        rows = rows[rows['_t'].str.contains(' 09:') | rows['_t'].str.contains(' 10:') | rows['_t'].str.contains(' 11:') | rows['_t'].str.contains(' 13:') | rows['_t'].str.contains(' 14:00') | rows['_t'].str.contains(' 14:15')]
        candles = []
        for _, row in rows.iterrows():
            time_str = str(row[time_col])
            try:
                t_obj = datetime.fromisoformat(time_str.replace('/', '-'))
            except Exception:
                continue
            if t_obj.time() >= settings.late_session_start_time:
                continue
            close = float(_first_present(row, CLOSE_COLUMNS))
            amount = float(_first_present(row, AMOUNT_COLUMNS, default=0.0))
            candles.append(Candle(
                symbol=sym, name=settings.name_for_symbol(sym), time=t_obj,
                open=float(_first_present(row, OPEN_COLUMNS)),
                high=float(_first_present(row, HIGH_COLUMNS)),
                low=float(_first_present(row, LOW_COLUMNS)),
                close=close, volume=_normalized_volume(row, close, amount), amount=amount,
            ))
        if candles:
            store.upsert_candles(candles)
            print(sym, target_date, 'upserted', len(candles), '15-min candles')
print()
print('=== Re-running detection ===')
all_alerts = []
for sym_cfg in settings.monitored_symbols():
    sym = sym_cfg.symbol
    all_candles = store.list_candles(sym, limit=500)
    for target_date in TARGET_DATES:
        day_candles = sorted([c for c in all_candles if c.time.date() == target_date], key=lambda c: c.time)
        historical = [c for c in all_candles if c.time.date() < target_date]
        for i in range(2, len(day_candles) + 1):
            sub = day_candles[:i]
            full = historical + sub
            alert = detect_volume_spike(full, settings)
            if alert is not None:
                saved, inserted = store.save_alert_with_status(alert)
                all_alerts.append(saved)
                if inserted:
                    print(sym, target_date, alert.candle_time, alert.alert_type, 'ratio=', alert.ratio, 'NEW')
if all_alerts:
    if settings.email_enabled:
        notifier = SMTPAlertNotifier(settings)
        notifier.send_alerts(all_alerts)
        print('sent', len(all_alerts), 'alert(s) to', settings.smtp_to)
    else:
        print('EMAIL_ENABLED is off; not sending')
else:
    print('no new alerts')
