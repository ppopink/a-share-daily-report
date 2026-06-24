import pandas as pd

import config as cfg
from backtest import _simulate_portfolio


def _base_kline(code="000001"):
    return pd.DataFrame([
        {"code": code, "date": "2025-01-01", "open": 10.0, "high": 10.2, "low": 9.8, "close": 10.0, "volume": 1000},
        {"code": code, "date": "2025-01-02", "open": 10.0, "high": 10.4, "low": 9.9, "close": 10.2, "volume": 1000},
        {"code": code, "date": "2025-01-03", "open": 10.3, "high": 11.2, "low": 10.2, "close": 11.0, "volume": 1000},
        {"code": code, "date": "2025-01-04", "open": 11.0, "high": 11.5, "low": 10.8, "close": 11.4, "volume": 1000},
        {"code": code, "date": "2025-01-05", "open": 11.5, "high": 11.8, "low": 11.0, "close": 11.2, "volume": 1000},
    ])


def _signals(code="000001", date="2025-01-01"):
    return pd.DataFrame([{
        "date": date,
        "code": code,
        "name": "测试股",
        "total_score": 90,
        "industry": "测试行业",
        "sector_rank_pct": 0.1,
        "stock_rank_in_sector": 0.1,
        "vol_ratio": 1.5,
        "adx": 30,
        "main_net_ratio": 0.01,
    }])


def _patch_costs(monkeypatch):
    monkeypatch.setattr(cfg, "INITIAL_CASH", 100000.0)
    monkeypatch.setattr(cfg, "MIN_BUY_AMOUNT", 0)
    monkeypatch.setattr(cfg, "MAX_HOLDINGS", 10)
    monkeypatch.setattr(cfg, "MAX_POSITION_PCT", 0.1)
    monkeypatch.setattr(cfg, "COMMISSION_RATE", 0.0)
    monkeypatch.setattr(cfg, "STAMP_TAX_RATE", 0.0)
    monkeypatch.setattr(cfg, "SLIPPAGE_RATE", 0.0)


def test_signal_buys_only_on_t_plus_1(monkeypatch):
    _patch_costs(monkeypatch)
    trades, _ = _simulate_portfolio(_signals(), _base_kline(), ["2025-01-01", "2025-01-02", "2025-01-03"], 1)
    filled = trades[trades["buy_status"] == "filled"].iloc[0]
    assert filled["signal_date"] == "2025-01-01"
    assert filled["buy_date"] == "2025-01-02"


def test_does_not_use_signal_day_open_price(monkeypatch):
    _patch_costs(monkeypatch)
    df = _base_kline()
    df.loc[df["date"] == "2025-01-01", "open"] = 1.0
    df.loc[df["date"] == "2025-01-02", "open"] = 10.0
    trades, _ = _simulate_portfolio(_signals(), df, ["2025-01-01", "2025-01-02", "2025-01-03"], 1)
    filled = trades[trades["buy_status"] == "filled"].iloc[0]
    assert filled["buy_price"] == 10.0


def test_suspended_buy_date_is_skipped(monkeypatch):
    _patch_costs(monkeypatch)
    df = _base_kline()
    df.loc[df["date"] == "2025-01-02", "volume"] = 0
    trades, _ = _simulate_portfolio(_signals(), df, ["2025-01-01", "2025-01-02", "2025-01-03"], 1)
    skipped = trades[trades["buy_status"] == "skipped"].iloc[0]
    assert bool(skipped["suspended_on_buy_date"]) is True
    assert "suspended_on_buy_date" in skipped["skip_reason"]


def test_limit_up_buy_date_is_skipped(monkeypatch):
    _patch_costs(monkeypatch)
    df = _base_kline()
    df.loc[df["date"] == "2025-01-02", "open"] = 11.0
    trades, _ = _simulate_portfolio(_signals(), df, ["2025-01-01", "2025-01-02", "2025-01-03"], 1)
    skipped = trades[trades["buy_status"] == "skipped"].iloc[0]
    assert bool(skipped["limit_up_on_buy_date"]) is True
    assert "limit_up_on_buy_date" in skipped["skip_reason"]


def test_limit_down_sell_is_delayed(monkeypatch):
    _patch_costs(monkeypatch)
    df = _base_kline()
    # buy on 2025-01-02, target sell 2025-01-03; make 2025-01-03跌停无法卖出。
    df.loc[df["date"] == "2025-01-03", "open"] = 9.0
    trades, _ = _simulate_portfolio(_signals(), df, ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"], 1)
    filled = trades[trades["buy_status"] == "filled"].iloc[0]
    assert filled["sell_date"] == "2025-01-04"
    assert filled["delayed_sell_days"] == 1
    assert bool(filled["limit_down_on_sell_date"]) is True


def test_daily_equity_marks_to_market_while_holding(monkeypatch):
    _patch_costs(monkeypatch)
    df = _base_kline()
    trades, equity = _simulate_portfolio(_signals(), df, ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"], 2)
    held = equity[equity["holding_count"] > 0]
    assert len(held) >= 2
    values = held["portfolio_value"].round(4).tolist()
    assert len(set(values)) > 1
