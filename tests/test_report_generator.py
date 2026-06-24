import pandas as pd

import config as cfg
from report_generator import generate_pick_reports


def test_generate_pick_reports_creates_excel_and_html(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "OUTPUT_DIR", str(tmp_path))
    pick_df = pd.DataFrame([
        {
            "rank": 1,
            "code": "600000",
            "name": "测试股",
            "industry": "银行",
            "price": 10.5,
            "pct_change": 1.2,
            "total_score": 88.5,
            "trend_score": 12,
            "volume_score": 8,
            "dmi_score": 9,
            "macd_score": 7,
            "expma_score": 6,
            "money_flow_score": 15,
            "sector_score": 10,
            "leading_score": 5,
            "adx": 32,
            "vol_ratio": 1.6,
            "entry_label": "适合入场",
        }
    ])

    manifest = generate_pick_reports(pick_df, trade_date="2026-06-19", output_dir=str(tmp_path))

    assert manifest["excel"].endswith("stock_pick_20260619.xlsx")
    assert manifest["html"].endswith("stock_pick_report_20260619.html")
    assert (tmp_path / "stock_pick_20260619.xlsx").exists()
    assert (tmp_path / "stock_pick_report_20260619.html").exists()
