# 计划：总手续费与单边手续费落盘展示

> 编号：P-20260814-total_commission
> 短标题规则：单词间用 _ 连接，不使用 -（例如 P-20260814-timeline_charts_fix）
> 状态：已确认
> 日期：2026-08-14
> 关联迭代：待填（收尾时填 V 号）
> 关联：commit / run（收尾时补）

## 需求目标

- 做什么：把回测手续费从引擎内部暴露到产出与展示：trades.csv 每行记录单边手续费；metrics.csv / run_card 增加总手续费；WebUI 报告页顶部指标汇总显示总手续费；digest 与 LLM 分析报告包含总手续费，并归入合适分类。
- 范围 / 边界：只改回测产物与展示层（引擎手续费计算逻辑不动）；不改 trades.csv 的既有列语义；不做 roundtrip_commission（本轮只做单边）。
- 验收标准（一句话）：重跑任意 run 后，trades.csv 每行有 commission（开仓行=entry_commission、平仓行=exit_commission），metrics/run_card/WebUI/digest/LLM 报告都能看到 total_commission，且数值等于所有单边手续费之和。

## 实现方案

（涉及文件/模块、关键设计；讨论中随时补充）

1. 手续费口径
   - 期货：entry/exit commission 只含手续费（rb 万 1 按乘数）。
   - A 股：entry commission = 佣金 + 过户费；exit commission = 佣金 + 过户费 + 卖出印花税。
   - trades.csv 每行 `commission` = 该次成交的单边费用（开仓行 entry_commission，平仓行 exit_commission）。
   - 总手续费 `total_commission` = 所有 TradeRecord.commission 之和 = 所有 trades.csv 行 commission 之和。

2. 后端落盘
   - `agent/backtest/engines/base.py`：`_write_artifacts` 的 trades.csv 增加 `commission` 列；entry 行写 `t.entry_commission`，exit 行写 `exit_comm`（当前未存到 TradeRecord，需在 `_close_position` 一并保存或从 `t.commission - t.entry_commission` 反推）。
   - `agent/backtest/metrics.py`：新增 `total_commission`，取 `sum(t.commission for t in trades)`；run_card 自动带上。
   - `trades.csv` 列顺序建议放在 `pnl` 后。

3. 展示与报告
   - `frontend/src/lib/formatters.ts`：新增 `total_commission` label（中文“总手续费”，英文“Total Commission”）、金额格式化（元，千分位，非百分比）、加入 `DISPLAY_ORDER`。
   - WebUI 顶部指标汇总由 MetricsCard 自动展示 metrics 新字段。
   - `agent/backtest/analysis/digest.py`：
     - METRIC_MEANINGS 增加 `total_commission` 说明；
     - METRIC_GROUPS 新建「交易成本」分组，`total_commission` 归入（2026-08-15 用户拍板方案 A）；
     - render_digest_for_llm 会按分组自动输出该指标。
   - 旧 run 无该字段：WebUI/digest 按缺失处理，不报错。

## 执行清单

1. 确认字段命名与口径（trades.csv 每行 commission、metrics/run_card total_commission）。
2. 后端：base.py 输出 trades.csv commission 列；metrics.py 输出 total_commission。
3. digest：METRIC_GROUPS / METRIC_MEANINGS 增加 total_commission。
4. 前端：formatters 增加 label/格式化/DISPLAY_ORDER。
5. 跑回归：重跑 rb 期货 run 与股票日 K run，核对单边手续费合计与 total_commission。
6. 浏览器验证 WebUI 顶部指标与 LLM 报告（可只跑 runner --with-analysis 验证报告文本）。
7. 收尾：ITERATION_LOG、计划状态与 README 索引。

## 开工前核对

（状态从“讨论中”切到“已确认”前由 Codex 逐项核对；核对结果按清单逐项展示“通过 / 未通过 + 发现项”）

- 需求目标 / 范围与讨论记录一致
- 范围/边界无被后续讨论反转但仍保留的旧约束
- 执行清单覆盖需求目标与验收标准
- 验收标准可验证
- 元信息已填（关联允许为待填）

## 验证

（有内容才写：测试命令、run_id、预期结果）

- `pytest tests/test_metrics.py tests/test_analysis_digest.py tests/test_ui_services.py tests/test_engine_metrics_json.py -q`。
- 前端 `npm test -- --run` + `npm run build`。
- 重跑 `rb_futures_5m_20250901_29_v1`：trades.csv 每行有 commission，合计约 1155.31；run_card/WebUI/digest/LLM 报告显示 total_commission。
- 重跑股票日 K run：A 股手续费口径（佣金+过户费+卖出印花税）汇总正确。

## 讨论记录

（append-only：谁提出、选项、结论；范围/边界反转时标注“范围变更：原=... → 现=...”）

- 2026-08-14，用户提出：run_card 要有总手续费、trades.csv 每行要有单边手续费、WebUI 顶部指标加总手续费、digest/LLM 报告包含总手续费。
- 2026-08-14，Codex 调研：trades.csv 是事件式（每行一次开或平），不能把开+平合计写进每一行；每行 commission 应为单边费用，total_commission 汇总所有单边。
- 2026-08-14，确认手续费构成：期货只含手续费；A 股 entry=佣金+过户费、exit=佣金+过户费+卖出印花税。
- 待确认：①”metrics.csv 每一行记录”是否指 trades.csv（建议按 trades.csv 理解）；②total_commission 在 LLM 报告归入”仓位与换手”还是”其他”；③是否在平仓行额外显示 roundtrip_commission（本轮默认不做）。
- 2026-08-15，待确认项收口（用户拍板）：①按需求目标理解，trades.csv 每行 commission（非 metrics.csv 每行）；②新建「交易成本」分组归入 total_commission（方案 A，非并入「仓位与换手」）；③本轮不做 roundtrip_commission。

## 风险 / 注意

（有内容才写）

- 旧 run 无 total_commission/commission 字段，前端与 digest 需容忍缺失。
- A 股手续费包含卖出印花税，期货只有手续费，对比跨市场 run 时口径不同。
- metrics.csv 是单行多列汇总，不能按“每行一笔交易”理解，trades.csv 才是逐笔事件。
- run_card 与 digest 需要重建才会出现新字段。
