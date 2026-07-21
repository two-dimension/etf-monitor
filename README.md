# ETF 当日成交量异动监控系统

面向易方达旗下多只 ETF 的 15 分钟 K 线价格和成交量异动监控台。当前默认监控 `159915.SZ`（创业板ETF易方达）、`510310.SH`（沪深300ETF易方达）和 `588080.SH`（科创50ETF易方达）。后端使用 AkShare 拉取 ETF 分钟行情，成功拉取后会把 K 线保存到本地 SQLite；当 AkShare 不稳定时，接口会回退展示本地缓存，前端状态会显示“本地缓存”。

## 一键运行

首次运行先安装依赖：

```powershell
python -m pip install -r backend/requirements-dev.txt
npm.cmd install --prefix frontend
```

之后在项目根目录只需要一个终端：

```powershell
npm.cmd run dev
```

打开 `http://127.0.0.1:5173` 查看监控台。后端 API 文档在 `http://127.0.0.1:8000/docs`。

也可以继续使用 PowerShell 脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-dev.ps1
```

## 项目结构

```text
backend/
  app/                 FastAPI 后端、AkShare 适配、多标的轮询、检测规则、SMTP 通知、SQLite 存储
  tests/               后端单元测试和 API 测试
frontend/
  src/                 Vite + React + TypeScript 监控台
scripts/
  dev.mjs              单终端同时启动前后端
  start-dev.ps1        PowerShell 启动入口
```

## 异动规则

- 监控标的由 `ETF_SYMBOLS` 配置，格式为 `代码:名称,代码:名称`。
- 当前默认标的：`159915.SZ:创业板ETF易方达,510310.SH:沪深300ETF易方达,588080.SH:科创50ETF易方达`。
- 优先使用 AkShare `fund_etf_hist_min_em(symbol="纯数字代码", period="15", adjust="")`；若东财分钟接口不可用，会自动回退到 AkShare `stock_zh_a_minute(symbol="sz/sh代码", period="15", adjust="")`。
- 只评估已完成的 15 分钟 K 线；每次拉取后会回扫最新交易日内尚未告警过的 K 线，避免启动晚或数据源恢复后漏掉盘中异动。
- 前端可切换监控标的，价格 K 线图和成交量图只展示所选 ETF 最新交易日的当日 15 分钟 K 线。
- 放量：当前成交量 / 前一根成交量 >= `VOLUME_RATIO_THRESHOLD`，默认 `2.0`。
- 缩量：当前成交量 / 前一根成交量 <= `VOLUME_SHRINK_RATIO_THRESHOLD`，默认 `0.5`。
- 当历史 K 线数量足够时，放量还需 >= 最近窗口成交量中位数 * `MEDIAN_MULTIPLIER_THRESHOLD`；缩量还需 <= 最近窗口成交量中位数 * `MEDIAN_SHRINK_MULTIPLIER_THRESHOLD`。
- 放量倍数 >= `CRITICAL_RATIO_THRESHOLD`，或缩量比例 <= `CRITICAL_SHRINK_RATIO_THRESHOLD`，标记为 `critical`，否则为 `warning`。
- 告警按 `symbol + candle_time` 去重，避免重复写入和重复邮件推送；后台轮询会依次检查全部配置标的。
- `last_updated` 返回最新已完成 K 线时间。

## 本地缓存

SQLite 默认文件：`backend/data/etf_monitor.db`。

每次 AkShare 成功返回 K 线后，系统会按 `symbol + candle_time` 更新本地 K 线缓存。AkShare 请求失败时，后端会返回最近缓存 K 线，前端显示“本地缓存”，并把详细错误折叠在提示条里，避免影响页面布局。

## API

- `GET /api/monitor/symbols`：返回当前配置的监控标的列表。
- `GET /api/monitor/snapshot?symbol=159915.SZ`：返回指定 ETF 的最新快照。
- `GET /api/alerts?symbol=159915.SZ&limit=100`：返回指定 ETF 的告警日志。
- `POST /api/monitor/poll?symbol=159915.SZ`：手动轮询指定 ETF。
- `POST /api/monitor/poll-all`：手动轮询全部配置标的。

## 邮件推送

邮件推送默认关闭。需要启用时，在 `.env` 中补充 SMTP 配置：

```text
EMAIL_ENABLED=true
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USERNAME=monitor@example.com
SMTP_PASSWORD=your-smtp-auth-code
SMTP_FROM=monitor@example.com
SMTP_TO=desk@example.com,pm@example.com
SMTP_USE_SSL=true
SMTP_STARTTLS=false
SMTP_TIMEOUT_SECONDS=10
```

当任一配置标的新增一条放量或缩量异动告警时，会通过 SMTP 给 `SMTP_TO` 中的收件人发送邮件。同一 `symbol + candle_time` 的告警只记录一次，也只发送一次邮件。若 SMTP 发送失败，后端只记录日志，不会中断行情拉取、缓存或告警写入。

常见邮箱服务通常要求使用“SMTP 授权码”而不是登录密码，例如 QQ 邮箱、163 邮箱和企业邮箱。

## 测试

```powershell
python -m pytest backend/tests -q --basetemp "$env:TEMP\etf-monitor-pytest"
npm.cmd test --prefix frontend
npm.cmd run build --prefix frontend
```
