"""
预测准确性评估

读取每日选股结果，回看未来 3/5/10/20 日表现，回答：
- 选出的股票未来收益和超额收益如何；
- Top20/Top10/Top5 的 precision 是否稳定；
- 评分与未来收益是否真的相关。
"""

import argparse
import datetime
import glob
import json
import os
import re
from typing import Optional

import numpy as np
import pandas as pd

import config as cfg
from data_fetcher import load_benchmark_data
from utils import history_output_path, output_day_dir


DEFAULT_HOLD_DAYS = [3, 5, 10, 20]
SCORE_COLUMNS = [
    "total_score",
    "raw_score",
    "tech_score",
    "trend_score",
    "trend_quality_score",
    "trend_persistence_score",
    "ma20_slope_score",
    "ma20_distance_score",
    "volume_score",
    "dmi_score",
    "macd_score",
    "expma_score",
    "money_flow_score",
    "flow_score",
    "sector_score",
    "leading_score",
    "adx",
    "vol_ratio",
    "above_ma20_days_20",
    "ma20_slope_10_pct",
    "ma20_slope_20_pct",
    "close_ma20_ratio",
    "main_net_ratio",
    "sector_rank_pct",
    "stock_rank_in_sector",
]


def _today_key() -> str:
    return datetime.date.today().strftime("%Y%m%d")


def _normalize_date(value) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def _parse_hold_days(value) -> list:
    if value is None:
        return DEFAULT_HOLD_DAYS
    if isinstance(value, (list, tuple)):
        return [int(v) for v in value]
    return [int(v.strip()) for v in str(value).split(",") if v.strip()]


def load_pick_history(path: str = None) -> pd.DataFrame:
    """读取 daily_picks_history.csv 或指定 stock_pick 文件。"""
    if path is None:
        path = history_output_path("daily_picks_history.csv")
        legacy = os.path.join(cfg.OUTPUT_DIR, "daily_picks_history.csv")
        if not os.path.exists(path) and os.path.exists(legacy):
            path = legacy
    if not os.path.exists(path):
        raise FileNotFoundError(f"未找到选股历史文件: {path}")

    df = pd.read_csv(path)
    if df.empty:
        return df

    if "trade_date" not in df.columns:
        m = re.search(r"stock_pick_(\d{8})", os.path.basename(path))
        if not m:
            raise ValueError("选股文件缺少 trade_date，且文件名不是 stock_pick_YYYYMMDD.csv")
        trade_date = datetime.datetime.strptime(m.group(1), "%Y%m%d").strftime("%Y-%m-%d")
        df.insert(0, "trade_date", trade_date)

    df["trade_date"] = df["trade_date"].map(_normalize_date)
    df["code"] = df["code"].astype(str).str.zfill(6)
    if "rank" not in df.columns:
        df["rank"] = df.groupby("trade_date").cumcount() + 1
    else:
        df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
        df["rank"] = df["rank"].fillna(df.groupby("trade_date").cumcount() + 1)
    return df.sort_values(["trade_date", "rank"]).reset_index(drop=True)


def _parse_backtest_cache_range(path: str):
    m = re.search(r"kline_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.parquet$", os.path.basename(path))
    if not m:
        return None
    return m.group(1), m.group(2)


def _required_date_window(picks: pd.DataFrame, max_hold_days: int) -> tuple:
    start = pd.to_datetime(picks["trade_date"].min()) - pd.Timedelta(days=120)
    end = pd.to_datetime(picks["trade_date"].max()) + pd.Timedelta(days=max_hold_days * 3 + 15)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def find_best_kline_cache(start_date: str, end_date: str) -> Optional[str]:
    """优先选择覆盖评估窗口的回测 parquet 缓存。"""
    candidates = []
    for path in glob.glob(os.path.join("cache", "kline_*.parquet")):
        parsed = _parse_backtest_cache_range(path)
        if not parsed:
            continue
        cache_start, cache_end = parsed
        try:
            date_col = pd.read_parquet(path, columns=["date"])["date"].astype(str)
            if not date_col.empty:
                cache_start = str(date_col.min())
                cache_end = str(date_col.max())
        except Exception:
            pass
        covers = cache_start <= start_date and cache_end >= end_date
        overlaps = cache_start <= end_date and cache_end >= start_date
        if covers or overlaps:
            span = (pd.to_datetime(cache_end) - pd.to_datetime(cache_start)).days
            candidates.append((covers, cache_end, -span, path))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][3]


def load_kline_data(
    picks: pd.DataFrame,
    hold_days_list: list,
    cache_path: str = None,
    fetch_missing: bool = False,
) -> pd.DataFrame:
    start_date, end_date = _required_date_window(picks, max(hold_days_list))
    if cache_path is None:
        cache_path = find_best_kline_cache(start_date, end_date)

    if fetch_missing:
        fetch_end = min(pd.to_datetime(end_date), pd.Timestamp.today()).strftime("%Y-%m-%d")
        try:
            from backtest import fetch_all_kline_cache
            codes = sorted(picks["code"].astype(str).str.zfill(6).unique().tolist())
            cache_path = fetch_all_kline_cache(
                codes,
                start_date,
                fetch_end,
                max_workers=getattr(cfg, "MAX_WORKERS", 2),
            )
        except Exception as e:
            print(f"[评估] 自动补取K线失败，继续使用本地缓存: {e}")

    if not cache_path or not os.path.exists(cache_path):
        print("[评估] 未找到覆盖评估区间的K线缓存，部分股票将无法评估")
        return pd.DataFrame(columns=["code", "date", "open", "high", "low", "close", "volume"])

    print(f"[评估] 使用K线缓存: {cache_path}")
    try:
        df = pd.read_parquet(cache_path)
    except Exception as e:
        print(f"[评估] K线缓存读取失败: {e}")
        return pd.DataFrame(columns=["code", "date", "open", "high", "low", "close", "volume"])

    df["code"] = df["code"].astype(str).str.zfill(6)
    df["date"] = df["date"].map(_normalize_date)
    codes = set(picks["code"].astype(str))
    df = df[df["code"].isin(codes)].copy()
    return df.sort_values(["code", "date"]).reset_index(drop=True)


def _benchmark_return(benchmark_df: pd.DataFrame, buy_date: str, sell_date: str) -> float:
    if benchmark_df is None or benchmark_df.empty:
        return np.nan
    bench = benchmark_df.copy()
    bench["trade_date"] = bench["trade_date"].map(_normalize_date)
    bench = bench.sort_values("trade_date")
    start_rows = bench[bench["trade_date"] >= buy_date]
    end_rows = bench[bench["trade_date"] <= sell_date]
    if start_rows.empty or end_rows.empty:
        return np.nan
    start_close = float(start_rows.iloc[0]["close"])
    end_close = float(end_rows.iloc[-1]["close"])
    if start_close <= 0:
        return np.nan
    return (end_close - start_close) / start_close * 100


def _evaluate_one_pick(stock_df: pd.DataFrame, signal_date: str, hold_days: int) -> tuple:
    stock_df = stock_df.sort_values("date").reset_index(drop=True)
    signal_rows = stock_df.index[stock_df["date"] == signal_date].tolist()
    if not signal_rows:
        after_signal = stock_df[stock_df["date"] > signal_date]
        if after_signal.empty:
            return None, "signal_date_not_in_cache"
        buy_pos = int(after_signal.index[0])
        signal_date_in_kline = False
    else:
        signal_pos = int(signal_rows[0])
        buy_pos = signal_pos + 1
        signal_date_in_kline = True

    sell_pos = buy_pos + hold_days
    if buy_pos >= len(stock_df) or sell_pos >= len(stock_df):
        return None, "not_mature_yet"

    buy = stock_df.iloc[buy_pos]
    sell = stock_df.iloc[sell_pos]
    buy_price = float(buy["open"])
    sell_price = float(sell["close"])
    if buy_price <= 0:
        return None

    holding = stock_df.iloc[buy_pos:sell_pos + 1]
    min_low = float(holding["low"].min()) if "low" in holding.columns else min(buy_price, sell_price)
    max_drawdown = (min_low - buy_price) / buy_price * 100
    return_pct = (sell_price - buy_price) / buy_price * 100
    return {
        "buy_date": buy["date"],
        "buy_price": buy_price,
        "sell_date": sell["date"],
        "sell_price": sell_price,
        "return_pct": return_pct,
        "max_drawdown_pct": max_drawdown,
        "signal_date_in_kline": signal_date_in_kline,
    }, "ok"


def build_evaluation_details(
    picks: pd.DataFrame,
    kline_df: pd.DataFrame,
    hold_days_list: list,
    benchmark_df: pd.DataFrame = None,
) -> pd.DataFrame:
    rows = []
    grouped_kline = {code: g.copy() for code, g in kline_df.groupby("code")} if not kline_df.empty else {}

    for _, pick in picks.iterrows():
        code = str(pick["code"]).zfill(6)
        stock_df = grouped_kline.get(code)
        for hold_days in hold_days_list:
            base = pick.to_dict()
            base["code"] = code
            base["hold_days"] = int(hold_days)
            if stock_df is None or stock_df.empty:
                base.update({"data_status": "no_kline"})
                rows.append(base)
                continue

            trade, status = _evaluate_one_pick(stock_df, pick["trade_date"], hold_days)
            if trade is None:
                base.update({"data_status": status})
                rows.append(base)
                continue

            bench_ret = _benchmark_return(benchmark_df, trade["buy_date"], trade["sell_date"])
            excess = trade["return_pct"] - bench_ret if pd.notna(bench_ret) else np.nan
            base.update(trade)
            base.update({
                "benchmark_return_pct": bench_ret,
                "excess_return_pct": excess,
                "is_win": trade["return_pct"] > 0,
                "is_outperform": excess > 0 if pd.notna(excess) else np.nan,
                "data_status": "ok",
            })
            rows.append(base)

    return pd.DataFrame(rows)


def _profit_loss_ratio(series: pd.Series) -> float:
    wins = series[series > 0]
    losses = series[series < 0]
    if wins.empty or losses.empty:
        return np.nan
    return float(wins.mean() / abs(losses.mean()))


def _safe_corr(x: pd.Series, y: pd.Series) -> float:
    x = pd.to_numeric(x, errors="coerce")
    y = pd.to_numeric(y, errors="coerce")
    valid = x.notna() & y.notna()
    if valid.sum() < 3 or x[valid].nunique() <= 1 or y[valid].nunique() <= 1:
        return np.nan
    return float(x[valid].corr(y[valid]))


def _safe_rank_corr(x: pd.Series, y: pd.Series) -> float:
    x = pd.to_numeric(x, errors="coerce")
    y = pd.to_numeric(y, errors="coerce")
    valid = x.notna() & y.notna()
    if valid.sum() < 3 or x[valid].nunique() <= 1 or y[valid].nunique() <= 1:
        return np.nan
    return float(x[valid].rank().corr(y[valid].rank()))


def _calc_summary(details: pd.DataFrame) -> pd.DataFrame:
    rows = []
    ok = details[details["data_status"] == "ok"].copy()
    if ok.empty:
        return pd.DataFrame()

    for hold_days, g in ok.groupby("hold_days"):
        top20 = g[g["rank"] <= 20]
        top10 = g[g["rank"] <= 10]
        top5 = g[g["rank"] <= 5]
        rows.append({
            "hold_days": int(hold_days),
            "sample_count": int(len(g)),
            "trade_date_count": int(g["trade_date"].nunique()),
            "win_rate": float(g["is_win"].mean()),
            "precision_at_5": float(top5["is_outperform"].mean()) if not top5.empty else np.nan,
            "precision_at_10": float(top10["is_outperform"].mean()) if not top10.empty else np.nan,
            "precision_at_20": float(top20["is_outperform"].mean()) if not top20.empty else np.nan,
            "average_return_pct": float(g["return_pct"].mean()),
            "median_return_pct": float(g["return_pct"].median()),
            "average_excess_return_pct": float(g["excess_return_pct"].mean()) if "excess_return_pct" in g else np.nan,
            "median_excess_return_pct": float(g["excess_return_pct"].median()) if "excess_return_pct" in g else np.nan,
            "average_max_drawdown_pct": float(g["max_drawdown_pct"].mean()),
            "worst_return_pct": float(g["return_pct"].min()),
            "best_return_pct": float(g["return_pct"].max()),
            "profit_loss_ratio": _profit_loss_ratio(g["return_pct"]),
            "score_ic": _safe_corr(g["total_score"], g["return_pct"]) if "total_score" in g else np.nan,
            "rank_ic": _safe_rank_corr(g["rank"], g["return_pct"]) if "rank" in g else np.nan,
        })
    return pd.DataFrame(rows)


def _calc_bucket_summary(details: pd.DataFrame) -> pd.DataFrame:
    ok = details[details["data_status"] == "ok"].copy()
    if ok.empty:
        return pd.DataFrame()
    ok["rank_bucket"] = pd.cut(
        ok["rank"],
        bins=[0, 5, 10, 20, np.inf],
        labels=["top1_5", "top6_10", "top11_20", "after20"],
        right=True,
    )
    rows = []
    for (hold_days, bucket), g in ok.groupby(["hold_days", "rank_bucket"], observed=True):
        rows.append({
            "hold_days": int(hold_days),
            "rank_bucket": str(bucket),
            "sample_count": int(len(g)),
            "win_rate": float(g["is_win"].mean()),
            "precision": float(g["is_outperform"].mean()) if "is_outperform" in g else np.nan,
            "average_return_pct": float(g["return_pct"].mean()),
            "average_excess_return_pct": float(g["excess_return_pct"].mean()) if "excess_return_pct" in g else np.nan,
        })
    return pd.DataFrame(rows)


def _calc_feature_ic(details: pd.DataFrame) -> pd.DataFrame:
    ok = details[details["data_status"] == "ok"].copy()
    if ok.empty:
        return pd.DataFrame()

    rows = []
    for hold_days, g in ok.groupby("hold_days"):
        for col in SCORE_COLUMNS:
            if col not in g.columns:
                continue
            x = pd.to_numeric(g[col], errors="coerce")
            if x.notna().sum() < 3 or x.nunique(dropna=True) <= 1:
                continue
            rows.append({
                "hold_days": int(hold_days),
                "feature": col,
                "return_ic": _safe_corr(x, g["return_pct"]),
                "return_rank_ic": _safe_rank_corr(x, g["return_pct"]),
                "excess_ic": _safe_corr(x, g["excess_return_pct"]) if g["excess_return_pct"].notna().sum() >= 3 else np.nan,
                "excess_rank_ic": _safe_rank_corr(x, g["excess_return_pct"]) if g["excess_return_pct"].notna().sum() >= 3 else np.nan,
                "sample_count": int(x.notna().sum()),
            })
    return pd.DataFrame(rows)


def _to_jsonable(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value):
            return None
        return float(value)
    if pd.isna(value):
        return None
    return value


def run_prediction_evaluation(
    picks_path: str = None,
    hold_days: str = None,
    kline_cache: str = None,
    fetch_missing: bool = False,
) -> dict:
    hold_days_list = _parse_hold_days(hold_days)
    picks = load_pick_history(picks_path)
    if picks.empty:
        raise RuntimeError("选股历史为空，无法评估")

    kline_df = load_kline_data(
        picks,
        hold_days_list,
        cache_path=kline_cache,
        fetch_missing=fetch_missing,
    )
    benchmark_df = load_benchmark_data()
    if benchmark_df.empty:
        print("[评估] 未找到本地基准数据，超额收益/precision 将为空")

    details = build_evaluation_details(picks, kline_df, hold_days_list, benchmark_df)
    summary = _calc_summary(details)
    buckets = _calc_bucket_summary(details)
    feature_ic = _calc_feature_ic(details)

    key = _today_key()
    out_dir = output_day_dir(key)
    detail_path = os.path.join(out_dir, f"prediction_accuracy_details_{key}.csv")
    summary_path = os.path.join(out_dir, f"prediction_accuracy_summary_{key}.csv")
    bucket_path = os.path.join(out_dir, f"prediction_accuracy_rank_buckets_{key}.csv")
    ic_path = os.path.join(out_dir, f"prediction_feature_ic_{key}.csv")
    json_path = os.path.join(out_dir, f"prediction_accuracy_report_{key}.json")

    details.to_csv(detail_path, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    buckets.to_csv(bucket_path, index=False, encoding="utf-8-sig")
    feature_ic.to_csv(ic_path, index=False, encoding="utf-8-sig")

    payload = {
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "picks_path": picks_path or history_output_path("daily_picks_history.csv"),
        "hold_days": hold_days_list,
        "pick_count": int(len(picks)),
        "evaluated_count": int((details["data_status"] == "ok").sum()) if not details.empty else 0,
        "missing_count": int((details["data_status"] != "ok").sum()) if not details.empty else 0,
        "summary": [
            {k: _to_jsonable(v) for k, v in row.items()}
            for row in summary.to_dict(orient="records")
        ],
        "output_files": {
            "details": detail_path,
            "summary": summary_path,
            "rank_buckets": bucket_path,
            "feature_ic": ic_path,
            "json": json_path,
        },
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("[评估] 输出文件:")
    for label, path in payload["output_files"].items():
        print(f"  {label}: {path}")
    if not summary.empty:
        print("[评估] 汇总:")
        for _, row in summary.iterrows():
            print(
                f"  持有{int(row['hold_days'])}日 | 样本{int(row['sample_count'])} | "
                f"胜率{row['win_rate']:.1%} | 平均收益{row['average_return_pct']:.2f}% | "
                f"平均超额{row['average_excess_return_pct']:.2f}%"
            )
    else:
        print("[评估] 暂无可评估样本，通常是缺少未来K线数据")

    return payload


def main():
    parser = argparse.ArgumentParser(description="评估每日选股结果的未来表现")
    parser.add_argument("--picks", default=None, help="选股CSV，默认 output/_history/daily_picks_history.csv")
    parser.add_argument("--hold", default="3,5,10,20", help="持有天数，逗号分隔")
    parser.add_argument("--kline-cache", default=None, help="指定K线 parquet 缓存")
    parser.add_argument("--fetch-missing", action="store_true", help="自动补取评估所需K线")
    args = parser.parse_args()
    run_prediction_evaluation(
        picks_path=args.picks,
        hold_days=args.hold,
        kline_cache=args.kline_cache,
        fetch_missing=args.fetch_missing,
    )


if __name__ == "__main__":
    main()
