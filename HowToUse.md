# Vibe-Trading 本地使用手册（HowToUse）

> 适用环境：Windows 11 / macOS + Python 3.13 + 源码目录 `<repo_root>`
> 当前版本：vibe-trading-ai 0.1.13（editable 源码安装）
> 官方参考：`README.md` / `README_zh.md` / `wiki/` / `vibe-trading --help`

> 路径约定：<repo_root> = 本仓库根目录；<vibe_home> = %USERPROFILE%\.vibe-trading（Windows）或 ~/.vibe-trading（其他系统）。文中占位符使用前替换为实际路径。克隆后先进入仓库根目录，所有 <repo_root> 均指该目录。

---

 ## 1. 两个重要概念：短命令 vs 完整路径

- 激活 venv 后，`vibe-trading` 短命令会由 PATH 自动解析到：
  `<repo_root>\.venv\Scripts\vibe-trading.exe`
- 所以 `vibe-trading ...` 和 `vibe-trading.exe ...` 是**同一个程序**，不是两个版本。
- 没激活时，PowerShell/cmd 找不到短命令，只能用完整路径：
  ```powershell
  <repo_root>\.venv\Scripts\vibe-trading.exe --version
  ```
- 完整路径后面接什么参数，就有什么功能（`init` / `run` / `list` / `--show` / `serve` 都在）。

---

## 2. 激活环境

### 2.1 PowerShell（推荐）

```powershell
cd <repo_root>
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
cd /d <repo_root>
.\.venv\Scripts\activate.bat
```

### 2.3 macOS（zsh / bash）

```bash
cd <repo_root>
source .venv/bin/activate
```

macOS 的 `.venv` 需在本机重建，Windows 的 `.venv` 不能跨平台复用：先 `python3 -m venv .venv`，激活后 `pip install -e .`，再 `vibe-trading setup` 构建前端。

### 2.4 不激活

直接用完整路径，不用设置执行策略：

```powershell
<repo_root>\.venv\Scripts\vibe-trading.exe --version
```

```bash
# macOS 不激活时
<repo_root>/.venv/bin/vibe-trading --version
```

### 2.5 验证

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
- 直接重跑某个已完成的 run（代码和数据都已就绪，不经过 agent、不烧 LLM token）：在 `agent` 目录下执行

  ```powershell
  cd <repo_root>\agent
  ..\.venv\Scripts\python.exe -m backtest.runner "<vibe_home>\runs\<run_id>"
  ```

  后面加 `--with-analysis` 会在回测成功后补生成 LLM 分析报告 `analysis.md`（会调用一次 LLM，见 8.36）。
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
cd <repo_root>\frontend
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

### 5.7 运行详情页的标签页

打开任意 run 后，详情页从左到右是：

| 标签 | 内容 |
|---|---|
| 图表 | 原有价格/权益曲线（基于 artifacts 里的 OHLCV / equity） |
| 分析图 | 基于 digest 的 7 张分析图（ECharts 交互渲染，PNG 按需作为兜底；可用 `--with-charts` 或 MCP `action="charts"` 生成） |
| 分析 | LLM 生成的 `analysis.md` 报告（agent 自动写，或 runner 补生成） |
| 交易 | `artifacts/trades.csv` 交易明细（含持仓占比、手数） |
| 运行卡片 | `run_card.json` 摘要 |
| 代码 | 本次策略 `code/signal_engine.py` |
| 验证 | `validation.json` 稳健性结果（存在时才显示） |

7 张分析图：净值曲线（累计收益率 %）、回撤瀑布图（水下曲线，0 在上、负值在下）、单笔盈亏散点（红赚绿亏）、月度损益热力图（红赚绿亏）、盈亏 vs 持仓时长、MAE/MFE 金标准图、持仓分桶盈亏与胜率。图表数据从 `artifacts/` 现算，不额外落库。

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
cd <repo_root>\frontend
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
- 也可以直接编辑 `<vibe_home>\.env`，把 `LANGCHAIN_MODEL_NAME` 改成 `deepseek-v4-flash`。

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
- 本机根因：沙箱子进程把 HOME 指到临时目录，默认 run root 被解析到 temp；而实际 run 目录是 `<vibe_home>\runs`，不在允许列表里。
- 为什么以前能跑：旧 pip 版没有“临时 HOME 沙箱”；切换到源码版后，回测子进程新增了临时 HOME 重定向（VT-001），默认 run root 就解析到了 temp，从而触发拦截。
- 临时修复（cmd）：`set VIBE_TRADING_ALLOWED_RUN_ROOTS=<vibe_home>\runs`，再运行 `vibe-trading run`。
- 临时修复（PowerShell）：`$env:VIBE_TRADING_ALLOWED_RUN_ROOTS="<vibe_home>\runs"`。
- 永久修复：在 `<vibe_home>\.env` 加一行 `VIBE_TRADING_ALLOWED_RUN_ROOTS=<vibe_home>\runs`；或 `setx VIBE_TRADING_ALLOWED_RUN_ROOTS "<vibe_home>\runs"` 后新开窗口。
- 已执行（本机 2026-08-07）：该行已追加到 `<vibe_home>\.env`；其他机器按需设置。
- 该变量只加目录白名单，不影响 API key 和其他配置。

### 8.14 OpenCode Go 套餐的 API key 能用于 Vibe-Trading 吗？

- 可以。OpenCode Go 提供 OpenAI 兼容端点，Vibe-Trading 已内置 `opencode-go` provider（`agent/src/providers/capabilities.py`）。
- 配置写入 `<vibe_home>\.env`：
  ```ini
  LANGCHAIN_PROVIDER=opencode-go
  OPENAI_API_KEY=你的Go key
  OPENAI_BASE_URL=https://opencode.ai/zen/go/v1
  LANGCHAIN_MODEL_NAME=deepseek-v4-flash
  ```
- 可用模型清单：https://opencode.ai/zen/go/v1/models（含 deepseek-v4-flash、deepseek-v4-pro、kimi-k3、glm-5.2 等）。
- `vibe-trading init` 的列表暂未列出 OpenCode Go，直接编辑 `.env` 或后续加进 init 列表。
- 注意：`opencode.ai/zen/go/v1/models` 和端点表格里的 Model ID 就是 OpenAI 兼容请求要填的 `model`；`opencode-go/<model-id>` 前缀只用于 OpenCode 自己的配置，Vibe-Trading 直接用短 ID 即可。
- 验证（2026-08-10 已实测通过）：`vibe-trading provider doctor` 显示 `provider=opencode-go`、`OPENAI_API_KEY=set`；最小 `vibe-trading run -p "Reply with exactly: OK"` 成功生成 run card，run_id 为 `20260810_225636_96_e7fbce`。
- 踩坑：`.env` 里必须写成 `OPENAI_API_KEY=sk-...` 同一行；key 换行会导致 dotenv 读不到。`.env` 编辑后若 doctor 显示 key 未 set，先检查是否断行。
- `provider doctor` 会把 base_url 脱敏成 `https://opencode.ai`（只显示域名），实际请求仍会使用 `OPENAI_BASE_URL=https://opencode.ai/zen/go/v1`，不要看到域名就去改掉完整路径。
- chat completions 偶发 500 时先等 1-2 分钟重试：2026-08-10 实测 OpenCode Go 端点曾连续 500，同一 key/模型稍后重试即返回 200，不是本地配置错误。

- 多套 provider 配置并存时，生效的是 `LANGCHAIN_PROVIDER` 指定的那一套：当前为 `opencode-go`，所以只读取 `OPENAI_API_KEY` / `OPENAI_BASE_URL`；`DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` 即使仍在 `.env` 中也不会参与请求，只是保留待用。想切回 DeepSeek 官方，把 `LANGCHAIN_PROVIDER` 改成 `deepseek` 即可，模型名无需改。

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
- 配置放在 `<vibe_home>\data-bridge\config.yaml`（对应源码 `agent/backtest/loaders/local_loader.py`）。示例：

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
- 多标的写法：一个 prompt 里列出多个 `local:` 前缀即可，例如“用本地数据回测 `local:600348.SH`、`local:601298.SH`、… 共 10 只，2023-01-01 ~ 2025-12-31，日线”。所有标的都必须登记在 data-bridge 的 `config.yaml`，缺一只会 fail closed，不会自动联网补齐。
- 直接跑 runner 的写法（与 agent 工具路径相反）：在 run 目录的 `config.json` 里写 `"source": "local"` 且 `"codes": ["local:600348.SH", ...]`，然后 `cd agent` 执行 `..\.venv\Scripts\python.exe -m backtest.runner "<run_dir>"`；此时可以也应当写 `source: local`，缺标的同样直接报 `incomplete data`，不会走网络兜底。
- 文件可以是任意粒度：请求更粗周期会自动聚合 OHLCV；请求比文件更细的周期无法造数据，会原样返回并警告。
- 日期范围按请求过滤：local loader 对本地文件做 `[start_date, end_date]` 闭区间截取，文件里多出的日期不会参与回测。本地数据完整覆盖请求区间时正常跑；只覆盖一部分时（例如文件到 2023-12-31，回测请求到 2024-01-31）不会报错，但回测实际只用到文件最后一天，且目前 runner 只校验“数据起点晚于请求起点 10 天以上”并告警，不校验终点。跑完建议看 `artifacts/ohlcv_*.csv` 最后一行 `trade_date`，或 run_card / metrics 确认实际区间。
- Windows 兼容（2026-08-07 已修）：回测子进程用临时 HOME 隔离，原来靠符号链接暴露 `data-bridge`，无开发者模式时链接失败会读不到配置；现在 `agent/src/core/runner.py` 在链接失败时复制 data-bridge/qveris.json 小配置文件（cache 不复制），`tests/test_runner_env.py` 新增回归测试，`12 passed`。
- 复权口径（2026-08-12 实测）：现有 tencent/eastmoney loader 固定返回前复权（qfq），腾讯接口本身可传 `hfq` 返回后复权；两者对同一区间的涨跌幅可能不同（例：002133.SZ 2021-12-31 → 2024-12-31，qfq -14.08%，hfq -9.53%）。用户表格写“后复权”时要用 hfq 口径核对，别拿 qfq 直接对表。

### 8.17 改完 Python 源码后，Web UI 直接发任务会生效吗？

- 结论：需要重启后端进程，不能在 Web UI 里只刷新页面。因为 `vibe-trading serve` / `vibe-trading dev` 启动的 FastAPI 后端没有开 `uvicorn reload`（`agent/api_server.py` 的 `uvicorn.run(app, ...)` 未传 reload），已运行进程不会自动加载新代码。
- 重启方式：在运行后端的窗口按 `Ctrl+C` 停掉，再重新执行原来的命令（`vibe-trading serve --port 8899` 或 `vibe-trading dev`），等日志出现 `Application startup complete` 后刷新页面即可。
- 不需要重新 `pip install`：源码版是 `pip install -e .`，新进程启动时直接读取仓库里的最新源码。
- `vibe-trading dev` 的 Vite 热更新只对前端源码生效；Python 后端改动同样要重启整个 `dev` 进程。
- 如果只是跑一次性 CLI（`vibe-trading run -p "..."`），每条命令都是新进程，改动直接生效，不需要先重启。
- 改前端源码后：`vibe-trading dev` 下 Vite 热更新，改完刷新页面即可；`setup + serve` 生产/单端口模式需要重新执行 `vibe-trading setup` 生成新 dist，刷新页面即生效，无需重启后端。

### 8.18 日志出现 `WinError 10054 远程主机强迫关闭了一个现有的连接`？

- 含义：agent 通过 SSE 流式读取 LLM 输出时，连接在流中途被远端/中转强制关闭（ReadError）。不是 key 失效、不是本地配置错误；`TIMEOUT_SECONDS` 调大对这种“中途断连”基本无效，因为报错不是超时。
- 本机实测（2026-08-07）：非流式请求、curl 流式请求、项目 venv 的 raw httpx 流式请求都能收到完整分片，只有 agent 实际跑的 langchain-openai 长流会间歇性 10054，说明是流式长连接不稳定，而不是服务不可用。
- 已修复：`agent/src/agent/loop.py` 在流式第一次失败后仍按原逻辑重试一次；若第二次也失败（确定性 4xx 除外），自动降级为一次非流式 `chat()`，任务照常完成，Web UI 会一次性显示答案。日志会出现 `Provider stream failed twice ... falling back to non-streaming chat` 和 `stream_reset` 事件 `reason=provider_stream_nonstreaming_fallback`。
- 涉及测试：`test_agent_loop_stream_retry.py`（新增双失败降级用例）、`test_agent_loop_terminal_state.py`（stream 与 fallback chat 都失败时仍返回 `provider_stream_error`）；相关 30 个 loop 测试通过。
- 仍想进一步降低触发概率：关闭本机代理（当前系统代理 127.0.0.1:7897）直连测试，或改用 OpenRouter / SiliconFlow 网关；也可以把 `MAX_RETRIES` 保持 5、`TIMEOUT_SECONDS` 保持 120-300。

### 8.19 任务跑 10+ 分钟、烧大量 token，最后前端显示“等待后已停止”？

- 典型过程：agent 生成 `code/signal_engine.py` 后，被回测沙箱 AST 校验打回（如 `Decorators are not allowed`、`Writing files via open(mode='w') ... not allowed`），于是反复“改代码→重跑回测→再改”，一次任务可跑 15+ 轮、烧 90 万+ token；前端则因 `VIBE_TRADING_SSE_TIMEOUT`（默认 90s）内收不到 SSE 事件而显示“等待 X 后已停止”，但后端可能仍在后台跑完。
- 已预防（2026-08-07）：`agent/src/skills/strategy-dev-manager/SKILL.md` 的 SignalEngine Contract 新增 Runner AST safety constraints：禁止一切装饰器、禁止 `open(mode='w'...)`/文件写入、禁止网络/子进程/eval/exec、禁止模块顶层与类体内可执行语句；诊断信息用 `print(...)` 输出即可。生成代码前先对照这份清单，能避免校验打回循环。
- 若仍然出现：改 `<vibe_home>\.env` 把 `VIBE_TRADING_SSE_TIMEOUT` 调大（如 600），重启后端，前端就不会在长任务中途断开等待。
- 策略“0 笔交易”不一定错：可能是入场条件在回测区间从未满足。可用已保存的 `artifacts/ohlcv_*.csv` 直接复算条件统计（触轨次数/突破次数/窗口分布），再决定放宽条件或换标的，不必整段重跑 agent。

### 8.20 怎么让任务跑得更快、更省 token？

- 已内置两项源码优化（2026-08-07）：
  1. `agent/src/skills/strategy-generate/SKILL.md` 与 `strategy-dev-manager/SKILL.md` 都新增 Runner AST safety constraints，并在生成策略后增加本地 AST 预检步骤，让 agent 在跑回测前先自查装饰器/写文件/网络/顶层语句，避免“生成→打回→重写”循环。
  2. 新增环境变量 `AGENT_MAX_ITERATIONS`（默认 50）：WebUI 会话的 AgentLoop 会读取它。建议在 `<vibe_home>\.env` 里设 `AGENT_MAX_ITERATIONS=12`，一般策略任务 8-12 轮足够，能封顶异常长跑并省 token。
- 同时建议设 `VIBE_TRADING_SSE_TIMEOUT=600`，避免前端在中途断开等待；设完重启后端。
- 工作流建议：①把“3 根窗口 / ATR×0.3 / 5% 风险 / 尾盘 14:55”等数字写死在 prompt 里，减少 agent 猜测；②同一只股票反复调参时，先离线跑一次拿到 `artifacts/ohlcv_*.csv`，之后用 local loader（`local:600097.SH`）或直接改已生成代码本地回测，完全不走 LLM；③策略信号数很少时，先看条件频次统计再决定放宽/换标的；④想保留已有 run 的上下文继续改，用 `vibe-trading --continue <run_id> "把窗口改成 5"`（见 4.5），不要从零重开。
- 数据缓存：固定标的 + 固定区间反复调参时，可开 loader 数据缓存 `VIBE_TRADING_DATA_CACHE=1` 复用已下载行情；是否值得开、怎么开、有哪些坑见 8.35。

### 8.21 data-bridge 是什么？怎么配置？

- 概念：data-bridge 是 Vibe-Trading 的“自带数据桥”，源码实现是 `agent/backtest/loaders/local_loader.py`。它让你把自己本地的 CSV / Parquet / DuckDB 行情文件喂给回测，不联网、不依赖东财/腾讯等在线数据源，也不会因为网络问题反复失败。
- WebUI 没有“本地数据”开关，data-bridge 是“配置文件 + 对话里指定”：配置文件放在 `<vibe_home>\data-bridge\config.yaml`，对话里写 `local:600097.SH` 触发。
- 本机当前还没有这个目录和文件（`vibe-trading init` 不会自动生成），需要自己创建。

配置步骤：

```powershell
New-Item -ItemType Directory -Force <vibe_home>\data-bridge
notepad <vibe_home>\data-bridge\config.yaml   # 粘贴 8.22 示例后保存（UTF-8）
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
- 期货代码后缀（2026-08-16 踩坑）：国内期货 symbol 的交易所后缀按引擎约定的缩写写，郑商所必须用 `.ZCE`（如 `FG0000.ZCE`、`RM0000.ZCE`），不要写 `.CZCE`。引擎的市场识别正则只认 `ZCE|DCE|SHFE|INE|CFFEX|GFEX`，写 `.CZCE` 匹配不上会被误判成 A 股引擎：数据能正常加载、回测能跑完，但所有开仓订单被拒——症状是回测 **0 笔交易、无任何报错/警告**（`metrics.csv` 里 `trade_count=0` 但 `rebalance_count>0`）。把 config 和 `config.json` 的 codes 都改成 `.ZCE` 即可；乘数/涨跌停/手续费等随后按品种表自动生效（如 FG=20、RM=10，见 8.41 的心忆期货流程）。

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
2. 本机现成例子：`<vibe_home>\runs\bb_macd_600097_20240403_20250307\artifacts\ohlcv_600097.SH.csv` 共 223 条，日期 2024-04-03 到 2025-03-07，逐日一条，即日线。
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
- 当前默认：`<vibe_home>\runs\<run_id>`（CLI 和 WebUI 都是这里）。
- 早期/其他版本也可能出现在 `<repo_root>\agent\runs\<run_id>`；`run_card.json` 的 `run_dir` 字段会记录本次实际目录。
- 注意：`vibe-trading serve` / `vibe-trading dev` 启动时会自动把旧版 `agent/runs`（及 sessions/uploads）迁移到 `~/.vibe-trading` 下，迁移后 `agent/runs` 目录会被清空移除；已迁移的 run 仍在 run 列表里，只是物理位置变了，无需手动处理。
- 允许的 run roots 由 `VIBE_TRADING_ALLOWED_RUN_ROOTS` 控制，见 8.13。

结构（以一次成功 run 为例）：

```text
<run_id>/
├─ config.json                 回测参数：codes / start_date / end_date / interval / source / initial_cash / 费率 / engine / optimizer / validation / entry_mode / exit_mode / stop_loss_mode（详见 8.34）
├─ req.json                    用户原始 prompt + context（session_id）
├─ state.json                  状态：{"status":"success"} 或失败原因
├─ run_card.json / run_card.md 结果摘要：metrics、data_sources、hash、artifacts 清单
├─ analysis.md                 LLM 生成的策略分析报告（agent 自动写，或 --with-analysis 补生成）
├─ analysis.status.json        分析状态：ok / failed / skipped + generated_by / llm_usage
├─ analysis.prompt.md          发给 LLM 的摘要正文（2026-08-12 起分析时生成，便于审计，见 8.36）
├─ analysis.digest.json        （2026-08-12 起回测成功后落库；前端/后端优先读缓存，artifacts 指纹过期才重建，见 8.36）
├─ analysis_charts/            按需生成的 7 张分析图 PNG（--with-charts 或 MCP action=charts）
├─ llm_usage.json              agent 每轮迭代的 token 统计（input / output / total）
├─ trace.jsonl                 agent 步骤追踪日志（调试用）
├─ code/
│  └─ signal_engine.py          本次策略生成的信号引擎代码
├─ artifacts/
│  ├─ metrics.csv               指标一行：total_return / annual_return / max_drawdown / sharpe / win_rate / trade_count / benchmark_label / benchmark_return 等
│  ├─ trades.csv                每笔交易明细
│  ├─ equity.csv                每日权益曲线
│  ├─ positions.csv             每日持仓
│  ├─ ohlcv_<代码>.csv          回测实际使用的行情（可直接复制给 data-bridge 复用）
│  ├─ rebalance_notes.json/.md  调仓记录
│  ├─ validation.json           蒙特卡洛等稳健性结果（trade_count>=10 自动生成；显式 validation 配置优先）
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
- 分析产物：默认回测不生成 `analysis_charts/` PNG；需要时用 `--with-charts` 或 MCP `backtest(action="charts")` 按需补生成。`analysis.digest.json` 在回测成功后落库，前端/后端优先读缓存，artifacts 指纹变化时自动重建；`analysis.md` / `analysis.status.json` 是 LLM 分析报告（agent 自动写，或 runner 加 `--with-analysis` 补生成），不存在不代表回测失败，见 8.36。
- 分析 prompt：调 LLM 前会把 `render_digest_for_llm()` 的渲染结果写成 `analysis.prompt.md`，并在日志打印 digest sha256、prompt 字符/行数，便于审计 LLM 实际看到的内容；完整 digest 也会落库，指纹一致时直接读缓存。

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
> - 指标区新增 `avg_portfolio_weight`（平均组合仓位）、`max_portfolio_weight`（最大组合仓位）、`max_single_weight`（单票最大目标仓位，新 run 默认 0.4）。旧名 `avg_position_weight` / `max_position_weight` 已于 2026-08-11 弃用：新 run 不再写入这两个字段，旧 run 的指标仍按旧名显示（前端兼容回退）。`positions.csv` 仍是每日目标权重（0=空仓，1=满仓），`risk_xray_avg_invested` 与平均组合仓位同值。
> - 口径说明（`avg_portfolio_weight` vs `max_portfolio_weight`）：两者**都是净敞口**（每日各 code 权重带符号求和，多正空负），区别只在聚合方式——`avg_portfolio_weight` 取**平均**（可为负：多空镜像策略空头日多/空头仓位重时，平均值会是负的，如 -0.49% 表示"平均而言净空 0.49%"，不是仓位大小为负；毛口径的仓位大小看「持仓与风险」tab 图 1）；`max_portfolio_weight` 取**最大正值**（只看多头侧最重的日子，空头侧最重的日子在它里面看不到——空头风险要看去图 2 账户风险度 / 单边口径）。真正的"毛持仓"（`sum|w|`，恒正）和"单边"（按 config `logical_groups` 组内取多空大边）是另两种口径，见 8.45；TA 海龟这类恒同向策略四种口径数值一致。

  ---

> ### 8.28 prompt 有换行，`run -p "..."` 会被 shell 当回车执行怎么办？
> - 把长 prompt 保存为 UTF-8 文本文件（项目里建议放 `<repo_root>\prompts\`，已有一份 `bb_macd_10stocks_2023_2025.txt` 可直接用），然后执行 `vibe-trading run -f prompts\bb_macd_10stocks_2023_2025.txt`（激活 venv 后在项目根目录）。
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
> - 已新增两个提醒机制：① agent 达到迭代上限、或已生成 `config.json`/策略代码却没产出 `run_card.json` 时，状态不再写 success，而是写 warning；② `vibe-trading --check <run_id>` 一键列出 run 的关键产物（req/config/signal_engine/run_card/metrics/trades/logs，以及可选分析产物 analysis.md / analysis_charts/*.png）并给出 REPORT OK / NO REPORT 结论。
> - 本次这类“SUCCESS 无报告”的直接原因：agent 迭代耗尽（最后被 forced_text_only 强制收尾，最后一条消息里是未执行的工具调用文本），它写完 config 和 signal_engine 后还没调用回测工具就结束了。补救：`vibe-trading --continue <id> "不要读 req.json 或 transcript，直接运行 python -m backtest.runner <run_dir> 并生成 run card"`，让它在已有代码基础上只做回测。

> ### 8.32 我不知道 req.json、transcript 是什么，下次怎么自己写 `--continue` 的提示词？
> - `req.json` 是 run 目录里保存你原始 prompt 的请求文件；`transcript_*.jsonl` 是那次 run 的完整对话日志，都存放在 `<vibe_home>\runs\<run_id>\` 和 `sessions\` 下。它们只是内部记录，你正常使用时不需要看懂，更不需要自己操作。
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
> - `analysis.md` / `analysis.status.json`：可选分析产物（见 8.36），不存在时 check 显示 `n/a (optional)`，不代表回测失败。
> - `analysis_charts/*.png`：分析图（净值/回撤/盈亏散点/月度热力图/MAE-MFE 等），多张统一显示为一行并给出 `OK (7)` 或 `warning (x/7)`；缺图只警告，不影响 REPORT OK 判定。

> ### 8.34 run 目录下的 `config.json` 是什么？里面的字段都怎么用？
>
> `config.json` 是回测 runner 实际读取的“参数单”：agent 按你的提示词生成，也可以手动改；`python -m backtest.runner <run_dir>` 读它决定数据源、周期、标的、本金、费率、成交模式等，再加载 `code/signal_engine.py` 跑回测。它不含 API key；改完不会自动生效，需要重跑 runner 或用 `--continue` 续跑。
>
> 常见字段（不写某字段就用默认值；旧配置文件可以保留，但 `exit_mode=stop` 必须按下方迁移规则改成三字段）：
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
> | `slippage_points` | 绝对跳点滑点：买价+n跳、卖价-n跳；配置后优先于 `slippage` 比例 | 无（用 `slippage`） |
> | `entry_mode` | 正常开仓/加仓成交时点：next_open（次日开盘）或 close（信号日收盘） | next_open |
> | `exit_mode` | 正常信号平仓/止盈/减仓成交时点：next_open 或 close；不能写 stop | next_open |
> | `stop_loss_mode` | 引擎保护性止损：none（关闭）或 hard（独立触发、优先平仓） | none |
> | `optimizer` | 权重优化器名（如 risk_parity）；`optimizer_params` 传参数 | 无（不优化） |
> | `constraints` | 组合约束（总仓位、单标的上限等），需配合 optimizer 才生效 | 无 |
> | `validation` | 显式 true 时跑蒙特卡洛；不写时若 trade_count >= 10 也会自动跑（n_simulations 降档：<100→1000，100-299→500，300-999→200，>=1000→100），产出 artifacts/validation.json | 自动（按交易数） |
> | `benchmark` | 基准标的，如 "000300.SH"；写 "auto" 时按代码后缀推断市场并取市场默认基准（A股=000300.SH、美股=SPY、港股=HK.03100、加密=BTC-USDT）；不写或写 null = 等权组合。取不到时一律降级为等权且不中断回测，标签会如实写成 equal-weight(universe)，并把失败原因写入 run_card 的 warnings（详见下方基准逻辑详解） | 无（等权组合） |
> | `extra_fields` | 取数时额外字段（如 vwap / amount） | 无 |
> | `fundamental_fields` / `event_feeds` | 进阶：给回测注入基本面或事件数据 | 无 |
> | `leverage` | 杠杆倍数；A股引擎强制 1，写多少都被覆盖 | 1.0 |
>
> 注意：`_run_card_effective_sources`、`_run_card_warnings` 是 runner 运行后写入的内部字段，不要手动编辑。
> - 滑点优先级：配置 `slippage_points` 时按绝对跳点计算（`price + direction * slippage_points`，rb 1 跳 = 1 点；开多/平空为 +，开空/平多为 -），不配置时回退到 `slippage` 比例滑点。目前由国内期货引擎（ChinaFuturesEngine）读取，其他引擎仍只认 `slippage`。
>
> #### 正常成交与保护性止损模式（重点）
>
> - 正常 `entry_mode/exit_mode` 组合目前只允许 `next_open/next_open` 和 `close/close`；`next_open/close`、`close/next_open` 暂不开放。
> - 四个常用 preset：
>   - `next_open/next_open` = `entry_mode: next_open` + `exit_mode: next_open` + `stop_loss_mode: none`；
>   - `close/close` = `entry_mode: close` + `exit_mode: close` + `stop_loss_mode: none`；
>   - `close/stop` = `entry_mode: close` + `exit_mode: close` + `stop_loss_mode: hard`；
>   - `next_open/stop` = `entry_mode: next_open` + `exit_mode: next_open` + `stop_loss_mode: hard`。
> - `next_open`：正常信号在当前 bar 产生，下一根实际 bar 开盘成交；`close`：正常信号在当前 bar 收盘成交。
> - `stop_loss_mode: hard`：持仓建立后独立维护 active stop，不需要策略先把 target 改成 0；止损优先于正常信号平仓。
> - next-open 入场当根启用 hard stop：若多单开盘价严格低于 stop，或空单开盘价严格高于 stop，取消入场，不产生开仓/止损双边手续费；若开盘没有穿 stop、入场后当根触及 stop，则先入场再按止损规则平仓。
> - hard stop 非跳空触发按止损价成交；只有多单 `open < stop` 或空单 `open > stop` 时才按开盘价成交；期货止损价继续按品种 tick 取整。
> - 旧配置 `exit_mode: stop` 不再支持：runner 会在加载行情前失败并给迁移提示。新配置使用 `exit_mode: close` 或 `next_open`，另加 `stop_loss_mode: hard`。
>
> #### `stop_prices`（策略代码字段，不写在 config.json）
>
> - 止损价由 `signal_engine.py` 自己算：`SignalEngine.generate()` 返回权重的同时，把 `self.stop_prices = {代码: pd.Series(绝对止损价, index=交易日)}` 带上。
> - 只有 `stop_loss_mode="hard"` 时引擎才把它作为独立保护止损读取；普通 `exit_mode` 平仓不会读取止损价。
> - 新 stop 候选默认在下一根 bar 生效；NaN 表示本 bar 不更新，沿用上一个有效 active stop。策略是否放宽止损由策略代码决定，引擎不做 max/min 限制。
> - next-open 以损定量暂不支持：如果 stop 依赖实际 next-open 入场价，当前策略应使用预先可知的绝对 stop；实际成交后按 stop distance 计算手数属于后续迭代。
> - `config.json` 不需要也不能写 `stop_prices`。
>
> #### 基准（benchmark）逻辑详解
>
> `benchmark` 决定“拿什么序列当基准”来计算 `excess_return` / `information_ratio` / `tracking_error` / `benchmark_beta` / `benchmark_return`。配置只有三种写法：
>
> | config.json 写法 | 实际使用的基准 | 标签与字段 |
> | --- | --- | --- |
> | 不写 `benchmark`（或写 `null`） | 等权组合：策略池每日收益等权平均 | `benchmark_label=equal-weight(universe)`；不联网、最快 |
> | `"benchmark": "auto"` | 按首标的代码后缀推断市场，取市场默认基准：A股（.SH/.SZ/.BJ）→ 000300.SH；美股（.US）→ SPY；港股（.HK）→ HK.03100；加密 → BTC-USDT | 取到：`benchmark_label=a_share` 等市场名 + `benchmark_ticker` + `benchmark_return`；取不到：降级为等权，`benchmark_label=equal-weight(universe)` |
> | `"benchmark": "000300.SH"` 等显式代码 | 只取你写的那个标的 | 取到：`benchmark_label=000300.SH` + `benchmark_ticker` + `benchmark_return`；取不到：降级为等权，`benchmark_label=equal-weight(universe)` |
>
> 无论哪种写法，取数失败都不会中断回测，只是基准退回等权组合。`metrics.csv` / run_card 里不会单独记录“请求值”；一旦发生降级，run_card 的 `warnings` 会出现一条 `benchmark fetch failed (requested: ...); fell back to equal-weight(universe)`，同时 `benchmark_label` 会是 `equal-weight(universe)`。两者配合即可判断“请求了自动/指定基准但没取到”。
>
> 判断本次到底用了什么基准，看 run_card.json / artifacts/metrics.csv 的三个字段：
> - `benchmark_label`：实际使用的基准描述；`equal-weight(universe)` = 等权组合，`a_share` 等 = 市场自动推断，具体代码 = 显式基准。
> - `benchmark_ticker`：实际取到的基准代码（如 000300.SH）；降级时不存在。
> - `benchmark_return`：该基准区间总收益；降级时就是等权组合收益，不是任何指数收益。
> - `warnings`（run_card 顶层）：非空且含 `benchmark fetch failed` 就说明这次请求过外部基准但降级成了等权组合。
>
> 想改基准标的：
> - 要等权：删掉 config.json 的 `benchmark` 字段（或写 `null`），重跑 runner。
> - 要自动：写 `"benchmark": "auto"`。
> - 要指定：写具体代码，如 `"benchmark": "000300.SH"`。
> - 改完不会自动生效：`cd agent` 后 `..\.venv\Scripts\python.exe -m backtest.runner "<run_dir>"` 重跑，或让 agent `--continue` 续跑。
>
> 真实 A 股基准 000300.SH 的坑（见 8.26）：免费链路里 yfinance 经常拉不到 A 股指数；最稳做法是 data-bridge 放一条 000300.SH 日线 CSV，source 用 local，config 写 `"benchmark": "000300.SH"`，本地离线取基准。
>
>
### 8.35 loader 数据缓存（`VIBE_TRADING_DATA_CACHE`）要不要开？什么时候开？

结论先说：你现在主要用 WebUI / `vibe-trading run` 发任务，这个缓存帮助不大（原因见下），更推荐直接用 data-bridge；只有当你改用 `python -m backtest.runner <run_dir>` 直接反复调同一批标的 + 固定区间时，才值得开。

- 是什么：回测 loader 的“可选本地行情缓存”。开启后，各数据源（tencent / tushare / akshare / mootdx / eastmoney / yfinance / ccxt / okx / futu / finnhub / tiingo / fmp / baostock / local 等）把“已完全结算的历史 K 线”按 key 存成 parquet；下次同一请求直接读本地，不联网。
- 怎么开：默认在 `~/.vibe-trading/.env` 加 `VIBE_TRADING_DATA_CACHE=1`（`true/yes/on` 也行），默认关闭，不设或写 `0` 即关。默认缓存目录是 `~/.vibe-trading/cache/loaders`；改完后重启 `serve` / `dev` 后端，或新开 CLI / runner 进程。
- 直跑 runner 已支持一次配置（2026-08-22）：`python -m backtest.runner "<run_dir>"` 启动时会复用统一的 `.env` 加载逻辑，因此不再需要每次在命令前手动带 `VIBE_TRADING_DATA_CACHE=1`。默认优先读取 `~/.vibe-trading/.env`，随后才回退到 `agent/.env` / 当前目录 `.env`。
- 自定义运行目录：如果进程启动前设置了 `VIBE_TRADING_HOME`，runner 会优先读取 `<VIBE_TRADING_HOME>/.env`。例如：

  ```powershell
  $env:VIBE_TRADING_HOME = 'E:\vibe-home'
  ..\.venv\Scripts\python.exe -m backtest.runner "<run_dir>"
  ```

  `VIBE_TRADING_HOME` 要在进程启动前设置；不要只把它写进待加载的 `.env` 里期待它反向决定 `.env` 位置。
- 自定义缓存目录：在已经会被加载的 `.env` 中增加 `VIBE_TRADING_DATA_CACHE_ROOT`，例如：

  ```dotenv
  VIBE_TRADING_DATA_CACHE=1
  VIBE_TRADING_DATA_CACHE_ROOT=E:/vibe-cache/loaders
  ```

  该变量只改变 loader parquet 的存放位置，不改变 runs、data-bridge 等其他目录；如果只设置 `VIBE_TRADING_HOME`，缓存默认仍按 `~/.vibe-trading/cache/loaders` 处理。
- 什么时候使用自定义缓存目录：C 盘空间紧张、希望把大批量历史行情缓存放到 E/D 盘、需要把缓存与运行产物分开，或多个实验共用一个稳定缓存目录时使用。若每次标的/区间都不同、已经使用 data-bridge 本地数据，或只是偶尔跑一次回测，则不建议额外设置。
- 这次修复对应计划 `documents/plans/P-20260816-cache_env_once.md`；缓存 key、缓存版本、过期判断和 data-bridge 行为均未改变。
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
- 怎么清：回测没在跑时删除 `<vibe_home>\cache\loaders` 整个目录，或只删对应 `<source>` 子目录即可，程序下次会自动重建。
- 替代方案：需要“确定且可长期复用”的数据，直接用 data-bridge（8.21）：把 `artifacts/ohlcv_*.csv` 复制到 data-bridge 目录，对话里用 `local:<symbol>` 回测，比缓存更透明、可控、可跨项目复用。

### 8.36 回测分析报告（analysis.md）和 7 张分析图是什么？

- 默认回测成功后不会生成 `analysis_charts/*.png`；需要图片时显式加 `--with-charts`，或对已完成 run 调用 MCP `backtest(action="charts")`。生成的是 7 张图：净值曲线、回撤瀑布、单笔盈亏散点、月度损益热力图、盈亏 vs 持仓时长、MAE/MFE、持仓分桶；不烧 LLM token，单张图失败不阻塞回测。
- 每次回测成功后，runner 会生成 `analysis.digest.json`（2026-08-12 起恢复落库，解决大 run 分析图加载慢）：digest 由回测现场构建并持久化；前端/后端读取时先校验 artifacts 指纹（config/run_card/metrics/trades/equity/positions/validation/risk_xray/OHLCV 统计），一致则直接用缓存，不一致才重建。2026-08-18（V034）起指纹源新增 `positions.csv`；对**旧 run**（此前生成的 digest）读取时会做**增量兼容**——只缺 positions.csv 指纹时仅补算每日持仓/风险序列（约 0.15s），保留原 digest 的 regime/MAE-MFE 等字段，不会触发全量重建（10 年 4H 全量重建约 11s，已避免）。里面包含：全量指标按“性能 / 基准相对 / 风险 / 仓位与换手 / 再平衡 / 其他”分组、逐日权益与基准序列（`equity` 每行含 `benchmark_cum_return_pct` / `benchmark_drawdown_pct`）、`validation`（蒙特卡洛）、交易明细、月度损益、持仓分桶、每日持仓与风险序列（`daily_position` 每日组合持仓、收盘口径，毛/净/单边；`daily_risk` 每天账户风险度、峰值口径）、MAE/MFE 摘要、Regime 摘要（至少 2 个标的时：FUSED 时间占比 / episodes / 按入场日归因的交易盈亏）等。benchmark 未配置时统一记 `equal-weight(universe)`；`benchmark: "auto"` 按 `.SH/.SZ/.BJ` 后缀识别为 a_share 并尝试取市场默认基准（A股=000300.SH），失败时降级为等权基准，并在 run_card warnings 记录 `benchmark fetch failed`。
- **持仓与风险数据的分层（V034-V036，口径详见 8.45）**：
  - digest 只存**组合级**：`daily_position`（图 1 每日组合持仓，收盘口径）+ `daily_risk`（图 2 每天账户风险度，峰值口径）+ `position_risk_summary`（LLM 派生摘要：收盘毛持仓/风险度的最大、平均、超 50/80/100% 天数与占比、风险度最高日期——**LLM 只拿摘要，不含全量日序列**）；
  - **单标的**逐标的序列**不进 digest**（100 标的 × 2400 天 ≈ 14MB，会拖垮 digest 及所有消费方）——图 3「单标的每日持仓」按需调 API：`/runs/{id}/analysis/positions/groups` 取标的列表（含各标的峰值仓位标注）、`/runs/{id}/analysis/positions/{group}` 取单标的收盘/峰值序列，后端现读 positions.csv 返回（单标的 ~140KB/次）；
  - 消费方：WebUI「持仓与风险」图 1/图 2 与 LLM 报告从 digest 取数（优先缓存，保证口径一致）；图 3 走上面的按需 API。
- LLM 分析报告 `analysis.md` 是可选产物，由两条路径生成，行为一致（同一份 digest 同一套 prompt）：
  1. agent 路径：回测成功后 agent 自动调用 `write_run_analysis` 工具写 `analysis.md` + `analysis.status.json`，最终回复只引用文件路径，不再重复长篇归因（省 token）。
  2. runner 路径：在 `agent` 目录下执行 `..\.venv\Scripts\python.exe -m backtest.runner "<vibe_home>\runs\<run_id>" --with-analysis`（也支持 `--withAnalysis`），回测成功后会补生成同一份分析（会调用一次 LLM；`VIBE_TRADING_ANALYSIS_TIMEOUT` 可调超时，默认 120 秒）。
- 分析 prompt 结构：一句话结论 → 结论详解 → 指标解读（全量、分组、逐项，每个指标至少一句解读）→ 交易行为诊断（交易概览、持仓分桶、月度损益、MAE/MFE）→ 交易环境分析（Beta 回归、Regime 分析）→ 稳健性验证（蒙特卡洛）→ 风险与改进建议，目标字数 1000-2500 字；全篇列表逐条分行（建议用 Markdown 有序列表），不挤在同一段落。
- 指标解读表格为“指标 | 含义 | 值”三列：含义由代码确定性生成（`METRIC_MEANINGS`，未知字段显示“自定义/派生指标，按字段名理解”），LLM 只解读、不得改写含义。
- `analysis.status.json` 记录 `status`（ok / failed / skipped）、`generated_by`（agent / runner）、`generated_at`、`llm_usage`（provider 上报时的真实 token 用量）。LLM 失败只把 status 记为 failed，不会让回测失败。
- 审计留痕：调 LLM 前会把 `render_digest_for_llm()` 的渲染结果写成 `analysis.prompt.md`（只含发给 LLM 的摘要正文，不含 system prompt），并在日志打印 digest sha256、prompt 字符/行数，便于确认 LLM 实际看到的内容；完整 digest 也会落库（指纹一致时直接读缓存）。
- WebUI 的“分析图”标签调用 `/runs/{id}/analysis/charts` 时优先读 `analysis.digest.json` 缓存再算 ECharts 数据，PNG 只是兜底图片；图表 payload 本身不单独落库。

### 8.37 直接跑 runner 报 `PermissionError: ... artifacts\trades.csv`？

- 原因：这个 CSV 正被 WPS 表格 / Excel 等程序打开，Windows 下文件被占用时无法覆盖写入；不是代码 bug，也不是路径问题。
- 解决：先关掉打开 `trades.csv` 的 WPS / Excel 窗口（或退出 WPS），再重跑 `..\.venv\Scripts\python.exe -m backtest.runner "<vibe_home>\runs\<run_id>" --with-analysis`。
- 只想补生成 `analysis.md`、不重跑回测时：`..\.venv\Scripts\python.exe -c "from backtest.analysis.report import generate_analysis_report; print(generate_analysis_report(r'<vibe_home>\runs\<run_id>', generated_by='runner'))"`（需要 `run_card.json` 和 `artifacts/metrics.csv` 已存在；不写 trades.csv，仍会调用一次 LLM）。
- 为什么这条命令不用跑回测：`generate_analysis_report` 与回测引擎无关，只检查 `run_card.json` + `artifacts/metrics.csv` 是否存在，然后读取/构建 digest（优先读 `analysis.digest.json` 缓存，指纹过期才重建）→ 拼 prompt → 调一次 LLM → 写 `analysis.md` + `analysis.status.json`；不写 trades.csv，也不启动 loader/engine。`--with-analysis` 会重跑回测并补 digest，再调用同一个报告函数；它不会自动生成 PNG，图片需要额外加 `--with-charts`。
- 注意：单独跑 `generate_analysis_report` 不会生成 `analysis_charts/*.png`。如果只想补 PNG 而不重跑回测：`..\.venv\Scripts\python.exe -c "from backtest.analysis.charts import generate_chart_artifacts; import json; print(json.dumps(generate_chart_artifacts(r'<vibe_home>\runs\<run_id>'), ensure_ascii=False))"`。WebUI 的“分析图”标签从 API 读缓存 digest 后现算 ECharts 数据，PNG 只是兜底，缺少 PNG 不影响图表显示。MCP `action="charts"` 和 `action="report"` 也都是这种只对已完成 run 做后处理的路径。
- 注意：重跑 runner 会覆盖 `artifacts/` 下全部文件，查看前最好先关掉相关编辑器。

### 8.38 已有策略想调参 / 微调，怎么探索最高效？

核心原则：**参数探索不走 LLM**。回测本身是本地确定性代码，一次直接跑 runner 只要几秒、0 token；LLM 只用在“生成策略 / 写分析报告”这两步。

1. 基线 run 准备：先正常跑一次，确认 run 目录里有 `code/signal_engine.py`、`config.json`、`artifacts/ohlcv_*.csv`。
2. 数据固化（只做一次，二选一）：
   - data-bridge（推荐）：把 `artifacts/ohlcv_*.csv` 拷到 `<vibe_home>\data-bridge\`，配好 `config.yaml`，之后用 `local:<symbol>`，完全离线。
   - loader 缓存：`VIBE_TRADING_DATA_CACHE=1`，同一数据源 + 标的 + 周期 + 区间会命中缓存（坑见 8.35）。
3. 一个变体 = 一个 run 目录副本：`Copy-Item "<vibe_home>\runs\<run_id>" "<vibe_home>\runs\exp_<名字>" -Recurse`；修改参数（具体见4）-改副本里的 `config.json`（参数）和/或 `code/signal_engine.py`（逻辑），然后 `cd agent` 跑 `..\.venv\Scripts\python.exe -m backtest.runner "<副本目录>"`。**不要直接改原 run 目录重跑**，会覆盖原 artifacts / run_card / analysis，也没法横向对比。
4. 参数修改细节（依规模）：见下方“规模分档 / 参数改法”要点。
5. 最后才烧 LLM：挑出 2-3 个候选后，再 `python -m backtest.runner "<候选目录>" --with-analysis` 补分析报告，或 `vibe-trading --continue <run_id> "..."` 继续精调。

常见坑：改 `config.json` / `signal_engine.py` 后必须重跑 runner 才生效；`local:` 是 codes 前缀（`local:600097.SH`），不要写 `source: local`；runner 要在 `agent` 目录下跑；trades.csv 被 Excel/WPS 占用时会 PermissionError（8.37）。
调参产物清理：每次回测都会在副本里生成完整 `artifacts/`（含行情快照 `ohlcv_*.csv`、equity、trades、metrics、validation 等）；7 张 `analysis_charts/*.png` 默认不再生成（见下“回测提速”，需要时加 `--with-charts`）。即使数据来自本地 data-bridge，`ohlcv_*.csv` 也会把内存里的行情快照再落一份到每个副本，10 标的 × 10 组约 3MB。批量调参后建议手动清理：删除 `exp_*/analysis_charts` 和 `exp_*/artifacts/ohlcv_*.csv`，保留 `metrics.csv` / `trades.csv` / `equity.csv` 等；删除行情快照后，digest 的 ohlcv 概览、MAE/MFE、regime 会缺失，回测指标和 run card 不受影响。另外 `VIBE_TRADING_DATA_CACHE=1` 时 local 数据还会在 `<vibe_home>\cache\loaders\local` 落 parquet，不需要可去掉该环境变量。

规模分档：1-5 组手动复制 + 改 `code/signal_engine.py` + 跑即可；6-20 组写简单循环脚本；几十上百组用网格脚本（复制模板目录 → 改参数 → 跑 runner → 汇总 metrics）。
参数改法二选一：
- 参数是顶部常量：脚本直接对副本 `code/signal_engine.py` 文本替换（如 `FAST = 20` → `FAST = 25`），不用改策略逻辑。
- 参数分散 / 组合多：在 `SignalEngine.__init__` 里从 `config.json` 的 `strategy_params` 读，脚本只改 config；沙箱禁顶层可执行语句、禁写文件，动态路径读取用 `Path.read_text()`。
筛选核心指标（先筛候选再详细对比）：
- 硬过滤：trade_count 至少 10-20、max_drawdown 可接受、风控字段合规、换手可执行、蒙特卡洛 p 值不能太差。
- 综合排序：calmar / sharpe / sortino / profit_factor；相邻参数结果平滑才算稳（尖峰多半是过拟合）。
- 最后只对 top 3-5 个跑 --with-analysis 详细对比。

回测提速（2026-08-16 起）：大区间反复调参时，两件事把一次回测从 10 分钟压到 10 秒——
- **默认跳过 PNG 图表**：runner 默认不再生成 7 张 `analysis_charts/*.png`（WebUI 分析图读 `analysis.digest.json` 算 ECharts，PNG 只是兜底图片），需要时加 `--with-charts`。3 年 15m 回测里 7 张 PNG 约 557 秒，占全程 93%，是唯一瓶颈。
- **loader 缓存**：`VIBE_TRADING_DATA_CACHE=1`（8.35）缓存同一 数据源 + 标的 + 周期 + 区间 的行情，命中后数据加载仅 0.6 秒。
- **`--fastrun` 跳过 digest 慢分析（2026-08-17 起）**：3 年 5m 场景下回测后 digest 的 regime（相关性）与 MAE/MFE 分析是新的耗时大头（约 750s，占 98%）。加 `--fastrun` 跳过这两项（等价 `--without-regime --without-mae-mfe`，以后新增耗时步骤也会并入 fastrun 跳表）；digest 不再含 regime / mae_mfe 字段，WebUI 分析图里 MAE/MFE 卡片显示"未计算"占位、LLM 报告不含这两段。注意：fastrun 重跑会**覆盖**该 run 已有 digest 为精简版，MAE/MFE 图与报告 Regime 段随之降级，完整重跑可恢复；digest 文件缺失或 artifacts 变化时 WebUI 会按完整版重建（该场景不加速）。
- 实测耗时分布（3 年 15m、缓存命中、含本地 1m 数据）：完整跑 596s → 默认跑约 11s。

  | 阶段 | 耗时 | 说明 |
  |---|---|---|
  | 数据加载 + 聚合（缓存命中） | 0.6s | 46 万根 1m → 1.7 万根 15m |
  | 策略 generate() 信号扫描 | 0.3s | 全量信号 + 过滤条件 |
  | 引擎 run_backtest | ~3s | 其中逐 bar 执行约 2s；写 trades.csv / metrics / run_card 合计 <0.6s，不是耗时项 |
  | digest 生成 | ~5s | WebUI 分析图数据源，不可省 |
  | 7 张 PNG（仅 `--with-charts`） | ~557s | matplotlib 渲染，WebUI 兜底图片 |

  结论：反复调参请用 `python -m backtest.runner "<副本>"`（不带 `--with-charts`），大区间小周期再叠 `--fastrun`，配合缓存即可秒级出指标；PNG 只在需要贴图/报告时用 `--with-charts` 补生成。

### 8.39 策略不变，怎么换一批标的 / 换数据源快速重跑？

核心原则：换标的、换数据源、换日期都只是“数据层”变化，`code/signal_engine.py` 一行都不用改；不要重新发 agent 任务，直接建 run 副本、改 `config.json`、跑 runner，几秒出结果、0 token。

1. 建新 run 目录（推荐只带 `code` + `config.json`，不复制旧 artifacts）：
   - `Copy-Item "<原run>\code" "<新run>\code" -Recurse`，再新建 `<新run>\config.json`。
   - 也可以直接复制整个原 run，runner 会覆盖 `artifacts/`，但旧 `analysis_charts/` 会残留，跑完手动清理。
2. 改 `config.json` 三个字段即可，其余字段（佣金、滑点、入场/离场模式、initial_cash）照抄原 config：
   - `codes`：换成新一批标的，A 股必须带交易所后缀，如 `"002133.SZ"`、`"600117.SH"`。
   - `start_date` / `end_date`：改成目标回测区间。
   - `source`：`tencent` / `eastmoney` 走联网，`local` 走 data-bridge（见 8.16）。
3. 跑 runner（不加 `--with-analysis` 就不烧 LLM）：

   ```powershell
   $env:VIBE_TRADING_ALLOWED_RUN_ROOTS='<vibe_home>\runs'
   cd <repo_root>\agent
   ..\.venv\Scripts\python.exe -X utf8 -m backtest.runner "<新run目录>"
   ```

4. 验证数据真的换过来了：看 `artifacts/ohlcv_*.csv` 的代码、行数、首末日期；看 `run_card.json` 的 `data_sources` 和 `warnings`；最终指标看 `artifacts/metrics.csv`。

数据源选择：
- 新标的本地没有数据：最快是 `source: tencent` 直接跑一次；跑完把 `artifacts/ohlcv_*.csv` 拷到 `data-bridge` 并登记 `config.yaml`，之后同区间可改 `local` 完全离线重跑。
- 新标的已有 CSV：直接配 data-bridge 后 `source: "local"` + `codes: ["local:002133.SZ", ...]`，完全不联网。
- local 缺标的会 fail closed，不会自动联网补齐；目前没有“本地为主、缺的联网拉”这个开关，需要先把缺的标的补成 CSV。
- 反复跑同一批标的 + 固定区间可以开 `VIBE_TRADING_DATA_CACHE=1` 命中 loader 缓存（8.35），但缓存不等于离线数据，最稳还是 data-bridge。

### 8.40 股价复权：项目现在只有前复权，怎么跑后复权？

现状（2026-08-12 实测）：
- 腾讯 loader（`agent/backtest/loaders/tencent_loader.py`）请求行情接口时固定传 `qfq`，只返回前复权。
- 东财 loader（`agent/backtest/loaders/eastmoney_loader.py`）固定 `fqt=1`，同样是前复权。
- local loader（`agent/backtest/loaders/local_loader.py`）不做任何复权处理，CSV 文件是什么口径，回测就用什么口径。
- 结论：在线数据源目前没有“后复权开关”，要后复权只能改代码或喂本地文件。

为什么要注意：前/后复权不是简单常数缩放，同一起止日期的涨跌幅可能明显不同。实测 `002133.SZ` 2021-12-31 → 2024-12-31：qfq 收盘 2.911 → 2.501（-14.08%），hfq 收盘 10.32 → 9.336（-9.53%）。用户表格若写“后复权”，不能直接拿 qfq 数据核对。

后复权两条路：
1. 改 loader 源码（影响在线回测，需要测试）：
   - 腾讯：给 `tencent_loader.py` 增加 `adjust` 配置，请求参数由 `qfq` 改成 `hfq`；腾讯返回的 key 是 `hfqday`。
   - 东财：给 `eastmoney_loader.py` 增加配置，`fqt=1`（前复权）改成 `fqt=2`（后复权）。
   - 建议默认仍走 qfq，把后复权做成可选参数并补回归测试，避免旧 run 结果口径被破坏。
2. 不改代码，用 data-bridge 喂后复权 CSV（最快落地）：
   - 用腾讯接口拉 `hfq` 或东财 `fqt=2` 的日线，保存成和 `artifacts/ohlcv_*.csv` 同结构的 CSV（`trade_date, open, high, low, close, volume`）。
   - 登记到 `<vibe_home>\data-bridge\config.yaml`，回测里写 `local:<symbol>`。
   - local loader 只按文件原样读取，所以文件是 hfq，跑出来就是后复权口径。

注意：同一份策略用 qfq 和 hfq 的结果不可直接对比；切换口径后要重新评估参数和信号阈值。


### 8.41 心忆 .min 数据做国内期货多周期回测，怎么组织数据最省事？

- 结论：只保留一份 1m 主数据即可，不需要每个周期存一份。local loader 会按请求 `interval` 现场把 1m 聚合为 5m/15m/30m/1H 等，`code/signal_engine.py` 和回测引擎都不用改。
- 实测（2026-08-13，rb 最近 10 个交易日）：同一份心忆 1m，local loader 现场聚合 5m 与 xinyi-kline skill 直接生成 5m 完全一致（690/690 根，OHLCV 全字段 0 差异）；用 `source: local` + `codes: ["local:rb0000.SHFE"]` + `interval: "5m"` 直接跑 runner 成功，走 ChinaFuturesEngine。
- 推荐工作流：
  1. 用 xinyi-kline skill 把每个品种/合约变体解析成 1m CSV，主连用默认 main-only + `--cache-dir`；具体合约用 `--all-contracts` 再筛。
  2. 注册进 `<vibe_home>\data-bridge\config.yaml`，`columns.date: datetime`、`date_format: "%Y-%m-%d %H:%M:%S"`。
  3. 主连 symbol 建议写成引擎能识别的形式，如 `rb0000.SHFE`；具体合约写 `rb2510.SHFE`，这样 ChinaFuturesEngine 能正确取乘数和保证金。
  4. 换周期 = 改 config 的 `interval`；换品种/换主连 vs 具体合约 = 改 `codes`，策略代码不动。
- 三个必须注意的边界：
  1. 夜盘按自然日过滤：`start_date` 要写成目标首个交易日前一天（含夜盘），否则首个交易日 21:00 夜盘会被丢掉；回测区间末端如果数据里还有次日文件，会把目标区间后一夜盘也带进来，生成 1m 文件时最好按精确区间切。
  2. 指标没有自动预热：策略用了 20/60 根均线等，文件应包含预热段，或策略代码自己跳过前 N 根。
  3. 不要用 1m 文件 + `interval: 1D` 跑日线：local 按自然日聚合会把夜盘分到前一天，日线直接用 skill `--period daily` 生成。
- open_oi 不会传给 SignalEngine，主连选择在解析时完成即可。

### 8.42 回测引擎支持哪些 K 线周期？想跑 20m / 2H 等没列出的周期怎么办？

- 引擎目前**只支持 7 个固定周期**（`agent/backtest/runner.py` 的 `_VALID_INTERVALS`）：`1m` / `5m` / `15m` / `30m` / `1H` / `4H` / `1D`。
- **大小写敏感**：小时/日必须写大写（`1H` / `4H` / `1D`），写 `1h` / `4h` / `1d` 会被校验直接拒绝（`unsupported interval` 报错），不是自动兼容。分钟周期写小写（`15m` 等）。
- 校验发生在 `config.json` 解析阶段（runner 的 pydantic validator），不支持的周期**直接报错、不会降级**。
- 想在回测里用 `20m`、`2H` 等未列出的周期：需要改引擎侧代码，共三处——
  1. `agent/backtest/runner.py` 的 `_VALID_INTERVALS` 集合加对应周期（如 `"20m"`）——这是"能不能跑"的闸门，不加必报错；
  2. `agent/backtest/loaders/local_loader.py` 的 `_RESAMPLE_RULES` 加映射（如 `"20m": "20min"`）——local 数据是按目标周期从 1m 现场聚合的，不加就只会警告并原样返回源 bar，等于没聚合；
  3. `agent/backtest/metrics.py` 的 `_BARS_PER_DAY` 年化表和 `_normalize_interval` 加对应映射——不加的话年化收益/夏普等按默认 1 bar/天折算，**指标失真**（回测执行和交易不受影响）。
  前两处决定"能不能跑"，第三处决定"年化指标准不准"。
- 前端 K 线图上的周期按钮（5m/15m/20m/1h/2h/4h/1D/1W/1M/1Y）是**前端本地聚合展示**，与回测 `interval` 无关——页面能切 20m 不代表回测能跑 20m；4h 与 1D 同级，基础回测周期不大于 4H 时显示，1D 基础回测仍只显示 1D 及以上，4H run 选择 4h 时直接展示原始 4H bar。

### 8.43 加仓怎么算成"单标的"持仓？（config.logical_groups 分组）

- **背景**：一个标的的金字塔加仓如果拆成多个 code（伪单位）表达（如 TA 策略的 TA0001-0004.ZCE 共享同一主连行情），引擎默认**按单 code**算"单票仓位"：`max_single_weight` 只是 4 个单位里权重最大的那一个 code（如 4.88%），而 `max_portfolio_weight` 是 4 个单位权重之和（如 14.18%）。两者不矛盾，只是口径不同——单票没算上"加仓的其它单位"。
- **现在的配置方式**：在 run 目录的 `config.json` 里声明 `logical_groups` 数组。策略代码不再写 `weight_groups`，分组唯一来源是 config：

  ```json
  {
    "codes": [
      "local:TA0001.ZCE", "local:TA0002.ZCE",
      "local:TA0003.ZCE", "local:TA0004.ZCE",
      "local:RB0001.ZCE"
    ],
    "logical_groups": [
      {
        "logical_symbol": "TA_MAIN",
        "display_name": "TA主连",
        "codes": [
          "local:TA0001.ZCE", "local:TA0002.ZCE",
          "local:TA0003.ZCE", "local:TA0004.ZCE"
        ],
        "chart_code": "local:TA0001.ZCE"
      },
      {
        "logical_symbol": "RB_MAIN",
        "display_name": "RB主连",
        "codes": ["local:RB0001.ZCE"]
      }
    ]
  }
  ```

  声明后 `max_single_weight` = 组内所有 code 权重之和的峰值（带符号求和）。4 个伪单位同向加仓时，`max_single_weight` 会自然等于 `max_portfolio_weight`（14.18%）。
- **注意**：
  1. `logical_groups` 必须是数组，适用于单标的加仓，也适用于同一策略同时回测 TA、RB 等多个标的；
  2. 每个 group 的 `codes` 必须来自顶层 `codes`；一个执行 code 不能同时属于多个 group；错误配置会直接 fail closed；
  3. `chart_code` 是该逻辑标的的代表行情代码，省略时默认使用该组第一个 code；组内其他 code 的交易标记会映射到代表图；
  4. 顶层 `codes` 中未加入任何 group 的 code 自动按单 code 逻辑标的处理；没有 `logical_groups` 的旧 config 也保持这个兼容行为；
  5. `max_single_weight`、持仓与风险 tab、行情 K 线选择器都使用同一份 config 分组；`positions.csv` 仍保留执行 code 明细；
  6. 该配置只影响新跑或重新生成分析产物的 run，旧 run 文件不会自动改变。

### 8.44 同一标的同时持有多、空两个方向，仓位怎么算？

- **引擎口径**：仓位权重（`max_portfolio_weight` / `max_single_weight`）都是**带符号求和（净敞口）**——多单为正、空单为负，同标的同组内多空会互相抵消。
- **和真实期货结算一致**：国内商品期货（含郑商所 TA）对**同一合约**的多空对锁持仓，结算时保证金按**单边**收取——等量多空时按一边算，不重复占用保证金。所以引擎里"多空对冲后净敞口≈0 → 单票仓位显示≈0"，对应现实里"锁仓不额外占用保证金、价格波动多空盈亏互相抵消"，是符合实际的。
- **但锁仓 ≠ 平仓**：多空两条持仓都还挂账（持仓量/额度占用都在），只是结算保证金按净额算；锁仓要付两次开仓手续费，且极端行情（涨跌停无法平仓、交易所临时上调保证金）下仍有流动性/强平风险。
- **容易误会的点**：单票（组内净敞口）可能**大于**组合净敞口——比如组合里两个标的一多一空相抵，但其中某个标的多头没被对冲，此时单票仓位显示 5%、组合仓位显示 0%，两个口径不要混着比。
- 实际影响：TA 海龟策略 4 个单位恒同向（全多或全空），永远不会出现同标的多空并存；本条适用于将来可能出现双向持仓的策略。

### 8.45 WebUI「持仓与风险」tab 的三张图是怎么算的？（每日组合持仓 / 每天账户风险度 / 单标的每日持仓）

- 位置：报告页「分析图」右边、「分析」左边的「持仓与风险」tab，含三张图。数据源都是 `artifacts/positions.csv`（引擎每 bar 每个 code 的目标权重）+ `artifacts/equity.csv`（每 bar 总权益）。
- **图 1「每日组合持仓」（取收盘值计算）**：三条线可叠加，默认只显示**毛持仓**（点图例可切换显示净持仓 / 单边最大持仓）；三条线都取**每个交易日收盘时**（最后一根日盘 bar，夜盘 bar 归下一交易日、不参与当日收盘）的持仓——是同一时刻的快照，可直接对比：
  - **毛持仓** = 所有 code 权重绝对值之和（`sum|w|`），恒为正，表示总仓位占用量（资金利用率）；
  - **净持仓** = 带符号求和（`sum w`），正=净多、负=净空，表示对市场的净风险暴露（**注意：净线只表示方向，判断资金占用必须看毛线**——多空混合时净可能很小甚至为负，但总占用可能很大）；
  - **单边最大持仓** = 按 config `logical_groups` 分组，组内取"多头和 / |空头和| 的大边"再跨组合计，等于真实期货"同一合约对锁按单边收保证金"的口径。
  - 三者的区别：同一标的多空各 20% 时——毛 40%（总占用量）、净 0%（风险对冲）、单边 20%（真实保证金占用）。恒同向的策略（如 TA 海龟）三者完全相等。
- **图 2「每天账户风险度」**：**单边口径**（= 单边最大持仓 ÷ 权益，百分比），**取每天峰值**（含夜盘），对应真实期货"风险度 = 占用保证金 ÷ 客户权益"；行业规则：风险度 > 100% 追保、100%~120% 强平（各期货公司风控线不同），图内画了 100% 强平参考虚线，超过 100% 的点标红。**职责分工：图 2 看"最重时刻的风险"，图 1 看"每天收盘的日常状态"**——盘中最重但收盘前减掉的日子，图 1 显示收盘状态、图 2 显示盘中峰值。
 - **图 3「单标的每日持仓」**：下拉框选择 config `logical_groups` 定义的逻辑标的（伪单位如 TA0001-0004 合并为 TA主连；未分组 code 按单 code 一组），选项上标注该标的的**峰值仓位**（如 `TA主连（峰值 41%）`）方便挑选；选中后显示该标的每日**毛 / 净 / 单边**三线，默认**收盘**（与图 1 同口径），可切换**峰值**（单边日峰值，与图 2 同口径）。数据按需加载（API 现读 positions.csv，单标的 ~140KB/次，不占 digest）。
- **多标的是怎么看持仓与风险**（同一账户同时交易多个标的，如某天 RB 多 + TA 空 + FG 多）：
  - **看资金利用率 / 总占用 → 毛持仓线**（多空都算：RB 10% + TA 8% + FG 12% = 30%）；多标的下**单边 = 毛**（不同标的多空不互抵，只有同一标的内锁仓时两者才不同）；
  - **看市场风险净暴露 → 净持仓线**（10% − 8% + 12% = 14% 净多）；净线可正可负，只表示多空相抵后的方向，**不代表仓位大小**；
  - **看最危险时刻 → 图 2 风险度**（日峰值，多空都算）；
  - **看哪个标的贡献最大 → 图 3 单标的每日持仓**（下拉框选标的，选项标注峰值，一眼看到最重的）；
  - 图 1/图 3 的收盘三线是同刻快照、图 2 的峰值可能来自当天不同 bar——不要把"收盘的毛"和"峰值的风险"当成同一时刻的全景。
- **必须知道的模型口径差异**：
  1. 引擎保证金按**开仓价**固定计算，真实期货按**每日结算价**逐日盯市——引擎的风险度曲线比真实略平滑，但主趋势（浮亏侵蚀权益 → 风险度被动上升）一致；
  2. 引擎**执行模型**按每个 code 独立全额占用保证金（多空都扣可用资金），比真实期货"对锁单边收取"保守——这只影响回测的资金约束，不影响展示指标；
  3. 由于引擎是"目标权重"模型，这些图反映的是**策略目标仓位水平**（每天设定的权重），不是逐笔成交后的真实持仓明细——对以损定量、权重即保证金占比的策略（如 TA 海龟）与真实口径一致。
- LLM 报告里只给**派生摘要**（收盘毛持仓 / 风险度的最大、平均、超 50%/80%/100% 的天数与占比、风险度最高日期），不给全量日序列（防 token 爆炸）；完整日序列在 digest（`daily_position` 收盘值 / `daily_risk` 峰值）供图表使用。
- **可迭代点（已记录）**：单标的逐标的持仓已实现（图 3，下拉框按需加载，V036）；后续可迭代：多标的叠加对比模式（不选下拉框时叠加显示各标的毛持仓线；3-4 标的可行，100 标的需降采样）。

### 8.46 WebUI 交易 Tab 如何查看全量交易？

- 默认进入交易 Tab 时使用后端 `trade_log` 预览，表格首屏显示 100 笔，统计基于当前预览数据（后端预览最多 500 笔），不是只统计首屏 100 笔。
- 点击统计行中“总盈亏”右侧的“加载全部交易”后，`全部`、`多开`、`空开`、`多平`、`空平`以及标的筛选都会切换到 `trades.csv` 全量；总笔数、四类计数、总盈亏和下载 CSV 同步使用全量数据。按钮不会消失，而是保留并置灰，显示“已加载全部 N 笔”；统计文字较长时会自动换行，避免覆盖右侧分类按钮。按钮默认是中性可点击样式，不表示已经加载。
- 同一 run 内切换分类、逻辑标的、行情图表标的或其他报告 tab，不会重新请求交易数据，也不会丢失“已加载全部”状态；刷新页面或离开后重新进入另一个 run 会重新加载。
- 交易标的筛选使用 `config.json` 的 `logical_groups`：TA0001~TA0004 等同一逻辑标的的执行 code 会合并统计，交易表仍保留实际执行 code；没有分组配置的旧 run 按单 code 展示。
- 全量模式使用窗口化表格，所有交易仍可连续滚动访问，但不会一次性把数千/上万行全部创建成 DOM。当前首次响应本身仍会携带全量交易；如果未来需要减少首次网络 payload，需另做后端按需加载。

### 8.47 小周期回测分析口径（2026-08-14 起）

- `config.json` 可新增 `backtest_start` / `backtest_end`：`start_date` / `end_date` 只负责数据加载与指标预热，回测执行、净值、回撤、metrics 从 `backtest_start` 开始，到 `backtest_end`（纯日期包含整天）结束。不配置时行为不变。
- `trades.csv` 的 `timestamp`：日内 run 显示完整 `YYYY-MM-DD HH:MM:SS`，日线 run 只显示 `YYYY-MM-DD`；新增 `holding_bars` 列，WebUI 交易表同步显示。
- 指标口径：`avg_holding_bars` 是平均持仓 bar 数；`avg_holding_days` 是按每交易日 bar 数换算的天数，两个值以引擎 metrics 为准。
- 行情 K 线左上角是周期按钮（5m/15m/20m/1h/2h/4h/1D/1W/1M/1Y，按基础周期动态显示），切换由前端聚合；4h 与 1D 同级，基础周期不大于 4H 时出现，4H 基础周期默认选中并直接展示原始 4H bar，较小基础周期选择 4h 时按自然时间前端聚合，1D 基础回测仍只显示 1D 及以上；1D/1W/1M/1Y 按 `trade_date` 分桶，期货夜盘归下一交易日。周期切换后只显示前端重算指标，后端 indicator_series 隐藏。
- 分析图：热力图支持日/周/月切换（默认按回测长度自动选）；净值/回撤从回测窗口开始；盈亏 vs 持仓、持仓分桶改用 bar 数。
- 旧 run 的 `analysis.digest.json` 是缓存，升级后需要重建（schema v3）才会显示新口径；重建方式是重新跑 `backtest.runner` 或删除该文件后刷新 WebUI。
- 1m 行情显示暂未开放：单标的约 8.5 万根会拖垮前端；后续按“区间/数量切片接口 + 懒加载”方案再补。

## 9. 脚本速查

`agent/scripts/` 下的数据抓取脚本用于把行情落库到本地，供离线回测复用；具体使用见 [`agent/scripts/README.md`](agent/scripts/README.md)。

| 脚本 | 功能 |
|---|---|
| `lib/fetch_kline.py` | 按标的、日期区间、数据源抓取日 K（复用 Vibe-Trading 数据层），落盘为 parquet/csv；支持 `--append` 增量补头尾缺口 |
| `lib/get_csi300_constituents.py` | 获取指数历史成分股（baostock 主源 + akshare 兜底），生成无幸存者偏差的 membership 长表；支持 `--index` 切换沪深300/中证500/上证50 |
| `run/run_fetch_csi300_kline.py` | 任务胶水：成分股 + 全部历史成分并集 K 线 + 基准指数落库，生成 data-bridge 配置和覆盖率报告 |

`agent/scripts/` 根目录另有 3 个原有开发脚本（`bench_performance.py`、`w4a_run_benches.py`、`w4a_patch_blog.py`），与数据抓取无关。

---


## 10. 命令速查表

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
| 直接重跑某个 run（无 LLM） | `cd agent; ..\.venv\Scripts\python.exe -m backtest.runner "<run_dir>"` |
| 复制 run 做参数变体 | `Copy-Item "<vibe_home>\runs\<run_id>" "...\runs\exp_<名字>" -Recurse` |
| 重跑并生成 LLM 分析报告 | 上一条命令加 `--with-analysis`（也支持 `--withAnalysis`） |
| 查看 run 分析报告/图表 | WebUI 运行详情“分析图 / 分析”标签，或 API `/runs/<id>/analysis` |
| 首次推送 | `git push -u origin mumu-main` |
| 日常推送 | `git add -A; git commit -m "..."; git push origin mumu-main` |

---

## 11. 文档与迭代记录

- 项目规则：见 [AGENTS.md](AGENTS.md)
- 迭代记忆：见 [ITERATION_LOG.md](ITERATION_LOG.md)
- 坑的认知与状态：见 [Mistake_Journal.md](Mistake_Journal.md)（8.x 只保留解法；坑是否修复以账本为准）
- 开工前计划：见 documents/plans/

<!-- BEGIN GENERATED: backtest-capabilities -->
## 12. MCP 回测工作流能力表（自动生成）

> 来源：`agent/src/backtest_capabilities.py`；注册表版本：`2026-08-23.1`。
> 公开 MCP 工具保持为一个：`backtest`。`fast_backtest`、`generate_charts`、`generate_report` 是 action/能力 ID，不是额外工具。

默认调用：`backtest(run_dir, action="run", speed="fast", use_cache=false)`。
它会执行真实回测，但不生成 PNG、不调用报告 LLM，也不隐式启用行情缓存。用户明确要求复用行情时，再传入 `use_cache=true`；需要图片或报告时，再显式调用同一个工具的 `action="charts"` 或 `action="report"`。

| 能力 ID | action | 作用 | runner flags | 允许生成 | 明确跳过 |
|---|---|---|---|---|---|
| `fast_backtest` | `run` | 快速回测：执行 loader、SignalEngine 和回测引擎，跳过可选的慢速 digest 分析。 | --fastrun | artifacts/metrics.csv、artifacts/trades.csv、artifacts/positions.csv、artifacts/equity.csv、run_card.json、analysis.digest.json | analysis_charts/*.png、analysis.md、LLM 报告 |
| `normal_backtest` | `run` | 普通回测：执行完整回测和完整 digest，但不隐式生成图片或 LLM 报告。 | — | artifacts/metrics.csv、artifacts/trades.csv、artifacts/positions.csv、artifacts/equity.csv、run_card.json、analysis.digest.json | analysis_charts/*.png、analysis.md、LLM 报告 |
| `generate_charts` | `charts` | 补生成分析图：读取已完成 run 的派生摘要并生成 PNG，不重新取数或执行策略。 | — | analysis.digest.json（必要时）、analysis_charts/*.png | loader、SignalEngine、回测引擎、analysis.md |
| `generate_report` | `report` | 补生成分析报告：读取已完成 run 的派生摘要并调用一次报告 LLM，不重新回测。 | — | analysis.digest.json（必要时）、analysis.md、analysis.status.json、analysis.prompt.md | loader、SignalEngine、回测引擎、analysis_charts/*.png |
| `full_backtest_workflow` | `full` | 完整回测工作流：按普通回测 → 图表后处理 → 报告后处理的顺序显式执行。 | — | 核心回测 artifacts、analysis.digest.json、analysis_charts/*.png、analysis.md、analysis.status.json、analysis.prompt.md | — |

### 公共参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `run_dir` | 必填 | 已允许路径下的独立 run 目录 |
| `action` | `run` | `run`、`charts`、`report`、`full` |
| `speed` | `fast` | `fast` 使用 `--fastrun`；`normal` 生成完整 digest；charts/report 不重新回测 |
| `use_cache` | `false` | 只影响 run/full 的 loader cache；只有用户明确要求时传 `true`，单次设置不修改全局 `.env` |
| `execution` | 省略 | 可选覆盖 `config.json` 的三字段；不改写原 config |

`execution` 的字段是 `entry_mode`、`exit_mode`、`stop_loss_mode`。当前四个合法 preset 为：`close/close/hard、close/close/none、next_open/next_open/hard、next_open/next_open/none`。
旧 `exit_mode=stop` 只用于返回迁移错误，不能自动解释为 hard stop。

小周期回测仍由 `config.json` 的 `interval`、`start_date`、`end_date`、`backtest_start`、`backtest_end` 和策略自身的 `holding_bars` 共同决定；MCP 不会替 Agent 重写数据层或引擎层。

图表/报告是已完成 run 的后处理：它们可以读取或更新派生的 `analysis.digest.json`，但不得改变核心 `config.json`、策略代码、`run_card.json`、`metrics.csv`、`trades.csv`、`positions.csv`、`equity.csv`。

MCP schema 摘要：`['run', 'charts', 'report', 'full']`；缓存默认 `False`。
<!-- END GENERATED: backtest-capabilities -->
