// 数据类型定义 —— 与后端选股系统 JSON 输出保持一致，便于后续接入真实数据。

export type FilterMode = "normal" | "strict" | "loose";
export type EntryTiming = "积极" | "观察" | "等待回踩" | "追高谨慎";
export type StrategyStatus = "偏强" | "一般" | "谨慎";
export type SampleStatus = "样本不足" | "样本成熟" | "需要继续观察";

export interface RiskFlag {
  level: "low" | "medium" | "high";
  label: string;
}

export interface Stock {
  rank: number;
  name: string;
  code: string;
  price: number;
  changePct: number;
  // 评分拆解
  totalScore: number;
  trendScore: number;
  volumeScore: number;
  dmiScore: number;
  macdScore: number;
  expmaScore: number;
  moneyFlowScore: number;
  sectorScore: number;
  trendQualityScore: number;
  // 入场 / 风险
  entryTiming: EntryTiming;
  entryNote: string;
  risks: RiskFlag[];
  riskNote: string;
  // 详细技术指标
  adx: number;
  plusDI: number;
  minusDI: number;
  volRatio: number;
  aboveMa20Days20: number;
  ma20Slope10Pct: number;
  ma20Slope20Pct: number;
  closeMa20Ratio: number;
  macdDIF: number;
  macdDEA: number;
  macdHIST: number;
  moneyFlowRatio: number; // 主力净流入比例 %
  sectorRankPct: number; // 板块排名分位 %
  sectorInnerRankPct: number; // 板块内排名分位 %
  sector: string;
}

export interface SummaryStat {
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "up" | "down" | "risk" | "primary";
}

export interface DiagnosticItem {
  id: string;
  label: string;
  passed: number;
  total: number;
}

export interface HotSector {
  rank: number;
  code: string;
  name: string;
  heatScore: number;
  pctChange: number;
  amount: number;
  turnover: number;
  upCount: number;
  downCount: number;
  flatCount: number;
  stockCount: number;
  upRatio: number;
  selectedCount: number;
  leaderName: string;
  leaderCode: string;
  leaderPctChange: number;
  leadingStocks: string;
  quantNote: string;
  dataSource: string;
}

export interface ReportFiles {
  csv?: string;
  hotSectorsCsv?: string;
  excel?: string;
  html?: string;
  pdf?: string;
}

export interface DailyReport {
  date: string;
  mode: FilterMode;
  generatedAt: string;
  files?: ReportFiles;
  stocks: Stock[];
  summary: {
    selectedCount: number;
    topStock: { name: string; code: string; score: number; price: number };
    avgScore: number;
    riskCount: number;
    above80Count: number;
    passRate: number; // 技术筛选通过率 %
  };
  conclusion: {
    selectedCount: number;
    top5: { name: string; code: string }[];
    strictestCondition: string;
    chaseRisk: boolean;
    status: StrategyStatus;
    narrative: string;
  };
  diagnostics: DiagnosticItem[];
  funnel: { stage: string; count: number }[];
  industryDist: { sector: string; count: number }[];
  hotSectors?: HotSector[];
}

export interface HistoryEntry {
  date: string;
  selectedCount: number;
  topStock: string;
  avgScore: number;
  files?: ReportFiles;
}

// ---- 回测 ----
export interface HoldingPeriodPerf {
  period: string; // 持有3日 ...
  samples: number;
  winRate: number;
  avgReturn: number;
  medianReturn: number;
  avgExcess: number;
  top5Precision: number;
  top10Precision: number;
  top20Precision: number;
  maxDrawdown: number;
}

export interface LayerPerf {
  layer: string; // Top1-5
  samples: number;
  winRate: number;
  avgReturn: number;
  avgExcess: number;
  beatBenchmarkPct: number;
}

export interface FactorIC {
  factor: string;
  returnIC: number;
  returnRankIC: number;
  excessIC: number;
  excessRankIC: number;
}

export type DetailStatus = "ok" | "not_mature_yet" | "no_kline" | "signal_date_missing";

export interface BacktestDetail {
  signalDate: string;
  name: string;
  code: string;
  rank: number;
  signalPrice: number;
  buyPrice: number;
  holdingPeriod: string;
  sellDate: string;
  returnPct: number | null;
  benchmarkPct: number | null;
  excessPct: number | null;
  maxDrawdown: number | null;
  profitable: boolean | null;
  beatBenchmark: boolean | null;
  status: DetailStatus;
}

export interface EquityPoint {
  date: string;
  strategy: number;
  benchmark: number | null;
  excess: number | null;
}

export interface BacktestData {
  rangeStart: string;
  rangeEnd: string;
  sampleCount: number;
  validCount: number;
  sampleStatus: SampleStatus;
  overview: {
    top20WinRate: number;
    top20BeatBenchmarkPct: number;
    avgReturn: number;
    avgExcess: number;
    maxDrawdown: number;
  };
  holdingPerf: HoldingPeriodPerf[];
  equityCurve: EquityPoint[];
  hasBenchmark: boolean;
  layers: LayerPerf[];
  factorIC: FactorIC[];
  details: BacktestDetail[];
}
