# 计划：换约规则自动识别主连切换日

> 编号：P-20260816-contract_switch_auto
> 状态：讨论中
> 日期：2026-08-16
> 关联迭代：待填（收尾时填 V 号）
> 关联：commit / run（收尾时补）

## 项目调研

> 查了才写；按外部、内部记调研事实。以下为 2026-08-16 探索记录。

- 内部·数据：vibe-trading rb 1m 源（data-bridge `rb0000.SHFE` → `E:/CodexWorkSpace/vibe-trading-codex-project/work/xinyi_rb/rb_1m.csv`）覆盖 2024-09-19 ~ 2025-09-29，含 `contract` 列（主连合约序列 rb2501 → rb2505 → rb2510 → rb2601）。来源：data-bridge config.yaml（2026-08-16 读）。
- 内部·切换日：2024-10~2025-09 一年窗口内主连切换 **3 次**（contract 变化首日）：**2024-12-04、2025-04-07、2025-08-28**。当前 V1/V2/V3 策略只硬编码处理 2025-08-29（8/27 收盘强平 + 8/28/29 禁开），另两次未覆盖。来源：rb_1m.csv contract 列扫描（2026-08-16）。
- 内部·loader：`agent/backtest/loaders/local_loader.py` 的 `_resample_to_interval` 聚合只保留 OHLCV + trade_date，**contract 列在聚合时被丢弃**；`_normalize_columns` 支持任意列映射，但 data-bridge config 未配置 contract 映射，策略运行时拿不到合约信息。来源：读代码（2026-08-16）。
- 外部·skill：xinyi-kline（`C:\Users\mumu\.zcode\skills\xinyi-kline`）无真正增量解析（断点续传）；`--days`/`--end-date` 控窗口、`--cache-dir` 整体复用 1m 主连解析；切换日可从 contract 列自动识别。来源：SKILL.md + build_xinyi_kline.py 源码（2026-08-16 调研）。
- 内部·试验：已试过"loader 聚合透传 contract（`_CONTRACT_AGG={"contract":"last"}`）+ data-bridge 加 contract 映射 + 策略按 contract 变化自动识别切换日"三件套，loader 单测 8 passed，方案可行；因用户要求走正式计划，改动已全部撤回（loader/config/策略均恢复原样，仅保留工作区既有的 `20m` 未提交行未动）。来源：2026-08-16 探索会话。

## 需求目标

- 做什么：把换约规则从"硬编码 2025-08-29"改为**自动识别所有主连切换日**；对每个切换日 T 生效：老仓在 **T-2 交易日**日盘（15:00 前）最后一根 bar 收盘价强制平仓；**T-1、T 交易日**（含 T-2 夜盘，按 trade_date 归交易日）禁开新仓。
- 范围 / 边界：不动引擎成交逻辑；不做 xinyi-kline 增量解析；只覆盖 data-bridge 中带 contract 列的数据源（当前仅 rb0000.SHFE）；策略侧检测逻辑对无 contract 列的数据自动降级为不启用换约规则。
- 验收标准（一句话）：一年窗口（2024-10-01~2025-09-29）自动识别出 2024-12-04 / 2025-04-07 / 2025-08-28 三个切换日并全部套用规则，且 8/29 相关行为与当前硬编码版一致。

## 实现方案

（讨论中，方向候选）

- 方案 A（已试通，倾向）：local_loader 聚合时透传 contract 列（agg `last`）+ data-bridge config 加 `contract: contract` 映射 + 策略 generate() 从 contract 列检测变化点得切换日清单，再套 T-2 平 / T-1·T 禁开。改动面：local_loader.py（项目代码，1 处常量 + 1 处 agg 规则）、data-bridge config（本地配置）、策略代码。
- 方案 B：不依赖数据列——由 runner 或配置注入切换日清单（如从原始 csv 离线识别后写 config 字段）。改动集中在 runner/config，策略不变，但"自动识别"需在数据侧前置一步，且未来新数据要重新生成清单。
- 方案 C：策略直接读原始 rb_1m.csv 识别（不可移植，路径硬编码，不推荐）。

## 执行清单

（讨论确认后填）

## 开工前核对

（状态切"已确认"前逐项核对展示）

- 需求目标 / 范围与讨论记录一致
- 范围/边界无被后续讨论反转但仍保留的旧约束
- 执行清单覆盖需求目标与验收标准
- 验收标准可验证
- 元信息已填（关联允许为待填）

## 验证

（有内容才写：测试命令、run_id、预期结果）

## 讨论记录

- 2026-08-16：探索一年期 15m 回测时发现 3 次主连切换、V3 只处理 8/29；尝试"loader 透传 contract + 策略自动识别"（loader 单测 8 passed）后，用户决定撤回试验改动、先建计划定为讨论中，优先继续策略探索（15m 基数已达 50 笔），本需求之后再实现。

## 风险 / 注意

- 切换日判定口径：contract 变化**首根 bar 的 trade_date**（夜盘归次日交易日），非自然日。
- 数据窗口首日若 contract 变化（数据起点即切换）不计入切换日（prev 为空跳过）。
- local_loader 改动影响所有 local 数据源：仅当源含 contract 列才新增 agg，无 contract 列行为不变，需跑 loader 回归单测。
- 一年窗口下 8/27 无持仓时强制平仓不触发属预期（无仓可平），验证时应同时检查"有仓日的 T-2 平仓"与"T-1/T 禁开（含被压制的候选信号）"。
