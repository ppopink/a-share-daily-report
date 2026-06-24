"""
技术指标计算模块
- MA（移动平均线）3, 5, 21
- DMI（趋向指标）7, 6 — +DI > -DI 且 ADX > 25 为必选条件
- EXPMA（指数移动平均线）7, 21 — 金叉为必选条件
- MACD（指数平滑异同移动平均线）6, 13, 5 — 进入零轴上方区域后的二次金叉为必选条件
- 成交量 — 当日 > 前5日均量 × 1.3
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional

import config as cfg


def _num(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value) -> bool:
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return bool(value)


def get_mode_params(mode: str = None) -> dict:
    """返回不同筛选模式的技术阈值和硬条件设置。"""
    mode = mode or cfg.SCREEN_MODE
    if mode == "strict":
        return {
            "adx_threshold": 25,
            "vol_mult": 1.3,
            "trend_above_days": cfg.TREND_STRICT_ABOVE_DAYS,
            "trend_slope10_pct": cfg.TREND_STRICT_SLOPE10_PCT,
            "trend_slope20_pct": cfg.TREND_STRICT_SLOPE20_PCT,
            "trend_max_close_ma20_ratio": cfg.TREND_STRICT_MAX_CLOSE_MA20_RATIO,
            "require_trend_quality": True,
            "require_expma_recent_cross": True,
            "require_macd_second_recent": True,
            "require_dif_dea_cross": True,
        }
    if mode == "loose":
        return {
            "adx_threshold": 20,
            "vol_mult": 1.1,
            "trend_above_days": cfg.TREND_LOOSE_ABOVE_DAYS,
            "trend_slope10_pct": cfg.TREND_LOOSE_SLOPE10_PCT,
            "trend_slope20_pct": cfg.TREND_LOOSE_SLOPE20_PCT,
            "trend_max_close_ma20_ratio": cfg.TREND_LOOSE_MAX_CLOSE_MA20_RATIO,
            "require_trend_quality": False,
            "require_expma_recent_cross": False,
            "require_macd_second_recent": False,
            "require_dif_dea_cross": False,
        }
    return {
        "adx_threshold": 22,
        "vol_mult": 1.2,
        "trend_above_days": cfg.TREND_NORMAL_ABOVE_DAYS,
        "trend_slope10_pct": cfg.TREND_NORMAL_SLOPE10_PCT,
        "trend_slope20_pct": cfg.TREND_NORMAL_SLOPE20_PCT,
        "trend_max_close_ma20_ratio": cfg.TREND_NORMAL_MAX_CLOSE_MA20_RATIO,
        "require_trend_quality": False,
        "require_expma_recent_cross": False,
        "require_macd_second_recent": False,
        "require_dif_dea_cross": True,
    }


def _macd_cross_details(df: pd.DataFrame) -> dict:
    if not {"MACD_DIFF", "MACD_DEA"}.issubset(df.columns) or len(df) < 2:
        return {
            "macd_golden_cross_above_zero": False,
            "macd_second_gc_above_zero": False,
            "macd_second_gc_recent": False,
            "macd_cross_count_in_zone": 0,
            "days_since_macd_second_gc": None,
        }

    diff = df["MACD_DIFF"].values
    dea = df["MACD_DEA"].values
    n = len(df)
    zone_start = None
    for i in range(1, n):
        was_above = diff[i - 1] > 0 and dea[i - 1] > 0
        is_above = diff[i] > 0 and dea[i] > 0
        if is_above and not was_above:
            zone_start = i

    crosses = []
    if zone_start is not None:
        for i in range(max(1, zone_start), n):
            if diff[i - 1] <= dea[i - 1] and diff[i] > dea[i] and diff[i] > 0 and dea[i] > 0:
                crosses.append(i)

    second_idx = crosses[-1] if len(crosses) >= 2 else None
    days_since = n - 1 - second_idx if second_idx is not None else None
    return {
        "macd_golden_cross_above_zero": bool(crosses and crosses[-1] == n - 1),
        "macd_second_gc_above_zero": second_idx is not None,
        "macd_second_gc_recent": second_idx is not None and days_since <= cfg.MACD_CROSS_DAYS,
        "macd_cross_count_in_zone": len(crosses),
        "days_since_macd_second_gc": days_since,
    }


def _expma_cross_recent(df: pd.DataFrame) -> bool:
    if not {"EXPMA7", "EXPMA21"}.issubset(df.columns) or len(df) < 2:
        return False
    expma7 = df["EXPMA7"].values
    expma21 = df["EXPMA21"].values
    last_cross = None
    for i in range(1, len(df)):
        if expma7[i - 1] <= expma21[i - 1] and expma7[i] > expma21[i]:
            last_cross = i
    return last_cross is not None and (len(df) - 1 - last_cross) <= cfg.EXPMA_CROSS_DAYS


def evaluate_technical_conditions(df: pd.DataFrame, mode: str = None) -> dict:
    """拆分所有技术条件，供筛选、诊断和失败原因复用。"""
    mode = mode or cfg.SCREEN_MODE
    params = get_mode_params(mode)
    latest = df.iloc[-1] if len(df) else pd.Series(dtype=float)
    close = _num(latest.get("close", 0))
    ma3 = _num(latest.get("MA3", 0))
    ma5 = _num(latest.get("MA5", 0))
    ma21 = _num(latest.get("MA21", 0))
    pdi = _num(latest.get("plus_di", 0))
    mdi = _num(latest.get("minus_di", 0))
    adx = _num(latest.get("ADX", 0))
    vol_ratio = _num(latest.get("VOL_RATIO", 0))
    expma7 = _num(latest.get("EXPMA7", 0))
    expma21 = _num(latest.get("EXPMA21", 0))
    dif = _num(latest.get("MACD_DIFF", 0))
    dea = _num(latest.get("MACD_DEA", 0))
    current_above_ma20 = _bool(latest.get("CURRENT_ABOVE_MA20", False))
    above_ma20_days_20 = int(_num(latest.get("ABOVE_MA20_DAYS_20", 0)))
    ma20_slope_10_pct = _num(latest.get("MA20_SLOPE_10_PCT", 0))
    ma20_slope_20_pct = _num(latest.get("MA20_SLOPE_20_PCT", 0))
    close_ma20_ratio = _num(latest.get("CLOSE_MA20_RATIO", 0))

    macd = _macd_cross_details(df)
    checks = {
        "ma_stack": close > ma3 > ma5 > ma21,
        "current_above_ma20": current_above_ma20,
        "above_ma20_days_ok": above_ma20_days_20 >= params["trend_above_days"],
        "ma20_slope_ok": (
            ma20_slope_10_pct >= params["trend_slope10_pct"]
            or ma20_slope_20_pct >= params["trend_slope20_pct"]
        ),
        "ma20_not_overheated": 0 < close_ma20_ratio <= params["trend_max_close_ma20_ratio"],
        "pdi_gt_mdi": pdi > mdi,
        "adx_enough": adx > params["adx_threshold"],
        "volume_enough": vol_ratio >= params["vol_mult"],
        "expma_bull": expma7 > expma21,
        "expma_recent_cross": _expma_cross_recent(df),
        "dif_dea_above_zero": dif > 0 and dea > 0,
        "dif_gt_dea": dif > dea,
        **macd,
    }
    checks["trend_quality_ok"] = (
        checks["current_above_ma20"]
        and checks["above_ma20_days_ok"]
        and checks["ma20_slope_ok"]
        and checks["ma20_not_overheated"]
    )

    hard = [
        checks["ma_stack"],
        checks["pdi_gt_mdi"],
        checks["adx_enough"],
        checks["volume_enough"],
        checks["expma_bull"],
        checks["dif_dea_above_zero"],
    ]
    if mode in ("strict", "normal"):
        hard.append(checks["dif_gt_dea"])
    if params["require_trend_quality"]:
        hard.append(checks["trend_quality_ok"])
    if params["require_expma_recent_cross"]:
        hard.append(checks["expma_recent_cross"])
    if params["require_macd_second_recent"]:
        hard.append(checks["macd_second_gc_recent"])

    checks["technical_pass"] = all(hard)
    checks["mode"] = mode
    checks["adx_threshold"] = params["adx_threshold"]
    checks["vol_mult"] = params["vol_mult"]
    checks["trend_above_days_threshold"] = params["trend_above_days"]
    checks["trend_slope10_threshold"] = params["trend_slope10_pct"]
    checks["trend_slope20_threshold"] = params["trend_slope20_pct"]
    checks["trend_max_close_ma20_ratio"] = params["trend_max_close_ma20_ratio"]
    return checks


# ============================================================
# MA — 移动平均线
# ============================================================

def calc_ma(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算 MA3, MA5, MA21，以及趋势持续性使用的 MA20
    """
    periods = sorted(set(list(cfg.MA_PERIODS) + [cfg.TREND_MA_PERIOD]))
    for period in periods:
        df[f"MA{period}"] = df["close"].rolling(window=period).mean()
    return df


def calc_trend_quality(df: pd.DataFrame) -> pd.DataFrame:
    """计算中期趋势持续性指标。"""
    ma_col = f"MA{cfg.TREND_MA_PERIOD}"
    if ma_col not in df.columns:
        df[ma_col] = df["close"].rolling(window=cfg.TREND_MA_PERIOD).mean()
    df["CURRENT_ABOVE_MA20"] = df["close"] > df[ma_col]
    df["ABOVE_MA20_DAYS_20"] = (
        df["CURRENT_ABOVE_MA20"]
        .astype(float)
        .rolling(window=cfg.TREND_LOOKBACK_DAYS)
        .sum()
    )
    df["MA20_SLOPE_10_PCT"] = (df[ma_col] / df[ma_col].shift(10) - 1) * 100
    df["MA20_SLOPE_20_PCT"] = (df[ma_col] / df[ma_col].shift(20) - 1) * 100
    df["CLOSE_MA20_RATIO"] = df["close"] / df[ma_col]
    return df


def check_trend_quality(df: pd.DataFrame, mode: str = None) -> Tuple[bool, float]:
    """检查并评分趋势持续性：站上MA20天数 + MA20斜率 + 不追高。"""
    if len(df) < cfg.TREND_MA_PERIOD + cfg.TREND_LOOKBACK_DAYS:
        return False, 0.0
    params = get_mode_params(mode)
    latest = df.iloc[-1]
    above_days = _num(latest.get("ABOVE_MA20_DAYS_20", 0))
    slope10 = _num(latest.get("MA20_SLOPE_10_PCT", 0))
    slope20 = _num(latest.get("MA20_SLOPE_20_PCT", 0))
    ratio = _num(latest.get("CLOSE_MA20_RATIO", 0))
    current_above = _bool(latest.get("CURRENT_ABOVE_MA20", False))

    persistence_ok = above_days >= params["trend_above_days"]
    slope_ok = slope10 >= params["trend_slope10_pct"] or slope20 >= params["trend_slope20_pct"]
    distance_ok = 0 < ratio <= params["trend_max_close_ma20_ratio"]
    ok = current_above and persistence_ok and slope_ok and distance_ok

    persistence_score = min(1.0, max(0.0, above_days / cfg.TREND_LOOKBACK_DAYS))
    slope_score = max(
        slope10 / max(params["trend_slope10_pct"], 0.01),
        slope20 / max(params["trend_slope20_pct"], 0.01),
    )
    slope_score = min(1.0, max(0.0, slope_score))
    if 1.00 <= ratio <= 1.08:
        distance_score = 1.0
    elif ratio < 1.00:
        distance_score = max(0.0, ratio / 1.00)
    elif ratio <= params["trend_max_close_ma20_ratio"]:
        span = max(params["trend_max_close_ma20_ratio"] - 1.08, 0.01)
        distance_score = max(0.65, 1.0 - (ratio - 1.08) / span * 0.35)
    else:
        distance_score = max(0.0, 0.65 - (ratio - params["trend_max_close_ma20_ratio"]) / 0.08)

    score = persistence_score * 0.4 + slope_score * 0.4 + distance_score * 0.2
    return ok, round(float(score), 4)


def check_ma_bullish(df: pd.DataFrame) -> Tuple[bool, float]:
    """
    检查均线多头排列: close > MA3 > MA5 > MA21
    返回 (是否多头, 乖离率评分)
    """
    if len(df) < 21:
        return False, 0.0

    latest = df.iloc[-1]
    ma3 = latest.get("MA3", np.nan)
    ma5 = latest.get("MA5", np.nan)
    ma21 = latest.get("MA21", np.nan)

    if pd.isna(ma3) or pd.isna(ma5) or pd.isna(ma21):
        return False, 0.0

    close = latest.get("close", np.nan)
    is_bullish = close > ma3 > ma5 > ma21

    if not is_bullish:
        return False, 0.0

    # 乖离率：MA3 相对 MA21 的偏离程度（太大 → 超买，太小 → 不够强）
    divergence = (ma3 - ma21) / ma21 * 100
    # 乖离在 2%~8% 之间最理想
    if 2 <= divergence <= 8:
        quality = 1.0
    elif 0 < divergence < 2:
        quality = 0.7
    elif 8 < divergence <= 15:
        quality = 0.5
    else:
        quality = 0.3

    return True, quality


# ============================================================
# DMI — 趋向指标 (Directional Movement Index)
# ============================================================

def calc_dmi(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算 DMI(7, 6):
    - +DI / -DI 周期 = 7（Wilder's smoothing）
    - ADX 平滑周期 = 6
    """
    period = cfg.DMI_PERIOD
    adx_period = cfg.ADX_PERIOD

    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    # True Range
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Directional Movement
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    # Wilder's smoothing: alpha = 1/period
    atr = tr.ewm(alpha=1.0/period, adjust=False).mean()
    smoothed_plus_dm = pd.Series(plus_dm).ewm(alpha=1.0/period, adjust=False).mean()
    smoothed_minus_dm = pd.Series(minus_dm).ewm(alpha=1.0/period, adjust=False).mean()

    # +DI, -DI
    df["plus_di"] = (smoothed_plus_dm / atr) * 100
    df["minus_di"] = (smoothed_minus_dm / atr) * 100

    # DX
    di_sum = df["plus_di"] + df["minus_di"]
    di_diff = (df["plus_di"] - df["minus_di"]).abs()
    df["dx"] = np.where(di_sum > 0, (di_diff / di_sum) * 100, 0)

    # ADX — Wilder's smoothing of DX with period 6
    df["ADX"] = pd.Series(df["dx"]).ewm(alpha=1.0/adx_period, adjust=False).mean()

    return df


def check_adx_condition(df: pd.DataFrame) -> Tuple[bool, float]:
    """
    检查 +DI > -DI 且 ADX > 25 条件
    返回 (是否满足, ADX强度评分 0~1)
    """
    if "ADX" not in df.columns or len(df) == 0:
        return False, 0.0

    latest = df.iloc[-1]
    latest_adx = latest.get("ADX", np.nan)
    plus_di = latest.get("plus_di", np.nan)
    minus_di = latest.get("minus_di", np.nan)

    if (
        pd.isna(latest_adx)
        or pd.isna(plus_di)
        or pd.isna(minus_di)
        or latest_adx <= cfg.ADX_THRESHOLD
        or plus_di <= minus_di
    ):
        return False, 0.0

    # ADX 强度评分: 25→0.5, 30→0.7, 40+→1.0
    if latest_adx >= 40:
        strength = 1.0
    elif latest_adx >= 35:
        strength = 0.85
    elif latest_adx >= 30:
        strength = 0.7
    else:
        strength = 0.5 + (latest_adx - 25) / 30  # 25~30线性映射到0.5~0.67

    return True, strength


# ============================================================
# EXPMA — 指数移动平均线
# ============================================================

def calc_expma(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算 EXPMA(7), EXPMA(21)
    EXPMA = EMA(close, period)
    """
    df["EXPMA7"] = df["close"].ewm(span=cfg.EXPMA_FAST, adjust=False).mean()
    df["EXPMA21"] = df["close"].ewm(span=cfg.EXPMA_SLOW, adjust=False).mean()
    return df


def check_expma_golden_cross(df: pd.DataFrame) -> Tuple[bool, float]:
    """
    检查 EXPMA 金叉:
    - EXPMA7 上穿 EXPMA21
    - 允许在近 N 日内发生；若较早但趋势仍保持多头，降分通过
    返回 (是否金叉, 金叉质量评分 0~1)
    """
    if len(df) < cfg.EXPMA_SLOW + 3:
        return False, 0.0

    expma7 = df["EXPMA7"].values
    expma21 = df["EXPMA21"].values
    n = len(df)

    # 当前必须 EXPMA7 > EXPMA21
    if expma7[-1] <= expma21[-1]:
        return False, 0.0

    # 搜索全区间内所有金叉点
    cross_days = cfg.EXPMA_CROSS_DAYS
    golden_cross_idx = -1
    for i in range(1, n):
        if expma7[i-1] <= expma21[i-1] and expma7[i] > expma21[i]:
            golden_cross_idx = i

    if golden_cross_idx == -1:
        return False, 0.0

    # 金叉距今的天数
    days_since_cross = n - 1 - golden_cross_idx

    # 计算乖离率
    divergence = (expma7[-1] - expma21[-1]) / expma21[-1] * 100

    if days_since_cross > cross_days:
        return False, 0.0

    # 质量评分：根据金叉新鲜度和乖离率
    if 1 <= divergence <= 5:
        quality = 1.0
    elif 0.3 <= divergence < 1:
        quality = 0.75
    elif 5 < divergence <= 10:
        quality = 0.5
    else:
        quality = 0.3

    return True, quality


# ============================================================
# MACD — 指数平滑异同移动平均线
# ============================================================

def calc_macd(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算 MACD(6, 13, 5):
    - DIFF = EMA(close, 6) - EMA(close, 13)
    - DEA = EMA(DIFF, 5)
    - MACD柱 = 2 × (DIFF - DEA)
    """
    ema_fast = df["close"].ewm(span=cfg.MACD_FAST, adjust=False).mean()
    ema_slow = df["close"].ewm(span=cfg.MACD_SLOW, adjust=False).mean()

    df["MACD_DIFF"] = ema_fast - ema_slow
    df["MACD_DEA"] = df["MACD_DIFF"].ewm(span=cfg.MACD_SIGNAL, adjust=False).mean()
    df["MACD_HIST"] = 2 * (df["MACD_DIFF"] - df["MACD_DEA"])

    return df


def check_macd_second_golden_cross(df: pd.DataFrame) -> Tuple[bool, float]:
    """
    检查 MACD 零轴上方二次金叉:
    1. DIFF 和 DEA 都在零轴上方（DIFF > 0, DEA > 0）
    2. DIFF 上穿 DEA（金叉）
    3. 这至少是零轴上方区域内的第二次金叉
    4. 最近一次金叉发生在近 N 日内

    返回 (是否满足, MACD质量评分 0~1)
    """
    if len(df) < cfg.MACD_SLOW + 10:
        return False, 0.0

    diff = df["MACD_DIFF"].values
    dea = df["MACD_DEA"].values
    hist = df["MACD_HIST"].values
    n = len(df)

    # ---- 第一步：找到最近一次进入零轴上方区域后的所有金叉 ----
    zone_start = None
    for i in range(1, n):
        was_above = diff[i-1] > 0 and dea[i-1] > 0
        is_above = diff[i] > 0 and dea[i] > 0
        if is_above and not was_above:
            zone_start = i

    if zone_start is None:
        return False, 0.0

    golden_crosses = []
    for i in range(max(1, zone_start), n):
        if diff[i-1] <= dea[i-1] and diff[i] > dea[i] and diff[i] > 0 and dea[i] > 0:
            golden_crosses.append(i)

    if len(golden_crosses) < 2:
        return False, 0.0

    # ---- 第二步：最近一次金叉应在近 N 日内 ----
    most_recent_cross = golden_crosses[-1]
    days_since_cross = n - 1 - most_recent_cross

    if days_since_cross > cfg.MACD_CROSS_DAYS:
        return False, 0.0

    # ---- 第三步：当前必须仍处于金叉状态（DIFF > DEA） ----
    if diff[-1] <= dea[-1]:
        return False, 0.0

    # ---- 第四步：验证两次金叉之间有过回调（DIFF下降），确保是"二次"而非"延续" ----
    if len(golden_crosses) >= 2:
        second_last_cross = golden_crosses[-2]
        diff_between = diff[second_last_cross:most_recent_cross]
        if len(diff_between) >= 3:
            peak = np.max(diff_between)
            trough = np.min(diff_between)
            if peak > 0 and (peak - trough) / peak < 0.02:
                # 几乎没有回调，不算真正的二次金叉
                return False, 0.0

    # ---- 第五步：质量评分 ----
    # 当前 DIFF 与 DEA 的距离
    diff_dea_gap = abs(diff[-1] - dea[-1])

    # 当前 MACD 柱强度
    hist_strength = abs(hist[-1]) if not pd.isna(hist[-1]) else 0

    # DIFF 的斜率（近3日趋势）
    if n >= 3 and diff[-3] != 0:
        diff_slope = (diff[-1] - diff[-3]) / abs(diff[-3])
    else:
        diff_slope = 0

    # 综合质量评分
    quality = 0.5  # 基础分（满足二次金叉条件）

    # DIFF 正在扩大（柱线增长）
    if diff[-1] > diff[-2] and hist[-1] > hist[-2]:
        quality += 0.2

    # DIFF 与 DEA 距离适中（不太近不太远）
    if diff[-1] > 0 and diff_dea_gap / diff[-1] > 0.05:
        quality += 0.15

    # DIFF 上升斜率
    if diff_slope > 0.05:
        quality += 0.15
    elif diff_slope < -0.05:
        quality -= 0.1

    return True, min(quality, 1.0)


# ============================================================
# 成交量条件
# ============================================================

def calc_volume_ma(df: pd.DataFrame) -> pd.DataFrame:
    """计算前N日均量和量比，不把当日成交量放进分母。"""
    df["VOL_MA5"] = df["volume"].shift(1).rolling(window=cfg.VOL_MA_PERIOD).mean()
    df["VOL_RATIO"] = df["volume"] / df["VOL_MA5"]
    return df


def check_volume_condition(df: pd.DataFrame) -> Tuple[bool, float]:
    """
    检查成交量条件: 当日成交量 > 前5日均量 × 1.3
    返回 (是否满足, 量比评分 0~1)
    """
    if len(df) < cfg.VOL_MA_PERIOD + 1:
        return False, 0.0

    latest = df.iloc[-1]
    vol_ratio = latest.get("VOL_RATIO", np.nan)

    if pd.isna(vol_ratio):
        return False, 0.0

    if vol_ratio < cfg.VOL_RATIO_MIN:
        return False, 0.0

    # 量比评分：1.3~2.0 最佳，过高可能出货
    if cfg.VOL_RATIO_OPTIMAL_LOW <= vol_ratio <= cfg.VOL_RATIO_OPTIMAL_HIGH:
        quality = 0.8 + 0.2 * (vol_ratio - 1.3) / 0.7  # 1.3~2.0 → 0.8~1.0
    elif vol_ratio < cfg.VOL_RATIO_OPTIMAL_LOW:
        quality = 0.6 + 0.2 * (vol_ratio - 1.0) / 0.3  # 1.0~1.3 → 0.6~0.8
    elif vol_ratio <= 3.0:
        quality = 0.8 - 0.3 * (vol_ratio - 2.0)  # 2.0~3.0 → 0.5~0.8
    else:
        quality = 0.3  # >3.0倍量：警惕出货

    return True, min(max(quality, 0), 1.0)


# ============================================================
# 综合条件检查
# ============================================================

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算所有技术指标"""
    df = df.copy()
    df = calc_ma(df)
    df = calc_trend_quality(df)
    df = calc_dmi(df)
    df = calc_expma(df)
    df = calc_macd(df)
    df = calc_volume_ma(df)
    return df


# ============================================================
# 入场时机分析 — 避免追高，找回调买入点
# ============================================================

def analyze_entry_timing(df: pd.DataFrame) -> dict:
    """
    分析入场时机质量，避免追涨被套
    返回 {
        "overextended": bool,      # 是否连续涨太多（不建议追）
        "consecutive_up": int,     # 连续上涨天数
        "consecutive_down": int,   # 连续下跌天数
        "position_vs_ma5": float,  # 收盘价相对MA5位置 (%)
        "position_vs_ma21": float, # 收盘价相对MA21位置 (%)
        "pullback_quality": float, # 回调质量 0~1
        "entry_score": float,      # 入场时机评分 0~1
        "entry_label": str,        # 入场时机标签
    }
    """
    if len(df) < 10:
        return {"overextended": False, "consecutive_up": 0, "consecutive_down": 0,
                "position_vs_ma5": 0, "position_vs_ma21": 0,
                "pullback_quality": 0, "entry_score": 0.5, "entry_label": "数据不足"}

    close = df["close"].values
    n = len(close)

    # ---- 统计连续涨跌天数 ----
    consecutive_up = 0
    consecutive_down = 0
    for i in range(n - 1, 0, -1):
        if close[i] > close[i-1]:
            if consecutive_down == 0:
                consecutive_up += 1
            else:
                break
        elif close[i] < close[i-1]:
            if consecutive_up == 0:
                consecutive_down += 1
            else:
                break
        else:
            break

    # ---- 价格相对均线位置 ----
    latest = df.iloc[-1]
    close_now = latest["close"]
    ma5 = latest.get("MA5", close_now)
    ma21 = latest.get("MA21", close_now)

    pos_vs_ma5 = (close_now - ma5) / ma5 * 100 if ma5 > 0 else 0
    pos_vs_ma21 = (close_now - ma21) / ma21 * 100 if ma21 > 0 else 0

    # ---- 判断是否过度延伸（追高风险） ----
    # 条件：连续涨3天+ 且 远离MA5超过5%
    overextended = (consecutive_up >= 3) or (pos_vs_ma5 > 8)

    # ---- 回调质量评分 ----
    pullback_quality = 0.5  # 默认中性

    # 均线多头排列（趋势向上）
    ma3 = latest.get("MA3", 0)
    trend_up = (ma3 > ma5 > ma21) if (ma3 and ma5 and ma21) else False

    if trend_up:
        if consecutive_down == 1:
            # 趋势向上 + 今天刚回调1天 → 最佳入场时机
            pullback_quality = 0.95
        elif consecutive_down == 2:
            # 趋势向上 + 回调2天 → 好时机，但需确认支撑
            if pos_vs_ma21 > 0:  # 仍在MA21上方
                pullback_quality = 0.85
            else:
                pullback_quality = 0.6
        elif consecutive_up == 1:
            # 趋势向上 + 刚涨1天 → 可以追
            pullback_quality = 0.75
        elif consecutive_up == 2:
            # 趋势向上 + 涨了2天 → 谨慎
            pullback_quality = 0.55
        else:
            pullback_quality = 0.5
    else:
        # 非多头排列，更谨慎
        if consecutive_down >= 2:
            pullback_quality = 0.2  # 下跌趋势中
        elif consecutive_up >= 2:
            pullback_quality = 0.3  # 可能是反弹
        else:
            pullback_quality = 0.4

    # ---- 综合入场评分 ----
    entry_score = pullback_quality

    # 偏离MA5太远减分（无论涨跌）
    if abs(pos_vs_ma5) > 5:
        entry_score -= 0.2
    # 跌破MA21严重减分
    if pos_vs_ma21 < -3:
        entry_score -= 0.3
    # 连续涨太多减分
    if consecutive_up >= 3:
        entry_score -= 0.4
    if consecutive_up >= 5:
        entry_score -= 0.3

    entry_score = max(0, min(1.0, entry_score))

    # ---- 标签 ----
    if consecutive_up >= 5:
        entry_label = "🔴 严重追高风险"
    elif consecutive_up >= 3:
        entry_label = "🟠 连涨多日，等回调再入"
    elif pos_vs_ma5 > 8:
        entry_label = "🟠 远离均线，不宜追高"
    elif trend_up and consecutive_down == 1 and abs(pos_vs_ma5) < 3:
        entry_label = "🟢 最佳入场时机"
    elif trend_up and consecutive_down == 1:
        entry_label = "🟢 回调即机会"
    elif trend_up and consecutive_down == 2 and pos_vs_ma21 > 0:
        entry_label = "🟡 连跌2日，关注支撑"
    elif trend_up and consecutive_up == 1 and pos_vs_ma5 < 3:
        entry_label = "🟢 趋势启动，适合入场"
    elif consecutive_up == 1:
        entry_label = "🟡 首日上涨，可关注"
    elif consecutive_up == 2:
        entry_label = "🟠 连涨2天，注意节奏"
    elif consecutive_down >= 3:
        entry_label = "🔴 连跌多日，趋势可能走坏"
    else:
        entry_label = "⚪ 中性"

    return {
        "overextended": overextended,
        "consecutive_up": consecutive_up,
        "consecutive_down": consecutive_down,
        "position_vs_ma5": round(pos_vs_ma5, 1),
        "position_vs_ma21": round(pos_vs_ma21, 1),
        "pullback_quality": round(pullback_quality, 2),
        "entry_score": round(entry_score, 2),
        "entry_label": entry_label,
    }


def check_all_conditions(df: pd.DataFrame) -> dict:
    """
    检查所有必选条件和评分条件
    返回 {
        "passed": bool,                        # 是否通过所有必选条件
        "adx_pass": bool, "adx_score": float,
        "expma_pass": bool, "expma_score": float,
        "macd_pass": bool, "macd_score": float,
        "volume_pass": bool, "volume_score": float,
        "ma_bullish": bool, "ma_score": float,
        "technical_score": float,              # 技术面总分 (0~55)
    }
    """
    result = {
        "passed": False,
        "adx_pass": False, "adx_score": 0.0,
        "expma_pass": False, "expma_score": 0.0,
        "macd_pass": False, "macd_score": 0.0,
        "volume_pass": False, "volume_score": 0.0,
        "ma_bullish": False, "ma_score": 0.0,
        "technical_score": 0.0,
        "adx_value": 0.0,
        "plus_di": 0.0,
        "minus_di": 0.0,
        "vol_ratio": 0.0,
        "close_ma21_ratio": 0.0,
        "ma3_ma5_ratio": 0.0,
        "expma_ratio": 0.0,
        "macd_diff": 0.0,
        "macd_dea": 0.0,
        "macd_hist": 0.0,
        "entry_timing": {},  # 入场时机分析
        "trend_quality_pass": False,
        "trend_quality_score": 0.0,
        "above_ma20_days_20": 0,
        "ma20_slope_10_pct": 0.0,
        "ma20_slope_20_pct": 0.0,
        "close_ma20_ratio": 0.0,
        "current_above_ma20": False,
        "ma20_not_overheated": False,
    }

    if len(df) < 25:
        return result

    latest = df.iloc[-1]
    checks = evaluate_technical_conditions(df, cfg.SCREEN_MODE)
    close = float(latest.get("close", 0) or 0)
    ma3 = float(latest.get("MA3", 0) or 0)
    ma5 = float(latest.get("MA5", 0) or 0)
    ma21 = float(latest.get("MA21", 0) or 0)
    expma7 = float(latest.get("EXPMA7", 0) or 0)
    expma21 = float(latest.get("EXPMA21", 0) or 0)

    result["close_ma21_ratio"] = close / ma21 - 1 if ma21 > 0 else 0.0
    result["close_ma20_ratio"] = _num(latest.get("CLOSE_MA20_RATIO", 0))
    result["ma3_ma5_ratio"] = ma3 / ma5 - 1 if ma5 > 0 else 0.0
    result["expma_ratio"] = expma7 / expma21 - 1 if expma21 > 0 else 0.0
    result["macd_diff"] = float(latest.get("MACD_DIFF", 0) or 0)
    result["macd_dea"] = float(latest.get("MACD_DEA", 0) or 0)
    result["macd_hist"] = float(latest.get("MACD_HIST", 0) or 0)

    # 1. +DI > -DI 且 ADX 达到当前模式阈值
    adx_ok, adx_s = check_adx_condition(df)
    adx_ok = checks["pdi_gt_mdi"] and checks["adx_enough"]
    if adx_ok and adx_s == 0:
        adx_value = checks.get("adx_value", float(latest.get("ADX", 0) or 0))
        adx_s = min(1.0, max(0.5, (float(latest.get("ADX", 0) or 0) - checks["adx_threshold"]) / 20 + 0.5))
    result["adx_pass"] = adx_ok
    result["adx_score"] = adx_s
    result["adx_value"] = float(latest.get("ADX", 0))
    result["plus_di"] = float(latest.get("plus_di", 0))
    result["minus_di"] = float(latest.get("minus_di", 0))

    # 2. EXPMA 金叉
    expma_recent_ok, expma_s = check_expma_golden_cross(df)
    expma_ok = checks["expma_bull"] if cfg.SCREEN_MODE in ("normal", "loose") else expma_recent_ok
    result["expma_pass"] = expma_ok
    result["expma_score"] = expma_s

    # 3. MACD 零轴上方二次金叉
    macd_recent_ok, macd_s = check_macd_second_golden_cross(df)
    if cfg.SCREEN_MODE == "strict":
        macd_ok = macd_recent_ok
    elif cfg.SCREEN_MODE == "normal":
        macd_ok = checks["dif_dea_above_zero"] and checks["dif_gt_dea"]
    else:
        macd_ok = checks["dif_dea_above_zero"]
    result["macd_pass"] = macd_ok
    result["macd_score"] = macd_s

    # 4. 成交量
    vol_ok, vol_s = check_volume_condition(df)
    vol_ok = checks["volume_enough"]
    if vol_ok and vol_s == 0:
        vol_ratio_value = float(latest.get("VOL_RATIO", 0) or 0)
        vol_s = min(1.0, max(0.5, vol_ratio_value / 2.0))
    result["volume_pass"] = vol_ok
    result["volume_score"] = vol_s
    result["vol_ratio"] = float(latest.get("VOL_RATIO", 0))

    # 5. 均线多头（非必选，但影响技术评分）
    ma_ok, ma_s = check_ma_bullish(df)
    result["ma_bullish"] = ma_ok
    result["ma_score"] = ma_s

    # 6. 趋势持续性：20日中多数站上MA20，且MA20斜率向上、不过热
    trend_ok, trend_s = check_trend_quality(df, cfg.SCREEN_MODE)
    result["trend_quality_pass"] = trend_ok
    result["trend_quality_score"] = trend_s
    result["above_ma20_days_20"] = int(_num(latest.get("ABOVE_MA20_DAYS_20", 0)))
    result["ma20_slope_10_pct"] = _num(latest.get("MA20_SLOPE_10_PCT", 0))
    result["ma20_slope_20_pct"] = _num(latest.get("MA20_SLOPE_20_PCT", 0))
    result["current_above_ma20"] = _bool(latest.get("CURRENT_ABOVE_MA20", False))
    result["ma20_not_overheated"] = bool(checks.get("ma20_not_overheated", False))

    # ---- 入场时机分析 ----
    entry = analyze_entry_timing(df)
    result["entry_timing"] = entry

    # ---- 必选条件：均线 + DMI + EXPMA + MACD + 放量 ----
    hard_pass = bool(checks["technical_pass"])
    # 如果连续涨5天以上且远离均线 → 即使技术面通过也标记为追高风险
    if entry["overextended"] and entry["consecutive_up"] >= 5:
        hard_pass = False  # 严重追高，直接排除
    result["passed"] = hard_pass

    # ---- 技术面总分（满分55） ----
    if hard_pass:
        tech_score = (
            cfg.TECH_ADX_WEIGHT * adx_s +
            cfg.TECH_MACD_WEIGHT * macd_s +
            cfg.TECH_EXPMA_WEIGHT * expma_s +
            cfg.TECH_MA_WEIGHT * ma_s +
            cfg.TECH_VOLUME_WEIGHT * vol_s
        )
        result["technical_score"] = round(tech_score, 2)
    else:
        result["technical_score"] = 0.0

    return result
