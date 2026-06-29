import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { FunnelBar, SectionTitle } from "./shared";
import type { BacktestData, DailyReport } from "../../data/types";

const BLUE = "#1f4e78";
const PALETTE = ["#1f4e78", "#3a6ea5", "#5c8fc0", "#d23b3b", "#e08a2b", "#1f9e6e", "#5c7184", "#8aa6bd"];

function ChartCard({
  title,
  desc,
  children,
}: {
  title: string;
  desc?: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="rounded-lg p-4 shadow-sm">
      <SectionTitle title={title} desc={desc} />
      {children}
    </Card>
  );
}

export function ChartsSection({
  report,
  backtest,
  selectedSector,
  onSectorSelect,
}: {
  report: DailyReport;
  backtest?: BacktestData;
  selectedSector?: string;
  onSectorSelect?: (sector: string) => void;
}) {
  const top = report.stocks.slice(0, 20);
  const scoreData = top.map((s) => ({ name: s.name, 总分: s.totalScore }));
  const stackData = top.slice(0, 10).map((s) => ({
    name: s.name,
    趋势: s.trendScore,
    量能: s.volumeScore,
    DMI: s.dmiScore,
    MACD: s.macdScore,
    EXPMA: s.expmaScore,
    资金: s.moneyFlowScore,
    板块: s.sectorScore,
  }));
  const scatterData = top.map((s) => ({
    name: s.name,
    adx: s.adx,
    vol: s.volRatio,
    score: s.totalScore,
  }));
  const funnelMax = report.funnel[0].count;
  const stackKeys = ["趋势", "量能", "DMI", "MACD", "EXPMA", "资金", "板块"];

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <HotSectorCard
        report={report}
        selectedSector={selectedSector}
        onSectorSelect={onSectorSelect}
      />

      <ChartCard title="Top20 综合评分" desc="按总分排序的入选股票">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={scoreData} margin={{ left: -10, bottom: 50 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e9ee" />
            <XAxis dataKey="name" angle={-45} textAnchor="end" interval={0} tick={{ fontSize: 11, fill: "#5c7184" }} height={60} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#5c7184" }} />
            <Tooltip cursor={{ fill: "rgba(31,78,120,0.06)" }} />
            <Bar dataKey="总分" radius={[3, 3, 0, 0]}>
              {scoreData.map((d, i) => (
                <Cell key={i} fill={d.总分 >= 80 ? "#d23b3b" : BLUE} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="评分拆解（Top10）" desc="各因子得分堆叠">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={stackData} margin={{ left: -10, bottom: 50 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e9ee" />
            <XAxis dataKey="name" angle={-45} textAnchor="end" interval={0} tick={{ fontSize: 11, fill: "#5c7184" }} height={60} />
            <YAxis tick={{ fontSize: 11, fill: "#5c7184" }} />
            <Tooltip cursor={{ fill: "rgba(31,78,120,0.06)" }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {stackKeys.map((k, i) => (
              <Bar key={k} dataKey={k} stackId="a" fill={PALETTE[i]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="ADX vs 量比" desc="趋势强度与放量程度分布">
        <ResponsiveContainer width="100%" height={300}>
          <ScatterChart margin={{ left: -10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e9ee" />
            <XAxis type="number" dataKey="adx" name="ADX" tick={{ fontSize: 11, fill: "#5c7184" }} label={{ value: "ADX", position: "insideBottom", offset: -4, fontSize: 11, fill: "#5c7184" }} />
            <YAxis type="number" dataKey="vol" name="量比" tick={{ fontSize: 11, fill: "#5c7184" }} />
            <ZAxis type="number" dataKey="score" range={[40, 280]} />
            <Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={(v, n) => [v, n]} labelFormatter={() => ""} />
            <Scatter data={scatterData} fill={BLUE} fillOpacity={0.65} />
          </ScatterChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="技术筛选漏斗" desc="从全市场到最终入选的逐级筛选">
        <div className="space-y-2.5 pt-1">
          {report.funnel.map((f) => (
            <FunnelBar key={f.stage} stage={f.stage} count={f.count} max={funnelMax} />
          ))}
        </div>
      </ChartCard>

      <ChartCard title="行业分布" desc="入选股票所属板块">
        <ResponsiveContainer width="100%" height={Math.max(220, report.industryDist.length * 30)}>
          <BarChart data={report.industryDist} layout="vertical" margin={{ left: 30 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e5e9ee" />
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "#5c7184" }} />
            <YAxis type="category" dataKey="sector" width={70} tick={{ fontSize: 11, fill: "#5c7184" }} />
            <Tooltip cursor={{ fill: "rgba(31,78,120,0.06)" }} />
            <Bar dataKey="count" name="数量" radius={[0, 3, 3, 0]} fill={BLUE} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <AccuracySummaryCard data={backtest} />
    </div>
  );
}

function formatAmount(value: number) {
  if (!value) return "-";
  return `${(value / 100000000).toFixed(1)}亿`;
}

function HotSectorCard({
  report,
  selectedSector,
  onSectorSelect,
}: {
  report: DailyReport;
  selectedSector?: string;
  onSectorSelect?: (sector: string) => void;
}) {
  const sectors = report.hotSectors ?? [];
  if (sectors.length === 0) {
    return (
      <Card className="rounded-lg border-dashed p-4 shadow-sm lg:col-span-2">
        <SectionTitle title="今日热门领涨板块" desc="暂无板块热度数据，等待后端生成 hot_sectors 文件" />
        <p className="text-sm text-neutral">运行最新版选股程序后会自动生成热门板块榜。</p>
      </Card>
    );
  }
  const topScore = Math.max(...sectors.map((s) => s.heatScore), 1);

  return (
    <Card className="rounded-lg p-5 shadow-sm lg:col-span-2">
      <SectionTitle
        title="今日热门领涨板块"
        desc="热度分综合板块涨幅、上涨占比、成交额、换手与领涨股强度"
      />
      <div className="grid gap-3 md:grid-cols-2">
        {sectors.slice(0, 6).map((s) => (
          <button
            key={`${s.rank}-${s.name}`}
            type="button"
            onClick={() => onSectorSelect?.(s.name)}
            className={`rounded-lg border p-3 text-left transition-colors ${
              selectedSector === s.name
                ? "border-finance-blue bg-finance-blue-soft"
                : "border-border bg-card hover:bg-neutral-soft/50"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-finance-blue-soft text-xs tabular-nums text-finance-blue">
                    {s.rank}
                  </span>
                  <span className="truncate text-foreground">{s.name}</span>
                  {s.selectedCount > 0 && (
                    <Badge variant="outline" className="text-finance-blue">
                      入选 {s.selectedCount}
                    </Badge>
                  )}
                </div>
                <div className="mt-1 text-xs text-neutral">
                  领涨：{s.leaderName || "-"} {s.leaderPctChange ? `${s.leaderPctChange.toFixed(2)}%` : ""}
                </div>
              </div>
              <div className="text-right">
                <div className="text-lg tabular-nums text-finance-blue">{s.heatScore.toFixed(1)}</div>
                <div className="text-xs text-neutral">热度分</div>
              </div>
            </div>

            <div className="mt-3 h-2 overflow-hidden rounded-full bg-neutral-soft">
              <div
                className="h-full rounded-full bg-finance-blue"
                style={{ width: `${Math.max(8, (s.heatScore / topScore) * 100)}%` }}
              />
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
              <div className="rounded-md bg-neutral-soft/50 p-2">
                <div className="text-neutral">板块涨幅</div>
                <div className={`mt-0.5 tabular-nums ${s.pctChange >= 0 ? "text-up" : "text-risk"}`}>
                  {s.pctChange.toFixed(2)}%
                </div>
              </div>
              <div className="rounded-md bg-neutral-soft/50 p-2">
                <div className="text-neutral">上涨占比</div>
                <div className="mt-0.5 tabular-nums text-foreground">{s.upRatio.toFixed(1)}%</div>
              </div>
              <div className="rounded-md bg-neutral-soft/50 p-2">
                <div className="text-neutral">成交额</div>
                <div className="mt-0.5 tabular-nums text-foreground">{formatAmount(s.amount)}</div>
              </div>
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-neutral">
              {s.quantNote || `${s.upCount}涨 / ${s.downCount}跌，来源：${s.dataSource || "板块数据"}`}
            </p>
          </button>
        ))}
      </div>
    </Card>
  );
}

/** 准确性评估摘要卡片（入口） */
function AccuracySummaryCard({ data }: { data?: BacktestData }) {
  const perf = data?.holdingPerf ?? [];
  const first = perf[0];
  const second = perf[1];
  const third = perf[2];
  return (
    <Card className="rounded-lg border-dashed p-4 shadow-sm">
      <SectionTitle title="准确性评估" desc="基于已成熟历史样本的未来表现" />
      <div className="grid grid-cols-2 gap-2 text-sm">
        {[
          [first?.period || "最短持有期", first ? `${first.winRate}%` : "暂无"],
          [second?.period || "次短持有期", second ? `${second.winRate}%` : "暂无"],
          ["平均收益", data ? `${data.overview.avgReturn >= 0 ? "+" : ""}${data.overview.avgReturn}%` : "暂无"],
          ["平均超额", data ? `${data.overview.avgExcess >= 0 ? "+" : ""}${data.overview.avgExcess}%` : "暂无"],
        ].map(([k, v]) => (
          <div key={k} className="rounded-md bg-neutral-soft/50 p-2.5">
            <div className="text-xs text-neutral">{k}</div>
            <div className="mt-0.5 tabular-nums text-foreground">{v}</div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs leading-relaxed text-neutral">
        {third ? `另有 ${third.period} 胜率 ${third.winRate}%。` : "当前样本仍在积累中。"}
        完整胜率、收益与因子预测力请见
        <b className="text-finance-blue"> “准确率回测” </b>标签页。
      </p>
    </Card>
  );
}
