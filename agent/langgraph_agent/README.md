# LangGraph 量化 Agent 原型（P0-2）

> 这是一个**离线原型**：它不接入生产 AgentLoop，也不改 `api_server.py`。
> 目的：在真实的 vibe-trading 工具上，对比「线性 ReAct 循环」和「显式状态图」在多步量化任务上的差别。

## 它在做什么

现在的 `AgentLoop` 是一个 while 循环：模型看一眼提示词里的流程建议，自己决定调哪个工具、下一步干什么。计划、进度、校验、中断、恢复都不在代码里。

本包把同一件事画成一张状态图：

```
decode → plan → decompose → route → execute → validate → summarize
                                      ↘ human_review（回测前暂停）
```

- `plan` 让 LLM 输出 1-3 步计划和子任务；
- `decompose` 用代码校验/去重/排序子任务；
- `route`/`execute` 逐个执行；
- `validate` 用白名单和子任务完整性检查，不指望模型自觉；
- `human_review` 在昂贵动作（回测）前中断，等人批准；
- 每一步状态存入 checkpointer，可断点恢复。

## 快速开始

所有命令在 `agent/` 目录下执行（`pythonpath=agent` 已由 pytest 配置；命令行用 `-m` 时需要先进入 `agent/`）。

```powershell
cd E:\myProgram\vibe-trading-src\agent
$env:LANGCHAIN_PROVIDER="deepseek"; $env:LANGCHAIN_MODEL_NAME="deepseek-chat"

# 1) 语料结构校验（45 条：40 单意图 + 5 多意图）
..\.venv\Scripts\python.exe -m langgraph_agent.run_eval --check-data

# 2) 单条 LLM 提示词验证（打印 JSON / 子任务 / 耗时）
..\.venv\Scripts\python.exe -m langgraph_agent.run_eval --check-llm

# 3) 真实链路：取数 → 回测 → 报告
..\.venv\Scripts\python.exe -m langgraph_agent.live_demo --symbols 600519.SH,000001.SZ --start 2024-01-01 --end 2024-12-31 --source baostock

# 4) 45 条评测（stub 工具，秒级）
..\.venv\Scripts\python.exe -m langgraph_agent.run_eval --impl graph
..\.venv\Scripts\python.exe -m langgraph_agent.run_eval --impl linear
```

`run_eval` 的产物写到 `agent/langgraph_agent/runs/<impl>-<timestamp>/`（已 gitignore），包含 `results.jsonl` 与 `summary.json`。

生成对比报告：

```powershell
..\.venv\Scripts\python.exe -m langgraph_agent.evaluator `
  --graph runs\graph-xxx\summary.json `
  --linear runs\linear-xxx\summary.json `
  --out docs\compare.md
```

## 演示服务（人工接管）

```powershell
..\.venv\Scripts\python.exe -m langgraph_agent.server --port 9200
```

```powershell
# 触发回测前的人工门（requireHumanReview=true）
curl -s -X POST 127.0.0.1:9200/agent/decide -H "Content-Type: application/json" `
  -d "{\"question\":\"用 20 日均线回测 600519.SH 2024 年\",\"requireHumanReview\":true}"

# 用上一步返回的 threadId 批准
curl -s -X POST 127.0.0.1:9200/agent/resume -H "Content-Type: application/json" `
  -d "{\"threadId\":\"<上一步>\",\"approved\":true}"
```

- `POST /agent/decide`：`{question, sessionId?, requireHumanReview?, maxSteps?}`
- `POST /agent/resume`：`{threadId, approved, note?}`
- `GET /agent/state/{threadId}`：状态快照
- 服务只绑定 `127.0.0.1`，无鉴权，仅本地 demo。

### 跨进程断点恢复（可选）

```powershell
..\.venv\Scripts\python.exe -m pip install langgraph-checkpoint-sqlite
..\.venv\Scripts\python.exe -m langgraph_agent.server --sqlite C:\tmp\p02_checkpoints.sqlite
```

进程 1 触发中断并退出；进程 2 用同一个 sqlite 文件和 `threadId` 调 `/agent/resume` 即可继续。

## 评测协议

- **语料**：`eval/cases.jsonl`，45 条量化请求；40 条单意图（行情/回测/报告/追问/结束各 8 条）+ 5 条多意图。设计与标注规则见 `eval/README.md`。
- **工具**：评测默认 stub（`MarketDataAdapter` / `BacktestAdapter` / `ReportAdapter` 只返回结构化摘要），保证秒级、可重复、不花钱；`--live-tools` 才调用真实工具。
- **指标**：单意图动作集准确率、多意图动作集完全一致、多意图覆盖率、枚举外动作率、平均步数、平均 LLM 调用次数、平均 Token、P95 延迟。
- **元信息**：每次 run 的 `summary.json` 记录 model/provider/temperature/prompt hash/dataset hash/git commit/git dirty。
- **对照**：同一模型、同一工具集、同一协议文本；线性基线只执行第一个工具调用（所有动作都是终态），状态图可以拆多个子任务并校验/中断。

## 诚实边界

- 45 条是合成语料、单轮、单模型，**不能外推线上准确率**。
- 单意图准确率**不预期**状态图更高；状态图的证据点是多意图拆解、可中断、可恢复、可观测。
- 评测用 stub 工具，不等于真实回测；真实链路由 `live_demo.py` 单独证明。
- 生产 `AgentLoop` 没有改动；本包是离线原型，不是“已上线”。
- `opencode-go` 当前可能返回 `400 MissingSessionID`；默认用 DeepSeek 直连，报告必须记录实际 provider。
- `stockdb` 需要本机 7899 服务；默认用 `baostock`。

## 测试

```powershell
..\.venv\Scripts\python.exe -m pytest tests\test_langgraph_agent_state.py tests\test_langgraph_agent_graph.py -q
```

测试用 `ScriptedLLM`，不访问网络、不花 token。
