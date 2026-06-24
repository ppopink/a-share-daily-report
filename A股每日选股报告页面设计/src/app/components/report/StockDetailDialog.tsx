import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";
import { ChangeText, EntryTag, RiskTag, NoRiskTag, ScoreBar } from "./shared";
import { KlineChart } from "./KlineChart";
import type { Stock } from "../../data/types";

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="rounded-md bg-neutral-soft/50 p-2.5">
      <div className="text-xs text-neutral">{label}</div>
      <div className="mt-1 tabular-nums text-foreground">{value}</div>
      {hint && <div className="text-[11px] text-neutral/80">{hint}</div>}
    </div>
  );
}

export function StockDetailDialog({
  stock,
  open,
  onClose,
}: {
  stock: Stock | null;
  open: boolean;
  onClose: () => void;
}) {
  if (!stock) return null;
  const scores: [string, number][] = [
    ["趋势分", stock.trendScore],
    ["趋势质量", stock.trendQualityScore],
    ["量能分", stock.volumeScore],
    ["DMI分", stock.dmiScore],
    ["MACD分", stock.macdScore],
    ["EXPMA分", stock.expmaScore],
    ["资金分", stock.moneyFlowScore],
    ["板块分", stock.sectorScore],
  ];

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        className="max-h-[94vh] !max-w-none gap-0 overflow-x-hidden overflow-y-auto p-0 sm:!max-w-none [&_*]:box-border"
        style={{
          width: "min(1280px, calc(100vw - 8px))",
          maxWidth: "calc(100vw - 8px)",
          boxSizing: "border-box",
          overflowX: "hidden",
        }}
      >
        <DialogHeader className="sticky top-0 z-10 min-w-0 max-w-full overflow-x-hidden border-b border-border bg-card px-3 py-4 sm:px-5">
          <DialogTitle className="flex min-w-0 flex-wrap items-center gap-2 pr-8">
            <span className="flex size-7 items-center justify-center rounded-md bg-finance-blue-soft text-sm text-finance-blue">
              {stock.rank}
            </span>
            <span className="min-w-0 truncate">{stock.name}</span>
            <span className="shrink-0 text-sm font-normal text-neutral">{stock.code}</span>
          </DialogTitle>
          <DialogDescription className="flex min-w-0 flex-wrap items-center gap-3 pr-8">
            <span className="text-lg tabular-nums text-foreground">
              {stock.price.toFixed(2)}
            </span>
            <ChangeText value={stock.changePct} />
            <span className="text-base tabular-nums text-finance-blue sm:ml-auto">
              总分 {stock.totalScore}
            </span>
          </DialogDescription>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <EntryTag timing={stock.entryTiming} />
            {stock.risks.length > 0 ? (
              stock.risks.map((r) => <RiskTag key={r.label} risk={r} />)
            ) : (
              <NoRiskTag />
            )}
          </div>
        </DialogHeader>

        <div className="min-w-0 max-w-full space-y-5 overflow-x-hidden px-2 pb-5 sm:px-5 lg:px-6" style={{ width: "100%" }}>
          <section className="min-w-0 max-w-full overflow-hidden" style={{ width: "100%" }}>
            <KlineChart data={stock.kline} />
          </section>

          <div className="grid min-w-0 max-w-full gap-5 overflow-x-hidden lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
            {/* 评分拆解 */}
            <section>
              <h4 className="mb-2 text-foreground">评分拆解</h4>
              <div className="space-y-2">
                {scores.map(([label, v]) => (
                  <ScoreBar key={label} label={label} score={v} max={25} compact />
                ))}
              </div>
            </section>

            {/* 趋势 / DMI */}
            <section>
              <h4 className="mb-2 text-foreground">趋势与 DMI</h4>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-3">
                <Metric label="ADX" value={stock.adx} />
                <Metric label="+DI" value={stock.plusDI} />
                <Metric label="-DI" value={stock.minusDI} />
                <Metric label="量比" value={stock.volRatio} />
                <Metric label="MA20上方天数" value={stock.aboveMa20Days20} hint="above_ma20_days_20" />
                <Metric label="股价/MA20" value={stock.closeMa20Ratio} hint="close_ma20_ratio" />
                <Metric label="MA20近10日斜率" value={<ChangeText value={stock.ma20Slope10Pct} />} hint="ma20_slope_10_pct" />
                <Metric label="MA20近20日斜率" value={<ChangeText value={stock.ma20Slope20Pct} />} hint="ma20_slope_20_pct" />
              </div>
            </section>
          </div>

          {/* MACD / 资金 / 板块 */}
          <section>
            <h4 className="mb-2 text-foreground">MACD · 资金 · 板块</h4>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <Metric label="DIF" value={stock.macdDIF} />
              <Metric label="DEA" value={stock.macdDEA} />
              <Metric label="HIST" value={<ChangeText value={stock.macdHIST} suffix="" />} />
              <Metric label="主力净流入比例" value={<ChangeText value={stock.moneyFlowRatio} />} />
              <Metric label="板块排名分位" value={`${stock.sectorRankPct}%`} hint={stock.sector} />
              <Metric label="板块内排名分位" value={`${stock.sectorInnerRankPct}%`} />
            </div>
          </section>

          {/* 入场 / 风险说明 */}
          <section className="space-y-2">
            <div className="rounded-md border border-finance-blue/15 bg-finance-blue-soft/50 p-3">
              <div className="mb-1 text-sm text-finance-blue">入场时机说明</div>
              <p className="text-sm text-foreground/90">{stock.entryNote}</p>
            </div>
            <div className="rounded-md border border-risk/15 bg-risk-soft/50 p-3">
              <div className="mb-1 text-sm text-risk">风险说明</div>
              <p className="text-sm text-foreground/90">{stock.riskNote}</p>
            </div>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}
