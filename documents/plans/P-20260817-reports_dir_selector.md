# 计划：WebUI 报告页目录选择器

> 编号：P-20260817-reports_dir_selector
> 状态：讨论中
> 日期：2026-08-17
> 关联迭代：待填（收尾时填 V 号）
> 关联：commit / run（收尾时补）

## 项目调研

- WebUI 报告页（Reports.tsx）通过 `api.listRuns()` → `GET /runs` 读 `~/.vibe-trading/runs`；后端 `agent/src/api/runs_routes.py::list_runs` 只 `iterdir()` 顶层目录，不递归子目录。2026-08-17，代码：runs_routes.py:402-501。
- 后端所有 run 详情路由（`/runs/{run_id}`、`/code`、`/pine`、`/analysis`、`/analysis/charts`、PNG）统一按 `RUNS_DIR / run_id` 解析；run_id 即目录名。代码：runs_routes.py:272-357。
- run_id 路径参数校验 `_SAFE_PATH_PARAM_RE = [A-Za-z0-9_-]{1,128}`，仅 ASCII，不支持中文/斜杠。代码：helpers.py:263-269。
- 前端 run 消费点：Reports.tsx（列表）、RunDetail.tsx（详情）、Compare.tsx（对比，api.listRuns + api.getRun）、聊天 RunCompleteCard.tsx（api.getRun / getRunPine）。2026-08-17，代码：frontend/src/pages/*、components/chat/RunCompleteCard.tsx。
- SPA 深链回退正则 `^/runs/[^/]+/?$` 只匹配单段 path，query string 不在匹配范围内，加 `?dir=` 不破坏深链。代码：helpers.py:42-53。
- 新 run 由 runner 固定写到 runs 根目录（state.py::create_run_dir），系统本身没有子目录分类机制；分类只能靠用户手动 mv。2026-08-17，代码：agent/src/core/state.py:16-32。
- 现有坑：M006（改 Python 源码后 WebUI 不生效，需重启后端 + 重建 dist）、M018（WebUI 硬编码组件，新增 UI 元素必须逐展示面核对）、E003（浏览器验证被静默跳过）。来源：Mistake_Journal.md / 全局踩坑日志。

## 需求目标

- 做什么：WebUI 报告页增加"报告目录"选择器。用户把 run 手动归类到 `~/.vibe-trading/runs/<分类>/` 子目录后，可在报告页选择该分类查看其中的 run；缺省行为（不选分类 = 只看根目录）与现状完全一致。
- 范围 / 边界：只改 WebUI 报告读取链路（后端 runs_routes + 前端 Reports/RunDetail）；不改 run 写入逻辑（runner 仍写根目录，分类靠用户手动 mv）；不含 swarm runs（独立目录 swarm/runs）；CLI `list` 命令不在本次范围。
- 验收标准：报告页下拉框列出 runs 根下的各分类目录，选择后列表、详情页、图表全部能打开对应子目录的 run；不选时行为与改动前一致；路径穿越请求（`../`、绝对路径）被拒绝。

## 实现方案

方案 A（推荐，改动最小、向后兼容）：所有 `/runs/*` 路由增加可选 `dir` query 参数（相对 runs 根的子目录路径），`dir` 缺省 = 根目录 = 现状。不做 `/runs/{dir}/{run_id}` 路径前缀改造（那会波及深链正则、校验正则和全部前端链接）。

### 后端（agent/src/api/runs_routes.py + helpers.py）

1. 新增目录解析辅助：`_resolve_runs_subdir(dir: str) -> Path`，`dir` 为空/缺省时返回 RUNS_DIR；否则拼接后 `resolve()`，校验结果必须位于 RUNS_DIR 内（`is_relative_to`），拒绝 `..`、绝对路径、UNC、空路径段。分类目录名放开非 ASCII（中文目录名可用），但不允许 `/` 段穿越。
2. `GET /runs`：`list_runs` 增加 `dir: Optional[str]` query 参数，扫描目录改为 `_resolve_runs_subdir(dir)`；**顺带修复现状问题**——过滤掉"非 run 目录"（目录内无 `state.json` / `req.json` / `artifacts/` / `run_card.json` 任一特征即视为分类目录，不当作 run 列出，避免垃圾条目）。
3. 新增 `GET /runs/dirs`：返回 runs 根下的一级子目录名列表（`List[str]`，空列表表示无分类），供前端下拉框使用。只列一级，不递归。
4. 详情类路由（`/runs/{run_id}`、`/code`、`/pine`、`/analysis`、`/analysis/charts`、`/analysis/charts/{name}.png`）统一增加 `dir` query 参数，`run_dir = _resolve_runs_subdir(dir) / run_id`。`run_id` 仍走原 `_validate_path_param` 校验不变。

### 前端（api.ts / Reports.tsx / RunDetail.tsx）

5. `api.ts`：`listRuns(limit, dir?)`、`getRun(id, params, dir?)`、`getRunCode/Pine/Analysis/AnalysisCharts/fetchRunAnalysisPng` 增加可选 `dir`，拼成 `?dir=`（复用/新增 `appendQueryParam` 模式，中文目录名需 encodeURIComponent，URLSearchParams 已自动处理）。
6. `Reports.tsx`：过滤器行新增"报告目录"下拉框（加载 `GET /runs/dirs`，选项 = "全部/根目录" + 各分类）；选中后 `loadReports` 带 dir 重新拉取；run 行链接改为 `/runs/${run_id}?dir=${dir}`（dir 为空时维持原链接）。行内"对比"链接同样带 dir。
7. `RunDetail.tsx`：从 `useSearchParams` 读 `dir`，传给全部 run API 调用；`run_id` 链接、代码/Pine/分析/图表/PNG 请求统一透传。
8. `Compare.tsx` 本次不改（仍读根目录；后续如需跨分类对比再单独迭代）。

### 不破坏的保证

- `dir` 缺省时所有路由行为与现状逐字节一致（根目录扫描、无新增过滤逻辑影响正常 run）。
- 深链、鉴权、PNG 路由结构不变。
- CLI、runner、swarm 不受影响。

## 执行清单

1. 后端：helpers.py 增加 `_resolve_runs_subdir`（含路径穿越校验），runs_routes.py 各路由接入 `dir` 参数，`list_runs` 过滤非 run 目录
2. 后端：新增 `GET /runs/dirs`
3. 前端：api.ts 各 run 方法支持 dir 参数
4. 前端：Reports.tsx 目录选择器 + 链接带 dir；RunDetail.tsx 读取并透传 dir
5. 测试：后端路径穿越/子目录列表/详情各路由 API 实测；前端 Reports 目录选择组件测试
6. 重建 dist，重启后端，浏览器逐展示面核对（列表、详情、代码、Pine、分析、图表、PNG、对比入口）

## 开工前核对

（状态从"讨论中"切到"已确认"前由 agent 逐项核对；核对结果按清单逐项展示"通过 / 未通过 + 发现项"）

- 需求目标 / 范围与讨论记录一致
- 范围/边界无被后续讨论反转但仍保留的旧约束
- 执行清单覆盖需求目标与验收标准
- 验收标准可验证
- 元信息已填（关联允许为待填）

## 验证

- 构造 `~/.vibe-trading/runs/` 下分类目录（含中文名）并移入若干 run；`GET /runs?dir=<分类>` 只返回该分类 run；`GET /runs/dirs` 返回分类列表；`GET /runs/{id}?dir=<分类>` 及 code/pine/analysis/charts/png 全部可读
- 路径穿越：`dir=../`、`dir=..%2F..`、`dir=/绝对路径`、`dir=C:%5C...` 返回 400/404 且不泄露根外文件
- 缺省 `dir`：`GET /runs` 与改动前一致
- 前端：`npm test`（Reports 目录选择相关用例）+ `npm run build` 重建 dist
- 无浏览器自动化工具时：API 实测 + 组件测试替代，并在收尾报告中明确"逐展示面核对未做 + 残余风险"

## 讨论记录

- 2026-08-17，用户提出：报告默认读 `~/.vibe-trading/runs`，想把部分报告按分类放子目录，webui 就看不到了，需要"选择报告目录"功能，并要求先评估合理性/难度/破坏性再写计划。
- 2026-08-17，需求评估结论（由 agent 调研后给出）：
  - 合理性：合理。run 目录无分类机制，手动归类是自然需求。两个事实需用户知悉：①现状下子目录里的 run 完全不可见，且子目录本身会被误列为一条垃圾 run（"Manual Analysis"）——本次顺带修复；②runner 新产出的 run 仍写根目录，选子目录后看不到新 run，需手动 mv。
  - 难度：中等。方案 A（`dir` query 参数 + `GET /runs/dirs`）改动集中在 runs_routes.py（7 个路由 + 1 新路由）+ 前端 3 个文件；难点在路径穿越校验与前端所有详情调用点透传 dir（遗漏任何一处该展示面就 404）。
  - 破坏性：低。dir 缺省 = 现状，向后兼容；唯一行为变化是 list_runs 过滤非 run 目录（净改善，已列入范围）；CLI/runner/swarm/深链不受影响。

## 风险 / 注意

- 中文分类目录名：`_validate_path_param` 的 ASCII 正则不能用于 dir，必须用新的 resolve 校验；前端 URL 编码要统一走 URLSearchParams/encodeURIComponent。
- 前端详情页有 6 个 API 调用点（getRun/code/pine/analysis/charts/png），透传 dir 时逐一点名核对，防遗漏（M018/E003 教训：UI 展示面必须逐面验证）。
- 过滤"非 run 目录"的判据要保守：只过滤完全没有 run 特征文件的目录，避免误伤命名不规范的 run 目录。
- 分类后 run 的绝对路径会变（`run_directory` 字段、run_card 内路径），详情页如有展示绝对路径处显示为子目录路径，属预期行为，不影响功能。
