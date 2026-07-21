export type DataStatus = "live" | "cached" | "degraded" | "empty";
export type Severity = "warning" | "critical";
export type AlertType = "volume_spike" | "volume_shrink";

export interface Candle {
  symbol?: string;
  name?: string;
  time: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume: number;
  amount?: number;
}

export interface AlertLog {
  id: number;
  symbol: string;
  name: string;
  alert_type: AlertType;
  candle_time: string;
  volume: number;
  prev_volume: number;
  ratio: number;
  threshold: number;
  severity: Severity;
  message: string;
  created_at: string;
}

export interface MonitorSnapshot {
  symbol: string;
  name: string;
  data_status: DataStatus;
  latest_candle: Candle | null;
  candles: Candle[];
  current_alert: AlertLog | null;
  last_updated: string | null;
  error: string | null;
}

export interface AlertListResponse {
  alerts: AlertLog[];
}

export interface SymbolInfo {
  symbol: string;
  name: string;
}

export interface SymbolListResponse {
  symbols: SymbolInfo[];
}
