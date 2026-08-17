# 计划：WebUI 交易明细"一键加载全部"按钮

> 编号：P-20260817-trade_log_full_load
> 状态：讨论中
> 日期：2026-08-17
> 关联迭代：待填（收尾时填 V 号）
> 关联：ta_turtle_15m_v1_2021_2023（发现场景 run）

## 项目调研

- 后端 `agent/src/api/runs_routes.py:183/206`：trades.csv 全量载入 `response.artifacts_trades_csv`（`models.py:78` "Full trade rows"），再 `trade_log = artifacts_trades_csv[:500]` 截断为预览；响应模型 `RunResponse` 两个字段都序列化（无 exclude）——**全量交易数据已随每次 `/runs/{id}` 响应下发**，`:500` 截断只影响 `trade_log` 字段。
- 前端 `RunDetail.tsx:786` TradesTab 只读 `run.trade_log`；多开/空开/多平/空平/总盈亏统计均由 `trades` 推导，**换数据源即自动刷新**；表格按 `TRADES_PAGE_SIZE` 分页渲染，不会一次性渲染全部 DOM。
- 前端 `lib/api.ts:587` RunData 类型只有 `trade_log`，未暴露 `artifacts_trades_csv`（JSON 里有但没类型，前端用不了）。
- 下载交易 CSV 按钮（`RunDetail.tsx:372`）也用 `run.trade_log`（截断 500 行）——加载全部后应同步用全量源。
- 图表 symbol 刷新合并（`RunDetail.tsx:249`）只保留 trade_log，需同步保留 artifacts_trades_csv（防切换 symbol 后丢全量）。

## 需求目标

- 做什么：WebUI 报告-交易页加"加载全部交易明细"按钮，点击后交易表显示全量交易，笔数与盈亏统计随之刷新；**默认进入仍显示截断前 500 行（原逻辑不变）**。
- 范围 / 边界：只改前端展示层（RunDetail TradesTab + RunData 类型 + i18n + 测试）；**后端零改动**（全量数据已在响应中）。
- 验收标准（一句话）：点击按钮后交易表笔数、多开/空开/多平/空平、总盈亏与 trades.csv 全量一致；默认进入仍为前 500 行。

## 实现方案

1. `frontend/src/lib/api.ts`：RunData 增加 `artifacts_trades_csv?: Array<Record<string, string>>`。
2. `frontend/src/pages/RunDetail.tsx`：
   - TradesTab 增加 `showAll` 状态；数据源 `trades = showAll && run.artifacts_trades_csv?.length ? run.artifacts_trades_csv : (run.trade_log || [])`；
   - 统计行旁加"加载全部交易明细"按钮：仅当 `run.artifacts_trades_csv?.length > (run.trade_log?.length ?? 0)` 且 `!showAll` 时显示（空值防护：老 run 无 `artifacts_trades_csv` 字段时不显示按钮）；加载后按钮隐藏/置灰，文案改为"已加载全部 N 笔"；
   - **幂等性约定**：按钮为单向加载（非 toggle），点击后 `showAll=true` 且按钮消失，无第二次点击入口；数据已随响应在内存中，无网络请求，重复触发 `setShowAll(true)` 无副作用；统计由 `trades` 每次渲染重新推导，与点击次数无关；
   - 下载交易 CSV 改用当前 `trades` 源（加载全部后下载全量）；
   - 图表 symbol 合并处（约 :249）同步保留 `artifacts_trades_csv`——否则切换 symbol 后已加载的全量被合并逻辑覆盖，而按钮已隐藏无法再加载（视图静默回落 500）。
3. `frontend/src/i18n/locales/{en,zh-CN,ja,ko,ar}.json`：补按钮与状态文案 key（如 `runDetail.loadAllTrades` / `runDetail.tradesAllLoaded`）。
4. 测试：`frontend/src/pages/__tests__/RunDetail.test.tsx` 补用例。

## 执行清单

1. api.ts RunData 增加 `artifacts_trades_csv` 类型
2. RunDetail.tsx TradesTab 加按钮 + `showAll` 状态 + 数据源切换
3. 下载 CSV 改用当前数据源；symbol 合并保留全量字段
4. 5 个语言包补 key（en/zh-CN/ja/ko/ar）
5. RunDetail.test.tsx 补默认截断 + 点击后全量统计两用例
6. 构建前端 + 组件测试 + WebUI 手动验证（v1 run）

## 开工前核对

（状态从"讨论中"切到"已确认"前逐项核对；核对结果逐项展示"通过 / 未通过 + 发现项"）

- 需求目标 / 范围与讨论记录一致（默认 500 不变、点击加载全部、统计刷新）
- 范围/边界无被后续讨论反转但仍保留的旧约束（后端零改动）
- 执行清单覆盖需求目标与验收标准
- 验收标准可验证（对比 trades.csv 全量）
- 元信息已填（关联迭代允许待填）

## 验证

- `cd frontend && npm test -- RunDetail`（组件测试）
- 构建后打开 v1 run（ta_turtle_15m_v1_2021_2023）WebUI 报告-交易：默认显示 500 笔 / 总盈亏 -1,150；点"加载全部"后显示 621 笔 / 总盈亏 -17,640（与 trades.csv 全量一致）
- 点击后下载 CSV 行数 = trades.csv 行数（1242 行）
- **跑一遍回撤验证（改动不得影响权益/回撤链路）**：重跑 v1 run（数据走缓存，秒级取数），核对 run_card/metrics 的 `max_drawdown = -34.50%`、`total_return = -23.03%`、`final_value = 76,972` 与重跑结果一致，且 WebUI 报告页的权益/回撤曲线、指标卡与 run_card 一致（本改动只动交易明细展示，指标与回撤链路必须原样）

## 讨论记录

- 2026-08-17 用户提出：WebUI 交易统计（500 笔 / 总盈亏 -1,150）与全量不符，要求"前端加一键加载全部交易明细并刷新统计，默认仍截断 500"。调研确认根因是后端 `trade_log[:500]` 截断预览，且全量 `artifacts_trades_csv` 已随响应下发——改动收敛为前端展示层。
- 2026-08-17 用户追问按钮幂等性。确认设计为单向加载（点击后按钮消失、无网络请求、统计按渲染重新推导），并把空值防护（老 run 无 `artifacts_trades_csv` 字段）、快速双击、切换 symbol 后合并保留全量字段等边界写进实现方案。

## 风险 / 注意

- 大 run（数万笔）的全量 JSON 已随默认响应下发（现状如此），本改动不新增负担；若未来要瘦身默认响应，可另立计划做"按需加载"（后端加参数控制），**本计划不做**。
- i18n 5 语言都要补 key，漏一个会导致按钮无文案。
- 表格分页渲染（TRADES_PAGE_SIZE）已存在，加载全量不会一次渲染全部 DOM。
