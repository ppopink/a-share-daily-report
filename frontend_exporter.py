#!/usr/bin/env python3
"""
把 Python 选股输出同步到前端页面的 public/data 目录。

前端是静态 Vite/React 页面，不能直接读取 output 目录。因此这里把每日
stock_pick、技术诊断、准确率评估和报告附件整理成 JSON 与可下载文件。
"""

import datetime
import json
import math
import os
import shutil
from typing import Any, Dict, List, Optional

import pandas as pd

import config as cfg


FRONTEND_DIR = os.path.join(cfg.BASE_DIR, "A股每日选股报告页面设计")
PUBLIC_DIR = os.path.join(FRONTEND_DIR, "public")
DATA_DIR = os.path.join(PUBLIC_DIR, "data")
REPORT_DATA_DIR = os.path.join(DATA_DIR, "reports")
PUBLIC_REPORT_DIR = os.path.join(PUBLIC_DIR, "reports")


def _is_date_dir(name: str) -> bool:
    return len(name) == 8 and name.isdigit() and name.startswith("20")


def _date_label(date_key: str) -> str:
    return f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}"


def _safe_num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _round(value: Any, digits: int = 2, default: float = 0.0) -> float:
    return round(_safe_num(value, default), digits)


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    text = str(value).strip()
    return text if text and text.lower() != "nan" else default


def _read_csv(path: str, **kwargs) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)


def _copy_artifacts(date_key: str, day_dir: str) -> Dict[str, str]:
    """复制当日报告附件到前端 public/reports/YYYYMMDD。"""
    target_dir = os.path.join(PUBLIC_REPORT_DIR, date_key)
    os.makedirs(target_dir, exist_ok=True)

    files: Dict[str, str] = {}
    patterns = {
        "csv": f"stock_pick_{date_key}.csv",
        "excel": f"stock_pick_{date_key}.xlsx",
        "html": f"stock_pick_report_{date_key}.html",
        "pdf": f"stock_pick_report_{date_key}.pdf",
    }
    for key, filename in patterns.items():
        src = os.path.join(day_dir, filename)
        if os.path.exists(src):
            dst = os.path.join(target_dir, filename)
            shutil.copy2(src, dst)
            files[key] = f"reports/{date_key}/{filename}"
    return files


def _risk_flags(row: pd.Series) -> List[Dict[str, str]]:
    risks: List[Dict[str, str]] = []
    close_ma20_ratio = _safe_num(row.get("close_ma20_ratio"), 1.0)
    pct_change = _safe_num(row.get("pct_change"))
    vol_ratio = _safe_num(row.get("vol_ratio"))
    main_net_ratio = _safe_num(row.get("main_net_ratio"))

    if close_ma20_ratio >= 1.15:
        risks.append({"level": "high", "label": "偏离MA20较大"})
    if pct_change >= 7:
        risks.append({"level": "medium", "label": "短线涨幅偏高"})
    if 0 < vol_ratio < 1.2:
        risks.append({"level": "medium", "label": "量能确认偏弱"})
    if main_net_ratio < 0:
        risks.append({"level": "low", "label": "主力净流入偏弱"})
    return risks


def _entry_timing(row: pd.Series) -> str:
    label = _safe_str(row.get("entry_label"))
    score = _safe_num(row.get("total_score"))
    close_ma20_ratio = _safe_num(row.get("close_ma20_ratio"), 1.0)
    if "追高" in label or "回调" in label or close_ma20_ratio >= 1.15:
        return "追高谨慎"
    if "最佳" in label or score >= 85:
        return "积极"
    if "观察" in label:
        return "观察"
    return "等待回踩"


def _stock_from_row(row: pd.Series) -> Dict[str, Any]:
    risks = _risk_flags(row)
    entry_timing = _entry_timing(row)
    risk_note = "暂无明显风险信号。" if not risks else "；".join(r["label"] for r in risks) + "。注意控制仓位。"
    code = _safe_str(row.get("code")).zfill(6)
    sector = _safe_str(row.get("industry"), "未分类")

    return {
        "rank": int(_safe_num(row.get("rank"), 0)),
        "name": _safe_str(row.get("name"), code),
        "code": code,
        "price": _round(row.get("price"), 2),
        "changePct": _round(row.get("pct_change"), 2),
        "totalScore": _round(row.get("total_score"), 2),
        "trendScore": _round(row.get("trend_score"), 2),
        "volumeScore": _round(row.get("volume_score"), 2),
        "dmiScore": _round(row.get("dmi_score"), 2),
        "macdScore": _round(row.get("macd_score"), 2),
        "expmaScore": _round(row.get("expma_score"), 2),
        "moneyFlowScore": _round(row.get("money_flow_score", row.get("flow_score")), 2),
        "sectorScore": _round(row.get("sector_score"), 2),
        "trendQualityScore": _round(row.get("trend_quality_score"), 2),
        "entryTiming": entry_timing,
        "entryNote": _safe_str(row.get("entry_label"), "信号成立，建议结合T+1开盘与成交情况观察。"),
        "risks": risks,
        "riskNote": risk_note,
        "adx": _round(row.get("adx"), 2),
        "plusDI": _round(row.get("plus_di"), 2),
        "minusDI": _round(row.get("minus_di"), 2),
        "volRatio": _round(row.get("vol_ratio"), 2),
        "aboveMa20Days20": int(_safe_num(row.get("above_ma20_days_20"), 0)),
        "ma20Slope10Pct": _round(row.get("ma20_slope_10_pct"), 2),
        "ma20Slope20Pct": _round(row.get("ma20_slope_20_pct"), 2),
        "closeMa20Ratio": _round(row.get("close_ma20_ratio"), 4, 1.0),
        "macdDIF": _round(row.get("macd_diff"), 4),
        "macdDEA": _round(row.get("macd_dea"), 4),
        "macdHIST": _round(row.get("macd_hist"), 4),
        "moneyFlowRatio": _round(row.get("main_net_ratio"), 2),
        "sectorRankPct": _round(_safe_num(row.get("sector_rank_pct")) * 100, 2),
        "sectorInnerRankPct": _round(_safe_num(row.get("stock_rank_in_sector")) * 100, 2),
        "sector": sector,
    }


def _diagnostics(date_key: str, day_dir: str) -> List[Dict[str, Any]]:
    path = os.path.join(day_dir, f"tech_diagnostic_{date_key}.csv")
    df = _read_csv(path)
    items: List[Dict[str, Any]] = []
    if df.empty:
        return items

    for idx, row in df.iterrows():
        name = _safe_str(row.get("condition_name"), f"condition_{idx + 1}")
        total = int(_safe_num(row.get("before_count"), _safe_num(row.get("total"), 0)))
        passed = int(_safe_num(row.get("pass_count"), _safe_num(row.get("passed"), 0)))
        items.append({
            "id": name.lower().replace(" ", "_").replace("/", "_")[:80],
            "label": name,
            "passed": passed,
            "total": total,
        })
    return items


def _funnel(date_key: str, day_dir: str, selected_count: int) -> List[Dict[str, Any]]:
    path = os.path.join(day_dir, f"filter_log_{date_key}.csv")
    df = _read_csv(path)
    if not df.empty:
        result = []
        for _, row in df.iterrows():
            result.append({
                "stage": _safe_str(row.get("step_name"), "筛选步骤"),
                "count": int(_safe_num(row.get("after_count"), _safe_num(row.get("pass_count"), 0))),
            })
        if result:
            return result
    return [
        {"stage": "最终入选", "count": selected_count},
    ]


def _industry_dist(stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for stock in stocks:
        sector = stock.get("sector") or "未分类"
        counts[sector] = counts.get(sector, 0) + 1
    return [
        {"sector": sector, "count": count}
        for sector, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


def _build_daily_report(date_key: str) -> Optional[Dict[str, Any]]:
    day_dir = os.path.join(cfg.OUTPUT_DIR, date_key)
    pick_path = os.path.join(day_dir, f"stock_pick_{date_key}.csv")
    df = _read_csv(pick_path, dtype={"code": str})
    if df.empty:
        return None

    df = df.sort_values("total_score", ascending=False).head(cfg.TOP_N)
    stocks = [_stock_from_row(row) for _, row in df.iterrows()]
    for idx, stock in enumerate(stocks, start=1):
        stock["rank"] = idx

    selected_count = len(stocks)
    avg_score = _round(sum(s["totalScore"] for s in stocks) / selected_count if selected_count else 0, 2)
    risk_count = sum(1 for s in stocks if s["risks"])
    above80 = sum(1 for s in stocks if s["totalScore"] >= 80)
    diagnostics = _diagnostics(date_key, day_dir)
    final_diag = next((d for d in diagnostics if "最终" in d["label"]), None)
    pass_rate = _round((final_diag["passed"] / final_diag["total"] * 100) if final_diag and final_diag["total"] else 0, 2)
    strictest = min(
        [d for d in diagnostics if d["total"] and "最终" not in d["label"]],
        key=lambda d: d["passed"] / d["total"],
        default={"label": "暂无诊断数据"},
    )
    top = stocks[0] if stocks else {"name": "-", "code": "-", "totalScore": 0, "price": 0}
    files = _copy_artifacts(date_key, day_dir)
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    manifest = _read_json(os.path.join(day_dir, f"stock_pick_report_{date_key}.json"))
    if manifest.get("created_at"):
        generated_at = manifest["created_at"]

    status = "偏强" if selected_count >= 20 and avg_score >= 80 else "一般" if selected_count else "谨慎"
    narrative = (
        f"{_date_label(date_key)} 共选出 {selected_count} 只候选股，"
        f"最高分为 {top['name']}({top['code']})，平均分 {avg_score}。"
        f"当前最严格的技术条件是：{strictest['label']}。"
    )

    return {
        "date": _date_label(date_key),
        "mode": cfg.SCREEN_MODE,
        "generatedAt": generated_at,
        "files": files,
        "stocks": stocks,
        "summary": {
            "selectedCount": selected_count,
            "topStock": {
                "name": top["name"],
                "code": top["code"],
                "score": top["totalScore"],
                "price": top["price"],
            },
            "avgScore": avg_score,
            "riskCount": risk_count,
            "above80Count": above80,
            "passRate": pass_rate,
        },
        "conclusion": {
            "selectedCount": selected_count,
            "top5": [{"name": s["name"], "code": s["code"]} for s in stocks[:5]],
            "strictestCondition": strictest["label"],
            "chaseRisk": any(s["entryTiming"] == "追高谨慎" for s in stocks),
            "status": status,
            "narrative": narrative,
        },
        "diagnostics": diagnostics,
        "funnel": _funnel(date_key, day_dir, selected_count),
        "industryDist": _industry_dist(stocks),
    }


def _sample_status(valid_count: int) -> str:
    if valid_count >= 100:
        return "样本成熟"
    if valid_count >= 30:
        return "需要继续观察"
    return "样本不足"


def _build_backtest_data(latest_date_key: str) -> Optional[Dict[str, Any]]:
    day_dir = os.path.join(cfg.OUTPUT_DIR, latest_date_key)
    report_json = _read_json(os.path.join(day_dir, f"prediction_accuracy_report_{latest_date_key}.json"))
    summary = _read_csv(os.path.join(day_dir, f"prediction_accuracy_summary_{latest_date_key}.csv"))
    buckets = _read_csv(os.path.join(day_dir, f"prediction_accuracy_rank_buckets_{latest_date_key}.csv"))
    ic = _read_csv(os.path.join(day_dir, f"prediction_feature_ic_{latest_date_key}.csv"))
    details = _read_csv(os.path.join(day_dir, f"prediction_accuracy_details_{latest_date_key}.csv"), dtype={"code": str})
    if summary.empty and not report_json:
        return None

    sample_count = int(report_json.get("pick_count", _safe_num(summary.get("sample_count", pd.Series([0])).sum())))
    valid_count = int(report_json.get("evaluated_count", _safe_num(summary.get("sample_count", pd.Series([0])).sum())))
    range_start = _date_label(latest_date_key)
    range_end = _date_label(latest_date_key)
    if not details.empty and "trade_date" in details.columns:
        dates = pd.to_datetime(details["trade_date"], errors="coerce").dropna()
        if not dates.empty:
            range_start = dates.min().strftime("%Y-%m-%d")
            range_end = dates.max().strftime("%Y-%m-%d")

    holding_perf = []
    overview_row = summary.iloc[0] if not summary.empty else pd.Series(dtype=object)
    for _, row in summary.iterrows():
        hold = int(_safe_num(row.get("hold_days"), 0))
        holding_perf.append({
            "period": f"持有{hold}日",
            "samples": int(_safe_num(row.get("sample_count"), 0)),
            "winRate": _round(_safe_num(row.get("win_rate")) * 100, 2),
            "avgReturn": _round(row.get("average_return_pct"), 2),
            "medianReturn": _round(row.get("median_return_pct"), 2),
            "avgExcess": _round(row.get("average_excess_return_pct"), 2),
            "top5Precision": _round(_safe_num(row.get("precision_at_5")) * 100, 2),
            "top10Precision": _round(_safe_num(row.get("precision_at_10")) * 100, 2),
            "top20Precision": _round(_safe_num(row.get("precision_at_20")) * 100, 2),
            "maxDrawdown": _round(row.get("average_max_drawdown_pct"), 2),
        })

    layer_rows = []
    if not buckets.empty:
        first_hold = buckets["hold_days"].iloc[0] if "hold_days" in buckets.columns else None
        for _, row in buckets[buckets["hold_days"] == first_hold].iterrows():
            layer_rows.append({
                "layer": _safe_str(row.get("rank_bucket"), "rank"),
                "samples": int(_safe_num(row.get("sample_count"), 0)),
                "winRate": _round(_safe_num(row.get("win_rate")) * 100, 2),
                "avgReturn": _round(row.get("average_return_pct"), 2),
                "avgExcess": _round(row.get("average_excess_return_pct"), 2),
                "beatBenchmarkPct": _round(_safe_num(row.get("precision")) * 100, 2),
            })

    factor_ic = []
    if not ic.empty:
        first_hold = ic["hold_days"].iloc[0] if "hold_days" in ic.columns else None
        for _, row in ic[ic["hold_days"] == first_hold].head(20).iterrows():
            factor_ic.append({
                "factor": _safe_str(row.get("feature"), "feature"),
                "returnIC": _round(row.get("return_ic"), 4),
                "returnRankIC": _round(row.get("return_rank_ic"), 4),
                "excessIC": _round(row.get("excess_ic"), 4),
                "excessRankIC": _round(row.get("excess_rank_ic"), 4),
            })

    detail_rows = []
    if not details.empty:
        for _, row in details.head(120).iterrows():
            status = _safe_str(row.get("status"), "ok")
            detail_rows.append({
                "signalDate": _safe_str(row.get("trade_date"), "-")[:10],
                "name": _safe_str(row.get("name"), "-"),
                "code": _safe_str(row.get("code")).zfill(6),
                "rank": int(_safe_num(row.get("rank"), 0)),
                "signalPrice": _round(row.get("signal_price"), 2),
                "buyPrice": _round(row.get("buy_price"), 2),
                "holdingPeriod": f"{int(_safe_num(row.get('hold_days'), 0))}日",
                "sellDate": _safe_str(row.get("sell_date"), "-")[:10],
                "returnPct": None if status != "ok" else _round(row.get("return_pct"), 2),
                "benchmarkPct": None if status != "ok" else _round(row.get("benchmark_return_pct"), 2),
                "excessPct": None if status != "ok" else _round(row.get("excess_return_pct"), 2),
                "maxDrawdown": None if status != "ok" else _round(row.get("max_drawdown_pct"), 2),
                "profitable": None if status != "ok" else bool(_safe_num(row.get("return_pct")) > 0),
                "beatBenchmark": None if status != "ok" else bool(_safe_num(row.get("excess_return_pct")) > 0),
                "status": status if status in {"ok", "not_mature_yet", "no_kline", "signal_date_missing"} else "ok",
            })

    avg_return = _round(overview_row.get("average_return_pct"), 2)
    avg_excess = _round(overview_row.get("average_excess_return_pct"), 2)
    return {
        "rangeStart": range_start,
        "rangeEnd": range_end,
        "sampleCount": sample_count,
        "validCount": valid_count,
        "sampleStatus": _sample_status(valid_count),
        "overview": {
            "top20WinRate": _round(_safe_num(overview_row.get("win_rate")) * 100, 2),
            "top20BeatBenchmarkPct": _round(_safe_num(overview_row.get("precision_at_20")) * 100, 2),
            "avgReturn": avg_return,
            "avgExcess": avg_excess,
            "maxDrawdown": _round(overview_row.get("average_max_drawdown_pct"), 2),
        },
        "holdingPerf": holding_perf,
        "equityCurve": [],
        "hasBenchmark": bool("average_excess_return_pct" in summary.columns),
        "layers": layer_rows,
        "factorIC": factor_ic,
        "details": detail_rows,
    }


def export_frontend_data() -> Dict[str, Any]:
    """同步所有已有日期输出，返回生成清单。"""
    if not os.path.isdir(FRONTEND_DIR):
        raise FileNotFoundError(f"未找到前端目录: {FRONTEND_DIR}")

    os.makedirs(REPORT_DATA_DIR, exist_ok=True)
    date_keys = sorted(
        [name for name in os.listdir(cfg.OUTPUT_DIR) if _is_date_dir(name)],
        reverse=True,
    )

    reports: List[Dict[str, Any]] = []
    for date_key in date_keys:
        report = _build_daily_report(date_key)
        if not report:
            continue
        _write_json(os.path.join(REPORT_DATA_DIR, f"{date_key}.json"), report)
        reports.append(report)

    latest = reports[0] if reports else None
    latest_key = latest["date"].replace("-", "") if latest else None
    backtest = _build_backtest_data(latest_key) if latest_key else None
    if backtest:
        _write_json(os.path.join(DATA_DIR, "backtest.json"), backtest)

    history = [
        {
            "date": report["date"],
            "selectedCount": report["summary"]["selectedCount"],
            "topStock": report["summary"]["topStock"]["name"],
            "avgScore": report["summary"]["avgScore"],
            "files": report.get("files", {}),
        }
        for report in reports
    ]
    index = {
        "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "latestDate": latest["date"] if latest else None,
        "availableDates": [report["date"] for report in reports],
        "history": history,
        "reports": [
            {
                "date": report["date"],
                "selectedCount": report["summary"]["selectedCount"],
                "topStock": report["summary"]["topStock"],
                "avgScore": report["summary"]["avgScore"],
                "files": report.get("files", {}),
            }
            for report in reports
        ],
        "hasBacktest": backtest is not None,
    }
    _write_json(os.path.join(DATA_DIR, "report_index.json"), index)
    return {
        "index": os.path.join(DATA_DIR, "report_index.json"),
        "report_count": len(reports),
        "latest_date": index["latestDate"],
        "backtest": os.path.join(DATA_DIR, "backtest.json") if backtest else None,
    }


if __name__ == "__main__":
    manifest = export_frontend_data()
    print("前端数据已同步")
    print(f"  index: {manifest['index']}")
    print(f"  reports: {manifest['report_count']}")
    print(f"  latest: {manifest['latest_date']}")
    if manifest.get("backtest"):
        print(f"  backtest: {manifest['backtest']}")
