# 计划：报告页行情 K 线增加当前 4H 周期

> 编号：P-20260819-chart_4h_interval
> 状态：已完成
> 日期：2026-08-19
> 关联迭代：V037
> 关联：无 commit；run `ta_turtle_4h_v438_swg2_2014_2023`、`ta_turtle_1h_v425_2021_2023`、`20260808_032625_05_e9f25e`

## 项目调研

- frontend/src/pages/RunDetail.tsx:725 已把 run.run_card.backtest.interval 传给 CandlestickChart 的 baseInterval；4H run 的周期信息与原始价格数据均已到图表组件（2026-08-19，代码确认）。
- frontend/src/lib/resample.ts 的 KlinePeriod、KLINE_PERIODS 和 PERIOD_MINUTES 没有 4h。availablePeriods() 采用“展示周期不小于回测基础周期”的规则：日线回测返回 1D/1W/1M/1Y；分钟至 4H 的回测会保留 1D 等更大周期。因此 4h 应加入共用周期列表，由同一过滤规则让它在基础周期不大于 4H 的回测中出现，而不是只为 4H run 写专用分支（2026-08-19，代码确认）。
- frontend/src/components/charts/CandlestickChart.tsx:58-62 在显示周期与 baseInterval 大小写无关地相等时，直接展示落盘原始 bar；基础周期小于 4H 时，选择 4h 会沿用前端 resampleBars() 的自然时间聚合路径，基础周期等于 4H 时则直接展示原始 4H bar（2026-08-19，代码确认）。
- 同组件的交易标记归桶把分钟周期硬编码为 5m/15m/20m/1h/2h，新增 4h 时必须同步处理，否则“标记时间不等于 bar 起点”的交易可能无法落到对应 4H bar（2026-08-19，代码确认）。
- 当前 4H 落盘 bar 仍是自然时钟、零点对齐口径；4H run 选择 4h 时只显示这些原始 bar，不改变其时间标签或 OHLCV；较小基础周期的 4h 选择沿用前端自然时间聚合。交易时间累计聚合另见 P-20260818-trading_time_aggregation 和 Mistake_Journal M029（2026-08-19，代码确认）。
- HowToUse.md:1045 规定 1m 行情显示尚未开放；本计划只增加 4h 展示周期，不开放 1m、不实现 2H 回测，也不改变既有 4H 自然时间聚合口径（2026-08-19，文档确认）。

## 需求目标

- 做什么：报告页「图表」tab 增加与 1D 同级的 4h 展示周期；基础周期不大于 4H 的 run 可选择 4h，4H run 默认展示其落盘的原始 4H K 线。
- 范围 / 边界：
  - 仅改前端展示层的周期 token、4H 周期列表和交易标记归桶判断；
  - 4h 加入共用展示周期列表，遵循现有“展示周期 >= 基础回测周期”的筛选规则：1m/5m/15m/20m/30m/1H/2H/4H 等基础周期显示 4h，1D 基础周期仍只显示 1D 及以上；
  - 基础周期为 4H 时，4h 默认选中并直接使用原始 4H bar；基础周期小于 4H 时，4h 作为更大展示周期使用现有前端自然时间聚合；
  - 不改回测引擎、local loader、数据源、config.json、指标、run artifact 或 4H 的自然时间聚合口径；
  - 不开放 1m 行情、不实现 2H 回测、不处理跨周期可视时间窗口映射；4h 在低于 4H 的基础周期 run 中作为前端展示聚合选项，但不改变回测引擎或 run artifact。
- 验收标准（一句话）：4H run 的图表周期按钮为 4h/1D/1W/1M/1Y 且默认选中 4h、原始 4H bar 和交易标记对齐；1H/2H 等更小基础周期的按钮中出现 4h 并可自然时间聚合；1D run 仍只显示 1D 及以上；1m、2H 引擎和自然时间 4H 口径不回归。

## 实现方案

1. **共用周期列表与 1D 同级筛选**
   - 在 frontend/src/lib/resample.ts 增加前端 token "4h" 与 240 分钟映射，使其可被类型、周期键、前端聚合和交易标记复用。
   - 将 4h 放入 KLINE_PERIODS 的 2h 与 1D 之间；保留 availablePeriods(baseInterval) 现有的“分钟周期不小于基础周期、日/周/月/年始终保留”规则。这样基础周期小于或等于 4H 时出现 4h，1D 基础周期不出现 4h。
   - 4H run 的过滤结果首项为 4h，现有 effectivePeriod = period ?? periods[0] 会默认选中；更小基础周期的首项仍为其自身周期，4h 仅作为可选的更大周期。

2. **原始 bar 与交易标记**
   - 保持 CandlestickChart 的“显示周期等于基础周期则直接使用原始 bar”路径：4H run 选择 4h 时不调用 resampleBars；更小基础周期选择 4h 时沿用 resampleBars 的自然时间聚合。
   - 将交易标记的“是否为分钟周期”判断改为可复用的周期能力判断（或至少纳入 4h），确保 4h 显示时标记通过同一个 4 小时自然时间键找到所属 K 线，且不再遗留易漏周期的硬编码列表。

3. **测试与人工核对**
   - 扩展 frontend/src/lib/__tests__/resample.test.ts：断言 1H/2H/4H 基础周期均出现 4h，1D 基础周期不出现 4h，4H 列表顺序和无重复，并覆盖 4h 的自然时间聚合键与 OHLCV。
   - 扩展 frontend/src/components/charts/__tests__/CandlestickChart.test.tsx：4H baseInterval 默认选中/显示 4h 且原始 bar 不被二次聚合；较小基础周期可显示 4h；时间落在同一自然 4H 桶内的交易标记能映射到正确 K 线。
   - 运行定向前端测试和生产构建；用一个真实 4H run 在浏览器核对按钮、首末 bar OHLCV、交易标记和周期切换。

## 执行清单

1. [x] 完成开工前核对，确认 4h 与 1D 同级的共用周期筛选规则。
2. [x] 更新 resample.ts 的 4h token、分钟映射和共用 KLINE_PERIODS 顺序，不增加 4H 专用分支。
3. [x] 更新 CandlestickChart.tsx 的交易标记归桶判断，保持 4H run 的原始 4H bar 直通。
4. [x] 补充 resample 与 CandlestickChart 的 4h/1D 同级筛选、原始直通、前端聚合和交易标记定向测试。
5. [x] 运行前端定向测试、生产构建和真实 4H/较小周期 run 的浏览器检查。
6. [x] 收尾更新计划状态、计划 README；如用户可见说明变化，再更新 HowToUse 与 ITERATION_LOG。

## 开工前核对

（状态从“讨论中”切到“已确认”前由 Codex 逐项核对；核对结果按清单逐项展示“通过 / 未通过 + 发现项”）

- 需求目标 / 范围与讨论记录一致
- 范围/边界无被后续讨论反转但仍保留的旧约束
- 执行清单覆盖需求目标与验收标准
- 验收标准可验证
- 元信息已填（关联允许为待填）

## 验证

- cd frontend; npm run test:run -- src/lib/__tests__/resample.test.ts src/components/charts/__tests__/CandlestickChart.test.tsx：验证 4h 与 1D 同级筛选、无重复、4H 原始 bar 直通、较小周期前端聚合和交易标记归桶。
- cd frontend; npm run build：类型检查与生产构建通过。
- 浏览器：打开真实 4H run 的报告页「图表」tab，确认默认 4h 处于选中态；其首末时间、OHLCV 与原始 price_series 对齐；交易标记落在正确 bar；切换 1D 再切回 4h 不改变 4H 原始数据。再打开较小周期 run，确认 4h 可选并按自然时间聚合。
- 回归：选择 1H/2H/4H/1D 等 run，确认 4h 只在基础周期不大于 4H 时出现，1D run 仍只显示 1D 及以上，1m 行情仍不开放。

## 讨论记录

- 2026-08-18，用户提出：报告页行情 K 线除了既有周期外，应能显示当前回测周期，例如 4H 回测也能查看 4H 行情。
- 2026-08-18，初步方案曾覆盖 1m、30m、2H、4H 等所有当前回测周期。随后调研发现：1m 行情尚未开放，2H 引擎和期货交易时间聚合仍未确认，泛化范围会混入不应在本项解决的议题。
- 2026-08-19，用户修正范围：4H 周期要与 1D 同级，遵循现有“更小基础周期也显示、更大展示周期保留”的可向上聚合逻辑；需先确认 1D 行为。
- 2026-08-19，Codex 代码确认：availablePeriods() 对分钟基础周期保留不小于基础周期的分钟展示项，并始终保留 1D/1W/1M/1Y；1D 基础周期只返回 1D 及以上。因此 4h 应进入共用 KLINE_PERIODS，基础周期不大于 4H 时出现，1D run 不显示 4h。
- 2026-08-19，用户确认：按上述与 1D 同级的逻辑实现。4H run 默认选中并直通原始 4H bar；更小基础周期选择 4h 时使用既有前端自然时间聚合。范围仍不改回测引擎、不开放 1m、不实现 2H、不改变自然时间 4H 口径。

## 风险 / 注意

- 本计划展示的是当前回测实际使用的自然时间 4H bar，不是同花顺/东方财富的交易时间累计 4H。两种口径将有不同的 bar 边界，不能拿后者直接对照策略信号。
- 未来 P-20260818-trading_time_aggregation 若改变 4H 落盘 bar 的时间语义，本计划的“基础周期直通”仍会展示新产物；届时应为该计划补做 4H 图表回归，而不是在本计划中预先复制交易时间算法。
- chartView.period 是 run 内共享状态；切换不同 run 时已有重置逻辑。4H 默认仅在 period 为空时生效，较小基础周期的默认项仍保持现有首项规则，用户主动选择其他周期后应保持现有行为。
