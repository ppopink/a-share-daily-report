"""
回测模块 — 用历史数据验证选股模型的有效性
工作流程:
  1. 批量获取回测期内的所有K线数据 → 缓存到 parquet
  2. 对每个交易日，用当日之前的数据模拟选股
  3. 跟踪选中股票在未来 N 天的实际收益
  4. 统计胜率、平均收益、对比基准
"""

import os
import time
import json
import datetime
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import config as cfg
from data_fetcher import (
    _sina_symbol,
    _get,
    get_stock_list,
    estimate_money_flow_from_kline,
    build_sector_score_map,
    load_benchmark_data,
)
from indicators import calculate_all_indicators, check_all_conditions
from scorer import compute_total_scores
from screener import _apply_rule_hard_filters
from utils import progress_bar
from utils import output_day_dir

# ---- 缓存路径 ----
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")


def _fetch_kline_for_backtest(code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    获取单只股票在指定日期范围内的全部日K线（新浪源）
    返回 DataFrame 含 date/open/high/low/close/volume
    """
    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    # 请求足够多的数据（新浪datalen上限约2000）
    params = {"symbol": _sina_symbol(code), "scale": "240", "ma": "no", "datalen": "2000"}

    try:
        resp = _get(url, params, timeout=20)
        data = resp.json() if hasattr(resp, 'json') else __import__('json').loads(resp.text)
    except Exception:
        return None

    if not data or not isinstance(data, list):
        return None

    rows = []
    for item in data:
        d = str(item.get("day", ""))
        if start_date <= d <= end_date:
            try:
                rows.append({
                    "date": d,
                    "open": float(item.get("open", 0) or 0),
                    "high": float(item.get("high", 0) or 0),
                    "low": float(item.get("low", 0) or 0),
                    "close": float(item.get("close", 0) or 0),
                    "volume": float(item.get("volume", 0) or 0),
                })
            except (ValueError, TypeError):
                continue

    if len(rows) < 30:
        return None

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    return df


def fetch_all_kline_cache(codes: list, start_date: str, end_date: str,
                           max_workers: int = 2) -> str:
    """
    批量获取所有股票K线，缓存到 parquet 文件
    返回缓存文件路径
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"kline_{start_date}_{end_date}.parquet")

    if os.path.exists(cache_file):
        print(f"[回测] 使用已缓存数据: {cache_file}")
        return cache_file

    print(f"[回测] 获取 {len(codes)} 只股票K线 ({start_date} ~ {end_date})...")
    print(f"[回测] 预计耗时 {len(codes) * 0.3 / max_workers:.0f} 秒...")

    all_data = []
    done = 0

    def _fetch(code):
        nonlocal done
        df = _fetch_kline_for_backtest(code, start_date, end_date)
        done += 1
        if done % 200 == 0:
            progress_bar(done, len(codes), prefix="回测数据", suffix=f"{done}/{len(codes)}")
        if df is not None:
            df["code"] = code
        return df

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_fetch, c) for c in codes]
        for f in as_completed(futures):
            try:
                df = f.result()
                if df is not None and len(df) >= 50:
                    all_data.append(df)
            except Exception:
                pass

    if not all_data:
        raise RuntimeError("未获取到任何回测K线数据")

    full_df = pd.concat(all_data, ignore_index=True)
    full_df.to_parquet(cache_file, index=False)
    print(f"\n[回测] 缓存已保存: {cache_file} ({len(full_df)} 行, {full_df['code'].nunique()} 只股票)")
    return cache_file


def _slice_history(full_df: pd.DataFrame, code: str, as_of_date: str, lookback: int = 80) -> Optional[pd.DataFrame]:
    """
    从全量数据中切出某只股票截至某日的历史K线
    """
    stock_df = full_df[full_df["code"] == code].copy()
    if stock_df.empty:
        return None
    stock_df = stock_df[stock_df["date"] <= as_of_date].sort_values("date")
    if len(stock_df) < 25:
        return None
    return stock_df.tail(lookback).reset_index(drop=True)


def _build_spot_snapshot(
    histories: dict,
    stock_meta: pd.DataFrame,
) -> pd.DataFrame:
    """用信号日K线构造当日快照，供完整评分复用。"""
    meta = stock_meta.set_index("code") if "code" in stock_meta.columns else stock_meta
    rows = []
    for code, hist in histories.items():
        if hist is None or len(hist) < 2:
            continue
        latest = hist.iloc[-1]
        prev = hist.iloc[-2]
        close = float(latest["close"])
        prev_close = float(prev["close"])
        pct_change = (close - prev_close) / prev_close * 100 if prev_close > 0 else 0
        amount = float(latest["volume"]) * close
        name = code
        industry = ""
        if code in meta.index:
            name = meta.loc[code].get("name", code)
            industry = meta.loc[code].get("industry", "")
        rows.append({
            "code": code,
            "name": name,
            "price": close,
            "pct_change": pct_change,
            "volume": float(latest["volume"]),
            "amount": amount,
            "industry": industry,
        })
    return pd.DataFrame(rows)


def _forward_trade(
    full_df: pd.DataFrame,
    code: str,
    signal_date: str,
    hold_days: int,
    buy_mode: str = None,
    cost_pct: float = None,
) -> Optional[dict]:
    """
    计算信号后的持有期收益。
    默认信号日收盘生成信号，下一交易日开盘买入，持有N个交易日后收盘卖出。
    """
    if buy_mode is None:
        buy_mode = cfg.BACKTEST_BUY_MODE
    if cost_pct is None:
        cost_pct = cfg.BACKTEST_TRADE_COST_PCT

    stock_df = full_df[full_df["code"] == code].sort_values("date").reset_index(drop=True)
    signal_rows = stock_df.index[stock_df["date"] == signal_date].tolist()
    if not signal_rows:
        after_signal = stock_df[stock_df["date"] > signal_date]
        if after_signal.empty:
            return None
        signal_pos = int(after_signal.index[0])
    else:
        signal_pos = signal_rows[0]

    if buy_mode == "same_close":
        buy_pos = signal_pos
        buy_price = float(stock_df.iloc[buy_pos]["close"])
    else:
        buy_pos = signal_pos + 1
        if buy_pos >= len(stock_df):
            return None
        buy_price = float(stock_df.iloc[buy_pos]["open"])

    # 找持有期末的价格
    sell_pos = buy_pos + hold_days
    if sell_pos >= len(stock_df):
        return None
    sell_price = float(stock_df.iloc[sell_pos]["close"])

    if buy_price <= 0:
        return None
    holding = stock_df.iloc[buy_pos:sell_pos + 1]
    min_low = float(holding["low"].min()) if "low" in holding.columns and not holding.empty else min(buy_price, sell_price)
    max_drawdown = (min_low - buy_price) / buy_price * 100
    gross_return = (sell_price - buy_price) / buy_price * 100
    net_return = gross_return - cost_pct
    return {
        "return_pct": net_return,
        "gross_return_pct": gross_return,
        "buy_date": stock_df.iloc[buy_pos]["date"],
        "sell_date": stock_df.iloc[sell_pos]["date"],
        "buy_price": buy_price,
        "sell_price": sell_price,
        "holding_days": hold_days,
        "max_drawdown_during_holding": max_drawdown,
        "exit_reason": f"hold_{hold_days}d",
    }


def _forward_return(full_df: pd.DataFrame, code: str, buy_date: str, hold_days: int) -> Optional[float]:
    trade = _forward_trade(full_df, code, buy_date, hold_days)
    return None if trade is None else trade["return_pct"]


def _stock_frame(full_df: pd.DataFrame, code: str) -> pd.DataFrame:
    return full_df[full_df["code"] == code].sort_values("date").reset_index(drop=True)


def _row_for_date(stock_df: pd.DataFrame, date: str):
    rows = stock_df[stock_df["date"] == date]
    return None if rows.empty else rows.iloc[0]


def _is_suspended(row) -> bool:
    if row is None:
        return True
    return float(row.get("open", 0) or 0) <= 0 or float(row.get("close", 0) or 0) <= 0 or float(row.get("volume", 0) or 0) <= 0


def _prev_close(stock_df: pd.DataFrame, pos: int) -> float:
    if pos <= 0:
        return 0.0
    return float(stock_df.iloc[pos - 1].get("close", 0) or 0)


def _limit_up(stock_df: pd.DataFrame, pos: int) -> bool:
    prev = _prev_close(stock_df, pos)
    if prev <= 0:
        return False
    row = stock_df.iloc[pos]
    open_price = float(row.get("open", 0) or 0)
    return open_price >= prev * (1 + cfg.LIMIT_UP_PCT)


def _limit_down(stock_df: pd.DataFrame, pos: int) -> bool:
    prev = _prev_close(stock_df, pos)
    if prev <= 0:
        return False
    row = stock_df.iloc[pos]
    open_price = float(row.get("open", 0) or 0)
    return open_price <= prev * (1 - cfg.LIMIT_DOWN_PCT)


def _amount_for_row(row) -> float:
    if row is None:
        return 0.0
    if "amount" in row.index:
        return float(row.get("amount", 0) or 0)
    return float(row.get("volume", 0) or 0) * float(row.get("close", 0) or 0)


def _next_trade_pos(stock_df: pd.DataFrame, signal_date: str):
    signal_rows = stock_df.index[stock_df["date"] == signal_date].tolist()
    if signal_rows:
        pos = signal_rows[0] + 1
    else:
        after = stock_df.index[stock_df["date"] > signal_date].tolist()
        pos = after[0] if after else None
    if pos is None or pos >= len(stock_df):
        return None
    return pos


def _can_buy(stock_df: pd.DataFrame, pos: int) -> dict:
    row = stock_df.iloc[pos] if pos is not None and pos < len(stock_df) else None
    suspended = _is_suspended(row)
    limit_up = False if suspended else _limit_up(stock_df, pos)
    low_amount = _amount_for_row(row) < cfg.MIN_BUY_AMOUNT
    ok = not suspended and not limit_up and not low_amount
    reasons = []
    if suspended:
        reasons.append("suspended_on_buy_date")
    if limit_up:
        reasons.append("limit_up_on_buy_date")
    if low_amount:
        reasons.append("low_amount_on_buy_date")
    return {
        "ok": ok,
        "reason": ";".join(reasons),
        "suspended": suspended,
        "limit_up": limit_up,
        "low_amount": low_amount,
    }


def _can_sell(stock_df: pd.DataFrame, pos: int) -> dict:
    row = stock_df.iloc[pos] if pos is not None and pos < len(stock_df) else None
    suspended = _is_suspended(row)
    limit_down = False if suspended else _limit_down(stock_df, pos)
    ok = not suspended and not limit_down
    reasons = []
    if suspended:
        reasons.append("suspended_on_sell_date")
    if limit_down:
        reasons.append("limit_down_on_sell_date")
    return {
        "ok": ok,
        "reason": ";".join(reasons),
        "suspended": suspended,
        "limit_down": limit_down,
    }


def _merge_benchmark(equity_df: pd.DataFrame) -> pd.DataFrame:
    bench = load_benchmark_data()
    equity = equity_df.copy()
    if bench.empty:
        equity["benchmark_return"] = np.nan
        equity["benchmark_cumulative_return"] = np.nan
        equity["excess_return"] = np.nan
        equity["excess_cumulative_return"] = np.nan
        return equity
    bench = bench.rename(columns={
        "daily_return": "benchmark_return",
        "cumulative_return": "benchmark_cumulative_return",
    })
    equity = equity.merge(
        bench[["trade_date", "benchmark_return", "benchmark_cumulative_return"]],
        on="trade_date",
        how="left",
    )
    equity["benchmark_return"] = equity["benchmark_return"].fillna(0)
    equity["benchmark_cumulative_return"] = (1 + equity["benchmark_return"]).cumprod() - 1
    equity["excess_return"] = equity["daily_return"] - equity["benchmark_return"]
    equity["excess_cumulative_return"] = equity["cumulative_return"] - equity["benchmark_cumulative_return"]
    return equity


def _simulate_portfolio(
    signals_df: pd.DataFrame,
    full_df: pd.DataFrame,
    backtest_dates: list,
    hold_days: int,
    initial_cash: float = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """逐日盯市组合回测，返回交易明细和每日净值。"""
    if initial_cash is None:
        initial_cash = cfg.INITIAL_CASH
    cash = float(initial_cash)
    positions = {}
    trades = []
    equity_rows = []
    stock_cache = {c: _stock_frame(full_df, c) for c in full_df["code"].unique()}
    signals = signals_df.copy()
    if signals.empty:
        dates = backtest_dates
    else:
        signals = signals.sort_values(["date", "total_score"], ascending=[True, False])
        dates = sorted(set(backtest_dates) | set(signals["date"].astype(str)))

    last_value = initial_cash
    peak = initial_cash

    for date in dates:
        daily_buy_count = 0
        daily_sell_count = 0

        # 先处理到期卖出，无法卖出则顺延。
        for code in list(positions.keys()):
            pos_data = positions[code]
            stock_df = stock_cache.get(code, pd.DataFrame())
            rows = stock_df.index[stock_df["date"] == date].tolist()
            if not rows:
                continue
            row_pos = rows[0]
            if date < pos_data["target_sell_date"]:
                continue
            sell_check = _can_sell(stock_df, row_pos)
            if not sell_check["ok"]:
                pos_data["delayed_sell_days"] += 1
                pos_data["suspended_on_sell_date"] = pos_data["suspended_on_sell_date"] or sell_check["suspended"]
                pos_data["limit_down_on_sell_date"] = pos_data["limit_down_on_sell_date"] or sell_check["limit_down"]
                continue

            row = stock_df.iloc[row_pos]
            raw_sell_price = float(row["open"])
            sell_price = raw_sell_price * (1 - cfg.SLIPPAGE_RATE)
            gross_proceeds = pos_data["shares"] * sell_price
            commission = gross_proceeds * cfg.COMMISSION_RATE
            stamp_tax = gross_proceeds * cfg.STAMP_TAX_RATE
            cash += gross_proceeds - commission - stamp_tax
            daily_sell_count += 1

            gross_return = (raw_sell_price - pos_data["raw_buy_price"]) / pos_data["raw_buy_price"] * 100
            net_return = (gross_proceeds - commission - stamp_tax - pos_data["total_buy_cost"]) / pos_data["total_buy_cost"] * 100
            trades.append({
                **pos_data["meta"],
                "buy_status": "filled",
                "skip_reason": "",
                "delayed_buy_reason": pos_data.get("delayed_buy_reason", ""),
                "sell_status": "filled",
                "signal_date": pos_data["signal_date"],
                "buy_date": pos_data["buy_date"],
                "buy_price": round(pos_data["buy_price"], 4),
                "sell_date": date,
                "sell_price": round(sell_price, 4),
                "holding_days": int((pd.Timestamp(date) - pd.Timestamp(pos_data["buy_date"])).days),
                "return_pct": round(net_return, 4),
                "gross_return_pct": round(gross_return, 4),
                "max_drawdown_during_holding": round(pos_data["max_drawdown"], 4),
                "exit_reason": f"hold_{hold_days}d",
                "delayed_sell_days": pos_data["delayed_sell_days"],
                "limit_up_on_buy_date": pos_data["limit_up_on_buy_date"],
                "limit_down_on_sell_date": pos_data["limit_down_on_sell_date"],
                "suspended_on_buy_date": pos_data["suspended_on_buy_date"],
                "suspended_on_sell_date": pos_data["suspended_on_sell_date"],
                "commission": round(pos_data["buy_commission"] + commission, 4),
                "stamp_tax": round(stamp_tax, 4),
                "slippage_cost": round(pos_data["buy_slippage_cost"] + pos_data["shares"] * raw_sell_price * cfg.SLIPPAGE_RATE, 4),
                "gross_return": round(gross_return, 4),
                "net_return": round(net_return, 4),
            })
            del positions[code]

        # 再处理当天可买入信号：T日信号，只能在个股T+1交易日买。
        today_signals = signals[signals["date"].astype(str) < date] if not signals.empty else pd.DataFrame()
        if not today_signals.empty:
            candidates = []
            for _, sig in today_signals.iterrows():
                code = sig["code"]
                if code in positions:
                    continue
                if any(t.get("ts_code") == code and t.get("signal_date") == sig["date"] for t in trades):
                    continue
                stock_df = stock_cache.get(code, pd.DataFrame())
                buy_pos = _next_trade_pos(stock_df, str(sig["date"])) if not stock_df.empty else None
                if buy_pos is None or stock_df.iloc[buy_pos]["date"] != date:
                    continue
                candidates.append((sig, stock_df, buy_pos))

            slots = max(cfg.MAX_HOLDINGS - len(positions), 0)
            candidates = sorted(candidates, key=lambda x: float(x[0].get("total_score", 0)), reverse=True)
            for sig, stock_df, buy_pos in candidates[:slots]:
                code = sig["code"]
                buy_check = _can_buy(stock_df, buy_pos)
                meta = {
                    "ts_code": code,
                    "code": code,
                    "stock_name": sig.get("name", ""),
                    "industry": sig.get("industry", ""),
                    "sector_rank_pct": sig.get("sector_rank_pct", np.nan),
                    "stock_rank_in_sector": sig.get("stock_rank_in_sector", np.nan),
                    "vol_ratio": sig.get("vol_ratio", np.nan),
                    "adx": sig.get("adx", np.nan),
                    "main_net_ratio": sig.get("main_net_ratio", np.nan),
                    "rank": sig.get("rank", np.nan),
                    "total_score": sig.get("total_score", np.nan),
                }
                if not buy_check["ok"]:
                    trades.append({
                        **meta,
                        "signal_date": sig["date"],
                        "buy_date": stock_df.iloc[buy_pos]["date"],
                        "buy_status": "skipped",
                        "skip_reason": buy_check["reason"],
                        "delayed_buy_reason": buy_check["reason"],
                        "sell_status": "",
                        "suspended_on_buy_date": buy_check["suspended"],
                        "limit_up_on_buy_date": buy_check["limit_up"],
                        "suspended_on_sell_date": False,
                        "limit_down_on_sell_date": False,
                        "delayed_sell_days": 0,
                    })
                    continue

                alloc = min(cash, initial_cash * cfg.MAX_POSITION_PCT)
                if alloc <= 0:
                    continue
                row = stock_df.iloc[buy_pos]
                raw_buy_price = float(row["open"])
                buy_price = raw_buy_price * (1 + cfg.SLIPPAGE_RATE)
                shares = alloc / (buy_price * (1 + cfg.COMMISSION_RATE))
                gross_cost = shares * buy_price
                buy_commission = gross_cost * cfg.COMMISSION_RATE
                total_buy_cost = gross_cost + buy_commission
                if total_buy_cost > cash:
                    shares = cash / (buy_price * (1 + cfg.COMMISSION_RATE))
                    gross_cost = shares * buy_price
                    buy_commission = gross_cost * cfg.COMMISSION_RATE
                    total_buy_cost = gross_cost + buy_commission
                cash -= total_buy_cost
                target_pos = min(buy_pos + hold_days, len(stock_df) - 1)
                positions[code] = {
                    "meta": meta,
                    "signal_date": sig["date"],
                    "buy_date": date,
                    "raw_buy_price": raw_buy_price,
                    "buy_price": buy_price,
                    "shares": shares,
                    "total_buy_cost": total_buy_cost,
                    "buy_commission": buy_commission,
                    "buy_slippage_cost": shares * raw_buy_price * cfg.SLIPPAGE_RATE,
                    "target_sell_date": stock_df.iloc[target_pos]["date"],
                    "max_drawdown": 0.0,
                    "delayed_sell_days": 0,
                    "delayed_buy_reason": "",
                    "suspended_on_buy_date": False,
                    "limit_up_on_buy_date": False,
                    "suspended_on_sell_date": False,
                    "limit_down_on_sell_date": False,
                }
                daily_buy_count += 1

        position_value = 0.0
        for code, pos_data in positions.items():
            stock_df = stock_cache.get(code, pd.DataFrame())
            rows = stock_df[stock_df["date"] <= date]
            if rows.empty:
                mark = pos_data["buy_price"]
            else:
                row = rows.iloc[-1]
                mark = float(row["close"])
                dd = (float(row.get("low", mark)) - pos_data["buy_price"]) / pos_data["buy_price"] * 100
                pos_data["max_drawdown"] = min(pos_data["max_drawdown"], dd)
            position_value += pos_data["shares"] * mark

        portfolio_value = cash + position_value
        daily_return = portfolio_value / last_value - 1 if last_value > 0 else 0
        peak = max(peak, portfolio_value)
        equity_rows.append({
            "trade_date": date,
            "cash": cash,
            "position_value": position_value,
            "portfolio_value": portfolio_value,
            "daily_return": daily_return,
            "cumulative_return": portfolio_value / initial_cash - 1,
            "drawdown": portfolio_value / peak - 1 if peak > 0 else 0,
            "holding_count": len(positions),
            "daily_buy_count": daily_buy_count,
            "daily_sell_count": daily_sell_count,
        })
        last_value = portfolio_value

    equity = pd.DataFrame(equity_rows)
    if not equity.empty:
        equity = _merge_benchmark(equity)
    return pd.DataFrame(trades), equity


def _period_returns(equity_df: pd.DataFrame, freq: str, trades_df: pd.DataFrame = None) -> dict:
    if equity_df.empty:
        return {}
    eq = equity_df.copy()
    eq["dt"] = pd.to_datetime(eq["trade_date"])
    returns = {}
    for period, group in eq.groupby(eq["dt"].dt.to_period(freq)):
        start_value = float(group["portfolio_value"].iloc[0])
        end_value = float(group["portfolio_value"].iloc[-1])
        ret = end_value / start_value - 1 if start_value > 0 else 0
        data = {"return": round(ret * 100, 2)}
        if freq == "Y" and trades_df is not None and not trades_df.empty:
            year = int(str(period))
            count = int((pd.to_datetime(trades_df["signal_date"]).dt.year == year).sum())
            data["trade_count"] = count
            data["sample_too_small"] = count < 10
        returns[str(period)] = data
    return returns


def _build_summary(trades_df: pd.DataFrame, equity_df: pd.DataFrame) -> dict:
    start_date = str(equity_df["trade_date"].iloc[0]) if not equity_df.empty else ""
    end_date = str(equity_df["trade_date"].iloc[-1]) if not equity_df.empty else ""
    initial_cash = float(cfg.INITIAL_CASH)
    final_value = float(equity_df["portfolio_value"].iloc[-1]) if not equity_df.empty else initial_cash
    if trades_df.empty:
        return {
            "start_date": start_date,
            "end_date": end_date,
            "initial_cash": initial_cash,
            "final_portfolio_value": final_value,
            "total_return": 0,
            "annual_return": 0,
            "gross_return": 0,
            "net_return": 0,
            "benchmark_total_return": 0,
            "excess_total_return": 0,
            "benchmark_annual_return": 0,
            "excess_annual_return": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "information_ratio": 0,
            "win_rate": 0,
            "trade_count": 0,
            "skipped_buy_count": 0,
            "delayed_sell_count": 0,
            "average_holding_days": 0,
            "average_delayed_sell_days": 0,
            "average_position_count": 0,
            "max_position_count": 0,
            "turnover_rate": 0,
            "total_commission": 0,
            "total_stamp_tax": 0,
            "total_slippage_cost": 0,
            "average_return_per_trade": 0,
            "median_return_per_trade": 0,
            "profit_loss_ratio": 0,
            "max_single_trade_loss": 0,
            "max_single_trade_gain": 0,
            "yearly_returns": {},
            "monthly_returns": {},
            "yearly_excess_returns": {},
            "sample_too_small_by_year": {},
        }

    filled = trades_df[trades_df.get("buy_status", "") == "filled"].copy()
    returns = filled["return_pct"].astype(float) if not filled.empty and "return_pct" in filled.columns else pd.Series(dtype=float)
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    total_return = float(equity_df["cumulative_return"].iloc[-1] * 100) if not equity_df.empty else float(returns.sum())
    days = max((pd.to_datetime(equity_df["trade_date"]).max() - pd.to_datetime(equity_df["trade_date"]).min()).days, 1) if not equity_df.empty else 1
    annual_return = ((1 + total_return / 100) ** (365 / days) - 1) * 100 if total_return > -100 else -100
    max_drawdown = float(equity_df["drawdown"].min() * 100) if not equity_df.empty else 0
    daily = equity_df["daily_return"].astype(float) if not equity_df.empty else pd.Series(dtype=float)
    sharpe = 0.0
    if len(daily) > 1 and daily.std() > 0:
        sharpe = float(daily.mean() / daily.std() * np.sqrt(252))
    benchmark_total = float(equity_df["benchmark_cumulative_return"].iloc[-1] * 100) if "benchmark_cumulative_return" in equity_df.columns and equity_df["benchmark_cumulative_return"].notna().any() else 0
    excess_total = total_return - benchmark_total
    benchmark_annual = ((1 + benchmark_total / 100) ** (365 / days) - 1) * 100 if benchmark_total > -100 else -100
    excess_annual = annual_return - benchmark_annual
    information_ratio = 0.0
    if "excess_return" in equity_df.columns:
        excess_daily = equity_df["excess_return"].dropna().astype(float)
        if len(excess_daily) > 1 and excess_daily.std() > 0:
            information_ratio = float(excess_daily.mean() / excess_daily.std() * np.sqrt(252))

    yearly_returns = _period_returns(equity_df, "Y", filled)
    yearly_excess = {}
    if "excess_cumulative_return" in equity_df.columns and not equity_df.empty:
        eq = equity_df.copy()
        eq["dt"] = pd.to_datetime(eq["trade_date"])
        for period, group in eq.groupby(eq["dt"].dt.to_period("Y")):
            start_v = float(group["excess_cumulative_return"].iloc[0])
            end_v = float(group["excess_cumulative_return"].iloc[-1])
            yearly_excess[str(period)] = round((end_v - start_v) * 100, 2)
    sample_small = {year: data.get("sample_too_small", True) for year, data in yearly_returns.items()}

    return {
        "start_date": start_date,
        "end_date": end_date,
        "initial_cash": initial_cash,
        "final_portfolio_value": round(final_value, 2),
        "total_return": round(total_return, 2),
        "annual_return": round(float(annual_return), 2),
        "gross_return": round(float(filled["gross_return_pct"].mean()), 2) if "gross_return_pct" in filled.columns and not filled.empty else 0,
        "net_return": round(float(returns.mean()), 2) if not returns.empty else 0,
        "benchmark_total_return": round(benchmark_total, 2),
        "excess_total_return": round(excess_total, 2),
        "benchmark_annual_return": round(float(benchmark_annual), 2),
        "excess_annual_return": round(float(excess_annual), 2),
        "max_drawdown": round(max_drawdown, 2),
        "sharpe_ratio": round(sharpe, 4),
        "information_ratio": round(information_ratio, 4),
        "win_rate": round(float((returns > 0).mean() * 100), 2) if not returns.empty else 0,
        "trade_count": int(len(filled)),
        "skipped_buy_count": int((trades_df.get("buy_status", "") == "skipped").sum()) if "buy_status" in trades_df.columns else 0,
        "delayed_sell_count": int((filled.get("delayed_sell_days", 0) > 0).sum()) if not filled.empty and "delayed_sell_days" in filled.columns else 0,
        "average_holding_days": round(float(filled["holding_days"].mean()), 2) if "holding_days" in filled.columns and not filled.empty else 0,
        "average_delayed_sell_days": round(float(filled["delayed_sell_days"].mean()), 2) if "delayed_sell_days" in filled.columns and not filled.empty else 0,
        "average_position_count": round(float(equity_df["holding_count"].mean()), 2) if "holding_count" in equity_df.columns and not equity_df.empty else 0,
        "max_position_count": int(equity_df["holding_count"].max()) if "holding_count" in equity_df.columns and not equity_df.empty else 0,
        "turnover_rate": round(float(len(filled) / max(len(equity_df), 1)), 4),
        "total_commission": round(float(filled.get("commission", pd.Series(dtype=float)).sum()), 2),
        "total_stamp_tax": round(float(filled.get("stamp_tax", pd.Series(dtype=float)).sum()), 2),
        "total_slippage_cost": round(float(filled.get("slippage_cost", pd.Series(dtype=float)).sum()), 2),
        "average_return_per_trade": round(float(returns.mean()), 2) if not returns.empty else 0,
        "median_return_per_trade": round(float(returns.median()), 2) if not returns.empty else 0,
        "profit_loss_ratio": round(float(wins.mean() / abs(losses.mean())), 2) if len(wins) and len(losses) else 0,
        "max_single_trade_loss": round(float(returns.min()), 2) if not returns.empty else 0,
        "max_single_trade_gain": round(float(returns.max()), 2) if not returns.empty else 0,
        "yearly_returns": yearly_returns,
        "monthly_returns": _period_returns(equity_df, "M"),
        "yearly_excess_returns": yearly_excess,
        "sample_too_small_by_year": sample_small,
    }


def _save_backtest_outputs(report: dict) -> dict:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = output_day_dir(ts[:8])
    trades_file = os.path.join(out_dir, f"backtest_trades_{ts}.csv")
    equity_file = os.path.join(out_dir, f"backtest_daily_equity_{ts}.csv")
    summary_file = os.path.join(out_dir, f"backtest_summary_{ts}.json")

    report["trades_df"].to_csv(trades_file, index=False, encoding="utf-8-sig")
    report["daily_equity_df"].to_csv(equity_file, index=False, encoding="utf-8-sig")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(report["summary"], f, ensure_ascii=False, indent=2)

    paths = {
        "trades": trades_file,
        "daily_equity": equity_file,
        "summary": summary_file,
    }
    report["output_files"] = paths
    return paths


def run_backtest_from_csv(history_csv: str, hold_days_list: list = None, save_outputs: bool = True) -> dict:
    """
    从已保存的 daily_picks_history.csv 直接读取历史选股记录，
    不需要重新跑模型，直接计算持有期收益 → 极快

    参数:
    - history_csv: daily_picks_history.csv 文件路径
    - hold_days_list: 持有天数列表

    返回: 回测报告 dict（格式同 run_backtest）
    """
    if hold_days_list is None:
        hold_days_list = [5, 10, 20]

    if not os.path.exists(history_csv):
        return {"error": f"文件不存在: {history_csv}"}

    print("=" * 70)
    print(f"  📊 快速回测（基于已保存的选股记录）")
    print(f"  数据源: {history_csv}")
    print(f"  持有期: {hold_days_list} 天")
    print("=" * 70)
    print()

    # 读取历史记录
    trades_df = pd.read_csv(history_csv)
    print(f"[回测] 读取 {len(trades_df)} 条历史选股记录")
    print(f"[回测] 日期范围: {trades_df['trade_date'].min()} ~ {trades_df['trade_date'].max()}")
    print(f"[回测] 涉及 {trades_df['code'].nunique()} 只不同股票")

    # 确定需要获取K线数据的日期范围
    min_date = trades_df["trade_date"].min()
    max_date = trades_df["trade_date"].max()
    buffer_before = 100
    buffer_after = max(hold_days_list) + 5
    fetch_start = (pd.Timestamp(min_date) - pd.Timedelta(days=buffer_before)).strftime("%Y-%m-%d")
    fetch_end = (pd.Timestamp(max_date) + pd.Timedelta(days=buffer_after)).strftime("%Y-%m-%d")

    # 获取涉及的股票K线数据
    codes = trades_df["code"].unique().tolist()
    print(f"\n[回测] 获取 {len(codes)} 只股票的K线数据用于计算收益...")
    cache_file = fetch_all_kline_cache(codes, fetch_start, fetch_end)
    full_df = pd.read_parquet(cache_file)

    print(f"\n[回测] 逐日盯市组合模拟...")
    signal_df = trades_df.rename(columns={"trade_date": "date", "name": "stock_name"}).copy()
    if "total_score" not in signal_df.columns:
        signal_df["total_score"] = 0
    hold_days = hold_days_list[0]
    all_dates = sorted(full_df["date"].unique())
    backtest_dates = [d for d in all_dates if min_date <= d <= fetch_end]
    detailed_df, daily_equity_df = _simulate_portfolio(
        signal_df,
        full_df,
        backtest_dates,
        hold_days=hold_days,
        initial_cash=cfg.INITIAL_CASH,
    )
    summary = _build_summary(detailed_df, daily_equity_df)
    filled = detailed_df[detailed_df.get("buy_status", "") == "filled"].copy() if not detailed_df.empty else detailed_df
    returns = filled["return_pct"].astype(float) if not filled.empty and "return_pct" in filled.columns else pd.Series(dtype=float)
    results = {
        f"hold_{hold_days}d": {
            "trades": int(len(filled)),
            "win_count": int((returns > 0).sum()) if not returns.empty else 0,
            "win_rate": round(float((returns > 0).mean() * 100), 1) if not returns.empty else 0,
            "avg_return": round(float(returns.mean()), 2) if not returns.empty else 0,
            "median_return": round(float(returns.median()), 2) if not returns.empty else 0,
            "max_return": round(float(returns.max()), 2) if not returns.empty else 0,
            "min_return": round(float(returns.min()), 2) if not returns.empty else 0,
            "std_return": round(float(returns.std()), 2) if len(returns) > 1 else 0,
            "total_return": summary.get("total_return", 0),
        }
    }

    report = {
        "config": {
            "source": "csv",
            "csv_file": history_csv,
            "date_range": f"{min_date} ~ {max_date}",
            "total_trades": len(trades_df),
            "unique_stocks": int(trades_df["code"].nunique()),
            "hold_periods": hold_days_list,
            "buy_mode": cfg.BACKTEST_BUY_MODE,
            "trade_cost_pct": cfg.BACKTEST_TRADE_COST_PCT,
        },
        "results": results,
        "trades_df": detailed_df,
        "daily_equity_df": daily_equity_df,
        "summary": summary,
    }
    if save_outputs:
        _save_backtest_outputs(report)

    return report


def run_backtest(
    start_date: str = None,
    end_date: str = None,
    hold_days_list: list = None,
    max_stocks_per_day: int = 10,
    code_limit: int = None,
    save_outputs: bool = True,
) -> dict:
    """
    执行完整回测

    参数:
    - start_date: 回测起始日 '2025-06-01'
    - end_date: 回测结束日 '2026-06-18'
    - hold_days_list: 持有天数列表 [5, 10, 20]
    - max_stocks_per_day: 每日最多选股数
    - code_limit: 限制股票数量（测试用，None=全量）

    返回: 回测报告 dict
    """
    if hold_days_list is None:
        hold_days_list = [5, 10, 20]

    # 默认回测近一年
    today = datetime.date.today()
    if end_date is None:
        end_date = today.strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (today - datetime.timedelta(days=365)).strftime("%Y-%m-%d")

    # 数据需要覆盖回测期 + 前80天（计算指标）+ 后max(hold_days)天（计算收益）
    buffer_before = 100
    buffer_after = max(hold_days_list) + 5
    fetch_start = (pd.Timestamp(start_date) - pd.Timedelta(days=buffer_before)).strftime("%Y-%m-%d")
    fetch_end = (pd.Timestamp(end_date) + pd.Timedelta(days=buffer_after)).strftime("%Y-%m-%d")

    print("=" * 70)
    print(f"  📊 回测模式")
    print(f"  回测期: {start_date} → {end_date}")
    print(f"  持有期: {hold_days_list} 天")
    print(f"  数据范围: {fetch_start} ~ {fetch_end}")
    if code_limit:
        print(f"  股票范围: 前 {code_limit} 只（测试模式）")
    print("=" * 70)
    print()

    # ---- Step 1: 获取股票列表 ----
    print("[回测] Step 1/5: 获取股票列表...")
    spot_df = get_stock_list()
    codes = spot_df["code"].astype(str).tolist()
    if code_limit and code_limit < len(codes):
        codes = codes[:code_limit]
    print(f"[回测] 候选股票: {len(codes)} 只")

    # ---- Step 2: 批量获取全量K线并缓存 ----
    print(f"\n[回测] Step 2/5: 批量获取K线数据...")
    cache_file = fetch_all_kline_cache(codes, fetch_start, fetch_end)
    full_df = pd.read_parquet(cache_file)
    print(f"[回测] 加载数据: {full_df['code'].nunique()} 只股票, {len(full_df)} 行")

    # ---- Step 3: 确定回测交易日列表 ----
    print(f"\n[回测] Step 3/5: 确定回测日期...")
    all_dates = sorted(full_df["date"].unique())
    backtest_dates = [d for d in all_dates if start_date <= d <= end_date]
    print(f"[回测] 共 {len(backtest_dates)} 个交易日")

    # ---- Step 4: 逐日模拟选股 ----
    print(f"\n[回测] Step 4/5: 逐日模拟选股...")
    all_trades = []  # 每笔: {date, code, name, score, ...}

    for i, as_of in enumerate(backtest_dates):
        day_histories = {}
        indicators_results = {}
        passed_symbols = []

        for code in codes:
            hist = _slice_history(full_df, code, as_of, cfg.HISTORY_DAYS)
            if hist is None:
                continue

            df_ind = calculate_all_indicators(hist)
            result = check_all_conditions(df_ind)
            indicators_results[code] = result
            day_histories[code] = hist
            if result["passed"]:
                passed_symbols.append(code)

        if passed_symbols:
            day_spot = _build_spot_snapshot(
                {c: day_histories[c] for c in day_histories},
                spot_df,
            )
            money_flow = estimate_money_flow_from_kline(
                {c: day_histories[c] for c in passed_symbols if c in day_histories}
            )
            passed_symbols, rule_flags = _apply_rule_hard_filters(
                passed_symbols,
                day_spot,
                money_flow,
                verbose=False,
            )
            if not passed_symbols:
                continue
            sector_score_map = build_sector_score_map(day_spot)
            scored = compute_total_scores(
                symbols=passed_symbols,
                indicators_results=indicators_results,
                money_flow_data=money_flow,
                spot_df=day_spot,
                sector_score_map=sector_score_map,
                rule_flags=rule_flags,
            )
            top = scored.head(max_stocks_per_day)
            for rank, (_, r) in enumerate(top.iterrows(), 1):
                all_trades.append({
                    "date": as_of,
                    "code": r["code"],
                    "name": r.get("name", r["code"]),
                    "industry": r.get("industry", ""),
                    "rank": rank,
                    "total_score": r["total_score"],
                    "raw_score": r["raw_score"],
                    "entry_bonus": r["entry_bonus"],
                    "flow_score": r["flow_score"],
                    "sector_score": r["sector_score"],
                    "tech_score": r["tech_score"],
                    "adx": r["adx"],
                    "plus_di": r.get("plus_di", 0),
                    "minus_di": r.get("minus_di", 0),
                    "pdi_mdi_diff": r.get("pdi_mdi_diff", 0),
                    "vol_ratio": r["vol_ratio"],
                    "main_net_ratio": r.get("main_net_ratio", 0),
                    "sector_rank_pct": r.get("sector_rank_pct", np.nan),
                    "stock_rank_in_sector": r.get("stock_rank_in_sector", np.nan),
                    "close_ma21_ratio": r.get("close_ma21_ratio", 0),
                    "ma3_ma5_ratio": r.get("ma3_ma5_ratio", 0),
                    "expma_ratio": r.get("expma_ratio", 0),
                    "macd_diff": r.get("macd_diff", 0),
                    "macd_dea": r.get("macd_dea", 0),
                    "macd_hist": r.get("macd_hist", 0),
                    "entry_label": r.get("entry_label", ""),
                })

        if (i + 1) % 20 == 0 or i == len(backtest_dates) - 1:
            progress_bar(i + 1, len(backtest_dates), prefix="回测进度",
                         suffix=f"{i+1}/{len(backtest_dates)} 累计选中{len(all_trades)}笔")

    if not all_trades:
        print("\n[回测] 回测期内无任何股票通过筛选！")
        return {"error": "无符合条件的交易"}

    trades_df = pd.DataFrame(all_trades)
    print(f"\n[回测] 回测期共产生 {len(trades_df)} 笔交易")
    print(f"[回测] 涉及 {trades_df['code'].nunique()} 只不同股票")
    print(f"[回测] 有效交易日: {trades_df['date'].nunique()} 天")

    # ---- Step 5: 逐日盯市组合模拟 ----
    hold_days = hold_days_list[0]
    print(f"\n[回测] Step 5/5: 逐日盯市组合模拟（持有 {hold_days} 天）...")
    detailed_df, daily_equity_df = _simulate_portfolio(
        trades_df,
        full_df,
        backtest_dates,
        hold_days=hold_days,
        initial_cash=cfg.INITIAL_CASH,
    )
    summary = _build_summary(detailed_df, daily_equity_df)
    filled = detailed_df[detailed_df.get("buy_status", "") == "filled"].copy() if not detailed_df.empty else detailed_df
    returns = filled["return_pct"].astype(float) if not filled.empty and "return_pct" in filled.columns else pd.Series(dtype=float)
    results = {}
    if not returns.empty:
        results[f"hold_{hold_days}d"] = {
            "trades": int(len(filled)),
            "win_count": int((returns > 0).sum()),
            "win_rate": round(float((returns > 0).mean() * 100), 1),
            "avg_return": round(float(returns.mean()), 2),
            "median_return": round(float(returns.median()), 2),
            "max_return": round(float(returns.max()), 2),
            "min_return": round(float(returns.min()), 2),
            "std_return": round(float(returns.std()), 2) if len(returns) > 1 else 0,
            "total_return": summary.get("total_return", 0),
        }
    else:
        results[f"hold_{hold_days}d"] = {"trades": 0, "error": "无有效成交"}

    # ---- 生成报告 ----
    report = {
        "config": {
            "start_date": start_date,
            "end_date": end_date,
            "backtest_days": len(backtest_dates),
            "total_trades": len(trades_df),
            "unique_stocks": int(trades_df["code"].nunique()),
            "hold_periods": hold_days_list,
            "buy_mode": cfg.BACKTEST_BUY_MODE,
            "trade_cost_pct": cfg.BACKTEST_TRADE_COST_PCT,
        },
        "results": results,
        "trades_df": detailed_df,
        "signals_df": trades_df,
        "daily_equity_df": daily_equity_df,
        "summary": summary,
    }
    if save_outputs:
        paths = _save_backtest_outputs(report)
        print(f"💾 回测交易明细: {paths['trades']}")
        print(f"💾 每日净值: {paths['daily_equity']}")
        print(f"💾 汇总报告: {paths['summary']}")

    return report


def print_report(report: dict):
    """格式化输出回测报告"""
    if "error" in report:
        print(f"\n  ❌ {report['error']}")
        return

    cfg = report["config"]
    res = report["results"]

    print("\n")
    print("=" * 70)
    print("  📊 回测报告")
    print("=" * 70)
    if cfg.get("source") == "csv":
        print(f"  数据来源:    CSV ({cfg.get('csv_file', '')})")
        print(f"  日期范围:    {cfg.get('date_range', '')}")
    else:
        print(f"  回测期:      {cfg.get('start_date', '')} → {cfg.get('end_date', '')}")
        print(f"  交易日数:    {cfg.get('backtest_days', '')} 天")
    print(f"  总交易笔数:  {cfg['total_trades']} 笔")
    print(f"  涉及股票:    {cfg['unique_stocks']} 只")
    print(f"  买入方式:    {cfg.get('buy_mode', '')}")
    print(f"  交易成本:    {cfg.get('trade_cost_pct', 0):.2f}%")
    print("-" * 70)

    for period, data in res.items():
        days = period.replace("hold_", "").replace("d", "")
        print(f"\n  📈 持有 {days} 天:")
        print(f"    交易数:    {data.get('trades', 0)} 笔")
        print(f"    盈利笔数:  {data.get('win_count', 0)}")
        print(f"    🎯 胜率:   {data.get('win_rate', 0)}%")
        print(f"    平均收益:  {data.get('avg_return', 0):+.2f}%")
        print(f"    中位收益:  {data.get('median_return', 0):+.2f}%")
        print(f"    最大收益:  {data.get('max_return', 0):+.2f}%")
        print(f"    最大亏损:  {data.get('min_return', 0):+.2f}%")
        print(f"    标准差:    {data.get('std_return', 0):.2f}%")
        print(f"    累计收益:  {data.get('total_return', 0):+.2f}%")

    summary = report.get("summary", {})
    if summary:
        print("\n  📌 汇总指标:")
        print(f"    总收益:    {summary.get('total_return', 0):+.2f}%")
        print(f"    年化收益:  {summary.get('annual_return', 0):+.2f}%")
        print(f"    最大回撤:  {summary.get('max_drawdown', 0):+.2f}%")
        print(f"    盈亏比:    {summary.get('profit_loss_ratio', 0):.2f}")
        print(f"    夏普:      {summary.get('sharpe_ratio', 0):.2f}")

        yearly = summary.get("yearly_returns", {})
        if yearly:
            print("\n  📅 分年度表现:")
            for year, data in yearly.items():
                sample = " sample_too_small=True" if data.get("sample_too_small") else ""
                print(f"    {year}: {data.get('return', 0):+.2f}% | 交易 {data.get('trade_count', 0)} 笔{sample}")

    print("\n" + "=" * 70)

    # 简要评价
    best_period = max(res.keys(), key=lambda k: res[k].get("win_rate", 0))
    best_days = best_period.replace("hold_", "").replace("d", "")
    best_wr = res[best_period].get("win_rate", 0)
    print(f"\n  💡 最佳持有期: {best_days} 天 (胜率 {best_wr}%)")

    if best_wr >= 60:
        print(f"  ✅ 模型表现良好，胜率显著高于随机")
    elif best_wr >= 50:
        print(f"  ⚠️ 模型有一定参考价值，胜率略高于随机")
    else:
        print(f"  ❌ 模型需要优化，胜率不理想")

    print()
