#!/usr/bin/env python3
"""
K线选股模型 - 主入口
结合资金净流入、板块领涨、技术面指标，每日从A股精选 Top 10

自动检测交易日：若今日非开盘日，推送最近一个交易日的推荐

用法:
    python main.py                       # 正常运行（选股）
    python main.py --test 200            # 测试模式（只扫描200只股票）
    python main.py --top 20              # 输出前20只
    python main.py --no-save             # 不保存CSV文件
    python main.py --backtest            # 回测模式（验证历史表现）
    python main.py --backtest --start 2025-06-01 --end 2026-06-01
"""

import argparse
import datetime
import os
import sys

import pandas as pd

import config as cfg
from screener import run_screening, compare_modes
from backtest import run_backtest, run_backtest_from_csv, print_report
from prediction_evaluator import run_prediction_evaluation
from report_generator import generate_pick_reports
from frontend_exporter import export_frontend_data
from utils import history_output_path, output_path


def check_trading_status(spot_df):
    """
    检测当前是否开盘日，返回 (实际交易日, 状态描述)
    状态: 'open' 今日开盘, 'closed' 已收盘, 'holiday' 非交易日
    """
    today = datetime.date.today()
    now = datetime.datetime.now()

    # 检查是否是周末
    if today.weekday() >= 5:
        # 找到最近一个周五
        days_since_friday = today.weekday() - 4
        last_trading = today - datetime.timedelta(days=days_since_friday)
        return last_trading, "weekend"

    # 检查交易时间 (9:30-15:00)
    market_open = datetime.time(9, 30)
    market_close = datetime.time(15, 0)
    current_time = now.time()

    if current_time < market_open:
        # 还没开盘，检查昨天是否有数据
        yesterday = today - datetime.timedelta(days=1)
        if yesterday.weekday() >= 5:
            yesterday = today - datetime.timedelta(days=today.weekday() - 4)
        return yesterday, "pre_market"
    elif current_time > market_close:
        return today, "closed"
    else:
        return today, "open"

    return today, "open"


def print_header(trade_date, status):
    """打印程序标头"""
    print()
    print("=" * 80)
    print(f"  📈 K线选股模型 — 每日精选 Top {cfg.TOP_N}")
    today = datetime.date.today()

    if status == "open":
        print(f"  📅 今日 {trade_date.strftime('%Y年%m月%d日')} 盘中（数据可能不完整）")
    elif status == "closed":
        print(f"  📅 {trade_date.strftime('%Y年%m月%d日')} 收盘后")
    elif status == "weekend":
        print(f"  📅 今日周末休市 → 推送最近交易日: {trade_date.strftime('%Y年%m月%d日')}")
    elif status == "pre_market":
        print(f"  📅 今日尚未开盘 → 推送上一交易日: {trade_date.strftime('%Y年%m月%d日')}")
    else:
        print(f"  📅 {trade_date.strftime('%Y年%m月%d日')}")

    print(f"  ⏰ 运行时间: {datetime.datetime.now().strftime('%H:%M:%S')}")
    print(f"  📊 扫描范围: 沪深主板")
    print("=" * 80)
    print()


def print_results(df, trade_date=None, status="closed"):
    """格式化输出选股结果"""
    if df.empty:
        print("\n  ❌ 未筛选出符合条件的股票")
        print("  💡 建议：检查市场环境，或适当放宽 config.py 中的筛选条件")
        return

    if trade_date is None:
        trade_date = datetime.date.today()

    print()
    print(f"  ⚠️ 以下基于 {trade_date.strftime('%Y-%m-%d')} 收盘数据" if status != "open" else
          f"  ⚠️ 盘中数据（{trade_date.strftime('%Y-%m-%d')}），收盘后会更新")
    print()

    print("-" * 170)
    header = (
        f"{'排名':<4} {'代码':<10} {'名称':<8} {'现价':<7} {'总分':<6} {'趋势':<6} {'DMI':<6} "
        f"{'量能':<6} {'MACD':<6} {'EXPMA':<6} {'资金':<6} {'板块':<6} {'领涨':<6} "
        f"{'涨跌幅':<7} {'ADX':<6} {'PDI/MDI':<13} {'量比':<5} {'入场时机':<20}"
    )
    print(header)
    print("-" * 170)

    for _, row in df.iterrows():
        rank = row.name if isinstance(row.name, int) else _ + 1
        code = row["code"]
        name = row["name"]
        price = row.get("price", 0)
        total = row["total_score"]
        pct = row["pct_change"]
        adx = row["adx"]
        pdi = row.get("plus_di", 0)
        mdi = row.get("minus_di", 0)
        vol = row["vol_ratio"]
        entry_label = row.get("entry_label", "")
        trend_score = row.get("trend_score", 0)
        dmi_score = row.get("dmi_score", 0)
        volume_score = row.get("volume_score", 0)
        macd_score = row.get("macd_score", 0)
        expma_score = row.get("expma_score", 0)
        money_flow_score = row.get("money_flow_score", row.get("flow_score", 0))
        sector_score = row.get("sector_score", 0)
        leading_score = row.get("leading_score", 0)

        # 涨跌幅
        pct_str = f"{pct:+.2f}%"
        if pct > 3:
            pct_str = f"↑{pct_str}"
        elif pct > 0:
            pct_str = f"↗{pct_str}"
        elif pct < -3:
            pct_str = f"↓{pct_str}"
        elif pct < 0:
            pct_str = f"↘{pct_str}"

        pdi_mdi = f"{pdi:.1f}/{mdi:.1f}"
        print(
            f"{rank:<4} {code:<10} {name:<8} {price:<7.2f} {total:<6.1f} {trend_score:<6.1f} {dmi_score:<6.1f} "
            f"{volume_score:<6.1f} {macd_score:<6.1f} {expma_score:<6.1f} {money_flow_score:<6.1f} "
            f"{sector_score:<6.1f} {leading_score:<6.1f} {pct_str:<7} {adx:<6.1f} {pdi_mdi:<13} "
            f"{vol:<5.2f} {entry_label:<20}"
        )

    print("-" * 170)
    print()

    # 摘要
    print("📊 选股摘要:")
    print(f"   入选总数: {len(df)} 只")
    if not df.empty:
        print(f"   🥇 最高分: {df['total_score'].max():.1f} — {df.iloc[0]['name']}({df.iloc[0]['code']})")
        # 入场时机统计
        best_entry = sum(1 for _, r in df.iterrows() if '最佳入场' in str(r.get('entry_label', '')))
        good_entry = sum(1 for _, r in df.iterrows() if '适合入场' in str(r.get('entry_label', '')))
        if best_entry:
            print(f"   🟢 最佳入场时机: {best_entry} 只")
        if good_entry:
            print(f"   🟢 适合入场: {good_entry} 只")
        avoid = sum(1 for _, r in df.iterrows() if '追高' in str(r.get('entry_label', '')))
        if avoid:
            print(f"   🟠 追高风险: {avoid} 只（排名已降权）")
    print()


def save_results(df, trade_date=None):
    """保存结果到CSV + 追加到历史汇总文件"""
    if trade_date is None:
        trade_date = datetime.date.today()
    date_str = trade_date.strftime("%Y%m%d")

    # ---- 1. 保存唯一当日结果CSV（最终筛选股票详情） ----
    filename = output_path(f"stock_pick_{date_str}.csv", trade_date)
    save_cols = [
        "code", "name", "industry", "price", "pct_change", "amount",
        "total_score", "raw_score", "entry_bonus",
        "flow_score", "sector_score", "tech_score",
        "trend_score", "volume_score", "dmi_score", "macd_score",
        "expma_score", "money_flow_score", "leading_score",
        "trend_quality_score", "trend_persistence_score",
        "ma20_slope_score", "ma20_distance_score",
        "adx", "plus_di", "minus_di", "pdi_mdi_diff", "vol_ratio",
        "close_ma21_ratio", "close_ma20_ratio",
        "above_ma20_days_20", "ma20_slope_10_pct", "ma20_slope_20_pct",
        "trend_quality_pass", "current_above_ma20", "ma20_not_overheated",
        "ma3_ma5_ratio", "expma_ratio",
        "macd_diff", "macd_dea", "macd_hist",
        "main_net_amount", "main_net_ratio",
        "sector_rank_pct", "stock_rank_in_sector",
        "amount_ok", "fund_ok", "sector_hot", "leading_stock",
        "consecutive_up", "consecutive_down",
        "entry_label",
        "planned_holding_days", "stop_loss_price",
        "take_profit_1_price", "take_profit_2_price",
        "trailing_stop_price", "risk_reward_ratio",
        "exit_strategy", "exit_signal", "exit_note",
        "day1_stop_loss_price", "day1_take_profit_price", "day1_exit_plan",
        "day2_stop_loss_price", "day2_take_profit_price", "day2_exit_plan",
        "day3_stop_loss_price", "day3_take_profit_price", "day3_exit_plan",
    ]
    available = [c for c in save_cols if c in df.columns]
    result_df = df[available].copy()
    result_df.insert(0, "rank", range(1, len(result_df) + 1))
    result_df.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"💾 当日筛选结果: {filename}")

    # ---- 2. 追加到历史汇总（回测直接读这个文件） ----
    history_file = history_output_path("daily_picks_history.csv")
    # 加入交易日字段
    df_save = df[available].copy()
    df_save.insert(0, "trade_date", trade_date.strftime("%Y-%m-%d"))

    if os.path.exists(history_file):
        # 检查是否已有该日数据，避免重复
        existing = pd.read_csv(history_file)
        if trade_date.strftime("%Y-%m-%d") in existing["trade_date"].values:
            pass
        else:
            existing = pd.concat([existing, df_save], ignore_index=True)
            existing.to_csv(history_file, index=False, encoding="utf-8-sig")
    else:
        df_save.to_csv(history_file, index=False, encoding="utf-8-sig")

    return filename


def sync_frontend_data():
    """把已有输出同步给前端页面。失败不影响主流程。"""
    try:
        manifest = export_frontend_data()
        print("💾 前端数据已同步:")
        print(f"   index: {manifest['index']}")
        print(f"   reports: {manifest['report_count']} 个交易日")
    except Exception as exc:
        print(f"⚠️ 前端数据同步失败: {exc}")


def main():
    parser = argparse.ArgumentParser(
        description="K线选股模型 — A股每日精选",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--test", type=int, default=None, metavar="N",
        help="测试模式：只扫描前N只股票（加快速度）"
    )
    parser.add_argument(
        "--top", type=int, default=cfg.TOP_N, metavar="N",
        help=f"输出前N只股票（默认: {cfg.TOP_N}）"
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="不保存CSV结果文件"
    )
    parser.add_argument(
        "--backtest", action="store_true",
        help="回测模式：用历史数据验证选股模型胜率"
    )
    parser.add_argument(
        "--start", type=str, default=None, metavar="DATE",
        help="回测起始日期 (YYYY-MM-DD)，默认一年前"
    )
    parser.add_argument(
        "--end", type=str, default=None, metavar="DATE",
        help="回测结束日期 (YYYY-MM-DD)，默认今天"
    )
    parser.add_argument(
        "--hold", type=str, default="5,10,20", metavar="DAYS",
        help="回测持有天数，逗号分隔 (默认: 5,10,20)"
    )
    parser.add_argument(
        "--from-csv", action="store_true",
        help="快速回测：从 daily_picks_history.csv 读取，秒出结果（不重跑模型）"
    )
    parser.add_argument(
        "--evaluate", action="store_true",
        help="评估历史选股未来表现，输出预测准确性报告"
    )
    parser.add_argument(
        "--report", action="store_true",
        help="从已有 stock_pick CSV 生成美化 Excel/HTML 报告"
    )
    parser.add_argument(
        "--report-picks", type=str, default=None,
        help="指定用于生成报告的 stock_pick CSV"
    )
    parser.add_argument(
        "--no-report", action="store_true",
        help="正常选股保存CSV后不自动生成Excel/HTML报告"
    )
    parser.add_argument(
        "--export-frontend", action="store_true",
        help="仅把已有 output 结果同步到前端 public/data，不重新扫描选股"
    )
    parser.add_argument(
        "--no-frontend-export", action="store_true",
        help="本次运行结束后不自动同步前端数据"
    )
    parser.add_argument(
        "--eval-picks", type=str, default=None,
        help="评估指定选股CSV，默认 output/_history/daily_picks_history.csv"
    )
    parser.add_argument(
        "--eval-hold", type=str, default="3,5,10,20",
        help="评估持有天数，逗号分隔（默认: 3,5,10,20）"
    )
    parser.add_argument(
        "--eval-kline-cache", type=str, default=None,
        help="评估时指定K线parquet缓存文件"
    )
    parser.add_argument(
        "--eval-fetch-missing", action="store_true",
        help="评估时自动补取缺失K线数据"
    )
    parser.add_argument(
        "--mode", choices=["strict", "normal", "loose"], default=cfg.SCREEN_MODE,
        help="筛选模式：strict/normal/loose（默认 normal）"
    )
    parser.add_argument(
        "--compare-modes", action="store_true",
        help="一次性比较 strict/normal/loose 三种模式的技术通过数量"
    )
    parser.add_argument(
        "--refresh-cache", action="store_true",
        help="忽略当日缓存，重新获取股票列表和K线"
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="本次运行不读取也不写入当日缓存"
    )
    parser.add_argument(
        "--no-money-flow-api", action="store_true",
        help="跳过东方财富资金流API，直接用K线量价估算资金流"
    )

    args = parser.parse_args()
    cfg.SCREEN_MODE = args.mode
    if args.refresh_cache:
        cfg.FORCE_REFRESH_CACHE = True
    if args.no_cache:
        cfg.USE_DAILY_CACHE = False
    if args.no_money_flow_api:
        cfg.USE_MONEY_FLOW_API = False

    if args.export_frontend:
        sync_frontend_data()
        return 0

    if args.compare_modes:
        print(f"筛选模式对比（当前默认: {cfg.SCREEN_MODE}）")
        print(f"当日缓存: {'关闭' if not cfg.USE_DAILY_CACHE else ('强制刷新' if cfg.FORCE_REFRESH_CACHE else '开启')}")
        compare_modes(max_stocks=args.test, verbose=True)
        return 0

    if args.evaluate:
        run_prediction_evaluation(
            picks_path=args.eval_picks,
            hold_days=args.eval_hold,
            kline_cache=args.eval_kline_cache,
            fetch_missing=args.eval_fetch_missing,
        )
        if not args.no_frontend_export:
            sync_frontend_data()
        return 0

    if args.report:
        manifest = generate_pick_reports(
            trade_date=None,
            picks_path=args.report_picks,
        )
        print("💾 报告输出:")
        for label in ["excel", "html", "pdf"]:
            if manifest.get(label):
                print(f"   {label}: {manifest[label]}")
        if not args.no_frontend_export:
            sync_frontend_data()
        return 0

    # ---- 回测模式 ----
    if args.backtest:
        hold_days = [int(d.strip()) for d in args.hold.split(",")]

        if args.from_csv:
            # 快速回测：从已保存的CSV读取
            history_csv = history_output_path("daily_picks_history.csv")
            report = run_backtest_from_csv(history_csv, hold_days)
        else:
            # 完整回测：重新模拟每天选股
            print()
            print("=" * 70)
            print("  📊 K线选股模型 — 历史回测")
            print("=" * 70)
            print()
            report = run_backtest(
                start_date=args.start,
                end_date=args.end,
                hold_days_list=hold_days,
                code_limit=args.test,
            )
        print_report(report)

        if report.get("output_files"):
            print("💾 回测输出文件:")
            for label, path in report["output_files"].items():
                print(f"   {label}: {path}")
        return 0

    # ---- 正常选股模式 ----
    if args.top != cfg.TOP_N:
        cfg.TOP_N = args.top

    # 检测交易日状态
    trade_date, status = check_trading_status(None)  # 先做基本判断
    print_header(trade_date, status)
    print(f"筛选模式: {cfg.SCREEN_MODE}")
    print(f"当日缓存: {'关闭' if not cfg.USE_DAILY_CACHE else ('强制刷新' if cfg.FORCE_REFRESH_CACHE else '开启')}")
    if not cfg.USE_MONEY_FLOW_API:
        print("资金流API: 关闭（使用K线量价估算）")
    print()

    # 运行选股
    df = run_screening(
        verbose=True,
        max_stocks=args.test,
    )

    # 输出结果（标注实际交易日）
    print_results(df.head(cfg.TOP_N), trade_date, status)

    # 保存结果（文件名用实际交易日）
    if not args.no_save and not df.empty:
        csv_path = save_results(df, trade_date)
        if not args.no_report:
            manifest = generate_pick_reports(df, trade_date=trade_date, picks_path=csv_path)
            print("💾 可视化报告:")
            for label in ["excel", "html", "pdf"]:
                if manifest.get(label):
                    print(f"   {label}: {manifest[label]}")
        if not args.no_frontend_export:
            sync_frontend_data()

    return 0


if __name__ == "__main__":
    sys.exit(main())
