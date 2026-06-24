#!/usr/bin/env python3
"""
参数稳健性扫描。
默认扫描提示词指定的参数网格，并输出 output/YYYYMMDD/parameter_scan_results.csv。
"""

import argparse
import itertools
import os

import pandas as pd

import config as cfg
from backtest import run_backtest
from utils import output_day_dir


VOL_MULT_VALUES = [1.2, 1.3, 1.4, 1.5]
ADX_THRESHOLD_VALUES = [20, 25, 30]
EXPMA_CROSS_DAYS_VALUES = [3, 5]
MACD_CROSS_DAYS_VALUES = [3, 5]
SECTOR_TOP_PCT_VALUES = [0.1, 0.2, 0.3]
LEADING_TOP_PCT_VALUES = [0.1, 0.2, 0.3]


def _snapshot_config():
    return {
        "VOL_RATIO_MIN": cfg.VOL_RATIO_MIN,
        "ADX_THRESHOLD": cfg.ADX_THRESHOLD,
        "EXPMA_CROSS_DAYS": cfg.EXPMA_CROSS_DAYS,
        "MACD_CROSS_DAYS": cfg.MACD_CROSS_DAYS,
        "SECTOR_HOT_TOP_PCT": cfg.SECTOR_HOT_TOP_PCT,
        "LEADING_STOCK_TOP_PCT": cfg.LEADING_STOCK_TOP_PCT,
    }


def _restore_config(snapshot):
    for key, value in snapshot.items():
        setattr(cfg, key, value)


def _apply_params(params):
    cfg.VOL_RATIO_MIN = params["vol_mult"]
    cfg.ADX_THRESHOLD = params["adx_threshold"]
    cfg.EXPMA_CROSS_DAYS = params["expma_cross_days"]
    cfg.MACD_CROSS_DAYS = params["macd_cross_days"]
    cfg.SECTOR_HOT_TOP_PCT = params["sector_top_pct"]
    cfg.LEADING_STOCK_TOP_PCT = params["leading_top_pct"]


def scan_parameters(
    start_date=None,
    end_date=None,
    code_limit=None,
    hold_days=5,
    max_combinations=None,
) -> pd.DataFrame:
    rows = []
    snapshot = _snapshot_config()
    grid = itertools.product(
        VOL_MULT_VALUES,
        ADX_THRESHOLD_VALUES,
        EXPMA_CROSS_DAYS_VALUES,
        MACD_CROSS_DAYS_VALUES,
        SECTOR_TOP_PCT_VALUES,
        LEADING_TOP_PCT_VALUES,
    )

    try:
        for i, values in enumerate(grid, 1):
            if max_combinations and i > max_combinations:
                break
            params = {
                "vol_mult": values[0],
                "adx_threshold": values[1],
                "expma_cross_days": values[2],
                "macd_cross_days": values[3],
                "sector_top_pct": values[4],
                "leading_top_pct": values[5],
            }
            print(f"[参数扫描] {i}: {params}")
            _apply_params(params)
            try:
                report = run_backtest(
                    start_date=start_date,
                    end_date=end_date,
                    hold_days_list=[hold_days],
                    code_limit=code_limit,
                    save_outputs=False,
                )
                summary = report.get("summary", {}) if "error" not in report else {}
                row = {
                    **params,
                    "total_return": summary.get("total_return", 0),
                    "annual_return": summary.get("annual_return", 0),
                    "max_drawdown": summary.get("max_drawdown", 0),
                    "win_rate": summary.get("win_rate", 0),
                    "trade_count": summary.get("trade_count", 0),
                    "average_return_per_trade": summary.get("average_return_per_trade", 0),
                    "sharpe_ratio": summary.get("sharpe_ratio", 0),
                    "error": report.get("error", ""),
                }
            except Exception as exc:
                row = {
                    **params,
                    "total_return": 0,
                    "annual_return": 0,
                    "max_drawdown": 0,
                    "win_rate": 0,
                    "trade_count": 0,
                    "average_return_per_trade": 0,
                    "sharpe_ratio": 0,
                    "error": str(exc),
                }
            row["score"] = (
                row["annual_return"]
                - abs(row["max_drawdown"]) * 0.7
                + row["win_rate"] * 0.2
            )
            rows.append(row)
    finally:
        _restore_config(snapshot)

    result = pd.DataFrame(rows)
    output = os.path.join(output_day_dir(), "parameter_scan_results.csv")
    result.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"[参数扫描] 结果已保存: {output}")
    return result


def main():
    parser = argparse.ArgumentParser(description="参数稳健性扫描")
    parser.add_argument("--start", default=None, help="回测起始日期 YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="回测结束日期 YYYY-MM-DD")
    parser.add_argument("--test", type=int, default=None, help="限制股票数量")
    parser.add_argument("--hold", type=int, default=5, help="持有天数")
    parser.add_argument("--max-combinations", type=int, default=None, help="最多扫描组合数，调试用")
    args = parser.parse_args()

    scan_parameters(
        start_date=args.start,
        end_date=args.end,
        code_limit=args.test,
        hold_days=args.hold,
        max_combinations=args.max_combinations,
    )


if __name__ == "__main__":
    main()
