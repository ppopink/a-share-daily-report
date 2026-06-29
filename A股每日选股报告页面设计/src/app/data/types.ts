// 数据类型定义 —— 与后端选股系统 JSON 输出保持一致，便于后续接入真实数据。

export type FilterMode = "normal" | "strict" | "loose";
export type EntryTiming = "积极" | "观察" | "等待回踩" | "追高谨慎";
export type StrategyStatus = "偏强" | "一般" | "谨慎";
export type SampleStatus = "样本不足" | "样本成熟" | "需要继续观察";

export interface RiskFlag {
  level: "low" | "medium" | "high";
  label: string;
}

export interface MarketGuard {
  marketStatus: string;
  riskLevel: "low" | "medium" | "high" | string;
  positionAdvice: string;
  tradePermission: string;
  marketNote: string;
  totalCount: number;
  upCount: number;
  downCount: number;
  upRatio: number;
  avgPctChange: number;
  limitUpCount: number;
  limitDownCount: number;
  totalAmount: number;
}

export interface DataQuality {
  klineStatus: string;
  moneyFlowStatus: string;
  contextStatus: string;
  industryStatus: string;
  hotSectorSource: string;
  stockCount: number;
  moneyFlowCoveragePct: number;
  contextCoveragePct: number;
  industryCoveragePct: number;
  notes: string[];
}

export interface DeploymentStatus {
  generatedAt: string;
  commitSha: string;
  branch: string;
  githubPagesUrl: string;
  actionsUrl: string;
}

export interface StrategyInsight {
  title: string;
  value: string;
  note: string;
  level: "good" | "neutral" | "risk";
}

export interface KlinePoint {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  ma5: number | null;
  ma20: number | null;
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
  contextScore: number;
  eventScore: number;
  eventCount: number;
  eventNote: string;
  eventTitles: string;
  marginScore: number;
  marginBalanceChangePct: number;
  marginNetBuy: number;
  marginNote: string;
  lhbScore: number;
  lhbCount: number;
  lhbNetBuy: number;
  lhbNote: string;
  contextNote: string;
  selectionReason?: string;
  watchReason?: string;
  buyAction?: string;
  buyTrigger?: string;
  buyAvoidRules?: string;
  maxOpenGapPct?: number;
  maxBuyPrice?: number;
  pullbackBuyPrice?: number;
  invalidBelowPrice?: number;
  recentPickCount?: number;
  consecutivePickDays?: number;
  firstSeenDate?: string;
  recentPickNote?: string;
  predictedWinProb1d?: number;
  predictedWinProb2d?: number;
  predictedWinProb3d?: number;
  predictionConfidence?: string;
  predictionNote?: string;
  modelVersion?: string;
  trendQualityScore: number;
  // 入场 / 风险
  entryTiming: EntryTiming;
  entryNote: string;
  risks: RiskFlag[];
  riskNote: string;
  // 退出计划 / 卖出建议
  plannedHoldingDays: number;
  stopLossPrice: number;
  takeProfit1Price: number;
  takeProfit2Price: number;
  trailingStopPrice: number;
  riskRewardRatio: number;
  exitStrategy: string;
  exitSignal: string;
  exitNote: string;
  day1StopLossPrice: number;
  day1TakeProfitPrice: number;
  day1ExitPlan: string;
  day2StopLossPrice: number;
  day2TakeProfitPrice: number;
  day2ExitPlan: string;
  day3StopLossPrice: number;
  day3TakeProfitPrice: number;
  day3ExitPlan: string;
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
  kline?: KlinePoint[];
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
  marketGuard?: MarketGuard;
  dataQuality?: DataQuality;
  conclusion: {
    selectedCount: number;
    top5: { name: string; code: string }[];
    strictestCondition: string;
    chaseRisk: boolean;
    status: StrategyStatus;
    narrative: string;
    marketAdvice?: string;
  };
  diagnostics: DiagnosticItem[];
  funnel: { stage: string; count: number }[];
  industryDist: { sector: string; count: number }[];
  hotSectors?: HotSector[];
}

export interface ModeReportSummary {
  mode: FilterMode;
  selectedCount: number;
  avgScore: number;
  passRate: number;
  riskCount: number;
  topStock: { name: string; code: string; score: number; price: number };
}

export interface HistoryEntry {
  date: string;
  selectedCount: number;
  topStock: string;
  avgScore: number;
  availableModes?: FilterMode[];
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
  strategyInsights?: StrategyInsight[];
}
