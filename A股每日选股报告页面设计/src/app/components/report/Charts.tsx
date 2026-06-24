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
import { FunnelBar, SectionTitle } from "./shared";
import type { DailyReport } from "../../data/types";

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

export function ChartsSection({ report }: { report: DailyReport }) {
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

      <AccuracySummaryCard />
    </div>
  );
}

/** 准确性评估摘要卡片（入口） */
function AccuracySummaryCard() {
  return (
    <Card className="rounded-lg border-dashed p-4 shadow-sm">
      <SectionTitle title="准确性评估" desc="未来 3/5/10/20 日表现" />
      <div className="grid grid-cols-2 gap-2 text-sm">
        {[
          ["未来3日胜率", "56.2%"],
          ["未来5日胜率", "58.3%"],
          ["平均收益", "+1.9%"],
          ["平均超额收益", "+0.8%"],
        ].map(([k, v]) => (
          <div key={k} className="rounded-md bg-neutral-soft/50 p-2.5">
            <div className="text-xs text-neutral">{k}</div>
            <div className="mt-0.5 tabular-nums text-foreground">{v}</div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs leading-relaxed text-neutral">
        当前样本仍在积累中，完整胜率、收益与因子预测力请见
        <b className="text-finance-blue"> “准确率回测” </b>标签页。
      </p>
    </Card>
  );
}
