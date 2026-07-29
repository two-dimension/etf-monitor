from pathlib import Path
src = Path('backend/app/config.py').read_text(encoding='utf-8')
old = (
    "    def is_opening_candle(self, candle_time) -> bool:\n"
    "        \"\"\"Opening candles (9:30 morning and 13:00 afternoon) compare to the previous trading day.\"\"\"\n"
    "        if hasattr(candle_time, \"time\"):\n"
    "            candle_time = candle_time.time()\n"
    "        return candle_time in {time(9, 30), time(13, 0)}\n"
)
new = (
    "    def is_opening_candle(self, candle_time) -> bool:\n"
    "        \"\"\"Opening/same-slot candles (9:30, 9:45, 13:00, 13:15) compare to the previous trading day.\"\"\"\n"
    "        if hasattr(candle_time, \"time\"):\n"
    "            candle_time = candle_time.time()\n"
    "        return candle_time in {time(9, 30), time(9, 45), time(13, 0), time(13, 15)}\n"
)
assert old in src, 'is_opening_candle anchor missing'
src = src.replace(old, new, 1)
Path('backend/app/config.py').write_text(src, encoding='utf-8')
print('config.py patched')
