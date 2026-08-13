# agent/scripts 数据抓取脚本

本目录用于把“沪深300 历史成分股 + 全成分日 K 线”落库到本地，供 Vibe-Trading
回测离线使用。行情抓取完全复用 Vibe-Trading 数据层（`backtest.runner.fetch_data_map`），
成分股使用 baostock 主源，akshare/sina 仅作兜底。

## 目录结构

```text
agent/scripts/
├── lib/                              # 可复用原语
│   ├── fetch_kline.py                # 通用 K 线抓取（复用 Vibe-Trading 数据层）
│   └── get_csi300_constituents.py    # 指数历史成分股（baostock 主源）
├── run/
│   └── run_fetch_csi300_kline.py     # 任务胶水：成分 + K 线 + 覆盖率报告
├── README.md
├── bench_performance.py              # 原有开发脚本
├── w4a_run_benches.py                # 原有开发脚本
└── w4a_patch_blog.py                 # 原有开发脚本
```

目录约定：

- `lib/`：可复用原语，一个脚本只做一件事，后续任务可继续复用。
- `run/`：任务胶水，负责把多个 `lib` 原语串成具体任务。
- 根目录三个 `.py`：原有开发脚本，说明见「原有脚本」章节。

## 环境要求

建议统一使用 Vibe-Trading 自带 venv：

```powershell
E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe -m pip install baostock pyarrow
```

依赖说明：

- `baostock`：成分股主源（已安装版本 0.9.3）。
- `akshare`：兜底源（已安装）。
- `pyarrow`：parquet 输出依赖。
- 脚本位于仓库 `agent/scripts/` 内，agent 目录默认按脚本位置自动推导；
  也可用环境变量 `VIBE_TRADING_SRC` 覆盖仓库根目录。

## lib

### **fetch_kline.py**

**功能**

通用 K 线抓取，逐标的调用 `fetch_data_map`，单标的失败不中断整批，失败清单会落盘。
支持普通全量抓取和 `--append` 增量补齐。

**用法（全量抓取）**

```powershell
E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe agent/scripts/lib/fetch_kline.py --codes 600519.SH,000001.SZ --start-date 2025-01-01 --end-date 2025-12-31 --out-dir C:/tmp/kline --source auto
```

从文件读标的（每行一个代码，`#` 开头为注释，多个标的一起抓）：

```powershell
E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe agent/scripts/lib/fetch_kline.py --codes-file universe.txt --start-date 2025-01-01 --end-date 2025-12-31 --out-dir C:/tmp/kline
```

**用法（--append 增量补齐）**

已有旧区间时，只联网补头尾缺口，自动读旧 parquet/csv、合并、去重、排序后写回；
多个标的写在一个 `--codes` 或 `--codes-file` 里同时生效，已完整覆盖的标的直接跳过联网。

```powershell
E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe agent/scripts/lib/fetch_kline.py --append --codes 600519.SH,600300.SH --start-date 2018-01-02 --end-date 2025-12-31 --out-dir C:/Users/mumu/.vibe-trading/data-bridge/csi300
```

例如 600519.SH、600300.SH 已有 2020-01-01 ~ 2024-01-01 的 parquet，上面这条命令只下载
2018~2019 和 2024~2025 两段缺口，不会重拉 2020~2024。

**参数**

- `--codes`：逗号分隔的代码，如 `600519.SH,000001.SZ`；与 `--codes-file` 二选一。
- `--codes-file`：代码文件路径，每行一个代码。
- `--start-date` / `--end-date`：含边界的日期区间，格式 `YYYY-MM-DD`。
- `--out-dir`：输出根目录。
- `--source`：数据源，默认 `auto`（腾讯 -> mootdx -> 东财 -> baostock -> akshare）。
- `--interval`：K 线周期，默认 `1D`。
- `--append`：增量补齐，只补已有文件的头尾缺口；多标的同时生效。
  注意：只补头部/尾部缺口，不修复旧文件中间的缺失；如果怀疑中间缺数据，用普通模式整段重拉。
  缺口语义：缺口区间联网后无数据（如新股上市前）视为已覆盖；联网失败则保留已有数据并记入 `gap_skipped`，不会把该标的标成 failed。

**输出**

- `out_dir/kline/<code>.parquet`：每个标的一个 parquet。
- `out_dir/manifest.json`：成功/失败清单、已覆盖清单、缺口跳过清单、实际生效数据源、行数统计。


### **get_csi300_constituents.py**

**功能**

获取指数历史成分股，默认每年 1 月 1 日、7 月 1 日调股后各查一次，外加区间起止日；
按 baostock 返回的 `updateDate` 去重，得到无幸存者偏差的 membership 长表。

**用法（默认沪深300）**

```powershell
E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe agent/scripts/lib/get_csi300_constituents.py --start-date 2020-01-01 --end-date 2026-12-31 --out-dir C:/tmp/csi300
```

**怎么换指定指数**

通过 `--index` 切换，只改这一个参数，其他参数不变：

| 指数 | `--index` 写法 |
|---|---|
| 沪深300（默认） | `399300.SZ` 或 `000300.SH` |
| 中证500 | `000905.SH` 或 `399905.SZ` |
| 上证50 | `000016.SH` |

例如抓中证500：

```powershell
E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe agent/scripts/lib/get_csi300_constituents.py --index 000905.SH --start-date 2020-01-01 --end-date 2026-12-31 --out-dir C:/tmp/csi500
```

说明：脚本会根据 `--index` 自动选择 baostock 查询函数（沪深300、中证500、上证50），
akshare 兜底的 `symbol` 也会自动映射（如 `399300` -> `000300`、`399905` -> `000905`）；
不支持的指数会直接报错。

**其他参数**

- `--snapshot-dates`：覆盖候选查询日，逗号分隔，例如 `2024-07-01,2026-07-31`（联调用）。
- `--sleep`：每次 baostock 查询后的限流间隔，默认 `0.2` 秒。
- `--max-retries`：每个查询/兜底源的最大重试次数，默认 `3`。
- `--fallback-timeout`：兜底源单次调用超时，默认 `30` 秒。

**输出**

- `out_dir/membership.parquet`：长表，列为 `update_date, code, code_name`。
- `out_dir/membership.csv`：同上，UTF-8 编码，便于 Excel 查看。
- `out_dir/snapshots.json`：每个查询日对应的快照元数据。

**兜底说明**

akshare/sina 兜底只能拿到当前最新一期，兜底快照会写入 `snapshots.json`
并在 warnings 中明确标记，不会冒充历史快照。

## run

### **run_fetch_csi300_kline.py**

**功能**

完整子任务入口：成分 membership -> 全部历史成分并集 + `000300.SH` 指数 ->
逐标的日 K 落库 -> 生成 `bridge_config.yaml` 片段与 `manifest.json` 覆盖率报告。

**用法（全量）**

```powershell
E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe agent/scripts/run/run_fetch_csi300_kline.py --start-date 2020-01-01 --end-date 2026-12-31 --out-dir C:/tmp/csi300 --source auto
```

默认输出目录：`C:\Users\<user>\.vibe-trading\data-bridge\csi300`。

**用法（增量补齐）**

```powershell
E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe agent/scripts/run/run_fetch_csi300_kline.py --append --start-date 2018-01-02 --end-date 2025-12-31 --out-dir C:/Users/mumu/.vibe-trading/data-bridge/csi300
```

`--append` 透传给 `fetch_kline`：整个标的池里已有 parquet 的只补头尾缺口，
没有文件的正常全量抓取。

**参数**

- `--index`：成分指数代码，默认 `399300.SZ`，换指数方式同 `get_csi300_constituents.py`。
- `--source`：K 线数据源，默认 `auto`。
- `--interval`：K 线周期，默认 `1D`。
- `--snapshot-dates`：覆盖成分查询日，逗号分隔。
- `--limit-codes N`：只抓前 N 只成分（保留 `000300.SH` 基准），用于小样本联调或分批续跑。
- `--append`：增量模式，已有 parquet 的标的只补头尾缺口。
- `--sleep` / `--max-retries` / `--fallback-timeout`：透传给成分抓取。

**输出**

- `out_dir/kline/`：每个标的一个 parquet。
- `out_dir/membership.parquet / membership.csv / snapshots.json`：成分数据。
- `out_dir/bridge_config.yaml`：data-bridge 配置片段。
- `out_dir/manifest.json`：覆盖率报告（快照数、成分数、成功/失败/已覆盖、缺失清单、生效数据源）。

## 原有脚本

本目录根节点原有三个开发脚本，与本抓取任务无关，保留不动：

- `bench_performance.py`：性能基准，对比新旧 operator/equity 路径。
- `w4a_run_benches.py`：跑 4 组 alpha zoo x universe 基准，产出 HTML/JSON 报告。
- `w4a_patch_blog.py`：读取 bench summary，幂等地修补 alpha 博客 HTML 的 TBD。

## 输出与 data-bridge 接入

```text
<out-dir>/
├── kline/
│   ├── 600519.SH.parquet
│   ├── 000300.SH.parquet
│   └── ...
├── membership.parquet / membership.csv
├── snapshots.json
├── bridge_config.yaml          # data-bridge config.yaml 片段
└── manifest.json               # 覆盖率报告
```

接入 Vibe-Trading 离线回测：

1. 把 `bridge_config.yaml` 里的 `sources:` 块合并进
   `C:\Users\mumu\.vibe-trading\data-bridge\config.yaml`（UTF-8 无 BOM）。
2. 对话/配置里用 `local:<code>` 写标的，例如 `local:600519.SH`。
3. 不需要联网，配置里缺标的会 fail closed，不会静默退化到在线源。

## 已知限制

- baostock 只按候选查询日抓取，若成分在非 1/7 月发生临时调整，默认粒度会漏掉；
  可通过 `--snapshot-dates` 显式补齐。
- 兜底源只有“最新一期”，历史回测遇到兜底快照时应视为近似数据。
- `source=auto` 的 A 股链路为腾讯 -> mootdx -> 东财 -> baostock -> akshare，
  腾讯日线为前复权；若策略严格要求后复权，需要额外校验/换源。
- 全量 2020-2026 约 900+ 只标的，抓取耗时会较长，可分批用同一 `--out-dir` 续跑；
  已拉过的区间可用 `--append` 增量补齐，避免重复下载。
- `--append` 只补头部/尾部缺口，不修复旧文件中间的缺失。
