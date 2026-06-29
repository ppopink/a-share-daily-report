import { ChevronRight } from "lucide-react";
import { Card } from "../ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../ui/table";
import { ChangeText, EntryTag, RiskTag, NoRiskTag } from "./shared";
import type { Stock } from "../../data/types";

function scoreColor(score: number) {
  return score >= 80
    ? "text-up"
    : score >= 70
      ? "text-finance-blue"
      : "text-foreground";
}

/** 移动端股票卡片 */
function StockCard({ stock, onClick }: { stock: Stock; onClick: () => void }) {
  return (
    <Card
      onClick={onClick}
      className="cursor-pointer rounded-lg p-4 shadow-sm transition-colors gap-3 active:bg-accent/40"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-finance-blue-soft text-xs tabular-nums text-finance-blue">
            {stock.rank}
          </span>
          <div>
            <div className="text-foreground leading-tight">{stock.name}</div>
            <div className="text-xs text-neutral tabular-nums">{stock.code}</div>
          </div>
        </div>
        <div className="text-right">
          <div className={`text-xl tabular-nums leading-none ${scoreColor(stock.totalScore)}`}>
            {stock.totalScore}
          </div>
          <div className="text-xs text-neutral">总分</div>
        </div>
      </div>

      <div className="flex items-end justify-between">
        <div className="flex items-baseline gap-2">
          <span className="text-lg tabular-nums text-foreground">
            {stock.price.toFixed(2)}
          </span>
          <ChangeText value={stock.changePct} className="text-sm" />
        </div>
        <ChevronRight className="size-4 text-neutral" />
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <EntryTag timing={stock.entryTiming} />
        {stock.risks.length > 0 ? (
          stock.risks.slice(0, 2).map((r) => <RiskTag key={r.label} risk={r} />)
        ) : (
          <NoRiskTag />
        )}
      </div>

      {stock.exitStrategy && (
        <div className="rounded-md bg-neutral-soft/60 px-2 py-1.5 text-xs text-neutral">
          短线计划：1日盈{stock.day1TakeProfitPrice?.toFixed(2) ?? "-"} / 损{stock.day1StopLossPrice?.toFixed(2) ?? "-"}；2日盈{stock.day2TakeProfitPrice?.toFixed(2) ?? "-"} / 损{stock.day2StopLossPrice?.toFixed(2) ?? "-"}
        </div>
      )}
      <div className="rounded-md bg-finance-blue-soft/45 px-2 py-1.5 text-xs text-finance-blue">
        明日：{stock.buyAction || "轻仓观察"} · 最高追价 {stock.maxBuyPrice?.toFixed(2) ?? "-"}
      </div>
      <div className="text-xs leading-relaxed text-neutral">
        入选：{stock.selectionReason || "综合规则排序靠前"}
      </div>
    </Card>
  );
}

export function StockList({
  stocks,
  onSelect,
}: {
  stocks: Stock[];
  onSelect: (s: Stock) => void;
}) {
  return (
    <>
      {/* 移动端：卡片 */}
      <div className="grid gap-3 sm:grid-cols-2 lg:hidden">
        {stocks.map((s) => (
          <StockCard key={s.code} stock={s} onClick={() => onSelect(s)} />
        ))}
      </div>

      {/* 桌面端：表格 */}
      <Card className="hidden overflow-hidden rounded-lg p-0 shadow-sm lg:block">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-neutral-soft/60 hover:bg-neutral-soft/60">
                {[
                  "#", "名称", "代码", "现价", "涨跌幅", "总分", "趋势", "量能",
                  "DMI", "MACD", "EXPMA", "资金", "板块", "上下文", "入场", "明日动作", "卖出计划", "风险",
                ].map((h) => (
                  <TableHead
                    key={h}
                    className="whitespace-nowrap text-neutral"
                  >
                    {h}
                  </TableHead>
                ))}
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {stocks.map((s) => (
                <TableRow
                  key={s.code}
                  onClick={() => onSelect(s)}
                  className="cursor-pointer"
                >
                  <TableCell className="tabular-nums text-neutral">{s.rank}</TableCell>
                  <TableCell className="whitespace-nowrap text-foreground">{s.name}</TableCell>
                  <TableCell className="tabular-nums text-neutral">{s.code}</TableCell>
                  <TableCell className="tabular-nums">{s.price.toFixed(2)}</TableCell>
                  <TableCell><ChangeText value={s.changePct} /></TableCell>
                  <TableCell className={`tabular-nums ${scoreColor(s.totalScore)}`}>{s.totalScore}</TableCell>
                  <TableCell className="tabular-nums text-neutral">{s.trendScore}</TableCell>
                  <TableCell className="tabular-nums text-neutral">{s.volumeScore}</TableCell>
                  <TableCell className="tabular-nums text-neutral">{s.dmiScore}</TableCell>
                  <TableCell className="tabular-nums text-neutral">{s.macdScore}</TableCell>
                  <TableCell className="tabular-nums text-neutral">{s.expmaScore}</TableCell>
                  <TableCell className="tabular-nums text-neutral">{s.moneyFlowScore}</TableCell>
                  <TableCell className="tabular-nums text-neutral">{s.sectorScore}</TableCell>
                  <TableCell className="tabular-nums text-neutral">{s.contextScore}</TableCell>
                  <TableCell><EntryTag timing={s.entryTiming} /></TableCell>
                  <TableCell className="whitespace-nowrap text-xs text-finance-blue">
                    {s.buyAction || "观察"} / ≤{s.maxBuyPrice?.toFixed(2) ?? "-"}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-xs text-neutral">
                    {s.exitStrategy
                      ? `1日盈${s.day1TakeProfitPrice?.toFixed(2) ?? "-"}/损${s.day1StopLossPrice?.toFixed(2) ?? "-"} · 2日盈${s.day2TakeProfitPrice?.toFixed(2) ?? "-"}/损${s.day2StopLossPrice?.toFixed(2) ?? "-"}`
                      : "-"}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    {s.risks.length > 0 ? (
                      <span className="text-xs text-risk">{s.risks[0].label}{s.risks.length > 1 ? ` +${s.risks.length - 1}` : ""}</span>
                    ) : (
                      <span className="text-xs text-down">无</span>
                    )}
                  </TableCell>
                  <TableCell><ChevronRight className="size-4 text-neutral" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>
    </>
  );
}
