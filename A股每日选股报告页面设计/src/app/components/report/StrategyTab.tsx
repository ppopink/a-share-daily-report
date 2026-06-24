import { Card } from "../ui/card";
import { SectionTitle } from "./shared";

const conditions = [
  "close > MA3 > MA5 > MA21（均线多头排列）",
  "close > MA20 today（站上中期均线）",
  "MA20 持续天数（20日内站上 MA20 的天数）",
  "MA20 斜率向上（中期趋势向上）",
  "未过度偏离 MA20（避免追高）",
  "MA20 趋势质量（持续性与斜率综合）",
  "+DI > -DI（多头占优）",
  "ADX > 阈值（趋势强度足够）",
  "量比达标（有效放量）",
  "EXPMA7 > EXPMA21（短期动能向上）",
  "DIF > 0 且 DEA > 0（MACD 在零轴上方）",
  "DIF > DEA（MACD 金叉状态）",
  "MACD 二次金叉（更强的确认信号）",
];

export function StrategyTab() {
  return (
    <div className="space-y-4">
      <Card className="rounded-lg p-5 shadow-sm">
        <SectionTitle title="策略说明" desc="本系统基于沪深A股 K线规则的量化选股逻辑" />
        <p className="text-sm leading-relaxed text-foreground/90">
          系统每个交易日收盘后运行一次，对全市场股票进行技术面打分，从趋势、量能、DMI、MACD、EXPMA、资金流向、板块等多个维度综合评分，筛选出当日符合规则的候选股票，并给出入场时机与风险提示。
        </p>
      </Card>

      <Card className="rounded-lg p-5 shadow-sm">
        <SectionTitle title="核心筛选条件" />
        <ul className="grid gap-2 md:grid-cols-2">
          {conditions.map((c, i) => (
            <li key={i} className="flex items-start gap-2 rounded-md bg-neutral-soft/50 p-2.5 text-sm text-foreground/90">
              <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded bg-finance-blue-soft text-xs text-finance-blue">{i + 1}</span>
              {c}
            </li>
          ))}
        </ul>
      </Card>

      <Card className="rounded-lg p-5 shadow-sm">
        <SectionTitle title="评分维度" />
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["趋势分", "均线排列与方向"],
            ["趋势质量分", "趋势持续性与斜率"],
            ["量能分", "成交量与量比"],
            ["DMI分", "ADX 与方向指标"],
            ["MACD分", "DIF/DEA/金叉"],
            ["EXPMA分", "指数平滑均线动能"],
            ["资金分", "主力净流入"],
            ["板块分", "所属板块强度与排名"],
          ].map(([k, v]) => (
            <div key={k} className="rounded-md border border-border p-3">
              <div className="text-foreground">{k}</div>
              <div className="mt-0.5 text-xs text-neutral">{v}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="rounded-lg border-risk/20 bg-risk-soft/30 p-5 shadow-sm">
        <p className="text-sm leading-relaxed text-risk">
          本策略与报告仅用于量化规则跟踪和学习交流，不构成任何投资建议。所有信号基于历史与收盘后数据计算，历史表现不代表未来收益，实际交易还需考虑手续费、滑点、涨跌停、停牌及流动性等约束。请独立判断并自负盈亏。
        </p>
      </Card>
    </div>
  );
}
