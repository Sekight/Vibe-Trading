# Vibe-Trading 本地使用手册（HowToUse）

> 适用环境：Windows 11 + Python 3.13 + 源码目录 `E:\gitCloneProgram\vibe-trading-src`
> 当前版本：vibe-trading-ai 0.1.13（editable 源码安装）
> 官方参考：`README.md` / `README_zh.md` / `wiki/` / `vibe-trading --help`

---

## 1. 两个重要概念：短命令 vs 完整路径

- 激活 venv 后，`vibe-trading` 短命令会由 PATH 自动解析到：
  `E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\vibe-trading.exe`
- 所以 `vibe-trading ...` 和 `vibe-trading.exe ...` 是**同一个程序**，不是两个版本。
- 没激活时，PowerShell/cmd 找不到短命令，只能用完整路径：
  ```powershell
  E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\vibe-trading.exe --version
  ```
- 完整路径后面接什么参数，就有什么功能（`init` / `run` / `list` / `--show` / `serve` 都在）。

---

## 2. 激活环境

### 2.1 PowerShell（推荐）

```powershell
cd E:\gitCloneProgram\vibe-trading-src
.\.venv\Scripts\Activate.ps1
```

如果报错“禁止运行脚本”，先放开当前窗口：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

`-Scope Process` 只对当前窗口生效，关掉即失效，最安全。
若想永久放开（只影响当前用户）：

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 2.2 cmd

```cmd
cd /d E:\gitCloneProgram\vibe-trading-src
.\.venv\Scripts\activate.bat
```

### 2.3 不激活

直接用完整路径，不用设置执行策略：

```powershell
E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\vibe-trading.exe --version
```

### 2.4 验证

```powershell
vibe-trading --version
# 输出：vibe-trading 0.1.13
```

---

## 3. cmd / PowerShell / 终端 的区别

- `cmd`：Windows 老式命令行解释器。
- `PowerShell`：Windows 新一代命令行解释器，本项目 Windows 官方激活命令是 PowerShell 版。
- `终端`（Windows Terminal）：窗口容器，里面可以跑 PowerShell、cmd、WSL 等。
- 激活后，`vibe-trading` 相关命令在 cmd 和 PowerShell 中写法基本一致；只有激活命令不同。

---

## 4. 日常使用流程

### 4.1 首次配置（只需一次）

```powershell
vibe-trading init
```

按提示选择 LLM provider（如 DeepSeek）、填入 API key、Base URL 和模型名。
配置会写入 `~/.vibe-trading/.env`，不会写进项目仓库。

### 4.2 跑一次任务

```powershell
vibe-trading run -p "Backtest a 20/50-day moving average crossover on 600519.SH for the past 2 years"
```

### 4.3 查看历史与结果

```powershell
vibe-trading list              # 列出 run
vibe-trading --show <run_id>   # 查看 run card 和指标
```

### 4.4 其他常用入口

```powershell
vibe-trading --help            # 查看全部子命令
vibe-trading --version         # 查看版本
vibe-trading chat              # 交互式聊天
```

### 4.5 针对已有 run 的常用操作

```powershell
vibe-trading --continue <run_id> "把窗口改成 5"   # 基于上次 run 的上下文继续跑，不重新开
vibe-trading --show <run_id>                        # 查看 run card 和指标
vibe-trading --check <run_id>                       # 检查 run 是否真的产出报告
vibe-trading --code <run_id>                        # 查看本次生成的 signal_engine.py 代码
vibe-trading --pine <run_id>                        # 查看 TradingView Pine Script（如生成了）
vibe-trading --trace <run_id>                       # 回放该 run 的 agent 步骤
vibe-trading --list                                 # 等同 vibe-trading list
```

说明：
- `--continue` 是关键新用法：改参数、修条件、接着上次结果继续跑都用它，比从零重开省 token。语法是顶层 `vibe-trading --continue <run_id> "新指令"`，不是 `run --continue`。
- `--show` / `--check` / `--code` / `--pine` / `--trace` 都是只读操作，不消耗 LLM token。带 run_id 的命令统一用 `--` 形式；子命令 `show` / `check` 也保留可用，但文档只写 `--` 形式。
- 交互式 `vibe-trading chat` 里也有对应快捷指令：`/show <run_id>`、`/code <run_id>`、`/continue <run_id> <prompt>`。
- 单次限制迭代：`vibe-trading run -p "..." --max-iter 12`，效果等同 .env 里的 `AGENT_MAX_ITERATIONS=12`，只影响这一次。
- 长 prompt 建议写进文件再跑：`vibe-trading run -f prompt.txt`，避免命令行引号和换行问题。

---

## 5. 启动 Web UI（前端）

### 5.1 前置条件

- 需要 Node.js 版本 >= 22.22（前端 `package.json` 的 engines 要求）。
- 已安装 Node.js 24.19.0 LTS + npm 11.17.0（2026-08-07，winget），满足要求。

### 5.2 开发模式（一条命令起前后端）

```powershell
vibe-trading setup     # 首次或前端依赖变更后：npm install + 构建，生成 node_modules 和 dist
vibe-trading dev       # 后端 8899 + 前端 Vite 5899
```

打开 `http://localhost:5899`，前端会自动把 API 请求代理到后端 `http://localhost:8899`。

### 5.3 开发模式（双终端，README 原版）

```powershell
# 终端 1：API 后端
vibe-trading serve --port 8899

# 终端 2：前端 dev server
cd E:\gitCloneProgram\vibe-trading-src\frontend
npm install
npm run dev
```

打开 `http://localhost:5899`。

### 5.4 生产 / 单端口模式

```powershell
vibe-trading setup
vibe-trading serve --port 8899
```

打开 `http://localhost:8899`，FastAPI 会把构建好的 `frontend/dist/` 作为静态文件返回。

### 5.5 端口速查

| 模式 | 后端 | 前端 | 访问地址 |
|---|---|---|---|
| dev | 8899 | 5899 | http://localhost:5899 |
| serve（已构建） | 8899 | 8899 | http://localhost:8899 |

### 5.6 开发模式和生产模式有什么区别？

| 对比项 | 开发模式（`vibe-trading dev`） | 生产/单端口（`setup` + `serve`） |
|---|---|---|
| 端口 | 前端 5899 + 后端 8899 | 都走 8899 |
| 前端代码改动 | Vite 热更新，改完刷新页面即可 | 需要重新 `vibe-trading setup` 构建 |
| 适用场景 | 自己改前端、调试 | 日常使用、单端口访问 |
| 启动前要求 | 先执行过一次 `setup`（生成 node_modules） | 先执行 `setup`（生成 dist） |

`vibe-trading setup` 不需要每次运行：只在首次、`frontend/package.json` 或锁文件变更、node_modules/dist 被删后执行。

---

## 6. 修改代码与添加依赖

### 6.1 只改 Python 代码

本项目是 editable 安装（`pip install -e .`），改 `agent/` 下的代码后**直接重跑命令即生效**，无需重新安装。

### 6.2 新增 Python 依赖

修改 `pyproject.toml`（或 `requirements-lock.txt`）后，在项目根目录执行：

```powershell
pip install -e . --timeout 1800
```

pip 会补装新增依赖，不需要重建 venv。
如果不放心旧依赖，可加 `--upgrade`；只有依赖大面积冲突时才考虑重建 `.venv`。

### 6.3 新增前端依赖

修改 `frontend/package.json` 后执行：

```powershell
vibe-trading setup
```

或手动：

```powershell
cd E:\gitCloneProgram\vibe-trading-src\frontend
npm install
```

---

## 7. 推送到自己的 GitHub 仓库

当前 git 配置：

- 分支：`mumu-main`
- `origin`：`git@github.com:Sekight/Vibe-Trading.git`（自己的 fork，SSH）
- `upstream`：`https://github.com/HKUDS/Vibe-Trading.git`（原项目，HTTPS）

首次推送：

```powershell
git push -u origin mumu-main
```

以后日常推送：

```powershell
git add -A
git commit -m "描述你的修改"
git push origin mumu-main
```

注意：

- `origin` 是 SSH 地址，需要本机 SSH key 已关联 GitHub；否则改 HTTPS：
  `git remote set-url origin https://github.com/Sekight/Vibe-Trading.git`
- 本机访问 github.com 主域曾被网络阻断，push 可能需要网络恢复或代理。
- 拉取原项目更新（网络可用时）：
  `git fetch upstream && git merge upstream/main`

---

## 8. 常见问题 FAQ

### 8.1 为什么要先激活？能不能不激活？

激活只是把 `.venv\Scripts` 加进 PATH，让你少打完整路径。不激活就用完整路径，功能完全一样。

### 8.2 运行报错“禁止运行脚本”？

见第 2.1 节，用 `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` 只放开当前窗口。

### 8.3 没有 API key 能跑吗？

- `vibe-trading --version`、`--help`、`serve` 可以无 key 运行。
- `vibe-trading run` 的 agent 回测需要 LLM provider key。
- 配置方法：`vibe-trading init`，key 存在 `~/.vibe-trading/.env`，不要提交到仓库。

### 8.4 run card 在哪里看？

跑完 `vibe-trading run` 后，用 `vibe-trading list` 找 run_id，再用
`vibe-trading --show <run_id>` 查看 run card 和指标。

### 8.5 为什么 GitHub 上 clone 不下来？

本机 github.com 主域/git 通道曾被网络阻断，但 codeload / PyPI / raw.githubusercontent.com 可用。
当前源码是通过官方 zip 解压 + `git init` 建立的开发仓库。

### 8.6 cmd 里出现 `[36m`、`[0m` 等乱码怎么办？

原因：cmd 老式控制台不解析 ANSI 颜色转义序列，Rich 美化界面直接输出转义码；本机实测注册表 `VirtualTerminalLevel` 未生效。

已解决（2026-08-07）：本地源码 `agent/cli/theme.py` 已把 Windows 下 `legacy_windows` 改为 `True`，Rich 改用 Win32 控制台 API 渲染，cmd 中不再输出 ANSI 转义。
- 不再需要设置注册表，也不需要 Windows Terminal。
- 改的是本地开发源码，推送自己 fork 时一并带上即可。
- 若以后想恢复 ANSI 彩色输出，把该行改回 `legacy_windows=False if sys.platform == "win32" else None`。
- `vibe-trading --no-rich init` 对 init 无效；`--no-rich` 主要作用于 `run` 输出。

### 8.7 想用列表里没有的模型（如 deepseek-v4-flash）？

- `init` 的 “Select default model” 提示可以自由输入，直接回车才使用括号里的默认模型。
- DeepSeek 官方 provider 选 3 后输入 `deepseek-v4-flash`；OpenRouter 则输入 `deepseek/deepseek-v4-flash`。
- 也可以直接编辑 `C:\Users\mumu\.vibe-trading\.env`，把 `LANGCHAIN_MODEL_NAME` 改成 `deepseek-v4-flash`。

### 8.8 之前加的 VirtualTerminalLevel 注册表要删吗？

- 已改用源码渲染修复 cmd 乱码，注册表项不再需要，留着也无害。
- 想恢复系统默认：`reg delete HKCU\Console /v VirtualTerminalLevel /f`，只删这一个值。

### 8.9 OpenRouter 是什么？为什么推荐？怎么用？

- OpenRouter 是聚合多家模型提供商的网关：一个 API key 就能调用 OpenAI / DeepSeek / Anthropic / Google 等大量模型，统一走 OpenAI 兼容接口。
- 项目把它列为 recommended，是因为一次配置即可随时切换模型，不用给每家 provider 单独申请 key。
- 用法：到 https://openrouter.ai/keys 注册并创建 key（格式 `sk-or-v1-...`）；`vibe-trading init` 选 1，粘贴 key，Base URL 用默认 `https://openrouter.ai/api/v1`，模型名填 `厂商/模型`，如 `deepseek/deepseek-v4-flash`。
- 模型清单与价格：https://openrouter.ai/models。
- 不想用网关，直接选 3 DeepSeek 官方 API 也可以，模型名填 `deepseek-v4-flash`。

### 8.10 Tushare token 是什么？一定要填吗？

- Tushare（https://tushare.pro）是 A 股金融数据平台，token 用于获取日线、财务等数据。
- 可选项：直接回车跳过即可。Vibe-Trading 自带免费 A 股 fallback（mootdx / AKShare），没有 token 也能回测 A 股。
- 想用 Tushare：注册后在个人中心复制 token 填入；Token 与 DeepSeek key 无关，只影响行情数据源。

### 8.11 日志里 `������ E �еľ�û�б�ǩ��` 是什么？

- 这是 Windows cmd 的 `dir` 输出（“驱动器 E 中的卷没有标签…”）被错误按 UTF-8 解码产生的乱码，属于显示问题，回测本身成功（exit_code 0）。
- 已修复 `agent/src/tools/bash_tool.py`：先按 UTF-8 解码，失败再按系统编码解码，之后新 run 不再出现。

### 8.12 `vibe-trading setup` 需要每次执行吗？

- 不需要。只在首次、前端依赖变更（package.json / package-lock.json）、或 node_modules/dist 被删除后执行。
- 开发模式只要 node_modules 存在，直接 `vibe-trading dev`。
- 生产模式改过前端代码后要重新 setup，dist 才会更新。

### 8.13 `run_dir ... outside allowed run roots` 报错是什么？

- 这是生成代码的安全校验：回测脚本只能在允许的 run 目录里写文件。
- 本机根因：沙箱子进程把 HOME 指到临时目录，默认 run root 被解析到 temp；而实际 run 目录是 `C:\Users\mumu\.vibe-trading\runs`，不在允许列表里。
- 为什么以前能跑：旧 pip 版没有“临时 HOME 沙箱”；切换到源码版后，回测子进程新增了临时 HOME 重定向（VT-001），默认 run root 就解析到了 temp，从而触发拦截。
- 临时修复（cmd）：`set VIBE_TRADING_ALLOWED_RUN_ROOTS=C:\Users\mumu\.vibe-trading\runs`，再运行 `vibe-trading run`。
- 临时修复（PowerShell）：`$env:VIBE_TRADING_ALLOWED_RUN_ROOTS="C:\Users\mumu\.vibe-trading\runs"`。
- 永久修复：在 `C:\Users\mumu\.vibe-trading\.env` 加一行 `VIBE_TRADING_ALLOWED_RUN_ROOTS=C:\Users\mumu\.vibe-trading\runs`；或 `setx VIBE_TRADING_ALLOWED_RUN_ROOTS "C:\Users\mumu\.vibe-trading\runs"` 后新开窗口。
- 已执行（2026-08-07）：该行已追加到 `C:\Users\mumu\.vibe-trading\.env`，新 run 直接生效。
- 该变量只加目录白名单，不影响 API key 和其他配置。

### 8.14 `AgentLoop error: Connection error / WinError 10054` 是什么？

- 含义：agent 调用 LLM（如 DeepSeek）时，远端把连接强制关闭，属于瞬时网络或服务端问题，不是本地配置/代码错误。
- 处理：先直接重跑一次；可先验证 `curl.exe -s -o NUL -m 20 -w "http_code=%{http_code} time=%{time_total}s" https://api.deepseek.com/v1/models`（输出 401 且 time 很小即网络通，000/超时即不通）。
- 若反复出现：把 `~/.vibe-trading/.env` 里的 `MAX_RETRIES` 提到 5、`TIMEOUT_SECONDS` 提到 300 再试；开代理/VPN 时先关闭直连测试；或改用 OpenRouter 网关。

### 8.15 回测日志出现 `eastmoney suggest failed ... Expecting value` / 候选为空？

- 已定位并修复（2026-08-07）：`searchapi.eastmoney.com` 对 Python HTTPS 请求会返回 JSONP 兜底页（`jQuery...(passportWeb...)`），不是股票候选；`response.json()` 因此报 `Expecting value`，agent 拿不到 600519/600097 等候选，反复尝试后超时。
- 修复内容：
  1. `agent/backtest/loaders/eastmoney_client.py` 的 `get_json()` 改为先取 `throttled_get()` 原始响应文本，再走已有的 `_strip_jsonp()`，兼容 JSON/JSONP 两种包裹。
  2. 搜索 URL 改为 `http://searchapi.eastmoney.com/api/suggest/get`（仅股票名/代码搜索，无敏感信息）；本机实测 Python 走 HTTPS 会被边缘节点返回 JSONP 兜底页，走 HTTP 返回正常 `QuotationCodeTable`。
  3. 同步更新 `agent/src/tools/symbol_search_tool.py` 的搜索 URL，并把 `tests/test_eastmoney_client.py`、`test_dragon_tiger_tool.py`、`test_stock_news_tool.py` 的 mock 改为 `throttled_get`；相关 4 个测试文件 `54 passed`。
- 若日志仍见 `yahoo search failed ... 403`：那是 Yahoo 对 A 股代码搜索的常态限制，不影响东财候选，可忽略。
- 若短时间内连跑多次后遇到 `RemoteDisconnected` / 断连：东财按来源 IP 限流甚至临时封禁（模块默认每主机至少间隔 1 秒），等 5-10 分钟再跑，或用 `VIBE_TRADING_EASTMONEY_MIN_INTERVAL` 调大请求间隔。
- 改完源码后无需重装：源码版 `pip install -e .` 已让修改即时生效，直接重跑 `vibe-trading run` 即可。

---

### 8.16 怎么用自带 local loader（CSV / Parquet / DuckDB）？

- WebUI 没有数据源选择器，local loader 是“配置文件 + 对话里指定”，不是页面开关。
- 配置放在 `C:\Users\mumu\.vibe-trading\data-bridge\config.yaml`（对应源码 `agent/backtest/loaders/local_loader.py`）。示例：

  ```yaml
  sources:
    - symbol: "600519.SH"
      type: csv
      path: "E:/data/600519.csv"
      columns:
        date: "trade_date"
        open: "open"
        high: "high"
        low: "low"
        close: "close"
        volume: "volume"
      date_format: "%Y-%m-%d"
  ```

- 必须至少提供 `open/high/low/close`，volume 可选；Parquet 用 `type: parquet` + `path`，DuckDB 用 `type: duckdb` + `db_path` + `query`。
- 对话/CLI 里要用 `local:` 前缀指定，例如“用本地数据回测 `local:600519.SH`，2024 年全年，日线”。agent 会调用 `get_market_data(codes=["local:600519.SH"], source="auto")`；`get_market_data` 的 source 枚举里没有 local，所以不要写 `source: local`。
- 文件可以是任意粒度：请求更粗周期会自动聚合 OHLCV；请求比文件更细的周期无法造数据，会原样返回并警告。
- Windows 兼容（2026-08-07 已修）：回测子进程用临时 HOME 隔离，原来靠符号链接暴露 `data-bridge`，无开发者模式时链接失败会读不到配置；现在 `agent/src/core/runner.py` 在链接失败时复制 data-bridge/qveris.json 小配置文件（cache 不复制），`tests/test_runner_env.py` 新增回归测试，`12 passed`。

### 8.17 改完 Python 源码后，Web UI 直接发任务会生效吗？

- 结论：需要重启后端进程，不能在 Web UI 里只刷新页面。因为 `vibe-trading serve` / `vibe-trading dev` 启动的 FastAPI 后端没有开 `uvicorn reload`（`agent/api_server.py` 的 `uvicorn.run(app, ...)` 未传 reload），已运行进程不会自动加载新代码。
- 重启方式：在运行后端的窗口按 `Ctrl+C` 停掉，再重新执行原来的命令（`vibe-trading serve --port 8899` 或 `vibe-trading dev`），等日志出现 `Application startup complete` 后刷新页面即可。
- 不需要重新 `pip install`：源码版是 `pip install -e .`，新进程启动时直接读取仓库里的最新源码。
- `vibe-trading dev` 的 Vite 热更新只对前端源码生效；Python 后端改动同样要重启整个 `dev` 进程。
- 如果只是跑一次性 CLI（`vibe-trading run -p "..."`），每条命令都是新进程，改动直接生效，不需要先重启。

### 8.18 日志出现 `WinError 10054 远程主机强迫关闭了一个现有的连接`？

- 含义：agent 通过 SSE 流式读取 LLM 输出时，连接在流中途被远端/中转强制关闭（ReadError）。不是 key 失效、不是本地配置错误；`TIMEOUT_SECONDS` 调大对这种“中途断连”基本无效，因为报错不是超时。
- 本机实测（2026-08-07）：非流式请求、curl 流式请求、项目 venv 的 raw httpx 流式请求都能收到完整分片，只有 agent 实际跑的 langchain-openai 长流会间歇性 10054，说明是流式长连接不稳定，而不是服务不可用。
- 已修复：`agent/src/agent/loop.py` 在流式第一次失败后仍按原逻辑重试一次；若第二次也失败（确定性 4xx 除外），自动降级为一次非流式 `chat()`，任务照常完成，Web UI 会一次性显示答案。日志会出现 `Provider stream failed twice ... falling back to non-streaming chat` 和 `stream_reset` 事件 `reason=provider_stream_nonstreaming_fallback`。
- 涉及测试：`test_agent_loop_stream_retry.py`（新增双失败降级用例）、`test_agent_loop_terminal_state.py`（stream 与 fallback chat 都失败时仍返回 `provider_stream_error`）；相关 30 个 loop 测试通过。
- 仍想进一步降低触发概率：关闭本机代理（当前系统代理 127.0.0.1:7897）直连测试，或改用 OpenRouter / SiliconFlow 网关；也可以把 `MAX_RETRIES` 保持 5、`TIMEOUT_SECONDS` 保持 120-300。

### 8.19 任务跑 10+ 分钟、烧大量 token，最后前端显示“等待后已停止”？

- 典型过程：agent 生成 `code/signal_engine.py` 后，被回测沙箱 AST 校验打回（如 `Decorators are not allowed`、`Writing files via open(mode='w') ... not allowed`），于是反复“改代码→重跑回测→再改”，一次任务可跑 15+ 轮、烧 90 万+ token；前端则因 `VIBE_TRADING_SSE_TIMEOUT`（默认 90s）内收不到 SSE 事件而显示“等待 X 后已停止”，但后端可能仍在后台跑完。
- 已预防（2026-08-07）：`agent/src/skills/strategy-dev-manager/SKILL.md` 的 SignalEngine Contract 新增 Runner AST safety constraints：禁止一切装饰器、禁止 `open(mode='w'...)`/文件写入、禁止网络/子进程/eval/exec、禁止模块顶层与类体内可执行语句；诊断信息用 `print(...)` 输出即可。生成代码前先对照这份清单，能避免校验打回循环。
- 若仍然出现：改 `C:\Users\mumu\.vibe-trading\.env` 把 `VIBE_TRADING_SSE_TIMEOUT` 调大（如 600），重启后端，前端就不会在长任务中途断开等待。
- 策略“0 笔交易”不一定错：可能是入场条件在回测区间从未满足。可用已保存的 `artifacts/ohlcv_*.csv` 直接复算条件统计（触轨次数/突破次数/窗口分布），再决定放宽条件或换标的，不必整段重跑 agent。

### 8.20 怎么让任务跑得更快、更省 token？

- 已内置两项源码优化（2026-08-07）：
  1. `agent/src/skills/strategy-generate/SKILL.md` 与 `strategy-dev-manager/SKILL.md` 都新增 Runner AST safety constraints，并在生成策略后增加本地 AST 预检步骤，让 agent 在跑回测前先自查装饰器/写文件/网络/顶层语句，避免“生成→打回→重写”循环。
  2. 新增环境变量 `AGENT_MAX_ITERATIONS`（默认 50）：WebUI 会话的 AgentLoop 会读取它。建议在 `C:\Users\mumu\.vibe-trading\.env` 里设 `AGENT_MAX_ITERATIONS=12`，一般策略任务 8-12 轮足够，能封顶异常长跑并省 token。
- 同时建议设 `VIBE_TRADING_SSE_TIMEOUT=600`，避免前端在中途断开等待；设完重启后端。
- 工作流建议：①把“3 根窗口 / ATR×0.3 / 5% 风险 / 尾盘 14:55”等数字写死在 prompt 里，减少 agent 猜测；②同一只股票反复调参时，先离线跑一次拿到 `artifacts/ohlcv_*.csv`，之后用 local loader（`local:600097.SH`）或直接改已生成代码本地回测，完全不走 LLM；③策略信号数很少时，先看条件频次统计再决定放宽/换标的；④想保留已有 run 的上下文继续改，用 `vibe-trading --continue <run_id> "把窗口改成 5"`（见 4.5），不要从零重开。
- 数据缓存：固定标的 + 固定区间反复调参时，可开 loader 数据缓存 `VIBE_TRADING_DATA_CACHE=1` 复用已下载行情；是否值得开、怎么开、有哪些坑见 8.35。

### 8.21 data-bridge 是什么？怎么配置？

- 概念：data-bridge 是 Vibe-Trading 的“自带数据桥”，源码实现是 `agent/backtest/loaders/local_loader.py`。它让你把自己本地的 CSV / Parquet / DuckDB 行情文件喂给回测，不联网、不依赖东财/腾讯等在线数据源，也不会因为网络问题反复失败。
- WebUI 没有“本地数据”开关，data-bridge 是“配置文件 + 对话里指定”：配置文件放在 `C:\Users\mumu\.vibe-trading\data-bridge\config.yaml`，对话里写 `local:600097.SH` 触发。
- 本机当前还没有这个目录和文件（`vibe-trading init` 不会自动生成），需要自己创建。

配置步骤：

```powershell
New-Item -ItemType Directory -Force C:\Users\mumu\.vibe-trading\data-bridge
notepad C:\Users\mumu\.vibe-trading\data-bridge\config.yaml   # 粘贴 8.22 示例后保存（UTF-8）
```
编码要求：`config.yaml` 必须是纯文本 UTF-8（无 BOM）。不要从 Office/旧式“另存为”创建，否则会生成 OLE 二进制文件（文件头 `D0 CF 11 E0`），VSCode 会提示二进制、记事本显示乱码；本机 2026-08-08 踩过此坑，坏文件已备份为 `config.yaml.bad`。
检查方法：用 VSCode 打开后看右下角编码是否为 UTF-8；若想转换，VSCode 右下角点编码 → “Save with Encoding” → UTF-8。

然后把你的数据文件放到该目录（或任意路径，config 里写绝对路径），再在对话/CLI 里说：用本地数据回测 `local:600097.SH`，2024-04-03 到 2025-03-07，日线。agent 会用 `local:` 前缀走 local loader。

注意：`config.yaml` 里的 `symbol` 必须和对话里 `local:` 后面的代码完全一致；不要写 `source: local`（市场数据 API 的 source 枚举里 local 只通过 `local:` 前缀路径生效）。

### 8.22 `data-bridge/config.yaml` 格式详解

```yaml
sources:
  - symbol: "600097.SH"          # 对话里 local:600097.SH 精确匹配这一项
    type: csv                     # csv / parquet / duckdb 三选一
    path: "C:/Users/mumu/.vibe-trading/data-bridge/600097_daily.csv"
    columns:                      # 你的文件列名 -> 标准字段；文件本来就叫 date/open/high/low/close/volume 时可不写
      date: "trade_date"
      open: "open"
      high: "high"
      low: "low"
      close: "close"
      volume: "volume"
    date_format: "%Y-%m-%d"      # 可选；不写则尝试自动解析

  - symbol: "BTC-USDT"            # parquet 示例
    type: parquet
    path: "~/data/btc.parquet"

  - symbol: "MYINDEX"             # duckdb 示例（用 db_path + query）
    type: duckdb
    db_path: "~/data/market.duckdb"
    query: "SELECT * FROM prices WHERE ticker = 'MYINDEX'"
```

字段说明：
- `symbol`（必填）：对话里 `local:` 后面用的代码。
- `type`（必填）：`csv` / `parquet` / `duckdb`。
- `path`：CSV/Parquet 的文件路径；`db_path` + `query` 是 DuckDB 专用。路径支持 `~/` 开头和绝对路径。
- `path` 省略不会默认指向 data-bridge 目录；必须显式写文件路径，否则 local loader 打 warning “missing path for symbol” 并返回空数据。
- `columns`：把文件列名映射成标准 `date/open/high/low/close/volume`，缺省即按标准列名读取。
- `date_format`：可选，如 `%Y-%m-%d`、`%Y-%m-%d %H:%M:%S`。
- 校验：文件必须含日期列和 `open/high/low/close`；`volume` 缺省自动补 0。配置为空或文件不存在时，local loader 不可用且不会静默回退到网络数据源。

`date_format` 常用格式（Python strftime/strptime 规则，local loader 用 `pd.to_datetime(..., format=date_format)` 解析）：

| 格式 | 含义 | 示例 |
|---|---|---|
| `%Y` | 4 位年份 | 2024 |
| `%m` | 2 位月份 | 04 |
| `%d` | 2 位日期 | 03 |
| `%H` | 24 小时制小时 | 14 |
| `%I` | 12 小时制小时 | 02 |
| `%p` | AM/PM | PM |
| `%M` | 分钟 | 55 |
| `%S` | 秒 | 00 |
| `%f` | 微秒（6 位） | 123456 |
| `%z` | UTC 时区偏移 | +0800 |

对应常见文件内容：

```text
2024-04-03                    -> %Y-%m-%d               （日线）
2024-04-03 14:55              -> %Y-%m-%d %H:%M         （15m/30m/小时）
2024-04-03 14:55:00           -> %Y-%m-%d %H:%M:%S      （分钟线）
2024-04-03T14:55:00           -> %Y-%m-%dT%H:%M:%S
04/03/2024 2:55 PM            -> %m/%d/%Y %I:%M %p
2024-04-03 14:55:00.123456    -> %Y-%m-%d %H:%M:%S.%f
2024-04-03 14:55:00+08:00     -> %Y-%m-%d %H:%M:%S%z
```

写法就是把文件里日期列的样子按上表拆成对应占位符，中间的分隔符（`-`、`/`、空格、`T`、`:`、`.`）原样保留。不写 `date_format` 时 pandas 也会尝试自动识别常见格式，但写明更稳妥、解析更快。

### 8.23 怎么确认数据是什么时间周期

config.yaml 里不写周期，周期由你文件的原始粒度决定。判断方法：

1. 最快：用 VSCode/Excel 打开 CSV，看相邻两行日期差。相邻差 1 天是日线（1D），差 1 小时是 1H，差 15 分钟是 15m，差 1 分钟是 1m。
2. 本机现成例子：`C:\Users\mumu\.vibe-trading\runs\bb_macd_600097_20240403_20250307\artifacts\ohlcv_600097.SH.csv` 共 223 条，日期 2024-04-03 到 2025-03-07，逐日一条，即日线。
3. 命令行算中位间隔（在项目根目录用 venv 的 python）：

```powershell
.\.venv\Scripts\python.exe -c "import pandas as pd; df=pd.read_csv(r'你的文件.csv'); s=pd.to_datetime(df.iloc[:,0]).sort_values(); print('rows:', len(df)); print('range:', s.iloc[0], '~', s.iloc[-1]); print('median diff:', s.diff().dropna().median())"
```

周期与请求的关系（local loader 自动处理）：
- 请求比文件更粗的周期（如 15m 文件请求 1D）→ 自动聚合为标准 OHLCV。
- 请求比文件更细的周期（如日线文件请求 1H）→ 无法造数据，原样返回并告警。
- 回测实际用的周期，看该次 run 的 `config.json` 里 `interval` 和 `artifacts/ohlcv_*.csv` 的行间隔。

### 8.24 run 目录在哪里，里面都是什么

位置：
- 当前默认：`C:\Users\mumu\.vibe-trading\runs\<run_id>`（CLI 和 WebUI 都是这里）。
- 早期/其他版本也可能出现在 `E:\gitCloneProgram\vibe-trading-src\agent\runs\<run_id>`；`run_card.json` 的 `run_dir` 字段会记录本次实际目录。
- 允许的 run roots 由 `VIBE_TRADING_ALLOWED_RUN_ROOTS` 控制，见 8.13。

结构（以一次成功 run 为例）：

```text
<run_id>/
├─ config.json                 回测参数：codes / start_date / end_date / interval / source / initial_cash / 费率 / engine / optimizer / validation / entry_mode / exit_mode（详见 8.34）
├─ req.json                    用户原始 prompt + context（session_id）
├─ state.json                  状态：{"status":"success"} 或失败原因
├─ run_card.json / run_card.md 结果摘要：metrics、data_sources、hash、artifacts 清单
├─ llm_usage.json              agent 每轮迭代的 token 统计（input / output / total）
├─ trace.jsonl                 agent 步骤追踪日志（调试用）
├─ code/
│  └─ signal_engine.py          本次策略生成的信号引擎代码
├─ artifacts/
│  ├─ metrics.csv               指标一行：total_return / annual_return / max_drawdown / sharpe / win_rate / trade_count 等
│  ├─ trades.csv                每笔交易明细
│  ├─ equity.csv                每日权益曲线
│  ├─ positions.csv             每日持仓
│  ├─ ohlcv_<代码>.csv          回测实际使用的行情（可直接复制给 data-bridge 复用）
│  ├─ rebalance_notes.json/.md  调仓记录
│  ├─ validation.json           蒙特卡洛等稳健性结果（可选）
│  ├─ risk_xray.json/.md        风险透视（可选）
│  └─ grounding_evidence.json   数据来源/证据
└─ logs/
   ├─ runner_stdout.txt         回测子进程标准输出
   └─ runner_stderr.txt         回测子进程报错
```

注意：
- 中途失败/被中止的 run 可能只有 `req.json`、`trace.jsonl`、`state.json`，没有 `code/` 和 `artifacts/`。
- 没有自动清理机制：新任务永远新建目录，旧 run 不会被覆盖也不会自动删除，需要自己手动清理。
- 查看入口：`vibe-trading list` 列所有 run，`vibe-trading --show <run_id>` 看 run card 和指标。

### 8.25 `source=local` 报 missing: ['local:600097.SH']，然后卡在 tushare token？

- 根因（已修复，2026-08-08）：local loader 返回的数据 key 会去掉 `local:` 前缀（返回 `600097.SH`），但 runner 按请求原样 `local:600097.SH` 去比对，误判“数据缺失”，随后回退到腾讯/东财/akshare/tushare 网络源，最终因 tushare 无 token 报错。
- 修复：`agent/backtest/runner.py` 取数前先剥离 `local:` 前缀；同时 local/qveris 数据源“失败即停止”，不再回退到任何网络源，配置缺失会直接报错而不是空转。
- 效果：`source: local` + `codes: ["local:600097.SH"]` 现在可正常回测，引擎实际收到的 key 是 `600097.SH`；直接跑 `python -m backtest.runner <run_dir>` 约 4-6 秒出结果。
- 注意：旧 run 的 `logs/runner_stderr.txt` 里可能残留修复前的报错，不影响 run card；重跑会覆盖。

### 8.26 `identity_mismatch` 后搜索 `000300 沪深300` 返回 0 候选是什么情况？

- 身份门（grounding）：一次会话会锁定唯一标的（如 600097.SH）；agent 再用 `get_market_data` 请求其它标的（如 000300.SH 沪深300 基准）时会被拦截，报 `identity_mismatch`，提示“先单独一轮调用 search_symbol 解析该标的，再使用完全一致的符号”。拦截只影响那一个工具调用，agent 会换路径继续，所以日志里 Error “一下就没”是正常现象。
- 000300 搜索 0 候选：本次 eastmoney/yahoo 都返回空（状态 ok 但无数据）；早前会话同样查询曾返回过 000300.SH，说明接口覆盖不稳定。`get_market_data` 要求先解析成功才能取数，因此独立拉沪深300基准在本环境经常拿不到。
- 重要：local 源且 config 没有 `benchmark` 字段时，run card 里的 `benchmark_return` 是策略标的自身持有收益（600097 同期 -18.54% ≈ 8.83/10.84-1），不是沪深300；`excess_return` / `information_ratio` / `tracking_error` / `benchmark_beta` 也随之没有真实对比意义。
- 想要真实基准：在 data-bridge 配置里加一条 000300.SH 日线 CSV，并在 config.json 写 `"benchmark": "000300.SH"`，local 源会走本地 loader 离线取基准，run card 里的 benchmark 才是真的沪深300。
---

> ### 8.27 回测报告里怎么看持仓占比和手数？
> - WebUI 交易明细新增两列：`持仓占比`（position_weight = 成交金额 / 当日总权益）和 `手数`（lots，仅 A 股按 100 股/手，其他市场留空）。
> - 新 run 的 `artifacts/trades.csv` 直接带 `position_weight`、`lots` 两列；旧 run 没有这两列时，WebUI 会用 `qty × price / equity.csv 当日权益` 现算占比、A 股用 `qty / 100` 现算手数。
> - 指标区新增 `avg_position_weight`（平均持仓占比）与 `max_position_weight`（最大持仓占比）；`positions.csv` 仍是每日目标权重（0=空仓，1=满仓），`risk_xray_avg_invested` 与平均持仓占比同值。

  ---

> ### 8.28 prompt 有换行，`run -p "..."` 会被 shell 当回车执行怎么办？
> - 把长 prompt 保存为 UTF-8 文本文件（项目里建议放 `E:\gitCloneProgram\vibe-trading-src\prompts\`，已有一份 `bb_macd_10stocks_2023_2025.txt` 可直接用），然后执行 `vibe-trading run -f prompts\bb_macd_10stocks_2023_2025.txt`（激活 venv 后在项目根目录）。
> - 原理：`-p "..."` 的多行文本在 cmd/PowerShell 交互式输入时，回车可能被当成命令结束；`-f` 让 CLI 自己读文件，换行、中文、引号、`<=` 都原样保留。
> - 用记事本/VSCode 编辑 prompt 文件时注意保存为 UTF-8（无 BOM），不要用 Word/Office 另存，否则会变二进制或乱码（同 8.2 的编码坑）。
> - 不想用文件时：① WebUI 输入框直接粘贴多行最省事；② 交互式 `vibe-trading chat` 里直接粘贴多行；③ PowerShell 用 here-string 变量再传：`$prompt = @'...多行...'@` 然后 `vibe-trading run -p $prompt`。cmd 没有可靠的命令行换行方式，仍建议文件或 WebUI。

  ---

> ### 8.29 在 `vibe-trading chat` 里粘贴提示词，为什么“粘不进去”？
> - 粘贴动作由终端负责，不是程序负责。`vibe-trading chat` 的输入编辑器（prompt_toolkit）不会拦截 Ctrl+V，控制台没把剪贴板内容送进来，界面就毫无反应。
> - cmd 控制台：默认右键粘贴（快速编辑模式）；Ctrl+V 需要勾选“启用 Ctrl 键快捷键”才有效。没反应时在标题栏右键 → 属性 → 选项，勾上“快速编辑模式”和“启用 Ctrl 键快捷键”；应急可用标题栏右键 → 编辑 → 粘贴。
> - Windows Terminal（Win11 开始菜单搜“终端”，或 Win+X → 终端）：Ctrl+V / Ctrl+Shift+V / 右键都能粘贴，最推荐用它跑 chat。
> - 粘贴后按 Enter 不发送、只换行，是多行编辑的正常行为：Enter 只有在 ASCII 括号 `()` `[]` `{}` 和引号都配对时才提交；不配对就插入换行。全角括号 `（）【】` 不参与判断，中文规则通常粘贴完直接回车即可。
> - Alt+Enter 或 Esc+Enter = 强制插入换行；Ctrl+J 只是模拟回车，仍走同一套括号检查，不能“强制提交”。若反复换行不提交，检查提示词里有没有不成对的半角括号/引号。
> - 实在粘贴不了：`vibe-trading run -f prompts\bb_macd_10stocks_2023_2025.txt` 或 WebUI 输入框，两条路都支持多行且不依赖终端粘贴。

> ### 8.30 日线数据做“14:55 判断、尾盘集合竞价买入”的回测，会不会有未来函数？
> - 不会产生跨日未来函数，但有“日内近似”：信号日 D 只用 D 日及以前的数据计算指标，成交价也用 D 日收盘价模拟尾盘竞价，符合该策略的真实动作（14:55 时价格≈收盘价，随后以收盘价成交）。真正禁止的是用 D+1 及以后的数据。“信号日收盘价同时用于指标和成交”是刻意设计，不是未来数据。
> - 日线回测真正的近似点在盘中动作：① 止损用“当日最低价<=止损价”触发，成交近似为触发价（低开时按开盘价），而非真实盘中即时成交；② 止盈“触及中轨”用当日最低价判断、按收盘价离场，如果盘中触碰后又反弹，真实手动操作与回测结果会有偏差；③ “涨停不进场”用收盘涨幅 >=9.9% 判断，与 14:55 时点基本一致。
> - 想更严格只有两条路：信号日收盘计算、次日开盘成交（规避同收盘价，但已不是你真实的尾盘策略）；或接入分钟级数据做 14:55 快照信号 + 收盘价成交（最忠实，但当前回测引擎按日线目标持仓输出，需额外改造）。对日线策略，当前“同日收盘信号+收盘成交”是公认可接受的近似。

> ### 8.31 显示 SUCCESS 但没有报告，`vibe-trading --show <id>` 又报 TypeError 是什么情况？
> - SUCCESS 只代表 agent 那一轮跑完了，不代表回测产出报告。判断是否真跑完：看 run 目录有没有 `artifacts/metrics.csv` 和 `run_card.json`。如果只有 `code/signal_engine.py` + `config.json` + `grounding_evidence.json`，说明策略代码已生成但回测 runner 没被调用，指标和交易明细自然不存在。
> - `vibe-trading show <id>` 的 TypeError 已修复（2026-08-08）：此前 `agent/cli/_legacy.py` 的 main 误用 `args.show`（`--show` 标志值）而不是 `args.run_id`，子命令方式下是 None，`RUNS_DIR / None` 抛错。现在 `vibe-trading --show <id>` 和子命令 `show <id>` 都能用，文档统一用 `--show`。
> - 已新增两个提醒机制：① agent 达到迭代上限、或已生成 `config.json`/策略代码却没产出 `run_card.json` 时，状态不再写 success，而是写 warning；② `vibe-trading --check <run_id>` 一键列出 run 的关键产物（req/config/signal_engine/run_card/metrics/trades/logs）并给出 REPORT OK / NO REPORT 结论。
> - 本次这类“SUCCESS 无报告”的直接原因：agent 迭代耗尽（最后被 forced_text_only 强制收尾，最后一条消息里是未执行的工具调用文本），它写完 config 和 signal_engine 后还没调用回测工具就结束了。补救：`vibe-trading --continue <id> "不要读 req.json 或 transcript，直接运行 python -m backtest.runner <run_dir> 并生成 run card"`，让它在已有代码基础上只做回测。

> ### 8.32 我不知道 req.json、transcript 是什么，下次怎么自己写 `--continue` 的提示词？
> - `req.json` 是 run 目录里保存你原始 prompt 的请求文件；`transcript_*.jsonl` 是那次 run 的完整对话日志，都存放在 `C:\Users\mumu\.vibe-trading\runs\<run_id>\` 和 `sessions\` 下。它们只是内部记录，你正常使用时不需要看懂，更不需要自己操作。
> - 写不出专业提示词没关系，`--continue` 只需要说人话：`vibe-trading --continue <run_id> "配置和策略代码已经生成好了，不要再重写代码，直接把回测跑完并生成 run card 和指标"`。`python -m backtest.runner <run_dir>` 是内部回测入口，agent 自己知道，不用你拼。
> - 如果上次 agent 又跑去翻历史文件浪费时间，可以加一句：`不要读 req.json、transcript、历史 run 的文件，只做回测`。

> ### 8.33 `vibe-trading --check <run_id>` 输出的每个文件是什么意思？
> - `req.json`：本次请求存档，包含你原始 prompt 和上下文；大小 199 表示 prompt 较短。
> - `config.json`：agent 生成的回测配置，如数据源（tencent/local）、周期（1D）、标的池、起止日期、初始本金、佣金/印花税/滑点。
> - `code/signal_engine.py`：策略信号引擎代码，回测实际执行的入场/出场/仓位逻辑。
> - `run_card.json`：run card，即回测结果摘要，含 artifacts 清单、状态、指标与数据来源；它是“报告”的标志性文件。
> - `artifacts/metrics.csv`：核心指标一行，如 total_return / annual_return / max_drawdown / sharpe / win_rate / trade_count。
> - `artifacts/trades.csv`：逐笔交易明细，含入场/出场日期、价格、手数、持仓占比、出场原因、盈亏。
> - `logs/runner_stdout.txt`：回测子进程的标准输出日志，排查回测内部报错用。
> - 判定标准：`run_card.json` 和 `artifacts/metrics.csv` 同时存在 → REPORT OK；缺任一个 → NO REPORT，说明代码可能生成了但回测没真正跑完。

> ### 8.34 run 目录下的 `config.json` 是什么？里面的字段都怎么用？
>
> `config.json` 是回测 runner 实际读取的“参数单”：agent 按你的提示词生成，也可以手动改；`python -m backtest.runner <run_dir>` 读它决定数据源、周期、标的、本金、费率、成交模式等，再加载 `code/signal_engine.py` 跑回测。它不含 API key；改完不会自动生效，需要重跑 runner 或用 `--continue` 续跑。
>
> 常见字段（不写某字段就用默认值；旧别名可同时保留）：
>
> | 字段 | 作用 | 默认值 |
> | --- | --- | --- |
> | `source` | 数据源：tencent / local / tushare / akshare / auto 等 | tushare |
> | `interval` | K 线周期：1m / 5m / 15m / 30m / 1H / 4H / 1D | 1D |
> | `codes` | 标的池，如 ["600519.SH"]；local 源可用 ["local:600097.SH"] | 必填 |
> | `start_date` / `end_date` | 回测起止日期，YYYY-MM-DD | 必填 |
> | `initial_cash` | 初始本金，引擎和指标都读它；`initial_capital` 是旧别名 | 1,000,000 |
> | `commission_rate` | 佣金费率（A股万2.5=0.00025，双边） | 0.00025 |
> | `commission_min` | 单笔最低佣金（A股 5 元）；旧别名 `min_commission` | 5.0 |
> | `stamp_tax` | 印花税，卖出单边（A股万5=0.0005）；旧别名 `stamp_duty` | 0.0005 |
> | `transfer_fee` | 过户费（A股万0.1=0.00001，双边） | 0.00001 |
> | `slippage` | 滑点比例（买价×1.001、卖价×0.999） | 0.001 |
> | `engine` | 回测引擎：daily / options | daily |
> | `entry_mode` | 开仓成交时点：next_open（次日开盘）或 close（信号日收盘） | next_open |
> | `exit_mode` | 平仓成交时点：next_open / close / stop（止损价成交） | next_open |
> | `optimizer` | 权重优化器名（如 risk_parity）；`optimizer_params` 传参数 | 无（不优化） |
> | `constraints` | 组合约束（总仓位、单标的上限等），需配合 optimizer 才生效 | 无 |
> | `validation` | 设为 true 时跑蒙特卡洛等稳健性验证，产出 artifacts/validation.json | false |
> | `benchmark` | 基准标的，如 "000300.SH"；配 local 数据源才能拿到真实基准 | 无 |
> | `extra_fields` | 取数时额外字段（如 vwap / amount） | 无 |
> | `fundamental_fields` / `event_feeds` | 进阶：给回测注入基本面或事件数据 | 无 |
> | `leverage` | 杠杆倍数；A股引擎强制 1，写多少都被覆盖 | 1.0 |
>
> 注意：`_run_card_effective_sources`、`_run_card_warnings` 是 runner 运行后写入的内部字段，不要手动编辑。
>
> #### 成交时点 `entry_mode` / `exit_mode`（重点）
>
> - 允许组合只有三种：`next_open/next_open`（默认，旧行为不变）、`close/close`、`close/stop`；`next_open/close`、`next_open/stop`、`close/next_open` 会在 `agent/backtest/engines/base.py` 直接报错。
> - `next_open`：信号日收盘出信号，次日开盘成交，避免用到当日收盘信息。
> - `close`：信号日收盘价成交，适合“尾盘集合竞价 / 当天决定当天成交”。
> - `stop`（只能配 `entry_mode=close`）：出场按策略给的止损价成交；当日最低价触及止损价时，成交价 = min(当日开盘价, 止损价)（跳空低开按开盘价，避免成交价低于开盘价）；未触及止损则按收盘价成交。
>
> #### `stop_prices`（策略代码字段，不写在 config.json）
>
> - 止损价由 `signal_engine.py` 自己算：`SignalEngine.generate()` 返回权重的同时，把 `self.stop_prices = {代码: pd.Series(止损价, index=交易日)}` 带上。
> - 只有 `exit_mode="stop"` 时引擎才读它；某天止损价为 NaN/缺失，当天出场退回收盘价成交。
> - `config.json` 不需要也不能写 `stop_prices`。
>
>
### 8.35 loader 数据缓存（`VIBE_TRADING_DATA_CACHE`）要不要开？什么时候开？

结论先说：你现在主要用 WebUI / `vibe-trading run` 发任务，这个缓存帮助不大（原因见下），更推荐直接用 data-bridge；只有当你改用 `python -m backtest.runner <run_dir>` 直接反复调同一批标的 + 固定区间时，才值得开。

- 是什么：回测 loader 的“可选本地行情缓存”。开启后，各数据源（tencent / tushare / akshare / mootdx / eastmoney / yfinance / ccxt / okx / futu / finnhub / tiingo / fmp / baostock / local 等）把“已完全结算的历史 K 线”按 key 存成 parquet；下次同一请求直接读本地，不联网。
- 怎么开：在 `C:\Users\mumu\.vibe-trading\.env` 加 `VIBE_TRADING_DATA_CACHE=1`（`true/yes/on` 也行），默认关闭，不设或写 `0` 即关。默认目录是 `C:\Users\mumu\.vibe-trading\cache\loaders`；想换位置再加 `VIBE_TRADING_DATA_CACHE_ROOT=E:\...\loader-cache`。改完重启 `serve` / `dev` 后端，或新开 CLI 进程。
- 缓存了什么：只有 loader 返回的行情 DataFrame（OHLCV + 你请求的 `extra_fields`）。不缓存 run card、策略代码、LLM 分析、token 用量，也不含 API key。目录结构为 `cache\loaders\<source>\<sha256>.parquet` + 同名 `.parquet.json` 元数据。
- key 怎么算：`缓存版本 + source + symbol + timeframe + start_date + end_date + fields`。所以只有“同一数据源 + 同一标的 + 同一周期 + 同一区间 + 同一字段”才会命中。
- 增量吗：不做增量。区间从 2023-01-01~2023-12-28 改成 ~2023-12-31 时，key 变了，会全量重拉并写一个新文件，旧文件仍留在磁盘，不会只补 3 天。
- 什么时候会缓存成功：只有 `end_date` 严格早于今天（最后一根 bar 已结算）才会缓存；区间结束日等于今天或未来时每次重新联网，避免把未完成的 bar 缓存成“最终数据”。
- 什么时候建议开：
  - 同一批标的 + 固定区间反复调参，且用直接 runner 跑（`python -m backtest.runner <run_dir>`）：缓存命中后取数是秒级，完全跳过网络。
  - 数据源网络不稳、限流或按次计费（yfinance / finnhub / tiingo / fmp / tushare 等）。
  - 长区间分页很慢的源（腾讯日线 500 根/段）。
- 什么时候不建议开 / 注意：
  - 本机 WebUI 和 `vibe-trading run` 的 agent 回测走沙箱临时 HOME；本机没有开发者模式、创建不了符号链接，`agent/src/core/runner.py` 对 `cache` 目录“不复制、只跳过”，所以缓存对沙箱内取数基本无效（写了也随临时 HOME 删除）。缓存主要对直接跑 runner 有用。
  - 命中率低就别开：每次区间/标的都不同，只会不断累积 parquet 文件。
  - 已经用 data-bridge 本地 CSV 时没必要：数据本来就在本地，再缓存一份是重复占盘。
  - 缓存没有自动过期：数据源后续修正复权、除权或历史数据时，旧缓存不会自己失效；2026-08-10 腾讯 500 根截断 bug 就是靠把缓存版本 3 升到 4 才让旧坏条目失效的。
  - 若在数据源出 bug 或网络半截期间开着缓存，坏数据也会被缓存并反复命中；遇到可疑结果先清缓存再重跑。
- 怎么清：回测没在跑时删除 `C:\Users\mumu\.vibe-trading\cache\loaders` 整个目录，或只删对应 `<source>` 子目录即可，程序下次会自动重建。
- 替代方案：需要“确定且可长期复用”的数据，直接用 data-bridge（8.21）：把 `artifacts/ohlcv_*.csv` 复制到 data-bridge 目录，对话里用 `local:<symbol>` 回测，比缓存更透明、可控、可跨项目复用。

  ## 9. 命令速查表


| 目的 | 命令 |
|---|---|
| 激活 venv（PowerShell） | `.\.venv\Scripts\Activate.ps1` |
| 激活 venv（cmd） | `.\.venv\Scripts\activate.bat` |
| 首次配置 key | `vibe-trading init` |
| 跑一次任务 | `vibe-trading run -p "..."` |
| 列出 run | `vibe-trading list` |
| 查看 run | `vibe-trading --show <run_id>` |
| 检查 run 是否真产出报告 | `vibe-trading --check <run_id>` |
| 续跑 / 精调某次 run | `vibe-trading --continue <run_id> "新指令"` |
| 查看 run 生成代码 | `vibe-trading --code <run_id>` |
| 回放 run 轨迹 | `vibe-trading --trace <run_id>` |
| 单次限制迭代次数 | `vibe-trading run -p "..." --max-iter 12` |
| 从文件读 prompt | `vibe-trading run -f prompt.txt` |
| 查看帮助 | `vibe-trading --help` |
| 查看版本 | `vibe-trading --version` |
| 启动后端 | `vibe-trading serve --port 8899` |
| 构建前端 | `vibe-trading setup` |
| 开发模式（前后端一起） | `vibe-trading dev` |
| 新增 Python 依赖 | `pip install -e . --timeout 1800` |
| 新增前端依赖 | `vibe-trading setup` 或 `cd frontend; npm install` |
| 首次推送 | `git push -u origin mumu-main` |
| 日常推送 | `git add -A; git commit -m "..."; git push origin mumu-main` |

---

## 10. 文档维护

本文档随使用过程中的问答持续更新。遇到新的使用问题后，会在此追加对应章节，不删除历史说明。
