import sqlite3
conn = sqlite3.connect('data/etf_monitor.db')
print("--- alerts by date (top 10) ---")
for row in conn.execute(
    "SELECT substr(candle_time,1,10) AS d, COUNT(*) FROM alerts GROUP BY d ORDER BY d DESC LIMIT 10"
).fetchall():
    print(row)
print("--- candles by date (top 10) ---")
for row in conn.execute(
    "SELECT substr(candle_time,1,10) AS d, COUNT(*) FROM candles GROUP BY d ORDER BY d DESC LIMIT 10"
).fetchall():
    print(row)
print("--- notification_events by event_type ---")
for row in conn.execute(
    "SELECT event_type, substr(candle_time,1,10) AS d, COUNT(*) FROM notification_events GROUP BY event_type, d ORDER BY d DESC"
).fetchall():
    print(row)
print("--- monitored symbols ---")
for row in conn.execute("SELECT DISTINCT symbol, name FROM candles ORDER BY symbol").fetchall():
    print(row)
