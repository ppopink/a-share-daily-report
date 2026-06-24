
  # A股每日选股报告页面设计

  This is a code bundle for A股每日选股报告页面设计. The original project is available at https://www.figma.com/design/iNoAVfQ9fXYujKxYPphpps/A%E8%82%A1%E6%AF%8F%E6%97%A5%E9%80%89%E8%82%A1%E6%8A%A5%E5%91%8A%E9%A1%B5%E9%9D%A2%E8%AE%BE%E8%AE%A1.

  ## Running the code

  Run `npm i` to install the dependencies.

  Run `npm run dev` to start the development server.

## 连接本地选股系统

后端选股程序会把 `output/YYYYMMDD` 中的 CSV、Excel、HTML、PDF 和准确率评估同步到：

- `public/data/report_index.json`
- `public/data/reports/YYYYMMDD.json`
- `public/data/backtest.json`
- `public/reports/YYYYMMDD/`

正常每日运行：

```bash
cd /Users/lisijia/Desktop/k线选股
python main.py
```

如果不想重新扫描，只想把已有 output 结果同步到前端：

```bash
cd /Users/lisijia/Desktop/k线选股
python main.py --export-frontend
```

启动前端：

```bash
cd /Users/lisijia/Desktop/k线选股/A股每日选股报告页面设计
npm i
npm run dev
```

页面会优先读取真实 JSON；如果还没有同步数据，会自动回落到演示数据。

## GitHub Pages 每日更新

本项目已经内置 GitHub Pages 自动部署工作流：

```text
../.github/workflows/deploy-pages.yml
```

第一次使用：

1. 在 GitHub 新建一个仓库，例如 `a-share-daily-report`。
2. 在本地项目根目录初始化并提交：

```bash
cd /Users/lisijia/Desktop/k线选股
git init
git add .
git commit -m "init daily stock report"
git branch -M main
git remote add origin https://github.com/你的用户名/a-share-daily-report.git
git push -u origin main
```

3. 打开 GitHub 仓库 `Settings -> Pages`，Source 选择 `GitHub Actions`。
4. 等 Actions 运行完成，页面地址通常是：

```text
https://你的用户名.github.io/a-share-daily-report/
```

每天更新：

```bash
cd /Users/lisijia/Desktop/k线选股
python main.py
git add A股每日选股报告页面设计/public
git commit -m "update daily report $(date +%Y%m%d)"
git push
```

如果当天已经跑过选股，只想重新同步前端：

```bash
python main.py --export-frontend
git add A股每日选股报告页面设计/public
git commit -m "update frontend data $(date +%Y%m%d)"
git push
```
  
