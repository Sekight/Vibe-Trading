# 计划：交易方向与开平动作展示（图表 + 交易表）

> 编号：P-20260814-trade_action_ui
> 短标题规则：单词间用 _ 连接，不使用 -（例如 P-20260814-timeline_charts_fix）
> 状态：已完成
> 日期：2026-08-14
> 关联迭代：V020
> 关联：commit / run（收尾时补）

## 需求目标

- 做什么：把 K 线标记和交易表的方向语义从“买入/卖出”升级为“开平 + 多空”四类动作：多开 / 空开 / 多平 / 空平。图表标记改为 B / S / CB / CS，其中平多 CB 绿色、平空 CS 红色；交易表方向列显示“多开 / 空开 / 多平 / 空平”，筛选 chips 和顶部计数也按四类拆分，颜色按原始 side 语义：多开/空平（买入）红、空开/多平（卖出）绿，与图表 B/S/CB/CS 一致。
- 范围 / 边界：只改分析展示层（前端图表/交易表 + `ui_services.build_trade_markers` 补充字段），不动回测引擎、trades.csv 写入格式、策略与数据链路；不改变主连选择规则。
- 验收标准（一句话）：1D/5m K 线标记能区分开平，平多显示绿色 CB、平空显示红色 CS；交易表方向四类文本与颜色正确，四类筛选可用；前端测试、构建、浏览器验证通过。

## 实现方案

（涉及文件/模块、关键设计；讨论中随时补充）

1. 交易动作模型（可复用虚拟币/外汇）
   - 定义 `action ∈ {open, close}`、`direction ∈ {long, short}`，展示分类 `long_open / short_open / long_close / short_close`，不绑定 A 股或期货。
   - 判定依据：现有 trades.csv 行 `pnl / holding_bars / holding_days` 判断 close（open 行为 0）；direction 由 side 推导：entry buy=long、entry sell=short；exit sell=long close、exit buy=short close。
   - 若未来交易记录自带 `action/direction` 字段则优先使用，当前逻辑作为 fallback。

2. 后端
   - `agent/src/ui_services.py` 的 `build_trade_markers`：每行输出 `action` 与 `direction`，供图表 marker 使用；兼容旧 run（holding_days fallback）。

3. 前端
   - 新增 `frontend/src/lib/tradeActions.ts`：统一计算 `{action, direction, kind}`，图表和交易表共用，后续虚拟币/外汇直接复用。
   - `CandlestickChart.tsx`：marker 文本 B（多开）/ S（空开）/ CB（多平）/ CS（空平）；颜色 B 红、S 绿保持现状，CB 绿、CS 红。
   - `RunDetail.tsx` TradesTab：方向列显示“多开 / 空开 / 多平 / 空平”，徽章颜色按原始 side 语义（多开/空平红、空开/多平绿）；筛选 chips 改为四类 + 全部；顶部计数按四类统计。
   - i18n：5 个语言文件（zh-CN/en/ja/ko/ar）新增四个方向 key，替换现有 sideBuy/sideSell 展示（保留旧 key 兼容其他入口）。

## 执行清单

1. 新增/调整交易动作模型与后端 markers 字段（ui_services.py）。
2. 新增前端 `tradeActions.ts` 及单测。
3. 修改 CandlestickChart 标记文本与颜色。
4. 修改 TradesTab 方向文本、徽章颜色、筛选 chips、顶部计数。
5. 更新 5 个 i18n 文件。
6. 跑前端 vitest + build、后端相关 pytest。
7. 浏览器验证：K 线 CB/CS 标记与颜色、交易表四类文本与筛选。
8. 收尾：ITERATION_LOG、计划状态与 README 索引。

## 开工前核对

（状态从“讨论中”切到“已确认”前由 Codex 逐项核对；核对结果按清单逐项展示“通过 / 未通过 + 发现项”）

- 需求目标 / 范围与讨论记录一致
- 范围/边界无被后续讨论反转但仍保留的旧约束
- 执行清单覆盖需求目标与验收标准
- 验收标准可验证
- 元信息已填（关联允许为待填）

核对结果（2026-08-14）：
- 通过：需求目标 / 范围与讨论记录一致（含颜色纠正记录）。
- 通过：范围/边界无被反转但仍保留的旧约束；颜色表述已按用户纠正更新。
- 通过：执行清单覆盖需求目标与验收标准。
- 通过：验收标准可用测试 + 浏览器验证。
- 通过：元信息已填（关联迭代收尾时填）。

## 验证

（有内容才写：测试命令、run_id、预期结果）

- `npm test -- --run`：新增 tradeActions / RunDetail / marker 相关用例全绿；`npm run build` 通过。
- `pytest tests/test_ui_services.py tests/test_analysis_digest.py -q` 通过。
- Chrome CDP 验证 rb 5m run：K 线多开 B 红、空开 S 绿、多平 CB 绿、空平 CS 红；交易表方向显示四类，筛选 chips 四类可过滤，徽章颜色正确。

## 讨论记录

（append-only：谁提出、选项、结论；范围/边界反转时标注“范围变更：原=... → 现=...”）

- 2026-08-14，用户提出：K 线平多显示 S、平空显示 B，希望平多 CB 绿色、平空 CS 红色；交易表平多不显示卖出而显示“多平”，平空不显示买入而显示“空平”。
- 2026-08-14，Codex 调研：trades.csv 可用 pnl/holding_bars/holding_days 区分开平，direction 可由 side 推导；改动集中在前端展示层，难度小。
- 2026-08-14，用户拍板：①筛选 chips 分四类；②颜色按图表语义；③B/S 颜色保持现状；④交易表“买入/卖出”改为“多开/空开”；⑤实现时考虑虚拟币、外汇复用。
- 2026-08-14，用户纠正颜色分组：多开/空平都是买入（红），空开/多平都是卖出（绿），与图表 B 红 / S 绿 / CB 绿 / CS 红一致；计划中此前“多开/多平绿、空开/空平红”的表述作废。

## 风险 / 注意

（有内容才写）

- 旧 run 若缺 holding_bars，用 holding_days fallback；极端情况（平价平仓）以 holding_bars/holding_days 为准。
- 筛选 chips 从“买入/卖出”改为四类，属于用户可见行为变化，收尾更新迭代日志。
- 虚拟币/外汇若 side 语义不同（例如无多空、双向持仓），后续扩展时保持 action/direction 模型，不硬编码 A 股/期货字段名。
- 图表 marker 颜色依赖主题色，CB/CS 使用显式绿/红常量，避免随主题翻转。
