import pandas as pd

import config as cfg
from screener import (
    _apply_rule_hard_filters,
    _build_rule_filter_flags,
    _candidate_priority_score,
    _fallback_hot_sectors_from_spot,
)


def _spot_df():
    return pd.DataFrame(
        {
            "code": ["000001", "000002", "000003", "000004"],
            "name": ["A", "B", "C", "D"],
            "industry": ["芯片", "芯片", "医药", "医药"],
            "pct_change": [10.0, 5.0, 1.0, -2.0],
            "amount": [200_000_000, 150_000_000, 300_000_000, 50_000_000],
        }
    )


def test_build_rule_filter_flags_marks_amount_fund_sector_and_leaders(monkeypatch):
    monkeypatch.setattr(cfg, "MIN_AMOUNT", 100_000_000)
    monkeypatch.setattr(cfg, "SECTOR_HOT_TOP_PCT", 0.5)
    monkeypatch.setattr(cfg, "LEADING_STOCK_TOP_PCT", 0.5)
    money_flow = {
        "000001": {"total_inflow": 1},
        "000002": {"total_inflow": -1},
        "000003": {"total_inflow": 1},
        "000004": {"total_inflow": 1},
    }

    flags = _build_rule_filter_flags(["000001", "000002", "000003", "000004"], _spot_df(), money_flow)
    row1 = flags.set_index("code").loc["000001"]
    row4 = flags.set_index("code").loc["000004"]

    assert bool(row1["amount_ok"]) is True
    assert bool(row1["fund_ok"]) is True
    assert bool(row1["sector_hot"]) is True
    assert bool(row1["leading_stock"]) is True
    assert bool(row4["amount_ok"]) is False


def test_apply_rule_hard_filters_differs_by_screen_mode(monkeypatch):
    monkeypatch.setattr(cfg, "MIN_AMOUNT", 100_000_000)
    monkeypatch.setattr(cfg, "REQUIRE_POSITIVE_MONEY_FLOW", True)
    monkeypatch.setattr(cfg, "REQUIRE_SECTOR_HOT", True)
    monkeypatch.setattr(cfg, "REQUIRE_LEADING_IN_SECTOR", True)
    monkeypatch.setattr(cfg, "SECTOR_HOT_TOP_PCT", 0.5)
    monkeypatch.setattr(cfg, "LEADING_STOCK_TOP_PCT", 0.5)
    money_flow = {
        "000001": {"total_inflow": 1},
        "000002": {"total_inflow": -1},
        "000003": {"total_inflow": 1},
        "000004": {"total_inflow": 1},
    }

    monkeypatch.setattr(cfg, "SCREEN_MODE", "strict")
    strict_passed, _ = _apply_rule_hard_filters(["000001", "000002", "000003", "000004"], _spot_df(), money_flow, verbose=False)

    monkeypatch.setattr(cfg, "SCREEN_MODE", "loose")
    loose_passed, _ = _apply_rule_hard_filters(["000001", "000002", "000003", "000004"], _spot_df(), money_flow, verbose=False)

    assert strict_passed == ["000001"]
    assert set(loose_passed) == {"000001", "000002", "000003", "000004"}


def test_candidate_priority_score_rewards_multiple_confirmations():
    strong = {
        "ma_stack": True,
        "trend_quality_ok": True,
        "above_ma20_days_20": 20,
        "ma20_slope_10_pct": 6,
        "ma20_not_overheated": True,
        "pdi_gt_mdi": True,
        "adx_enough": True,
        "adx": 60,
        "volume_enough": True,
        "vol_ratio": 3,
        "expma_bull": True,
        "expma_recent_cross": True,
        "dif_dea_above_zero": True,
        "dif_gt_dea": True,
        "macd_second_gc_above_zero": True,
        "macd_second_gc_recent": True,
    }
    weak = {"adx": 10, "vol_ratio": 0.5}

    assert _candidate_priority_score(strong) > _candidate_priority_score(weak)


def test_fallback_hot_sectors_from_spot_quantifies_industry_heat():
    hot = _fallback_hot_sectors_from_spot(_spot_df())

    assert not hot.empty
    assert hot.iloc[0]["sector_name"] == "芯片"
    assert hot.iloc[0]["heat_score"] > hot.iloc[-1]["heat_score"]
    assert hot.iloc[0]["leader_name"] == "A"
    assert "热度" in hot.iloc[0]["quant_note"]
