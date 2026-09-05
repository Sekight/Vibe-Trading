# 计划：stockdb 数据源接入（A 股日线 + local loader 额外列透传）

> 编号：P-20260905-stockdb_ma_convergence_data
> 状态：已完成
> 日期：2026-09-05
> 关联迭代：V048
> 关联：commit / run（收尾时补）；验证 run：agent/runs/vt_e2e_stockdb_100（透传对照 vt_e2e_stockdb_100_nox）

## 项目调研

> 外部（实测，2026-09-05）：stockdb 本地服务 `127.0.0.1:7899`（`E:\data\free-stockdb-windows-v0.3.2-more-power\stockdb`，SDK 在 `pybao/`，`PYTHONPATH=.../pybao python -c "import stock_sdk"` 实测可导入；服务在本轮调研中曾掉线，重启 `stockdb.exe` 后恢复）。

- stockdb 本地数据（LevelDB，离线，总量约 24GB）：
  - `日k:code:YYYYMMDD` → dict，字段实测：`date/code/name/open/high/low/close/pre_close/volume(股)/amount(元)/turnover(换手率%)/pct_chg/amplitude/is_st/vol_ratio/total_share/float_share/total_mv/float_mv/pe_ttm/pb`；`turnover` 已交叉验证 = volume/float_share×100。
  - `复权:code:YYYYMMDD` → `{div,give,trans,mult,cum}`；后复权价 = 原始价 × cum（SDK `get_data(fq="hfq")` 直接给）。
  - `股票代码` → `{前缀:[code,...]}` 共 7563 只，其中沪深 A 股 5201 只（0=深A 1493、3=创业板 1397、6=沪A 2311；1/5 为基金、9 为北交所）。
  - `退市` → 970 条；`bk.get(code,1,"name")` → 申万一级（当前状态）。
  - 无指数 K 线/交易日历/Barra（本地）。
- stockdb 在线 API：`get_trade_days` ✓、`get_all_securities` ✓（上市/退市日期）；`get_industry / get_index_stocks / get_index_weights` ✗（参数未通）。
- **导出体积实测（2026-09-05）**：全市场沪深 A 股（5201 只）2011-01 起日线约 **1920 万行**；抽样 20 只打包实测：**Parquet ≈ 1.5GB、CSV ≈ 3.6GB**（每行 Parquet 76B / CSV 188B）。原始 24GB 的空间大头是分钟线（约一年半全证券 1 分钟 bar），本次只导日线+复权+生命周期+行业+日历，不导分钟线。
- vibe-trading 现状（内部查证，2026-09-05）：
  - local loader（`agent/backtest/loaders/local_loader.py`）：data-bridge 配置驱动，支持 CSV/Parquet/DuckDB；**只保留 OHLCV + trade_date 列，amount/turnover/float_share/行业/市值一律丢弃**（`_normalize_columns` keep_cols 硬编码）；对复权原样读取（HowToUse 8.40）。`source="local"` + `codes=["local:600519.SH"]` 直跑 runner 可用。
  - A 股引擎 `china_a.py` 已存在（涨跌停/佣金/印花税/过户费/滑点）；A 股 symbol 规约 `^\d{6}\.(SZ|SH|BJ)$`；支持多标的同时组合回测。
  - MCP `backtest` 单入口 + `BacktestConfigSchema` 配置契约（V046）；bridge skill 规定外部 Agent 不碰引擎/loader，本计划由项目侧开发 loader 改动。
  - 仓库内无任何 stockdb 引用 → 接入为全新工作。
- 首个落地场景：《均线收敛与发散》研报复现（口径、因子、验收数值全部在外部文档《20240414_均线收敛与发散_复现实验.md》，本计划不重复）。

## 需求目标

- 做什么：为 vibe-trading 增加 stockdb A 股数据源接入能力——
  1. **stockdb 导出工具**：把 stockdb 的 A 股日线（含后复权价、换手率/成交额/流通股本等列）、复权因子、证券生命周期、申万行业、交易日历导出为 data-bridge 可直接读取的文件（Parquet/CSV）；
  2. **local loader 额外列透传（方案 A）**：data-bridge 配置声明 `extra_columns` 后，信号引擎可拿到换手率等字段，支撑需要非 OHLCV 数据的策略；
  3. **端到端验证**：以导出的 stockdb 数据跑通一个小池 A 股 run（首个落地场景为研报复现，其口径/数值以复现实验文档为准）。
- 范围 / 边界：
  - **不改** `backtest/engines` 与 runner 业务逻辑；交易层仅按本计划增强 local loader 额外列透传（方案 A）。
  - **不做**：指数增强、Barra 归因、多空可执行化；方案 B（stockdb 直连 loader）为后续方向，不进本期。
  - **文档分工**：研报复现的方法论（口径、因子、对照数值）全部在外部《20240414_均线收敛与发散_复现实验.md》，本计划只写数据源接入本身。
- 验收标准（第一版）：导出工具幂等产出 data-bridge 可用文件且体积可控（≤2GB Parquet）；`extra_columns` 透传生效且未声明时行为与现状一致（回归既有 local loader 测试）；小池 A 股 run 经 MCP `backtest` 端到端跑通并产出核心 artifacts。

## 实现方案

### 阶段 1：stockdb 导出工具（`agent/scripts/export_stockdb_ashare.py`）

产物（Parquet 分片，行=date；全沪深 A 股，2011-01 起，含 MA120 预热）：
1. `daily.parquet`：`date/code/open/high/low/close/pre_close/volume/amount/turnover/float_share/float_mv/total_mv/is_st` + 后复权 `open_hfq/high_hfq/low_hfq/close_hfq`（SDK `fq="hfq"` 单次取数，不做二次折算）；原样保留的 `turnover(%)`、`amount(元)`、`float_share(股)` 是策略层非 OHLCV 字段的来源。
2. `calendar.parquet`：交易日历（在线 `get_trade_days`，失败时用老证券日 bar 日期并集推导并标注口径）。
3. `securities.parquet`：代码/名称/上市日/退市日（在线 `get_all_securities` 交集本地 `退市` 表；退市股票保留）。
4. `industry.parquet`：申万一级行业（本地 `bk.get(code,1)`，标注"当前状态近似"）。
5. 停牌推导：`calendar × (上市日,退市日)` 区间内缺 bar = 停牌（脚本内推导即可）。

取数约束（遵守 stockdb SDK 文档规则）：
- 大范围用前缀查询（`rd.vals("日k","6*"...)、"0*"、"3*"`），不逐股循环；日期按年分片，避免单次查询过大。
- 只导出股票（前缀 0/3/6，剔除基金 1/5；北交所 9 默认关闭、可配置）。
- 幂等：以 `(code,date)` 主键重建；数据仓目录放 `<repo_root>/tools/` 或独立数据工程目录，不落入 `.env`/run artifacts。
- manifest：记录导出日期、stockdb 同步版本，复现可溯源。

### 阶段 2（方案 A）：local loader 额外列透传

- 改 `agent/backtest/loaders/local_loader.py`：data-bridge 配置新增 `extra_columns`（如 `[turnover, amount, float_share]`），`_normalize_columns` 的保留列由硬编码"OHLCV + trade_date"改为"OHLCV + trade_date + extra_columns 原样透传"；信号引擎 `data_map[symbol]` 即含对应列，策略侧按列名直接读取。
- **扩展性（配置驱动，不改代码）**：以后需要读取本地文件里的其他列，只需在 config.yaml 的 `extra_columns` 里加列名（要求列存在于导出文件）；支持 `策略名: 文件列名` 形式的可选重命名映射，避免列名不一致时改代码。loader/引擎代码无需再动。
- 兼容性：未声明 `extra_columns` 时行为与现状完全一致；缺列时按现有逻辑处理（不强制）；补 loader 单测与回归（HowToUse 8.16/8.22 用法）。
- 不改引擎/runner/成交逻辑；策略侧仅 `data_map` 多出可选项。

### 阶段 3（方案 A）：小池端到端验证（数据源链路）

- data-bridge `config.yaml` 登记导出文件的 symbol（`600519.SH` 规约）与 `extra_columns`；`config.json` 写 `source="local"`、`codes=["local:<code>.SH|SZ"]`。
- 以 50-100 只股票的小 run 走 MCP `backtest` 单入口（人工确认后回测）：验证数据加载、透传列到达信号引擎、china_a 引擎成交/费用/涨跌停路径、核心 artifacts（metrics/trades/positions/equity/run_card）产出。
- 信号引擎用所需字段（如换手率）算出非全零目标权重即可，具体因子/策略内容由落地场景（研报复现）决定，见复现实验文档。

## 执行清单

1. 实现 stockdb 导出工具（四表 + 停牌推导，前缀分片、幂等、manifest），产出 data-bridge 可读 Parquet/CSV。
2. 数据质量检查：`(code,date)` 唯一、OHLC 合法、`hfq/raw = cum` 抽查、`turnover ≈ volume/float_share×100` 抽查、退市股保留、体积实测 ≤2GB。
3. local loader `extra_columns` 透传实现 + 单测（未声明行为不变）+ 既有 local loader 回归。
4. data-bridge 登记 + `config.json`（source="local"、`local:` 前缀 codes、backtest 窗口）编写。
5. 小池端到端 run：MCP `backtest(action="run")` 产出核心 artifacts，确认透传列到达信号引擎并输出非全零目标权重。
6. 收尾：更新计划状态、计划 README、ITERATION_LOG；坑入 Mistake_Journal（**只记 vibe-trading 项目内与本迭代相关的坑**，外部数据源如 stockdb 自身的问题不记账、不入全局踩坑日志）。

## 开工前核对

- 需求目标 / 范围与讨论记录一致（本期 = 导出工具 + 方案 A 透传 + 端到端验证；方案 B 仅后续方向）
- 导出体积结论（Parquet≈1.5GB 全量）已实测支撑，不存在"再造 24GB"问题
- 文档分工已确认：研报复现细节（口径/因子/对照数值）在外部复现实验文档，本计划无重复
- 不改 engines/runner 业务逻辑；local loader 改动保持"未声明 extra_columns 时行为不变"
- 执行清单覆盖需求目标与验收标准；验收标准可验证
- 元信息已填（关联迭代允许为待填）

## 验证

- 数据质量与体积：`(code,date)` 唯一、OHLC 非负、`hfq/raw=cum` 抽 10 只、`turnover` 自洽抽 10 只、退市股保留；全量 Parquet 体积实测 ≤2GB；脚本重建幂等（二次产出 hash 一致，除 manifest 时间戳）。
- loader 透传：声明 `extra_columns` 后 `data_map` 含对应列且不改变 OHLCV/成交逻辑；未声明时与现状一致（回归既有 local loader 测试）。
- 端到端：小池 run 经 MCP `backtest` 产出 metrics/trades/positions/equity/run_card；信号引擎输出非全零目标权重。
- 首个落地场景（研报复现）的因子/验收数值按复现实验文档第 3 章执行，属该文档验收，不在本计划验证范围。

## 讨论记录

- 2026-09-05 用户提出：以本地 stockdb 为数据源复现开源证券《均线收敛与发散》，先调研"是否需要额外开发"，需要则写计划确认。
- 2026-09-05 调研结论：需要额外开发，集中在（研究层）stockdb→Parquet 导出 + 因子/收益矩阵脚本；（交易层）信号引擎需要换手率等列而 local loader 只透传 OHLCV。vibe-trading 现有能力（factor_analysis、china_a 引擎、local loader、config 契约、bridge 工作流）可直接复用，无需改引擎。
- 2026-09-05 口径确认与文档分流：用户拍板成交点用次日开盘价、其余采纳推荐（ddof=0、hfq close、月末/周末最后交易日、第一版不去极值、行业当前口径近似）；明确这些属研报复现细节、不属于 vibe-trading 适配需求——口径总账迁至外部《20240414_均线收敛与发散_复现实验.md》（含原 notebook 第 4 章复现方案全文）。
- 2026-09-05 A/B 讨论与拍板：用户认可 B（stockdb 直连 loader）适合"以后常研究 A 股用 stockdb"、A（local loader 透传）适合"常换本地源"；结论 A 的 stockdb 解析发生在仓库外导出脚本、vibe-trading 只需透传额外列，A/B 共用"额外列透传"工程点、分叉在数据来源（快照文件 vs 实时服务）。**用户拍板本期采用方案 A**；方案 B 仅后续方向。
- 2026-09-05 空间顾虑澄清与方案再评估：用户担心"再转化一份 24GB 会不会太大、是否直接 B 合理"。实测厘清：原始 24GB 大头是分钟线（不导）；只导 A 股日线+复权+生命周期+行业+日历为 **Parquet≈1.5GB / CSV≈3.6GB**（5201 只、2011 起、1920 万行）——体积可控，空间不构成选 B 的理由；且研究层无论 A/B 都建议保留轻量快照（快、可复现、与取数解耦）。维持方案 A 结论不变。
- 2026-09-05 文档范围调整：用户要求计划文档只包含 vibe-trading 接入 stockdb 数据源的内容；研报复现相关内容（数据仓字段选型、因子矩阵脚本、factor_analysis 验证、补充统计、中性化对照、验收数值）全部移入复现实验文档（其第 4 章），计划文档只写导出工具 + loader 透传 + 端到端链路。

## 风险 / 注意

- **stockdb 服务稳定性**：本轮调研中服务曾掉线（约 24GB 库大查询后连接被拒），export 工具对连接失败要有重试与断点续导；离线复现仍以导出快照为准，不依赖服务常驻。该问题属外部数据源环境问题，只作为导出工具的设计约束，不写入 Mistake_Journal / 全局踩坑日志。
- local loader 是公共组件：`extra_columns` 改动必须保持"未声明时行为不变"，回归既有 local loader 测试，避免影响其他本地数据用户（HowToUse 8.16/8.22）。
- 历史行业为当前申万一级近似（无历史时点回溯）：下游策略/中性化结果需标注近似误差（复现实验文档"已知近似"）。
- 指数成分/权重与 Barra 缺失（在线 get_index_stocks 参数未通）：方案 B 与指数类场景待后续数据源解决，不影响本期日线接入。
- Windows 大文件：22GB LevelDB 前缀分片导出耗时未最终实测（抽样 20 只 5.6s），正式导出按年分片并保留进度；失败不中断已写分片（幂等重建）。