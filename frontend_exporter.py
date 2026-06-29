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
import subprocess
from typing import Any, Dict, List, Optional

import pandas as pd

import config as cfg


FRONTEND_DIR = os.path.join(cfg.BASE_DIR, "A股每日选股报告页面设计")
PUBLIC_DIR = os.path.join(FRONTEND_DIR, "public")
DATA_DIR = os.path.join(PUBLIC_DIR, "data")
REPORT_DATA_DIR = os.path.join(DATA_DIR, "reports")
PUBLIC_REPORT_DIR = os.path.join(PUBLIC_DIR, "reports")
SCREEN_MODES = ["normal", "strict", "loose"]


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


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _git_value(args: List[str], default: str = "") -> str:
    try:
        return subprocess.check_output(args, cwd=cfg.BASE_DIR, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return default


def _deployment_status() -> Dict[str, Any]:
    commit = _git_value(["git", "rev-parse", "--short", "HEAD"], "unknown")
    branch = _git_value(["git", "branch", "--show-current"], "main")
    repo = "a-share-daily-report"
    return {
        "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "commitSha": commit,
        "branch": branch,
        "githubPagesUrl": f"https://ppopink.github.io/{repo}/",
        "actionsUrl": f"https://github.com/ppopink/{repo}/actions",
    }


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


def _mode_pick_filename(date_key: str, mode: str) -> str:
    return f"stock_pick_{mode}_{date_key}.csv"


def _pick_path(date_key: str, day_dir: str, mode: str) -> str:
    mode_path = os.path.join(day_dir, _mode_pick_filename(date_key, mode))
    if os.path.exists(mode_path):
        return mode_path
    if mode == "normal":
        legacy_path = os.path.join(day_dir, f"stock_pick_{date_key}.csv")
        if os.path.exists(legacy_path):
            return legacy_path
    return mode_path


def _copy_artifacts(date_key: str, day_dir: str, mode: str = "normal") -> Dict[str, str]:
    """复制当日报告附件到前端 public/reports/YYYYMMDD。"""
    target_dir = os.path.join(PUBLIC_REPORT_DIR, date_key)
    os.makedirs(target_dir, exist_ok=True)

    files: Dict[str, str] = {}
    csv_name = os.path.basename(_pick_path(date_key, day_dir, mode))
    patterns = {
        "csv": csv_name,
        "hotSectorsCsv": f"hot_sectors_{date_key}.csv",
    }
    if mode == "normal":
        patterns.update({
            "excel": f"stock_pick_{date_key}.xlsx",
            "html": f"stock_pick_report_{date_key}.html",
            "pdf": f"stock_pick_report_{date_key}.pdf",
        })
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
    context_score = _safe_num(row.get("context_score"))
    lhb_count = _safe_num(row.get("lhb_count"))
    if context_score <= -2:
        risks.append({"level": "medium", "label": "事件/两融/龙虎榜偏负"})
    if lhb_count > 0:
        risks.append({"level": "low", "label": "近期上龙虎榜"})
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


def _load_kline_cache(date_key: str) -> pd.DataFrame:
    preferred = os.path.join(cfg.CACHE_DIR, f"kline_daily_{date_key}_{cfg.HISTORY_DAYS}.pkl")
    candidates = [preferred]
    if not os.path.exists(preferred):
        import glob
        candidates = sorted(glob.glob(os.path.join(cfg.CACHE_DIR, f"kline_daily_{date_key}_*.pkl")), reverse=True)
    for path in candidates:
        if os.path.exists(path):
            try:
                df = pd.read_pickle(path)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    df = df.copy()
                    df["code"] = df["code"].astype(str).str.zfill(6)
                    return df
            except Exception:
                continue
    return pd.DataFrame()


def _kline_points(kline_df: pd.DataFrame, code: str, limit: int = 60) -> List[Dict[str, Any]]:
    if kline_df.empty or "code" not in kline_df.columns:
        return []
    sub = kline_df[kline_df["code"].astype(str).str.zfill(6) == str(code).zfill(6)].copy()
    if sub.empty:
        return []
    sub = sub.sort_values("date").tail(limit).copy()
    sub["MA5"] = pd.to_numeric(sub["close"], errors="coerce").rolling(5).mean()
    sub["MA20"] = pd.to_numeric(sub["close"], errors="coerce").rolling(20).mean()

    points = []
    for _, row in sub.iterrows():
        points.append({
            "date": _safe_str(row.get("date")),
            "open": _round(row.get("open"), 3),
            "close": _round(row.get("close"), 3),
            "high": _round(row.get("high"), 3),
            "low": _round(row.get("low"), 3),
            "volume": _round(row.get("volume"), 0),
            "ma5": None if pd.isna(row.get("MA5")) else _round(row.get("MA5"), 3),
            "ma20": None if pd.isna(row.get("MA20")) else _round(row.get("MA20"), 3),
        })
    return points


def _stock_from_row(row: pd.Series, kline_df: pd.DataFrame = None, recent_stats: Dict[str, Any] = None) -> Dict[str, Any]:
    risks = _risk_flags(row)
    entry_timing = _entry_timing(row)
    risk_note = "暂无明显风险信号。" if not risks else "；".join(r["label"] for r in risks) + "。注意控制仓位。"
    code = _safe_str(row.get("code")).zfill(6)
    sector = _safe_str(row.get("industry"), "未分类")
    recent = (recent_stats or {}).get(code, {})
    prediction = _prediction_from_stock(row, risks)

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
        "contextScore": _round(row.get("context_score"), 2),
        "eventScore": _round(row.get("event_score"), 2),
        "eventCount": int(_safe_num(row.get("event_count"), 0)),
        "eventNote": _safe_str(row.get("event_note"), "近期公告中性"),
        "eventTitles": _safe_str(row.get("event_titles")),
        "marginScore": _round(row.get("margin_score"), 2),
        "marginBalanceChangePct": _round(row.get("margin_balance_change_pct"), 2),
        "marginNetBuy": _round(row.get("margin_net_buy"), 2),
        "marginNote": _safe_str(row.get("margin_note"), "两融变化中性"),
        "lhbScore": _round(row.get("lhb_score"), 2),
        "lhbCount": int(_safe_num(row.get("lhb_count"), 0)),
        "lhbNetBuy": _round(row.get("lhb_net_buy"), 2),
        "lhbNote": _safe_str(row.get("lhb_note"), "近期未上龙虎榜"),
        "contextNote": _safe_str(row.get("context_note"), "上下文数据中性"),
        "selectionReason": _safe_str(row.get("selection_reason"), "综合规则排序靠前"),
        "watchReason": _safe_str(row.get("watch_reason"), "按T+1开盘条件执行"),
        "buyAction": _safe_str(row.get("buy_action"), "轻仓观察"),
        "buyTrigger": _safe_str(row.get("buy_trigger"), "等待T+1开盘确认。"),
        "buyAvoidRules": _safe_str(row.get("buy_avoid_rules"), "涨停、停牌、高开过大或放量走弱不买。"),
        "maxOpenGapPct": _round(row.get("max_open_gap_pct"), 2),
        "maxBuyPrice": _round(row.get("max_buy_price"), 2),
        "pullbackBuyPrice": _round(row.get("pullback_buy_price"), 2),
        "invalidBelowPrice": _round(row.get("invalid_below_price"), 2),
        "recentPickCount": int(_safe_num(recent.get("recentPickCount"), 1)),
        "consecutivePickDays": int(_safe_num(recent.get("consecutivePickDays"), 1)),
        "firstSeenDate": _safe_str(recent.get("firstSeenDate"), _date_label(_safe_str(row.get("trade_date"), "")) if row.get("trade_date") else ""),
        "recentPickNote": _safe_str(recent.get("recentPickNote"), "首次或近期入选次数较少"),
        **prediction,
        "trendQualityScore": _round(row.get("trend_quality_score"), 2),
        "entryTiming": entry_timing,
        "entryNote": _safe_str(row.get("entry_label"), "信号成立，建议结合T+1开盘与成交情况观察。"),
        "risks": risks,
        "riskNote": risk_note,
        "plannedHoldingDays": int(_safe_num(row.get("planned_holding_days"), 5)),
        "stopLossPrice": _round(row.get("stop_loss_price"), 2),
        "takeProfit1Price": _round(row.get("take_profit_1_price"), 2),
        "takeProfit2Price": _round(row.get("take_profit_2_price"), 2),
        "trailingStopPrice": _round(row.get("trailing_stop_price"), 2),
        "riskRewardRatio": _round(row.get("risk_reward_ratio"), 2),
        "exitStrategy": _safe_str(row.get("exit_strategy"), ""),
        "exitSignal": _safe_str(row.get("exit_signal"), ""),
        "exitNote": _safe_str(row.get("exit_note"), ""),
        "day1StopLossPrice": _round(row.get("day1_stop_loss_price"), 2),
        "day1TakeProfitPrice": _round(row.get("day1_take_profit_price"), 2),
        "day1ExitPlan": _safe_str(row.get("day1_exit_plan"), ""),
        "day2StopLossPrice": _round(row.get("day2_stop_loss_price"), 2),
        "day2TakeProfitPrice": _round(row.get("day2_take_profit_price"), 2),
        "day2ExitPlan": _safe_str(row.get("day2_exit_plan"), ""),
        "day3StopLossPrice": _round(row.get("day3_stop_loss_price"), 2),
        "day3TakeProfitPrice": _round(row.get("day3_take_profit_price"), 2),
        "day3ExitPlan": _safe_str(row.get("day3_exit_plan"), ""),
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
        "kline": _kline_points(kline_df if kline_df is not None else pd.DataFrame(), code),
    }


def _diagnostics(date_key: str, day_dir: str, mode: str = "normal") -> List[Dict[str, Any]]:
    mode_path = os.path.join(day_dir, f"tech_diagnostic_{mode}_{date_key}.csv")
    path = mode_path if os.path.exists(mode_path) else os.path.join(day_dir, f"tech_diagnostic_{date_key}.csv")
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


def _funnel(date_key: str, day_dir: str, selected_count: int, mode: str = "normal") -> List[Dict[str, Any]]:
    mode_path = os.path.join(day_dir, f"filter_log_{mode}_{date_key}.csv")
    path = mode_path if os.path.exists(mode_path) else os.path.join(day_dir, f"filter_log_{date_key}.csv")
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


def _hot_sectors(date_key: str, day_dir: str) -> List[Dict[str, Any]]:
    path = os.path.join(day_dir, f"hot_sectors_{date_key}.csv")
    df = _read_csv(path, dtype={"sector_code": str, "leader_code": str})
    if df.empty:
        return []

    sectors: List[Dict[str, Any]] = []
    for _, row in df.head(getattr(cfg, "HOT_SECTOR_TOP_N", 8)).iterrows():
        sectors.append({
            "rank": int(_safe_num(row.get("sector_rank"), len(sectors) + 1)),
            "code": _safe_str(row.get("sector_code")),
            "name": _safe_str(row.get("sector_name"), "未命名板块"),
            "heatScore": _round(row.get("heat_score"), 2),
            "pctChange": _round(row.get("pct_change"), 2),
            "amount": _round(row.get("amount"), 2),
            "turnover": _round(row.get("turnover"), 2),
            "upCount": int(_safe_num(row.get("up_count"), 0)),
            "downCount": int(_safe_num(row.get("down_count"), 0)),
            "flatCount": int(_safe_num(row.get("flat_count"), 0)),
            "stockCount": int(_safe_num(row.get("stock_count"), 0)),
            "upRatio": _round(_safe_num(row.get("up_ratio")) * 100, 2),
            "selectedCount": int(_safe_num(row.get("selected_count"), 0)),
            "leaderName": _safe_str(row.get("leader_name")),
            "leaderCode": _safe_str(row.get("leader_code")),
            "leaderPctChange": _round(row.get("leader_pct_change"), 2),
            "leadingStocks": _safe_str(row.get("leading_stocks")),
            "quantNote": _safe_str(row.get("quant_note")),
            "dataSource": _safe_str(row.get("data_source")),
        })
    return sectors


def _build_recent_pick_stats(date_key: str, mode: str = "normal", window: int = 5) -> Dict[str, Dict[str, Any]]:
    date_keys = sorted(
        [name for name in os.listdir(cfg.OUTPUT_DIR) if _is_date_dir(name) and name <= date_key],
        reverse=True,
    )[:window]
    appearances: Dict[str, List[str]] = {}
    for key in date_keys:
        day_dir = os.path.join(cfg.OUTPUT_DIR, key)
        path = _pick_path(key, day_dir, mode)
        if not os.path.exists(path):
            continue
        df = _read_csv(path, dtype={"code": str})
        if df.empty or "code" not in df.columns:
            continue
        for code in df["code"].dropna().astype(str).str.zfill(6).unique():
            appearances.setdefault(code, []).append(_date_label(key))

    stats: Dict[str, Dict[str, Any]] = {}
    current_label = _date_label(date_key)
    ordered_labels = [_date_label(k) for k in date_keys]
    for code, dates in appearances.items():
        consecutive = 0
        date_set = set(dates)
        for label in ordered_labels:
            if label in date_set:
                consecutive += 1
            else:
                break
        count = len(dates)
        first_seen = dates[-1] if dates else current_label
        if consecutive >= 3:
            note = f"连续{consecutive}次入选，注意是否已进入拥挤交易"
        elif count >= 3:
            note = f"近{window}次报告第{count}次入选，需关注是否已兑现涨幅"
        elif count == 2:
            note = "近期第2次入选，信号有延续"
        else:
            note = "首次或近期入选次数较少"
        stats[code] = {
            "recentPickCount": count,
            "consecutivePickDays": consecutive,
            "firstSeenDate": first_seen,
            "recentPickNote": note,
        }
    return stats


def _prediction_from_stock(row: pd.Series, risks: List[Dict[str, str]]) -> Dict[str, Any]:
    """轻量规则校准预测，用于前端展示未来模型字段的形态。"""
    score = _safe_num(row.get("total_score"), 60)
    vol_ratio = _safe_num(row.get("vol_ratio"), 1)
    trend_quality = _safe_num(row.get("trend_quality_score"), 0)
    context_score = _safe_num(row.get("context_score"), 0)
    action = _safe_str(row.get("buy_action"), "轻仓观察")
    pct_change = _safe_num(row.get("pct_change"), 0)

    base = 48 + (score - 70) * 0.55
    base += _clip((vol_ratio - 1.2) * 3, -3, 5)
    base += _clip((trend_quality - 8) * 0.6, -3, 4)
    base += _clip(context_score * 0.6, -4, 4)
    if action == "可积极观察":
        base += 3
    elif action == "等回踩确认":
        base -= 3
    if pct_change >= 8:
        base -= 4
    if risks:
        base -= min(6, len(risks) * 2)

    p1 = _clip(base, 35, 72)
    p2 = _clip(p1 + 1.5 - max(0, pct_change - 5) * 0.25, 35, 74)
    p3 = _clip(p2 + 1.0 + min(context_score, 4) * 0.2, 35, 76)
    avg = (p1 + p2 + p3) / 3
    if avg >= 62 and score >= 80 and len(risks) <= 1:
        confidence = "高"
    elif avg >= 54:
        confidence = "中"
    else:
        confidence = "低"

    return {
        "predictedWinProb1d": round(p1, 2),
        "predictedWinProb2d": round(p2, 2),
        "predictedWinProb3d": round(p3, 2),
        "predictionConfidence": confidence,
        "predictionNote": (
            f"规则校准预测：1日{p1:.1f}%、2日{p2:.1f}%、3日{p3:.1f}%。"
            "该概率来自规则分、趋势质量和上下文风险的轻量校准，尚非机器学习模型。"
        ),
        "modelVersion": "rule_calibrated_v1",
    }


def _market_guard(date_key: str, day_dir: str) -> Dict[str, Any]:
    path = os.path.join(day_dir, f"market_guard_{date_key}.csv")
    df = _read_csv(path)
    if df.empty:
        return {
            "marketStatus": "数据不足",
            "riskLevel": "medium",
            "positionAdvice": "轻仓观察",
            "tradePermission": "谨慎",
            "marketNote": "暂无市场宽度数据。",
            "totalCount": 0,
            "upCount": 0,
            "downCount": 0,
            "upRatio": 0,
            "avgPctChange": 0,
            "limitUpCount": 0,
            "limitDownCount": 0,
            "totalAmount": 0,
        }
    row = df.iloc[0]
    return {
        "marketStatus": _safe_str(row.get("market_status"), "数据不足"),
        "riskLevel": _safe_str(row.get("risk_level"), "medium"),
        "positionAdvice": _safe_str(row.get("position_advice"), "轻仓观察"),
        "tradePermission": _safe_str(row.get("trade_permission"), "谨慎"),
        "marketNote": _safe_str(row.get("market_note"), "暂无市场宽度数据。"),
        "totalCount": int(_safe_num(row.get("total_count"), 0)),
        "upCount": int(_safe_num(row.get("up_count"), 0)),
        "downCount": int(_safe_num(row.get("down_count"), 0)),
        "upRatio": _round(_safe_num(row.get("up_ratio")) * 100, 2),
        "avgPctChange": _round(row.get("avg_pct_change"), 2),
        "limitUpCount": int(_safe_num(row.get("limit_up_count"), 0)),
        "limitDownCount": int(_safe_num(row.get("limit_down_count"), 0)),
        "totalAmount": _round(row.get("total_amount"), 2),
    }


def _data_quality(stocks: List[Dict[str, Any]], hot_sectors: List[Dict[str, Any]]) -> Dict[str, Any]:
    count = len(stocks)
    money_flow_ok = sum(1 for s in stocks if abs(_safe_num(s.get("moneyFlowRatio"))) > 0)
    context_ok = sum(1 for s in stocks if _safe_str(s.get("contextNote")) and _safe_str(s.get("contextNote")) != "上下文数据中性")
    industry_ok = sum(1 for s in stocks if _safe_str(s.get("sector")) not in {"", "未分类"})
    hot_source = _safe_str(hot_sectors[0].get("dataSource")) if hot_sectors else "暂无板块数据"

    money_pct = round(money_flow_ok / count * 100, 2) if count else 0
    context_pct = round(context_ok / count * 100, 2) if count else 0
    industry_pct = round(industry_ok / count * 100, 2) if count else 0
    notes = []
    if industry_pct < 60:
        notes.append("行业字段覆盖不足，热门板块联动可能无法精确匹配入选股。")
    if money_pct < 80:
        notes.append("部分资金流来自估算或缺失，资金分需要谨慎解读。")
    if context_pct < 50:
        notes.append("大事件/两融/龙虎榜数据覆盖有限，未命中不代表没有事件。")
    if not notes:
        notes.append("主要数据字段覆盖较完整。")

    return {
        "klineStatus": "已同步最近K线",
        "moneyFlowStatus": "资金流API+估算",
        "contextStatus": "大事件/两融/龙虎榜缓存",
        "industryStatus": "行业字段来自行情源",
        "hotSectorSource": hot_source,
        "stockCount": count,
        "moneyFlowCoveragePct": money_pct,
        "contextCoveragePct": context_pct,
        "industryCoveragePct": industry_pct,
        "notes": notes,
    }


def _build_daily_report(date_key: str, mode: str = "normal") -> Optional[Dict[str, Any]]:
    day_dir = os.path.join(cfg.OUTPUT_DIR, date_key)
    pick_path = _pick_path(date_key, day_dir, mode)
    if not os.path.exists(pick_path):
        return None
    df = _read_csv(pick_path, dtype={"code": str})

    if not df.empty and "total_score" in df.columns:
        df = df.sort_values("total_score", ascending=False).head(cfg.TOP_N)
    kline_df = _load_kline_cache(date_key)
    recent_stats = _build_recent_pick_stats(date_key, mode)
    stocks = [_stock_from_row(row, kline_df, recent_stats) for _, row in df.iterrows()]
    for idx, stock in enumerate(stocks, start=1):
        stock["rank"] = idx

    selected_count = len(stocks)
    avg_score = _round(sum(s["totalScore"] for s in stocks) / selected_count if selected_count else 0, 2)
    risk_count = sum(1 for s in stocks if s["risks"])
    above80 = sum(1 for s in stocks if s["totalScore"] >= 80)
    diagnostics = _diagnostics(date_key, day_dir, mode)
    market_guard = _market_guard(date_key, day_dir)
    final_diag = next((d for d in diagnostics if "最终" in d["label"]), None)
    pass_rate = _round((final_diag["passed"] / final_diag["total"] * 100) if final_diag and final_diag["total"] else 0, 2)
    strictest = min(
        [d for d in diagnostics if d["total"] and "最终" not in d["label"]],
        key=lambda d: d["passed"] / d["total"],
        default={"label": "暂无诊断数据"},
    )
    top = stocks[0] if stocks else {"name": "-", "code": "-", "totalScore": 0, "price": 0}
    files = _copy_artifacts(date_key, day_dir, mode)
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    manifest = _read_json(os.path.join(day_dir, f"stock_pick_report_{date_key}.json"))
    if manifest.get("created_at"):
        generated_at = manifest["created_at"]

    status = "偏强" if selected_count >= 20 and avg_score >= 80 else "一般" if selected_count else "谨慎"
    narrative = (
        f"{_date_label(date_key)} {mode} 模式共选出 {selected_count} 只候选股，"
        f"最高分为 {top['name']}({top['code']})，平均分 {avg_score}。"
        f"当前最严格的技术条件是：{strictest['label']}。"
    )

    hot_sectors = _hot_sectors(date_key, day_dir)
    return {
        "date": _date_label(date_key),
        "mode": mode,
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
        "marketGuard": market_guard,
        "dataQuality": _data_quality(stocks, hot_sectors),
        "conclusion": {
            "selectedCount": selected_count,
            "top5": [{"name": s["name"], "code": s["code"]} for s in stocks[:5]],
            "strictestCondition": strictest["label"],
            "chaseRisk": any(s["entryTiming"] == "追高谨慎" for s in stocks),
            "status": status,
            "narrative": narrative,
            "marketAdvice": market_guard["marketNote"],
        },
        "diagnostics": diagnostics,
        "funnel": _funnel(date_key, day_dir, selected_count, mode),
        "industryDist": _industry_dist(stocks),
        "hotSectors": hot_sectors,
    }


def _sample_status(valid_count: int) -> str:
    if valid_count >= 100:
        return "样本成熟"
    if valid_count >= 30:
        return "需要继续观察"
    return "样本不足"


def _strategy_insights(
    holding_perf: List[Dict[str, Any]],
    factor_ic: List[Dict[str, Any]],
    valid_count: int,
) -> List[Dict[str, str]]:
    insights: List[Dict[str, str]] = []

    if holding_perf:
        best_period = max(
            holding_perf,
            key=lambda item: (
                _safe_num(item.get("avgExcess")),
                _safe_num(item.get("winRate")),
                _safe_num(item.get("avgReturn")),
            ),
        )
        win_rate = _safe_num(best_period.get("winRate"))
        avg_excess = _safe_num(best_period.get("avgExcess"))
        level = "good" if avg_excess > 0 and win_rate >= 50 else "neutral" if win_rate >= 45 else "risk"
        insights.append({
            "title": "当前更优持有期",
            "value": _safe_str(best_period.get("period"), "待观察"),
            "note": f"胜率 {win_rate:.2f}%，平均超额 {avg_excess:.2f}%。短线执行优先参考该周期，但仍需结合T+1开盘。",
            "level": level,
        })

    if factor_ic:
        best_factor = max(factor_ic, key=lambda item: _safe_num(item.get("returnRankIC")))
        rank_ic = _safe_num(best_factor.get("returnRankIC"))
        insights.append({
            "title": "近期较强因子",
            "value": _safe_str(best_factor.get("factor"), "暂无"),
            "note": f"return_rank_ic {rank_ic:.2f}。正值说明该因子近期排序与收益方向更一致。",
            "level": "good" if rank_ic > 0.05 else "neutral" if rank_ic >= 0 else "risk",
        })

    status = _sample_status(valid_count)
    if valid_count < 30:
        sample_note = "已评估样本少，不能据此判断策略稳定性，建议继续累计每日预测结果。"
        level = "risk"
    elif valid_count < 100:
        sample_note = "样本开始可读，但仍容易受单日行情影响，适合做方向性参考。"
        level = "neutral"
    else:
        sample_note = "样本量较充分，可以更认真比较持有期、分层收益和因子有效性。"
        level = "good"
    insights.append({
        "title": "样本可信度",
        "value": status,
        "note": f"当前有效样本 {valid_count} 条。{sample_note}",
        "level": level,
    })

    return insights


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
    strategy_insights = _strategy_insights(holding_perf, factor_ic, valid_count)
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
        "strategyInsights": strategy_insights,
    }


def _latest_backtest_date(date_keys: List[str]) -> Optional[str]:
    for date_key in date_keys:
        day_dir = os.path.join(cfg.OUTPUT_DIR, date_key)
        has_summary = os.path.exists(os.path.join(day_dir, f"prediction_accuracy_summary_{date_key}.csv"))
        has_report = os.path.exists(os.path.join(day_dir, f"prediction_accuracy_report_{date_key}.json"))
        if has_summary or has_report:
            return date_key
    return None


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
    available_modes_by_date: Dict[str, List[str]] = {}
    for date_key in date_keys:
        mode_reports: Dict[str, Dict[str, Any]] = {}
        for mode in SCREEN_MODES:
            report = _build_daily_report(date_key, mode)
            if not report:
                continue
            _write_json(os.path.join(REPORT_DATA_DIR, f"{date_key}_{mode}.json"), report)
            mode_reports[mode] = report

        if not mode_reports:
            continue

        report = mode_reports.get("normal") or next(iter(mode_reports.values()))
        _write_json(os.path.join(REPORT_DATA_DIR, f"{date_key}.json"), report)
        available_modes_by_date[report["date"]] = list(mode_reports.keys())
        reports.append(report)

    latest = reports[0] if reports else None
    latest_backtest_key = _latest_backtest_date(date_keys)
    backtest = _build_backtest_data(latest_backtest_key) if latest_backtest_key else None
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
    deployment = _deployment_status()
    index = {
        "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "deploymentStatus": deployment,
        "latestDate": latest["date"] if latest else None,
        "availableDates": [report["date"] for report in reports],
        "availableModesByDate": available_modes_by_date,
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
        "backtestDate": _date_label(latest_backtest_key) if latest_backtest_key else None,
    }
    _write_json(os.path.join(DATA_DIR, "report_index.json"), index)
    return {
        "index": os.path.join(DATA_DIR, "report_index.json"),
        "report_count": len(reports),
        "latest_date": index["latestDate"],
        "deployment_status": deployment,
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
