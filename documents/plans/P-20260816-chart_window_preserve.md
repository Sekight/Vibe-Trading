# 计划：图表页保持行情可视时间窗口

> 编号：P-20260816-chart_window_preserve
> 短标题规则：单词间用 _ 连接，不使用 -（例如 P-20260814-timeline_charts_fix）
> 状态：已确认
> 日期：2026-08-16
> 关联迭代：V027（已交付部分）/ 待填（本次补充后收尾填）
> 关联：commit `544658b`、`27dbd57`；run 无（纯前端改动）

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

- 做什么：在图表页，调整 1 indicators / 2 副图指标 / 3 切换标签 时保持当前行情可视时间窗口（不重置回默认）；行为 3 同时保持 副图/指标/周期 选择；加标的时新图加载到当前同组可视窗口（与现有图一致，不出现突然放大/缩小），删标的不影响其余图窗口。**多标的切换标的（showOnly / 删增）时，indicators / 副图 / 周期 / 时间窗口 均保持（各标的共用同一套图表设置与窗口）**。行为 4（切换周期）本轮不做，后续再议。
- 范围 / 边界：只改前端展示层（CandlestickChart.tsx、RunDetail.tsx 及相关）；不改后端、不改数据、不影响回测；切换 run / 加载新 run 时图表重置为默认，不携带旧 run 的指标/副图/周期/窗口状态。
- 验收标准（一句话）：在 rb run 图表页滑到任一非默认时间段后，分别执行 1/2/3 三类操作，K 线图保持原可视时间范围；切换到其他 run 的报告后图表恢复默认、不串数据。

## 实现方案

- **窗口捕获与回写（统一机制）**：CandlestickChart 内维护可视窗口（`viewWindow` = dataZoom start/end 百分比，或时间区间）；监听 ECharts `datazoom` 事件同步最新窗口；每次 setOption 前读取当前窗口（`chart.getOption().dataZoom[0]`）回写 start/end，替代硬编码 defaultStart。首次渲染 / 无窗口时用 defaultStart 兜底。
- **行为 1/2（指标/副图）**：数据长度不变，窗口以百分比原样保留，改动最小。
- **行为 3（标签切换）**：ChartTab 保持挂载，非「图表」标签时用 CSS 隐藏（替代状态提升，代码更少）；组件不卸载则 sub/overlays/period/窗口自然保留。
- **多标的共享图表设置（本次补充）**：把 `sub`/`overlays`/`period`/窗口 提升为 RunDetail 级共享状态 `chartView`，经 ChartTab 传入所有 CandlestickChart；各标的共用同一套设置与窗口——切换标的（showOnly/删增）新图读共享状态保持，删标的不影响其余图。**替换 V027 的模块级 sharedWindow/计数清空方案**（该方案在切换标的经过「全部卸载」时误清窗口）。
- **run 隔离**：runId 变化的 RunDetail effect 显式重置 `chartView`（与现有 setSelectedSymbols([]) 等重置并列），新 run / 切换 run 不携带旧状态。
- **多图联动**：connectCharts 已同步用户缩放；回写时以同一时间窗口应用到各图即可（保持联动语义）。
- 行为 4（周期切换，跨周期时间窗口映射）本轮不做，列为后续迭代。

## 执行清单

1. RunDetail：新增 `chartView` 共享状态（sub/overlays/period/window），runId effect 重置；ChartTab 传入。
2. CandlestickChart：改为受控（sub/overlays/period/window 来自 props），datazoom 事件上报窗口；去掉模块级 sharedWindow/计数。
3. 验证行为 1/2/3：调指标/副图/切标签不重置窗口。
4. 验证多标的：切换标的（showOnly/删增）指标/副图/周期/窗口全保持；run 切换后新 run 恢复默认不串数据。
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
- 场景 4（加删标的）：多标的页滑到非默认窗口后，加一个标的 → 新图显示与现有图一致的时间范围（无突然放大/缩小）；删一个标的 → 其余图窗口不变；再加回 → 仍加入同一窗口。
- 场景 5（切换标的保持设置）：多标的下把某图设为 MACD + BOLL + 滑到非默认窗口后，showOnly 切换到另一标的 / 删旧增新 → 新图保持 MACD + BOLL + 同一窗口；周期亦保持。
- 场景 6（run 隔离回归）：切换 run / 加载新 run，图表设置与窗口恢复默认、不串数据。
- 边界：空数据、数据不足 250 根。

## 讨论记录

（append-only：谁提出、选项、结论；范围/边界反转时标注“范围变更：原=... → 现=...”）

- 2026-08-16，用户提出：图表页四个行为（1 indicators / 2 副图 / 3 标签切换 / 4 周期切换）都会把行情重置回默认时间段，希望都保持之前的时间窗口；1/2 必须做，3/4 待讨论。
- 2026-08-16，Codex 调研：根因 = setOption(notMerge) 每次硬覆盖 dataZoom.start（最后 250 根），缩放状态仅存 ECharts 实例内；标签切换条件渲染卸载组件；周期切换为前端 resample 后重算窗口。多图经 connect 联动共享窗口。复杂度：1/2 低、3 中（状态提升）、4 中高（时间窗口跨周期映射）。
- 2026-08-16，Codex 建议：3 建议实现（状态提升后边际成本低、切走不丢上下文是基本预期，TradingView 等专业软件均如此）；4 建议实现但可单独第二阶段（TradingView 切换周期保持时间范围是行业标准习惯，但实现最复杂、与 1/2/3 正交）。待用户拍板 3/4 范围与阶段划分。
- 2026-08-16，用户拍板：1/2/3 全做，4（周期切换）本轮不做；验证补充三场景——①新 run 不携带旧 run 数据 ②切换不同 run 报告不串数据 ③回归。
- 2026-08-16，用户问：①run 隔离含义、现有实现是否已隔离（less is more）②多标的切标的是否会重置。Codex 核查：runId 变化时 RunDetail 现有 effect 已清空 selectedSymbols → 图表卸载 → run 隔离天然成立，无需额外编码；多标的 per-chart 状态独立、窗口经 echarts.connect 组内联动，增删标的不影响已有图。实现方案相应简化：行为 3 用保持挂载 + CSS 隐藏，不做状态提升。
- 2026-08-16，用户澄清：加标的、删标的都不能影响现有标的的时间窗口，且**加的标的也要加载到同一时间窗口**，否则 K 线会突然放大/缩小。Codex 确认：删标的不影响已有图（现状已满足）；加标的现状从默认 250 根开始、与现有窗口不一致，需修——方案为模块级共享窗口（datazoom 事件记录百分比，新图挂载时采用，最后一张图卸载时清空），全部在 CandlestickChart 内实现。
- 2026-08-16，用户反馈（V027 已交付后）：多标的切换标的（showOnly/删增）时，indicators / 副图 / 周期 / 时间窗口全部重置；要求都保持，且换 run / 新 run 不携带旧数据。Codex 定位：①指标/副图/周期是各图内部 useState，新图默认值；②模块级共享窗口「最后一张图卸载时清空」在切换标的经过全部卸载时误清窗口。修法：状态提升为 RunDetail 级共享 `chartView`（sub/overlays/period/window），runId effect 显式重置——切换标的全保持、换 run 不串；替换模块级方案。

## 风险 / 注意

- connectCharts 联动：回写窗口时多图一致性（保持同步是期望行为）。
- 行为 3 采用保持挂载：ECharts 实例在非图表标签时保持存活（内存占用可接受），重新显示时依赖现有 ResizeObserver 触发 resize。
- 共享状态 `chartView` 提升到 RunDetail：会改 ChartTab props 结构（新增 chartView + 更新回调），需回归多标的图表页；run 隔离靠 runId effect 显式重置保证（验证场景 6）。
- 行为 4（周期切换）本轮不做，跨周期时间窗口映射列后续迭代。
