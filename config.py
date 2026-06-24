"""
K线选股模型 - 配置文件
所有可调参数集中管理
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 技术指标参数
# ============================================================

# 均线周期
MA_PERIODS = [3, 5, 21]

# 趋势持续性参数：避免只看单日金叉，优先寻找中期趋势稳步抬升的股票
TREND_MA_PERIOD = 20
TREND_LOOKBACK_DAYS = 20
TREND_STRICT_ABOVE_DAYS = 16
TREND_NORMAL_ABOVE_DAYS = 15
TREND_LOOSE_ABOVE_DAYS = 14
TREND_STRICT_SLOPE10_PCT = 3.0
TREND_NORMAL_SLOPE10_PCT = 2.0
TREND_LOOSE_SLOPE10_PCT = 1.0
TREND_STRICT_SLOPE20_PCT = 5.0
TREND_NORMAL_SLOPE20_PCT = 4.0
TREND_LOOSE_SLOPE20_PCT = 2.5
TREND_STRICT_MAX_CLOSE_MA20_RATIO = 1.15
TREND_NORMAL_MAX_CLOSE_MA20_RATIO = 1.18
TREND_LOOSE_MAX_CLOSE_MA20_RATIO = 1.22

# DMI 参数 (周期, ADX平滑周期)
DMI_PERIOD = 7
ADX_PERIOD = 6
ADX_THRESHOLD = 25  # ADX 最低阈值

# EXPMA 参数
EXPMA_FAST = 7
EXPMA_SLOW = 21
EXPMA_CROSS_DAYS = 3  # 金叉允许在近N日内发生

# MACD 参数 (快线, 慢线, 信号线)
MACD_FAST = 6
MACD_SLOW = 13
MACD_SIGNAL = 5
MACD_CROSS_DAYS = 3  # 二次金叉允许在近N日内发生

# 成交量参数
VOL_MA_PERIOD = 5  # 均量周期
VOL_RATIO_MIN = 1.3  # 最低量比
VOL_RATIO_OPTIMAL_LOW = 1.3  # 最优量比下限
VOL_RATIO_OPTIMAL_HIGH = 2.0  # 最优量比上限

# ============================================================
# 数据获取参数
# ============================================================

# 历史K线回溯天数（需足够计算所有指标）
HISTORY_DAYS = 80

# 并发获取数据的线程数
MAX_WORKERS = 2

# 当日数据缓存：同一天重复运行时复用股票列表和K线，显著缩短调参/出报告时间
USE_DAILY_CACHE = True
FORCE_REFRESH_CACHE = False
CACHE_DIR = os.path.join(BASE_DIR, "cache")
INCREMENTAL_KLINE_UPDATE = True
MAX_INCREMENTAL_CACHE_AGE_DAYS = 5
USE_MONEY_FLOW_CACHE = True
USE_MONEY_FLOW_API = True
MONEY_FLOW_API_TIMEOUT = 5
MONEY_FLOW_API_RETRIES = 1
MONEY_FLOW_MAX_WORKERS = 6
MONEY_FLOW_PROGRESS_INTERVAL = 10
MONEY_FLOW_TOTAL_TIMEOUT = 45
USE_HOT_SECTOR_API = True
HOT_SECTOR_TOP_N = 8
HOT_SECTOR_API_TIMEOUT = 8

# API请求间隔（秒）
REQUEST_DELAY = 0.25

# 请求重试次数
MAX_RETRIES = 3

# 回测成交成本（买卖合计，单位：百分比）
BACKTEST_TRADE_COST_PCT = 0.15

# 回测买入方式：next_open=信号次日开盘买入，same_close=信号当日收盘买入
BACKTEST_BUY_MODE = "next_open"

# 真实成交模型
INITIAL_CASH = 1_000_000
COMMISSION_RATE = 0.0003
STAMP_TAX_RATE = 0.0005
SLIPPAGE_RATE = 0.001
MIN_BUY_AMOUNT = 100_000_000
LIMIT_UP_PCT = 0.098
LIMIT_DOWN_PCT = 0.098

# 持仓和资金分配
MAX_HOLDINGS = 10
POSITION_SIZE_MODE = "equal_weight"
MAX_POSITION_PCT = 0.1

# 基准数据：优先读取本地CSV，缺失时回测中保留空基准列
BENCHMARK_CODE = "沪深300"
BENCHMARK_CSV = os.path.join(BASE_DIR, "data", "benchmark.csv")

# ============================================================
# 筛选条件
# ============================================================

SCREEN_MODE = "normal"  # strict / normal / loose

# 过滤条件
EXCLUDE_ST = True  # 排除ST
EXCLUDE_NEW = True  # 排除上市不足60日新股
EXCLUDE_BJ = True  # 排除北交所
MAIN_BOARD_ONLY = True  # 只要沪深主板（排除科创板688/创业板300/301/中小板002/003）
MIN_LISTING_DAYS = 60
MIN_AMOUNT = 100_000_000  # 最低成交额：1亿元

# 提示词第一版硬过滤：资金净流入、板块热度、板块内领涨
REQUIRE_POSITIVE_MONEY_FLOW = True
REQUIRE_SECTOR_HOT = True
REQUIRE_LEADING_IN_SECTOR = True
SECTOR_HOT_TOP_PCT = 0.20
LEADING_STOCK_TOP_PCT = 0.20

# ============================================================
# 评分权重（总和100）
# ============================================================

WEIGHT_CAPITAL_FLOW = 25   # 资金净流入权重
WEIGHT_SECTOR_LEAD = 20    # 板块领涨权重
WEIGHT_TECHNICAL = 55      # 技术面权重

# 技术面子项权重（占技术面55分的分配）
TECH_ADX_WEIGHT = 15       # ADX强度
TECH_MACD_WEIGHT = 15      # MACD质量
TECH_EXPMA_WEIGHT = 10     # EXPMA乖离
TECH_MA_WEIGHT = 10        # 均线多头
TECH_VOLUME_WEIGHT = 5     # 量价配合

# ============================================================
# 资金流向参数
# ============================================================

# 计算资金净流入的天数
FLOW_LOOKBACK_DAYS = 5

# ============================================================
# 输出配置
# ============================================================

TOP_N = 20  # 最终输出的股票数量
OUTPUT_DIR = os.path.join(BASE_DIR, "output")  # CSV输出目录

# ============================================================
# 板块领涨参数
# ============================================================

# 板块涨幅排名阈值
SECTOR_RANK_TOP3_SCORE = 20
SECTOR_RANK_TOP10_SCORE = 15
SECTOR_RANK_TOP20_SCORE = 10
SECTOR_RANK_OTHER_SCORE = 5

# 没有行业/板块数据时，是否退化为个股相对强度评分
SECTOR_FALLBACK_TO_RELATIVE_STRENGTH = True
