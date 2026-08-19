# 计划：回测与前端支持按交易时间聚合（同花顺式，可选开关）

> 编号：P-20260818-trading_time_aggregation
> 状态：讨论中
> 日期：2026-08-18
> 关联迭代：待填（收尾时填 V 号）
> 关联：commit / run（收尾时补）

> 当前阶段范围说明（2026-08-19）：本计划继续讨论既有 4H 回测的交易时间聚合；本文此前关于新增 2H 回测周期、2H 测试与 2H 前端展示的表述均不再属于当前实施范围。P-20260818-backtest_2h_interval 已废弃；若未来恢复 2H，须在本计划交易时间口径确认后另建或恢复实施计划。

## 项目调研

> 查了才写，不为了写而查；按外部（接口/文献/网页）、内部（代码/项目现状）记调研事实。

- 引擎侧现状：local_loader `_resample_to_interval`（agent/backtest/loaders/local_loader.py:86）用 `df.resample(rule)`（rule = 1min/5min/15min/30min/1h/4h/1D）纯自然时间、零点对齐分桶；`_TRADE_DATE_AGG = {"trade_date": "last"}` 在聚合时保留 trade_date 列（2026-08-18，代码确认）。
- 源数据现状：期货 CSV（如 E:/data/chaina_future/TA/TA_1m.csv）带 trade_date 列，夜盘 21:00 bar 的 trade_date 已归下一交易日（2026-08-18，本地数据确认；坑见 Mistake_Journal M026）。
- 前端侧现状：price_series.csv 由引擎按 run interval 落盘；CandlestickChart 在"显示周期 == run 周期"时直接用落盘 bar，切换周期时前端 resampleBars（frontend/src/lib/resample.ts:80）按自然时间整点桶聚合；PriceBar 接口已有 `trade_date?: string` 字段（frontend/src/lib/api.ts:478）；run 的 interval 通过 `run.run_card.backtest.interval` 下发（frontend/src/pages/RunDetail.tsx:725）。
- 项目内无任何交易时段/夜盘数据表（全仓库 grep trading_time/夜盘 仅命中 local_loader 自身的 resample 代码；data-bridge config.yaml 320 个 symbol 均为"symbol→文件路径"映射，2026-08-18 确认）。
- 参照口径：同花顺/东财的多分钟 K 线 = 交易日为锚 + 交易时间累计切分（TA 4H = 2 根/天：[21:00→次日 11:15ish 满 4 小时]、[11:15ish→15:00 尾段]；2H = 3 根/天：[21-23]、[9-11:15]、[11:15-15]）；天勤 TqSdk 服务端与 vibe-trading 现引擎同为自然时钟（2026-08-18 实测，见记忆 tqsdk-kline-aggregation）。
- 边界：P-20260818-backtest_2h_interval（讨论中）负责"引擎支持 2H 周期"（_VALID_INTERVALS/_RESAMPLE_RULES 加条目），与本计划正交：本计划改聚合算法，组合后即"交易时间聚合的 2H"（同花顺 2H，3 根/天）。两计划可独立做。

## 需求目标

- 做什么：给回测引擎与 WebUI 前端 K 线增加**可选的"按交易时间聚合"**模式（同花顺式：交易日为锚、组内交易时间累计、满周期切一根、末根不足保留），与现有"自然时间"模式并存（config 开关，默认 natural 保持现状兼容）。
- 范围 / 边界：
  - 只改聚合层：local_loader 的 resample + 前端 resample/展示链路 + config/run_card 元数据下发；
  - 不改引擎成交逻辑、不改策略代码（signal_engine.py 的 is_last_bar 硬编码适配不在本计划，见"风险/注意"）；
  - 2H 周期支持另见 P-20260818-backtest_2h_interval，不在本计划；
  - 不内置"品种→交易时段"表（见"实现方案·数据"：算法数据驱动，不需要）。
- 验收标准：TA_1m 数据 aggregation=trading_time 聚合结果与同花顺 TA 4H/2H bar 边界一致（4H = 2 根/天 [21:00→次日11:15ish]、[11:15ish→15:00]；2H = 3 根/天 [21-23]、[9-11:15]、[11:15-15]）；WebUI 该 run 的"run 周期"与切换周期均按同一聚合模式显示；aggregation=natural（默认）行为与现状完全一致（回归）。

## 实现方案

### 核心算法（关键洞察）

"按交易时间累计切分"在 bar 粒度上**等价于**：按 trade_date 分组 → 组内按时间排序 → 累计 bar 时长（基础粒度分钟 × bar 数）→ 每满目标周期分钟切一根 → 末根不足保留；bar 的 datetime = 该 bar 第一个交易分钟的时间戳（同花顺式标签，如 4H 第一根 21:00 起、第二根 11:15 起）。

**不需要内置夜盘时段表**：夜盘有无、时长差异（21-23 / 21-01 / 21-02:30）全部由源数据的 trade_date 字段天然处理——夜盘 bar 已归下一交易日，同 trade_date 组内连续累计即跨夜盘+日盘。只需源数据带 trade_date 列（现有期货 CSV 都有，local_loader 已保留）。

### 引擎侧（agent/backtest/loaders/local_loader.py）

1. config 新增 `aggregation: "natural" | "trading_time"`（默认 "natural"；runner 校验可选值，非法值回退 natural 并 warning）。
2. `_resample_to_interval` 增加 trading_time 分支：替代 pandas resample，按上述算法实现；复用 `_OHLCV_AGG`；返回 bar 保留 trade_date（`"last"`）。
   - 约束：源粒度 ≤ 目标粒度的判定沿用现有逻辑（target < source 时返回源 bar + warning）；源粒度必须是目标粒度的约数（1m→4H 240 根、5m→2H 24 根、15m→4H 16 根），非约数时 warning 或按 floor 累计并说明（首版：要求整除，不整除 warning 后按 floor）。
   - 无 trade_date 列时：trading_time 模式 warning 并回退 natural（交易日锚定无依据，见 M026）。
3. 日线（1D）在 trading_time 模式下仍按 trade_date 聚合（天然已是交易日锚定，行为不变）。

### 前端侧（frontend/src/lib/resample.ts + CandlestickChart.tsx + run_card）

1. run_card.backtest 增加 `aggregation` 字段（引擎写入 config 即可，run_card 生成时带出），前端从 `run.run_card.backtest.aggregation` 读取。
2. resample.ts：`resampleBars(bars, period, aggregation)` 增加 trading_time 分支——按 trade_date 分组累计切分（与引擎同一算法；PriceBar 已有 trade_date）。自然时间逻辑保留为默认。
3. CandlestickChart：把 aggregation 传给 resampleBars；availablePeriods 不变（周期范围与聚合模式无关）。

### 数据

- 不需要新增数据文件：trade_date 已在源 CSV 与落盘 bar 中。
- 可选后续增强（不在首版）：内置"品种→交易所规则交易时段表"，用于 ①源数据缺 trade_date 时推断；②数据缺失时按规则对齐累计分钟。表来源必须为交易所官方规则并经用户确认，不依赖模型记忆。

## 执行清单

1. config / runner：`aggregation` 字段读写 + 校验（非法回退 natural）；run_card 带出。
2. local_loader：trading_time 累计切分实现（按 trade_date 分组、组内累计、满周期切、末根不足、datetime=组内起点）。
3. 引擎单测：TA 1m→4H/2H 边界断言（2 根/天、3 根/天、跨午休、跨夜盘/日盘、末根不足、无 trade_date 回退）。
4. 前端 resample.ts：trading_time 聚合实现 + resample.test.ts 补用例（与引擎同一算法、同一期望）。
5. CandlestickChart / RunDetail：aggregation 下发与传参。
6. 端到端验证：TA_1m + aggregation=trading_time + interval=4H/2H 回测，bar 边界与同花顺对照；WebUI 显示一致。
7. 回归：natural 默认模式跑现有 TA 15m/4H run，结果与现状一致。

## 开工前核对

（状态从"讨论中"切到"已确认"前逐项核对；核对结果按清单逐项展示"通过 / 未通过 + 发现项"）

- 需求目标 / 范围与讨论记录一致
- 范围/边界无被后续讨论反转但仍保留的旧约束
- 执行清单覆盖需求目标与验收标准
- 验收标准可验证
- 元信息已填（关联允许为待填）

## 验证

- 单测：引擎与前端 trading_time 聚合算法（TA 1m→4H/2H 边界——**4H：2 根/天 [21:00→次日11:15ish]、[11:15ish→15:00]**；**2H：3 根/天 [21-23]、[9-11:15]、[11:15-15]**；满周期切、末根不足、跨午休、跨夜盘/日盘）。
- 端到端：TA_1m.csv + aggregation=trading_time + interval=4H/2H 官方 runner 回测；bar 边界与同花顺 TA 图对照（用户提供参照）。
- 前端：WebUI 打开该 run，"run 周期"与切换 2H/1H 显示与引擎落盘一致。
- 回归：natural 模式跑现有 TA 15m/4H run，指标与现状一致（快照对比）。

## 讨论记录

（append-only：谁提出、选项、结论；范围/边界反转时标注"范围变更：原=... → 现=..."）

- 2026-08-18 用户提出：把 vibe-trading 做成支持像同花顺那样按交易时间聚合（可选），回测与 WebUI 前端 K 线都要按交易时间聚合；提示需评估国内期货夜盘差异（哪些品种有夜盘、时段 21-23 / 21-01 / 21-02:30 不等）。
- 2026-08-18 评估结论：核心算法只需源数据带 trade_date（现有数据已具备），不需要内置夜盘时段表；夜盘差异被 trade_date 天然处理。夜盘品种/时段知识仅用于人工核对与验证参照，不作为实现依赖。
- 2026-08-18 方案取舍：默认 natural 保持兼容，trading_time 为 config 开关；前端跨周期聚合与引擎用同一算法（模式经 run_card 下发），不做前端独立时段表。
- 2026-08-19 用户确认：①策略管策略、引擎层管聚合——策略层 is_last_bar 适配不在本计划（迁移时另做），范围不变；②验证参照（同花顺）认可，验证部分补 4H 边界（与 2H 边界并列）。
- 2026-08-19，用户决定：不再单独推进 2H 回测。范围变更：原=本计划同时验收 4H/2H 的交易时间聚合，并与独立 2H 引擎计划组合；现=本计划当前阶段只讨论和验收既有 4H 回测的交易时间聚合，2H 不进入 runner、loader、metrics、前端或端到端执行清单。P-20260818-backtest_2h_interval 已归档为已废弃。

## 风险 / 注意

- **策略层 is_last_bar 硬编码**：现有策略（signal_engine.py）的 `is_last_bar = 12:00/20:00`、换月强平 force 时间戳是按自然 4H 桶标签写的；trading_time 聚合下末根 bar 时间戳不固定（TA 4H 末根 11:15 起），策略需改为"按交易日最后一根聚合 bar"判定。本计划不改策略，迁移/实盘时另行适配。
- **trade_date 依赖**：trading_time 模式要求源数据带 trade_date 列（无则回退 natural + warning）；M026 教训：夜盘归属必须用 trade_date 字段。
- **前端模式下发**：前端必须拿到 aggregation（run_card.backtest.aggregation），否则会用默认自然时间聚合、与回测不一致。
- **数据缺口**：若某交易时段数据缺失，累计分钟偏少（口径按"数据实际分钟"而非"交易所规则分钟"）；首版接受，后续如需严格对齐再内置时段表。
- **与 2H 计划的边界**：本计划不碰 _VALID_INTERVALS；P-20260818-backtest_2h_interval 加 2H 周期后，两者组合即"交易时间聚合 2H"。
- **当前阶段的 2H 边界**：以上关于 2H 的历史调研和设计不构成当前实施范围；在交易时间聚合口径确认、且用户重新立项前，禁止以本计划为依据修改 2H 周期契约或实现。
