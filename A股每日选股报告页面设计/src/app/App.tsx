import { useEffect, useState } from "react";
import { toast, Toaster } from "sonner";
import { BarChart3, CalendarRange, FileText, LineChart } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import { Header, DisclaimerBar } from "./components/report/Header";
import { SummaryCards, ConclusionPanel } from "./components/report/Summary";
import { StockList } from "./components/report/StockList";
import { StockDetailDialog } from "./components/report/StockDetailDialog";
import { ChartsSection } from "./components/report/Charts";
import { Diagnostics } from "./components/report/Diagnostics";
import { ShareSummary, buildShareText } from "./components/report/ShareSummary";
import { BacktestTab } from "./components/report/BacktestTab";
import { HistoryTab } from "./components/report/HistoryTab";
import { StrategyTab } from "./components/report/StrategyTab";
import { SectionTitle } from "./components/report/shared";
import { backtestData, historyList, todayReport } from "./data/mock";
import type { BacktestData, DailyReport, FilterMode, HistoryEntry, Stock } from "./data/types";

const tabs = [
  { id: "today", label: "今日选股", icon: FileText },
  { id: "backtest", label: "准确率回测", icon: BarChart3 },
  { id: "history", label: "历史报告", icon: CalendarRange },
  { id: "strategy", label: "策略说明", icon: LineChart },
];

type ReportIndex = {
  latestDate?: string;
  availableDates?: string[];
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

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(`${publicUrl(url)}?v=${Date.now()}`);
  if (!res.ok) {
    throw new Error(`load failed: ${url}`);
  }
  return res.json();
}

export default function App() {
  const [tab, setTab] = useState("today");
  const [date, setDate] = useState(todayReport.date);
  const [mode, setMode] = useState<FilterMode>(todayReport.mode);
  const [report, setReport] = useState<DailyReport>(todayReport);
  const [availableDates, setAvailableDates] = useState<string[]>(historyList.map((h) => h.date));
  const [history, setHistory] = useState<HistoryEntry[]>(historyList);
  const [backtest, setBacktest] = useState<BacktestData>(backtestData);
  const [dataError, setDataError] = useState("");
  const [selected, setSelected] = useState<Stock | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialData() {
      try {
        const index = await fetchJson<ReportIndex>("data/report_index.json");
        const nextDates = index.availableDates?.length ? index.availableDates : [todayReport.date];
        const urlDate = getDateFromUrl();
        const latest = index.latestDate || nextDates[0] || todayReport.date;
        const targetDate = nextDates.includes(urlDate) ? urlDate : latest;
        const [daily, bt] = await Promise.all([
          fetchJson<DailyReport>(`data/reports/${dateToKey(targetDate)}.json`),
          fetchJson<BacktestData>("data/backtest.json").catch(() => backtestData),
        ]);

        if (cancelled) return;
        setAvailableDates(nextDates);
        setHistory(index.history?.length ? index.history : historyList);
        setBacktest(bt);
        setDate(targetDate);
        setMode(daily.mode);
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
      try {
        const daily = await fetchJson<DailyReport>(`data/reports/${dateToKey(date)}.json`);
        if (cancelled) return;
        setReport(daily);
        setMode(daily.mode);
        setDataError("");
      } catch {
        if (!cancelled) {
          setDataError(`未找到 ${date} 的真实报告数据。`);
        }
      }
    }

    loadDailyReport();
    return () => {
      cancelled = true;
    };
  }, [date, availableDates]);

  const viewReport = { ...report, date, mode };

  const handleDateChange = (nextDate: string) => {
    if (!nextDate || nextDate === date) return;
    setDate(nextDate);

    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("date", nextDate);
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
        onModeChange={setMode}
        onShare={handleShare}
        onViewHistory={() => setTab("history")}
        availableDates={availableDates}
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
            <section>
              <SectionTitle title="今日入选 Top20" desc="点击查看每只股票的详细技术诊断" />
              <StockList stocks={viewReport.stocks} onSelect={openStock} />
            </section>
            <section>
              <SectionTitle title="图表分析" />
              <ChartsSection report={viewReport} />
            </section>
            <Diagnostics items={viewReport.diagnostics} />
            <ShareSummary report={viewReport} />
          </TabsContent>

          <TabsContent value="backtest">
            <BacktestTab data={backtest} />
          </TabsContent>

          <TabsContent value="history">
            <HistoryTab
              list={history}
              onView={(d) => {
                handleDateChange(d);
                setTab("today");
              }}
            />
          </TabsContent>

          <TabsContent value="strategy">
            <StrategyTab />
          </TabsContent>
        </Tabs>
      </main>

      <footer className="border-t border-border bg-card">
        <div className="mx-auto w-full max-w-6xl px-4 py-4 text-center text-xs leading-relaxed text-neutral">
          A股每日选股报告 · 量化规则跟踪与学习交流 · 不构成投资建议 · 历史表现不代表未来收益
        </div>
      </footer>

      <StockDetailDialog
        stock={selected}
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
      />
    </div>
  );
}
