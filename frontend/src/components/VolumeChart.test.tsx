import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test } from "vitest";

import { VolumeChart } from "./VolumeChart";

const candles = [
  {
    time: "2026-07-20T13:00:00",
    open: 1.01,
    high: 1.04,
    low: 1,
    close: 1.03,
    volume: 900,
    amount: 912.5,
  },
  {
    time: "2026-07-20T13:15:00",
    open: 1.03,
    high: 1.08,
    low: 1.01,
    close: 1.05,
    volume: 3600,
    amount: 3776.2,
  },
];

describe("VolumeChart tooltip", () => {
  test("shows a custom dark tooltip for price candles", async () => {
    render(<VolumeChart candles={candles} />);

    await userEvent.hover(screen.getByLabelText("13:15 K线详情"));

    const tooltip = await screen.findByRole("tooltip");
    expect(tooltip).toHaveClass("chart-tooltip");
    expect(tooltip).toHaveTextContent("13:15 K线");
    expect(tooltip).toHaveTextContent("开 1.030");
    expect(tooltip).toHaveTextContent("高 1.080");
    expect(tooltip).toHaveTextContent("低 1.010");
    expect(tooltip).toHaveTextContent("收 1.050");
  });

  test("shows a custom dark tooltip for volume bars", async () => {
    render(<VolumeChart candles={candles} />);

    await userEvent.hover(screen.getByLabelText("13:15 成交量详情"));

    const tooltip = await screen.findByRole("tooltip");
    expect(tooltip).toHaveClass("chart-tooltip");
    expect(tooltip).toHaveTextContent("13:15 成交量");
    expect(tooltip).toHaveTextContent("量 3,600");
    expect(tooltip).toHaveTextContent("额 3,776.20");
  });
});
