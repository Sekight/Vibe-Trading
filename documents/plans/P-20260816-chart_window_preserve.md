# 计划：图表页保持行情可视时间窗口

> 编号：P-20260816-chart_window_preserve
> 短标题规则：单词间用 _ 连接，不使用 -（例如 P-20260814-timeline_charts_fix）
> 状态：讨论中
> 日期：2026-08-16
> 关联迭代：待填（收尾时填 V 号）
> 关联：commit / run（收尾时补）

## 项目调研

**外部（用户反馈 / 行为）**
- 用户在 K 线图滑动到目标时间段后，调整 indicators（1）、副图 vol/macd/rsi/kdj（2）、切换标签（3）、切换周期（4）任一行为都会把行情重置回默认时间段（最后 250 根）——2026-08-16，用户反馈
- 目标：四个行为都保持之前的行情可视时间窗口不刷新；1/2 必须做，3/4 待讨论——2026-08-16，用户反馈

**内部（代码 / 项目现状）**
- `CandlestickChart` 每次 `setOption(notMerge=true)` 重建，`dataZoom.start = defaultStart`（`visibleData.length<=250 ? 0 : 100-250/len*100`）硬覆盖可视窗口；缩放状态只存 ECharts 实例内，setOption 即丢失——2026-08-16，frontend/src/components/charts/CandlestickChart.tsx:236-296
- setOption 效应依赖 `[visibleData, markers, baseData, indicatorCache, sub, overlays, period, dark]`，sub/overlays/period 任一变化即重算窗口——同上
- `sub`/`overlays`/`period` 均为组件内部 useState；周期切换是纯前端 resample（`resampleBars`）——同上
- 标签切换 `{tab === "chart" && <ChartTab/>}` 条件渲染，切走即卸载 ChartTab 及其下所有 CandlestickChart（ECharts 实例 + 内部 state 全丢）——frontend/src/pages/RunDetail.tsx:388-407
- 多标的每标的一个 CandlestickChart，经 `echarts.connect(CHART_GROUP)` 联动缩放窗口（多图共享时间窗口是期望行为）——CandlestickChart.tsx:95-96、RunDetail.tsx:697-699

## 需求目标

- 做什么：在图表页，调整 1 indicators / 2 副图指标 / 3 切换标签 时保持当前行情可视时间窗口（不重置回默认）；行为 3 同时保持 副图/指标/周期 选择。行为 4（切换周期）本轮不做，后续再议。
- 范围 / 边界：只改前端展示层（CandlestickChart.tsx、RunDetail.tsx 及相关）；不改后端、不改数据、不影响回测；切换 run / 加载新 run 时图表重置为默认，不携带旧 run 的指标/副图/周期/窗口状态。
- 验收标准（一句话）：在 rb run 图表页滑到任一非默认时间段后，分别执行 1/2/3 三类操作，K 线图保持原可视时间范围；切换到其他 run 的报告后图表恢复默认、不串数据。

## 实现方案

- **窗口捕获与回写（统一机制）**：CandlestickChart 内维护可视窗口（`viewWindow` = dataZoom start/end 百分比，或时间区间）；监听 ECharts `datazoom` 事件同步最新窗口；每次 setOption 前读取当前窗口（`chart.getOption().dataZoom[0]`）回写 start/end，替代硬编码 defaultStart。首次渲染 / 无窗口时用 defaultStart 兜底。
- **行为 1/2（指标/副图）**：数据长度不变，窗口以百分比原样保留，改动最小。
- **行为 3（标签切换）**：把 `sub`/`overlays`/`period`/`viewWindow` 状态提升到 RunDetail（或 ChartTab 保持挂载），组件重挂载后恢复；按 run_id 归属状态，run_id 变化时重置。
- **run 隔离**：提升后的状态以 run_id 为 key（或 run_id 变化时显式重置），保证新 run / 切换 run 不携带旧状态。
- **多图联动**：connectCharts 已同步用户缩放；回写时以同一时间窗口应用到各图即可（保持联动语义）。
- 行为 4（周期切换，跨周期时间窗口映射）本轮不做，列为后续迭代。

## 执行清单

1. CandlestickChart：新增 viewWindow 捕获（datazoom 事件）+ setOption 前回写。
2. 验证行为 1/2：调 indicators / 副图不重置窗口。
3. 行为 3：状态提升（sub/overlays/period/viewWindow 到 RunDetail 或 keep-mounted），run_id 变化时重置。
4. 验证 run 隔离：新 run / 切换不同 run 报告，图表恢复默认、不携带旧状态。
5. 单测 / 前端测试 + 交互验证。
6. 收尾：ITERATION_LOG、计划状态、README 索引。

## 开工前核对

（状态从“讨论中”切到“已确认”前由 Codex 逐项核对；核对结果按清单逐项展示“通过 / 未通过 + 发现项”）

- 需求目标 / 范围与讨论记录一致
- 范围/边界无被后续讨论反转但仍保留的旧约束
- 执行清单覆盖需求目标与验收标准
- 验收标准可验证
- 元信息已填（关联允许为待填）

## 验证

- 前端 vitest（CandlestickChart 窗口保留相关用例，若可测）+ `npm run build`。
- 手动 / 浏览器验证：rb run 图表页滑到非默认区间 → ①调 MA/BOLL ②切 vol/macd/rsi/kdj ③切到分析图/分析再切回，均保持可视时间范围。
- 场景 1（新 run 不携带旧数据）：加载一个新 run 的报告，图表窗口与 sub/overlays/period 恢复默认，不出现旧 run 的窗口状态。
- 场景 2（切换不同 run 不串数据）：rb run 图表滑到非默认区间并调过指标后，切到 A 股 run，图表恢复默认、指标/副图不串。
- 场景 3（回归）：前端全量 vitest + npm build；后端不受影响（纯前端改动），相关 pytest 抽查。
- 边界：空数据、数据不足 250 根。

## 讨论记录

（append-only：谁提出、选项、结论；范围/边界反转时标注“范围变更：原=... → 现=...”）

- 2026-08-16，用户提出：图表页四个行为（1 indicators / 2 副图 / 3 标签切换 / 4 周期切换）都会把行情重置回默认时间段，希望都保持之前的时间窗口；1/2 必须做，3/4 待讨论。
- 2026-08-16，Codex 调研：根因 = setOption(notMerge) 每次硬覆盖 dataZoom.start（最后 250 根），缩放状态仅存 ECharts 实例内；标签切换条件渲染卸载组件；周期切换为前端 resample 后重算窗口。多图经 connect 联动共享窗口。复杂度：1/2 低、3 中（状态提升）、4 中高（时间窗口跨周期映射）。
- 2026-08-16，Codex 建议：3 建议实现（状态提升后边际成本低、切走不丢上下文是基本预期，TradingView 等专业软件均如此）；4 建议实现但可单独第二阶段（TradingView 切换周期保持时间范围是行业标准习惯，但实现最复杂、与 1/2/3 正交）。待用户拍板 3/4 范围与阶段划分。
- 2026-08-16，用户拍板：1/2/3 全做，4（周期切换）本轮不做；验证补充三场景——①新 run 不携带旧 run 数据 ②切换不同 run 报告不串数据 ③回归。

## 风险 / 注意

- connectCharts 联动：回写窗口时多图一致性（保持同步是期望行为）。
- 状态提升会改 ChartTab props 结构，需回归多标的图表页。
- run 隔离是硬性要求：窗口/指标/副图状态按 run_id 归属，新 run / 切换 run 必须重置，靠状态提升处的 run_id key 保证。
- 行为 4（周期切换）本轮不做，跨周期时间窗口映射列后续迭代。
