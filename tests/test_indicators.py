import pandas as pd

import config as cfg
from indicators import (
    analyze_exit_plan,
    calc_ma,
    calculate_all_indicators,
    calc_trend_quality,
    calc_volume_ma,
    check_adx_condition,
    check_expma_golden_cross,
    check_ma_bullish,
    check_macd_second_golden_cross,
    check_trend_quality,
)


def test_ma_condition_requires_close_above_ma_stack():
    close = [10.0] * 21 + [11.0, 12.0, 13.0, 14.0]
    df = calc_ma(pd.DataFrame({"close": close}))
    ok, _ = check_ma_bullish(df)
    assert ok is True

    broken = df.copy()
    broken.loc[broken.index[-1], "close"] = broken.loc[broken.index[-1], "MA3"] - 0.01
    ok, _ = check_ma_bullish(broken)
    assert ok is False

    broken = df.copy()
    broken.loc[broken.index[-1], "MA5"] = broken.loc[broken.index[-1], "MA3"] + 0.01
    ok, _ = check_ma_bullish(broken)
    assert ok is False


def test_volume_ratio_uses_previous_five_days_only():
    df = pd.DataFrame({"volume": [100, 100, 100, 100, 100, 200]})
    out = calc_volume_ma(df)
    assert out.loc[5, "VOL_MA5"] == 100
    assert out.loc[5, "VOL_RATIO"] == 2

    wrong_ma_including_today = df["volume"].rolling(5).mean().iloc[5]
    assert wrong_ma_including_today == 120
    assert out.loc[5, "VOL_MA5"] != wrong_ma_including_today


def _expma_df(cross_index, n=30):
    expma21 = [10.0] * n
    expma7 = [9.0] * n
    for i in range(cross_index, n):
        expma7[i] = 11.0
    return pd.DataFrame({"EXPMA7": expma7, "EXPMA21": expma21})


def test_expma_cross_recent(monkeypatch):
    monkeypatch.setattr(cfg, "EXPMA_CROSS_DAYS", 3)
    ok, _ = check_expma_golden_cross(_expma_df(27, n=30))
    assert ok is True

    ok, _ = check_expma_golden_cross(_expma_df(25, n=30))
    assert ok is False

    ok, _ = check_expma_golden_cross(_expma_df(24, n=30))
    assert ok is False


def _macd_df(second_cross_index=27, n=30):
    diff = [-0.20] * n
    dea = [-0.10] * n

    # 0轴下方金叉，不应计入。
    diff[4], dea[4] = -0.20, -0.18
    diff[5], dea[5] = -0.10, -0.18

    # 最近一次进入0轴上方区域。
    for i in range(10, n):
        diff[i], dea[i] = 0.08, 0.10

    # 第一次0轴上方金叉。
    diff[11], dea[11] = 0.08, 0.10
    diff[12], dea[12] = 0.13, 0.10

    # 中间回调，确保不是延续。
    for i in range(13, second_cross_index):
        diff[i], dea[i] = 0.07, 0.10

    # 第二次金叉。
    diff[second_cross_index - 1], dea[second_cross_index - 1] = 0.08, 0.10
    diff[second_cross_index], dea[second_cross_index] = 0.14, 0.10
    for i in range(second_cross_index + 1, n):
        diff[i], dea[i] = 0.16, 0.10

    hist = [2 * (d - e) for d, e in zip(diff, dea)]
    return pd.DataFrame({
        "MACD_DIFF": diff,
        "MACD_DEA": dea,
        "MACD_HIST": hist,
    })


def test_macd_second_cross_only_counts_current_above_zero_zone(monkeypatch):
    monkeypatch.setattr(cfg, "MACD_CROSS_DAYS", 3)
    ok, _ = check_macd_second_golden_cross(_macd_df(second_cross_index=27))
    assert ok is True

    # 第二次金叉太早，不满足近3日触发。
    ok, _ = check_macd_second_golden_cross(_macd_df(second_cross_index=25))
    assert ok is False

    # 只有0轴下方金叉和0轴上方第一次金叉，不应通过。
    one_cross = _macd_df(second_cross_index=27)
    one_cross.loc[13:, "MACD_DIFF"] = 0.16
    one_cross.loc[13:, "MACD_DEA"] = 0.10
    ok, _ = check_macd_second_golden_cross(one_cross)
    assert ok is False


def test_dmi_requires_pdi_gt_mdi_and_adx_threshold(monkeypatch):
    monkeypatch.setattr(cfg, "ADX_THRESHOLD", 25)
    df = pd.DataFrame({"ADX": [26.0], "plus_di": [30.0], "minus_di": [10.0]})
    ok, _ = check_adx_condition(df)
    assert ok is True

    df = pd.DataFrame({"ADX": [25.0], "plus_di": [30.0], "minus_di": [10.0]})
    ok, _ = check_adx_condition(df)
    assert ok is False


def test_trend_quality_requires_persistence_slope_and_not_overheated(monkeypatch):
    monkeypatch.setattr(cfg, "TREND_STRICT_ABOVE_DAYS", 16)
    monkeypatch.setattr(cfg, "TREND_STRICT_SLOPE10_PCT", 3.0)
    monkeypatch.setattr(cfg, "TREND_STRICT_SLOPE20_PCT", 5.0)
    monkeypatch.setattr(cfg, "TREND_STRICT_MAX_CLOSE_MA20_RATIO", 1.15)

    close = [10.0] * 25 + [10.2 + i * 0.12 for i in range(25)]
    df = calc_trend_quality(calc_ma(pd.DataFrame({"close": close})))
    ok, score = check_trend_quality(df, mode="strict")
    assert ok is True
    assert score > 0.7
    assert int(df.iloc[-1]["ABOVE_MA20_DAYS_20"]) >= 16
    assert df.iloc[-1]["MA20_SLOPE_10_PCT"] >= 3 or df.iloc[-1]["MA20_SLOPE_20_PCT"] >= 5

    overheated = df.copy()
    overheated.loc[overheated.index[-1], "CLOSE_MA20_RATIO"] = 1.16
    ok, _ = check_trend_quality(overheated, mode="strict")
    assert ok is False

    weak_persistence = df.copy()
    weak_persistence.loc[weak_persistence.index[-1], "ABOVE_MA20_DAYS_20"] = 15
    ok, _ = check_trend_quality(weak_persistence, mode="strict")
    assert ok is False

    weak_slope = df.copy()
    weak_slope.loc[weak_slope.index[-1], "MA20_SLOPE_10_PCT"] = 2.9
    weak_slope.loc[weak_slope.index[-1], "MA20_SLOPE_20_PCT"] = 4.9
    ok, _ = check_trend_quality(weak_slope, mode="strict")
    assert ok is False

    df = pd.DataFrame({"ADX": [24.99], "plus_di": [30.0], "minus_di": [10.0]})
    ok, _ = check_adx_condition(df)
    assert ok is False


def test_exit_plan_outputs_holding_stop_profit_and_note():
    close = [10 + i * 0.2 for i in range(40)]
    high = [c * 1.02 for c in close]
    low = [c * 0.98 for c in close]
    open_ = [c * 0.99 for c in close]
    volume = [1000 + i * 10 for i in range(40)]
    df = calculate_all_indicators(pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }))

    plan = analyze_exit_plan(df)

    assert plan["planned_holding_days"] in {3, 5, 10}
    assert 0 < plan["stop_loss_price"] < close[-1]
    assert plan["take_profit_1_price"] > close[-1]
    assert plan["take_profit_2_price"] > plan["take_profit_1_price"]
    assert plan["trailing_stop_price"] >= plan["stop_loss_price"]
    assert "止损" in plan["exit_signal"]

    df = pd.DataFrame({"ADX": [30.0], "plus_di": [10.0], "minus_di": [10.0]})
    ok, _ = check_adx_condition(df)
    assert ok is False
