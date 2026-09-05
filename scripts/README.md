# scripts 数据工程目录

本目录收**数据抓取/导出类脚本**：指数成分股、K 线抓取、stockdb 行情导出，
结构与原 `agent/scripts/` 一致（`lib/` 可复用原语 + `run/` 任务胶水 + 平铺的独立工具）。
agent 自身的开发与能力维护脚本保留在 `agent/scripts/`（见其 README）。

## 目录结构

```text
scripts/
├── dev/                          # 仓库原有：开发环境快捷入口（bash）
├── README.md
├── export_stockdb_ashare.py      # 独立工具：stockdb A 股日线 → data-bridge Parquet
├── lib/                          # 可复用原语
│   ├── fetch_kline.py            # 通用 K 线抓取（复用 Vibe-Trading 数据层 fetch_data_map）
│   └── get_csi300_constituents.py# 指数历史成分股（baostock 主源）
└── run/
    └── run_fetch_csi300_kline.py # 任务胶水：成分 + K 线 + 覆盖率报告
```

目录约定：

- `lib/`：可复用原语，一个脚本只做一件事。
- `run/`：任务胶水，把多个 `lib` 原语串成具体任务。
- 平铺的 `.py`：独立工具（不依赖 `lib/`）。

## 环境要求

统一使用 Vibe-Trading 自带 venv（`fetch_kline.py` 依赖 agent 数据层时自己把
`<repo>/agent` 加入 sys.path；也可用环境变量 `VIBE_TRADING_SRC` 覆盖仓库根）：

```powershell
E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe -m pip install baostock pyarrow
```

## 脚本说明

### export_stockdb_ashare.py

把本地 stockdb 服务（`127.0.0.1:7899`）的沪深 A 股日线导出为 data-bridge 可读的
Parquet 数据仓：全字段保留（OHLC/pre_close/volume/amount/turnover/float_share/
float_mv/is_st 等 21 列 + 后复权 4 列，后复权与 stockdb SDK `fq="hfq"` 逐位一致），
另导出交易日历、证券生命周期（含退市）、申万一级行业与 manifest 版本。幂等可重建，
支持前缀分片、`--limit` / `--codes-file`（断点续跑）。

```powershell
PYTHONPATH=E:/data/free-stockdb-windows-v0.3.2-more-power/stockdb/pybao `
  E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe scripts/export_stockdb_ashare.py `
  --out data/stockdb_ashare --start 20110101
```

### lib/fetch_kline.py

通用 K 线抓取，逐标的调用 `fetch_data_map`（腾讯 -> 东财 -> baostock 等兜底链），
单标的失败不中断整批，失败清单落盘；支持 `--append` 增量补齐头尾缺口。
输出 `out_dir/kline/<code>.parquet` + `manifest.json`。

```powershell
E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe scripts/lib/fetch_kline.py --codes 600519.SH,000001.SZ --start-date 2025-01-01 --end-date 2025-12-31 --out-dir C:/tmp/kline --source auto
```

### lib/get_csi300_constituents.py

获取指数历史成分股（沪深300 默认，中证500/上证50 用 `--index` 切换），baostock 主源、
akshare/sina 兜底（兜底只能取最新一期，会标记近似）。输出 membership 长表
（无幸存者偏差）。`--snapshot-dates` 可覆盖候选查询日。

```powershell
E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe scripts/lib/get_csi300_constituents.py --start-date 2020-01-01 --end-date 2026-12-31 --out-dir C:/tmp/csi300
```

### run/run_fetch_csi300_kline.py

完整子任务入口：成分 membership（`get_csi300_constituents`）-> 全部历史成分并集 +
`000300.SH` 指数 -> 逐标的日 K 落库（`fetch_kline`）-> 生成 `bridge_config.yaml` 片段
与 `manifest.json` 覆盖率报告。`--append` 增量补齐、`--limit-codes N` 分批续跑。

```powershell
E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe scripts/run/run_fetch_csi300_kline.py --start-date 2020-01-01 --end-date 2026-12-31 --out-dir C:/tmp/csi300 --source auto
```

## 与 agent/scripts 的分工

- 本目录：数据抓取/导出（不参与 agent 引擎/能力运行）。
- `agent/scripts/`：agent 开发与能力维护（`w4a_run_benches`/`w4a_patch_blog`/
  `bench_performance`/`sync_backtest_capabilities`）。
- 本目录脚本如复用 agent 数据层（`fetch_kline`），会自行把 `<repo>/agent` 加入
  sys.path，不影响 `agent/scripts` 的划分。

## 已知限制

- baostock 只按候选查询日抓取成分，非 1/7 月的临时调整默认粒度会漏，可用
  `--snapshot-dates` 补齐。
- 兜底源只有"最新一期"，历史回测遇到兜底快照应视为近似数据。
- `source=auto` 的 A 股链路腾讯日线为前复权；若策略严格要求后复权，需额外校验/换源
  （`export_stockdb_ashare.py` 输出的后复权列可用于此场景）。
- `--append` 只补头尾缺口，不修复旧文件中间缺失。