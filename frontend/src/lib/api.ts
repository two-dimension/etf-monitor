import type { AlertListResponse, MonitorSnapshot, SymbolListResponse } from "../types";

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchSnapshot(symbol = "159915.SZ"): Promise<MonitorSnapshot> {
  return getJson<MonitorSnapshot>(
    `/api/monitor/snapshot?symbol=${encodeURIComponent(symbol)}`,
  );
}

export function fetchAlerts(symbol = "159915.SZ", limit = 100): Promise<AlertListResponse> {
  return getJson<AlertListResponse>(
    `/api/alerts?symbol=${encodeURIComponent(symbol)}&limit=${limit}`,
  );
}

export function fetchSymbols(): Promise<SymbolListResponse> {
  return getJson<SymbolListResponse>("/api/monitor/symbols");
}

export function pollMonitor(symbol = "159915.SZ"): Promise<unknown> {
  return getJson(
    `/api/monitor/poll?symbol=${encodeURIComponent(symbol)}`,
    { method: "POST" },
  );
}
