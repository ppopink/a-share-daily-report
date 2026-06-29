import {
  CalendarDays,
  ChevronDown,
  Copy,
  FileDown,
  History,
  Sheet,
} from "lucide-react";
import { Button } from "../ui/button";
import {
  ToggleGroup,
  ToggleGroupItem,
} from "../ui/toggle-group";
import { Badge } from "../ui/badge";
import type { FilterMode, ReportFiles } from "../../data/types";

const modeLabels: Record<FilterMode, string> = {
  normal: "normal 标准",
  strict: "strict 严格",
  loose: "loose 宽松",
};

export function Header({
  date,
  mode,
  generatedAt,
  onDateChange,
  onModeChange,
  onShare,
  onViewHistory,
  availableDates,
  files,
}: {
  date: string;
  mode: FilterMode;
  generatedAt: string;
  onDateChange: (d: string) => void;
  onModeChange: (m: FilterMode) => void;
  onShare: () => void;
  onViewHistory: () => void;
  availableDates: string[];
  files?: ReportFiles;
}) {
  const dates = availableDates.length ? availableDates : [date];

  return (
    <div className="border-b border-border bg-finance-blue text-white">
      <div className="mx-auto w-full max-w-6xl px-4 py-4 md:py-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-white/15 text-lg">
              A股
            </div>
            <div>
              <h1 className="text-white leading-tight">A股每日选股报告</h1>
              <p className="mt-0.5 text-sm text-white/70">
                量化规则跟踪 · 生成于 {generatedAt}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <label className="relative inline-flex h-9 items-center">
              <span className="sr-only">切换报告日期</span>
              <CalendarDays className="pointer-events-none absolute left-3 size-4 text-white" />
              <select
                aria-label="切换报告日期"
                value={date}
                onChange={(event) => onDateChange(event.target.value)}
                className="h-9 cursor-pointer appearance-none rounded-md border-0 bg-white/15 pl-9 pr-8 text-sm font-medium text-white outline-none transition-colors hover:bg-white/25 focus:bg-white/25 focus:ring-2 focus:ring-white/50"
              >
                {dates.map((d, index) => (
                  <option key={d} value={d} style={{ color: "#172033" }}>
                    {d}
                    {index === 0 ? " 今天" : ""}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 size-4 text-white/70" />
            </label>

            <ToggleGroup
              type="single"
              value={mode}
              onValueChange={(v) => v && onModeChange(v as FilterMode)}
              className="rounded-md bg-white/10 p-0.5"
            >
              {(["loose", "normal", "strict"] as FilterMode[]).map((m) => (
                <ToggleGroupItem
                  key={m}
                  value={m}
                  className="h-8 px-2.5 text-xs text-white/80 data-[state=on]:bg-white data-[state=on]:text-finance-blue"
                >
                  {m}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Badge className="bg-white/15 text-white border-0">
            筛选模式：{modeLabels[mode]}
          </Badge>
          <div className="flex-1" />
          <Button
            size="sm"
            variant="secondary"
            asChild={Boolean(files?.pdf)}
            disabled={!files?.pdf}
            className="h-8 gap-1.5 bg-white text-finance-blue hover:bg-white/90"
          >
            {files?.pdf ? (
              <a href={files.pdf} download>
                <FileDown className="size-4" /> PDF
              </a>
            ) : (
              <>
                <FileDown className="size-4" /> PDF
              </>
            )}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            asChild={Boolean(files?.excel)}
            disabled={!files?.excel}
            className="h-8 gap-1.5 bg-white text-finance-blue hover:bg-white/90"
          >
            {files?.excel ? (
              <a href={files.excel} download>
                <Sheet className="size-4" /> Excel
              </a>
            ) : (
              <>
                <Sheet className="size-4" /> Excel
              </>
            )}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            className="h-8 gap-1.5 bg-white/15 text-white hover:bg-white/25 border-0"
            onClick={onShare}
          >
            <Copy className="size-4" /> 复制摘要
          </Button>
          <Button
            size="sm"
            variant="secondary"
            className="h-8 gap-1.5 bg-white/15 text-white hover:bg-white/25 border-0"
            onClick={onViewHistory}
          >
            <History className="size-4" /> 历史
          </Button>
        </div>
      </div>
    </div>
  );
}

export function DisclaimerBar() {
  return (
    <div className="border-b border-risk/20 bg-risk-soft">
      <div className="mx-auto w-full max-w-6xl px-4 py-2.5">
        <p className="text-xs leading-relaxed text-risk">
          ⚠️ 本报告仅为量化规则选股跟踪和学习交流，<b>不构成投资建议</b>
          。信号基于收盘后数据，默认 T+1 开盘观察，历史表现不代表未来收益。
        </p>
      </div>
    </div>
  );
}
