"""
工具函数：进度显示、重试、日期处理、股票代码转换
"""

import time
import functools
import datetime
import os
from typing import Callable, Any


def get_market_prefix(code: str) -> str:
    """
    根据股票代码返回市场前缀（sh/sz）
    - 6xxxxx → sh（上海）
    - 0xxxxx, 3xxxxx → sz（深圳）
    - 4xxxxx, 8xxxxx → bj（北京）
    """
    if code.startswith(("4", "8")):
        return "bj"
    elif code.startswith("6"):
        return "sh"
    else:
        return "sz"


def code_to_ak_symbol(code: str) -> str:
    """将纯数字代码转换为带市场前缀格式（如 '000001' → 'sz000001'）"""
    return f"{get_market_prefix(code)}{code}"


def retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    重试装饰器
    - max_retries: 最大重试次数
    - delay: 初始等待时间（秒）
    - backoff: 退避倍数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            _delay = delay
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        time.sleep(_delay)
                        _delay *= backoff
            raise last_exception  # type: ignore
        return wrapper
    return decorator


def progress_bar(current: int, total: int, prefix: str = "", suffix: str = "", length: int = 40):
    """命令行进度条"""
    if total == 0:
        return
    percent = current / total
    filled = int(length * percent)
    bar = "█" * filled + "░" * (length - filled)
    print(f"\r{prefix} |{bar}| {percent:.1%} {suffix}", end="", flush=True)
    if current >= total:
        print()


def get_recent_trading_dates(n_days: int = 80) -> list:
    """估算近N个交易日对应的日历日期范围（含容错余量）"""
    today = datetime.date.today()
    # 考虑周末和节假日，多回溯 ~40% 的日历天数
    calendar_days = int(n_days * 1.6)
    start = today - datetime.timedelta(days=calendar_days)
    return [start.strftime("%Y%m%d"), today.strftime("%Y%m%d")]


def safe_float(value, default=0.0) -> float:
    """安全转换为 float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0) -> int:
    """安全转换为 int"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def date_key(trade_date=None) -> str:
    """把日期统一转换为 YYYYMMDD。"""
    if trade_date is None:
        trade_date = datetime.date.today()
    if isinstance(trade_date, str):
        text = trade_date.strip()
        if len(text) >= 8 and text[:8].isdigit():
            return text[:8]
        return datetime.datetime.strptime(text[:10], "%Y-%m-%d").strftime("%Y%m%d")
    if isinstance(trade_date, datetime.datetime):
        return trade_date.strftime("%Y%m%d")
    return trade_date.strftime("%Y%m%d")


def output_day_dir(trade_date=None) -> str:
    """返回某个日期的输出目录：output/YYYYMMDD。"""
    import config as cfg

    path = os.path.join(cfg.OUTPUT_DIR, date_key(trade_date))
    os.makedirs(path, exist_ok=True)
    return path


def output_path(filename: str, trade_date=None) -> str:
    """返回某个日期目录下的输出文件路径。"""
    return os.path.join(output_day_dir(trade_date), filename)


def history_output_dir() -> str:
    """跨日期汇总文件目录。"""
    import config as cfg

    path = os.path.join(cfg.OUTPUT_DIR, "_history")
    os.makedirs(path, exist_ok=True)
    return path


def history_output_path(filename: str) -> str:
    return os.path.join(history_output_dir(), filename)
