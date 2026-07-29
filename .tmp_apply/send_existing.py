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
from app.config import Settings
from app.notifier import SMTPAlertNotifier
from app.store import AlertStore
settings = Settings()
store = AlertStore(settings.db_path)
TARGET_DATES = [date(2026, 7, 27), date(2026, 7, 24)]
all_alerts = []
for sym_cfg in settings.monitored_symbols():
    sym = sym_cfg.symbol
    alerts = store.list_alerts(sym, limit=500)
    for target_date in TARGET_DATES:
        for a in alerts:
            if a.candle_time.date() != target_date:
                continue
            if a.alert_type != 'volume_spike':
                continue
            all_alerts.append(a)
all_alerts.sort(key=lambda a: (a.candle_time, a.symbol))
print('found', len(all_alerts), 'volume_spike alerts for', [str(d) for d in TARGET_DATES])
for a in all_alerts:
    print('  ', a.candle_time, a.symbol, a.alert_type, 'ratio=', a.ratio, 'prev=', a.prev_volume, 'vol=', a.volume)
if all_alerts:
    notifier = SMTPAlertNotifier(settings)
    notifier.smtp_to = '2357694165@qq.com'
    notifier.send_alerts(all_alerts)
    print('sent', len(all_alerts), 'alert(s) to 2357694165@qq.com')
else:
    print('no alerts to send')
