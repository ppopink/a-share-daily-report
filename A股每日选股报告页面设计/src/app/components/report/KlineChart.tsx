import type { KlinePoint } from "../../data/types";

const UP = "#d23b3b";
const DOWN = "#1f9e6e";
const BLUE = "#1f4e78";
const ORANGE = "#e08a2b";
const GRID = "#e5e9ee";
const TEXT = "#5c7184";

function scale(value: number, min: number, max: number, top: number, bottom: number) {
  if (max <= min) return (top + bottom) / 2;
  return bottom - ((value - min) / (max - min)) * (bottom - top);
}

function linePath(points: { x: number; y: number; valid: boolean }[]) {
  let path = "";
  points.forEach((p) => {
    if (!p.valid) return;
    path += path ? ` L ${p.x.toFixed(1)} ${p.y.toFixed(1)}` : `M ${p.x.toFixed(1)} ${p.y.toFixed(1)}`;
  });
  return path;
}

export function KlineChart({ data }: { data?: KlinePoint[] }) {
  const points = (data ?? []).slice(-60);
  if (points.length < 5) {
    return (
      <div className="rounded-lg border border-dashed border-border p-4 text-sm text-neutral">
        暂无足够 K 线数据，运行最新选股后会自动带入最近走势。
      </div>
    );
  }

  const width = 760;
  const height = 360;
  const pad = { left: 42, right: 18, top: 18, bottom: 26 };
  const priceBottom = 248;
  const volumeTop = 278;
  const chartWidth = width - pad.left - pad.right;
  const candleGap = chartWidth / points.length;
  const candleWidth = Math.max(3, Math.min(9, candleGap * 0.55));
  const highs = points.flatMap((p) => [p.high, p.ma5 ?? p.close, p.ma20 ?? p.close]);
  const lows = points.flatMap((p) => [p.low, p.ma5 ?? p.close, p.ma20 ?? p.close]);
  const maxPrice = Math.max(...highs);
  const minPrice = Math.min(...lows);
  const pricePad = Math.max((maxPrice - minPrice) * 0.08, maxPrice * 0.01);
  const yMax = maxPrice + pricePad;
  const yMin = Math.max(0, minPrice - pricePad);
  const maxVolume = Math.max(...points.map((p) => p.volume), 1);
  const latest = points[points.length - 1];
  const prev = points[points.length - 2];
  const changePct = prev?.close ? ((latest.close - prev.close) / prev.close) * 100 : 0;

  const ma5Path = linePath(points.map((p, i) => ({
    x: pad.left + i * candleGap + candleGap / 2,
    y: scale(p.ma5 ?? 0, yMin, yMax, pad.top, priceBottom),
    valid: p.ma5 !== null,
  })));
  const ma20Path = linePath(points.map((p, i) => ({
    x: pad.left + i * candleGap + candleGap / 2,
    y: scale(p.ma20 ?? 0, yMin, yMax, pad.top, priceBottom),
    valid: p.ma20 !== null,
  })));

  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => yMin + (yMax - yMin) * t);

  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h4 className="text-foreground">近期 K 线走势</h4>
          <p className="text-xs text-neutral">最近 {points.length} 个交易日 · 含 MA5 / MA20 / 成交量</p>
        </div>
        <div className="text-right text-xs">
          <div className="tabular-nums text-foreground">
            收盘 {latest.close.toFixed(2)}
            <span className={changePct >= 0 ? "ml-2 text-up" : "ml-2 text-down"}>
              {changePct >= 0 ? "+" : ""}{changePct.toFixed(2)}%
            </span>
          </div>
          <div className="text-neutral">{latest.date}</div>
        </div>
      </div>

      <div className="w-full overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="h-auto min-w-[680px]">
          {ticks.map((tick) => {
            const y = scale(tick, yMin, yMax, pad.top, priceBottom);
            return (
              <g key={tick}>
                <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke={GRID} strokeDasharray="3 3" />
                <text x={8} y={y + 4} fontSize="11" fill={TEXT}>{tick.toFixed(2)}</text>
              </g>
            );
          })}

          {points.map((p, i) => {
            const x = pad.left + i * candleGap + candleGap / 2;
            const yHigh = scale(p.high, yMin, yMax, pad.top, priceBottom);
            const yLow = scale(p.low, yMin, yMax, pad.top, priceBottom);
            const yOpen = scale(p.open, yMin, yMax, pad.top, priceBottom);
            const yClose = scale(p.close, yMin, yMax, pad.top, priceBottom);
            const isUp = p.close >= p.open;
            const color = isUp ? UP : DOWN;
            const bodyTop = Math.min(yOpen, yClose);
            const bodyHeight = Math.max(2, Math.abs(yClose - yOpen));
            const volHeight = (p.volume / maxVolume) * 58;
            return (
              <g key={`${p.date}-${i}`}>
                <line x1={x} x2={x} y1={yHigh} y2={yLow} stroke={color} strokeWidth="1.2" />
                <rect
                  x={x - candleWidth / 2}
                  y={bodyTop}
                  width={candleWidth}
                  height={bodyHeight}
                  fill={isUp ? "#fff" : color}
                  stroke={color}
                  strokeWidth="1.2"
                />
                <rect
                  x={x - candleWidth / 2}
                  y={volumeTop + 62 - volHeight}
                  width={candleWidth}
                  height={volHeight}
                  fill={color}
                  opacity="0.35"
                />
                {(i === 0 || i === points.length - 1 || i % 12 === 0) && (
                  <text x={x} y={height - 8} textAnchor="middle" fontSize="10" fill={TEXT}>
                    {p.date.slice(5)}
                  </text>
                )}
              </g>
            );
          })}

          <path d={ma5Path} fill="none" stroke={BLUE} strokeWidth="1.8" />
          <path d={ma20Path} fill="none" stroke={ORANGE} strokeWidth="1.8" />
          <line x1={pad.left} x2={width - pad.right} y1={volumeTop} y2={volumeTop} stroke={GRID} />
          <text x={pad.left} y={272} fontSize="11" fill={TEXT}>成交量</text>
          <g transform={`translate(${width - 170}, 20)`}>
            <line x1="0" x2="20" y1="0" y2="0" stroke={BLUE} strokeWidth="2" />
            <text x="26" y="4" fontSize="11" fill={TEXT}>MA5</text>
            <line x1="70" x2="90" y1="0" y2="0" stroke={ORANGE} strokeWidth="2" />
            <text x="96" y="4" fontSize="11" fill={TEXT}>MA20</text>
          </g>
        </svg>
      </div>
    </div>
  );
}
