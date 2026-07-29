import os
import sys
from datetime import date
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BACKEND = os.path.join(ROOT, 'backend')
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
os.environ['DB_PATH'] = os.path.join(BACKEND, 'data', 'etf_monitor.db')
os.environ['EMAIL_ENABLED'] = 'true'
import sqlite3
from app.config import Settings
from app.detector import detect_volume_spike
from app.notifier import SMTPAlertNotifier
from app.store import AlertStore
settings = Settings()
store = AlertStore(settings.db_path)
TARGET_DATES = [date(2026, 7, 27), date(2026, 7, 24)]
deleted = 0
with sqlite3.connect(str(settings.db_path)) as conn:
    cur = conn.cursor()
    cur.execute("DELETE FROM alerts WHERE alert_type = 'volume_shrink'")
    deleted = cur.rowcount
    conn.commit()
print('deleted', deleted, 'volume_shrink alerts')
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
                if inserted:
                    all_alerts.append(saved)
                    print(sym, target_date, alert.candle_time, alert.alert_type, 'ratio=', alert.ratio, 'NEW')
if all_alerts:
    notifier = SMTPAlertNotifier(settings)
    notifier.smtp_to = '2357694165@qq.com'
    notifier.send_alerts(all_alerts)
    print('sent', len(all_alerts), 'alert(s) to 2357694165@qq.com')
else:
    print('no new alerts')
