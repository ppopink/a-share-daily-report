"""
数据获取层 — 混合数据源
- 新浪财经 API: 股票列表 + K线历史（稳定可靠）
- 东方财富 push2his API: 资金流向
使用 curl_cffi 模拟浏览器TLS指纹
"""

import time
import json
import os
import datetime
import glob
import re
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from typing import Optional

import config as cfg
from utils import progress_bar, get_recent_trading_dates, get_market_prefix


LAST_STOCK_FILTER_LOG = []


def _cache_enabled() -> bool:
    return bool(getattr(cfg, "USE_DAILY_CACHE", True))


def _force_refresh_cache() -> bool:
    return bool(getattr(cfg, "FORCE_REFRESH_CACHE", False))


def _cache_dir() -> str:
    path = getattr(cfg, "CACHE_DIR", "cache")
    os.makedirs(path, exist_ok=True)
    return path


def _today_key() -> str:
    return datetime.date.today().strftime("%Y%m%d")


def _stock_list_cache_file() -> str:
    return os.path.join(_cache_dir(), f"stock_list_{_today_key()}.pkl")


def _kline_cache_file(days: int) -> str:
    return os.path.join(_cache_dir(), f"kline_daily_{_today_key()}_{days}.pkl")


def _money_flow_cache_file() -> str:
    return os.path.join(_cache_dir(), f"money_flow_{_today_key()}_{cfg.FLOW_LOOKBACK_DAYS}.pkl")


def _hot_sector_cache_file() -> str:
    return os.path.join(_cache_dir(), f"hot_sector_{_today_key()}.pkl")


def _market_context_cache_file() -> str:
    return os.path.join(_cache_dir(), f"market_context_{_today_key()}.pkl")


def _log_filter_step(log: list, step_name: str, before_count: int, after_count: int):
    pass_count = after_count
    pass_rate = pass_count / before_count if before_count else 0
    log.append({
        "step_name": step_name,
        "before_count": int(before_count),
        "after_count": int(after_count),
        "pass_count": int(pass_count),
        "pass_rate": round(pass_rate, 4),
    })

# ---- HTTP 客户端 ----
try:
    from curl_cffi import requests as _http_lib
    _USE_CURL = True
except ImportError:
    import requests as _http_lib
    _USE_CURL = False


def _get(url: str, params: dict = None, timeout: int = 15, retries: int = None):
    """统一HTTP GET，自动选择TLS指纹伪装"""
    if retries is None:
        retries = cfg.MAX_RETRIES
    last_err = None
    for attempt in range(retries):
        try:
            kwargs = {"params": params, "timeout": timeout}
            if _USE_CURL:
                kwargs["impersonate"] = "chrome120"
            else:
                kwargs["headers"] = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                }
            resp = _http_lib.get(url, **kwargs)
            if resp.status_code == 200:
                return resp
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise last_err or Exception(f"请求失败: {url}")


def _make_secid(code: str) -> str:
    """东方财富 secid: 上海=1.xxxxxx，深圳=0.xxxxxx。"""
    market = "1" if str(code).startswith("6") else "0"
    return f"{market}.{code}"


# ============================================================
# 股票列表（新浪财经）
# ============================================================

def get_stock_list() -> pd.DataFrame:
    """
    获取全A股实时行情（新浪源），过滤ST/北交所/停牌
    字段: code, name, price, pct_change, volume, amount, turnover, high, low, open, pre_close
    """
    global LAST_STOCK_FILTER_LOG
    LAST_STOCK_FILTER_LOG = []

    cache_file = _stock_list_cache_file()
    if _cache_enabled() and not _force_refresh_cache() and os.path.exists(cache_file):
        try:
            df_cached = pd.read_pickle(cache_file)
            _log_filter_step(LAST_STOCK_FILTER_LOG, "初始股票池（当日缓存）", len(df_cached), len(df_cached))
            _log_filter_step(LAST_STOCK_FILTER_LOG, "最终股票池（当日缓存）", len(df_cached), len(df_cached))
            print(f"[缓存] 使用股票列表缓存: {cache_file} ({len(df_cached)} 只)")
            return df_cached.reset_index(drop=True)
        except Exception as e:
            print(f"[缓存] 股票列表缓存读取失败，改为重新获取: {e}")

    print("[数据] 获取A股股票列表（新浪源）...")

    url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    all_rows = []
    page = 1
    page_size = 80  # Sina API 单页最大约100条，80条最稳定

    while True:
        params = {
            "page": str(page),
            "num": str(page_size),
            "sort": "symbol",
            "asc": "1",
            "node": "hs_a",
            "symbol": "",
            "_s_r_a": "init",
        }
        try:
            resp = _get(url, params, timeout=30)
            data = json.loads(resp.text)
        except Exception as e:
            print(f"\n[警告] 股票列表第{page}页失败: {e}")
            break

        if not data or not isinstance(data, list):
            break

        for item in data:
            all_rows.append({
                "code": str(item.get("code", "")),
                "name": str(item.get("name", "")),
                "price": float(item.get("trade", 0) or 0),
                "pct_change": float(item.get("changepercent", 0) or 0),
                "change": float(item.get("pricechange", 0) or 0),
                "volume": float(item.get("volume", 0) or 0),
                "amount": float(item.get("amount", 0) or 0),
                "turnover": float(item.get("turnoverratio", 0) or 0),
                "high": float(item.get("high", 0) or 0),
                "low": float(item.get("low", 0) or 0),
                "open": float(item.get("open", 0) or 0),
                "pre_close": float(item.get("settlement", 0) or 0),
                "total_mcap": float(item.get("mktcap", 0) or 0),
                "circ_mcap": float(item.get("nmc", 0) or 0),
                "industry": str(item.get("industry", "") or item.get("hangye", "") or ""),
            })

        if len(data) < page_size:
            break
        page += 1
        # 每10页显示一次进度
        if page % 10 == 0:
            print(f"  已加载 {len(all_rows)} 只...")
        time.sleep(0.25)

    if not all_rows:
        raise RuntimeError("新浪股票列表为空，请检查网络")

    df = pd.DataFrame(all_rows)
    _log_filter_step(LAST_STOCK_FILTER_LOG, "初始股票池", len(df), len(df))

    # 过滤 ST / *ST / 退市
    if cfg.EXCLUDE_ST:
        before = len(df)
        df = df[~df["name"].str.contains("ST|退", na=False)]
        _log_filter_step(LAST_STOCK_FILTER_LOG, "去除 ST", before, len(df))

    # 过滤北交所（代码 8/4/9 开头）
    if cfg.EXCLUDE_BJ:
        before = len(df)
        df = df[~df["code"].str.match(r"^(8|4|9)\d{5}")]
        _log_filter_step(LAST_STOCK_FILTER_LOG, "去除北交所", before, len(df))

    # 过滤停牌
    before = len(df)
    df = df[df["volume"] > 0]
    df = df[df["price"] > 0]
    _log_filter_step(LAST_STOCK_FILTER_LOG, "去除停牌", before, len(df))

    # 过滤：只保留沪深主板
    if cfg.MAIN_BOARD_ONLY:
        # 上海主板: 600xxx, 601xxx, 603xxx, 605xxx
        # 深圳主板: 000xxx, 001xxx
        # 排除: 002/003中小板, 300/301创业板, 688科创板, 4/8/9北交所
        main_board = df["code"].str.match(r"^(600|601|603|605|000|001)\d{3}$")
        before = len(df)
        df = df[main_board]
        _log_filter_step(LAST_STOCK_FILTER_LOG, "保留沪深主板", before, len(df))
        print(f"[数据] 过滤非主板: {before} → {len(df)} 只")

    df = df.reset_index(drop=True)
    print(f"[数据] 获取到 {len(df)} 只有效股票")

    if _cache_enabled():
        try:
            df.to_pickle(cache_file)
            print(f"[缓存] 已保存股票列表缓存: {cache_file}")
        except Exception as e:
            print(f"[缓存] 股票列表缓存保存失败: {e}")

    return df


# ============================================================
# K线历史（新浪财经 — 稳定可靠）
# ============================================================

def _sina_symbol(code: str) -> str:
    """'000001' → 'sz000001', '600519' → 'sh600519'"""
    prefix = "sh" if code.startswith("6") else "sz"
    return f"{prefix}{code}"


def _fetch_one_kline(code: str, days: int = None) -> Optional[pd.DataFrame]:
    """获取单只股票日K线（新浪源），返回标准化DataFrame"""
    if days is None:
        days = cfg.HISTORY_DAYS

    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {
        "symbol": _sina_symbol(code),
        "scale": "240",       # 日K线
        "ma": "no",
        "datalen": str(days),
    }

    try:
        resp = _get(
            url,
            params,
            timeout=getattr(cfg, "MONEY_FLOW_API_TIMEOUT", 5),
            retries=getattr(cfg, "MONEY_FLOW_API_RETRIES", 1),
        )
        data = json.loads(resp.text)
    except Exception:
        return None

    if not data or not isinstance(data, list) or len(data) < 25:
        return None

    rows = []
    for item in data:
        try:
            rows.append({
                "date": str(item.get("day", "")),
                "open": float(item.get("open", 0) or 0),
                "close": float(item.get("close", 0) or 0),
                "high": float(item.get("high", 0) or 0),
                "low": float(item.get("low", 0) or 0),
                "volume": float(item.get("volume", 0) or 0),
            })
        except (ValueError, TypeError):
            continue

    if len(rows) < 25:
        return None

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    time.sleep(cfg.REQUEST_DELAY * 0.6)
    return df


def _load_kline_cache(symbols: list, days: int) -> tuple[dict, set]:
    if not _cache_enabled() or _force_refresh_cache():
        return {}, set()

    cache_file = _kline_cache_file(days)
    if not os.path.exists(cache_file):
        return {}, set()

    try:
        cached_df = pd.read_pickle(cache_file)
    except Exception as e:
        print(f"[缓存] K线缓存读取失败，改为重新获取: {e}")
        return {}, set()

    if cached_df.empty or "code" not in cached_df.columns:
        return {}, set()

    requested = {str(s) for s in symbols}
    cached_df["code"] = cached_df["code"].astype(str).str.zfill(6)
    cached_df = cached_df[cached_df["code"].isin(requested)].copy()
    if cached_df.empty:
        return {}, set()

    results = {}
    for code, g in cached_df.groupby("code"):
        hist = g.drop(columns=["code"]).sort_values("date").reset_index(drop=True)
        if len(hist) >= 25:
            results[code] = hist

    print(f"[缓存] K线命中: {len(results)}/{len(symbols)} ({cache_file})")
    return results, set(results.keys())


def _find_recent_kline_cache(days: int):
    pattern = os.path.join(_cache_dir(), f"kline_daily_*_{days}.pkl")
    today = datetime.datetime.strptime(_today_key(), "%Y%m%d").date()
    candidates = []
    for path in glob.glob(pattern):
        m = re.search(r"kline_daily_(\d{8})_", os.path.basename(path))
        if not m:
            continue
        try:
            cache_date = datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            continue
        age = (today - cache_date).days
        if 0 < age <= getattr(cfg, "MAX_INCREMENTAL_CACHE_AGE_DAYS", 5):
            candidates.append((cache_date, age, path))
    if not candidates:
        return None, None
    candidates.sort(reverse=True)
    _, age, path = candidates[0]
    return path, age


def _infer_latest_trade_date() -> str:
    today = datetime.date.today()
    if today.weekday() >= 5:
        today = today - datetime.timedelta(days=today.weekday() - 4)
    return today.strftime("%Y-%m-%d")


def _build_latest_kline_rows_from_spot(spot_df: pd.DataFrame) -> dict:
    if spot_df is None or spot_df.empty or "code" not in spot_df.columns:
        return {}

    date_str = _infer_latest_trade_date()
    rows = {}
    for _, row in spot_df.iterrows():
        code = str(row.get("code", "")).zfill(6)
        try:
            open_price = float(row.get("open", 0) or 0)
            close_price = float(row.get("price", 0) or row.get("close", 0) or 0)
            high_price = float(row.get("high", 0) or 0)
            low_price = float(row.get("low", 0) or 0)
            volume = float(row.get("volume", 0) or 0)
        except (TypeError, ValueError):
            continue
        if not code or min(open_price, close_price, high_price, low_price, volume) <= 0:
            continue
        rows[code] = {
            "date": date_str,
            "open": open_price,
            "close": close_price,
            "high": high_price,
            "low": low_price,
            "volume": volume,
        }
    return rows


def _load_incremental_kline_cache(symbols: list, days: int, spot_df: pd.DataFrame = None) -> tuple[dict, set]:
    if (
        not _cache_enabled()
        or _force_refresh_cache()
        or not getattr(cfg, "INCREMENTAL_KLINE_UPDATE", True)
        or spot_df is None
        or spot_df.empty
    ):
        return {}, set()

    cache_file, age = _find_recent_kline_cache(days)
    if not cache_file:
        return {}, set()

    latest_rows = _build_latest_kline_rows_from_spot(spot_df)
    if not latest_rows:
        return {}, set()

    try:
        cached_df = pd.read_pickle(cache_file)
    except Exception as e:
        print(f"[缓存] 旧K线缓存读取失败，改为全量获取: {e}")
        return {}, set()

    if cached_df.empty or "code" not in cached_df.columns:
        return {}, set()

    requested = {str(s).zfill(6) for s in symbols}
    cached_df["code"] = cached_df["code"].astype(str).str.zfill(6)
    cached_df = cached_df[cached_df["code"].isin(requested)].copy()
    if cached_df.empty:
        return {}, set()

    results = {}
    appended = 0
    for code, g in cached_df.groupby("code"):
        hist = g.drop(columns=["code"]).sort_values("date").reset_index(drop=True)
        latest_row = latest_rows.get(code)
        if latest_row:
            last_date = str(hist.iloc[-1]["date"]) if not hist.empty else ""
            if latest_row["date"] > last_date:
                hist = pd.concat([hist, pd.DataFrame([latest_row])], ignore_index=True)
                appended += 1
        hist = hist.tail(days).reset_index(drop=True)
        if len(hist) >= 25:
            results[code] = hist

    if results:
        print(
            f"[缓存] 使用旧K线增量更新: {cache_file} "
            f"(距今{age}天, 追加当日K线 {appended}/{len(results)} 只)"
        )
    return results, set(results.keys())


def _save_kline_cache(results: dict, days: int):
    if not _cache_enabled() or not results:
        return

    cache_file = _kline_cache_file(days)
    frames = []
    for code, df in results.items():
        if df is None or df.empty:
            continue
        d = df.copy()
        d.insert(0, "code", str(code).zfill(6))
        frames.append(d)

    if not frames:
        return

    try:
        out = pd.concat(frames, ignore_index=True)
        out.to_pickle(cache_file)
        print(f"[缓存] 已保存K线缓存: {cache_file} ({len(results)} 只)")
    except Exception as e:
        print(f"[缓存] K线缓存保存失败: {e}")


def get_stock_histories_batch(symbols: list, days: int = None,
                               max_workers: int = None,
                               spot_df: pd.DataFrame = None) -> dict:
    """并发批量获取K线"""
    if days is None:
        days = cfg.HISTORY_DAYS
    symbols = [str(s).zfill(6) for s in symbols]

    # Sina API 对并发敏感，默认低并发保证成功率；可在 config.py 中调整
    if max_workers is None:
        max_workers = cfg.MAX_WORKERS

    cached_results, cached_symbols = _load_kline_cache(symbols, days)
    if not cached_results:
        cached_results, cached_symbols = _load_incremental_kline_cache(symbols, days, spot_df)
        if cached_results:
            _save_kline_cache(cached_results, days)

    missing_symbols = [s for s in symbols if s not in cached_symbols]
    if not missing_symbols:
        print(f"[数据] K线全部来自缓存: {len(cached_results)}/{len(symbols)}")
        return cached_results

    total = len(missing_symbols)
    est = total * (cfg.REQUEST_DELAY * 0.6 + 0.3) / max_workers
    if cached_results:
        print(f"[数据] 仅补取缺失K线 {total} 只（缓存已命中 {len(cached_results)} 只）")
    print(f"[数据] 批量获取 {total} 只K线（{days}天, {max_workers}线程, ~{est:.0f}s, Sina源）...")

    fetched_results = {}
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut = {ex.submit(_fetch_one_kline, s, days): s for s in missing_symbols}
        for f in as_completed(fut):
            sym = fut[f]
            done += 1
            try:
                df = f.result()
                if df is not None:
                    fetched_results[sym] = df
            except Exception:
                pass
            if done % 500 == 0 or done == total:
                progress_bar(done, total, prefix="K线",
                             suffix=f"{done}/{total} ✓{len(fetched_results)}")

    results = {**cached_results, **fetched_results}
    print(f"\n[数据] K线完成: {len(results)}/{len(symbols)}")
    _save_kline_cache(results, days)
    return results


# ============================================================
# 资金流向（东方财富 push2his）
# ============================================================

def _fetch_one_fund_flow(code: str) -> Optional[dict]:
    """获取单只股票近期资金流向"""
    secid = _make_secid(code)
    start_date, end_date = get_recent_trading_dates(cfg.FLOW_LOOKBACK_DAYS + 15)

    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "klt": "101",
        "beg": start_date,
        "end": end_date,
    }

    try:
        resp = _get(
            url,
            params,
            timeout=getattr(cfg, "MONEY_FLOW_API_TIMEOUT", 5),
            retries=getattr(cfg, "MONEY_FLOW_API_RETRIES", 1),
        )
        data = resp.json()
        klines = data.get("data", {}).get("klines", [])
    except Exception:
        return None

    if not klines:
        return None

    # 格式: 日期,主力净流入,超大单净流入,大单净流入,中单净流入,小单净流入,...
    total_inflow = 0.0
    for line in klines[-cfg.FLOW_LOOKBACK_DAYS:]:
        parts = line.split(",")
        if len(parts) >= 2:
            total_inflow += float(parts[1])

    time.sleep(cfg.REQUEST_DELAY * 0.5)
    return {"symbol": code, "total_inflow": total_inflow}


def get_money_flow_batch(symbols: list, max_workers: int = None) -> dict:
    """并发批量获取资金流向，API失败时用价格*量估算"""
    symbols = [str(s).zfill(6) for s in symbols]
    total_requested = len(symbols)
    if total_requested == 0:
        return {}

    if max_workers is None:
        max_workers = max(1, int(getattr(cfg, "MONEY_FLOW_MAX_WORKERS", 6)))

    results = {}
    cache_file = _money_flow_cache_file()
    use_cache = _cache_enabled() and getattr(cfg, "USE_MONEY_FLOW_CACHE", True) and not _force_refresh_cache()
    if use_cache and os.path.exists(cache_file):
        try:
            cached = pd.read_pickle(cache_file)
            if isinstance(cached, dict):
                requested = set(symbols)
                results = {
                    str(code).zfill(6): data
                    for code, data in cached.items()
                    if str(code).zfill(6) in requested
                }
                print(f"[缓存] 资金流命中: {len(results)}/{total_requested} ({cache_file})")
        except Exception as e:
            print(f"[缓存] 资金流缓存读取失败，改为重新获取: {e}")

    symbols_to_fetch = [s for s in symbols if s not in results]
    total = len(symbols_to_fetch)
    if total == 0:
        print(f"[数据] 资金流全部来自当日缓存: {len(results)}/{total_requested}")
        return results

    if not getattr(cfg, "USE_MONEY_FLOW_API", True):
        print("[数据] 已关闭资金流API，改用K线量价估算")
        return results

    if results:
        print(f"[数据] 仅补取缺失资金流 {total} 只（缓存已命中 {len(results)} 只）")
    max_workers = min(max_workers, total)
    max_wait = float(getattr(cfg, "MONEY_FLOW_TOTAL_TIMEOUT", 45))
    print(
        f"[数据] 获取 {total} 只资金流向..."
        f"（{max_workers}线程, 单只超时{getattr(cfg, 'MONEY_FLOW_API_TIMEOUT', 5)}s, 最多等待{max_wait:.0f}s）"
    )

    fetched_results = {}
    done = 0
    progress_interval = max(1, int(getattr(cfg, "MONEY_FLOW_PROGRESS_INTERVAL", 10)))
    start_time = time.time()
    ex = ThreadPoolExecutor(max_workers=max_workers)
    fut = {ex.submit(_fetch_one_fund_flow, s): s for s in symbols_to_fetch}
    pending = set(fut.keys())
    timed_out = False
    try:
        while pending:
            remaining = max_wait - (time.time() - start_time)
            if remaining <= 0:
                timed_out = True
                break
            completed, pending = wait(
                pending,
                timeout=min(1.0, remaining),
                return_when=FIRST_COMPLETED,
            )
            if not completed:
                continue
            for f in completed:
                sym = fut[f]
                done += 1
                try:
                    d = f.result()
                    if d is not None:
                        fetched_results[sym] = d
                except Exception:
                    pass
                if done % progress_interval == 0 or done == total:
                    progress_bar(done, total, prefix="资金",
                                 suffix=f"{done}/{total} ✓{len(fetched_results)}")
        if pending:
            for f in pending:
                f.cancel()
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

    if timed_out:
        print(f"\n[警告] 资金流API等待超过 {max_wait:.0f}s，剩余 {len(pending)} 只改用K线估算")
    elif done and done < total:
        progress_bar(done, total, prefix="资金",
                     suffix=f"{done}/{total} ✓{len(fetched_results)}")

    results.update(fetched_results)
    print(f"\n[数据] 资金流向API: {len(fetched_results)}/{total} | 合计 {len(results)}/{total_requested}")

    if _cache_enabled() and getattr(cfg, "USE_MONEY_FLOW_CACHE", True):
        try:
            existing = {}
            if os.path.exists(cache_file) and not _force_refresh_cache():
                cached = pd.read_pickle(cache_file)
                if isinstance(cached, dict):
                    existing = {str(code).zfill(6): data for code, data in cached.items()}
            existing.update(results)
            pd.to_pickle(existing, cache_file)
            print(f"[缓存] 已保存资金流缓存: {cache_file} ({len(existing)} 只)")
        except Exception as e:
            print(f"[缓存] 资金流缓存保存失败: {e}")

    # 对没有API数据的股票，用价格涨跌*成交量估算
    if len(results) < len(symbols):
        print("[数据] 对剩余股票使用量价估算资金流向...")
    return results


def estimate_money_flow_from_kline(kline_data: dict) -> dict:
    """
    当API资金流向不可用时，基于K线量价关系估算主力资金方向
    原理：收盘>开盘且放量 → 净流入；收盘<开盘且放量 → 净流出
    返回 {symbol: {"total_inflow": float}}
    """
    estimates = {}
    for sym, df in kline_data.items():
        if len(df) < cfg.FLOW_LOOKBACK_DAYS:
            continue
        recent = df.tail(cfg.FLOW_LOOKBACK_DAYS)
        total_estimate = 0.0
        for _, row in recent.iterrows():
            o, c, v = row["open"], row["close"], row["volume"]
            if c > o:
                # 阳线：估算净流入
                total_estimate += v * (c - o) / o * c
            else:
                # 阴线：估算净流出
                total_estimate += v * (c - o) / o * c
        estimates[sym] = {"symbol": sym, "total_inflow": total_estimate}
    return estimates


# ============================================================
# 行业板块（通过新浪股票分类构建映射）
# ============================================================

def get_industry_performance(spot_df: pd.DataFrame) -> pd.DataFrame:
    """
    通过股票涨跌幅聚合行业表现
    由于直接获取板块排行的API在当前环境受限，
    改为从股票数据的行业分类自行聚合计算
    """
    if spot_df is None or spot_df.empty or "industry" not in spot_df.columns:
        return pd.DataFrame()

    df = spot_df.copy()
    df["industry"] = df["industry"].fillna("").astype(str).str.strip()
    df = df[(df["industry"] != "") & df["pct_change"].notna()]
    if df.empty:
        return pd.DataFrame()

    grouped = (
        df.groupby("industry")
        .agg(
            avg_pct_change=("pct_change", "mean"),
            median_pct_change=("pct_change", "median"),
            stock_count=("code", "count"),
        )
        .reset_index()
    )
    grouped = grouped[grouped["stock_count"] >= 3]
    return grouped.sort_values("avg_pct_change", ascending=False).reset_index(drop=True)


def build_sector_score_map(spot_df: pd.DataFrame = None) -> dict:
    """
    基于股票行业当日平均涨跌幅构建评分。
    返回 {code: score}；如果数据源没有行业字段，则返回空映射。
    """
    if spot_df is None or spot_df.empty or "industry" not in spot_df.columns:
        return {}

    industry_perf = get_industry_performance(spot_df)
    if industry_perf.empty:
        return {}

    total = len(industry_perf)
    industry_scores = {}
    for rank, row in industry_perf.iterrows():
        percentile = 1 - rank / max(total, 1)
        if percentile >= 0.97:
            score = cfg.SECTOR_RANK_TOP3_SCORE
        elif percentile >= 0.90:
            score = cfg.SECTOR_RANK_TOP10_SCORE
        elif percentile >= 0.80:
            score = cfg.SECTOR_RANK_TOP20_SCORE
        else:
            score = cfg.SECTOR_RANK_OTHER_SCORE
        industry_scores[row["industry"]] = float(score)

    scores = {}
    for _, row in spot_df.iterrows():
        industry = str(row.get("industry", "") or "").strip()
        if industry in industry_scores:
            scores[str(row["code"])] = industry_scores[industry]
    return scores


def _normalize_series(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0)
    v_min = float(values.min()) if len(values) else 0
    v_max = float(values.max()) if len(values) else 0
    if v_max <= v_min:
        return pd.Series([0.5] * len(values), index=values.index)
    return (values - v_min) / (v_max - v_min)


def get_hot_sector_boards(limit: int = None) -> pd.DataFrame:
    """
    获取东方财富行业板块实时热度榜。

    返回字段：
    sector_rank, sector_code, sector_name, heat_score, pct_change, amount,
    turnover, up_count, down_count, up_ratio, leader_name, leader_code,
    leader_pct_change, quant_note
    """
    if limit is None:
        limit = getattr(cfg, "HOT_SECTOR_TOP_N", 8)

    cache_file = _hot_sector_cache_file()
    if _cache_enabled() and not _force_refresh_cache() and os.path.exists(cache_file):
        try:
            cached = pd.read_pickle(cache_file)
            if not cached.empty:
                print(f"[缓存] 使用热门板块缓存: {cache_file} ({len(cached)} 个)")
                return cached.head(limit).copy()
        except Exception as e:
            print(f"[缓存] 热门板块缓存读取失败，改为重新获取: {e}")

    if not getattr(cfg, "USE_HOT_SECTOR_API", True):
        return pd.DataFrame()

    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": str(max(limit * 3, 30)),
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        # m:90+t:2 为东方财富行业板块列表
        "fs": "m:90+t:2",
        "fields": "f12,f14,f3,f6,f8,f104,f105,f106,f128,f136,f140",
    }
    try:
        resp = _get(url, params=params, timeout=getattr(cfg, "HOT_SECTOR_API_TIMEOUT", 8), retries=1)
        payload = resp.json()
        diff = (payload.get("data") or {}).get("diff") or []
    except Exception as e:
        print(f"[警告] 热门板块获取失败: {e}")
        return pd.DataFrame()

    rows = []
    for item in diff:
        up_count = float(item.get("f104") or 0)
        down_count = float(item.get("f105") or 0)
        flat_count = float(item.get("f106") or 0)
        total_count = up_count + down_count + flat_count
        rows.append({
            "sector_code": str(item.get("f12", "")),
            "sector_name": str(item.get("f14", "")),
            "pct_change": float(item.get("f3") or 0),
            "amount": float(item.get("f6") or 0),
            "turnover": float(item.get("f8") or 0),
            "up_count": int(up_count),
            "down_count": int(down_count),
            "flat_count": int(flat_count),
            "stock_count": int(total_count),
            "up_ratio": up_count / total_count if total_count else 0,
            "leader_name": str(item.get("f128", "") or ""),
            "leader_code": str(item.get("f140", "") or ""),
            "leader_pct_change": float(item.get("f136") or 0),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    pct_score = _normalize_series(df["pct_change"])
    amount_score = _normalize_series(df["amount"])
    turnover_score = _normalize_series(df["turnover"])
    leader_score = _normalize_series(df["leader_pct_change"])
    up_ratio = pd.to_numeric(df["up_ratio"], errors="coerce").fillna(0).clip(0, 1)
    df["heat_score"] = (
        pct_score * 45
        + up_ratio * 25
        + amount_score * 15
        + leader_score * 10
        + turnover_score * 5
    ).round(2)
    df = df.sort_values(["heat_score", "pct_change", "amount"], ascending=[False, False, False]).reset_index(drop=True)
    df.insert(0, "sector_rank", range(1, len(df) + 1))
    df["quant_note"] = df.apply(
        lambda r: (
            f"热度{r['heat_score']:.1f} = 涨幅{r['pct_change']:.2f}%、"
            f"上涨占比{r['up_ratio'] * 100:.1f}%、成交额{r['amount'] / 1e8:.1f}亿、"
            f"领涨股{r['leader_name']} {r['leader_pct_change']:.2f}%"
        ),
        axis=1,
    )

    if _cache_enabled():
        try:
            df.to_pickle(cache_file)
            print(f"[缓存] 已保存热门板块缓存: {cache_file}")
        except Exception as e:
            print(f"[缓存] 热门板块缓存保存失败: {e}")

    return df.head(limit).copy()


# ============================================================
# 市场上下文：大事件 / 融资融券 / 龙虎榜
# ============================================================

POSITIVE_EVENT_KEYWORDS = [
    "回购", "增持", "中标", "重大合同", "签订合同", "预增", "业绩增长",
    "扭亏", "股权激励", "重组", "并购", "定增获批", "项目投产",
]
NEGATIVE_EVENT_KEYWORDS = [
    "减持", "立案", "处罚", "问询函", "监管函", "诉讼", "仲裁",
    "预减", "亏损", "业绩下降", "终止", "解禁", "质押", "退市",
]
EVENT_RISK_KEYWORDS = ["异动", "异常波动", "澄清", "停牌", "风险提示"]


def _em_sec_code(code: str) -> str:
    code = str(code).zfill(6)
    suffix = "SH" if code.startswith("6") else "SZ"
    return f"{code}.{suffix}"


def _plain_stock_code(code: str) -> str:
    return str(code).zfill(6)


def _date_yyyy_mm_dd(days: int) -> tuple[str, str]:
    end = datetime.date.today()
    start = end - datetime.timedelta(days=max(days, 1) * 2)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _date_yyyymmdd(days: int) -> tuple[str, str]:
    start, end = get_recent_trading_dates(max(days + 10, 15))
    return start, end


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def _score_event_titles(titles: list[str]) -> tuple[float, str]:
    positive = 0
    negative = 0
    risk = 0
    for title in titles:
        positive += sum(1 for kw in POSITIVE_EVENT_KEYWORDS if kw in title)
        negative += sum(1 for kw in NEGATIVE_EVENT_KEYWORDS if kw in title)
        risk += sum(1 for kw in EVENT_RISK_KEYWORDS if kw in title)
    score = _clip(positive * 1.5 - negative * 2.0 - risk * 0.8, 3.0)
    if not titles:
        note = "近期无重大公告"
    elif score > 0:
        note = f"公告偏正面({positive}个积极关键词)"
    elif score < 0:
        note = f"公告偏风险({negative}个负面关键词, {risk}个异动/风险词)"
    else:
        note = "近期公告中性"
    return round(score, 2), note


def _fetch_recent_events(code: str) -> dict:
    if not getattr(cfg, "USE_EVENT_API", True):
        return {"score": 0.0, "count": 0, "titles": [], "note": "公告接口关闭"}

    begin, end = _date_yyyy_mm_dd(getattr(cfg, "EVENT_LOOKBACK_DAYS", 14))
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
    params = {
        "sr": "-1",
        "page_size": "30",
        "page_index": "1",
        "ann_type": "A",
        "client_source": "web",
        "stock_list": _plain_stock_code(code),
        "f_node": "0",
        "s_node": "0",
        "begin_time": begin,
        "end_time": end,
    }
    try:
        payload = _get(
            url,
            params=params,
            timeout=getattr(cfg, "MARKET_CONTEXT_API_TIMEOUT", 6),
            retries=getattr(cfg, "MARKET_CONTEXT_API_RETRIES", 1),
        ).json()
        items = (payload.get("data") or {}).get("list") or []
    except Exception:
        return {"score": 0.0, "count": 0, "titles": [], "note": "公告数据获取失败"}

    titles = []
    for item in items:
        title = str(item.get("title") or item.get("announcementTitle") or "").strip()
        if title:
            titles.append(title)
    score, note = _score_event_titles(titles)
    return {
        "score": score,
        "count": len(titles),
        "titles": titles[:3],
        "note": note,
    }


def _fetch_margin_data(code: str) -> dict:
    if not getattr(cfg, "USE_MARGIN_API", True):
        return {"score": 0.0, "change_pct": 0.0, "net_buy": 0.0, "note": "两融接口关闭"}

    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "DATE",
        "sortTypes": "-1",
        "pageSize": str(max(getattr(cfg, "MARGIN_LOOKBACK_DAYS", 5), 5)),
        "pageNumber": "1",
        "reportName": "RPTA_WEB_RZRQ_GGMX",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f'(SCODE="{str(code).zfill(6)}")',
    }
    try:
        payload = _get(
            url,
            params=params,
            timeout=getattr(cfg, "MARKET_CONTEXT_API_TIMEOUT", 6),
            retries=getattr(cfg, "MARKET_CONTEXT_API_RETRIES", 1),
        ).json()
        rows = (payload.get("result") or {}).get("data") or []
    except Exception:
        return {"score": 0.0, "change_pct": 0.0, "net_buy": 0.0, "note": "两融数据获取失败"}

    if not rows:
        return {"score": 0.0, "change_pct": 0.0, "net_buy": 0.0, "note": "无两融数据"}

    latest = rows[0]
    oldest = rows[-1]
    latest_balance = _safe_float(latest.get("RZYE") or latest.get("FIN_BALANCE"))
    oldest_balance = _safe_float(oldest.get("RZYE") or oldest.get("FIN_BALANCE"))
    change_pct = ((latest_balance - oldest_balance) / oldest_balance * 100) if oldest_balance > 0 else 0.0
    buy_amt = _safe_float(latest.get("RZMRE") or latest.get("FIN_BUY_AMT"))
    repay_amt = _safe_float(latest.get("RZCHE") or latest.get("FIN_REPAY_AMT"))
    net_buy = _safe_float(latest.get("RZJME"), buy_amt - repay_amt)

    score = 0.0
    if change_pct >= 5:
        score += 2.0
    elif change_pct >= 1:
        score += 1.0
    elif change_pct <= -5:
        score -= 2.0
    elif change_pct <= -1:
        score -= 1.0
    if net_buy > 0:
        score += 0.8
    elif net_buy < 0:
        score -= 0.8
    score = round(_clip(score, 3.0), 2)

    if score > 0:
        note = f"融资余额上升{change_pct:.1f}%"
    elif score < 0:
        note = f"融资余额下降{change_pct:.1f}%"
    else:
        note = "两融变化中性"
    return {
        "score": score,
        "change_pct": round(change_pct, 2),
        "net_buy": round(net_buy, 2),
        "note": note,
    }


def _fetch_lhb_data(code: str) -> dict:
    if not getattr(cfg, "USE_LHB_API", True):
        return {"score": 0.0, "count": 0, "net_buy": 0.0, "note": "龙虎榜接口关闭"}

    begin, end = _date_yyyy_mm_dd(getattr(cfg, "LHB_LOOKBACK_DAYS", 10))
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "TRADE_DATE",
        "sortTypes": "-1",
        "pageSize": "20",
        "pageNumber": "1",
        "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": (
            f'(SECURITY_CODE="{str(code).zfill(6)}")'
            f'(TRADE_DATE>="{begin}")(TRADE_DATE<="{end}")'
        ),
    }
    try:
        payload = _get(
            url,
            params=params,
            timeout=getattr(cfg, "MARKET_CONTEXT_API_TIMEOUT", 6),
            retries=getattr(cfg, "MARKET_CONTEXT_API_RETRIES", 1),
        ).json()
        rows = (payload.get("result") or {}).get("data") or []
    except Exception:
        return {"score": 0.0, "count": 0, "net_buy": 0.0, "note": "龙虎榜数据获取失败"}

    if not rows:
        return {"score": 0.0, "count": 0, "net_buy": 0.0, "note": "近期未上龙虎榜"}

    net_buy = 0.0
    reasons = []
    for row in rows:
        net_buy += _safe_float(
            row.get("BILLBOARD_NET_AMT")
            or row.get("BILLBOARD_NET_BUY_AMT")
            or row.get("NET_BUY_AMT")
        )
        reason = str(row.get("EXPLAIN") or row.get("EXPLANATION") or "").strip()
        if reason:
            reasons.append(reason)

    score = 0.8
    if net_buy > 0:
        score += 1.7
    elif net_buy < 0:
        score -= 2.2
    if len(rows) >= 2:
        score += 0.5 if net_buy > 0 else -0.5
    score = round(_clip(score, 3.0), 2)
    if net_buy > 0:
        note = f"龙虎榜{len(rows)}次，净买入{net_buy / 1e8:.2f}亿"
    elif net_buy < 0:
        note = f"龙虎榜{len(rows)}次，净卖出{abs(net_buy) / 1e8:.2f}亿"
    else:
        note = f"龙虎榜{len(rows)}次，净额中性"
    if reasons:
        note += f"；{reasons[0][:24]}"
    return {
        "score": score,
        "count": len(rows),
        "net_buy": round(net_buy, 2),
        "note": note,
    }


def _neutral_market_context(code: str, note: str = "上下文数据中性") -> dict:
    return {
        "symbol": str(code).zfill(6),
        "context_score": 0.0,
        "event_score": 0.0,
        "event_count": 0,
        "event_titles": "",
        "event_note": note,
        "margin_score": 0.0,
        "margin_balance_change_pct": 0.0,
        "margin_net_buy": 0.0,
        "margin_note": note,
        "lhb_score": 0.0,
        "lhb_count": 0,
        "lhb_net_buy": 0.0,
        "lhb_note": note,
        "context_note": note,
    }


def _fetch_one_market_context(code: str) -> dict:
    code = str(code).zfill(6)
    event = _fetch_recent_events(code)
    margin = _fetch_margin_data(code)
    lhb = _fetch_lhb_data(code)
    total = round(_clip(
        float(event.get("score", 0)) + float(margin.get("score", 0)) + float(lhb.get("score", 0)),
        float(getattr(cfg, "MARKET_CONTEXT_SCORE_LIMIT", 8)),
    ), 2)
    notes = [
        str(event.get("note", "")),
        str(margin.get("note", "")),
        str(lhb.get("note", "")),
    ]
    return {
        "symbol": code,
        "context_score": total,
        "event_score": float(event.get("score", 0)),
        "event_count": int(event.get("count", 0) or 0),
        "event_titles": "；".join(event.get("titles", []) or []),
        "event_note": str(event.get("note", "")),
        "margin_score": float(margin.get("score", 0)),
        "margin_balance_change_pct": float(margin.get("change_pct", 0)),
        "margin_net_buy": float(margin.get("net_buy", 0)),
        "margin_note": str(margin.get("note", "")),
        "lhb_score": float(lhb.get("score", 0)),
        "lhb_count": int(lhb.get("count", 0) or 0),
        "lhb_net_buy": float(lhb.get("net_buy", 0)),
        "lhb_note": str(lhb.get("note", "")),
        "context_note": "；".join(n for n in notes if n),
    }


def get_market_context_batch(symbols: list, max_workers: int = None) -> dict:
    """批量获取大事件、融资融券和龙虎榜上下文评分。"""
    symbols = [str(s).zfill(6) for s in symbols]
    if not symbols:
        return {}
    if not getattr(cfg, "USE_MARKET_CONTEXT_API", True):
        return {s: _neutral_market_context(s, "上下文接口关闭") for s in symbols}

    if max_workers is None:
        max_workers = max(1, int(getattr(cfg, "MARKET_CONTEXT_MAX_WORKERS", 4)))

    results = {}
    cache_file = _market_context_cache_file()
    use_cache = _cache_enabled() and getattr(cfg, "USE_MARKET_CONTEXT_CACHE", True) and not _force_refresh_cache()
    if use_cache and os.path.exists(cache_file):
        try:
            cached = pd.read_pickle(cache_file)
            if isinstance(cached, dict):
                requested = set(symbols)
                results = {
                    str(code).zfill(6): data
                    for code, data in cached.items()
                    if str(code).zfill(6) in requested
                }
                print(f"[缓存] 市场上下文命中: {len(results)}/{len(symbols)} ({cache_file})")
        except Exception as e:
            print(f"[缓存] 市场上下文缓存读取失败，改为重新获取: {e}")

    symbols_to_fetch = [s for s in symbols if s not in results]
    if not symbols_to_fetch:
        return results

    total = len(symbols_to_fetch)
    max_workers = min(max_workers, total)
    max_wait = float(getattr(cfg, "MARKET_CONTEXT_TOTAL_TIMEOUT", 35))
    print(f"[数据] 获取 {total} 只市场上下文（大事件/两融/龙虎榜）...")

    fetched = {}
    start_time = time.time()
    ex = ThreadPoolExecutor(max_workers=max_workers)
    fut = {ex.submit(_fetch_one_market_context, s): s for s in symbols_to_fetch}
    pending = set(fut.keys())
    try:
        while pending:
            remaining = max_wait - (time.time() - start_time)
            if remaining <= 0:
                break
            completed, pending = wait(
                pending,
                timeout=min(1.0, remaining),
                return_when=FIRST_COMPLETED,
            )
            for f in completed:
                sym = fut[f]
                try:
                    fetched[sym] = f.result()
                except Exception:
                    fetched[sym] = _neutral_market_context(sym, "上下文数据获取失败")
        for f in pending:
            sym = fut[f]
            f.cancel()
            fetched[sym] = _neutral_market_context(sym, "上下文数据超时")
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

    results.update(fetched)
    if _cache_enabled() and getattr(cfg, "USE_MARKET_CONTEXT_CACHE", True):
        try:
            existing = {}
            if os.path.exists(cache_file) and not _force_refresh_cache():
                cached = pd.read_pickle(cache_file)
                if isinstance(cached, dict):
                    existing = {str(code).zfill(6): data for code, data in cached.items()}
            existing.update(results)
            pd.to_pickle(existing, cache_file)
            print(f"[缓存] 已保存市场上下文缓存: {cache_file} ({len(existing)} 只)")
        except Exception as e:
            print(f"[缓存] 市场上下文缓存保存失败: {e}")

    return results


def load_benchmark_data(csv_path: str = None, benchmark_code: str = None) -> pd.DataFrame:
    """
    读取本地基准日线CSV。
    支持字段 trade_date/date、benchmark_code、close；自动计算 daily_return/cumulative_return。
    """
    if csv_path is None:
        csv_path = cfg.BENCHMARK_CSV
    if benchmark_code is None:
        benchmark_code = cfg.BENCHMARK_CODE
    if not csv_path or not os.path.exists(csv_path):
        return pd.DataFrame(columns=[
            "trade_date", "benchmark_code", "close", "daily_return", "cumulative_return"
        ])

    df = pd.read_csv(csv_path)
    if "trade_date" not in df.columns and "date" in df.columns:
        df = df.rename(columns={"date": "trade_date"})
    if "trade_date" not in df.columns or "close" not in df.columns:
        raise ValueError("benchmark csv must include trade_date/date and close columns")
    if "benchmark_code" not in df.columns:
        df["benchmark_code"] = benchmark_code
    if benchmark_code and "benchmark_code" in df.columns:
        filtered = df[df["benchmark_code"].astype(str) == str(benchmark_code)]
        if not filtered.empty:
            df = filtered

    df = df.sort_values("trade_date").copy()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    if "daily_return" not in df.columns:
        df["daily_return"] = df["close"].pct_change().fillna(0)
    else:
        df["daily_return"] = pd.to_numeric(df["daily_return"], errors="coerce").fillna(0)
        if df["daily_return"].abs().max() > 2:
            df["daily_return"] = df["daily_return"] / 100.0
    if "cumulative_return" not in df.columns:
        df["cumulative_return"] = (1 + df["daily_return"]).cumprod() - 1
    else:
        df["cumulative_return"] = pd.to_numeric(df["cumulative_return"], errors="coerce").fillna(0)
        if df["cumulative_return"].abs().max() > 2:
            df["cumulative_return"] = df["cumulative_return"] / 100.0

    return df[["trade_date", "benchmark_code", "close", "daily_return", "cumulative_return"]]
