# 计划：BacktestConfigSchema 配置契约与 Agent 暴露

> 编号：P-20260827-backtest_config_schema_agent
> 状态：已完成
> 日期：2026-08-27
> 关联迭代：V046
> 关联：本次提交 / 无真实 run（本次未改引擎行为）

## 项目调研

- 内部·配置校验：`agent/backtest/runner.py` 的 `BacktestConfigSchema` 当前声明 `codes`、`start_date`、`end_date`、`source`、`interval`、`engine`、三字段 execution、`initial_cash`、`fundamental_fields`、`event_feeds`；模型使用 `extra="allow"`，因此未声明的引擎扩展字段也会被放行。
- 内部·窗口现状：`backtest_start` / `backtest_end` 已由 runner 传给策略，并由 `agent/backtest/engines/base.py` 截取实际执行和统计窗口，但尚未正式声明在 `BacktestConfigSchema` 中。
- 内部·逻辑标的现状：`config.json.logical_groups` 已由 `agent/backtest/logical_groups.py` 独立解析和校验，负责成员 code、重复归组、`chart_code` 归属以及未分组 code 的兼容回退。
- 内部·MCP 分层：`agent/src/backtest_capabilities.py` 的 `backtest_tool_schema()` 只描述 MCP `backtest` 的调用参数；server instructions、bridge skill 和 HowToUse 能力块由注册表生成，不能把 `config.json` 字段误建模为 `backtest(...)` 顶层参数。
- 内部·配置范围：不同引擎还会读取各自的费率、滑点、保证金、基准和数据扩展字段；本计划先明确外部 Agent 生成策略所需的通用配置契约，并保留 engine-specific 扩展兼容位，不在没有字段盘点和兼容性验证的情况下收紧全部 `extra`。

## 需求目标

- 做什么：让 Agent 通过 MCP 暴露的 `BacktestConfigSchema` 配置契约，知道如何创建和修改 `run_dir/config.json`，并理解每个通用字段的类型、默认值、作用和使用关系。
- 核心字段：正式说明 `codes`、`source`、`interval`、`start_date`、`end_date`、`backtest_start`、`backtest_end`、`engine`、`initial_cash`、`entry_mode`、`exit_mode`、`stop_loss_mode` 和 `logical_groups`。
- 关键口径：明确 `start_date/end_date` 是行情加载和指标预热窗口，`backtest_start/end` 是实际交易与统计窗口；同一真实标的的多个执行 code 必须通过 `logical_groups` 合并为一个逻辑标的。
- Agent 可见性：`BacktestConfigSchema` 的字段说明作为唯一配置说明源，自动生成 MCP server instructions 的配置摘要；Agent 不需要依赖 HowToUse 才能完成基本配置。
- 保持现状：继续使用单一公开 MCP `backtest` 工具；配置字段留在 `config.json`，不新增 `backtest` 顶层参数，不改变 fast/cache 默认行为。

## 范围 / 边界

- **包含**：配置模型字段描述和通用字段定义、`backtest_start/end` 的兼容性校验、`logical_groups` 的结构 schema、从配置模型生成 Agent 可读摘要、bridge skill 的核对提示、生成文档和定向测试。
- **不包含**：修改 `backtest/engines`、`backtest/loaders`、成交逻辑、指标口径、缓存逻辑、策略生成算法或 WebUI 展示逻辑。
- **不包含**：把 `start_date`、`backtest_start/end`、`logical_groups` 变成 MCP `backtest()` 的顶层调用参数；不新增 `describe_config` 或其他公开 MCP 工具。
- **兼容边界**：暂时保留 `extra="allow"`，不因本计划一次性禁止引擎专属扩展字段；窗口校验只在与当前 runner/engine 语义一致且完成历史配置核对后收紧。

## 实现方案

### 1. 让 `BacktestConfigSchema` 成为配置契约源

- 为现有通用字段增加 `Field(description=...)`、默认值说明、允许值说明和使用关系；字段说明要面向 Agent，包含“什么时候配置”和“会影响什么”。
- 将 `backtest_start` / `backtest_end` 声明为可选日期字段，保持不配置时行为不变；增加与当前引擎一致的日期格式和窗口顺序校验，是否强制要求执行窗口落在数据窗口内，先以历史 config 兼容性核对结果为准。
- 为 `logical_groups` 增加嵌套配置模型，描述 `logical_symbol`、`display_name`、`codes`、`chart_code` 的类型和作用；结构校验交给 Pydantic，成员必须属于顶层 `codes`、不得重复归组等跨字段规则继续由 `parse_logical_groups()` 负责，避免复制两套业务语义。
- 保留 `extra="allow"`，并在 schema 说明中明确：引擎专属字段仍可扩展，通用配置契约只列出 Agent 生成策略必须掌握的字段。

### 2. 从配置模型向 MCP Agent 暴露

- 新增一个由 `BacktestConfigSchema.model_json_schema()` 驱动的紧凑配置摘要渲染函数；摘要包含字段名、必填/默认、类型、描述和关键示例，不把完整 JSON schema 无限制塞进系统 instructions。
- 将摘要接入 `render_mcp_instructions()`，使 Agent 连接 MCP 后可以直接获得“如何写 `config.json`”的说明；继续保留 `backtest_tool_schema()` 作为“如何调用 `backtest`”的独立 schema。
- `backtest` 的 `run_dir` 参数说明只引用配置契约和文件位置，不重复维护字段白名单；调用前的 MCP 参数核对和配置文件内的字段核对分开表达。

### 3. bridge skill 与文档分工

- bridge skill 继续保持 10 条工作流边界，不复制完整配置字段表；在第 2/4 条保留两步核对要求：写 `config.json` 时遵循 `BacktestConfigSchema`，调用 `backtest` 时遵循 MCP tool schema。
- HowToUse/README 的详细字段表和示例由配置 schema 摘要或现有生成器同步，避免手工维护第三套参数定义；人工文档可保留面向用户的案例和坑。
- 生成区块继续通过 `agent/scripts/sync_backtest_capabilities.py` 更新，并用 `--check` 检测漂移。

## 执行清单

1. 在用户确认前，完成通用 config 字段、`backtest_start/end` 和 `logical_groups` 的现状盘点，核对 Pydantic、runner、engine、parser 的职责边界。
2. 扩展 `BacktestConfigSchema` 及必要的嵌套模型/字段校验；保留旧 config 无窗口、无逻辑分组和带引擎扩展字段的兼容行为。
3. 实现从 `BacktestConfigSchema` JSON schema 到 MCP instructions 配置摘要的生成；保持 `backtest` 单一入口和现有 MCP 调用 schema 不变。
4. 更新 bridge skill 的核对措辞，并同步 HowToUse/README 生成区块；不在 skill 中复制完整参数定义。
5. 增加 schema 字段/描述、窗口、逻辑分组、兼容性、MCP 暴露和生成物无漂移测试。
6. 按验证章节执行定向单测、MCP 冒烟/回归、`py_compile`、生成器 `--check` 和 `git diff --check`；本计划不要求因配置说明改动而重跑大规模真实回测，除非兼容性测试发现行为变化。
7. 实现收尾时更新计划状态、计划 README、HowToUse/README、`ITERATION_LOG` 完成条目和提交信息；迭代日志不得在用户确认前把计划写成已完成。

## 开工前核对

- 需求目标 / 范围与讨论记录一致
- 已区分 MCP 工具调用 schema 与 `config.json` 配置 schema
- 已明确 `BacktestConfigSchema`、`parse_logical_groups()` 和引擎读取逻辑的职责边界
- 已确认 `backtest_start/end` 的兼容校验范围，不会无依据收紧历史 config
- 已确认 `logical_groups` 的结构校验不会复制或替代现有跨字段业务校验
- 方案没有新增公开 MCP 工具或 `backtest` 顶层配置参数
- Agent 可见的配置摘要确实从 `BacktestConfigSchema` 生成，而不是在 skill/MCP 中各写一份
- bridge skill 仍保持 10 条工作流边界，并保留“配置 schema / MCP tool schema 分别核对”的提醒
- 执行清单覆盖生成、暴露、兼容性、同步和验证要求
- 用户已确认本计划后，才将状态改为“已确认”并开始写码

## 验证

- `BacktestConfigSchema.model_json_schema()` 包含核心字段、类型、默认值和字段描述；`backtest_start/end`、`logical_groups` 的结构可被 Agent 读取。
- 旧 config（无 `backtest_start/end`、无 `logical_groups`）仍可通过；合法窗口和合法逻辑分组可通过；非法日期、逆序窗口、非法分组结构仍能在回测前可读失败。
- MCP instructions 含从配置模型生成的核心字段摘要，同时 `backtest_tool_schema()` 仍只包含 `run_dir/action/speed/use_cache/execution`。
- bridge skill 仍为 10 条，且明确配置 schema 与 MCP tool schema 的两步核对；生成的 HowToUse/README 无 drift。
- 运行 `agent/tests` 中的配置 schema、logical groups、MCP workflow/stdio 回归；对目标 Python 文件执行 `py_compile`，同步器 `--check` 和 `git diff --check` 通过。
- 若引入任何引擎或数据加载行为变化，视为范围越界，停止并回到计划重新确认；本计划预期不触发真实回测结果变更。

## 实际执行结果（V046）

- 配置模型：`BacktestConfigSchema` 已增加面向 Agent 的字段描述，正式声明 `backtest_start/end`，新增 `LogicalGroupConfigSchema` 结构，并保留 `extra="allow"` 与现有 `parse_logical_groups()` 跨字段校验。
- MCP 暴露：`backtest_config_schema()` 从 `BacktestConfigSchema.model_json_schema()` 读取字段、类型、默认值和描述，生成 MCP server instructions 的配置摘要；`backtest` 调用 schema 仍只有 `run_dir/action/speed/use_cache/execution`。
- 生成物：bridge skill 仍为 10 条工作流边界，并加入配置 schema / MCP tool schema 分步核对；HowToUse 第 12 节和 README 能力区块已同步，嵌套 `logical_groups` 元素结构可见。
- 验证：配置、逻辑分组、MCP workflow、冒烟和回归定向测试 `94 passed, 1 skipped`；stdio/runner 定向测试 `16 passed`；目标源码 `py_compile`、生成器 `--check`、`git diff --check` 通过。
- 范围核对：本次只修改配置 schema、MCP registry/说明生成、bridge skill、生成文档和测试；未修改 `backtest/engines`、`backtest/loaders`、成交/指标/缓存业务逻辑，因此未新增真实回测 run。
- 后续审计修正（V047）：清理 bridge skill 和 MCP/能力表中的重复配置语义；在核对 163 个现有 run config 均无越界后，补充数据加载窗口覆盖实际执行窗口的早失败校验，并按 date-only end 的整日语义处理盘中时间。

## 讨论记录

- 2026-08-27 用户提出：希望 Agent 通过查看 `BacktestConfigSchema` 就能知道如何配置回测参数和如何使用，而不是把部分配置说明散落在 skill、MCP schema 和 HowToUse 中。
- 2026-08-27 调研结论：当前 MCP `backtest` schema 只描述工具调用参数；`start_date/end_date` 已在配置模型中，`backtest_start/end` 尚未正式声明，`logical_groups` 由独立 parser 校验；需要先补齐配置契约，再把模型 schema 摘要暴露给 MCP Agent。
- 2026-08-27 设计结论：不把 config 字段加入 `backtest()` 顶层参数；`BacktestConfigSchema` 负责机器可读的配置契约，MCP instructions 负责自动暴露摘要，bridge skill 只保留“写 config 核对配置 schema、调用工具核对 MCP schema”的工作流提醒。
- 2026-08-27 用户要求：先写计划文档并查看，确认后再修改代码；实现完成时必须补写 `ITERATION_LOG`，本阶段不把未实施方案记为已完成迭代。
- 2026-08-27 用户确认：按本计划开始实施。

## 风险 / 注意

- `BacktestConfigSchema` 当前允许额外字段；若未来要做到所有引擎参数都严格可枚举，需要另做字段盘点和分引擎配置模型，不在本计划中隐式扩大范围。
- Pydantic 的嵌套模型只能表达结构，不能独立替代 `logical_groups` 对顶层 `codes`、重复成员和 `chart_code` 的跨字段校验。
- 把完整 schema 原文塞进 MCP instructions 可能增加 Agent 上下文噪声，因此默认生成紧凑摘要；如后续需要按需读取完整 schema，再单独评估 MCP resource，不新增回测工具。
- 字段描述属于 Agent 的配置依据，但实际执行仍以 runner 校验和引擎代码为准；任何文档与代码冲突都以代码为准。
