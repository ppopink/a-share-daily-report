import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Hourglass, Info } from "lucide-react";
import { Card } from "../ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../ui/table";
import { Badge } from "../ui/badge";
import { ChangeText, DataCard, SectionTitle } from "./shared";
import type {
  BacktestData,
  BacktestDetail,
  DetailStatus,
} from "../../data/types";

export function BacktestTab({ data }: { data: BacktestData }) {
  const matureSample = data.validCount >= 100; // 演示阈值
  return (
    <div className="space-y-4">
      <BacktestHeader data={data} />
      {!matureSample && <SampleNotMature />}
      <Overview data={data} />
      <ShortTermAccuracy data={data} />
      <HoldingPerf data={data} />
      <EquityCurve data={data} />
      <LayerPerf data={data} />
      <FactorIC data={data} />
      <DetailTable rows={data.details} />
      <Credibility />
    </div>
  );
}

function ShortTermAccuracy({ data }: { data: BacktestData }) {
  const rows = data.holdingPerf.slice(0, 3);
  if (!rows.length) return null;
  return (
    <Card className="rounded-lg p-5 shadow-sm">
      <SectionTitle title="短线准确率摘要" desc="优先看最短几个持有周期，适合 1/2/3 日短线决策复盘" />
      <div className="grid gap-3 md:grid-cols-3">
        {rows.map((p) => (
          <div key={p.period} className="rounded-lg border border-border p-4">
            <div className="flex items-center justify-between">
              <span className="text-foreground">{p.period}</span>
              <Badge variant="outline" className="text-neutral">{p.samples} 样本</Badge>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <div>
                <div className="text-xs text-neutral">胜率</div>
                <div className="tabular-nums text-finance-blue">{p.winRate}%</div>
              </div>
              <div>
                <div className="text-xs text-neutral">平均收益</div>
                <ChangeText value={p.avgReturn} />
              </div>
              <div>
                <div className="text-xs text-neutral">平均超额</div>
                <ChangeText value={p.avgExcess} />
              </div>
              <div>
                <div className="text-xs text-neutral">最大回撤</div>
                <ChangeText value={p.maxDrawdown} />
              </div>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs leading-relaxed text-neutral">
        这里展示的是历史预测命中情况，不是未来收益承诺；样本不足时优先看方向和回撤，不要只看单一胜率。
      </p>
    </Card>
  );
}

function BacktestHeader({ data }: { data: BacktestData }) {
  const statusStyle = {
    样本不足: "bg-risk-soft text-risk",
    样本成熟: "bg-down-soft text-down",
    需要继续观察: "bg-finance-blue-soft text-finance-blue",
  }[data.sampleStatus];
  return (
    <Card className="rounded-lg p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-foreground">准确率回测</h3>
          <p className="mt-0.5 text-sm text-neutral">
            回测区间 {data.rangeStart} ～ {data.rangeEnd} · 样本 {data.sampleCount} · 有效 {data.validCount}
          </p>
        </div>
        <span className={`rounded-md px-2.5 py-1 text-sm ${statusStyle}`}>
          当前状态：{data.sampleStatus}
        </span>
      </div>
    </Card>
  );
}

function SampleNotMature() {
  return (
    <Card className="rounded-lg border-dashed border-finance-blue/30 bg-finance-blue-soft/30 p-6 text-center shadow-sm">
      <Hourglass className="mx-auto mb-2 size-7 text-finance-blue" />
      <h4 className="text-foreground">样本仍在积累中</h4>
      <p className="mx-auto mt-1 max-w-md text-sm leading-relaxed text-neutral">
        当前选股结果尚未经过足够未来交易日验证。系统会在样本成熟后自动展示完整胜率、收益和超额收益。以下数据基于现有有效样本，仅供参考。
      </p>
    </Card>
  );
}

function Overview({ data }: { data: BacktestData }) {
  const o = data.overview;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
      <DataCard label="Top20 胜率" value={`${o.top20WinRate}%`} tone="primary" />
      <DataCard label="跑赢基准比例" value={`${o.top20BeatBenchmarkPct}%`} tone="primary" />
      <DataCard label="平均收益" value={<ChangeText value={o.avgReturn} />} />
      <DataCard label="平均超额收益" value={<ChangeText value={o.avgExcess} />} />
      <DataCard label="最大单笔回撤" value={<ChangeText value={o.maxDrawdown} />} tone="down" />
    </div>
  );
}

function HoldingPerf({ data }: { data: BacktestData }) {
  return (
    <Card className="rounded-lg p-5 shadow-sm">
      <SectionTitle title="按持有期表现" desc="不同持有周期的统计结果" />
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="bg-neutral-soft/60 hover:bg-neutral-soft/60">
              {["持有期", "样本数", "胜率", "平均收益", "中位收益", "平均超额", "Top5", "Top10", "Top20", "最大回撤"].map((h) => (
                <TableHead key={h} className="whitespace-nowrap text-neutral">{h}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.holdingPerf.map((p) => (
              <TableRow key={p.period}>
                <TableCell className="whitespace-nowrap text-foreground">{p.period}</TableCell>
                <TableCell className="tabular-nums text-neutral">{p.samples}</TableCell>
                <TableCell className="tabular-nums text-finance-blue">{p.winRate}%</TableCell>
                <TableCell><ChangeText value={p.avgReturn} /></TableCell>
                <TableCell><ChangeText value={p.medianReturn} /></TableCell>
                <TableCell><ChangeText value={p.avgExcess} /></TableCell>
                <TableCell className="tabular-nums text-neutral">{p.top5Precision}%</TableCell>
                <TableCell className="tabular-nums text-neutral">{p.top10Precision}%</TableCell>
                <TableCell className="tabular-nums text-neutral">{p.top20Precision}%</TableCell>
                <TableCell><ChangeText value={p.maxDrawdown} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Card>
  );
}

function EquityCurve({ data }: { data: BacktestData }) {
  const chartData = data.equityCurve.map((p) => ({
    date: p.date.slice(5),
    策略: +((p.strategy - 1) * 100).toFixed(2),
    基准: p.benchmark === null ? null : +((p.benchmark - 1) * 100).toFixed(2),
    超额: p.excess === null ? null : +(p.excess * 100).toFixed(2),
  }));
  return (
    <Card className="rounded-lg p-5 shadow-sm">
      <SectionTitle title="收益曲线" desc="累计收益（%），含基准与超额收益" />
      {!data.hasBenchmark && (
        <p className="mb-2 text-sm text-risk">暂无基准数据，仅展示绝对收益。</p>
      )}
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData} margin={{ left: -10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e9ee" />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#5c7184" }} />
          <YAxis tick={{ fontSize: 11, fill: "#5c7184" }} unit="%" />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="策略" stroke="#d23b3b" strokeWidth={2} dot={false} />
          {data.hasBenchmark && (
            <Line type="monotone" dataKey="基准" stroke="#5c7184" strokeWidth={1.5} dot={false} />
          )}
          {data.hasBenchmark && (
            <Line type="monotone" dataKey="超额" stroke="#1f4e78" strokeWidth={1.5} strokeDasharray="4 3" dot={false} />
          )}
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}

function LayerPerf({ data }: { data: BacktestData }) {
  const maxReturn = Math.max(...data.layers.map((l) => l.avgReturn));
  return (
    <Card className="rounded-lg p-5 shadow-sm">
      <SectionTitle title="分层表现" desc="不同排名组的胜率与收益对比" />
      <div className="grid gap-3 md:grid-cols-3">
        {data.layers.map((l) => (
          <div key={l.layer} className="rounded-lg border border-border p-4">
            <div className="flex items-center justify-between">
              <span className="text-foreground">{l.layer}</span>
              <Badge variant="outline" className="text-neutral">{l.samples} 样本</Badge>
            </div>
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-neutral">胜率</span><span className="tabular-nums text-finance-blue">{l.winRate}%</span></div>
              <div className="flex justify-between"><span className="text-neutral">平均收益</span><ChangeText value={l.avgReturn} /></div>
              <div className="flex justify-between"><span className="text-neutral">平均超额</span><ChangeText value={l.avgExcess} /></div>
              <div className="flex justify-between"><span className="text-neutral">跑赢基准</span><span className="tabular-nums text-foreground">{l.beatBenchmarkPct}%</span></div>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-neutral-soft">
              <div className="h-full rounded-full bg-finance-blue" style={{ width: `${(l.avgReturn / maxReturn) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ICCell({ value }: { value: number }) {
  // 热力：正值蓝，负值橙，强度由绝对值决定
  const a = Math.min(1, Math.abs(value) / 0.18);
  const bg =
    value >= 0
      ? `rgba(31,78,120,${0.12 + a * 0.7})`
      : `rgba(224,138,43,${0.12 + a * 0.7})`;
  const textColor = a > 0.55 ? "#fff" : "var(--foreground)";
  return (
    <td className="px-2 py-1.5 text-center tabular-nums" style={{ backgroundColor: bg, color: textColor }}>
      {value.toFixed(2)}
    </td>
  );
}

function FactorIC({ data }: { data: BacktestData }) {
  const sorted = [...data.factorIC].sort((a, b) => b.returnRankIC - a.returnRankIC);
  return (
    <Card className="rounded-lg p-5 shadow-sm">
      <SectionTitle title="因子预测力 IC" desc="各评分字段与未来收益的相关性（热力图）" />
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0.5 text-sm">
          <thead>
            <tr className="text-neutral">
              <th className="px-2 py-1.5 text-left">因子</th>
              <th className="px-2 py-1.5 text-center">return_ic</th>
              <th className="px-2 py-1.5 text-center">return_rank_ic</th>
              <th className="px-2 py-1.5 text-center">excess_ic</th>
              <th className="px-2 py-1.5 text-center">excess_rank_ic</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((f) => (
              <tr key={f.factor}>
                <td className="whitespace-nowrap px-2 py-1.5 text-foreground">{f.factor}</td>
                <ICCell value={f.returnIC} />
                <ICCell value={f.returnRankIC} />
                <ICCell value={f.excessIC} />
                <ICCell value={f.excessRankIC} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 flex items-start gap-1.5 text-xs leading-relaxed text-neutral">
        <Info className="mt-0.5 size-3.5 shrink-0" />
        IC 越高，说明该指标与未来收益相关性越强；样本少时不应过度解读。
      </p>
    </Card>
  );
}

const statusMeta: Record<DetailStatus, { label: string; cls: string }> = {
  ok: { label: "ok", cls: "bg-down-soft text-down" },
  not_mature_yet: { label: "未成熟", cls: "bg-finance-blue-soft text-finance-blue" },
  no_kline: { label: "无K线", cls: "bg-neutral-soft text-neutral" },
  signal_date_missing: { label: "信号缺失", cls: "bg-risk-soft text-risk" },
};

function DetailTable({ rows }: { rows: BacktestDetail[] }) {
  return (
    <Card className="rounded-lg p-5 shadow-sm">
      <SectionTitle title="历史预测明细" desc="每只入选股票的后续表现跟踪" />
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="bg-neutral-soft/60 hover:bg-neutral-soft/60">
              {["信号日期", "名称", "代码", "排名", "信号价", "T+1买入", "持有期", "卖出日期", "收益率", "基准", "超额", "最大回撤", "盈利", "跑赢", "状态"].map((h) => (
                <TableHead key={h} className="whitespace-nowrap text-neutral">{h}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r, i) => {
              const meta = statusMeta[r.status];
              return (
                <TableRow key={`${r.code}-${r.signalDate}-${i}`}>
                  <TableCell className="whitespace-nowrap tabular-nums text-neutral">{r.signalDate}</TableCell>
                  <TableCell className="whitespace-nowrap text-foreground">{r.name}</TableCell>
                  <TableCell className="tabular-nums text-neutral">{r.code}</TableCell>
                  <TableCell className="tabular-nums text-neutral">{r.rank}</TableCell>
                  <TableCell className="tabular-nums">{r.signalPrice.toFixed(2)}</TableCell>
                  <TableCell className="tabular-nums">{r.buyPrice ? r.buyPrice.toFixed(2) : "—"}</TableCell>
                  <TableCell className="whitespace-nowrap text-neutral">{r.holdingPeriod}</TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums text-neutral">{r.sellDate}</TableCell>
                  <TableCell><ChangeText value={r.returnPct} /></TableCell>
                  <TableCell><ChangeText value={r.benchmarkPct} /></TableCell>
                  <TableCell><ChangeText value={r.excessPct} /></TableCell>
                  <TableCell><ChangeText value={r.maxDrawdown} /></TableCell>
                  <TableCell>{r.profitable === null ? <span className="text-neutral">—</span> : r.profitable ? <span className="text-up">是</span> : <span className="text-down">否</span>}</TableCell>
                  <TableCell>{r.beatBenchmark === null ? <span className="text-neutral">—</span> : r.beatBenchmark ? <span className="text-up">是</span> : <span className="text-down">否</span>}</TableCell>
                  <TableCell><span className={`rounded px-1.5 py-0.5 text-xs ${meta.cls}`}>{meta.label}</span></TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </Card>
  );
}

function Credibility() {
  const items = [
    "信号基于 T 日收盘后数据生成",
    "默认 T+1 开盘买入",
    "持有 N 个交易日后按收盘价评估",
    "结果用于验证规则预测力，不代表真实投资收益",
    "仍需考虑手续费、滑点、涨跌停、停牌、成交量不足等现实约束",
    "样本量太小时不要过度解读胜率",
  ];
  return (
    <Card className="rounded-lg border-risk/20 bg-risk-soft/30 p-5 shadow-sm">
      <SectionTitle title="回测可信度说明" />
      <ul className="space-y-1.5 text-sm text-foreground/85">
        {items.map((t) => (
          <li key={t} className="flex items-start gap-2">
            <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-risk" />
            {t}
          </li>
        ))}
      </ul>
    </Card>
  );
}
