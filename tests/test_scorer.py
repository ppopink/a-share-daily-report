import pandas as pd

import config as cfg
from scorer import compute_total_scores, score_capital_flow, score_sector_leadership


def test_score_capital_flow_normalizes_by_inflow_amount_ratio():
    symbols = ["000001", "000002", "000003"]
    spot_df = pd.DataFrame(
        {
            "amount": [100.0, 100.0, 100.0],
        },
        index=symbols,
    )
    money_flow = {
        "000001": {"total_inflow": 0.0},
        "000002": {"total_inflow": 50.0},
        "000003": {"total_inflow": 100.0},
    }

    scores = score_capital_flow(symbols, money_flow, spot_df)

    assert scores["000001"] == 0.0
    assert scores["000002"] == cfg.WEIGHT_CAPITAL_FLOW / 2
    assert scores["000003"] == cfg.WEIGHT_CAPITAL_FLOW


def test_score_sector_leadership_uses_sector_score_map_first():
    spot_df = pd.DataFrame(
        {
            "code": ["000001", "000002"],
            "pct_change": [1.0, 10.0],
        }
    )

    scores = score_sector_leadership(
        ["000001", "000002"],
        {"000001": 20.0, "000002": 5.0},
        spot_df,
    )

    assert scores == {"000001": 20.0, "000002": 5.0}


def test_score_sector_leadership_falls_back_to_relative_strength(monkeypatch):
    monkeypatch.setattr(cfg, "SECTOR_FALLBACK_TO_RELATIVE_STRENGTH", True)
    spot_df = pd.DataFrame(
        {
            "code": ["000001", "000002", "000003", "000004", "000005"],
            "pct_change": [-2.0, -1.0, 0.0, 1.0, 9.0],
        }
    )

    scores = score_sector_leadership(["000001", "000005"], {}, spot_df)

    assert scores["000005"] == cfg.SECTOR_RANK_TOP20_SCORE
    assert scores["000001"] == cfg.SECTOR_RANK_OTHER_SCORE


def test_compute_total_scores_sorts_by_total_score_and_preserves_key_fields():
    symbols = ["000001", "000002"]
    indicators = {
        "000001": {
            "technical_score": 55,
            "ma_bullish": True,
            "trend_quality_pass": True,
            "above_ma20_days_20": 20,
            "ma20_slope_10_pct": 5,
            "ma20_slope_20_pct": 8,
            "close_ma20_ratio": 1.04,
            "vol_ratio": 2.0,
            "adx_value": 45,
            "macd_pass": True,
            "macd_score": 1,
            "expma_ratio": 0.03,
            "expma_score": 1,
            "plus_di": 35,
            "minus_di": 10,
            "entry_timing": {"position_vs_ma21": 5, "consecutive_down": 1, "position_vs_ma5": 1},
        },
        "000002": {
            "technical_score": 20,
            "ma_bullish": False,
            "trend_quality_pass": False,
            "above_ma20_days_20": 5,
            "ma20_slope_10_pct": 0,
            "ma20_slope_20_pct": 0,
            "close_ma20_ratio": 1.2,
            "vol_ratio": 0.8,
            "adx_value": 18,
            "macd_pass": False,
            "macd_score": 0,
            "expma_ratio": 0.005,
            "expma_score": 0,
            "plus_di": 12,
            "minus_di": 20,
            "entry_timing": {},
        },
    }
    spot_df = pd.DataFrame(
        {
            "code": symbols,
            "name": ["强势股", "弱势股"],
            "industry": ["测试", "测试"],
            "pct_change": [5.0, -1.0],
            "price": [10.0, 20.0],
            "amount": [1000.0, 1000.0],
        }
    )
    money_flow = {
        "000001": {"total_inflow": 200.0},
        "000002": {"total_inflow": 0.0},
    }
    flags = pd.DataFrame(
        {
            "code": symbols,
            "sector_rank_pct": [0.1, 0.8],
            "stock_rank_in_sector": [0.1, 0.9],
            "amount_ok": [True, True],
            "fund_ok": [True, False],
            "sector_hot": [True, False],
            "leading_stock": [True, False],
        }
    )

    out = compute_total_scores(
        symbols=symbols,
        indicators_results=indicators,
        money_flow_data=money_flow,
        spot_df=spot_df,
        sector_score_map={"000001": 20.0, "000002": 5.0},
        rule_flags=flags,
    )

    assert out.iloc[0]["code"] == "000001"
    assert out.iloc[0]["name"] == "强势股"
    assert out.iloc[0]["total_score"] > out.iloc[1]["total_score"]
    assert out.iloc[0]["entry_bonus"] > 0
    assert bool(out.iloc[0]["sector_hot"]) is True
