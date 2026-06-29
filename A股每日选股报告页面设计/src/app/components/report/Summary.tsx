import {
  AlertTriangle,
  Award,
  Filter,
  Gauge,
  ListChecks,
  ShieldAlert,
  Trophy,
} from "lucide-react";
import { Card } from "../ui/card";
import { DataCard } from "./shared";
import type { DailyReport, FilterMode, ModeReportSummary } from "../../data/types";

export function SummaryCards({ report }: { report: DailyReport }) {
  const s = report.summary;
  const market = report.marketGuard;
  const marketTone =
    market?.riskLevel === "high" ? "risk" : market?.riskLevel === "low" ? "up" : "primary";
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-7">
      <DataCard
        label="市场闸门"
        value={market?.tradePermission || "谨慎"}
        sub={market?.positionAdvice || "轻仓观察"}
        tone={marketTone}
        icon={<ShieldAlert className="size-4" />}
      />
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
      {report.marketGuard && (
        <p className="mt-2 text-sm leading-relaxed text-foreground/90">
          <b>市场风控：</b>{c.marketAdvice || report.marketGuard.marketNote}
        </p>
      )}

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

const modeNames: Record<FilterMode, string> = {
  strict: "严格",
  normal: "标准",
  loose: "宽松",
};

export function ModeComparePanel({
  summaries,
  currentMode,
  onModeChange,
}: {
  summaries: ModeReportSummary[];
  currentMode: FilterMode;
  onModeChange: (mode: FilterMode) => void;
}) {
  if (!summaries.length) return null;

  return (
    <Card className="rounded-lg p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-foreground">模式对比</h3>
          <p className="mt-0.5 text-sm text-neutral">
            strict 找强信号，normal 做日常主策略，loose 做观察池。
          </p>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {summaries.map((s) => {
          const active = s.mode === currentMode;
          return (
            <button
              key={s.mode}
              type="button"
              onClick={() => onModeChange(s.mode)}
              className={`rounded-lg border p-4 text-left transition-colors ${
                active
                  ? "border-finance-blue bg-finance-blue-soft"
                  : "border-border bg-card hover:bg-neutral-soft/50"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-foreground">{modeNames[s.mode]}模式</span>
                <span className="rounded-md bg-white/70 px-2 py-0.5 text-xs text-finance-blue">
                  {s.mode}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <div>
                  <div className="text-xs text-neutral">入选</div>
                  <div className="tabular-nums text-foreground">{s.selectedCount}只</div>
                </div>
                <div>
                  <div className="text-xs text-neutral">均分</div>
                  <div className="tabular-nums text-finance-blue">{s.avgScore}</div>
                </div>
                <div>
                  <div className="text-xs text-neutral">通过率</div>
                  <div className="tabular-nums text-foreground">{s.passRate}%</div>
                </div>
                <div>
                  <div className="text-xs text-neutral">风险提示</div>
                  <div className="tabular-nums text-risk">{s.riskCount}</div>
                </div>
              </div>
              <div className="mt-3 rounded-md bg-background/70 px-2 py-1.5 text-xs text-neutral">
                最高分：{s.topStock.name} {s.topStock.score || "-"}
              </div>
            </button>
          );
        })}
      </div>
    </Card>
  );
}

export function ShareSnapshotCard({ report }: { report: DailyReport }) {
  const top3 = report.stocks.slice(0, 3);
  return (
    <Card className="rounded-lg border-finance-blue/15 bg-finance-blue-soft/35 p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm text-neutral">手机分享摘要</div>
          <h3 className="mt-1 text-foreground">
            {report.date} · {report.mode} · {report.marketGuard?.tradePermission || "谨慎"}
          </h3>
          <p className="mt-1 text-sm leading-relaxed text-neutral">
            {report.marketGuard?.marketNote || report.conclusion.narrative}
          </p>
        </div>
        <div className="rounded-lg bg-card px-3 py-2 text-right">
          <div className="text-xs text-neutral">入选</div>
          <div className="text-2xl tabular-nums text-finance-blue">{report.summary.selectedCount}</div>
        </div>
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {top3.map((s) => (
          <div key={s.code} className="rounded-md bg-card/80 p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-foreground">{s.name}</span>
              <span className="tabular-nums text-finance-blue">{s.totalScore}</span>
            </div>
            <div className="mt-1 text-xs text-neutral">{s.code} · {s.buyAction || "观察"}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

export function DataQualityPanel({ report }: { report: DailyReport }) {
  const q = report.dataQuality;
  if (!q) return null;

  return (
    <Card className="rounded-lg p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-foreground">数据质量提示</h3>
          <p className="mt-0.5 text-sm text-neutral">
            这些提示用于判断哪些分数应谨慎解读。
          </p>
        </div>
      </div>
      <div className="grid gap-2 sm:grid-cols-4">
        {[
          ["资金流覆盖", `${q.moneyFlowCoveragePct}%`, q.moneyFlowStatus],
          ["上下文覆盖", `${q.contextCoveragePct}%`, q.contextStatus],
          ["行业覆盖", `${q.industryCoveragePct}%`, q.industryStatus],
          ["板块来源", q.hotSectorSource || "-", "热门板块数据源"],
        ].map(([label, value, sub]) => (
          <div key={label} className="rounded-md bg-neutral-soft/60 p-3">
            <div className="text-xs text-neutral">{label}</div>
            <div className="mt-1 truncate text-foreground">{value}</div>
            <div className="mt-0.5 truncate text-xs text-neutral">{sub}</div>
          </div>
        ))}
      </div>
      <ul className="mt-3 space-y-1 text-xs leading-relaxed text-neutral">
        {q.notes.map((note) => (
          <li key={note}>- {note}</li>
        ))}
      </ul>
    </Card>
  );
}
