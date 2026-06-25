import pandas as pd

import config as cfg
import data_fetcher
from data_fetcher import (
    build_sector_score_map,
    get_hot_sector_boards,
    get_industry_performance,
    get_market_context_batch,
)


def test_get_industry_performance_aggregates_and_filters_small_groups():
    spot = pd.DataFrame(
        {
            "code": ["1", "2", "3", "4", "5"],
            "industry": ["芯片", "芯片", "芯片", "医药", "医药"],
            "pct_change": [3.0, 6.0, 9.0, 10.0, -10.0],
        }
    )

    perf = get_industry_performance(spot)

    assert perf["industry"].tolist() == ["芯片"]
    assert perf.iloc[0]["stock_count"] == 3
    assert perf.iloc[0]["avg_pct_change"] == 6.0


def test_build_sector_score_map_assigns_scores_by_industry_rank(monkeypatch):
    monkeypatch.setattr(cfg, "SECTOR_RANK_TOP20_SCORE", 10)
    monkeypatch.setattr(cfg, "SECTOR_RANK_OTHER_SCORE", 5)
    rows = []
    for i in range(3):
        rows.append({"code": f"00000{i}", "industry": "强势", "pct_change": 10 + i})
        rows.append({"code": f"00010{i}", "industry": "弱势", "pct_change": -3 + i})
    spot = pd.DataFrame(rows)

    scores = build_sector_score_map(spot)

    assert scores["000000"] >= scores["000100"]
    assert set(scores.keys()) == set(spot["code"])


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_get_hot_sector_boards_parses_eastmoney_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(cfg, "USE_DAILY_CACHE", False)
    monkeypatch.setattr(cfg, "FORCE_REFRESH_CACHE", False)
    monkeypatch.setattr(cfg, "USE_HOT_SECTOR_API", True)
    monkeypatch.setattr(cfg, "HOT_SECTOR_TOP_N", 2)

    payload = {
        "data": {
            "diff": [
                {
                    "f12": "BK001",
                    "f14": "芯片",
                    "f3": 5.0,
                    "f6": 1000.0,
                    "f8": 3.0,
                    "f104": 8,
                    "f105": 1,
                    "f106": 1,
                    "f128": "龙头A",
                    "f136": 10.0,
                    "f140": "000001",
                },
                {
                    "f12": "BK002",
                    "f14": "医药",
                    "f3": 1.0,
                    "f6": 200.0,
                    "f8": 1.0,
                    "f104": 3,
                    "f105": 6,
                    "f106": 1,
                    "f128": "龙头B",
                    "f136": 2.0,
                    "f140": "000002",
                },
            ]
        }
    }

    monkeypatch.setattr(data_fetcher, "_get", lambda *args, **kwargs: _FakeResponse(payload))
    out = get_hot_sector_boards(limit=2)

    assert out.iloc[0]["sector_name"] == "芯片"
    assert out.iloc[0]["heat_score"] > out.iloc[1]["heat_score"]
    assert out.iloc[0]["up_ratio"] == 0.8
    assert "领涨股龙头A" in out.iloc[0]["quant_note"]


def test_get_hot_sector_boards_returns_empty_on_api_error(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(cfg, "USE_DAILY_CACHE", False)
    monkeypatch.setattr(cfg, "USE_HOT_SECTOR_API", True)

    def raise_error(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(data_fetcher, "_get", raise_error)
    out = get_hot_sector_boards(limit=2)

    assert out.empty


def test_get_market_context_batch_combines_event_margin_and_lhb(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(cfg, "USE_DAILY_CACHE", False)
    monkeypatch.setattr(cfg, "USE_MARKET_CONTEXT_API", True)
    monkeypatch.setattr(cfg, "USE_EVENT_API", True)
    monkeypatch.setattr(cfg, "USE_MARGIN_API", True)
    monkeypatch.setattr(cfg, "USE_LHB_API", True)

    def fake_get(url, params=None, **kwargs):
        if "np-anotice" in url:
            return _FakeResponse({
                "data": {
                    "list": [
                        {"title": "关于回购股份方案的公告"},
                        {"title": "关于中标重大合同的公告"},
                    ]
                }
            })
        report = (params or {}).get("reportName")
        if report == "RPTA_WEB_RZRQ_GGMX":
            return _FakeResponse({
                "result": {
                    "data": [
                        {"RZYE": 110.0, "RZMRE": 30.0, "RZCHE": 10.0},
                        {"RZYE": 100.0, "RZMRE": 10.0, "RZCHE": 10.0},
                    ]
                }
            })
        if report == "RPT_DAILYBILLBOARD_DETAILSNEW":
            return _FakeResponse({
                "result": {
                    "data": [
                        {"BILLBOARD_NET_AMT": 200000000.0, "EXPLAIN": "日涨幅偏离值达7%"},
                    ]
                }
            })
        return _FakeResponse({})

    monkeypatch.setattr(data_fetcher, "_get", fake_get)
    out = get_market_context_batch(["000001"], max_workers=1)

    ctx = out["000001"]
    assert ctx["context_score"] > 0
    assert ctx["event_count"] == 2
    assert ctx["margin_balance_change_pct"] == 10.0
    assert ctx["lhb_count"] == 1
    assert "公告偏正面" in ctx["context_note"]
