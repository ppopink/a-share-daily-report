// Mock 数据 —— 结构与真实选股系统输出一致。接入真实数据时，替换本文件的导出即可。
import type {
  BacktestData,
  DailyReport,
  HistoryEntry,
  Stock,
} from "./types";

const rawNames: [string, string, string][] = [
  // [name, code, sector]
  ["紫光国微", "002049", "半导体"],
  ["宁德时代", "300750", "电池"],
  ["中际旭创", "300308", "光模块"],
  ["立讯精密", "002475", "消费电子"],
  ["北方华创", "002371", "半导体设备"],
  ["金山办公", "688111", "软件"],
  ["阳光电源", "300274", "光伏"],
  ["汇川技术", "300124", "工业自动化"],
  ["恒生电子", "600570", "金融科技"],
  ["韦尔股份", "603501", "半导体"],
  ["兆易创新", "603986", "半导体"],
  ["三花智控", "002050", "汽车零部件"],
  ["拓普集团", "601689", "汽车零部件"],
  ["天孚通信", "300394", "光模块"],
  ["新易盛", "300502", "光模块"],
  ["科大讯飞", "002230", "人工智能"],
  ["亿纬锂能", "300014", "电池"],
  ["晶澳科技", "002459", "光伏"],
  ["澜起科技", "688008", "半导体"],
  ["盛美上海", "688082", "半导体设备"],
];

const entryOptions = ["积极", "观察", "等待回踩", "追高谨慎"] as const;

function seeded(i: number) {
  // 稳定的伪随机，保证刷新一致
  const x = Math.sin(i * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

function round(n: number, d = 2) {
  const f = 10 ** d;
  return Math.round(n * f) / f;
}

const stocks: Stock[] = rawNames.map(([name, code, sector], idx) => {
  const rank = idx + 1;
  const r = (k: number) => seeded(idx * 7 + k);
  const totalScore = round(92 - idx * 1.8 - r(1) * 3, 1);
  const changePct = round((r(2) - 0.35) * 6, 2);
  const price = round(8 + r(3) * 80, 2);
  const adx = round(22 + r(4) * 28, 1);
  const plusDI = round(24 + r(5) * 16, 1);
  const minusDI = round(8 + r(6) * 10, 1);
  const closeMa20Ratio = round(1.0 + r(7) * 0.12, 3);
  const overheated = closeMa20Ratio > 1.08;
  const entryTiming =
    overheated
      ? "追高谨慎"
      : idx < 6
        ? "积极"
        : entryOptions[Math.floor(r(8) * 4)];

  const risks = [] as Stock["risks"];
  if (overheated) risks.push({ level: "high", label: "偏离MA20较大" });
  if (changePct > 4) risks.push({ level: "medium", label: "短线涨幅偏高" });
  if (r(9) > 0.78) risks.push({ level: "medium", label: "量能不持续" });
  if (r(10) > 0.88) risks.push({ level: "low", label: "临近前高压力" });

  return {
    rank,
    name,
    code,
    price,
    changePct,
    totalScore,
    trendScore: round(15 + r(11) * 10, 1),
    volumeScore: round(10 + r(12) * 8, 1),
    dmiScore: round(10 + r(13) * 8, 1),
    macdScore: round(8 + r(14) * 7, 1),
    expmaScore: round(6 + r(15) * 6, 1),
    moneyFlowScore: round(5 + r(16) * 8, 1),
    sectorScore: round(5 + r(17) * 6, 1),
    trendQualityScore: round(6 + r(18) * 6, 1),
    entryTiming,
    entryNote:
      entryTiming === "积极"
        ? "趋势与量能配合，T+1开盘可重点观察。"
        : entryTiming === "追高谨慎"
          ? "股价已明显偏离MA20，建议等待回踩不破均线再观察。"
          : entryTiming === "等待回踩"
            ? "趋势完好但短线略急，回踩5日线企稳更稳妥。"
            : "信号成立但确认度一般，建议小仓位观察。",
    risks,
    riskNote:
      risks.length === 0
        ? "暂无明显风险信号。"
        : risks.map((x) => x.label).join("；") + "。注意控制仓位与止损。",
    adx,
    plusDI,
    minusDI,
    volRatio: round(0.9 + r(19) * 1.8, 2),
    aboveMa20Days20: Math.floor(6 + r(20) * 14),
    ma20Slope10Pct: round((r(21) - 0.1) * 4, 2),
    ma20Slope20Pct: round((r(22) - 0.1) * 3, 2),
    closeMa20Ratio,
    macdDIF: round((r(23) - 0.3) * 1.2, 3),
    macdDEA: round((r(24) - 0.3) * 1.0, 3),
    macdHIST: round((r(25) - 0.4) * 0.6, 3),
    moneyFlowRatio: round((r(26) - 0.3) * 12, 2),
    sectorRankPct: round(r(27) * 100, 1),
    sectorInnerRankPct: round(r(28) * 100, 1),
    sector,
  };
});

const above80 = stocks.filter((s) => s.totalScore >= 80).length;
const avgScore = round(
  stocks.reduce((a, s) => a + s.totalScore, 0) / stocks.length,
  1,
);
const riskCount = stocks.filter((s) => s.risks.length > 0).length;

const industryMap = stocks.reduce<Record<string, number>>((acc, s) => {
  acc[s.sector] = (acc[s.sector] ?? 0) + 1;
  return acc;
}, {});

export const todayReport: DailyReport = {
  date: "2026-06-24",
  mode: "normal",
  generatedAt: "2026-06-24 15:42",
  stocks,
  summary: {
    selectedCount: stocks.length,
    topStock: {
      name: stocks[0].name,
      code: stocks[0].code,
      score: stocks[0].totalScore,
      price: stocks[0].price,
    },
    avgScore,
    riskCount,
    above80Count: above80,
    passRate: 18.6,
  },
  conclusion: {
    selectedCount: stocks.length,
    top5: stocks.slice(0, 5).map((s) => ({ name: s.name, code: s.code })),
    strictestCondition: "MA20 趋势质量（持续在均线上方且斜率向上）",
    chaseRisk: stocks.some((s) => s.entryTiming === "追高谨慎"),
    status: "一般",
    narrative:
      "今日规则共筛出 20 只候选股票，整体集中在半导体、光模块与新能源方向。Top 标的趋势与量能配合较好，但部分个股股价已偏离MA20，存在追高风险，建议优先关注回踩企稳的标的，整体保持观察。",
  },
  diagnostics: [
    { id: "ma_order", label: "close > MA3 > MA5 > MA21", passed: 312, total: 980 },
    { id: "above_ma20", label: "close > MA20 today", passed: 540, total: 980 },
    { id: "ma20_persist", label: "MA20 持续天数（20内）", passed: 421, total: 980 },
    { id: "ma20_slope", label: "MA20 斜率向上", passed: 388, total: 980 },
    { id: "not_overheated", label: "未过度偏离 MA20", passed: 305, total: 980 },
    { id: "trend_quality", label: "MA20 趋势质量", passed: 256, total: 980 },
    { id: "di", label: "+DI > -DI", passed: 470, total: 980 },
    { id: "adx", label: "ADX > 阈值", passed: 332, total: 980 },
    { id: "vol_ratio", label: "量比达标", passed: 410, total: 980 },
    { id: "expma", label: "EXPMA7 > EXPMA21", passed: 398, total: 980 },
    { id: "dif_dea_pos", label: "DIF > 0 且 DEA > 0", passed: 366, total: 980 },
    { id: "dif_gt_dea", label: "DIF > DEA", passed: 344, total: 980 },
    { id: "macd_second", label: "MACD 二次金叉", passed: 182, total: 980 },
  ],
  funnel: [
    { stage: "全市场样本", count: 980 },
    { stage: "趋势条件通过", count: 421 },
    { stage: "量能条件通过", count: 268 },
    { stage: "DMI 条件通过", count: 142 },
    { stage: "MACD 条件通过", count: 64 },
    { stage: "最终入选", count: 20 },
  ],
  industryDist: Object.entries(industryMap)
    .map(([sector, count]) => ({ sector, count }))
    .sort((a, b) => b.count - a.count),
};

export const historyList: HistoryEntry[] = [
  { date: "2026-06-24", selectedCount: 20, topStock: "紫光国微", avgScore: avgScore },
  { date: "2026-06-23", selectedCount: 18, topStock: "中际旭创", avgScore: 81.2 },
  { date: "2026-06-20", selectedCount: 24, topStock: "北方华创", avgScore: 79.5 },
  { date: "2026-06-19", selectedCount: 15, topStock: "宁德时代", avgScore: 83.1 },
  { date: "2026-06-18", selectedCount: 21, topStock: "立讯精密", avgScore: 78.8 },
  { date: "2026-06-17", selectedCount: 12, topStock: "金山办公", avgScore: 80.4 },
  { date: "2026-06-16", selectedCount: 19, topStock: "汇川技术", avgScore: 77.9 },
  { date: "2026-06-13", selectedCount: 22, topStock: "阳光电源", avgScore: 82.0 },
];

// ---- 回测 mock ----
const equityCurve = Array.from({ length: 18 }, (_, i) => {
  const d = 1 + i;
  const date = `2026-06-${String(d).padStart(2, "0")}`;
  const strategy = round(1 + i * 0.012 + (seeded(i) - 0.5) * 0.02, 4);
  const benchmark = round(1 + i * 0.005 + (seeded(i + 50) - 0.5) * 0.015, 4);
  return {
    date,
    strategy,
    benchmark,
    excess: round(strategy - benchmark, 4),
  };
});

export const backtestData: BacktestData = {
  rangeStart: "2026-06-01",
  rangeEnd: "2026-06-24",
  sampleCount: 168,
  validCount: 96,
  sampleStatus: "需要继续观察",
  overview: {
    top20WinRate: 58.3,
    top20BeatBenchmarkPct: 61.4,
    avgReturn: 1.92,
    avgExcess: 0.84,
    maxDrawdown: -7.6,
  },
  hasBenchmark: true,
  holdingPerf: [
    { period: "持有3日", samples: 96, winRate: 56.2, avgReturn: 1.1, medianReturn: 0.8, avgExcess: 0.4, top5Precision: 64, top10Precision: 60, top20Precision: 56, maxDrawdown: -4.2 },
    { period: "持有5日", samples: 84, winRate: 58.3, avgReturn: 1.9, medianReturn: 1.3, avgExcess: 0.8, top5Precision: 68, top10Precision: 62, top20Precision: 58, maxDrawdown: -5.6 },
    { period: "持有10日", samples: 60, winRate: 55.0, avgReturn: 2.7, medianReturn: 1.9, avgExcess: 1.1, top5Precision: 66, top10Precision: 61, top20Precision: 55, maxDrawdown: -7.6 },
    { period: "持有20日", samples: 32, winRate: 53.1, avgReturn: 3.4, medianReturn: 2.1, avgExcess: 1.3, top5Precision: 62, top10Precision: 58, top20Precision: 53, maxDrawdown: -9.8 },
  ],
  equityCurve,
  layers: [
    { layer: "Top1-5", samples: 40, winRate: 64.0, avgReturn: 2.8, avgExcess: 1.6, beatBenchmarkPct: 68 },
    { layer: "Top6-10", samples: 38, winRate: 57.0, avgReturn: 1.9, avgExcess: 0.9, beatBenchmarkPct: 60 },
    { layer: "Top11-20", samples: 18, winRate: 51.0, avgReturn: 1.1, avgExcess: 0.3, beatBenchmarkPct: 53 },
  ],
  factorIC: [
    { factor: "total_score", returnIC: 0.12, returnRankIC: 0.15, excessIC: 0.1, excessRankIC: 0.13 },
    { factor: "trend_score", returnIC: 0.09, returnRankIC: 0.11, excessIC: 0.08, excessRankIC: 0.1 },
    { factor: "trend_quality_score", returnIC: 0.14, returnRankIC: 0.16, excessIC: 0.12, excessRankIC: 0.14 },
    { factor: "volume_score", returnIC: 0.06, returnRankIC: 0.07, excessIC: 0.05, excessRankIC: 0.06 },
    { factor: "dmi_score", returnIC: 0.08, returnRankIC: 0.09, excessIC: 0.07, excessRankIC: 0.08 },
    { factor: "macd_score", returnIC: 0.04, returnRankIC: 0.05, excessIC: 0.03, excessRankIC: 0.04 },
    { factor: "expma_score", returnIC: 0.05, returnRankIC: 0.06, excessIC: 0.04, excessRankIC: 0.05 },
    { factor: "money_flow_score", returnIC: 0.11, returnRankIC: 0.13, excessIC: 0.1, excessRankIC: 0.12 },
    { factor: "sector_score", returnIC: 0.07, returnRankIC: 0.08, excessIC: 0.06, excessRankIC: 0.07 },
    { factor: "above_ma20_days_20", returnIC: 0.1, returnRankIC: 0.12, excessIC: 0.09, excessRankIC: 0.11 },
    { factor: "ma20_slope_10_pct", returnIC: 0.13, returnRankIC: 0.14, excessIC: 0.11, excessRankIC: 0.13 },
    { factor: "close_ma20_ratio", returnIC: -0.06, returnRankIC: -0.07, excessIC: -0.05, excessRankIC: -0.06 },
    { factor: "adx", returnIC: 0.09, returnRankIC: 0.1, excessIC: 0.08, excessRankIC: 0.09 },
    { factor: "vol_ratio", returnIC: 0.03, returnRankIC: 0.04, excessIC: 0.02, excessRankIC: 0.03 },
  ],
  details: [
    { signalDate: "2026-06-19", name: "宁德时代", code: "300750", rank: 1, signalPrice: 198.4, buyPrice: 199.1, holdingPeriod: "5日", sellDate: "2026-06-26", returnPct: 3.2, benchmarkPct: 1.1, excessPct: 2.1, maxDrawdown: -1.8, profitable: true, beatBenchmark: true, status: "ok" },
    { signalDate: "2026-06-19", name: "立讯精密", code: "002475", rank: 4, signalPrice: 32.1, buyPrice: 32.4, holdingPeriod: "5日", sellDate: "2026-06-26", returnPct: -1.4, benchmarkPct: 1.1, excessPct: -2.5, maxDrawdown: -3.1, profitable: false, beatBenchmark: false, status: "ok" },
    { signalDate: "2026-06-20", name: "北方华创", code: "002371", rank: 1, signalPrice: 410.5, buyPrice: 412.0, holdingPeriod: "3日", sellDate: "2026-06-25", returnPct: 2.6, benchmarkPct: 0.7, excessPct: 1.9, maxDrawdown: -1.2, profitable: true, beatBenchmark: true, status: "ok" },
    { signalDate: "2026-06-23", name: "中际旭创", code: "300308", rank: 1, signalPrice: 142.0, buyPrice: 143.2, holdingPeriod: "3日", sellDate: "—", returnPct: null, benchmarkPct: null, excessPct: null, maxDrawdown: null, profitable: null, beatBenchmark: null, status: "not_mature_yet" },
    { signalDate: "2026-06-24", name: "紫光国微", code: "002049", rank: 1, signalPrice: 78.5, buyPrice: 0, holdingPeriod: "5日", sellDate: "—", returnPct: null, benchmarkPct: null, excessPct: null, maxDrawdown: null, profitable: null, beatBenchmark: null, status: "not_mature_yet" },
    { signalDate: "2026-06-18", name: "某退市股", code: "000xxx", rank: 12, signalPrice: 5.2, buyPrice: 0, holdingPeriod: "10日", sellDate: "—", returnPct: null, benchmarkPct: null, excessPct: null, maxDrawdown: null, profitable: null, beatBenchmark: null, status: "no_kline" },
  ],
};

export const availableDates = historyList.map((h) => h.date);
