// 共享展示组件：数据卡片、评分条、风险标签、漏斗条、入场标签、涨跌数字。
import type { ReactNode } from "react";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { Card } from "../ui/card";
import { cn } from "../ui/utils";
import type { EntryTiming, RiskFlag } from "../../data/types";

/** 涨跌幅 / 收益数字，遵循 A股 红涨绿跌 */
export function ChangeText({
  value,
  suffix = "%",
  className,
  showSign = true,
}: {
  value: number | null;
  suffix?: string;
  className?: string;
  showSign?: boolean;
}) {
  if (value === null || Number.isNaN(value)) {
    return <span className={cn("text-neutral", className)}>—</span>;
  }
  const tone = value > 0 ? "text-up" : value < 0 ? "text-down" : "text-neutral";
  const sign = showSign && value > 0 ? "+" : "";
  return (
    <span className={cn("tabular-nums", tone, className)}>
      {sign}
      {value.toFixed(2)}
      {suffix}
    </span>
  );
}

/** 数据概览卡片 */
export function DataCard({
  label,
  value,
  sub,
  tone = "neutral",
  icon,
}: {
  label: string;
  value: ReactNode;
  sub?: string;
  tone?: "neutral" | "up" | "down" | "risk" | "primary";
  icon?: ReactNode;
}) {
  const valueTone = {
    neutral: "text-foreground",
    up: "text-up",
    down: "text-down",
    risk: "text-risk",
    primary: "text-finance-blue",
  }[tone];
  return (
    <Card className="rounded-lg border-border/70 p-4 shadow-sm gap-2">
      <div className="flex items-center justify-between text-neutral">
        <span className="text-sm">{label}</span>
        {icon}
      </div>
      <div className={cn("text-2xl tabular-nums leading-none", valueTone)}>
        {value}
      </div>
      {sub && <div className="text-xs text-neutral">{sub}</div>}
    </Card>
  );
}

/** 评分条 0-100 */
export function ScoreBar({
  score,
  max = 100,
  label,
  compact = false,
}: {
  score: number;
  max?: number;
  label?: string;
  compact?: boolean;
}) {
  const pct = Math.max(0, Math.min(100, (score / max) * 100));
  const color =
    pct >= 80 ? "var(--finance-blue)" : pct >= 60 ? "#4a7aa8" : "var(--neutral)";
  return (
    <div className="flex items-center gap-2">
      {label && (
        <span className="w-16 shrink-0 text-xs text-neutral">{label}</span>
      )}
      <div
        className={cn(
          "relative flex-1 overflow-hidden rounded-full bg-neutral-soft",
          compact ? "h-1.5" : "h-2",
        )}
      >
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="w-10 shrink-0 text-right text-xs tabular-nums text-foreground">
        {score.toFixed(score % 1 === 0 ? 0 : 1)}
      </span>
    </div>
  );
}

/** 风险标签 */
export function RiskTag({ risk }: { risk: RiskFlag }) {
  const styles = {
    high: "bg-risk-soft text-risk border-risk/30",
    medium: "bg-risk-soft text-risk border-risk/20",
    low: "bg-neutral-soft text-neutral border-border",
  }[risk.level];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs",
        styles,
      )}
    >
      <AlertTriangle className="size-3" />
      {risk.label}
    </span>
  );
}

export function NoRiskTag() {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-down/20 bg-down-soft px-2 py-0.5 text-xs text-down">
      <ShieldCheck className="size-3" />
      暂无风险信号
    </span>
  );
}

/** 入场时机标签 */
export function EntryTag({ timing }: { timing: EntryTiming }) {
  const styles: Record<EntryTiming, string> = {
    积极: "bg-up-soft text-up border-up/30",
    观察: "bg-finance-blue-soft text-finance-blue border-finance-blue/20",
    等待回踩: "bg-neutral-soft text-neutral border-border",
    追高谨慎: "bg-risk-soft text-risk border-risk/30",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs whitespace-nowrap",
        styles[timing],
      )}
    >
      {timing}
    </span>
  );
}

/** 筛选漏斗条 */
export function FunnelBar({
  stage,
  count,
  max,
}: {
  stage: string;
  count: number;
  max: number;
}) {
  const pct = Math.max(4, (count / max) * 100);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-foreground">{stage}</span>
        <span className="tabular-nums text-neutral">{count}</span>
      </div>
      <div className="h-5 w-full overflow-hidden rounded-md bg-neutral-soft">
        <div
          className="flex h-full items-center justify-end rounded-md bg-finance-blue/85 px-2 text-xs text-white transition-all"
          style={{ width: `${pct}%` }}
        >
          {pct > 18 && <span className="tabular-nums">{count}</span>}
        </div>
      </div>
    </div>
  );
}

/** 区块标题 */
export function SectionTitle({
  title,
  desc,
  action,
}: {
  title: string;
  desc?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-3 flex items-end justify-between gap-3">
      <div>
        <h3 className="text-foreground">{title}</h3>
        {desc && <p className="mt-0.5 text-sm text-neutral">{desc}</p>}
      </div>
      {action}
    </div>
  );
}
