from pathlib import Path
src = Path('backend/app/detector.py').read_text(encoding='utf-8')
old_shrink_call = (
    '    shrink = _detect_shrink(ratio, settings)\n'
    '    if shrink:\n'
    '        return _alert(\n'
    '            current,\n'
    '            previous,\n'
    '            round(ratio, 2),\n'
    '            settings.volume_shrink_ratio_threshold,\n'
    '            shrink,\n'
    '            settings,\n'
    '        )\n'
    '\n'
    '    return None\n'
)
new_shrink_call = '    return None\n'
assert old_shrink_call in src, 'shrink call block anchor missing'
src = src.replace(old_shrink_call, new_shrink_call, 1)
old_shrink_def = (
    'def _detect_shrink(\n'
    '    ratio: float,\n'
    '    settings: Settings,\n'
    ') -> tuple[str, str] | None:\n'
    '    if ratio > settings.volume_shrink_ratio_threshold:\n'
    '        return None\n'
    '    severity = "critical" if ratio <= settings.critical_shrink_ratio_threshold else "warning"\n'
    '    return "volume_shrink", severity\n'
    '\n'
    '\n'
)
assert old_shrink_def in src, 'shrink def anchor missing'
src = src.replace(old_shrink_def, '', 1)
Path('backend/app/detector.py').write_text(src, encoding='utf-8')
print('detector.py patched, length:', len(src))
