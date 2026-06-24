"""
主筛选引擎 — 串联数据获取 → 指标计算 → 条件过滤 → 综合评分 → 排序输出
"""

import datetime
import os
import time
import pandas as pd
import numpy as np
from typing import Optional

import config as cfg
import data_fetcher
from data_fetcher import (
    get_stock_list,
    get_stock_histories_batch,
    get_money_flow_batch,
    estimate_money_flow_from_kline,
    build_sector_score_map,
    get_hot_sector_boards,
)
from indicators import calculate_all_indicators, check_all_conditions, evaluate_technical_conditions
from scorer import compute_total_scores
from utils import output_path


def _filter_log_row(step_name: str, before_count: int, after_count: int) -> dict:
    pass_count = after_count
    pass_rate = pass_count / before_count if before_count else 0
    return {
        "step_name": step_name,
        "before_count": int(before_count),
        "after_count": int(after_count),
        "pass_count": int(pass_count),
        "pass_rate": round(pass_rate, 4),
    }


def _save_filter_log(rows: list, trade_date: datetime.date = None) -> str:
    if trade_date is None:
        trade_date = datetime.date.today()
    path = output_path(f"filter_log_{trade_date.strftime('%Y%m%d')}.csv", trade_date)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _fallback_hot_sectors_from_spot(spot_df: pd.DataFrame, selected_df: pd.DataFrame = None) -> pd.DataFrame:
    """当远程板块接口不可用时，用本地行情聚合生成保守版热度榜。"""
    if spot_df is None or spot_df.empty:
        return pd.DataFrame()
    df = spot_df.copy()
    df["pct_change"] = pd.to_numeric(df.get("pct_change", 0), errors="coerce").fillna(0)
    df["amount"] = pd.to_numeric(df.get("amount", 0), errors="coerce").fillna(0)
    if "industry" in df.columns and df["industry"].fillna("").astype(str).str.strip().ne("").any():
        df["sector_name"] = df["industry"].fillna("").astype(str).str.strip()
        df = df[df["sector_name"] != ""]
    else:
        # 行业字段缺失时，明确标记为行情强势分组，不伪装成真实板块。
        df["sector_name"] = "未分类强势组"

    if df.empty:
        return pd.DataFrame()

    grouped = (
        df.groupby("sector_name")
        .agg(
            pct_change=("pct_change", "mean"),
            amount=("amount", "sum"),
            stock_count=("code", "count"),
            up_count=("pct_change", lambda s: int((s > 0).sum())),
            down_count=("pct_change", lambda s: int((s < 0).sum())),
            strong_count=("pct_change", lambda s: int((s >= 5).sum())),
        )
        .reset_index()
    )
    grouped["up_ratio"] = grouped["up_count"] / grouped["stock_count"].replace(0, np.nan)
    grouped["strong_ratio"] = grouped["strong_count"] / grouped["stock_count"].replace(0, np.nan)

    top_stocks = []
    for sector_name, sub in df.groupby("sector_name"):
        leaders = sub.sort_values("pct_change", ascending=False).head(3)
        leader = leaders.iloc[0]
        top_stocks.append({
            "sector_name": sector_name,
            "leader_name": leader.get("name", ""),
            "leader_code": str(leader.get("code", "")),
            "leader_pct_change": float(leader.get("pct_change", 0)),
            "leading_stocks": "；".join(
                f"{r.get('name', '')}({str(r.get('code', ''))}) {float(r.get('pct_change', 0)):.2f}%"
                for _, r in leaders.iterrows()
            ),
        })
    grouped = grouped.merge(pd.DataFrame(top_stocks), on="sector_name", how="left")

    pct_norm = (grouped["pct_change"] - grouped["pct_change"].min()) / max(grouped["pct_change"].max() - grouped["pct_change"].min(), 1e-9)
    amount_norm = (grouped["amount"] - grouped["amount"].min()) / max(grouped["amount"].max() - grouped["amount"].min(), 1e-9)
    grouped["heat_score"] = (
        pct_norm.fillna(0) * 45
        + grouped["up_ratio"].fillna(0).clip(0, 1) * 25
        + grouped["strong_ratio"].fillna(0).clip(0, 1) * 15
        + amount_norm.fillna(0) * 15
    ).round(2)
    grouped["sector_code"] = ""
    grouped["turnover"] = 0.0
    grouped["flat_count"] = grouped["stock_count"] - grouped["up_count"] - grouped["down_count"]
    grouped = grouped.sort_values(["heat_score", "pct_change"], ascending=[False, False]).reset_index(drop=True)
    grouped.insert(0, "sector_rank", range(1, len(grouped) + 1))
    grouped["quant_note"] = grouped.apply(
        lambda r: (
            f"热度{r['heat_score']:.1f} = 平均涨幅{r['pct_change']:.2f}%、"
            f"上涨占比{r['up_ratio'] * 100:.1f}%、强势股占比{r['strong_ratio'] * 100:.1f}%、"
            f"成交额{r['amount'] / 1e8:.1f}亿"
        ),
        axis=1,
    )
    return grouped


def _save_hot_sector_report(
    spot_df: pd.DataFrame,
    selected_df: pd.DataFrame = None,
    trade_date: datetime.date = None,
    verbose: bool = True,
) -> str:
    if trade_date is None:
        trade_date = datetime.date.today()
    date_str = trade_date.strftime("%Y%m%d")
    hot = get_hot_sector_boards(limit=max(getattr(cfg, "HOT_SECTOR_TOP_N", 8), 8))
    source = "东方财富行业板块"
    if hot.empty:
        hot = _fallback_hot_sectors_from_spot(spot_df, selected_df)
        source = "本地行情聚合"

    if selected_df is not None and not selected_df.empty and "industry" in selected_df.columns and not hot.empty:
        selected = selected_df.copy()
        selected["industry"] = selected["industry"].fillna("").astype(str).str.strip()
        selected_counts = selected[selected["industry"] != ""].groupby("industry")["code"].count().to_dict()
        hot["selected_count"] = hot["sector_name"].map(selected_counts).fillna(0).astype(int)
    elif not hot.empty:
        hot["selected_count"] = 0

    if not hot.empty:
        hot["data_source"] = source
        hot = hot.head(getattr(cfg, "HOT_SECTOR_TOP_N", 8)).copy()

    cols = [
        "sector_rank", "sector_code", "sector_name", "heat_score",
        "pct_change", "amount", "turnover", "up_count", "down_count",
        "flat_count", "stock_count", "up_ratio", "selected_count",
        "leader_name", "leader_code", "leader_pct_change", "leading_stocks",
        "quant_note", "data_source",
    ]
    path = output_path(f"hot_sectors_{date_str}.csv", trade_date)
    save_df = hot[[c for c in cols if c in hot.columns]].copy() if not hot.empty else pd.DataFrame(columns=cols)
    save_df.to_csv(path, index=False, encoding="utf-8-sig")
    if verbose:
        print(f"[板块] 热门板块榜: {path} ({len(save_df)} 个, {source})")
        for _, row in save_df.head(5).iterrows():
            print(
                f"  {int(row.get('sector_rank', 0))}. {row.get('sector_name', '')} "
                f"热度 {float(row.get('heat_score', 0)):.1f} | "
                f"涨幅 {float(row.get('pct_change', 0)):.2f}% | "
                f"上涨占比 {float(row.get('up_ratio', 0)) * 100:.1f}% | "
                f"领涨 {row.get('leader_name', '')}"
            )
    return path


TECH_CONDITION_LABELS = [
    ("close > MA3 > MA5 > MA21", "ma_stack"),
    ("close > MA20 today", "current_above_ma20"),
    ("MA20 persistence days within 20", "above_ma20_days_ok"),
    ("MA20 slope up", "ma20_slope_ok"),
    ("close not overheated vs MA20", "ma20_not_overheated"),
    ("MA20 trend quality", "trend_quality_ok"),
    ("+DI > -DI", "pdi_gt_mdi"),
    ("ADX > ADX_THRESHOLD", "adx_enough"),
    ("volume / previous_5day_avg_volume >= VOL_MULT", "volume_enough"),
    ("EXPMA7 > EXPMA21", "expma_bull"),
    ("EXPMA7 recent golden cross within N days", "expma_recent_cross"),
    ("DIF > 0 and DEA > 0", "dif_dea_above_zero"),
    ("DIF > DEA", "dif_gt_dea"),
    ("MACD golden cross above zero", "macd_golden_cross_above_zero"),
    ("MACD second golden cross above zero", "macd_second_gc_above_zero"),
    ("MACD second golden cross within N days", "macd_second_gc_recent"),
    ("最终技术面通过", "technical_pass"),
]


FAIL_REASON_MAP = {
    "ma_stack": "MA_NOT_BULLISH",
    "current_above_ma20": "CLOSE_NOT_ABOVE_MA20",
    "above_ma20_days_ok": "MA20_PERSISTENCE_NOT_ENOUGH",
    "ma20_slope_ok": "MA20_SLOPE_NOT_ENOUGH",
    "ma20_not_overheated": "CLOSE_TOO_FAR_FROM_MA20",
    "trend_quality_ok": "TREND_QUALITY_NOT_OK",
    "pdi_gt_mdi": "PDI_NOT_GT_MDI",
    "adx_enough": "ADX_NOT_ENOUGH",
    "volume_enough": "VOLUME_NOT_ENOUGH",
    "expma_bull": "EXPMA_NOT_BULL",
    "expma_recent_cross": "NO_EXPMA_RECENT_CROSS",
    "dif_dea_above_zero": "MACD_NOT_ABOVE_ZERO",
    "dif_gt_dea": "DIF_NOT_GT_DEA",
    "macd_golden_cross_above_zero": "NO_MACD_GC_ABOVE_ZERO",
    "macd_second_gc_above_zero": "NO_MACD_SECOND_GC",
    "macd_second_gc_recent": "NO_MACD_SECOND_GC_RECENT",
}


def _save_tech_diagnostics(rows: list, verbose: bool = True, trade_date: datetime.date = None) -> tuple[str, str]:
    if trade_date is None:
        trade_date = datetime.date.today()
    date_str = trade_date.strftime("%Y%m%d")
    total = len(rows)

    diag_rows = []
    for label, key in TECH_CONDITION_LABELS:
        pass_count = sum(1 for r in rows if r.get(key))
        fail_count = total - pass_count
        diag_rows.append({
            "condition_name": label,
            "before_count": total,
            "pass_count": pass_count,
            "pass_rate": round(pass_count / total, 4) if total else 0,
            "fail_count": fail_count,
            "fail_rate": round(fail_count / total, 4) if total else 0,
        })

    diag_path = output_path(f"tech_diagnostic_{date_str}.csv", trade_date)
    pd.DataFrame(diag_rows).to_csv(diag_path, index=False, encoding="utf-8-sig")

    fail_rows = []
    for r in rows:
        failed = [reason for key, reason in FAIL_REASON_MAP.items() if not r.get(key)]
        fail_rows.append({
            "ts_code": r.get("code", ""),
            "stock_name": r.get("name", ""),
            "close": r.get("close", np.nan),
            "ma3": r.get("ma3", np.nan),
            "ma5": r.get("ma5", np.nan),
            "ma20": r.get("ma20", np.nan),
            "ma21": r.get("ma21", np.nan),
            "above_ma20_days_20": r.get("above_ma20_days_20", np.nan),
            "ma20_slope_10_pct": r.get("ma20_slope_10_pct", np.nan),
            "ma20_slope_20_pct": r.get("ma20_slope_20_pct", np.nan),
            "close_ma20_ratio": r.get("close_ma20_ratio", np.nan),
            "pdi": r.get("pdi", np.nan),
            "mdi": r.get("mdi", np.nan),
            "adx": r.get("adx", np.nan),
            "vol_ratio": r.get("vol_ratio", np.nan),
            "expma7": r.get("expma7", np.nan),
            "expma21": r.get("expma21", np.nan),
            "dif": r.get("dif", np.nan),
            "dea": r.get("dea", np.nan),
            "macd_hist": r.get("macd_hist", np.nan),
            "failed_conditions": ";".join(failed),
        })
    fail_path = output_path(f"tech_fail_reasons_{date_str}.csv", trade_date)
    pd.DataFrame(fail_rows).to_csv(fail_path, index=False, encoding="utf-8-sig")

    if verbose:
        print("[诊断] 技术条件通过数量:")
        for row in diag_rows:
            print(f"  {row['condition_name']}: {row['pass_count']}/{row['before_count']} ({row['pass_rate']:.1%})")
        print(f"[诊断] 技术诊断: {diag_path}")
        print(f"[诊断] 失败原因: {fail_path}")
    return diag_path, fail_path


def _candidate_output_columns() -> list:
    return [
        "priority_rank", "priority_score",
        "code", "name", "close",
        "ma3", "ma5", "ma20", "ma21",
        "above_ma20_days_20", "ma20_slope_10_pct", "ma20_slope_20_pct", "close_ma20_ratio",
        "pdi", "mdi", "adx",
        "vol_ratio",
        "expma7", "expma21",
        "dif", "dea", "macd_hist",
        "ma_stack",
        "current_above_ma20",
        "above_ma20_days_ok",
        "ma20_slope_ok",
        "ma20_not_overheated",
        "trend_quality_ok",
        "pdi_gt_mdi",
        "adx_enough",
        "volume_enough",
        "expma_bull",
        "expma_recent_cross",
        "dif_dea_above_zero",
        "dif_gt_dea",
        "macd_golden_cross_above_zero",
        "macd_second_gc_above_zero",
        "macd_second_gc_recent",
        "technical_pass",
    ]


def _candidate_priority_score(row: dict) -> float:
    """技术候选优先级评分，用于候选清单从高到低排序。"""
    score = 0.0
    score += 20 if row.get("ma_stack") else 0
    score += 14 if row.get("trend_quality_ok") else 0
    score += min(float(row.get("above_ma20_days_20", 0) or 0), 20) / 20 * 8
    score += min(max(float(row.get("ma20_slope_10_pct", 0) or 0), 0), 6) / 6 * 6
    score += 4 if row.get("ma20_not_overheated") else 0
    score += 10 if row.get("pdi_gt_mdi") else 0
    score += 10 if row.get("adx_enough") else 0
    score += min(float(row.get("adx", 0) or 0), 60) / 60 * 10
    score += 10 if row.get("volume_enough") else 0
    score += min(float(row.get("vol_ratio", 0) or 0), 3) / 3 * 10
    score += 8 if row.get("expma_bull") else 0
    score += 8 if row.get("expma_recent_cross") else 0
    score += 8 if row.get("dif_dea_above_zero") else 0
    score += 8 if row.get("dif_gt_dea") else 0
    score += 8 if row.get("macd_second_gc_above_zero") else 0
    score += 8 if row.get("macd_second_gc_recent") else 0
    return round(score, 2)


def _save_technical_candidates(
    rows: list,
    mode: str,
    prefix: str = "technical_candidates",
    trade_date: datetime.date = None,
    verbose: bool = True,
) -> str:
    """保存某个模式下技术面通过股票的名称、代码和关键指标。"""
    if trade_date is None:
        trade_date = datetime.date.today()
    path = output_path(f"{prefix}_{mode}_{trade_date.strftime('%Y%m%d')}.csv", trade_date)
    selected = []
    for r in rows:
        if r.get("technical_pass"):
            item = dict(r)
            item["priority_score"] = _candidate_priority_score(item)
            selected.append(item)
    df = pd.DataFrame(selected)
    if not df.empty:
        df = df.sort_values(
            ["priority_score", "adx", "vol_ratio"],
            ascending=[False, False, False],
        ).reset_index(drop=True)
        df.insert(0, "priority_rank", range(1, len(df) + 1))
    cols = [c for c in _candidate_output_columns() if c in df.columns]
    if cols:
        df = df[cols]
    df.to_csv(path, index=False, encoding="utf-8-sig")
    if verbose:
        print(f"[候选] {mode} 技术候选股清单: {path} ({len(df)} 只)")
    return path


def _build_rule_filter_flags(
    symbols: list,
    spot_df: pd.DataFrame,
    money_flow_data: dict,
) -> pd.DataFrame:
    """按提示词第一版规则生成资金/成交额/板块过滤标记。"""
    if "code" not in spot_df.columns:
        base = spot_df.reset_index().copy()
    else:
        base = spot_df.copy()
    base["code"] = base["code"].astype(str)
    base = base[base["code"].isin(symbols)].copy()

    if base.empty:
        return pd.DataFrame(columns=["code", "amount_ok", "fund_ok", "sector_hot", "leading_stock"])

    base["amount"] = pd.to_numeric(base.get("amount", 0), errors="coerce").fillna(0)
    base["pct_change"] = pd.to_numeric(base.get("pct_change", 0), errors="coerce").fillna(0)
    base["amount_ok"] = base["amount"] >= cfg.MIN_AMOUNT
    base["fund_ok"] = base["code"].map(
        lambda c: float(money_flow_data.get(c, {}).get("total_inflow", 0)) > 0
    )

    has_industry = "industry" in base.columns and base["industry"].fillna("").astype(str).str.strip().ne("").any()
    if has_industry:
        full = spot_df.copy()
        full["industry"] = full["industry"].fillna("").astype(str).str.strip()
        full["pct_change"] = pd.to_numeric(full.get("pct_change", 0), errors="coerce").fillna(0)
        full = full[full["industry"] != ""]
        sector_perf = full.groupby("industry")["pct_change"].mean().rank(pct=True, ascending=False)
        stock_rank = full.groupby("industry")["pct_change"].rank(pct=True, ascending=False)
        full = full.assign(
            sector_rank_pct=full["industry"].map(sector_perf),
            stock_rank_in_sector=stock_rank,
        )
        ranks = full[["code", "sector_rank_pct", "stock_rank_in_sector"]].copy()
        ranks["code"] = ranks["code"].astype(str)
        base = base.merge(ranks, on="code", how="left")
        base["sector_hot"] = base["sector_rank_pct"].fillna(1) <= cfg.SECTOR_HOT_TOP_PCT
        base["leading_stock"] = base["stock_rank_in_sector"].fillna(1) <= cfg.LEADING_STOCK_TOP_PCT
    else:
        pct_rank = base["pct_change"].rank(pct=True, ascending=False)
        base["sector_rank_pct"] = pct_rank
        base["stock_rank_in_sector"] = pct_rank
        base["sector_hot"] = pct_rank <= cfg.SECTOR_HOT_TOP_PCT
        base["leading_stock"] = pct_rank <= cfg.LEADING_STOCK_TOP_PCT

    return base[[
        "code", "amount_ok", "fund_ok", "sector_hot", "leading_stock",
        "sector_rank_pct", "stock_rank_in_sector",
    ]]


def _apply_rule_hard_filters(
    symbols: list,
    spot_df: pd.DataFrame,
    money_flow_data: dict,
    verbose: bool = True,
) -> tuple[list, pd.DataFrame]:
    flags = _build_rule_filter_flags(symbols, spot_df, money_flow_data)
    if flags.empty:
        return [], flags

    mask = flags["amount_ok"]
    if cfg.SCREEN_MODE == "loose":
        mask = pd.Series(True, index=flags.index)
    if cfg.SCREEN_MODE in ("strict", "normal") and cfg.REQUIRE_POSITIVE_MONEY_FLOW:
        mask &= flags["fund_ok"]
    if cfg.SCREEN_MODE == "strict" and cfg.REQUIRE_SECTOR_HOT:
        mask &= flags["sector_hot"]
    if cfg.SCREEN_MODE == "strict" and cfg.REQUIRE_LEADING_IN_SECTOR:
        mask &= flags["leading_stock"]

    passed = flags.loc[mask, "code"].astype(str).tolist()
    if verbose:
        print(
            "[筛选] 规则硬过滤: "
            f"成交额 {int(flags['amount_ok'].sum())}/{len(flags)} | "
            f"资金 {int(flags['fund_ok'].sum())}/{len(flags)} | "
            f"板块热度 {int(flags['sector_hot'].sum())}/{len(flags)} | "
            f"板块内领涨 {int(flags['leading_stock'].sum())}/{len(flags)} | "
            f"最终 {len(passed)}/{len(flags)}"
        )
    return passed, flags


def run_screening(
    verbose: bool = True,
    max_stocks: Optional[int] = None,
) -> pd.DataFrame:
    """
    执行完整选股流程，返回 Top N 股票 DataFrame
    """
    start_time = time.time()

    # ================================================
    # Step 1: 获取股票列表（新浪源）
    # ================================================
    spot_df = get_stock_list()
    filter_log = list(data_fetcher.LAST_STOCK_FILTER_LOG)
    if spot_df.empty:
        print("[错误] 无法获取股票列表")
        return pd.DataFrame()

    symbols_all = spot_df["code"].astype(str).tolist()

    # 测试模式：限制数量
    if max_stocks and max_stocks < len(symbols_all):
        before = len(symbols_all)
        symbols_all = symbols_all[:max_stocks]
        filter_log.append(_filter_log_row("测试模式截断", before, len(symbols_all)))
        if verbose:
            print(f"[测试] 限制为 {max_stocks} 只")

    # ================================================
    # Step 2: 批量获取K线（东方财富源）
    # ================================================
    history_data = get_stock_histories_batch(symbols_all, spot_df=spot_df)

    if not history_data:
        print("[错误] 未获取到任何K线数据")
        return pd.DataFrame()

    if verbose:
        print(f"[进度] K线获取完毕: {len(history_data)} 只")

    # ================================================
    # Step 3: 计算指标 + 硬条件过滤
    # ================================================
    if verbose:
        print("[进度] 计算技术指标并筛选...")

    passed_symbols = []
    indicators_results = {}
    tech_diag_rows = []
    total = len(history_data)
    spot_indexed = spot_df.set_index("code") if "code" in spot_df.columns else spot_df

    for i, (sym, df) in enumerate(history_data.items()):
        df_with_ind = calculate_all_indicators(df)
        result = check_all_conditions(df_with_ind)
        indicators_results[sym] = result
        checks = evaluate_technical_conditions(df_with_ind, cfg.SCREEN_MODE)
        latest = df_with_ind.iloc[-1]
        tech_diag_rows.append({
            "code": sym,
            "name": spot_indexed.loc[sym, "name"] if sym in spot_indexed.index and "name" in spot_indexed.columns else sym,
            "close": latest.get("close", np.nan),
            "ma3": latest.get("MA3", np.nan),
            "ma5": latest.get("MA5", np.nan),
            "ma20": latest.get("MA20", np.nan),
            "ma21": latest.get("MA21", np.nan),
            "above_ma20_days_20": latest.get("ABOVE_MA20_DAYS_20", np.nan),
            "ma20_slope_10_pct": latest.get("MA20_SLOPE_10_PCT", np.nan),
            "ma20_slope_20_pct": latest.get("MA20_SLOPE_20_PCT", np.nan),
            "close_ma20_ratio": latest.get("CLOSE_MA20_RATIO", np.nan),
            "pdi": latest.get("plus_di", np.nan),
            "mdi": latest.get("minus_di", np.nan),
            "adx": latest.get("ADX", np.nan),
            "vol_ratio": latest.get("VOL_RATIO", np.nan),
            "expma7": latest.get("EXPMA7", np.nan),
            "expma21": latest.get("EXPMA21", np.nan),
            "dif": latest.get("MACD_DIFF", np.nan),
            "dea": latest.get("MACD_DEA", np.nan),
            "macd_hist": latest.get("MACD_HIST", np.nan),
            **checks,
        })
        if result["passed"]:
            passed_symbols.append(sym)

        if verbose and (i + 1) % 500 == 0:
            print(f"  已处理 {i+1}/{total}, 通过: {len(passed_symbols)}")

    filter_log.extend([
        _filter_log_row("MA 条件", total, sum(1 for r in indicators_results.values() if r.get("ma_bullish"))),
        _filter_log_row("MA20 趋势持续性", total, sum(1 for r in indicators_results.values() if r.get("trend_quality_pass"))),
        _filter_log_row("DMI 条件", total, sum(1 for r in indicators_results.values() if r.get("adx_pass"))),
        _filter_log_row("成交量条件", total, sum(1 for r in indicators_results.values() if r.get("volume_pass"))),
        _filter_log_row("EXPMA 条件", total, sum(1 for r in indicators_results.values() if r.get("expma_pass"))),
        _filter_log_row("MACD 二次金叉条件", total, sum(1 for r in indicators_results.values() if r.get("macd_pass"))),
        _filter_log_row("技术条件合计", total, len(passed_symbols)),
    ])
    _save_tech_diagnostics(tech_diag_rows, verbose=verbose)
    _save_technical_candidates(
        tech_diag_rows,
        cfg.SCREEN_MODE,
        prefix="technical_candidates",
        verbose=verbose,
    )

    if verbose:
        pct = len(passed_symbols) / total * 100 if total > 0 else 0
        print(f"[筛选] 技术面通过: {len(passed_symbols)} / {total} ({pct:.1f}%)")

    if not passed_symbols:
        _save_hot_sector_report(spot_df, selected_df=None, verbose=verbose)
        log_path = _save_filter_log(filter_log)
        if verbose:
            print(f"[日志] 过滤过程已保存: {log_path}")
        print("[结果] 无股票通过技术面筛选")
        return pd.DataFrame()

    # ================================================
    # Step 4: 资金流向（东方财富源）
    # ================================================
    if verbose:
        print(f"[进度] 获取 {len(passed_symbols)} 只候选股资金流向...")

    money_flow_data = get_money_flow_batch(passed_symbols)

    # API不可用时用K线量价估算
    if len(money_flow_data) < len(passed_symbols):
        missing = [s for s in passed_symbols if s not in money_flow_data]
        # 只对缺失的股票估算
        missing_kline = {s: history_data[s] for s in missing if s in history_data}
        estimated = estimate_money_flow_from_kline(missing_kline)
        money_flow_data.update(estimated)

    if verbose:
        print(f"[数据] 资金流向: {len(money_flow_data)} 只有效 (API+估算)")

    passed_symbols, rule_flags = _apply_rule_hard_filters(
        passed_symbols,
        spot_df,
        money_flow_data,
        verbose=verbose,
    )
    if not rule_flags.empty:
        before_rules = len(rule_flags)
        filter_log.extend([
            _filter_log_row("成交额过滤", before_rules, int(rule_flags["amount_ok"].sum())),
            _filter_log_row("资金净流入条件", before_rules, int(rule_flags["fund_ok"].sum())),
            _filter_log_row("板块热度条件", before_rules, int(rule_flags["sector_hot"].sum())),
            _filter_log_row("板块内领涨条件", before_rules, int(rule_flags["leading_stock"].sum())),
            _filter_log_row("最终股票池", before_rules, len(passed_symbols)),
        ])
    log_path = _save_filter_log(filter_log)
    if verbose:
        print(f"[日志] 过滤过程已保存: {log_path}")
    if not passed_symbols:
        _save_hot_sector_report(spot_df, selected_df=None, verbose=verbose)
        print("[结果] 无股票通过资金/成交额/板块硬过滤")
        return pd.DataFrame()

    # ================================================
    # Step 5: 板块评分（基于相对强度）
    # ================================================
    sector_score_map = build_sector_score_map(spot_df)
    if verbose:
        if sector_score_map:
            print(f"[数据] 板块评分：基于行业相对强度")
        else:
            print(f"[数据] 板块评分：无行业字段，使用个股相对强度估算")

    # ================================================
    # Step 6: 综合评分排名
    # ================================================
    if verbose:
        print("[进度] 计算综合评分...")

    result_df = compute_total_scores(
        symbols=passed_symbols,
        indicators_results=indicators_results,
        money_flow_data=money_flow_data,
        spot_df=spot_df,
        sector_score_map=sector_score_map,
        rule_flags=rule_flags,
    )
    _save_hot_sector_report(spot_df, selected_df=result_df, verbose=verbose)

    # ================================================
    # Step 7: 返回 Top N
    # ================================================
    top_n = result_df.head(cfg.TOP_N) if not result_df.empty else result_df

    elapsed = time.time() - start_time
    if verbose:
        print(f"\n[完成] 耗时 {elapsed:.0f}s | 入选 {len(result_df)} 只 | 展示 Top {cfg.TOP_N}")

    return top_n


def compare_modes(max_stocks: Optional[int] = None, verbose: bool = True) -> pd.DataFrame:
    """一次抓取数据，对 strict/normal/loose 三种模式做技术通过数量对比。"""
    old_mode = cfg.SCREEN_MODE
    spot_df = get_stock_list()
    symbols = spot_df["code"].astype(str).tolist()
    if max_stocks and max_stocks < len(symbols):
        symbols = symbols[:max_stocks]
    history_data = get_stock_histories_batch(symbols, spot_df=spot_df)
    spot_indexed = spot_df.set_index("code") if "code" in spot_df.columns else spot_df

    rows = []
    for mode in ["strict", "normal", "loose"]:
        cfg.SCREEN_MODE = mode
        count = 0
        candidate_rows = []
        for _, df in history_data.items():
            df_ind = calculate_all_indicators(df)
            checks = evaluate_technical_conditions(df_ind, mode)
            latest = df_ind.iloc[-1]
            code = str(df_ind.get("code", pd.Series([""])).iloc[-1]) if "code" in df_ind.columns else _
            name = spot_indexed.loc[code, "name"] if code in spot_indexed.index and "name" in spot_indexed.columns else code
            candidate_rows.append({
                "code": code,
                "name": name,
                "close": latest.get("close", np.nan),
                "ma3": latest.get("MA3", np.nan),
                "ma5": latest.get("MA5", np.nan),
                "ma20": latest.get("MA20", np.nan),
                "ma21": latest.get("MA21", np.nan),
                "above_ma20_days_20": latest.get("ABOVE_MA20_DAYS_20", np.nan),
                "ma20_slope_10_pct": latest.get("MA20_SLOPE_10_PCT", np.nan),
                "ma20_slope_20_pct": latest.get("MA20_SLOPE_20_PCT", np.nan),
                "close_ma20_ratio": latest.get("CLOSE_MA20_RATIO", np.nan),
                "pdi": latest.get("plus_di", np.nan),
                "mdi": latest.get("minus_di", np.nan),
                "adx": latest.get("ADX", np.nan),
                "vol_ratio": latest.get("VOL_RATIO", np.nan),
                "expma7": latest.get("EXPMA7", np.nan),
                "expma21": latest.get("EXPMA21", np.nan),
                "dif": latest.get("MACD_DIFF", np.nan),
                "dea": latest.get("MACD_DEA", np.nan),
                "macd_hist": latest.get("MACD_HIST", np.nan),
                **checks,
            })
            if checks["technical_pass"]:
                count += 1
        _save_technical_candidates(
            candidate_rows,
            mode,
            prefix="mode_candidates",
            verbose=verbose,
        )
        rows.append({
            "mode": mode,
            "passed_count": count,
            "total_count": len(history_data),
            "pass_rate": round(count / len(history_data), 4) if history_data else 0,
        })
        if verbose:
            print(f"{mode}: {count}只")
    cfg.SCREEN_MODE = old_mode

    today = datetime.date.today()
    path = output_path(f"mode_compare_{today.strftime('%Y%m%d')}.csv", today)
    result = pd.DataFrame(rows)
    result.to_csv(path, index=False, encoding="utf-8-sig")
    if verbose:
        print(f"[模式对比] 已保存: {path}")
    return result
