import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import App from "./App";

const snapshot = {
  symbol: "159915.SZ",
  name: "创业板ETF易方达",
  data_status: "live",
  latest_candle: {
    symbol: "159915.SZ",
    name: "创业板ETF易方达",
    time: "2026-07-20T13:30:00",
    open: 1,
    high: 1.1,
    low: 0.9,
    close: 1.05,
    volume: 3600,
    amount: 3600,
  },
  candles: [
    { time: "2026-07-20T13:00:00", open: 1.01, high: 1.04, low: 1.0, close: 1.03, volume: 900 },
    { time: "2026-07-20T13:15:00", open: 1.03, high: 1.05, low: 1.01, close: 1.02, volume: 1000 },
    { time: "2026-07-20T13:30:00", open: 1.02, high: 1.08, low: 1.01, close: 1.05, volume: 3600 },
  ],
  current_alert: {
    id: 1,
    symbol: "159915.SZ",
    name: "创业板ETF易方达",
    alert_type: "volume_spike",
    candle_time: "2026-07-20T13:30:00",
    volume: 3600,
    prev_volume: 1000,
    ratio: 3.6,
    threshold: 3,
    severity: "warning",
    message: "159915.SZ 15分钟成交量放大 3.60 倍",
    created_at: "2026-07-20T13:31:00",
  },
  last_updated: "2026-07-20T13:31:00",
  error: null,
};

const alerts = {
  alerts: [
    {
      id: 1,
      symbol: "159915.SZ",
      name: "创业板ETF易方达",
      alert_type: "volume_spike",
      candle_time: "2026-07-20T13:30:00",
      volume: 3600,
      prev_volume: 1000,
      ratio: 3.6,
      threshold: 3,
      severity: "warning",
      message: "159915.SZ 15分钟成交量放大 3.60 倍",
      created_at: "2026-07-20T13:31:00",
    },
  ],
};

const symbols = {
  symbols: [
    { symbol: "159915.SZ", name: "创业板ETF易方达" },
    { symbol: "510310.SH", name: "沪深300ETF易方达" },
    { symbol: "588080.SH", name: "科创50ETF易方达" },
  ],
};

const hs300Snapshot = {
  ...snapshot,
  symbol: "510310.SH",
  name: "沪深300ETF易方达",
  latest_candle: {
    ...snapshot.latest_candle,
    symbol: "510310.SH",
    name: "沪深300ETF易方达",
    volume: 1800,
  },
  current_alert: null,
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ETF monitor dashboard", () => {
  test("renders live snapshot, anomaly tag, chart, and alert log", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      const path = String(url);
      const body = path.includes("/api/monitor/symbols")
        ? symbols
        : path.includes("/api/alerts")
          ? alerts
          : snapshot;
      return new Response(JSON.stringify(body), { status: 200 });
    });

    render(<App />);

    expect(await screen.findByText("创业板ETF易方达")).toBeInTheDocument();
    expect(screen.getByText("159915.SZ")).toBeInTheDocument();
    expect(screen.getByText("实时")).toBeInTheDocument();
    expect(screen.getByText("异动提醒")).toBeInTheDocument();
    expect(screen.getAllByText("3.60x")).toHaveLength(2);
    expect(screen.getByRole("table", { name: "告警日志" })).toBeInTheDocument();
    expect(screen.getByLabelText("15分钟价格K线图")).toBeInTheDocument();
    expect(screen.getByLabelText("15分钟成交量图")).toBeInTheDocument();
  });

  test("shows cached status when backend falls back to local candle data", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      const path = String(url);
      const body = path.includes("/api/monitor/symbols")
        ? symbols
        : path.includes("/api/alerts")
        ? { alerts: [] }
        : {
            ...snapshot,
            data_status: "cached",
            current_alert: null,
            error: "akshare failed",
          };
      return new Response(JSON.stringify(body), { status: 200 });
    });

    render(<App />);

    expect(await screen.findByText("本地缓存")).toBeInTheDocument();
    expect(screen.getByText("akshare failed")).toBeInTheDocument();
    expect(screen.getByText("暂无异动")).toBeInTheDocument();
  });

  test("refresh button polls backend and reloads dashboard data", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      const path = String(url);
      if (path.includes("/api/monitor/symbols")) {
        return new Response(JSON.stringify(symbols), { status: 200 });
      }
      if (path.includes("/api/monitor/poll")) {
        return new Response(JSON.stringify({ alert: null }), { status: 200 });
      }
      return new Response(JSON.stringify(path.includes("/api/alerts") ? alerts : snapshot), {
        status: 200,
      });
    });

    render(<App />);
    const button = await screen.findByRole("button", { name: "刷新数据" });
    await userEvent.click(button);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/monitor/poll?symbol=159915.SZ", {
        method: "POST",
      });
    });
  });

  test("volume chart only shows candles from the latest trading day", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      const path = String(url);
      const body = path.includes("/api/monitor/symbols")
        ? symbols
        : path.includes("/api/alerts")
        ? { alerts: [] }
        : {
            ...snapshot,
            candles: [
              { time: "2026-07-17T14:45:00", volume: 900 },
              { time: "2026-07-17T15:00:00", volume: 950 },
              { time: "2026-07-20T09:45:00", volume: 1000 },
              { time: "2026-07-20T10:00:00", volume: 1200 },
            ],
            latest_candle: {
              ...snapshot.latest_candle,
              time: "2026-07-20T10:00:00",
              volume: 1200,
            },
          };
      return new Response(JSON.stringify(body), { status: 200 });
    });

    render(<App />);

    expect(await screen.findByText("2 根K线")).toBeInTheDocument();
  });

  test("renders volume shrink anomaly as shrink alert", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      const path = String(url);
      const shrinkAlert = {
        id: 2,
        symbol: "159915.SZ",
        name: "创业板ETF易方达",
        alert_type: "volume_shrink",
        candle_time: "2026-07-20T14:00:00",
        volume: 900,
        prev_volume: 3200,
        ratio: 0.28,
        threshold: 0.35,
        severity: "warning",
        message: "159915.SZ 15分钟成交量缩至前一根 0.28 倍",
        created_at: "2026-07-20T14:01:00",
      };
      const body = path.includes("/api/monitor/symbols")
        ? symbols
        : path.includes("/api/alerts")
        ? { alerts: [shrinkAlert] }
        : {
            ...snapshot,
            current_alert: shrinkAlert,
            latest_candle: {
              ...snapshot.latest_candle,
              time: "2026-07-20T14:00:00",
              volume: 900,
            },
          };
      return new Response(JSON.stringify(body), { status: 200 });
    });

    render(<App />);

    expect(await screen.findByText("缩额提醒")).toBeInTheDocument();
    expect(screen.getAllByText("0.28x")).toHaveLength(2);
    expect(screen.getByText("缩额比例")).toBeInTheDocument();
  });

  test("switches monitored ETF and loads the selected symbol", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      const path = String(url);
      if (path.includes("/api/monitor/symbols")) {
        return new Response(JSON.stringify(symbols), { status: 200 });
      }
      if (path.includes("/api/alerts")) {
        return new Response(JSON.stringify({ alerts: [] }), { status: 200 });
      }
      const body = path.includes("510310.SH") ? hs300Snapshot : snapshot;
      return new Response(JSON.stringify(body), { status: 200 });
    });

    render(<App />);

    await userEvent.selectOptions(
      await screen.findByLabelText("监控标的"),
      "510310.SH",
    );

    expect(await screen.findByText("沪深300ETF易方达")).toBeInTheDocument();
    expect(screen.getByText("510310.SH")).toBeInTheDocument();
  });
});
