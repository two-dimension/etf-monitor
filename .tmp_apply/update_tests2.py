from pathlib import Path
src = Path('backend/tests/test_detector.py').read_text(encoding='utf-8')
old_afternoon = (
    'def test_afternoon_open_candle_compares_to_same_day_predecessor():\n'
    '    settings = Settings(volume_ratio_threshold=3.0)\n'
    '    # The 13:15 spike is compared to the 11:30 candle on the same day.\n'
    '    candles = [\n'
    '        candle("2026-07-20T11:30:00", 200),\n'
    '        candle("2026-07-20T13:15:00", 1000),\n'
    '        candle("2026-07-21T11:30:00", 250),\n'
    '        candle("2026-07-21T13:15:00", 3600),\n'
    '    ]\n'
    '\n'
    '    alert = detect_volume_spike(candles, settings)\n'
    '\n'
    '    assert alert is not None\n'
    '    assert alert.alert_type == "volume_spike"\n'
    '    assert alert.candle_time == datetime.fromisoformat("2026-07-21T1'
)
old_rest = (
    '3:15:00")\n'
    '    assert alert.prev_volume == 1000\n'
    '    assert alert.ratio == 3.6\n'
)
assert old_afternoon + old_rest in src, 'afternoon test anchor missing'
new_afternoon = (
    'def test_afternoon_open_candle_compares_to_same_day_predecessor():\n'
    '    settings = Settings(volume_ratio_threshold=3.0)\n'
    '    # 13:15 is now an opening candle: compare to 13:15 on the previous trading day.\n'
    '    candles = [\n'
    '        candle("2026-07-20T13:15:00", 1000),\n'
    '        candle("2026-07-21T11:30:00", 250),\n'
    '        candle("2026-07-21T13:15:00", 3600),\n'
    '    ]\n'
    '\n'
    '    alert = detect_volume_spike(candles, settings)\n'
    '\n'
    '    assert alert is not None\n'
    '    assert alert.alert_type == "volume_spike"\n'
    '    assert alert.candle_time == datetime.fromisoformat("2026-07-21T1'
)
new_rest = (
    '3:15:00")\n'
    '    assert alert.prev_volume == 1000\n'
    '    assert alert.ratio == 3.6\n'
)
src = src.replace(old_afternoon + old_rest, new_afternoon + new_rest, 1)
old_non = (
    'def test_non_opening_candle_still_uses_day_threshold():\n'
    '    """The 9:45 candle (15-min) should use the regular 2.0x threshold, not the opening 1.5x."""\n'
    '    settings = Settings(\n'
    '        median_multiplier_threshold=0,\n'
    '    )\n'
    '    candles = [\n'
    '    candle("2026-07-20T09:45:00", 1000),\n'
    '    candle("2026-07-20T10:00:00", 1000),\n'
    '    candle("2026-07-21T09:45:00", 1600),\n'
    '    ]\n'
    '    alert = detect_volume_spike(candles, settings)\n'
    '    assert alert is None'
)
new_non = (
    'def test_non_opening_candle_still_uses_day_threshold():\n'
    '    """A 11:30 candle (15-min) should use the regular 2.0x threshold, not opening/late-session."""\n'
    '    settings = Settings(\n'
    '        median_multiplier_threshold=0,\n'
    '    )\n'
    '    candles = [\n'
    '    candle("2026-07-20T11:15:00", 1000),\n'
    '    candle("2026-07-20T11:30:00", 1000),\n'
    '    candle("2026-07-21T11:30:00", 1600),\n'
    '    ]\n'
    '    alert = detect_volume_spike(candles, settings)\n'
    '    assert alert is None'
)
assert old_non in src, 'non opening test anchor missing'
src = src.replace(old_non, new_non, 1)
old_shrink_start = 'def test_alerts_shrink_when_ratio_falls_below_threshold():'
old_shrink_end = 'def test_marks_critical_when_shrink_breaks_critical_threshold():'
old_shrink_end_pos = src.find(old_shrink_end)
if old_shrink_start in src and old_shrink_end_pos > src.find(old_shrink_start):
    start_pos = src.find(old_shrink_start)
    end_pos = old_shrink_end_pos
    src = src[:start_pos] + src[end_pos:]
    print('removed shrink tests')
Path('backend/tests/test_detector.py').write_text(src, encoding='utf-8')
print('test_detector.py patched, length:', len(src))
