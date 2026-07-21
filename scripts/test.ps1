$ErrorActionPreference = "Stop"

$env:PYTHONPATH = "backend"
python -m pytest backend/tests -q --basetemp "$env:TEMP\etf-monitor-pytest"
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
