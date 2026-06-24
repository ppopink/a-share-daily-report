"""
万得(Wind)金融数据适配器 — 可选数据源
需要本地安装 Wind 终端 + WindPy 包 + 有效账号

使用方法:
    在 config.py 中设置 DATA_SOURCE = "wind"
    或在 screener.py 中手动调用 wind 函数替换数据源

Wind API 参考:
- w.wsd() — 日线历史数据
- w.wss() — 快照数据（实时行情）
- w.wset() — 数据集（板块、行业等）
"""

import pandas as pd
import numpy as np
from typing import Optional

import config as cfg

# 尝试导入 WindPy
try:
    from WindPy import w
    _WIND_AVAILABLE = True
except ImportError:
    _WIND_AVAILABLE = False
    w = None


def wind_is_available() -> bool:
    """检查 Wind 是否可用"""
    return _WIND_AVAILABLE


def wind_start() -> bool:
    """启动 Wind 连接，返回是否成功"""
    if not _WIND_AVAILABLE:
        print("[Wind] WindPy 未安装，请先安装: pip install WindPy")
        return False
    try:
        result = w.start()
        if result.ErrorCode != 0:
            print(f"[Wind] 连接失败: {result.Data}")
            return False
        print("[Wind] 连接成功")
        return True
    except Exception as e:
        print(f"[Wind] 启动异常: {e}")
        return False


def wind_get_kline(codes: list, days: int = None) -> dict:
    """
    通过 Wind 批量获取日K线数据
    codes: 股票代码列表 ['000001.SZ', '600519.SH']
    返回 {code: DataFrame}
    """
    if not _WIND_AVAILABLE or w is None:
        return {}

    if days is None:
        days = cfg.HISTORY_DAYS

    # Wind 代码格式: 000001.SZ, 600519.SH
    wind_codes = []
    for c in codes:
        if "." not in c:
            suffix = ".SH" if c.startswith("6") else ".SZ"
            wind_codes.append(f"{c}{suffix}")
        else:
            wind_codes.append(c)

    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=int(days * 1.6))).strftime("%Y-%m-%d")

    fields = ["open", "high", "low", "close", "volume", "amt", "pct_chg", "turn"]

    try:
        # w.wsd 批量获取历史数据
        result = w.wsd(
            ",".join(wind_codes),
            ",".join(fields),
            start_date, end_date,
            "returnType=dict"
        )
        if result.ErrorCode != 0:
            print(f"[Wind] K线获取失败: {result.Data}")
            return {}

        raw = result.Data  # dict keyed by field name
        results = {}

        # Wind 返回格式: {field: {code: [values]}}
        for i, wcode in enumerate(wind_codes):
            code = wcode.split(".")[0]
            df_data = {"date": result.Times}
            has_data = False
            for field in fields:
                if field in raw and wcode in raw[field]:
                    values = raw[field][wcode]
                    if values and any(v is not None for v in values):
                        has_data = True
                    df_data[field] = values
                else:
                    df_data[field] = [None] * len(result.Times)

            if has_data:
                df = pd.DataFrame(df_data)
                df = df.dropna(subset=["close"])
                df = df.rename(columns={
                    "amt": "amount", "pct_chg": "pct_change",
                    "turn": "turnover",
                })
                if len(df) >= 25:
                    results[code] = df

        return results

    except Exception as e:
        print(f"[Wind] K线获取异常: {e}")
        return {}


def wind_get_money_flow(codes: list, days: int = None) -> dict:
    """
    通过 Wind 获取资金流向数据
    Wind 资金流向字段: net_inflow_amount (主力净流入)
    """
    if not _WIND_AVAILABLE or w is None:
        return {}

    if days is None:
        days = cfg.FLOW_LOOKBACK_DAYS

    wind_codes = []
    for c in codes:
        suffix = ".SH" if c.startswith("6") else ".SZ"
        wind_codes.append(f"{c}{suffix}")

    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=int(days * 2.5))).strftime("%Y-%m-%d")

    try:
        result = w.wsd(
            ",".join(wind_codes),
            "net_inflow_amount",
            start_date, end_date,
            "returnType=dict"
        )
        if result.ErrorCode != 0:
            return {}

        raw = result.Data
        results = {}

        for i, wcode in enumerate(wind_codes):
            code = wcode.split(".")[0]
            values = raw.get("net_inflow_amount", {}).get(wcode, [])
            if values:
                total = sum(v for v in values[-days:] if v is not None)
                results[code] = {"symbol": code, "total_inflow": float(total)}

        return results

    except Exception as e:
        print(f"[Wind] 资金流向异常: {e}")
        return {}


def wind_get_stock_list() -> pd.DataFrame:
    """
    通过 Wind 获取全A股实时行情
    """
    if not _WIND_AVAILABLE or w is None:
        return pd.DataFrame()

    try:
        # 获取全部A股快照
        result = w.wset(
            "sectorconstituent",
            f"date={pd.Timestamp.now().strftime('%Y-%m-%d')};sectorid=a001010100000000"
        )
        if result.ErrorCode != 0:
            return pd.DataFrame()

        codes = result.Data[1]  # 股票代码列表
        wind_codes = codes

        # 获取行情快照
        fields = ["rt_last", "rt_pct_chg", "rt_vol", "rt_amt", "rt_turn",
                   "rt_high", "rt_low", "rt_open", "rt_pre_close"]

        snap = w.wss(
            ",".join(wind_codes),
            ",".join(fields),
            "returnType=dict"
        )
        if snap.ErrorCode != 0:
            return pd.DataFrame()

        rows = []
        for i, wcode in enumerate(wind_codes):
            code = wcode.split(".")[0] if "." in wcode else wcode
            rows.append({
                "code": code,
                "name": wcode,
                "price": float(snap.Data.get("rt_last", {}).get(wcode, 0) or 0),
                "pct_change": float(snap.Data.get("rt_pct_chg", {}).get(wcode, 0) or 0),
                "volume": float(snap.Data.get("rt_vol", {}).get(wcode, 0) or 0),
                "amount": float(snap.Data.get("rt_amt", {}).get(wcode, 0) or 0),
                "turnover": float(snap.Data.get("rt_turn", {}).get(wcode, 0) or 0),
                "high": float(snap.Data.get("rt_high", {}).get(wcode, 0) or 0),
                "low": float(snap.Data.get("rt_low", {}).get(wcode, 0) or 0),
                "open": float(snap.Data.get("rt_open", {}).get(wcode, 0) or 0),
                "pre_close": float(snap.Data.get("rt_pre_close", {}).get(wcode, 0) or 0),
            })

        df = pd.DataFrame(rows)
        if cfg.EXCLUDE_ST:
            df = df[~df["name"].str.contains("ST|退", na=False)]
        if cfg.EXCLUDE_BJ:
            df = df[~df["code"].str.match(r"^(8|4|9)\d{5}")]
        df = df[df["volume"] > 0]
        return df.reset_index(drop=True)

    except Exception as e:
        print(f"[Wind] 股票列表异常: {e}")
        return pd.DataFrame()
