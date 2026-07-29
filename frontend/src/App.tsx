import {
  Activity,
  AlertTriangle,
  Clock3,
  Database,
  RefreshCw,
  Signal,
  WifiOff,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { VolumeChart } from "./components/VolumeChart";
import { fetchAlerts, fetchSnapshot, fetchSymbols, pollMonitor } from "./lib/api";
import type { AlertLog, DataStatus, MonitorSnapshot, SymbolInfo } from "./types";

const statusText: Record<DataStatus, string> = {
  live: "实时",
  cached: "本地缓存",
  degraded: "数据异常",
  empty: "等待数据",
};

const statusIcon: Record<DataStatus, typeof Activity> = {
  live: Signal,
  cached: Database,
  degraded: WifiOff,
  empty: Activity,
};

export default function App() {
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState("159915.SZ");
  const [snapshot, setSnapshot] = useState<MonitorSnapshot | null>(null);
  const [alerts, setAlerts] = useState<AlertLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    const [snapshotData, alertsData] = await Promise.all([
      fetchSnapshot(selectedSymbol),
      fetchAlerts(selectedSymbol),
    ]);
    setSnapshot(snapshotData);
    setAlerts(alertsData.alerts);
    setError(null);
  }, [selectedSymbol]);

  useEffect(() => {
    fetchSymbols()
      .then((data) => {
        setSymbols(data.symbols);
        if (
          data.symbols.length > 0 &&
          !data.symbols.some((item) => item.symbol === selectedSymbol)
        ) {
          setSelectedSymbol(data.symbols[0].symbol);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, [selectedSymbol]);

  useEffect(() => {
    setLoading(true);
    loadDashboard()
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));

    const timer = window.setInterval(() => {
      void loadDashboard().catch((err: Error) => setError(err.message));
    }, 60_000);
    return () => window.clearInterval(timer);
  }, [loadDashboard]);

  async function refresh() {
    setLoading(true);
    try {
      await pollMonitor(selectedSymbol);
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "刷新失败");
    } finally {
      setLoading(false);
    }
  }

  const latest = snapshot?.latest_candle ?? null;
  const currentAlert = snapshot?.current_alert ?? null;
  const status = snapshot?.data_status ?? "empty";
  const StatusIcon = statusIcon[status];
  const volumeDelta = useMemo(() => {
    if (!currentAlert) return null;
    return currentAlert.volume - currentAlert.prev_volume;
  }, [currentAlert]);
  const currentAlertLabel = currentAlert ? alertTypeLabel(currentAlert) : "";
  const currentRatioLabel = currentAlert ? alertRatioLabel(currentAlert) : "";
  const selectedSymbolInfo = symbols.find((item) => item.symbol === selectedSymbol);

  return (
    <main className="app-shell">
      <header className="hero">
        <div className="hero-main">
          <div className="eyebrow">ETF 15分钟成交量监控</div>
          <div className="title-row">
            <h1>{snapshot?.name ?? selectedSymbolInfo?.name ?? "创业板ETF易方达"}</h1>
            <span className="symbol-chip">{snapshot?.symbol ?? selectedSymbol}</span>
          </div>
          <p className="subtitle">
            监控多只 ETF 已完成 15 分钟 K 线成交量，AkShare 不稳定时自动读取本地缓存。
          </p>
        </div>

        <div className="hero-actions">
          <label className="symbol-select">
            <span>监控标的</span>
            <select
              aria-label="监控标的"
              value={selectedSymbol}
              onChange={(event) => setSelectedSymbol(event.target.value)}
            >
              {(symbols.length > 0
                ? symbols
                : [{ symbol: selectedSymbol, name: selectedSymbolInfo?.name ?? "创业板ETF易方达" }]
              ).map((item) => (
                <option key={item.symbol} value={item.symbol}>
                  {item.name} {item.symbol}
                </option>
              ))}
            </select>
          </label>
          <span className={`status-badge status-${status}`}>
            <StatusIcon size={16} aria-hidden="true" />
            {statusText[status]}
          </span>
          <button className="refresh-button" type="button" onClick={refresh} disabled={loading}>
            <RefreshCw size={17} aria-hidden="true" className={loading ? "spin" : ""} />
            刷新数据
          </button>
        </div>
      </header>

      {(error || snapshot?.error) && (
        <details className="notice" open={status !== "cached"}>
          <summary>{status === "cached" ? "AkShare连接失败，正在使用本地缓存" : "数据源异常"}</summary>
          <p>{error ?? snapshot?.error}</p>
        </details>
      )}

      <section className="summary-grid" aria-label="核心指标">
        <Metric label="最新成交量" value={formatNumber(latest?.volume)} />
        <Metric label="最新成交额" value={formatMoney(latest?.amount)} />
        <Metric label="最新K线" value={formatDateTime(latest?.time)} />
        <Metric label="最后更新" value={formatDateTime(snapshot?.last_updated)} />
      </section>

      <section className="content-grid">
        <VolumeChart candles={snapshot?.candles ?? []} />

        <aside className="alert-panel" aria-label="当前异动">
          <div className="panel-title">
            <AlertTriangle size={18} aria-hidden="true" />
            <span>当前状态</span>
          </div>

          {currentAlert ? (
            <div className={`alert-card ${currentAlert.severity}`}>
              <span className="alert-tag">{currentAlertLabel}</span>
              <strong>{currentAlert.ratio.toFixed(2)}x</strong>
              <p>{currentAlert.message}</p>
              <div className="alert-stats">
                <span>当前 {formatNumber(currentAlert.volume)}</span>
                <span>前一根 {formatNumber(currentAlert.prev_volume)}</span>
                <span>{currentRatioLabel} {currentAlert.ratio.toFixed(2)}x</span>
                <span>{currentAlert.alert_type === "volume_shrink" ? "缩量" : "增量"} {formatNumber(volumeDelta ?? 0)}</span>
              </div>
            </div>
          ) : (
            <div className="quiet-card">
              <span>暂无异动</span>
              <p>最近一根已完成 K 线没有触发放量阈值。</p>
            </div>
          )}
        </aside>
      </section>

      <section className="log-panel">
        <div className="panel-title split">
          <span>
            <Database size={18} aria-hidden="true" />
            告警日志
          </span>
          <span>{alerts.length} 条</span>
        </div>
        <AlertTable alerts={alerts} />
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AlertTable({ alerts }: { alerts: AlertLog[] }) {
  if (alerts.length === 0) {
    return <div className="empty-log">暂无日志</div>;
  }

  return (
    <div className="table-wrap">
      <table aria-label="告警日志">
        <thead>
          <tr>
            <th>时间</th>
            <th>级别</th>
            <th>{alertRatioLabel(alerts[0])}</th>
            <th>成交量</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((alert) => (
            <tr key={alert.id}>
              <td>
                <span className="time-cell">
                  <Clock3 size={14} aria-hidden="true" />
                  {formatDateTime(alert.candle_time)}
                </span>
              </td>
              <td>
                <span className={`severity-pill ${alert.severity}`}>
                  {alert.severity === "critical" ? "严重" : "提醒"}
                </span>
              </td>
              <td>{alert.ratio.toFixed(2)}x</td>
              <td>{formatNumber(alert.volume)}</td>
              <td>{alert.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function alertTypeLabel(alert: AlertLog) {
  return alert.alert_type === "volume_shrink" ? "缩量提醒" : "异动提醒";
}

function alertRatioLabel(alert: AlertLog) {
  return alert.alert_type === "volume_shrink" ? "缩量比例" : "放量倍数";
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "--";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function formatNumber(value: number | null | undefined) {
  if (value == null) return "--";
  return value.toLocaleString("zh-CN");
}

function formatMoney(value: number | null | undefined) {
  if (value == null) return "--";
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(2)}亿`;
  if (value >= 10_000) return `${(value / 10_000).toFixed(2)}万`;
  return formatNumber(value);
}
