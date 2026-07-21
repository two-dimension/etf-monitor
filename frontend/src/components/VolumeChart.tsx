import type { Candle } from "../types";

interface VolumeChartProps {
  candles: Candle[];
}

type PriceCandle = Candle & {
  open: number;
  high: number;
  low: number;
  close: number;
};

const formatTime = (value: string) =>
  new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));

const formatNumber = (value: number) => value.toLocaleString("zh-CN");

export function VolumeChart({ candles }: VolumeChartProps) {
  const visibleCandles = latestTradingDayCandles(candles).slice(-48);
  const priceCandles = visibleCandles.filter(hasPrice);
  const maxVolume = Math.max(...visibleCandles.map((item) => item.volume), 1);
  const highPrice = Math.max(...priceCandles.map((item) => item.high), 1);
  const lowPrice = Math.min(...priceCandles.map((item) => item.low), highPrice);
  const priceRange = Math.max(highPrice - lowPrice, 0.001);

  return (
    <section className="chart-panel">
      <div className="panel-title split">
        <span>15分钟K线</span>
        <span>{visibleCandles.length} 根K线</span>
      </div>

      {visibleCandles.length === 0 ? (
        <div className="empty-chart">暂无K线</div>
      ) : (
        <div className="combined-chart">
          <section className="price-chart" aria-label="15分钟价格K线图">
            <div className="chart-scale price-scale">
              <span>{highPrice.toFixed(3)}</span>
              <span>{((highPrice + lowPrice) / 2).toFixed(3)}</span>
              <span>{lowPrice.toFixed(3)}</span>
            </div>
            <div className="candle-track">
              {priceCandles.map((candle, index) => {
                const isUp = candle.close >= candle.open;
                const wickTop = ((highPrice - candle.high) / priceRange) * 100;
                const wickHeight = Math.max(
                  ((candle.high - candle.low) / priceRange) * 100,
                  1,
                );
                const bodyTop =
                  ((highPrice - Math.max(candle.open, candle.close)) / priceRange) * 100;
                const bodyHeight = Math.max(
                  (Math.abs(candle.close - candle.open) / priceRange) * 100,
                  2,
                );
                const showLabel =
                  index === 0 || index === priceCandles.length - 1 || index % 8 === 0;

                return (
                  <div className="candle-slot" key={candle.time}>
                    <div
                      className={`wick ${isUp ? "up" : "down"}`}
                      style={{ top: `${wickTop}%`, height: `${wickHeight}%` }}
                    />
                    <div
                      className={`candle-body ${isUp ? "up" : "down"}`}
                      style={{ top: `${bodyTop}%`, height: `${bodyHeight}%` }}
                      title={`${formatTime(candle.time)} 开 ${candle.open.toFixed(3)} 收 ${candle.close.toFixed(3)}`}
                    />
                    <span>{showLabel ? formatTime(candle.time) : ""}</span>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="volume-chart" aria-label="15分钟成交量图">
            <div className="chart-scale">
              <span>{formatNumber(maxVolume)}</span>
              <span>{formatNumber(Math.round(maxVolume / 2))}</span>
              <span>0</span>
            </div>
            <div className="bar-track">
              {visibleCandles.map((candle, index) => {
                const height = Math.max(6, Math.round((candle.volume / maxVolume) * 100));
                const showLabel =
                  index === 0 || index === visibleCandles.length - 1 || index % 8 === 0;
                const isUp = candle.close == null || candle.open == null || candle.close >= candle.open;

                return (
                  <div className="bar-slot" key={candle.time}>
                    <div
                      className={`bar ${isUp ? "up" : "down"}`}
                      style={{ height: `${height}%` }}
                      title={`${formatTime(candle.time)} ${formatNumber(candle.volume)}`}
                    />
                    <span>{showLabel ? formatTime(candle.time) : ""}</span>
                  </div>
                );
              })}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

function hasPrice(candle: Candle): candle is PriceCandle {
  return (
    typeof candle.open === "number" &&
    typeof candle.high === "number" &&
    typeof candle.low === "number" &&
    typeof candle.close === "number"
  );
}

function latestTradingDayCandles(candles: Candle[]) {
  const ordered = [...candles].sort((a, b) => a.time.localeCompare(b.time));
  const latest = ordered[ordered.length - 1];
  if (!latest) return [];
  const latestDay = latest.time.slice(0, 10);
  return ordered.filter((candle) => candle.time.slice(0, 10) === latestDay);
}
