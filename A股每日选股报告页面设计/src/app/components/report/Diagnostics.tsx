import { Card } from "../ui/card";
import { SectionTitle } from "./shared";
import type { DiagnosticItem } from "../../data/types";

function DiagnosticRow({ item }: { item: DiagnosticItem }) {
  const pct = (item.passed / item.total) * 100;
  const color = pct >= 40 ? "#1f4e78" : pct >= 25 ? "#4a7aa8" : "#5c7184";
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="truncate text-foreground">{item.label}</span>
        <span className="shrink-0 tabular-nums text-neutral">
          {item.passed}/{item.total}
          <span className="ml-1.5 text-finance-blue">{pct.toFixed(1)}%</span>
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-soft">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

export function Diagnostics({ items }: { items: DiagnosticItem[] }) {
  return (
    <Card className="rounded-lg p-5 shadow-sm">
      <SectionTitle
        title="技术诊断"
        desc="各筛选条件在全市场样本中的通过数量与通过率"
      />
      <div className="grid gap-x-8 gap-y-3 md:grid-cols-2">
        {items.map((item) => (
          <DiagnosticRow key={item.id} item={item} />
        ))}
      </div>
    </Card>
  );
}
