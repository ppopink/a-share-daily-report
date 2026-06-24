# K线选股模型

A股每日K线规则选股系统。第一阶段每天收盘后跑规则，输出候选股；第二阶段用严格回测验证；如果规则稳定，再把规则特征导出给模型做预测选股。

## 选股逻辑

### 技术指标配置

| 指标 | 参数 | 必选条件 |
|------|------|----------|
| 均线 MA | 3, 5, 21 日 | **close > MA3 > MA5 > MA21** |
| DMI | 7, 6 | **+DI > -DI 且 ADX > 25** |
| EXPMA | 7, 21 日 | **近3日金叉**（EXPMA7上穿EXPMA21） |
| MACD | 6, 13, 5 | **最近一次进入零轴上方区域后的二次金叉，近3日触发** |
| 成交量 | 前5日均量 | **当日成交量 > 前5日均量 × 1.3** |
| 趋势持续性 | MA20 | 最近20日多数站上MA20 + MA20斜率向上 + 股价不过度偏离MA20 |

### 趋势持续性优化

为减少只靠单日金叉造成的噪声，系统新增 MA20 趋势质量指标：

- `above_ma20_days_20`：最近20日中收盘价站上MA20的天数。
- `ma20_slope_10_pct`：MA20近10日涨幅。
- `ma20_slope_20_pct`：MA20近20日涨幅。
- `close_ma20_ratio`：当前收盘价 / MA20，用于识别追高过热。

不同模式使用不同强度：

- `strict`：16/20日站上MA20，MA20近10日涨幅>=3%或近20日涨幅>=5%，且股价不超过MA20的1.15倍；作为硬过滤。
- `normal`：15/20日站上MA20，MA20近10日涨幅>=2%或近20日涨幅>=4%，且股价不超过MA20的1.18倍；主要作为排序加分。
- `loose`：14/20日站上MA20，MA20近10日涨幅>=1%或近20日涨幅>=2.5%，且股价不超过MA20的1.22倍；作为观察加分。

### 评分体系（100分）

- **资金净流入**（25分）：近5日主力净流入占成交额比例
- **板块/相对强度**（20分）：优先按行业涨幅排名评分；数据源无行业字段时退化为个股相对强度
- **技术面**（55分）：ADX强度 + MACD质量 + EXPMA乖离 + 均线多头 + 量价配合

### 硬过滤条件

1. 非ST、非停牌、非北交所，默认只保留沪深主板
2. 今日成交额 > 1亿元
3. 今日成交量 / 前5日均量 >= 1.3
4. close > MA3 > MA5 > MA21
5. EXPMA7 近3日内上穿 EXPMA21
6. MACD 6/13/5 在0轴上方区域内近3日出现二次金叉
7. +DI > -DI 且 ADX > 25
8. 主力净流入 > 0（API失败时使用量价估算）
9. 所属行业/板块涨幅排名前20%
10. 个股在板块内涨幅排名前20%

## 使用方法

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
# 正常运行（全A股扫描）
python main.py

# 测试模式（只扫描前200只，快速验证）
python main.py --test 200

# 输出前20只
python main.py --top 20

# 不保存CSV
python main.py --no-save

# 回测（默认信号次日开盘买入，扣除交易成本）
python main.py --backtest --test 500

# 评估历史选股准确性：未来3/5/10/20日收益、超额收益、评分IC
python main.py --evaluate

# 从已有选股CSV生成美化 Excel/HTML 报告
python main.py --report --report-picks output/YYYYMMDD/stock_pick_YYYYMMDD.csv

# 只评估某个选股文件，或自定义持有期
python main.py --evaluate --eval-picks output/YYYYMMDD/stock_pick_YYYYMMDD.csv --eval-hold 5,10,20

# 本地K线缓存不足时，自动补取评估所需K线
python main.py --evaluate --eval-fetch-missing
```

### 加速日常运行

程序默认开启缓存，会把当天股票列表、80 日K线和资金流保存到 `cache/`。同一天重复运行、切换 `strict/normal/loose`、调整评分或重新生成 `stock_pick_YYYYMMDD.csv` 时，会优先复用缓存，不再全市场逐只重新拉K线。

如果前一交易日已经有 K 线缓存，程序会优先用旧缓存叠加股票列表里的当日开高低收量，增量生成最新一根日K线；只有缺失或缓存太旧时才回退到接口全量获取。

```bash
# 日常收盘后运行：优先使用当日缓存
python main.py --mode normal

# 收盘数据刚更新，强制重新拉取并覆盖当日缓存
python main.py --mode normal --refresh-cache

# 排查接口或缓存问题，本次完全不用缓存
python main.py --mode normal --no-cache

# 东方财富资金流接口很慢时，跳过API并使用K线量价估算
python main.py --mode normal --no-money-flow-api

# 快速调试，只扫描前300只
python main.py --mode normal --test 300
```

### 输出

- **终端**：格式化表格，显示排名、代码、名称、各维度评分、涨跌幅
- **CSV**：自动保存到 `output/YYYYMMDD/stock_pick_YYYYMMDD.csv`
- **Excel**：自动生成 `output/YYYYMMDD/stock_pick_YYYYMMDD.xlsx`，包含摘要、选股详情、技术诊断、筛选漏斗和准确性评估。
- **HTML**：自动生成 `output/YYYYMMDD/stock_pick_report_YYYYMMDD.html`，可直接浏览 Top20、评分拆解、技术漏斗和散点图。
- **PDF**：自动生成 `output/YYYYMMDD/stock_pick_report_YYYYMMDD.pdf`，适合直接发给手机用户查看。
- **历史汇总**：跨日期汇总保存到 `output/_history/daily_picks_history.csv`

### 准确性评估输出

运行 `python main.py --evaluate` 后，会基于 T 日信号、T+1 开盘买入、持有 N 个交易日收盘卖出的口径，输出：

- `output/YYYYMMDD/prediction_accuracy_details_YYYYMMDD.csv`：每只入选股票的未来收益明细。
- `output/YYYYMMDD/prediction_accuracy_summary_YYYYMMDD.csv`：按持有期汇总胜率、平均收益、超额收益、precision@5/10/20。
- `output/YYYYMMDD/prediction_accuracy_rank_buckets_YYYYMMDD.csv`：Top1-5、Top6-10、Top11-20 分层表现。
- `output/YYYYMMDD/prediction_feature_ic_YYYYMMDD.csv`：各评分字段与未来收益/超额收益的相关性。
- `output/YYYYMMDD/prediction_accuracy_report_YYYYMMDD.json`：机器可读汇总报告。

## 配置

所有参数集中在 `config.py`，可按需调整：
- 技术指标周期
- 筛选阈值
- 评分权重
- 回测买入方式和交易成本
- API请求参数

## 运行时机

建议每个交易日**15:30后**运行（收盘后数据完整）。

## 数据源

主要使用新浪财经接口获取股票列表与日K线，使用东方财富接口获取资金流向；资金流接口不可用时，会用近5日K线量价关系做估算。无需 API Key。

## 回测可信度与限制

- 当前信号基于 T 日收盘后可获得的数据。
- 默认 T+1 开盘买入，避免 T 日收盘信号使用 T 日开盘价的未来函数问题。
- 当日资金流、板块涨幅、个股排名都只能盘后使用。
- 如果要做盘中实时选股，不能直接使用收盘后指标。
- 当前策略是规则选股，不代表真实投资收益。
- 必须考虑手续费、滑点、涨跌停、停牌、成交量不足等问题。
- 参数扫描只是稳健性检验，不应该为了最高收益反复调参。

## 真实回测假设

- 信号使用 T 日收盘后数据。
- 买入使用 T+1 开盘价，并加入滑点。
- 涨停、停牌默认无法买入。
- 跌停、停牌默认无法卖出，需要顺延。
- 每日净值为逐日盯市，持仓期间每天用收盘价计算组合市值。
- 回测结果已扣除佣金、印花税和滑点。
- 基准默认尝试读取沪深300或中证1000本地CSV数据。
- 当前仍然是历史模拟，不代表未来收益。
