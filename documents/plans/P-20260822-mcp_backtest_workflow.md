# 计划：MCP 回测模式与外部 Agent 协作工作流

> 编号：P-20260822-mcp_backtest_workflow
> 状态：已完成
> 日期：2026-08-22
> 关联迭代：V044 / V045
> 关联：P-20260816-cache_env_once / P-20260817-fastrun / P-20260822-risk_exit_execution_modes / V044 / V045 / commit（未提交） / synthetic small local run

## 项目调研

- 内部·MCP 工具：`agent/mcp_server.py` 的 `backtest` 当前只接收 `run_dir`；`agent/src/tools/backtest_tool.py` 调用 runner 时只传 run 目录，不透传 `--fastrun`、`--with-charts`、`--with-analysis` 等 CLI 选项。
- 内部·CLI 能力：`agent/backtest/runner.py` 已支持 `--fastrun`、`--without-regime`、`--without-mae-mfe`、`--with-charts`、`--with-analysis`。
- 内部·既有迭代：V030 已将 PNG 改为默认跳过；V032 已实现 fastrun，但明确记录 MCP backtest 不透传 flag。详见 `ITERATION_LOG.md` V030/V032。
- 内部·使用手册：HowToUse 8.35 记录 loader cache，8.36/8.37 记录分析图、报告独立补生成，8.38 记录参数探索与 fastrun，12 记录小周期回测口径。
- 内部·缓存现状：P-20260816-cache_env_once 已由 V042 完成；runner 现在复用统一 dotenv 加载，默认可从 `<vibe_home>/.env` 读取 cache 开关，缓存 key/版本/loader 行为未改动。MCP 本次只需定义 `use_cache` 的默认与单次覆盖，不再修改 cache_env_once。
- 内部·执行模式现状：旧 P-20260820-execution_mode_state_machine 已废弃；P-20260822-risk_exit_execution_modes 已由 V043 完成。当前契约是 `entry_mode`（正常开仓/加仓）+ `exit_mode`（正常信号平仓/止盈/减仓/反转）+ `stop_loss_mode`（`none|hard` 独立保护止损），旧 `exit_mode=stop` 在 runner 早失败并给迁移提示。
- 内部·策略契约现状：`strategy-generate` 与 `strategy-dev-manager` 已同步三字段和 `stop_prices` 规则；bridge skill 不应重新定义执行语义，只需引用当前契约并规定外部 Agent 协作边界。
- 内部·文档一致性：HowToUse 8.34 已更新三字段执行模式和硬止损；8.35 已记录 V042 缓存修复；8.36/8.24 仍有“回测成功自动生成 PNG”的旧表述，与 V030/8.38 及当前 runner 默认 `with_charts=False` 冲突，需要同步修正。
- 内部·git 真相：当前 HEAD `9afc0b9` 已包含 V043 三字段执行模式/独立硬止损实现，前一提交 `e517559` 已包含 V042 cache env 修复；本次 MCP 计划应复用这些已落地接口，不再改动执行状态机或 dotenv 主逻辑。

## 前置计划与顺序评估

- **已完成前置：P-20260822-risk_exit_execution_modes**。本需求要把三字段 execution profile 写入 capability registry 和 MCP schema；现在 normal/stop 路径、`next_open/stop`、缺少 `stop_prices`、同 bar 冲突等语义已有计划与回归验证，后续 MCP 实现应复用公共校验，不得复制字符串白名单。
- **已完成前置：P-20260816-cache_env_once（V042）**。本需求直接复用统一 dotenv 和缓存根目录行为，不再重复修改 runner 的 cache env 加载；只补 MCP `use_cache` 的显式开关和测试。
- **软依赖：P-20260818-trading_time_aggregation**。它会增加 `aggregation` 配置并改变小周期 bar 的时间边界，但不直接改 MCP `backtest` 的动作层；本需求应把 `aggregation` 作为可扩展 config 字段透传，不在 bridge skill 中写死自然时间聚合。若该计划在本需求之前落地，只需重新生成能力表和小周期说明，不需要重写 MCP 工具。
- **非前置阻塞：P-20260816-contract_switch_auto**。它改 local loader 的 `contract` 列透传和策略侧换约识别，不改变 MCP 回测动作；本需求只需确保 run_dir/config/artifact 以通用方式传递。
- **非前置阻塞：P-20260817-reports_dir_selector**。它只改 WebUI 报告目录读取链路；本需求的 MCP 工具应始终使用完整 `run_dir` 和 allowed roots，不假设 run 一定在 runs 根目录，避免未来子目录选择器返工。
- **非前置阻塞：P-20260818-position_weight_magnitude**。它改 metrics/digest 的仓位口径；本需求只返回当前 artifacts 和状态，不在 MCP 层硬编码指标含义。报告/图表后处理应读取现有产物，兼容该计划未来的字段变化。

## 需求目标

- 做什么：让 Codex 通过 Vibe-Trading MCP 能稳定理解并调用普通回测、快速回测、分析图生成、分析报告生成和缓存开关。
- 默认行为：Codex/MCP 协作路径默认使用 fast backtest；不生成 `analysis.md`；不生成 PNG；默认不打开 loader cache，只有用户明确要求时传 `use_cache=true`。
- 显式能力：只保留一个公开 MCP `backtest` 工具，通过 `action`、`speed`、`use_cache`、`execution` 参数支持快速回测、普通回测、图片、报告和三字段成交模式（`entry_mode` / `exit_mode` / `stop_loss_mode`）。
- 小周期支持：bridge skill 只说明工作流边界；参数 schema/默认值由 MCP 注册表提供。能力包括 `start_date/end_date` 与 `backtest_start/backtest_end`、完整时间戳、`holding_bars`、fastrun 与分析产物之间的关系。
- 范围 / 边界：推荐只改变 MCP/外部 Agent 默认工作流；保留 CLI `vibe-trading run` 与直接 runner 的现有默认语义，避免破坏既有用户流程。若用户确认要全局改变 CLI 默认值，另列为范围变更。
- 验收标准：Codex 只通过 MCP 和 bridge skill，即可按用户意图选择 fast backtest、补 PNG、补报告、控制缓存，并能在执行前后解释会生成或不会生成哪些产物。

## 实现方案

1. **单一能力/工作流注册表（唯一维护入口）**
   - 新增一个可执行的 capability registry，统一登记：工具/工作流名称、用途、参数、默认值、runner flags、产物、跳过项、缓存行为、已完成的三字段 execution profile、`backtest_start/end`、小周期口径、HowToUse/ITERATION_LOG 锚点。
   - `fast_backtest`、`generate_charts`、`generate_report` 只作为能力/动作 ID，不作为三个公开 MCP 工具；公开工具数量保持最少。
   - `entry_mode`、`exit_mode`、`stop_loss_mode` 的允许值、四个 preset、旧 `exit_mode=stop` 迁移失败语义和配置字段由注册表引用/对拍 `agent/backtest/execution_modes.py`，不再复制旧的字符串白名单。
   - 不新增 `describe_capabilities` 公开工具；能力索引由注册表生成到 MCP server instructions、bridge skill 和 HowToUse 能力表。

2. **MCP 工具层**
   - 扩展现有 `backtest` 为单一公开入口：`backtest(run_dir, action="run|charts|report|full", speed="fast|normal", use_cache=false, execution={entry_mode, exit_mode, stop_loss_mode})`。
   - `action="run"` 默认 `speed="fast"`，调用 runner 的 `--fastrun`，不生成 PNG/LLM 报告；`speed="normal"` 执行完整 digest。
   - `action="charts"` 只调用确定性的 `generate_chart_artifacts`，不重跑行情和引擎；`action="report"` 只调用 `generate_analysis_report`；`action="full"` 才执行完整回测并显式补图/报告。
   - `execution` 暴露/校验三字段 preset；实际配置仍以 run 目录 `config.json` 为准，不由工具静默改写原 run。旧 `exit_mode=stop` 必须返回迁移错误，不得映射成新 hard stop。
   - `use_cache=true/false` 安全传入回测子进程；必要时补齐 `VIBE_TRADING_DATA_CACHE_ROOT` 的 runtime env allowlist。
   - 返回结构统一报告 `action`、`speed`、`cache_enabled`、`backtest_reran`、`charts_generated`、`report_generated`、执行模式和核心 artifact 路径。

3. **从注册表生成 MCP instructions / bridge skill / HowToUse 能力表**
   - `vibe-trading-bridge` 的源文件放在 Vibe-Trading 仓库，通过 MCP 的 `load_skill` 提供给 Codex/Z-Code；不在多个 Agent 中手工维护副本。
   - bridge skill 只承载协作边界和 10 项工作流能力：目录/契约、禁止重写引擎、生成与回测分离、人工确认、产物审计、单问题迭代、失败不无限重试等；不重复 MCP 参数说明。
   - 外部 Agent 生成策略时必须新建独立 run 目录，只写 `config.json` 与 `code/signal_engine.py`；数据加载、市场规则、成交引擎、artifacts 由 Vibe-Trading 负责，Agent 不得重写 `backtest/engines` 或 `backtest/loaders`。
   - 外部 Agent 的策略生成、人工确认、MCP 回测和后续调参必须分阶段；参数调整使用 run 副本和直接回测，不重新进入 Vibe-Trading LLM 生成循环。
   - MCP tool schema 负责参数类型、枚举、默认值、返回字段和错误；MCP server instructions 负责默认路由和跨工具约束。
   - 生成 MCP server 初始化 instructions，明确默认 fast、无报告、无 PNG、cache 关闭；只有用户明确要求时开启 cache；参数探索不走 LLM、不得重写回测引擎和 loader。
   - HowToUse 只保留详细解释、案例和坑；当前能力矩阵、参数、默认值和 MCP 工具表由注册表生成区块，避免三处漂移。

4. **缓存一致性**
   - 复用已完成的 P-20260816-cache_env_once/V042：直跑 runner 统一加载 `<vibe_home>/.env`。
   - 复用 V042 已完成的统一 dotenv 加载；Codex MCP 协作路径默认传入 `VIBE_TRADING_DATA_CACHE=0`，用户明确要求时由单次 `use_cache=true` 覆盖，不修改全局 `.env`。
   - 不改缓存 key 语义，不把 cache 当离线数据源；保留 data-bridge 作为确定性离线数据方案。

5. **文档和迭代留痕**
   - 修正 HowToUse 8.24/8.36 的 PNG 默认行为冲突：默认 runner/fast action 不生成 PNG，`--with-charts` 或 `action="charts"` 才生成；digest/WebUI ECharts 与 PNG 兜底要分开说明。
   - 以 V043 已完成的 HowToUse 8.34 三字段执行模式为准，不恢复旧的 `exit_mode=stop` 表述。
   - 由注册表生成/同步 HowToUse 的 MCP 使用表和 README MCP tools 表。
   - `ITERATION_LOG` 继续记录为什么做、讨论结论、验证和影响，不作为当前能力的唯一真相源。

6. **Codex 配置**
   - 在确认后将 Vibe-Trading stdio MCP 注册到 `<codex_home>/.codex/config.toml`，使用 `<repo_root>/.venv/Scripts/python.exe` 启动 `agent/mcp_server.py`。
   - 不在 Codex MCP 配置中预设 cache 环境变量；`backtest` action 按调用参数传递缓存开关；不启用 shell-capable tools。

## 执行清单

1. 复读并对拍已完成的 P-20260822-risk_exit_execution_modes/V043：复用 `agent/backtest/execution_modes.py`、runner 三字段校验和四个 preset，不重新实现 execution state machine。
2. 复用已完成的 P-20260816-cache_env_once/V042：不再修改 runner 的 dotenv 加载；仅验证 MCP 的 `use_cache` 默认/覆盖行为。
3. 复读本计划与 P-20260817-fastrun，完成开工前核对并确认“默认 fast 仅作用于 MCP/Codex 路径”。
4. 设计并实现 capability registry，登记回测模式、缓存、`entry_mode/exit_mode/stop_loss_mode`、`backtest_start/end`、`aggregation` 扩展位和小周期分析口径。
5. 扩展现有单一 MCP `backtest` 工具：`action`、`speed`、`use_cache`、`execution={entry_mode,exit_mode,stop_loss_mode}`；不新增三个公开工具或 `describe_capabilities`。
6. 让 MCP schema、工具说明和默认值从 registry 生成/校验，增加 registry 与 `execution_modes.py`、runner schema、实际 artifacts 的对拍测试。
7. 增加统一返回 envelope，确认工具不会误重跑回测或误生成报告/PNG，并保留 legacy `exit_mode=stop` 的迁移错误语义。
8. 从 registry 生成 `vibe-trading-bridge` 的能力索引、MCP server instructions 和 HowToUse/README 能力表；bridge skill 引用三字段当前契约和 next-open risk-based sizing 暂不支持的限制；通过 `SkillsLoader` 与 MCP `list_skills/load_skill` 验证可发现、可加载。
9. 配置 Codex 的 Vibe-Trading stdio MCP；执行 `codex mcp list` 和 `/mcp` 核对 enabled。
10. 使用小规模本地 run 做端到端验证：
   - `backtest(action="run", speed="fast")`：有 metrics/trades/equity/run_card/digest，无 PNG、无 `analysis.md`；
   - `backtest(action="charts")`：只新增 PNG，不重跑引擎；
   - `backtest(action="report")`：只新增 `analysis.md`/status，不重跑引擎；
   - cache true/false：行为和返回状态准确；
   - 小周期：时间戳、`backtest_start/end`、`holding_bars`、fastrun digest 降级口径正确。
10. 运行后端定向测试、MCP 测试、runner/digest 测试和前端构建；最后更新 HowToUse、计划状态与 ITERATION_LOG。

## 开工前核对

- 需求目标 / 范围与讨论记录一致
- 已完成前置契约是否已对拍：V042 cache env + V043 三字段 execution modes → MCP workflow
- capability registry 是否作为唯一维护入口，生成物范围是否明确
- 默认 fast 是否只作用于 MCP/Codex 路径，未误改 CLI/WebUI 旧默认值
- 单一 `backtest` 入口的 `action/speed/use_cache/execution` schema 是否覆盖用户需求
- cache 默认关闭和用户显式开启的优先级已冻结
- `entry_mode/exit_mode/stop_loss_mode`、小周期窗口和缓存是否已纳入同一能力契约
- charts/report 是否保证只做后处理、不重跑回测
- 小周期分析的 `backtest_start/end`、时间戳、`holding_bars` 口径已冻结
- bridge skill、MCP instructions 与 HowToUse 的生成/分工已冻结，不复制完整策略 skill
- 执行清单覆盖所有验收标准
- Codex 配置写入范围和 allowed run roots 已确认
- 验收标准可验证
- 元信息已填

## 验证

### 1. 已完成基线对拍

- 复核当前代码基线：HEAD `9afc0b9` 包含 V043 三字段执行模式/独立硬止损，前置 `e517559` 包含 V042 cache env 修复；本需求不得改变上述执行语义和缓存 key/版本。
- 运行 V042/V043 已有定向回归，作为本需求前置基线：

  ```powershell
  cd <repo_root>\agent
  ..\.venv\Scripts\python.exe -m pytest tests/test_runner_dotenv.py tests/test_engine_execution_modes.py tests/test_runner_coverage.py -q
  ```

  预期：V042 dotenv/cache 回归、V043 execution profile/runner 早失败和 runner coverage 均通过；已有基线失败不因本需求扩大。

### 2. 能力注册表与生成物

- capability registry 与 `agent/backtest/execution_modes.py`、runner schema 对拍：三字段、四个 preset、旧 `exit_mode=stop` 迁移错误、未开放的 normal 非对称组合完全一致。
- 运行能力同步生成器两次，第二次不产生 diff；生成后的 MCP schema、server instructions、bridge skill 能力索引、HowToUse/README 生成区块保持一致。
- 增加漂移测试：注册表缺 handler、MCP 参数缺 registry 定义、生成文档未更新时测试失败；bridge skill 的 10 项工作流边界不因参数生成而重复膨胀。

### 3. 单一 `backtest` MCP 工具模式

使用一个小型本地 run 副本，逐项验证：

- `backtest(action="run", speed="fast", use_cache=true)`：运行 `--fastrun`；产出核心 `metrics/trades/equity/positions/run_card/digest`，不产生 PNG 和 `analysis.md`。
- `backtest(action="run", speed="normal")`：不跳过 regime/MAE-MFE，其他默认语义与直接 runner 一致。
- `backtest(action="charts")`：只调用图表后处理，不启动 loader、SignalEngine 或引擎；允许新增/更新派生的 `analysis.digest.json` 与 `analysis_charts/*.png`，核心 artifacts 的 hash 不变。
- `backtest(action="report")`：只调用报告后处理，不启动 loader、SignalEngine 或引擎；允许新增/更新派生的 `analysis.digest.json`、`analysis.md`、`analysis.status.json` 及必要的 prompt 审计文件，核心 artifacts 的 hash 不变。
- `backtest(action="full")`：按明确顺序完成正常回测、digest、PNG 和报告；返回 envelope 明确列出每一阶段是否执行。
- 缺少 `run_card.json`/核心 metrics 时，charts/report 返回可读错误，不偷偷重跑回测。
- `execution={entry_mode, exit_mode, stop_loss_mode}`：合法三字段进入现有 runner/engine；旧 `exit_mode=stop` 在数据加载前返回迁移错误；MCP 不静默改写原 `config.json`。

### 4. fast/normal 结果一致性

- 同一 run 先跑 normal、再跑 fast，比较 `metrics.csv`、`trades.csv`、`equity.csv`、`positions.csv` 和核心 run-card 字段：这些回测/交易结果必须一致；只允许 digest 缺少 fastrun 规定的 regime/MAE-MFE 字段。
- 验证 fastrun 重跑对已有 digest 的覆盖行为，以及完整 normal 重跑可恢复完整 digest；与 HowToUse 8.38/V032 口径一致。
- 验证默认 CLI/直接 runner 行为不因 MCP 扩展改变。

### 5. 缓存开关

- `use_cache=true`：子进程实际读取 V042 统一 dotenv/cache 配置，重复相同 source、symbol、interval、区间时命中缓存。
- `use_cache=false`：本次调用绕过 loader cache，不删除已有缓存，不改变全局 `.env`；返回 envelope 标记 `cache_enabled=false`。
- `VIBE_TRADING_DATA_CACHE_ROOT` 自定义目录仍按 V042 行为生效；缓存不被误当作 data-bridge 离线数据。

### 6. 外部 Agent 策略生成契约

- 使用 Codex/Z-Code 模拟调用：新建独立 run 目录，只写 `config.json` 和 `code/signal_engine.py`。
- 检查 Agent 不会修改 `backtest/engines`、`backtest/loaders` 或生成第二套 runner。
- 检查 `config.json` 能正确承载 `source/codes/interval/start_date/end_date/backtest_start/backtest_end/entry_mode/exit_mode/stop_loss_mode` 等字段。
- 人工确认前不调用 backtest；确认后调用单一 `backtest`；调参使用 run 副本且不进入 Vibe-Trading LLM 无限循环。
- 回测后 Agent 必须读取 `metrics.csv`、`trades.csv`、`positions.csv`、`equity.csv` 和 `run_card.json`，并能解释 normal exit 与 hard stop 的 `reason`。

### 7. 小周期回测分析

- 使用 5m/15m 本地 run 验证：`start_date/end_date` 负责数据加载和 warmup，`backtest_start/backtest_end` 负责执行窗口。
- `trades.csv` 保留日内完整 timestamp，`holding_bars` 与 metrics 口径一致。
- fast action 不生成 PNG/LLM 报告；charts/report 后处理读取同一 run artifacts，不改变交易结果。
- 确认小周期 fastrun 不会因 digest 缺失字段导致 WebUI/报告读取崩溃。

### 8. 安全与路径回归

- `run_dir` 仍经过 allowed run roots 校验；不允许通过 MCP action 访问根目录外的策略文件。
- 原 run 不被静默覆盖；需要变体时由 Agent 创建副本。
- MCP stdio 默认不启用 shell-capable tools，API key 不进入 skill、registry 或生成文档。

### 9. 最终回归

- 后端 MCP/runner/digest/analysis 定向 pytest；前端相关分析页测试和 `npm run build`。
- 生成的 HowToUse/README/bridge skill 与 registry 对拍无 diff。
- 收尾记录实际测试命令、耗时、run_id、artifact hash 对比和已知局限。

### 实际执行结果（V044）

1. **基线对拍：通过**。`tests/test_runner_dotenv.py tests/test_engine_execution_modes.py tests/test_runner_coverage.py`：31 passed。
2. **注册表与生成物：通过**。同步生成器连续执行两次均输出 `generated files are in sync`；skill、MCP schema、README/HowToUse 能力块对拍通过。
3. **单一 backtest 入口：通过**。MCP/stdio/registry/新工具回归 62 passed；本次改动面最终定向回归 204 passed、1 skipped。不存在独立公开的 `fast_backtest`、`generate_charts`、`generate_report` 工具。
4. **fast/normal：通过**。真实小型本地 run 的核心 `metrics/trades/positions/equity` 文件逐字节一致；fast digest 只省略 `regime` 与 `mae_mfe_summary`，正常 digest 可恢复；fast/normal 都没有隐式 PNG 或 `analysis.md`。
5. **缓存：通过**。`use_cache=true/false` 分别向子进程传入 `VIBE_TRADING_DATA_CACHE=1/0`；`VIBE_TRADING_DATA_CACHE_ROOT` 在 allowlist 中可透传；不改全局 `.env`、缓存 key 或已有缓存。
6. **外部 Agent 契约：通过**。bridge skill 由 registry 生成且仅保留 10 条工作流边界；策略 run 约束为 `config.json` + `code/signal_engine.py`，不重写 engines/loaders；人工确认、逐笔产物读取、单问题迭代和有限失败处理均已写入 skill。
7. **小周期/分析：通过**。现有 digest/engine 测试覆盖 timestamp、`holding_bars`、`backtest_start/end` 及 fast 缺失字段；charts/report 后处理 hash 守卫通过，未启动 loader/SignalEngine/engine。
8. **安全与路径：通过**。MCP shell 默认关闭，allowed run roots 和 file-tool path 测试通过；Codex 配置使用本地 stdio server，不暴露 shell capability 或 API key。
9. **最终回归：改动面通过，完整套件有环境基线失败**。前端 Vitest 458 passed，`npm run build` 成功；完整后端 pytest 为 `9526 passed, 86 skipped, 85 failed, 9 errors`，失败集中于 Windows symlink 权限、可选/网络 fixture 与既有共享状态，不涉及本迭代改动文件，已记录 M037/E114。后续默认 cache 已改为关闭，并补跑默认值与生成物同步检查。

### 最终核对

- 计划状态、计划 README 索引、ITERATION_LOG V044、Mistake_Journal M037 和全局日志 E114 已同步。
- 核心实现只增加 MCP/工作流 registry、runner 参数/环境透传、bridge skill、生成器和验证；未修改 `backtest/engines` 或 `backtest/loaders` 业务逻辑。
- `charts/report` 的准确语义已统一为：可更新派生 `analysis.digest.json`，但核心 artifacts hash 不变；报告 action 只调用一次报告 LLM。
- `git diff --check` 通过；生成文件无 drift；Codex CLI 已确认 `vibe_trading enabled`。

## 讨论记录

- 2026-08-22 用户提出：希望 Codex 默认 fast backtest、不生成报告和图片、默认开启缓存，并能理解 fast_backtest / generate_charts / generate_report / cache 开关 / 小周期分析。
- 2026-08-22 评估结论：当前 fastrun 已有 CLI 实现，但 MCP backtest 不透传 flag；需要 MCP 工具层 + bridge skill 双层补齐，不能只改使用文档。
- 2026-08-22 推荐方案：Codex/MCP 默认走 `fast_backtest`，保留 CLI/直接 runner 既有默认行为；报告和 PNG 作为显式后处理工具。
- 2026-08-22 用户提出维护漂移疑问：不希望每次迭代分别手改 HowToUse、MCP、skill；并指出 `entry_mode` / `exit_mode` 也容易遗漏。
- 2026-08-22 范围调整建议（待用户确认）：增加单一能力/工作流注册表，统一登记工具名、runner 参数、缓存默认值、产物、entry/exit mode、小周期口径和文档锚点；由生成器或运行时注册表同步 MCP schema、server instructions、bridge skill 和 HowToUse 的生成区块，迭代日志继续保留为历史叙事，不作为当前能力真相源。
- 2026-08-22 用户追问第 1 点：`fast_backtest` / `generate_charts` / `generate_report` 的性质。结论：它们是 MCP 的可执行工具，不是 skill；skill 只能说明何时调用、调用顺序和边界，不能替代缺失的执行接口。
- 2026-08-22 用户追问第 2 点：`vibe-trading-bridge` 的归属。结论：源文件放在 Vibe-Trading 仓库，通过 Vibe MCP 的 `load_skill` 提供给 Codex/Z-Code；如其他 Agent 不能连 MCP，才从同一源生成副本，不手工维护第二份。
- 2026-08-22 用户确认：接受“能力注册表单一真相源 → 自动生成 MCP schema / server instructions / bridge skill / HowToUse 能力表”的方向；本计划仍保持“讨论中”，等待本次计划文本修改后再次确认。
- 2026-08-22 用户进一步提出工具数量疑问：不希望把同一回测生命周期拆成多个公开 MCP tool，担心 Agent 选择困难。
- 2026-08-22 设计修正：不公开新增 `fast_backtest` / `generate_charts` / `generate_report` 三个工具；统一扩展原 `backtest` 的 `action`、`speed`、`use_cache`、`execution` 参数。三者保留为 action/能力 ID，内部 handler 不直接暴露。
- 2026-08-22 bridge skill 职责再次收敛：不重复 MCP 参数说明，只保留原约定的工作流能力和协作边界；参数由 MCP schema、server instructions 和能力注册表提供。
- 2026-08-22 用户要求复查其他“讨论中”计划的前置关系，避免本需求先固化接口后被后续引擎/缓存计划迫使返工。
- 2026-08-22 依赖评估结论：P-20260822-risk_exit_execution_modes 与 P-20260816-cache_env_once 为硬前置或必须并入 Phase 0；交易时间聚合、换约识别、仓位指标和报告目录选择器为软依赖/非阻塞，但 registry 和 MCP 必须保留配置、run_dir、artifact 口径的扩展兼容性。
- 2026-08-23 状态更新：P-20260816-cache_env_once 已完成并关联 V042；P-20260820-execution_mode_state_machine 已废弃；P-20260822-risk_exit_execution_modes 已完成并关联 V043。当前 MCP 计划不再实现或等待 execution/cache 前置，改为消费已落地的 V042/V043 契约。
- 2026-08-23 新执行契约：MCP `execution` 必须登记 `entry_mode`、`exit_mode`、`stop_loss_mode` 三字段；旧 `exit_mode=stop` 保留为可观察的迁移失败，不得在 MCP 或 bridge skill 中重新解释为新模式；next-open risk-based sizing、take-profit mode、fill callback 仍不在本期范围。
- 2026-08-23 文档核对：HowToUse 8.34、策略生成 skill 和 SDM skill 已同步三字段；8.35 已同步 V042；8.24 的分析 PNG 旧表述仍需在本需求的文档同步阶段修正，8.36 需继续与 V030/8.38 的默认跳过 PNG 语义对齐。
- 2026-08-23 用户要求：cache_env_once 已完成，旧 execution_mode_state_machine 已废弃，当前计划必须基于最新 git、V042/V043、HowToUse 和新风险止损计划重新调整。
- 2026-08-23 调整结论：本需求不再把缓存或执行状态机列为待实现前置；MCP 直接消费 V042 的 dotenv/cache 行为和 V043 的三字段 execution profile，只补工具参数、工作流契约、能力注册表和外部 Agent 协作层。
- 2026-08-23 用户确认：按本计划执行；验证必须严格逐项覆盖“验证”章节的 1–9 项，并在冒烟测试、回归测试后完成最终核对。
- 2026-08-23 后续调整：用户明确不希望默认开启行情缓存；MCP `use_cache` 默认改为 `false`，仅在用户明确要求时传 `true`，Codex 配置移除 `VIBE_TRADING_DATA_CACHE=1`，schema/instructions/文档由注册表同步更新。

## 后续可迭代方向

- 当前能力注册表只覆盖 **MCP 回测工作流**：`backtest` 的 action、参数、默认值、缓存、execution profile、bridge skill 和对应的 HowToUse/README 生成区块。
- 新增普通 MCP 工具（例如新的 `get_xxx` 工具）时，当前流程不会自动更新完整的 README MCP tools 总表，也不会自动新增对应的 HowToUse 使用说明；运行时工具注册和文档同步目前是两条链路。
- 新增普通 skill 时，`SkillsLoader` 会在运行时自动发现并加载，但 README 的 skill 数量、分类和说明不会自动生成；现有测试只能发现漂移并报错，不能自动修改文档。
- 当前同步器是命令驱动的，不是文件监听器：需要先更新能力注册表，再运行 `agent/scripts/sync_backtest_capabilities.py`；`--check` 可用于 CI/收尾时发现生成物 drift。
- 如果未来希望所有 MCP 新工具都自动同步，需另建全局 MCP 工具注册表/文档生成机制，至少覆盖：工具名称、用途、参数 schema、README 总表、HowToUse 使用说明、skill 索引和漂移检测。本需求暂不增加该范围。

## 风险 / 注意

- `--fastrun` 会覆盖同一 run 的 digest 为精简版；完整 digest 需要完整重跑恢复。
- `generate_report` 会调用 LLM；必须保持显式调用，不能让 fast backtest 隐式生成。
- `generate_charts` 是后处理，依赖已有 artifacts；缺少完整 artifacts 时应返回可读错误，不应偷偷重跑。
- MCP stdio server 的环境变量由 Codex client 注入；不要把 API key 写入 skill 或仓库配置。
- `VIBE_TRADING_ALLOWED_RUN_ROOTS`、`VIBE_TRADING_DATA_CACHE_ROOT` 需要同时考虑 MCP 主进程和回测子进程的路径可见性。
- 不得把 `entry_mode` / `exit_mode` / `stop_loss_mode` 的字符串白名单直接复制到 MCP/skill；应由公共 execution profile 生成，避免 MCP 与引擎再次漂移。
- `aggregation`、`logical_groups`、报告目录 `dir` 等后续配置/路径扩展不得被 MCP 工具硬编码为 runs 根目录或自然时间聚合。
- execution mode 的实现与迁移以已完成计划 `P-20260822-risk_exit_execution_modes.md` 为准；旧计划保留为已废弃历史，不再作为 MCP 前置引用。
