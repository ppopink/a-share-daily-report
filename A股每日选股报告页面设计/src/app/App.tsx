import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { toast, Toaster } from "sonner";
import { BarChart3, CalendarRange, FileText, LineChart } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import { Header, DisclaimerBar } from "./components/report/Header";
import { SummaryCards, ConclusionPanel, DataQualityPanel, ModeComparePanel, ShareSnapshotCard } from "./components/report/Summary";
import { StockList } from "./components/report/StockList";
import { Diagnostics } from "./components/report/Diagnostics";
import { ShareSummary, buildShareText } from "./components/report/ShareSummary";
import { SectionTitle } from "./components/report/shared";
import { backtestData, historyList, todayReport } from "./data/mock";
import type { BacktestData, DailyReport, FilterMode, HistoryEntry, ModeReportSummary, Stock } from "./data/types";

const tabs = [
  { id: "today", label: "今日选股", icon: FileText },
  { id: "backtest", label: "准确率回测", icon: BarChart3 },
  { id: "history", label: "历史报告", icon: CalendarRange },
  { id: "strategy", label: "策略说明", icon: LineChart },
];

const StockDetailDialog = lazy(() =>
  import("./components/report/StockDetailDialog").then((m) => ({ default: m.StockDetailDialog })),
);
const ChartsSection = lazy(() =>
  import("./components/report/Charts").then((m) => ({ default: m.ChartsSection })),
);
const BacktestTab = lazy(() =>
  import("./components/report/BacktestTab").then((m) => ({ default: m.BacktestTab })),
);
const HistoryTab = lazy(() =>
  import("./components/report/HistoryTab").then((m) => ({ default: m.HistoryTab })),
);
const StrategyTab = lazy(() =>
  import("./components/report/StrategyTab").then((m) => ({ default: m.StrategyTab })),
);

type ReportIndex = {
  latestDate?: string;
  availableDates?: string[];
  availableModesByDate?: Record<string, FilterMode[]>;
  history?: HistoryEntry[];
};

function dateToKey(date: string) {
  return date.replaceAll("-", "");
}

function publicUrl(path: string) {
  return `${import.meta.env.BASE_URL}${path.replace(/^\/+/, "")}`;
}

function getDateFromUrl() {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("date") || "";
}

function getModeFromUrl(): FilterMode | "" {
  if (typeof window === "undefined") return "";
  const mode = new URLSearchParams(window.location.search).get("mode");
  return mode === "strict" || mode === "normal" || mode === "loose" ? mode : "";
}

function reportPath(date: string, mode: FilterMode) {
  const key = dateToKey(date);
  return mode === "normal"
    ? `data/reports/${key}_normal.json`
    : `data/reports/${key}_${mode}.json`;
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(`${publicUrl(url)}?v=${Date.now()}`);
  if (!res.ok) {
    throw new Error(`load failed: ${url}`);
  }
  return res.json();
}

function toModeSummary(report: DailyReport): ModeReportSummary {
  return {
    mode: report.mode,
    selectedCount: report.summary.selectedCount,
    avgScore: report.summary.avgScore,
    passRate: report.summary.passRate,
    riskCount: report.summary.riskCount,
    topStock: report.summary.topStock,
  };
}

function LoadingPanel({ label = "加载中..." }: { label?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-5 text-sm text-neutral shadow-sm">
      {label}
    </div>
  );
}

function StockFilterPanel({
  query,
  onQueryChange,
  entryFilter,
  onEntryFilterChange,
  riskFilter,
  onRiskFilterChange,
  scoreFilter,
  onScoreFilterChange,
  actionFilter,
  onActionFilterChange,
  sectors,
  selectedSector,
  onSectorChange,
  resultCount,
}: {
  query: string;
  onQueryChange: (value: string) => void;
  entryFilter: string;
  onEntryFilterChange: (value: string) => void;
  riskFilter: string;
  onRiskFilterChange: (value: string) => void;
  scoreFilter: string;
  onScoreFilterChange: (value: string) => void;
  actionFilter: string;
  onActionFilterChange: (value: string) => void;
  sectors: string[];
  selectedSector: string;
  onSectorChange: (value: string) => void;
  resultCount: number;
}) {
  const controlClass = "h-9 rounded-md border border-border bg-card px-3 text-sm outline-none focus:ring-2 focus:ring-finance-blue/20";
  return (
    <div className="rounded-lg border border-border bg-card p-3 shadow-sm">
      <div className="grid gap-2 md:grid-cols-[minmax(0,1.4fr)_repeat(5,minmax(0,1fr))]">
        <input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="搜索名称 / 代码 / 入选原因"
          className={controlClass}
        />
        <select value={scoreFilter} onChange={(event) => onScoreFilterChange(event.target.value)} className={controlClass}>
          <option value="all">全部分数</option>
          <option value="80">80分以上</option>
          <option value="70">70分以上</option>
        </select>
        <select value={entryFilter} onChange={(event) => onEntryFilterChange(event.target.value)} className={controlClass}>
          <option value="all">全部入场</option>
          <option value="积极">积极</option>
          <option value="观察">观察</option>
          <option value="等待回踩">等待回踩</option>
          <option value="追高谨慎">追高谨慎</option>
        </select>
        <select value={riskFilter} onChange={(event) => onRiskFilterChange(event.target.value)} className={controlClass}>
          <option value="all">全部风险</option>
          <option value="no-risk">无明显风险</option>
          <option value="has-risk">有风险提示</option>
          <option value="recent">近期重复入选</option>
        </select>
        <select value={actionFilter} onChange={(event) => onActionFilterChange(event.target.value)} className={controlClass}>
          <option value="all">全部动作</option>
          <option value="可积极观察">可积极观察</option>
          <option value="轻仓观察">轻仓观察</option>
          <option value="等回踩确认">等回踩确认</option>
        </select>
        <select value={selectedSector} onChange={(event) => onSectorChange(event.target.value)} className={controlClass}>
          <option value="">全部板块</option>
          {sectors.map((sector) => (
            <option key={sector} value={sector}>{sector}</option>
          ))}
        </select>
      </div>
      <div className="mt-2 text-xs text-neutral">当前显示 {resultCount} 只。</div>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("today");
  const [date, setDate] = useState(todayReport.date);
  const [mode, setMode] = useState<FilterMode>(todayReport.mode);
  const [report, setReport] = useState<DailyReport>(todayReport);
  const [availableDates, setAvailableDates] = useState<string[]>(historyList.map((h) => h.date));
  const [availableModesByDate, setAvailableModesByDate] = useState<Record<string, FilterMode[]>>({});
  const [history, setHistory] = useState<HistoryEntry[]>(historyList);
  const [backtest, setBacktest] = useState<BacktestData>(backtestData);
  const [modeSummaries, setModeSummaries] = useState<ModeReportSummary[]>([]);
  const [dataError, setDataError] = useState("");
  const [selected, setSelected] = useState<Stock | null>(null);
  const [selectedSector, setSelectedSector] = useState("");
  const [searchText, setSearchText] = useState("");
  const [entryFilter, setEntryFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");
  const [scoreFilter, setScoreFilter] = useState("all");
  const [actionFilter, setActionFilter] = useState("all");
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialData() {
      try {
        const index = await fetchJson<ReportIndex>("data/report_index.json");
        const nextDates = index.availableDates?.length ? index.availableDates : [todayReport.date];
        const nextModesByDate = index.availableModesByDate || {};
        const urlDate = getDateFromUrl();
        const urlMode = getModeFromUrl();
        const latest = index.latestDate || nextDates[0] || todayReport.date;
        const targetDate = nextDates.includes(urlDate) ? urlDate : latest;
        const modesForDate = nextModesByDate[targetDate] || ["normal"];
        const targetMode = urlMode && modesForDate.includes(urlMode)
          ? urlMode
          : modesForDate.includes("normal")
            ? "normal"
            : modesForDate[0];
        const [daily, bt] = await Promise.all([
          fetchJson<DailyReport>(reportPath(targetDate, targetMode)).catch(() =>
            fetchJson<DailyReport>(`data/reports/${dateToKey(targetDate)}.json`),
          ),
          fetchJson<BacktestData>("data/backtest.json").catch(() => backtestData),
        ]);

        if (cancelled) return;
        setAvailableDates(nextDates);
        setAvailableModesByDate(nextModesByDate);
        setHistory(
          index.history?.length
            ? index.history.map((item) => ({
                ...item,
                availableModes: nextModesByDate[item.date] || ["normal"],
              }))
            : historyList,
        );
        setBacktest(bt);
        setDate(targetDate);
        setMode(daily.mode || targetMode);
        setReport(daily);
        setDataError("");
      } catch {
        if (cancelled) return;
        setDataError("未读取到真实前端数据，当前显示演示数据。请先运行 python main.py --export-frontend。");
      }
    }

    loadInitialData();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadDailyReport() {
      if (!availableDates.includes(date)) return;
      const modesForDate = availableModesByDate[date] || ["normal"];
      if (!modesForDate.includes(mode)) {
        const fallbackMode = modesForDate.includes("normal") ? "normal" : modesForDate[0];
        if (fallbackMode && fallbackMode !== mode) {
          setMode(fallbackMode);
        }
        return;
      }
      try {
        const daily = await fetchJson<DailyReport>(reportPath(date, mode)).catch(() => {
          if (mode === "normal") {
            return fetchJson<DailyReport>(`data/reports/${dateToKey(date)}.json`);
          }
          throw new Error(`missing ${mode} report`);
        });
        if (cancelled) return;
        setReport(daily);
        setDataError("");
      } catch {
        if (!cancelled) {
          setDataError(`未找到 ${date} 的 ${mode} 模式报告数据。请重新运行 python main.py 生成三种模式数据。`);
        }
      }
    }

    loadDailyReport();
    return () => {
      cancelled = true;
    };
  }, [date, mode, availableDates, availableModesByDate]);

  useEffect(() => {
    let cancelled = false;

    async function loadModeSummaries() {
      const modesForDate = availableModesByDate[date] || ["normal"];
      try {
        const summaries = await Promise.all(
          modesForDate.map((m) =>
            fetchJson<DailyReport>(reportPath(date, m)).then(toModeSummary),
          ),
        );
        if (!cancelled) {
          setModeSummaries(summaries);
        }
      } catch {
        if (!cancelled) {
          setModeSummaries([toModeSummary(viewReport)]);
        }
      }
    }

    loadModeSummaries();
    return () => {
      cancelled = true;
    };
  }, [date, availableModesByDate]);

  const viewReport = { ...report, date, mode };
  const availableModesForDate = availableModesByDate[date] || ["normal"];
  const sectors = useMemo(
    () => Array.from(new Set(viewReport.stocks.map((s) => s.sector).filter(Boolean))).sort(),
    [viewReport.stocks],
  );
  const displayedStocks = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    return viewReport.stocks.filter((s) => {
      if (selectedSector && s.sector !== selectedSector) return false;
      if (entryFilter !== "all" && s.entryTiming !== entryFilter) return false;
      if (riskFilter === "no-risk" && s.risks.length > 0) return false;
      if (riskFilter === "has-risk" && s.risks.length === 0) return false;
      if (riskFilter === "recent" && (s.recentPickCount ?? 1) <= 1) return false;
      if (scoreFilter !== "all" && s.totalScore < Number(scoreFilter)) return false;
      if (actionFilter !== "all" && s.buyAction !== actionFilter) return false;
      if (!query) return true;
      const haystack = `${s.name} ${s.code} ${s.sector} ${s.selectionReason || ""} ${s.watchReason || ""}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [actionFilter, entryFilter, riskFilter, scoreFilter, searchText, selectedSector, viewReport.stocks]);

  useEffect(() => {
    setSelectedSector("");
    setSearchText("");
    setEntryFilter("all");
    setRiskFilter("all");
    setScoreFilter("all");
    setActionFilter("all");
  }, [date, mode]);

  const handleDateChange = (nextDate: string) => {
    if (!nextDate || nextDate === date) return;
    const modesForNextDate = availableModesByDate[nextDate] || ["normal"];
    const nextMode = modesForNextDate.includes(mode)
      ? mode
      : modesForNextDate.includes("normal")
        ? "normal"
        : modesForNextDate[0];
    setDate(nextDate);
    setMode(nextMode);

    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("date", nextDate);
      url.searchParams.set("mode", nextMode);
      window.history.replaceState({}, "", url);
    }
  };

  const handleModeChange = (nextMode: FilterMode) => {
    if (nextMode === mode) return;
    if (!availableModesForDate.includes(nextMode)) {
      toast.info(`${date} 暂无 ${nextMode} 模式数据，请重新运行 python main.py 生成。`);
      return;
    }
    setMode(nextMode);

    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("date", date);
      url.searchParams.set("mode", nextMode);
      window.history.replaceState({}, "", url);
    }
  };

  const openStock = (s: Stock) => {
    setSelected(s);
    setDialogOpen(true);
  };

  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(buildShareText(viewReport));
      toast.success("分享摘要已复制到剪贴板");
    } catch {
      toast.info("请在分享摘要区手动复制");
      setTab("today");
    }
  };

  return (
    <div className="min-h-screen w-full bg-background text-foreground">
      <Toaster position="top-center" richColors />
      <Header
        date={date}
        mode={mode}
        generatedAt={report.generatedAt}
        onDateChange={handleDateChange}
        onModeChange={handleModeChange}
        onShare={handleShare}
        onViewHistory={() => setTab("history")}
        availableDates={availableDates}
        availableModes={availableModesForDate}
        files={report.files}
      />
      <DisclaimerBar />

      <main className="mx-auto w-full max-w-6xl px-4 py-5">
        {dataError && (
          <div className="mb-4 rounded-md border border-risk/20 bg-risk-soft px-3 py-2 text-sm text-risk">
            {dataError}
          </div>
        )}
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="mb-5 grid h-auto w-full grid-cols-2 gap-1 bg-neutral-soft/70 p-1 sm:inline-flex sm:w-auto">
            {tabs.map((t) => (
              <TabsTrigger
                key={t.id}
                value={t.id}
                className="gap-1.5 data-[state=active]:bg-card data-[state=active]:text-finance-blue"
              >
                <t.icon className="size-4" />
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>

          <TabsContent value="today" className="space-y-6">
            <SummaryCards report={viewReport} />
            <ConclusionPanel report={viewReport} />
            <ShareSnapshotCard report={viewReport} />
            <ModeComparePanel
              summaries={modeSummaries}
              currentMode={mode}
              onModeChange={handleModeChange}
            />
            <DataQualityPanel report={viewReport} />
            <section>
              <div className="flex flex-wrap items-end justify-between gap-2">
                <SectionTitle
                  title={selectedSector ? `${selectedSector} 入选股` : "今日入选 Top20"}
                  desc="点击查看每只股票的详细技术诊断"
                />
                {selectedSector && (
                  <button
                    type="button"
                    onClick={() => setSelectedSector("")}
                    className="rounded-md border border-border bg-card px-3 py-1.5 text-sm text-neutral hover:bg-neutral-soft"
                  >
                    清除板块筛选
                  </button>
                )}
              </div>
              <StockFilterPanel
                query={searchText}
                onQueryChange={setSearchText}
                entryFilter={entryFilter}
                onEntryFilterChange={setEntryFilter}
                riskFilter={riskFilter}
                onRiskFilterChange={setRiskFilter}
                scoreFilter={scoreFilter}
                onScoreFilterChange={setScoreFilter}
                actionFilter={actionFilter}
                onActionFilterChange={setActionFilter}
                sectors={sectors}
                selectedSector={selectedSector}
                onSectorChange={setSelectedSector}
                resultCount={displayedStocks.length}
              />
              <StockList stocks={displayedStocks} onSelect={openStock} />
            </section>
            <section>
              <SectionTitle title="图表分析" />
              <Suspense fallback={<LoadingPanel label="图表加载中..." />}>
                <ChartsSection
                  report={viewReport}
                  backtest={backtest}
                  selectedSector={selectedSector}
                  onSectorSelect={setSelectedSector}
                />
              </Suspense>
            </section>
            <Diagnostics items={viewReport.diagnostics} />
            <ShareSummary report={viewReport} />
          </TabsContent>

          <TabsContent value="backtest">
            <Suspense fallback={<LoadingPanel label="回测数据加载中..." />}>
              <BacktestTab data={backtest} />
            </Suspense>
          </TabsContent>

          <TabsContent value="history">
            <Suspense fallback={<LoadingPanel label="历史报告加载中..." />}>
              <HistoryTab
                list={history}
                onView={(d) => {
                  handleDateChange(d);
                  setTab("today");
                }}
              />
            </Suspense>
          </TabsContent>

          <TabsContent value="strategy">
            <Suspense fallback={<LoadingPanel label="策略说明加载中..." />}>
              <StrategyTab />
            </Suspense>
          </TabsContent>
        </Tabs>
      </main>

      <footer className="border-t border-border bg-card">
        <div className="mx-auto w-full max-w-6xl px-4 py-4 text-center text-xs leading-relaxed text-neutral">
          A股每日选股报告 · 量化规则跟踪与学习交流 · 不构成投资建议 · 历史表现不代表未来收益
        </div>
      </footer>

      <Suspense fallback={null}>
        <StockDetailDialog
          stock={selected}
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
        />
      </Suspense>
    </div>
  );
}
