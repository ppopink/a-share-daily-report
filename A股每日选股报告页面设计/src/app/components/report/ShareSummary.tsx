import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Card } from "../ui/card";
import { Button } from "../ui/button";
import { SectionTitle } from "./shared";
import type { DailyReport } from "../../data/types";

export function buildShareText(report: DailyReport): string {
  const c = report.conclusion;
  const top = report.summary.topStock;
  const top5 = c.top5.map((s) => s.name).join("、");
  return `${report.date} A股规则选股观察：
今日入选 ${c.selectedCount} 只，Top5：${top5}。
最高分：${top.name}，当前价格 ${top.price.toFixed(2)}。
技术最严格条件：${c.strictestCondition}。
仅供规则跟踪和学习交流，不构成投资建议。`;
}

export function ShareSummary({ report }: { report: DailyReport }) {
  const [copied, setCopied] = useState(false);
  const text = buildShareText(report);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* 剪贴板不可用时忽略 */
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Card className="rounded-lg p-5 shadow-sm">
      <SectionTitle
        title="分享摘要"
        desc="一键复制，适合微信转发"
        action={
          <Button size="sm" className="h-8 gap-1.5 bg-finance-blue hover:bg-finance-blue/90" onClick={copy}>
            {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
            {copied ? "已复制" : "复制"}
          </Button>
        }
      />
      <pre className="whitespace-pre-wrap rounded-md border border-border bg-neutral-soft/50 p-3 text-sm leading-relaxed text-foreground/90">
        {text}
      </pre>
    </Card>
  );
}
