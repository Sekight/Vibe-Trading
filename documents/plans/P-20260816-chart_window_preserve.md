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

- 做什么：在图表页，调整 1 indicators / 2 副图指标 / 3 切换标签 / 4 切换周期 时都保持当前行情可视时间窗口（不重置回默认）；行为 3 同时保持 副图/指标/周期 选择。
- 范围 / 边界：只改前端展示层（CandlestickChart.tsx、RunDetail.tsx 及相关）；不改后端、不改数据、不影响回测；切换 run（换一个 run）时重置为默认属预期行为。
- 验收标准（一句话）：在 rb run 图表页滑到任一非默认时间段后，分别执行 1/2/3/4 四类操作，K 线图保持原可视时间范围（跨周期按时间窗口映射）。

## 实现方案

- **窗口捕获与回写（统一机制）**：CandlestickChart 内维护可视窗口（`viewWindow` = dataZoom start/end 百分比，或时间区间）；监听 ECharts `datazoom` 事件同步最新窗口；每次 setOption 前读取当前窗口（`chart.getOption().dataZoom[0]`）回写 start/end，替代硬编码 defaultStart。首次渲染 / 无窗口时用 defaultStart 兜底。
- **行为 1/2（指标/副图）**：数据长度不变，窗口以百分比原样保留，改动最小。
- **行为 3（标签切换）**：把 `sub`/`overlays`/`period`/`viewWindow` 状态提升到 RunDetail（或 ChartTab 保持挂载），组件重挂载后恢复；run_id 变化时重置。
- **行为 4（周期切换）**：切换前把当前可视窗口由 bar 索引换算成时间区间（startTime/endTime），切换后用新周期数据把时间区间映射回 bar 索引 → 计算 start/end 百分比；处理期货 trade_date/夜盘、数据缺口、区间 bar 数过少（至少 1 根）等边界。
- **多图联动**：connectCharts 已同步用户缩放；回写时以同一时间窗口应用到各图即可（保持联动语义）。
- **阶段划分（待拍板）**：阶段一 = 行为 1/2/3；阶段二 = 行为 4。

## 执行清单

1. CandlestickChart：新增 viewWindow 捕获（datazoom 事件）+ setOption 前回写。
2. 验证行为 1/2：调 indicators / 副图不重置窗口。
3. 行为 3：状态提升（sub/overlays/period/viewWindow 到 RunDetail 或 keep-mounted），run 切换重置。
4. 行为 4：时间窗口跨周期映射 + 边界处理。
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
- 手动 / 浏览器验证：rb run 图表页滑到非默认区间 → ①调 MA/BOLL ②切 vol/macd/rsi/kdj ③切到分析图再切回 ④切 5m/1h/1D 周期，均保持可视时间范围。
- 边界：空数据、数据不足 250 根、期货夜盘 trade_date、跨周期区间 bar 过少。

## 讨论记录

（append-only：谁提出、选项、结论；范围/边界反转时标注“范围变更：原=... → 现=...”）

- 2026-08-16，用户提出：图表页四个行为（1 indicators / 2 副图 / 3 标签切换 / 4 周期切换）都会把行情重置回默认时间段，希望都保持之前的时间窗口；1/2 必须做，3/4 待讨论。
- 2026-08-16，Codex 调研：根因 = setOption(notMerge) 每次硬覆盖 dataZoom.start（最后 250 根），缩放状态仅存 ECharts 实例内；标签切换条件渲染卸载组件；周期切换为前端 resample 后重算窗口。多图经 connect 联动共享窗口。复杂度：1/2 低、3 中（状态提升）、4 中高（时间窗口跨周期映射）。
- 2026-08-16，Codex 建议：3 建议实现（状态提升后边际成本低、切走不丢上下文是基本预期，TradingView 等专业软件均如此）；4 建议实现但可单独第二阶段（TradingView 切换周期保持时间范围是行业标准习惯，但实现最复杂、与 1/2/3 正交）。待用户拍板 3/4 范围与阶段划分。

## 风险 / 注意

- connectCharts 联动：回写窗口时多图一致性（保持同步是期望行为）。
- 行为 4 跨周期映射边界最多（trade_date/夜盘、缺口、区间 bar 极少），是主要工作量与风险点。
- 状态提升会改 ChartTab props 结构，需回归多标的图表页。
- run 切换时重置窗口，避免旧 run 窗口带到新 run。
