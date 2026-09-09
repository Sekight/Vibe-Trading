# 计划：全市场 run 的 OHLCV 不落库（--no-ohlcv）+ 报告页 K 线默认空态按需加载

> 编号：P-20260909-ohlcv_no_persist_and_chart_lazy
> 状态：已完成
> 日期：2026-09-09
> 关联迭代：V049（2026-09-09）
> 关联：commit（本次提交）

## 项目调研

- **根因**：全市场 run（5200 只）的 `artifacts/ohlcv_*.csv` 共 1.3GB/1839 万行；报告页打开即自动请求首标的 K 线，后端 `build_run_analysis` 先全量读 5200 个 OHLCV 文件再过滤，进程 MemoryError，后续请求连锁崩。（2026-09-09，线上复现 + 代码定位：`ui_services.py:556/388`、`RunDetail.tsx:194-196`）
- **前端空态 UI 已存在**：`selectedSymbols` 非空但无 K 线数据时显示"选择一个标的以加载图表数据"（`RunDetail.tsx:734-738`）；切 tab 不重载、ChartTab 保持挂载（`RunDetail.tsx:405-425`）。改默认空态只需删打开即自动加载首标的的调用。
- **OHLCV 产物写入点**：`backtest/engines/base.py:1777-1778`，回测结束后统一逐股 `df.to_csv`，无配置开关。引擎 `self.config` 已持有 config（`base.py:456`），CLI flag → config → 引擎链路可直通。
- **CLI 同构参照**：`--fastrun`（`runner.py:1673-1703`）经 `main(without_regime=..., without_mae_mfe=...)` → digest 构建参数。`--no-ohlcv` 照此模式，但目标是 config 字段而非 digest 参数。
- **OHLCV 全部读取方**（调研确认）：WebUI K 线 `_load_ohlcv_artifacts`（OOM 源）、digest 的 `add_mae_mfe`/`_load_close_prices`(regime)/`ohlcv_summary`（缺文件时均 graceful 降级，`digest.py:842` skipped 路径）、MCP `pattern_tool`（全量，强依赖文件）。
- **决策（用户拍板）**：① K 线默认空态；② `--no-ohlcv` 默认 OHLCV 落库（向后兼容），传 flag 才跳过；③ 不做"无本地 OHLCV 时网络重建单标的"兜底——按现状，缺文件就显示空/降级，不额外开发；④ 加回归测试。

## 需求目标

- 做什么：
  1. 报告页（WebUI run 详情）K 线行情默认**空态**，不自动加载任何标的；用户选择标的才按需请求该标的 K 线。
  2. 回测支持 `--no-ohlcv` 命令行开关：**默认 OHLCV 仍落库**，传 `--no-ohlcv` 才跳过 `ohlcv_*.csv` 落盘（1.3GB/5200 文件），其余产物（equity/positions/trades/metrics/run_card/digest 等）照常写；不落库时 WebUI 按现状降级（K 线空态、digest 的 MAE/MFE/regime 缺失），不做网络重建兜底。
- 范围 / 边界：只改加载/展示层与落盘开关；不改 fetch 数据、不改回测执行、不改 digest 构建逻辑（降级是自然的）、不做网络重建单标的兜底。
- 验收标准：① 打开任意 run 报告（含 5200 只全市场）不再 OOM；② 默认显示 K 线空态，选择标的才加载；③ `--no-ohlcv` 回测的 artifacts 无 `ohlcv_*.csv`，其余产物完整，WebUI 不崩、K 线显示空态；④ 默认不传 flag 时 OHLCV 照常落库，既有 run/行为不变；⑤ 回归测试通过。

## 实现方案

### 改动 1：后端按需加载（OOM 根治）—— `agent/src/ui_services.py`

- `_load_ohlcv_artifacts(run_dir, symbols=None)`：新增 `symbols` 参数（`Collection[str] | None`）。传值时只读匹配的 `ohlcv_{code}.csv` 文件，跳过其余；`None` 保持全量旧行为。文件枚举用 `glob` 后按 code 过滤。
- `load_price_series(run_dir, symbols=None)`：透传 `symbols`；`price_series.csv` 分支同样按 `code` 列过滤。
- `build_run_analysis`：请求带 `symbols` 时传给 `load_price_series`；`chart_symbols` 改从 `_artifact_symbols`（只读文件名/首列）取，不再依赖全量 `price_rows` 兜底生成 chart_symbols。

> 注：`reconstruct_price_series` 保持现状（全 codes 重建），本次不改；仅在 `price_series.csv` 与 `ohlcv_*.csv` 都不存在时才触发，全市场 run 已关闭 OHLCV 落库时走不到该路径（用户明确不要网络兜底）。

> **补充修复（2026-09-09 二期）**：`build_run_analysis` 在**不带 `chart_symbol` 的完整请求**（`selected_symbols` 为空 → 之前 `symbols=None`）时仍会全量加载所有 OHLCV 文件，导致无参 `api.getRun()` 调用（Compare 对比页 `Compare.tsx:271/302`、Agent 报告判定 `Agent.tsx:570/919`、聊天卡片 `RunCompleteCard.tsx:40`）触发全量加载 OOM。改为：`selected_symbols` 为空时**不加载任何 OHLCV**（`price_rows=[]`，`price_series`/`indicator_series` 返回空），只返回 chart_symbols/chart_groups/equity/trades——这些调用方本来只需要 metrics/equity_curve。带 `chart_symbol` 的请求行为不变（仍只读目标标的单文件）。`load_price_series(symbols=None)` 的全量语义保留给直接调用者（如单测 `test_load_price_series_no_symbols_full`）。新增回归用例 `test_build_run_analysis_without_symbols_does_not_load_ohlcv`。

### 改动 2：前端默认空态 —— `frontend/src/pages/RunDetail.tsx`

- 主 `useEffect`（`RunDetail.tsx:155-205`）：
  - 保留 `selectedSymbol` / `chartPickerSymbol` 设为首标的（下拉默认值，仅 UI）。
  - **删除 `selectedSymbols` 初始化为 `[firstSymbol]` 与 `loadChartSymbol(firstSymbol)` 自动调用**（`RunDetail.tsx:188-196`），`selectedSymbols` 保持 `[]`，触发空态文案。
  - `cacheFromRun` 初始缓存调用保留（summary 通常无 K 线，缓存为空占位，无害）。
- 用户选择标的：`handleAddChartSymbol`（`RunDetail.tsx:273-279`）→ `loadChartSymbol` → 请求该标的 K 线。此路径不变。
- 更新 `RunDetail.test.tsx` 中"打开即发 `chart_symbol` 请求"的断言（改为默认不自动请求）。

### 改动 3：`--no-ohlcv` 命令行开关（默认落库） —— `agent/backtest/runner.py` + `agent/backtest/engines/base.py`

- `runner.py` `__main__`（`runner.py:1673` 附近）：
  - 新增 `parser.add_argument("--no-ohlcv", action="store_true", help="Skip writing per-symbol OHLCV CSV artifacts (ohlcv_*.csv)")`。
  - `main(..., without_ohlcv=args.no_ohlcv)`。
- `runner.py` `main()` 签名加 `without_ohlcv: bool = False`；在 config 组装后写 `config["save_ohlcv"] = not without_ohlcv`（config 会经 `_create_market_engine(source, config, codes)` 传给引擎）。默认 `without_ohlcv=False` → `save_ohlcv=True`。
- `backtest/engines/base.py` `_write_artifacts`（`base.py:1777` 前）：
  - `if not self.config.get("save_ohlcv", True):` 跳过 OHLCV 循环，其余产物照常写。
  - 注释说明：WebUI K 线读 OHLCV 时缺文件即空态；digest 的 MAE/MFE/regime 自然降级。
- 不改 `BacktestConfigSchema`（`extra="allow"`，`config["save_ohlcv"]` 可直接透传）；但 `config.json` 本身不落 `save_ohlcv`（CLI 临时注入，不影响复用）。

### 改动 4：回归测试

- 后端（`agent/tests/`，用临时目录构造，不污染真实 run）：
  - `test_load_price_series_symbols_filter`：构造含 2 个 ohlcv 文件的临时 run，断言 `load_price_series(run_dir, symbols=["A"])` 只返回 A 的行、不读 B。
  - `test_load_price_series_no_symbols_full`：不传 symbols 时返回全部标的行为不变（默认全量兼容）。
  - `test_write_artifacts_save_ohlcv_default`：引擎 `_write_artifacts` 无 `save_ohlcv` 字段时照常写 OHLCV（默认落库回归）。
  - `test_write_artifacts_no_ohlcv`：`config["save_ohlcv"]=False` 时跳过 OHLCV、其余产物（equity/trades/metrics）照常写。
  - `test_build_run_analysis_chart_symbols`：`build_run_analysis(symbols=[...])` 返回的 `chart_symbols` 正确、`price_series` 只含请求标的。
- 前端：更新 `RunDetail.test.tsx` 断言（默认空态不自动请求；用户选标的才请求该标的）。

## 执行清单

1. `ui_services.py`：`_load_ohlcv_artifacts` / `load_price_series` 加 `symbols` 参数并过滤；`build_run_analysis` 前置透传 symbols、`chart_symbols` 走 `_artifact_symbols`。
2. `RunDetail.tsx`：删自动加载首标的 K 线、`selectedSymbols` 默认 `[]`；`RunDetail.test.tsx` 同步更新断言。
3. `runner.py`：加 `--no-ohlcv` flag + `main(without_ohlcv=...)` + `config["save_ohlcv"]`（默认 True）。
4. `engines/base.py` `_write_artifacts`：`save_ohlcv` 开关跳过 OHLCV 写入。
5. 后端回归测试：上述 5 个用例。
6. 后端冒烟：单标的过滤加载、`--no-ohlcv` 产物缺 OHLCV 且其余完整。
7. WebUI 验证：打开 5200 只全市场 run 不 OOM、默认空态、选标的才加载 K 线。

## 开工前核对

（状态从"讨论中"切到"已确认"前由 Codex 逐项核对；核对结果按清单逐项展示"通过 / 未通过 + 发现项"）

- [x] 需求目标 / 范围与讨论记录一致 —— 通过（K 线默认空态 + `--no-ohlcv` 默认落库 + 回归测试）
- [x] 范围/边界无被后续讨论反转但仍保留的旧约束 —— 通过（不做网络重建兜底，用户明确确认）
- [x] 执行清单覆盖需求目标与验收标准 —— 通过
- [x] 验收标准可验证 —— 通过（OOM 复现 run、--no-ohlcv 小 run、回归测试）
- [x] 元信息已填（关联允许为待填） —— 通过

## 验证

- 后端：对 `ma_acf_full_top50_neu` 调用 `build_run_analysis(symbols=["000001.SZ"])`，断言只读 1 个文件、响应含该标的 K 线、内存占用显著低于全量。
- 回测：小 run 跑 `python -m backtest.runner <run_dir> --no-ohlcv`，断言 artifacts 无 `ohlcv_*.csv`、有 equity/trades/metrics/run_card，digest 构建不崩。
- 前端：`RunDetail.test.tsx` 更新后跑测试通过；打开全市场 run 报告不 OOM、K 线空态；选择 `000001.SZ` 加载该标的 K 线；切 tab 往返状态保持。
- 二期补充验证：`test_build_run_analysis_without_symbols_does_not_load_ohlcv`（无 symbols 时 `price_series`/`indicator_series` 为空、`chart_symbols` 仍从 artifact 列表拿到）；后端 `test_ohlcv_persistence` 7 passed、相关 `test_analysis_*` 50 passed 无回归；前端 RunDetail 14 passed；`tsc -b` 通过。

## 讨论记录

- 2026-09-09 用户：打开报告报 OOM，要求分析是哪个 tab/图导致、digest 已落库为何不直接读。
- 2026-09-09 调研：OOM 源为报告页打开即请求首标的 K 线 + 后端全量读 OHLCV；digest 本就走轻量路径，是受害者非元凶。
- 2026-09-09 用户拍板：① K 线默认空态（非默认加载首标的）；② `--no-ohlcv` 做成命令行（类似 fastrun）；③ 不做"无本地 OHLCV 时网络重建单标的"兜底，缺文件按现状空态/降级即可。
- 2026-09-09 确认：`--no-ohlcv` 的副作用（digest 的 MAE/MFE、regime 缺失）用户接受，不为此额外开发。
- 2026-09-09 补充（用户）：加回归测试不影响正常功能；`--no-ohlcv` 默认 OHLCV 落库（向后兼容）。
- 2026-09-09 二期（用户复测发现）：点击"显示"选标的在**新代码**下 200 OK 不卡（带 chart_symbol 路径已修复），但**无参 `api.getRun()`**（Compare/Agent/聊天卡片）仍触发全量加载 OOM——`build_run_analysis` 在 `selected_symbols` 为空时 `symbols=None` 走全量。修复：空时 `price_rows=[]` 不加载 OHLCV。**需要重启 vibe-trading 服务让新代码生效**（旧进程仍会 OOM）。

## 风险 / 注意

- `--no-ohlcv` 后 `analysis.digest.json` 的 `ohlcv_summary` 计数为 0、`mae_mfe_summary`/`regime` 缺失：WebUI 对应区块需能容忍空/缺字段（现状已 graceful，需验证）。
- MCP `pattern_tool`（图表形态识别）强依赖 OHLCV 文件：`--no-ohlcv` 的 run 该工具不可用，属预期，不额外处理。
- `RunDetail.test.tsx` 断言变更属行为契约变更，需同步更新并跑相关前端测试。
- 回归测试需用临时目录构造，避免污染真实 run 目录。
