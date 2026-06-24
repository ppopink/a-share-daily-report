"""
回测与特征校验工具。
用于防止未来函数、信号/成交时间错位，以及滚动窗口误用。
"""

import pandas as pd


FUTURE_COLUMN_KEYWORDS = (
    "future_ret",
    "future_return",
    "label",
    "next_open",
    "next_close",
    "next_high",
    "next_low",
    "tomorrow",
    "t_plus",
)


def check_no_future_columns(df: pd.DataFrame) -> dict:
    """检查选股阶段数据中是否混入未来字段。"""
    columns = [str(c) for c in df.columns]
    bad = [
        c for c in columns
        if any(keyword in c.lower() for keyword in FUTURE_COLUMN_KEYWORDS)
    ]
    return {
        "passed": len(bad) == 0,
        "future_columns": bad,
        "message": "ok" if not bad else f"发现疑似未来字段: {bad}",
    }


def check_signal_trade_timing(backtest_result) -> dict:
    """
    确认 T 日信号不能用 T 日开盘买入。
    要求交易明细中包含 signal_date/date 与 buy_date。
    """
    if isinstance(backtest_result, dict):
        trades = backtest_result.get("trades_df", pd.DataFrame())
    else:
        trades = backtest_result
    if trades is None or trades.empty:
        return {"passed": True, "violations": [], "message": "无交易可检查"}

    trades = trades.copy()
    if "signal_date" not in trades.columns and "date" in trades.columns:
        trades["signal_date"] = trades["date"]
    required = {"signal_date", "buy_date"}
    missing = sorted(required - set(trades.columns))
    if missing:
        return {
            "passed": False,
            "violations": [],
            "message": f"缺少字段: {missing}",
        }

    violations = []
    for idx, row in trades.iterrows():
        signal_date = pd.Timestamp(row["signal_date"])
        buy_date = pd.Timestamp(row["buy_date"])
        if buy_date <= signal_date:
            violations.append({
                "row": int(idx),
                "code": row.get("code", row.get("ts_code", "")),
                "signal_date": str(row["signal_date"]),
                "buy_date": str(row["buy_date"]),
            })

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "message": "ok" if not violations else "存在信号日当天或更早买入",
    }


def check_rolling_shift_usage(df: pd.DataFrame) -> dict:
    """
    检查 VOL_MA5 是否等于前5日均量。
    需要包含 volume 和 VOL_MA5 字段。
    """
    if "volume" not in df.columns or "VOL_MA5" not in df.columns:
        return {
            "passed": False,
            "message": "缺少 volume 或 VOL_MA5 字段",
            "bad_rows": [],
        }

    expected = df["volume"].shift(1).rolling(5).mean()
    actual = df["VOL_MA5"]
    comparable = expected.notna() & actual.notna()
    diff = (expected[comparable] - actual[comparable]).abs()
    bad_index = diff[diff > 1e-9].index.tolist()
    return {
        "passed": len(bad_index) == 0,
        "bad_rows": [int(i) for i in bad_index],
        "message": "ok" if not bad_index else "VOL_MA5 未使用 shift(1) 前5日均量",
    }
