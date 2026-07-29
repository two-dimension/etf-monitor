import os
import sys
import sqlite3
import akshare as ak
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BACKEND = os.path.join(ROOT, 'backend')
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
os.environ['DB_PATH'] = os.path.join(BACKEND, 'data', 'etf_monitor.db')
from app.market_data import sina_symbol, TIME_COLUMNS, VOLUME_COLUMNS
conn = sqlite3.connect(os.environ['DB_PATH'])
cur = conn.cursor()
print('=== 2026-07-23 13:15 stored in DB vs AkShare ===')
for sym in ['588000.SH', '159915.SZ', '510300.SH']:
    cur.execute('SELECT volume FROM candles WHERE symbol = ? AND candle_time = ?', (sym, '2026-07-23T13:15:00'))
    row = cur.fetchone()
    db_vol = row[0] if row else 'MISSING'
    try:
        df = ak.stock_zh_a_minute(symbol=sina_symbol(sym), period='15', adjust='')
        time_col = next((c for c in df.columns if c in TIME_COLUMNS), df.columns[0])
        df['_t'] = df[time_col].astype(str)
        row2 = df[df['_t'].str.startswith('2026-07-23') & df['_t'].str.contains('13:15')]
        fresh_vol = None
        if not row2.empty:
            for col in VOLUME_COLUMNS:
                if col in row2.iloc[0].index:
                    fresh_vol = int(row2.iloc[0][col])
                    break
        print(sym + ' DB=' + str(db_vol) + ' fresh(AkShare 7/23 13:15)=' + str(fresh_vol))
    except Exception as e:
        print(sym + ' DB=' + str(db_vol) + ' fresh error: ' + repr(e))
print()
print('=== All 7/23 15-min K-lines in DB ===')
for sym in ['588000.SH', '159915.SZ', '510300.SH']:
    cur.execute('SELECT candle_time, volume FROM candles WHERE symbol = ? AND substr(candle_time,1,10) = ? ORDER BY candle_time', (sym, '2026-07-23'))
    rows = cur.fetchall()
    print(sym + ' (' + str(len(rows)) + ' candles)')
    for r in rows:
        print('  ' + r[0] + ' vol=' + str(r[1]))
