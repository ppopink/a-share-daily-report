# 本地自动运行说明

本目录用于在本机 Mac 上定时生成并发布 A 股每日选股报告。

## 定时计划

- 周一到周五 14:30：盘中预览版 `intraday`
- 周一到周五 16:00：收盘正式版 `close`

自动任务会执行：

1. 运行 `python main.py --mode normal --refresh-cache`
2. 生成 CSV / HTML / PDF / 前端 JSON
3. `git add .`
4. `git commit`
5. `git push origin main`
6. GitHub Pages 自动部署

## 首次安装

在项目根目录执行：

```bash
chmod +x automation/install_launchd.sh automation/uninstall_launchd.sh automation/run_auto_report.py
automation/install_launchd.sh
```

## 手动测试

只测试流程、不推送：

```bash
/usr/bin/python3 automation/run_auto_report.py --run-type intraday --test 50 --skip-push
```

只打印将要执行的动作：

```bash
/usr/bin/python3 automation/run_auto_report.py --run-type close --dry-run
```

## 查看日志

```bash
tail -f automation/logs/intraday.log
tail -f automation/logs/close.log
tail -f automation/logs/intraday.err.log
tail -f automation/logs/close.err.log
```

## 查看任务是否加载

```bash
launchctl print gui/$(id -u) | grep com.ppopink.ashare
```

## 卸载定时任务

```bash
automation/uninstall_launchd.sh
```

## 注意事项

- 电脑需要在对应时间开机并联网。
- 14:30 是盘中预览，不应当等同于收盘确认信号。
- 16:00 正式版默认强制刷新缓存，避免复用 14:30 的盘中 K 线。
- 周末自动跳过；A股节假日如果行情源返回异常，日志和 `public/data/automation_status.json` 会记录失败原因。
