# 计划：MCP 回测模式与外部 Agent 协作工作流

> 编号：P-20260822-mcp_backtest_workflow
> 状态：讨论中
> 日期：2026-08-22
> 关联迭代：待填（收尾时填 V 号）
> 关联：P-20260816-cache_env_once / P-20260817-fastrun / P-20260822-risk_exit_execution_modes / commit / run（收尾时补）

## 项目调研

- 内部·MCP 工具：`agent/mcp_server.py` 的 `backtest` 当前只接收 `run_dir`；`agent/src/tools/backtest_tool.py` 调用 runner 时只传 run 目录，不透传 `--fastrun`、`--with-charts`、`--with-analysis` 等 CLI 选项。
- 内部·CLI 能力：`agent/backtest/runner.py` 已支持 `--fastrun`、`--without-regime`、`--without-mae-mfe`、`--with-charts`、`--with-analysis`。
- 内部·既有迭代：V030 已将 PNG 改为默认跳过；V032 已实现 fastrun，但明确记录 MCP backtest 不透传 flag。详见 `ITERATION_LOG.md` V030/V032。
- 内部·使用手册：HowToUse 8.35 记录 loader cache，8.36/8.37 记录分析图、报告独立补生成，8.38 记录参数探索与 fastrun，12 记录小周期回测口径。
- 内部·缓存计划：P-20260816-cache_env_once 仍为“讨论中”，直跑 runner 尚未统一加载 `<vibe_home>/.env`。
- 内部·文档一致性：HowToUse 8.36 开头仍有“每次回测自动生成 PNG”的旧表述，与 V030/8.38 及当前 runner 默认 `with_charts=False` 冲突，需要同步修正。
- 内部·skill：当前 `strategy-generate`、`strategy-dev-manager`、`backtest-diagnose` 未包含上述 CLI-only 模式说明，需增加独立的 `vibe-trading-bridge` skill，避免重复复制完整策略生成 skill。

## 前置计划与顺序评估

- **已完成前置：P-20260822-risk_exit_execution_modes**。本需求要把三字段 execution profile 写入 capability registry 和 MCP schema；现在 normal/stop 路径、`next_open/stop`、缺少 `stop_prices`、同 bar 冲突等语义已有计划与回归验证，后续 MCP 实现应复用公共校验，不得复制字符串白名单。
- **必须先完成/并入：P-20260816-cache_env_once**。本需求默认 `use_cache=true`，需要先统一 runner 加载 `<vibe_home>/.env` 的路径；否则 CLI、MCP 子进程和直跑 runner 可能出现不同缓存行为。该计划只改 env 加载，不改缓存算法，风险和范围可控。
- **软依赖：P-20260818-trading_time_aggregation**。它会增加 `aggregation` 配置并改变小周期 bar 的时间边界，但不直接改 MCP `backtest` 的动作层；本需求应把 `aggregation` 作为可扩展 config 字段透传，不在 bridge skill 中写死自然时间聚合。若该计划在本需求之前落地，只需重新生成能力表和小周期说明，不需要重写 MCP 工具。
- **非前置阻塞：P-20260816-contract_switch_auto**。它改 local loader 的 `contract` 列透传和策略侧换约识别，不改变 MCP 回测动作；本需求只需确保 run_dir/config/artifact 以通用方式传递。
- **非前置阻塞：P-20260817-reports_dir_selector**。它只改 WebUI 报告目录读取链路；本需求的 MCP 工具应始终使用完整 `run_dir` 和 allowed roots，不假设 run 一定在 runs 根目录，避免未来子目录选择器返工。
- **非前置阻塞：P-20260818-position_weight_magnitude**。它改 metrics/digest 的仓位口径；本需求只返回当前 artifacts 和状态，不在 MCP 层硬编码指标含义。报告/图表后处理应读取现有产物，兼容该计划未来的字段变化。

## 需求目标

- 做什么：让 Codex 通过 Vibe-Trading MCP 能稳定理解并调用普通回测、快速回测、分析图生成、分析报告生成和缓存开关。
- 默认行为：Codex/MCP 协作路径默认使用 fast backtest；不生成 `analysis.md`；不生成 PNG；默认打开 loader cache。
- 显式能力：只保留一个公开 MCP `backtest` 工具，通过 `action`、`speed`、`use_cache`、`execution` 参数支持快速回测、普通回测、图片、报告和成交模式。
- 小周期支持：bridge skill 只说明工作流边界；参数 schema/默认值由 MCP 注册表提供。能力包括 `start_date/end_date` 与 `backtest_start/backtest_end`、完整时间戳、`holding_bars`、fastrun 与分析产物之间的关系。
- 范围 / 边界：推荐只改变 MCP/外部 Agent 默认工作流；保留 CLI `vibe-trading run` 与直接 runner 的现有默认语义，避免破坏既有用户流程。若用户确认要全局改变 CLI 默认值，另列为范围变更。
- 验收标准：Codex 只通过 MCP 和 bridge skill，即可按用户意图选择 fast backtest、补 PNG、补报告、控制缓存，并能在执行前后解释会生成或不会生成哪些产物。

## 实现方案

1. **单一能力/工作流注册表（唯一维护入口）**
   - 新增一个可执行的 capability registry，统一登记：工具/工作流名称、用途、参数、默认值、runner flags、产物、跳过项、缓存行为、`entry_mode/exit_mode`、小周期口径、HowToUse/ITERATION_LOG 锚点。
   - `fast_backtest`、`generate_charts`、`generate_report` 只作为能力/动作 ID，不作为三个公开 MCP 工具；公开工具数量保持最少。
   - `entry_mode/exit_mode` 的允许组合、默认值和配置字段也由注册表登记，并与 `BaseEngine` 校验对拍，避免再次遗漏。
   - 不新增 `describe_capabilities` 公开工具；能力索引由注册表生成到 MCP server instructions、bridge skill 和 HowToUse 能力表。

2. **MCP 工具层**
   - 扩展现有 `backtest` 为单一公开入口：`backtest(run_dir, action="run|charts|report|full", speed="fast|normal", use_cache=true, execution=...)`。
   - `action="run"` 默认 `speed="fast"`，调用 runner 的 `--fastrun`，不生成 PNG/LLM 报告；`speed="normal"` 执行完整 digest。
   - `action="charts"` 只调用确定性的 `generate_chart_artifacts`，不重跑行情和引擎；`action="report"` 只调用 `generate_analysis_report`；`action="full"` 才执行完整回测并显式补图/报告。
   - `execution` 只暴露/校验 `entry_mode`、`exit_mode` 的允许组合；实际配置仍以 run 目录 `config.json` 为准，不由工具静默改写原 run。
   - `use_cache=true/false` 安全传入回测子进程；必要时补齐 `VIBE_TRADING_DATA_CACHE_ROOT` 的 runtime env allowlist。
   - 返回结构统一报告 `action`、`speed`、`cache_enabled`、`backtest_reran`、`charts_generated`、`report_generated`、执行模式和核心 artifact 路径。

3. **从注册表生成 MCP instructions / bridge skill / HowToUse 能力表**
   - `vibe-trading-bridge` 的源文件放在 Vibe-Trading 仓库，通过 MCP 的 `load_skill` 提供给 Codex/Z-Code；不在多个 Agent 中手工维护副本。
   - bridge skill 只承载协作边界和 10 项工作流能力：目录/契约、禁止重写引擎、生成与回测分离、人工确认、产物审计、单问题迭代、失败不无限重试等；不重复 MCP 参数说明。
   - MCP tool schema 负责参数类型、枚举、默认值、返回字段和错误；MCP server instructions 负责默认路由和跨工具约束。
   - 生成 MCP server 初始化 instructions，明确默认 fast、无报告、无 PNG、cache 开启、参数探索不走 LLM、不得重写回测引擎和 loader。
   - HowToUse 只保留详细解释、案例和坑；当前能力矩阵、参数、默认值和 MCP 工具表由注册表生成区块，避免三处漂移。

4. **缓存一致性**
   - 复用/完成 P-20260816-cache_env_once：直跑 runner 统一加载 `<vibe_home>/.env`。
   - Codex MCP 配置的 Vibe server 默认注入 `VIBE_TRADING_DATA_CACHE=1`；单次 `use_cache=false` 优先级高于默认值。
   - 不改缓存 key 语义，不把 cache 当离线数据源；保留 data-bridge 作为确定性离线数据方案。

5. **文档和迭代留痕**
   - 修正 HowToUse 8.36 的 PNG 默认行为冲突。
   - 由注册表生成/同步 HowToUse 的 MCP 使用表和 README MCP tools 表。
   - `ITERATION_LOG` 继续记录为什么做、讨论结论、验证和影响，不作为当前能力的唯一真相源。

6. **Codex 配置**
   - 在确认后将 Vibe-Trading stdio MCP 注册到 `<codex_home>/.codex/config.toml`，使用 `<repo_root>/.venv/Scripts/python.exe` 启动 `agent/mcp_server.py`。
   - 默认传入 cache 环境变量和允许的 run roots；不启用 shell-capable tools。

## 执行清单

1. 先处理前置计划：冻结/实现 P-20260820 的公共 execution profile、配置校验和 `entry_mode/exit_mode` 语义；若不单独完成，则将其作为本计划 Phase 0，禁止先暴露未定稿的 execution schema。
2. 复用/完成 P-20260816-cache_env_once，统一 runner 的 `<vibe_home>/.env` 加载，并完成 cache 开关回归测试。
3. 复读本计划与 P-20260817-fastrun，完成开工前核对并确认“默认 fast 仅作用于 MCP/Codex 路径”。
4. 设计并实现 capability registry，登记回测模式、缓存、已冻结的 `entry_mode/exit_mode`、`backtest_start/end`、`aggregation` 扩展位和小周期分析口径。
5. 扩展现有单一 MCP `backtest` 工具：`action`、`speed`、`use_cache`、`execution`；不新增三个公开工具或 `describe_capabilities`。
6. 让 MCP schema、工具说明和默认值从 registry 生成/校验，增加 registry 与实际 runner/engine 的对拍测试。
7. 增加统一返回 envelope，确认工具不会误重跑回测或误生成报告/PNG。
8. 从 registry 生成 `vibe-trading-bridge` 的能力索引、MCP server instructions 和 HowToUse/README 能力表；bridge skill 的工作流边界保持稳定；通过 `SkillsLoader` 与 MCP `list_skills/load_skill` 验证可发现、可加载。
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
- 前置计划顺序是否已冻结：execution mode → cache env → MCP workflow
- capability registry 是否作为唯一维护入口，生成物范围是否明确
- 默认 fast 是否只作用于 MCP/Codex 路径，未误改 CLI/WebUI 旧默认值
- 单一 `backtest` 入口的 `action/speed/use_cache/execution` schema 是否覆盖用户需求
- cache 默认打开和单次关闭的优先级已冻结
- `entry_mode/exit_mode`、小周期窗口和缓存是否已纳入同一能力契约
- charts/report 是否保证只做后处理、不重跑回测
- 小周期分析的 `backtest_start/end`、时间戳、`holding_bars` 口径已冻结
- bridge skill、MCP instructions 与 HowToUse 的生成/分工已冻结，不复制完整策略 skill
- 执行清单覆盖所有验收标准
- Codex 配置写入范围和 allowed run roots 已确认
- 验收标准可验证
- 元信息已填

## 验证

（用户确认后补充具体测试命令、run_id 和耗时对比。）

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

## 风险 / 注意

- `--fastrun` 会覆盖同一 run 的 digest 为精简版；完整 digest 需要完整重跑恢复。
- `generate_report` 会调用 LLM；必须保持显式调用，不能让 fast backtest 隐式生成。
- `generate_charts` 是后处理，依赖已有 artifacts；缺少完整 artifacts 时应返回可读错误，不应偷偷重跑。
- MCP stdio server 的环境变量由 Codex client 注入；不要把 API key 写入 skill 或仓库配置。
- `VIBE_TRADING_ALLOWED_RUN_ROOTS`、`VIBE_TRADING_DATA_CACHE_ROOT` 需要同时考虑 MCP 主进程和回测子进程的路径可见性。
- 不得把 `entry_mode` / `exit_mode` / `stop_loss_mode` 的字符串白名单直接复制到 MCP/skill；应由公共 execution profile 生成，避免 MCP 与引擎再次漂移。
- `aggregation`、`logical_groups`、报告目录 `dir` 等后续配置/路径扩展不得被 MCP 工具硬编码为 runs 根目录或自然时间聚合。
- execution mode 的实现与迁移以已完成计划 `P-20260822-risk_exit_execution_modes.md` 为准；旧计划保留为已废弃历史，不再作为 MCP 前置引用。
