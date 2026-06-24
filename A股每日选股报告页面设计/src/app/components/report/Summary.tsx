import {
  AlertTriangle,
  Award,
  Filter,
  Gauge,
  ListChecks,
  Trophy,
} from "lucide-react";
import { Card } from "../ui/card";
import { DataCard } from "./shared";
import type { DailyReport } from "../../data/types";

export function SummaryCards({ report }: { report: DailyReport }) {
  const s = report.summary;
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
      <DataCard
        label="今日入选"
        value={s.selectedCount}
        sub="只候选股票"
        tone="primary"
        icon={<ListChecks className="size-4" />}
      />
      <DataCard
        label="最高分"
        value={s.topStock.score}
        sub={`${s.topStock.name} ${s.topStock.code}`}
        tone="up"
        icon={<Trophy className="size-4" />}
      />
      <DataCard
        label="平均分"
        value={s.avgScore}
        sub="入选股票均值"
        icon={<Gauge className="size-4" />}
      />
      <DataCard
        label="风险提示"
        value={s.riskCount}
        sub="只含风险信号"
        tone="risk"
        icon={<AlertTriangle className="size-4" />}
      />
      <DataCard
        label="80分以上"
        value={s.above80Count}
        sub="只高分标的"
        tone="primary"
        icon={<Award className="size-4" />}
      />
      <DataCard
        label="技术通过率"
        value={`${s.passRate}%`}
        sub="全市场样本"
        icon={<Filter className="size-4" />}
      />
    </div>
  );
}

export function ConclusionPanel({ report }: { report: DailyReport }) {
  const c = report.conclusion;
  const statusStyle = {
    偏强: "bg-up-soft text-up",
    一般: "bg-finance-blue-soft text-finance-blue",
    谨慎: "bg-risk-soft text-risk",
  }[c.status];
  return (
    <Card className="rounded-lg border-l-4 border-l-finance-blue p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-foreground">今日结论</h3>
        <span className={`rounded-md px-2.5 py-1 text-sm ${statusStyle}`}>
          策略状态：{c.status}
        </span>
      </div>
      <p className="text-sm leading-relaxed text-foreground/90">{c.narrative}</p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-md bg-neutral-soft/60 p-3">
          <div className="mb-1.5 text-xs text-neutral">今日入选</div>
          <div className="text-foreground">
            共 <b className="text-finance-blue">{c.selectedCount}</b> 只
          </div>
        </div>
        <div className="rounded-md bg-neutral-soft/60 p-3">
          <div className="mb-1.5 text-xs text-neutral">追高风险</div>
          {c.chaseRisk ? (
            <span className="inline-flex items-center gap-1 text-risk">
              <AlertTriangle className="size-4" /> 存在，注意回踩
            </span>
          ) : (
            <span className="text-down">暂无明显追高风险</span>
          )}
        </div>
        <div className="rounded-md bg-neutral-soft/60 p-3 sm:col-span-2">
          <div className="mb-1.5 text-xs text-neutral">Top5 标的</div>
          <div className="flex flex-wrap gap-2">
            {c.top5.map((s) => (
              <span
                key={s.code}
                className="rounded-md border border-border bg-card px-2 py-1 text-sm"
              >
                {s.name}
                <span className="ml-1 text-xs text-neutral">{s.code}</span>
              </span>
            ))}
          </div>
        </div>
        <div className="rounded-md bg-neutral-soft/60 p-3 sm:col-span-2">
          <div className="mb-1.5 text-xs text-neutral">今日最严格技术条件</div>
          <div className="text-foreground">{c.strictestCondition}</div>
        </div>
      </div>
    </Card>
  );
}
