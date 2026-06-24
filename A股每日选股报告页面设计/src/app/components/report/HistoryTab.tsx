import { Eye, FileDown, Sheet } from "lucide-react";
import { Card } from "../ui/card";
import { Button } from "../ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../ui/table";
import { SectionTitle } from "./shared";
import type { HistoryEntry } from "../../data/types";

export function HistoryTab({
  list,
  onView,
}: {
  list: HistoryEntry[];
  onView: (date: string) => void;
}) {
  return (
    <Card className="rounded-lg p-5 shadow-sm">
      <SectionTitle title="历史报告" desc="按日期查看过往选股报告" />

      {/* 移动端：卡片 */}
      <div className="space-y-3 md:hidden">
        {list.map((h) => (
          <div key={h.date} className="rounded-lg border border-border p-3">
            <div className="flex items-center justify-between">
              <span className="tabular-nums text-foreground">{h.date}</span>
              <span className="text-sm text-neutral">入选 {h.selectedCount} 只</span>
            </div>
            <div className="mt-1.5 flex items-center justify-between text-sm">
              <span className="text-neutral">最高分：<span className="text-foreground">{h.topStock}</span></span>
              <span className="tabular-nums text-finance-blue">均分 {h.avgScore}</span>
            </div>
            <div className="mt-3 flex gap-2">
              <Button size="sm" variant="outline" className="h-8 flex-1 gap-1" onClick={() => onView(h.date)}>
                <Eye className="size-4" /> 查看
              </Button>
              <Button size="sm" variant="outline" asChild={Boolean(h.files?.pdf)} disabled={!h.files?.pdf} className="h-8 gap-1">
                {h.files?.pdf ? <a href={h.files.pdf} download><FileDown className="size-4" /> PDF</a> : <><FileDown className="size-4" /> PDF</>}
              </Button>
              <Button size="sm" variant="outline" asChild={Boolean(h.files?.excel)} disabled={!h.files?.excel} className="h-8 gap-1">
                {h.files?.excel ? <a href={h.files.excel} download><Sheet className="size-4" /> Excel</a> : <><Sheet className="size-4" /> Excel</>}
              </Button>
            </div>
          </div>
        ))}
      </div>

      {/* 桌面端：表格 */}
      <div className="hidden overflow-x-auto md:block">
        <Table>
          <TableHeader>
            <TableRow className="bg-neutral-soft/60 hover:bg-neutral-soft/60">
              {["日期", "入选数量", "最高分股票", "平均分", "操作"].map((h) => (
                <TableHead key={h} className="text-neutral">{h}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {list.map((h) => (
              <TableRow key={h.date}>
                <TableCell className="tabular-nums text-foreground">{h.date}</TableCell>
                <TableCell className="tabular-nums text-neutral">{h.selectedCount}</TableCell>
                <TableCell className="text-foreground">{h.topStock}</TableCell>
                <TableCell className="tabular-nums text-finance-blue">{h.avgScore}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" className="h-8 gap-1" onClick={() => onView(h.date)}><Eye className="size-4" /> 查看详情</Button>
                    <Button size="sm" variant="outline" asChild={Boolean(h.files?.pdf)} disabled={!h.files?.pdf} className="h-8 gap-1">
                      {h.files?.pdf ? <a href={h.files.pdf} download><FileDown className="size-4" /> PDF</a> : <><FileDown className="size-4" /> PDF</>}
                    </Button>
                    <Button size="sm" variant="outline" asChild={Boolean(h.files?.excel)} disabled={!h.files?.excel} className="h-8 gap-1">
                      {h.files?.excel ? <a href={h.files.excel} download><Sheet className="size-4" /> Excel</a> : <><Sheet className="size-4" /> Excel</>}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Card>
  );
}
