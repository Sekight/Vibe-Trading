# 计划：LangGraph 版量化 Agent（状态图 + 规划拆解 + 人工接管）

> 编号：P-20261025-P02_interview_langgraph_agent
> 状态：已完成
> 日期：2026-10-25
> 关联迭代：V051
> 关联：上游规格 `E:\interview\DOCS\计划\AI-Agent-P0P1改造计划与执行手册-20261021.md` §3.2（P0-2）；分支 `interview-1`；commit / run 收尾时补

## 0. 这份计划在做什么（给不看代码的读者）

### 0.1 一句话

把 vibe-trading 里“模型自己边想边做”的 Agent，改造成一张**看得见、停得住、能恢复、能校验**的流程图：先列计划，再按子任务执行，关键步骤停下来等人确认，失败能回到上一步，中途挂了能接着跑。

### 0.2 现在是怎么做的

打个比方：现在的 Agent 像一个能力很强、但把待办记在脑子里的员工。

- 你问它“拉茅台数据、跑回测、出报告”，它先看公司手册——手册里用自然语言写了做回测的推荐步骤（`agent/src/agent/context.py:70-79` 的 `## Task Routing`）。
- 然后它自己决定先调哪个工具、下一步干什么。代码里的 `AgentLoop`（`agent/src/agent/loop.py:624`）只负责把模型的话和工具结果来回搬运。
- 真正的工具在 `agent/src/tools/`（取行情、跑回测、写报告等），由 `ToolRegistry` 注册。

问题不是它做不了，而是：

1. **你看不到它的计划**：它打算走几步、现在走到哪，只能从日志里猜。
2. **它可能漏步或重复**：比如忘了“出报告”，或者把回测跑了两遍。
3. **昂贵动作停不下来**：回测要跑几分钟、还会写产物，你想先确认参数，代码层没有地方能暂停。
4. **失败只能重来**：跑到一半模型或工具出错，没有断点可恢复。
5. **流程靠自觉**：提示词里写了“应该先做什么”，但代码不检查它是否真的照做。

### 0.3 改完之后

同一名员工，面前多了一块看板：有列（步骤）、有卡（子任务）、有审批门（回测前必须你点头）、有存档点（每步自动保存）。

具体流程：

1. 收到问题，先产出一个 1-3 步的计划；
2. 把多意图拆成子任务（“拉数据 + 跑回测 + 出报告”是三个）；
3. 逐个执行，每步记录用了哪个工具、结果是什么；
4. 遇到回测这种昂贵动作，暂停，等人批准后再继续；
5. 全部做完后校验：子任务有没有漏、动作合不合法；
6. 任何一步失败，回到计划修一次；修不好就降级为“只回文本”，不硬闯；
7. 每一步状态都存下来，进程挂了能从断点接着跑。

对应到代码，就是 `agent/langgraph_agent/` 里的一张状态图：

```
用户请求
  → decode（清洗输入）
  → plan（LLM 输出 1-3 步计划 + 子任务）
  → decompose（校验、去重、排序子任务）
  → route（选下一个子任务）
  → execute（调真实工具，只记录不重复执行）
  → validate（动作白名单 + 子任务完整性）
  → summarize（汇总动作与文本）
        ↘ human_review（昂贵动作前中断，等人批准）
```

### 0.4 为什么值得做

**项目层面**：量化研究天然是多步、长耗时、有产物的流程（取数 → 回测 → 读指标 → 写分析）。这类流程需要四样东西，而现在的 while 循环给不了：

- **可观测**：现在只能看“模型又调了什么工具”，看不到“计划走到第几步、哪步失败”。
- **可中断**：回测这种昂贵动作，应该在执行前停下来让人确认。
- **可恢复**：跑了一半失败，不应该从头再来。
- **可校验**：子任务有没有漏、动作合不合法，应该由代码检查，而不是指望模型遵守提示词。

**面试层面**：目标岗位的 JD 常问 LangGraph、规划/拆解、人机协同。项目里已经有自研 ReAct 循环，正好做“同工具、同模型、同数据”的对照，证明状态图多换来了什么、多付出了什么（多一次规划调用、更多代码复杂度）。这不是为了 JD 硬造功能——上面的工程需求先成立，面试证据是副产品。

### 0.5 不做什么

- 不改模型的“理解能力”，不换 LLM，不改提示词的语义理解部分。
- 不改回测引擎、数据加载器、现有工具实现。
- 不改生产 `AgentLoop`、`api_server.py`、`cli`；P0-2 是 `agent/langgraph_agent/` 下的离线原型。
- 不做 UI、鉴权、多智能体、长期记忆、RAG。
- 不声称“状态图准确率更高”；单意图任务预期接近，价值点在多意图拆解、可中断、可恢复、可观测。

## 1. 前因后果

### 1.1 为什么会有这份计划

- **P0-1** 做的是 ai-job（Java 求职 Agent）的评测闭环：40 条单步动作语料、服务端回放、held-out、事实断言、对抗样本。它证明的是“单步决策 Agent 的动作准确率”。
- **P0-2** 要做的是“多步 Agent 的流程控制”。上游手册明确把落点定在 vibe-trading（Python，已有自研 ReAct AgentLoop），理由是复用度最高：同一套工具、同一个模型，可以直接做“线性循环 vs 状态图”的对照。
- 两个项目定位不同：**ai-job 是单步、不可逆动作（发简历/挽留）**；**vibe-trading 是多步、可分析的研究流程（取数/回测/报告）**。所以 P0-2 必须用 vibe-trading 自己的业务语料，不能把 ai-job 的 HR 语料搬过来。

### 1.2 第一稿的错误与纠正（必须记住）

第一稿计划把 ai-job 的 40 条 HR 语料（“简历/岗位/SEND_RESUME”）直接当成 P0-2 的评测集，理由是“它有现成标注”。这是错误的：

- **领域错位**：量化项目里的 Agent 处理“HR 要简历”，面试官第一句就会问“这跟你的项目有什么关系”，答“只是夹具”很弱。
- **无法复用**：这套动作/工具/语料在 vibe-trading 里没有业务价值，做完只能当 demo。
- **违反设计三问的第一问**：“业务上真的需要吗？”——不需要。

本版已彻底删除 HR 语料，改为量化原生的任务与工具（见 §4）。第一稿保留在 git 历史里，不删档，但不再作为执行依据。

## 2. 项目调研（2026-10-25，实测 / 源码）

> 结论均来自本机实测或源码；标注「待验证」的才是推断。

### 2.1 现有 Agent 架构（代码事实）

| 层 | 位置 | 现状 |
|---|---|---|
| 循环层 | `agent/src/agent/loop.py:502`（`AgentLoop`）、`:624`（`run()`） | while 循环：LLM → tool_calls → 执行工具 → 回灌结果 → 再问，直到无工具调用或达到 `max_iterations` |
| 提示词层 | `agent/src/agent/context.py:22`（系统提示词）、`:70-79`（`## Task Routing`） | 做回测的推荐步骤写在**自然语言**里，代码不强制 |
| 工具层 | `agent/src/agent/tools.py:13`（`BaseTool`）、`:54`（`ToolRegistry`）；`agent/src/tools/*` | 工具自动发现与注册；真实工具包括 `get_market_data`、`backtest`、`write_run_analysis` 等 |
| 可观测 | `agent/src/agent/trace.py:64`（`TraceWriter`） | JSONL + fsync + 大字段 sidecar，可复用 |
| 状态 | `agent/src/agent/memory.py:14`（`WorkspaceMemory`） | 仅单次 run 的 `run_dir` + 计数器；**没有跨轮持久状态** |
| 中断/恢复 | 全仓库 `grep resume/checkpoint/interrupt`（agent 层） | 零命中；只有取消（cancel）的协作检查点，没有断点恢复 |

**结论**：现在能做多步任务，但“计划/进度/校验/中断/恢复”都不在代码里，靠模型自觉。P0-2 要补的正是这一层。

### 2.2 LangGraph 环境（实测）

- `pyproject.toml:30-31` 已声明 `langgraph>=1.2.5,<1.3`、`langgraph-checkpoint>=2.1.0,<5`；venv 实测 `langgraph 1.2.10`、`langgraph-checkpoint 4.1.1`。
- 全仓库代码 `grep "from langgraph|import langgraph"` **0 命中**（排除 .venv）→ P0-2 是新增，不是“已有”。
- 最小脚本实测（2026-10-25）：
  - `StateGraph + MemorySaver + compile(interrupt_before=[...])`：停在断点，`invoke(None, cfg)` 可继续。
  - 动态 `interrupt({...}) + Command(resume={...})`：首次返回 `__interrupt__`，resume 后继续跑完。
  - `langgraph.checkpoint.sqlite` **未安装**（`ModuleNotFoundError`）→ `SqliteSaver` 走 optional extra。

### 2.3 量化原生工具（代码事实）

| 子任务类型 | 真实工具 | 位置 | 说明 |
|---|---|---|---|
| `market_data` | `get_market_data` | `agent/src/tools/market_data_tool.py:14` | OHLCV，支持 stockdb/baostock/akshare/tencent 等 |
| `backtest` | `backtest` | `agent/src/tools/backtest_tool.py:310` | 输入 run_dir（config.json + code/signal_engine.py），默认 fastrun |
| `report` | `write_run_analysis` | `agent/src/tools/write_run_analysis_tool.py:20` | 对已完成 run 生成 `analysis.md` |
| `clarify` | 图内动作（无外部工具） | 新增 | 信息不足时先追问，不猜 |
| `stop` | 图内动作（无外部工具） | 新增 | 无关/结束 |

工具注册用 `build_registry()`（`agent/src/tools/__init__.py:66`）自动发现；P0-2 为了控制提示词体积，只注册上述 3 个真实工具的**薄适配器** + 2 个图内动作。

### 2.4 数据源与 LLM 可行性（实测，2026-10-25）

**LLM**：

- `~/.vibe-trading/.env` 配置为 `opencode-go / deepseek-v4-flash`；直接调用当前返回 `400 MissingSessionID`（网关要求 `x-opencode-session` 头，项目配置未带）。
- 改用 DeepSeek 直连（`LANGCHAIN_PROVIDER=deepseek`、`LANGCHAIN_MODEL_NAME=deepseek-chat`，复用 `.env` 里的 `DEEPSEEK_API_KEY`/`DEEPSEEK_BASE_URL`）实测成功：1 次规划调用 1.59 秒，返回合法 JSON，3 个子任务（`market_data / backtest / report`），confidence 0.85。
- 结论：评测/演示默认走 DeepSeek 直连；`opencode-go` 作为可选 provider，启动前先做连通性预检，失败则回退并记录 `provider_used`。

**数据源**：

- `stockdb` 服务当前未运行（7899 端口无监听）；`local` data-bridge 指向的 parquet 文件不存在。
- `baostock` 与 `tencent` 实测可取 A 股日线（600519.SH 2024-01 返回 22 根）。
- 结论：冒烟回测与现场演示用 `source="baostock"`；stockdb 作为可选（启动服务后可用）。

**真实小回测**（验证“能跑”）：

- 配置：`source=baostock`、`600519.SH + 000001.SZ`、2024 全年日线、20 日动量等权。
- 命令：`python -m backtest.runner <run_dir> --fastrun`
- 实测：**7.3 秒**完成，`trade_count=30`，产出 `metrics.csv` / `run_card.json` / `analysis.digest.json`。
- 结论：一次真实回测成本约 7 秒，足够放进现场演示；评测主表仍用 stub 工具，避免 45 × 2 次真跑。

### 2.5 回归基线（实测）

- 目标回归子集：`test_agent_loop_*.py`（8 个文件）+ `test_backtest_workflow.py`，共 **50 个测试**。
- 实测：**47 通过 / 3 失败，14 秒**。3 个失败都是 `status == "warning"` 而不是 `"success"`，根因是测试环境的 `_SecretRegistry` 没有 `tool_names`，导致 `run_manifest` 写失败（`loop.py:622` 日志可见）；与 P0-2 无关，是**既有失败**。
- 失败清单（作为回归基线，不修）：
  - `test_agent_loop_dsml_tool_calls.py::test_agent_loop_executes_dsml_textual_tool_call`
  - `test_agent_loop_no_assistant_prefill.py::test_background_notifications_are_reintroduced_as_user_messages`
  - `test_agent_loop_trace.py::test_session_trace_uses_session_dir_and_round_trips_long_answer`
- 回归判定：**失败集合不新增**（不是要求全绿）；P0-2 只新增文件，生产代码零改动。

## 3. 需求目标

- **做什么**：
  1. 在 `agent/langgraph_agent/` 实现量化原生状态图 Agent：8 节点 + 3 条条件边 + 动态 `interrupt()` 人工接管 + `MemorySaver`/`SqliteSaver`。
  2. 提供同条件线性 ReAct 基线，跑同一批 45 条量化请求（40 单意图 + 5 多意图），产出 `compare.md`。
  3. 提供最小 FastAPI demo（`POST /agent/decide`、`POST /agent/resume`、`GET /agent/state/{thread_id}`），独立端口 9200。
  4. 提供 1 条真实端到端演示：真取数 → 真回测 → 真报告（复用现有 `backtest` 工具与 runner）。
- **范围 / 边界**：
  - 只新增 `agent/langgraph_agent/**`、`agent/tests/test_langgraph_agent_*.py`、本计划与计划索引；`pyproject.toml` 只加 optional extra。
  - 不改 `agent/src/agent/`、`agent/api_server.py`、`agent/cli/`、`agent/src/tools/`、`agent/backtest/`；不碰 ai-job。
  - 评测语料全部是量化请求；**不含任何 HR/简历/岗位内容**。
  - 不把 HR 语料、ai-job 数据、外部仓库数字带入本计划。
- **验收标准（一句话）**：三条验证命令全部可复现（LLM 提示词、真实小回测、回归对照），45 条评测产出可核对指标，`interrupt → resume` 能现场演示，生产代码 `git diff` 为零。

## 4. 实现方案

### 4.1 目录结构（全部新增）

```
agent/langgraph_agent/
├── __init__.py
├── state.py            # AgentState + 子任务/动作枚举 + 初始状态
├── prompts.py          # 量化协议 + 规划 JSON 契约 + 线性工具契约
├── tools.py            # 量化工具适配器（stub/live）+ clarify/stop
├── nodes.py            # 9 个节点函数（含 human_review / fallback）
├── graph.py            # build_graph + 条件边 + decide/resume 封装
├── baseline.py         # 线性 ReAct 最小回路（同工具/同协议/同模型）
├── evaluator.py        # 语料加载、动作集评分、指标汇总、Markdown 渲染
├── run_eval.py         # CLI：--impl graph|linear --limit --mock --sqlite --check-data
├── server.py           # 独立 FastAPI demo（127.0.0.1:9200）
├── live_demo.py        # 真实端到端：取数 → 回测 → 报告（复用现有工具）
├── README.md           # 启动命令 / 演示脚本 / 诚实边界
├── docs/
│   └── compare.md      # 最终对比报告（由脚本生成表格 + 人工解读）
└── eval/
    ├── cases.jsonl     # 40 条单意图 + 5 条多意图（量化原生）
    └── README.md       # 语料设计规则、标注口径、修订记录
```

`agent/langgraph_agent/runs/` 放 trace 与逐样本结果，加入 `.gitignore`；只提交 `docs/compare.md` 与 `summary.json`。

### 4.2 State schema（`state.py`）

```python
class AgentState(TypedDict, total=False):
    # 输入
    question: str
    session_id: str
    profile: dict                 # 可选：默认标的池/日期范围等偏好
    require_human_review: bool
    # 规划
    plan: list[str]
    subtasks: list[dict]          # {id, type, reason, params, status}
    confidence: float
    plan_source: str              # llm | llm_repair | rule
    # 执行
    cursor: int
    current_step: int
    max_steps: int
    current_subtask: dict
    completed: list[dict]         # {subtask_id, action, params, status}
    reviewed: list[str]           # 已人工确认的子任务 id
    errors: list[dict]
    # 结果
    final_actions: list[str]      # MARKET_DATA / BACKTEST / REPORT / CLARIFY / STOP
    final_text: str
    stopped_reason: str           # done | max_steps | validation_failed | llm_fallback
    trace: Annotated[list[dict], operator.add]
```

约定：`trace` 用 `operator.add` 追加；其余字段整值替换；每个节点只写自己负责的字段。

### 4.3 节点职责与边

| 节点 | 类型 | 职责 | 写字段 |
|---|---|---|---|
| `decode` | 确定性 | 去控制字符、折叠空白；>2000 字符截断并记录；保留原始长度 | `question`, `errors`, `trace` |
| `plan` | LLM（唯一规划调用） | 输出 JSON：`{plan, subtasks:[{type,reason,params}], confidence}`；`type ∈ {market_data,backtest,report,clarify,stop}`；失败时 repair 一次，再失败走规则兜底 | `plan`, `subtasks`, `confidence`, `plan_source`, `trace` |
| `decompose` | 确定性 | 校验/去重/排序子任务，最多 3 个；空则补 1 个 `clarify` | `subtasks`, `cursor`, `trace` |
| `route` | 确定性 | 取 `subtasks[cursor]` 写入 `current_subtask`；由条件边决定 `validate` / `human_review` / `execute` | `current_subtask`, `trace` |
| `human_review` | 中断 | 仅当 `type=backtest` 且（`confidence < 0.7` 或 `require_human_review`）进入；`interrupt({question, action, params, confidence})`；拒绝 → 降级 `clarify` | `subtasks`, `reviewed`, `trace` |
| `execute` | 工具调用（只记录） | 调 `ToolRegistry.execute()`；不重复执行；记录动作与参数 | `completed`, `subtasks`, `cursor`, `current_step`, `trace` |
| `validate` | 确定性 | 动作 ∈ 枚举；非 `max_steps` 时子任务必须全部完成；失败 → `repair` 一次 → 仍失败 → `fallback` | `errors`, `validation_failed`, `repair_attempted`, `trace` |
| `fallback` | 确定性 | 清空动作，只保留 `CLARIFY` 文本，`stopped_reason=validation_failed` | `final_actions`, `final_text`, `stopped_reason`, `trace` |
| `summarize` | 确定性模板 | 汇总 `final_actions` / `final_text`；多意图按子任务顺序拼接 | `final_actions`, `final_text`, `stopped_reason`, `trace` |

**条件边**：

1. `route` 后：无当前子任务 → `validate`；`backtest` 且未人工确认且低置信度/强制审核 → `human_review`；否则 → `execute`。
2. `execute` 后：`cursor < len(subtasks)` → `route`（循环）；否则 → `validate`。
3. `validate` 后：通过 → `summarize`；失败且未 repair → `plan`（带 errors 重规划）；失败且已 repair → `fallback`。

### 4.4 量化工具适配器（`tools.py`）

| 适配器 | 对应真实工具 | stub 模式 | live 模式 |
|---|---|---|---|
| `MarketDataAdapter` | `get_market_data` | 返回固定 OHLCV 摘要（不联网） | 调真实工具取数 |
| `BacktestAdapter` | `backtest` | 返回固定 metrics 摘要 | 复制模板 run_dir → 写 config → 调 runner |
| `ReportAdapter` | `write_run_analysis` | 返回固定 `analysis.md` 摘要 | 调真实工具生成报告 |
| `ClarifyAction` | 无 | 返回追问文本 | 同左 |
| `StopAction` | 无 | 返回结束标记 | 同左 |

- 所有适配器继承现有 `BaseTool`，注册进现有 `ToolRegistry`；`execute` 返回 JSON 字符串。
- **stub 模式**用于 45 条评测与单测，保证秒级、可重复、不花钱；**live 模式**只用于 1 条端到端演示与人工验收。
- `BacktestAdapter` 的 live 路径复用 §2.4 实测过的配置：`source=baostock`、2 只标的、1 年日线、20 日动量；run_dir 复制模板，避免污染用户已有 run。

### 4.5 线性基线（`baseline.py`）

- 结构 = `AgentLoop.run()` 的核心循环（`agent/src/agent/loop.py:624` 起）：`messages=[system,user]` → `llm.chat(tools=...)` → 有 tool_call 就执行**第一个**并结束（所有动作都是终态）→ 无 tool_call 取文本。
- **为什么不用生产 AgentLoop 直接跑**：其系统提示词是金融研究域（`context.py:22`），与“量化请求→动作”的评测协议不同条件；基线因此是“同构最小回路”，在 README/报告里写明差异。
- 同一 `ChatLLM`、同一工具集、同一协议文本、同一 45 条语料；唯一结构差异是“线性只落一个动作，状态图可拆多个子任务并校验/中断”。

### 4.6 评测语料（40 单意图 + 5 多意图，量化原生）

**5 类单意图，每类 8 条**：

| 类型 | 示例 | 期望动作 |
|---|---|---|
| `market_data` | “拉一下 600519.SH 2024 年的日线” | `MARKET_DATA` |
| `backtest` | “用 20 日均线策略回测 600519.SH 2024 年” | `BACKTEST` |
| `report` | “给刚才那次回测写一份报告” | `REPORT` |
| `clarify` | “帮我跑个回测”（缺标的/区间/策略） | `CLARIFY` |
| `stop` | “谢谢，先这样” | `STOP` |

**5 条多意图**（每条 2-3 个显式意图）：

| id | 请求 | 期望动作集 |
|---|---|---|
| m001 | 拉 600519.SH 2024 日线，然后跑 20 日均线回测 | `[MARKET_DATA, BACKTEST]` |
| m002 | 跑 000001.SZ 2024 双均线回测，再给一份报告 | `[BACKTEST, REPORT]` |
| m003 | 先看 300750.SZ 近一年行情，再跑动量回测并出报告 | `[MARKET_DATA, BACKTEST, REPORT]` |
| m004 | 用 510300.SH 做 2023 年回测；另外把 2024 年日线也拉一下 | `[BACKTEST, MARKET_DATA]` |
| m005 | 拉 600519.SH 2024 日线，跑回测，再解释最大回撤 | `[MARKET_DATA, BACKTEST, REPORT]` |

**语料规则**：

- 全部是量化请求，不含 HR/简历/岗位；每条标注 `expect.actions`、`tags`、`source: synthetic`、`reviewed: true`、`notes`。
- `clarify` 的判定：缺标的、缺区间、或缺策略三者之一；不允许模型猜默认值。
- `stop` 的判定：致谢/结束语/与投研无关的闲聊；不允许触发任何工具。
- 多意图按**动作集合完全一致**计 pass，另报 `multi_action_recall`（覆盖了期望动作的比例）。

### 4.7 指标与报告

| 指标 | 定义 | 分母 |
|---|---|---|
| `single_action_accuracy` | 实际动作集 == 期望动作集 | 40 |
| `multi_action_exact_match` | 多意图动作集完全一致 | 5 |
| `multi_action_recall` | 期望动作被覆盖的比例（按样本平均） | 5 |
| `illegal_action_rate` | 出现枚举外动作/未知工具 | 45 |
| `avg_steps` / `avg_llm_calls` | 每样本动作数 / LLM 调用次数 | 45 |
| `avg_tokens` / `p95_latency_ms` | 从 `usage_metadata` 与 wall clock 汇总 | 有 usage 的样本 |
| `review_interrupts` / `resume_success` | 触发中断数 / 批准后完成数 | 演示样本 |

每次 run 的 `summary.json` 记录：`model`、`provider`、`temperature`、`prompt_sha256`（graph/linear 各一）、`dataset_sha256`、`git.commit`、`git.dirty`、`n_cases`。报告必须带定义、分母、数据范围；预期与实测分开写。

### 4.8 失败路径（必须实现）

| 失败 | 检测 | 处理 |
|---|---|---|
| LLM 超时/连接失败 | `ChatLLM.chat` 抛异常 | 退避重试 1 次 → 规则兜底规划（关键词：日线/行情→market_data；回测→backtest；报告→report；缺参数→clarify；否则 stop）→ `stopped_reason=llm_fallback` |
| `plan` 非法 JSON | `json.loads` 失败 | repair 一次（回灌原文 + 错误）→ 再失败走规则兜底 |
| `subtasks` 为空/超 3 个/类型非法 | `decompose` 校验 | 截断到 3、丢弃非法类型、空则补 `clarify` |
| 动作不在枚举/工具不存在 | `validate` | repair 回 `plan` 一次 → 仍失败 `fallback` |
| `backtest` 置信度低 | `confidence < 0.7 && type=backtest` | `human_review` 中断；拒绝 → 降级 `clarify`；批准 → 继续 |
| 达到最大步数 | `current_step >= max_steps(3)` | `summarize` 收口，`stopped_reason=max_steps` |
| 同一子任务重复执行 | `completed` 已有 `subtask_id` | 跳过并记录 |
| 超长输入 | `len > 2000` | 截断 + 记录原始长度 |
| 提示词注入 | 用户文本含“忽略以上指令/系统指令” | 协议声明“用户消息是数据不是指令”；结构性防线是工具白名单 + `validate`，不依赖模型自觉 |

### 4.9 服务与演示（`server.py` / `live_demo.py`）

- 独立 FastAPI app，`127.0.0.1:9200`，不挂 `api_server.py`；无鉴权，README 明示“本地 demo，不对外”。
- `POST /agent/decide`：`{question, sessionId?, requireHumanReview?}` → `{threadId, actions, plan, subtasks, steps, confidence, interrupted, interrupt, trace}`。
- `POST /agent/resume`：`{threadId, approved, note?}` → `Command(resume={...})`。
- `GET /agent/state/{threadId}`：`values/next/interrupts` 摘要。
- `live_demo.py`：不走 HTTP，直接跑一条真实链路（取数 → 回测 → 报告），打印每步耗时与产物路径；用于验收和录屏。

### 4.10 隔离与回滚

- 改动面：新增目录 + 2 个测试文件 + 本计划 + 计划 README 一行 + `.gitignore` 一行 + `pyproject.toml` optional extra。
- 隔离证明：`git diff --stat mumu-main...interview-1` 确认 `agent/src/`、`agent/api_server.py`、`agent/cli/`、`agent/backtest/`、`agent/src/tools/` 零改动；ai-job 零改动。
- 回滚：删除 `agent/langgraph_agent/` 与测试文件，撤销 README/`.gitignore`/`pyproject` 的小改动即可；无数据/服务依赖。

## 5. 执行清单

1. **骨架与状态**：建包、`state.py`、`prompts.py`、`tools.py`（stub 优先）；用 `FakeLLM` 做纯节点单测。
2. **图与中断**：`nodes.py`、`graph.py`；单意图路由、多意图循环、非法 JSON repair、max_steps、`interrupt/resume`、thread 隔离。
3. **线性基线**：`baseline.py`；同工具/同协议/同模型；验证“只执行第一个动作”的结构限制。
4. **语料**：生成 `eval/cases.jsonl`（40 + 5），脚本校验 id 唯一、动作 ∈ 枚举、无 HR 词表残留。
5. **评测**：`evaluator.py`、`run_eval.py`；先 `--mock --limit 5`，再真跑 5 条，最后全量 45 × 2。
6. **真实链路**：`live_demo.py`；真取数（baostock）→ 真回测（7 秒级）→ 真报告；记录耗时与产物。
7. **服务**：`server.py`；curl 三连（decide → interrupted → resume）。
8. **持久化**：安装 `langgraph-checkpoint-sqlite`，`--sqlite` 跨进程恢复演示。
9. **回归**：跑 §7(c) 的目标子集，对比失败集合；跑新文件 ruff/pytest。
10. **收尾**：README、`compare.md`；更新计划状态与关联迭代、ITERATION_LOG、计划 README 索引。

## 6. 开工前核对

| 检查项 | 结果 | 发现项 |
|---|---|---|
| 需求目标 / 范围与讨论记录一致 | 通过 | 已删除 HR 语料，改为量化原生；范围限定新增目录 |
| 范围/边界无被后续讨论反转但仍保留的旧约束 | 通过 | 第一稿 HR 语料已明确作废；本版无残留 |
| 执行清单覆盖需求目标与验收标准 | 通过 | R1-R5 均有对应步骤；新增 (a)(b)(c) 三条验证 |
| 验收标准可验证 | 通过 | 三条验证命令已实测；回归基线失败集合已记录 |
| 元信息已填（关联允许为待填） | 通过 | 编号/状态/日期/上游规格已填；V 号与 commit 待填 |

**可行性核对结论（2026-10-25 实测）**：

- (a) LLM 提示词：DeepSeek 直连 1.59 秒返回合法 JSON（3 子任务）；opencode-go 当前 400，需回退。
- (b) 真实小回测：baostock 2 标的 1 年日线，7.3 秒完成，30 笔交易，产物齐全。
- (c) 回归：目标子集 47/50 通过，3 个失败为既有问题（`status=warning`），与 P0-2 无关。
- 结论：**可以执行**；无阻塞项。

## 7. 验证

### 7.1 (a) LLM 提示词验证

```powershell
cd E:\myProgram\vibe-trading-src\agent
$env:LANGCHAIN_PROVIDER="deepseek"; $env:LANGCHAIN_MODEL_NAME="deepseek-chat"
..\.venv\Scripts\python.exe -m langgraph_agent.run_eval --check-llm --limit 1
```

预期：输出合法 JSON、子任务类型在枚举内、耗时与 token 打印。实测基线 1.59 秒 / 316 tokens。

### 7.2 (b) 真实小回测验证

```powershell
cd E:\myProgram\vibe-trading-src\agent
..\.venv\Scripts\python.exe -m langgraph_agent.live_demo --symbols 600519.SH,000001.SZ --start 2024-01-01 --end 2024-12-31 --source baostock
```

预期：取数 → 回测 → 报告三步全部完成；回测约 7 秒；产物路径打印；失败时给出可读原因。

### 7.3 (c) 回归验证（不影响线上）

```powershell
# 1) 生产代码零改动
git diff --stat mumu-main...interview-1

# 2) 目标回归子集（基线：47/50，3 个既有失败）
.venv\Scripts\python.exe -m pytest agent/tests/test_agent_loop_content_filter.py agent/tests/test_agent_loop_dsml_tool_calls.py agent/tests/test_agent_loop_no_assistant_prefill.py agent/tests/test_agent_loop_repeatable_tools.py agent/tests/test_agent_loop_stream_retry.py agent/tests/test_agent_loop_terminal_state.py agent/tests/test_agent_loop_thought_signature.py agent/tests/test_agent_loop_trace.py agent/tests/test_backtest_workflow.py -q

# 3) 新增代码自身的测试与静态检查
.venv\Scripts\python.exe -m pytest agent/tests/test_langgraph_agent_state.py agent/tests/test_langgraph_agent_graph.py -q
.venv\Scripts\python.exe -m ruff check agent/langgraph_agent agent/tests/test_langgraph_agent_state.py agent/tests/test_langgraph_agent_graph.py
```

判定：生产代码 diff 为空；回归失败集合与基线一致（仍为那 3 个）；新增测试全绿；ruff 无错误。

## 8. 待拍板

本轮用户已拍板 4 项（SqliteSaver optional extra、动作集完全一致口径、量化原生语料、独立 9200 demo server）。新增 2 个默认值，按推荐执行：

1. **LLM provider**：推荐 DeepSeek 直连跑评测/演示（当前可用）；`opencode-go` 作为可选，启动前预检，失败自动回退并记录。
2. **真实回测数据源**：推荐 `baostock`（当前可用、离线零配置）；stockdb 作为可选（需启动 7899 服务）。

## 9. 讨论记录

- **2026-10-25 用户指令**：按上游 P0-2 设计做开发，先写计划；新开分支 `interview-1`；不必过度设计，只为面试服务；面试标准参考 `E:\myProgram\AgentGuide` 与 `E:\myProgram\ai-agent-interview-guide`。
- **2026-10-25 第一稿**：落点 `agent/langgraph_agent/`，8 节点 + 条件边 + interrupt/checkpoint；但评测语料误用了 ai-job 的 40 条 HR 数据。
- **2026-10-25 用户质疑**：“量化项目里为什么会有简历/岗位/SEND_RESUME？”——确认领域错位，第一稿语料作废。
- **2026-10-25 修正（本版）**：评测语料改为量化原生（40 单意图 + 5 多意图）；工具改为 `get_market_data` / `backtest` / `write_run_analysis` 的薄适配器；新增三条验证（LLM 提示词、真实小回测、回归）。
- **2026-10-25 用户拍板**：4 项推荐全部采纳；计划编号改为 `P-20261025-P02_interview_langgraph_agent`。
- **2026-10-25 可行性核对**：LLM 1.59s 合法 JSON；回测 7.3s/30 笔；回归 47/50（3 个既有失败）。结论：可执行。
- **范围变更**：原=HR 语料 + 4 个 HR 动作工具 → 现=量化原生语料 + 3 个真实工具适配器 + 2 个图内动作。
- **2026-10-25 用户确认**：开始执行。按 §5 清单实现，先跑 (a)(b)(c) 三项验证，再收尾。

## 10. 风险 / 注意

- **不要宣称 ai-job 已用 LangGraph**：ai-job 仍是单步固定工作流；P0-2 是 vibe-trading 下的离线原型。
- **不要宣称“状态图准确率更高”**：单意图预期接近；如果 graph 更低，如实写（多一次规划调用可能引入额外错误）。价值点只在多意图、可中断、可恢复、可观测。
- **provider 漂移**：`opencode-go` 当前不可用（`MissingSessionID`）；评测必须记录 `provider_used`，跨 provider 不混算。
- **数据源漂移**：stockdb 未运行、local parquet 缺失；默认 baostock，报告记 `source` 与取数区间。
- **成本**：45 × 2 ≈ 90 次决策，graph 每样本多 1 次规划调用；先 `--mock`/`--limit` 再全量。
- **评测集小型化**：45 条、合成句、单轮；所有结论带“45 条自建集”限定，不外推线上准确率。
- **回归基线非全绿**：3 个既有失败必须作为基线记录，判定标准是“不新增失败”，不是“全绿”；收尾报告要写明。
- **Windows 路径**：命令统一用 venv 绝对路径 + 前斜杠；`PYTHONPATH` 指向 `agent` 目录；不用反斜杠拼接（E009）。
- **run artifacts 不入库**：`agent/langgraph_agent/runs/` 必须先加 `.gitignore`，只提交 `docs/compare.md` 与 `summary.json`。

## 11. 收尾记录（2026-10-25）

- 状态：已完成；关联迭代 V051。
- 交付物：
  - 代码：`agent/langgraph_agent/`（state/prompts/tools/nodes/graph/baseline/evaluator/run_eval/server/live_demo）。
  - 语料：`agent/langgraph_agent/eval/cases.jsonl`（45 条：40 单意图 + 5 多意图）。
  - 报告：`agent/langgraph_agent/docs/compare.md`；run 产物在 `agent/langgraph_agent/runs/`（gitignore）。
  - 测试：`agent/tests/test_langgraph_agent_state.py`、`agent/tests/test_langgraph_agent_graph.py`。
- 验证结果：
  - 单测：14 passed（无网络、无真实 LLM）。
  - (a) LLM 提示词：DeepSeek 直连 1.45s，返回合法 JSON，3 个子任务；`opencode-go` 当前 400 MissingSessionID，已回退并记录 provider。
  - (b) 真实链路：market_data 2.93s → backtest 8.29s（30 笔，run `p02_langgraph_bt_1792921417981`）→ report 20.6s（`analysis.md` 落盘）。
  - (c) 全量 45×2（deepseek-chat，temperature 0）：graph single 0.975 / multi exact 1.000 / recall 1.000 / steps 1.156 / 679.8 tok / P95 1458.21ms；linear single 0.950 / multi exact 0.000 / recall 0.433 / steps 0.978 / 1233.2 tok / P95 1202.2ms。
  - 人工接管：demo server `decide` 触发 interrupt（action=BACKTEST，confidence=0.95，requireHumanReview=true）；`resume` 批准后 actions=[BACKTEST]，`state.next=[]`；SqliteSaver 跨进程 resume 成功。
  - 回归：目标子集 47 passed / 3 既有失败（`test_agent_loop_dsml_tool_calls`、`test_agent_loop_no_assistant_prefill`、`test_agent_loop_trace`，均为 `_SecretRegistry` 缺 `tool_names` 导致 status=warning），失败集合与改动前一致；新增代码 ruff 通过。
  - 隔离：`git diff --name-only -- agent/src agent/api_server.py agent/cli agent/backtest agent/src/tools` 为空；生产代码零改动。
- 诚实边界：45 条合成语料、单轮、单模型，不能外推线上准确率；单意图准确率的差距（95%→97.5%）是 4 条样本的小样本差异，不作为“状态图更准”的证据；状态图的证据点是多意图动作集（0%→100%）、可中断/可恢复、节点级 trace。评测用 stub 工具，真实回测仅 1 条链路验证。
