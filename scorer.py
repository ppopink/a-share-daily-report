"""
综合评分模块
- 资金净流入评分（25分）
- 板块领涨 / 相对强度评分（20分）
- 技术面评分（55分）
"""

import numpy as np
import pandas as pd

import config as cfg


def score_capital_flow(
    symbols: list,
    money_flow_data: dict,
    spot_df: pd.DataFrame
) -> dict:
    """
    资金净流入评分（满分25分）
    使用近N日主力净流入占成交额的比例，Min-Max归一化排名

    money_flow_data: {symbol: {"total_inflow": float}, ...}
    返回 {symbol: float (0~25)}
    """
    if not money_flow_data:
        return {s: round(cfg.WEIGHT_CAPITAL_FLOW * 0.5, 2) for s in symbols}

    scores = {}

    # 计算流入/成交额比
    ratios = {}
    for sym, data in money_flow_data.items():
        inflow = data.get("total_inflow", 0)
        try:
            amount = float(spot_df.loc[sym, "amount"]) if sym in spot_df.index else 0
        except (KeyError, TypeError):
            amount = 0
        ratios[sym] = inflow / amount if amount > 0 else 0

    if not ratios:
        return {s: round(cfg.WEIGHT_CAPITAL_FLOW * 0.5, 2) for s in symbols}

    values = list(ratios.values())
    v_min, v_max = min(values), max(values)

    for sym in symbols:
        if sym in ratios and v_max > v_min:
            normalized = (ratios[sym] - v_min) / (v_max - v_min)
        else:
            normalized = 0.5
        scores[sym] = round(normalized * cfg.WEIGHT_CAPITAL_FLOW, 2)

    return scores


def score_sector_leadership(
    symbols: list,
    sector_score_map: dict,
    spot_df: pd.DataFrame
) -> dict:
    """
    板块领涨评分（满分20分）

    优先使用 sector_score_map（板块成份股映射），
    若无板块数据且允许 fallback，则基于当日涨跌幅相对排名估算：
      - 涨幅在全市场前 3%  → 20分（极可能是领涨股）
      - 涨幅在前 10%       → 15分
      - 涨幅在前 20%       → 10分
      - 其他               →  5分

    sector_score_map: {symbol: score (0~20)}
    spot_df: 全市场行情（含 pct_change 列）
    返回 {symbol: float}
    """
    scores = {}

    # 如果已有板块映射，直接使用
    if sector_score_map:
        for sym in symbols:
            scores[sym] = float(sector_score_map.get(sym, cfg.SECTOR_RANK_OTHER_SCORE))
        return scores

    if not cfg.SECTOR_FALLBACK_TO_RELATIVE_STRENGTH:
        return {s: float(cfg.SECTOR_RANK_OTHER_SCORE) for s in symbols}

    # 否则基于相对强度估算
    if "code" not in spot_df.columns:
        spot_df = spot_df.reset_index()
    if "code" not in spot_df.columns:
        return {s: 5.0 for s in symbols}

    # 获取全市场涨跌幅用于排名
    all_pcts = spot_df["pct_change"].dropna().values
    if len(all_pcts) == 0:
        return {s: 5.0 for s in symbols}

    # 计算每个候选股的市场百分位
    for sym in symbols:
        try:
            sym_pct = float(spot_df[spot_df["code"] == sym]["pct_change"].iloc[0])
        except (IndexError, KeyError):
            scores[sym] = 5.0
            continue

        percentile = (all_pcts < sym_pct).sum() / len(all_pcts)

        if percentile >= 0.97:    # 前3%
            scores[sym] = float(cfg.SECTOR_RANK_TOP3_SCORE)
        elif percentile >= 0.90:  # 前10%
            scores[sym] = float(cfg.SECTOR_RANK_TOP10_SCORE)
        elif percentile >= 0.80:  # 前20%
            scores[sym] = float(cfg.SECTOR_RANK_TOP20_SCORE)
        else:
            scores[sym] = float(cfg.SECTOR_RANK_OTHER_SCORE)

    return scores


def _build_selection_reason(ind: dict, row: dict, context: dict) -> str:
    reasons = []
    if row.get("trend_quality_score", 0) >= 10:
        reasons.append("趋势质量较好")
    if ind.get("above_ma20_days_20", 0) >= 16:
        reasons.append("20日多数站上MA20")
    if ind.get("ma20_slope_10_pct", 0) >= 5 or ind.get("ma20_slope_20_pct", 0) >= 8:
        reasons.append("MA20斜率上行")
    if ind.get("adx_value", 0) >= 35 and ind.get("plus_di", 0) > ind.get("minus_di", 0):
        reasons.append("DMI趋势偏强")
    if ind.get("vol_ratio", 0) >= 1.5:
        reasons.append("量能放大")
    if ind.get("macd_pass"):
        reasons.append("MACD动能确认")
    if row.get("main_net_ratio", 0) > 0:
        reasons.append("资金净流入")
    if row.get("sector_score", 0) >= 15:
        reasons.append("板块相对靠前")
    if row.get("context_score", 0) > 0:
        reasons.append("事件/两融/龙虎榜加分")
    if not reasons:
        reasons.append("综合规则排序靠前")
    return "；".join(reasons[:5])


def _build_watch_reason(ind: dict, row: dict, entry_label: str) -> str:
    reasons = []
    if "追高" in entry_label or "连涨" in entry_label:
        reasons.append("短线已有涨幅，避免高开追入")
    if row.get("pct_change", 0) >= 7:
        reasons.append("当日涨幅较高")
    if ind.get("close_ma20_ratio", 1) >= 1.15:
        reasons.append("偏离MA20较大")
    if ind.get("vol_ratio", 0) < 1.2:
        reasons.append("量能确认不足")
    if row.get("main_net_ratio", 0) < 0:
        reasons.append("资金净流入偏弱")
    if row.get("context_score", 0) < 0:
        reasons.append("事件/两融/龙虎榜偏负")
    return "；".join(reasons) if reasons else "暂无明显额外风险，仍需按T+1开盘条件执行"


def _build_buy_trigger(row: dict, ind: dict, entry_label: str, entry_bonus: float, exit_plan: dict) -> dict:
    price = float(row.get("price", 0) or exit_plan.get("signal_close", 0) or 0)
    ma5 = float(exit_plan.get("reference_ma5", 0) or 0)
    atr = float(exit_plan.get("reference_atr", 0) or max(price * 0.025, 0.01))
    pct_change = float(row.get("pct_change", 0) or 0)
    vol_ratio = float(ind.get("vol_ratio", 0) or 0)
    close_ma20_ratio = float(ind.get("close_ma20_ratio", 1) or 1)

    if price <= 0:
        return {
            "buy_action": "等待确认",
            "buy_trigger": "价格数据不足，不能生成明日买入触发条件。",
            "buy_avoid_rules": "缺少有效价格时不交易。",
            "max_open_gap_pct": 0.0,
            "max_buy_price": 0.0,
            "pullback_buy_price": 0.0,
            "invalid_below_price": 0.0,
        }

    if "追高" in entry_label or pct_change >= 7 or close_ma20_ratio >= 1.15:
        max_gap_pct = 1.5
        buy_action = "等回踩确认"
    elif entry_bonus > 0 and vol_ratio >= 1.3:
        max_gap_pct = 3.0
        buy_action = "可积极观察"
    else:
        max_gap_pct = 2.0
        buy_action = "轻仓观察"

    max_buy_price = price * (1 + max_gap_pct / 100)
    pullback_buy_price = ma5 if ma5 > 0 else max(price - 0.6 * atr, price * 0.98)
    invalid_below_price = max(price * 0.985, ma5 * 0.985 if ma5 > 0 else 0)

    buy_trigger = (
        f"T+1不涨停、不停牌；开盘高开不超过{max_gap_pct:.1f}%且价格≤{max_buy_price:.2f}；"
        f"盘中回踩{pullback_buy_price:.2f}附近不破、重新放量转强再考虑。"
    )
    buy_avoid_rules = (
        f"一字涨停/开盘涨停不买；高开超过{max_gap_pct:.1f}%不追；"
        f"跌破{invalid_below_price:.2f}或开盘后放量走弱不买；成交额明显不足不买。"
    )
    return {
        "buy_action": buy_action,
        "buy_trigger": buy_trigger,
        "buy_avoid_rules": buy_avoid_rules,
        "max_open_gap_pct": round(max_gap_pct, 2),
        "max_buy_price": round(max_buy_price, 2),
        "pullback_buy_price": round(pullback_buy_price, 2),
        "invalid_below_price": round(invalid_below_price, 2),
    }


def compute_total_scores(
    symbols: list,
    indicators_results: dict,
    money_flow_data: dict,
    spot_df: pd.DataFrame,
    sector_score_map: dict,
    rule_flags: pd.DataFrame = None,
    market_context_data: dict = None,
) -> pd.DataFrame:
    """
    计算综合总分并排序
    返回 DataFrame，按 total_score 降序
    """
    # 设置索引
    if "code" in spot_df.columns:
        spot_indexed = spot_df.set_index("code")
    else:
        spot_indexed = spot_df

    # 分项评分
    flow_scores = score_capital_flow(symbols, money_flow_data, spot_indexed)
    sector_scores = score_sector_leadership(symbols, sector_score_map, spot_df)
    market_context_data = market_context_data or {}
    if rule_flags is not None and not rule_flags.empty:
        flags_indexed = rule_flags.set_index("code")
    else:
        flags_indexed = pd.DataFrame()

    results = []
    for sym in symbols:
        ind = indicators_results.get(sym, {})
        tech_score = ind.get("technical_score", 0)
        flow_score = flow_scores.get(sym, 12.5)
        sector_score = sector_scores.get(sym, 5.0)
        money_flow = money_flow_data.get(sym, {})
        total_inflow = float(money_flow.get("total_inflow", 0))
        context = market_context_data.get(sym, {}) or {}
        context_score = float(context.get("context_score", 0) or 0)

        try:
            name = spot_indexed.loc[sym, "name"] if sym in spot_indexed.index else sym
        except (KeyError, TypeError):
            name = sym

        try:
            pct = float(spot_indexed.loc[sym, "pct_change"]) if sym in spot_indexed.index else 0
        except (KeyError, TypeError):
            pct = 0

        try:
            price = float(spot_indexed.loc[sym, "price"]) if sym in spot_indexed.index else 0
        except (KeyError, TypeError):
            price = 0

        try:
            amount = float(spot_indexed.loc[sym, "amount"]) if sym in spot_indexed.index else 0
        except (KeyError, TypeError):
            amount = 0

        try:
            industry = spot_indexed.loc[sym, "industry"] if sym in spot_indexed.index and "industry" in spot_indexed.columns else ""
        except (KeyError, TypeError):
            industry = ""

        flags = flags_indexed.loc[sym] if not flags_indexed.empty and sym in flags_indexed.index else {}
        sector_rank_pct = float(flags.get("sector_rank_pct", np.nan)) if hasattr(flags, "get") else np.nan
        stock_rank_in_sector = float(flags.get("stock_rank_in_sector", np.nan)) if hasattr(flags, "get") else np.nan
        above_ma20_days = float(ind.get("above_ma20_days_20", 0) or 0)
        trend_persistence_score = min(6.0, max(0.0, above_ma20_days / 20 * 6))
        ma20_slope_raw = max(
            float(ind.get("ma20_slope_10_pct", 0) or 0) / 4.0,
            float(ind.get("ma20_slope_20_pct", 0) or 0) / 7.0,
        )
        ma20_slope_score = min(5.0, max(0.0, ma20_slope_raw * 5))
        close_ma20_ratio = float(ind.get("close_ma20_ratio", 0) or 0)
        if 1.00 <= close_ma20_ratio <= 1.08:
            ma20_distance_score = 4.0
        elif 0.98 <= close_ma20_ratio < 1.00:
            ma20_distance_score = 2.5
        elif close_ma20_ratio <= 1.18:
            ma20_distance_score = max(1.5, 4.0 - (close_ma20_ratio - 1.08) / 0.10 * 2.5)
        else:
            ma20_distance_score = 0.0
        ma_stack_bonus = 3.0 if ind.get("ma_bullish") else 0.0
        trend_quality_score = min(15.0, trend_persistence_score + ma20_slope_score + ma20_distance_score + ma_stack_bonus)
        trend_score = trend_quality_score
        volume_score = min(10.0, max(0.0, ind.get("vol_ratio", 0) / 2.5 * 10))
        dmi_score = min(15.0, max(0.0, (ind.get("adx_value", 0) - 15) / 30 * 15))
        macd_score = 0.0
        if ind.get("macd_pass"):
            macd_score += 8
        if ind.get("macd_score", 0) > 0:
            macd_score += ind.get("macd_score", 0) * 7
        expma_score = min(10.0, max(0.0, ind.get("expma_ratio", 0) * 300))
        if ind.get("expma_score", 0) > 0:
            expma_score = min(10.0, expma_score + ind.get("expma_score", 0) * 4)
        money_flow_score = flow_score
        leading_score = 0.0 if np.isnan(stock_rank_in_sector) else max(0.0, (1 - stock_rank_in_sector) * 10)
        sector_component = sector_score
        total = round(
            trend_score + volume_score + dmi_score + macd_score + expma_score +
            money_flow_score + sector_component + leading_score + context_score,
            2,
        )

        # 入场时机信息
        entry = ind.get("entry_timing", {})
        entry_label = entry.get("entry_label", "")
        consecutive_up = entry.get("consecutive_up", 0)
        consecutive_down = entry.get("consecutive_down", 0)
        pos_vs_ma5 = entry.get("position_vs_ma5", 0)
        exit_plan = ind.get("exit_plan", {}) or {}

        # 入场时机加成：好时机加分，追高风险减分
        entry_bonus = 0
        if trend_up := entry.get("position_vs_ma21", 0) > 0:
            if consecutive_down == 1 and abs(pos_vs_ma5) < 3:
                entry_bonus = 6  # 最佳入场：趋势向上+回调1天+贴近均线
            elif consecutive_down == 1:
                entry_bonus = 3  # 趋势向上+回调1天
            elif consecutive_up == 1 and abs(pos_vs_ma5) < 5:
                entry_bonus = 2  # 刚启动
            elif consecutive_down == 2 and pos_vs_ma5 < 3:
                entry_bonus = 1  # 回调2天但支撑有效

        if consecutive_up >= 5:
            entry_bonus = -15  # 严重追高
        elif consecutive_up >= 4:
            entry_bonus = -10  # 连涨4天
        elif consecutive_up >= 3:
            entry_bonus = -6   # 连涨3天
        elif pos_vs_ma5 > 8:
            entry_bonus = -4   # 远离均线

        total_with_entry = round(total + entry_bonus, 2)
        base_for_reason = {
            "price": price,
            "pct_change": pct,
            "trend_quality_score": round(trend_quality_score, 2),
            "sector_score": sector_component,
            "context_score": context_score,
            "main_net_ratio": total_inflow / amount if amount > 0 else 0,
        }
        buy_plan = _build_buy_trigger(base_for_reason, ind, entry_label, entry_bonus, exit_plan)
        selection_reason = _build_selection_reason(ind, base_for_reason, context)
        watch_reason = _build_watch_reason(ind, base_for_reason, entry_label)

        results.append({
            "code": sym,
            "name": name,
            "industry": industry,
            "price": price,
            "pct_change": round(pct, 2),
            "amount": round(amount, 2),
            "total_score": total_with_entry,  # 使用含入场时机的总分
            "raw_score": total,                # 原始分
            "entry_bonus": entry_bonus,         # 入场加减分
            "flow_score": flow_score,
            "sector_score": sector_score,
            "trend_score": round(trend_score, 2),
            "trend_quality_score": round(trend_quality_score, 2),
            "trend_persistence_score": round(trend_persistence_score, 2),
            "ma20_slope_score": round(ma20_slope_score, 2),
            "ma20_distance_score": round(ma20_distance_score, 2),
            "volume_score": round(volume_score, 2),
            "dmi_score": round(dmi_score, 2),
            "macd_score": round(macd_score, 2),
            "expma_score": round(expma_score, 2),
            "money_flow_score": round(money_flow_score, 2),
            "leading_score": round(leading_score, 2),
            "context_score": round(context_score, 2),
            "event_score": round(float(context.get("event_score", 0) or 0), 2),
            "event_count": int(context.get("event_count", 0) or 0),
            "event_note": context.get("event_note", ""),
            "event_titles": context.get("event_titles", ""),
            "margin_score": round(float(context.get("margin_score", 0) or 0), 2),
            "margin_balance_change_pct": round(float(context.get("margin_balance_change_pct", 0) or 0), 2),
            "margin_net_buy": round(float(context.get("margin_net_buy", 0) or 0), 2),
            "margin_note": context.get("margin_note", ""),
            "lhb_score": round(float(context.get("lhb_score", 0) or 0), 2),
            "lhb_count": int(context.get("lhb_count", 0) or 0),
            "lhb_net_buy": round(float(context.get("lhb_net_buy", 0) or 0), 2),
            "lhb_note": context.get("lhb_note", ""),
            "context_note": context.get("context_note", ""),
            "selection_reason": selection_reason,
            "watch_reason": watch_reason,
            **buy_plan,
            "tech_score": tech_score,
            "adx": round(ind.get("adx_value", 0), 1),
            "plus_di": round(ind.get("plus_di", 0), 2),
            "minus_di": round(ind.get("minus_di", 0), 2),
            "vol_ratio": round(ind.get("vol_ratio", 0), 2),
            "pdi_mdi_diff": round(ind.get("plus_di", 0) - ind.get("minus_di", 0), 2),
            "close_ma21_ratio": round(ind.get("close_ma21_ratio", 0), 6),
            "close_ma20_ratio": round(ind.get("close_ma20_ratio", 0), 6),
            "above_ma20_days_20": int(ind.get("above_ma20_days_20", 0) or 0),
            "ma20_slope_10_pct": round(ind.get("ma20_slope_10_pct", 0), 4),
            "ma20_slope_20_pct": round(ind.get("ma20_slope_20_pct", 0), 4),
            "trend_quality_pass": bool(ind.get("trend_quality_pass", False)),
            "current_above_ma20": bool(ind.get("current_above_ma20", False)),
            "ma20_not_overheated": bool(ind.get("ma20_not_overheated", False)),
            "ma3_ma5_ratio": round(ind.get("ma3_ma5_ratio", 0), 6),
            "expma_ratio": round(ind.get("expma_ratio", 0), 6),
            "macd_diff": round(ind.get("macd_diff", 0), 6),
            "macd_dea": round(ind.get("macd_dea", 0), 6),
            "macd_hist": round(ind.get("macd_hist", 0), 6),
            "main_net_amount": round(total_inflow, 2),
            "main_net_ratio": round(total_inflow / amount, 6) if amount > 0 else 0,
            "sector_rank_pct": round(sector_rank_pct, 4) if not np.isnan(sector_rank_pct) else np.nan,
            "stock_rank_in_sector": round(stock_rank_in_sector, 4) if not np.isnan(stock_rank_in_sector) else np.nan,
            "amount_ok": bool(flags.get("amount_ok", False)) if hasattr(flags, "get") else False,
            "fund_ok": bool(flags.get("fund_ok", False)) if hasattr(flags, "get") else False,
            "sector_hot": bool(flags.get("sector_hot", False)) if hasattr(flags, "get") else False,
            "leading_stock": bool(flags.get("leading_stock", False)) if hasattr(flags, "get") else False,
            "consecutive_up": consecutive_up,
            "consecutive_down": consecutive_down,
            "entry_label": entry_label,
            "planned_holding_days": int(exit_plan.get("planned_holding_days", 5) or 5),
            "stop_loss_price": round(float(exit_plan.get("stop_loss_price", 0) or 0), 2),
            "take_profit_1_price": round(float(exit_plan.get("take_profit_1_price", 0) or 0), 2),
            "take_profit_2_price": round(float(exit_plan.get("take_profit_2_price", 0) or 0), 2),
            "trailing_stop_price": round(float(exit_plan.get("trailing_stop_price", 0) or 0), 2),
            "risk_reward_ratio": round(float(exit_plan.get("risk_reward_ratio", 0) or 0), 2),
            "exit_strategy": exit_plan.get("exit_strategy", ""),
            "exit_signal": exit_plan.get("exit_signal", ""),
            "exit_note": exit_plan.get("exit_note", ""),
            "day1_stop_loss_price": round(float(exit_plan.get("day1_stop_loss_price", 0) or 0), 2),
            "day1_take_profit_price": round(float(exit_plan.get("day1_take_profit_price", 0) or 0), 2),
            "day1_exit_plan": exit_plan.get("day1_exit_plan", ""),
            "day2_stop_loss_price": round(float(exit_plan.get("day2_stop_loss_price", 0) or 0), 2),
            "day2_take_profit_price": round(float(exit_plan.get("day2_take_profit_price", 0) or 0), 2),
            "day2_exit_plan": exit_plan.get("day2_exit_plan", ""),
            "day3_stop_loss_price": round(float(exit_plan.get("day3_stop_loss_price", 0) or 0), 2),
            "day3_take_profit_price": round(float(exit_plan.get("day3_take_profit_price", 0) or 0), 2),
            "day3_exit_plan": exit_plan.get("day3_exit_plan", ""),
        })

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values("total_score", ascending=False).reset_index(drop=True)
        df.index = df.index + 1
    return df
