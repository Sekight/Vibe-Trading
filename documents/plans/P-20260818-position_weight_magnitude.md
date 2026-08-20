# 计划：指标区最大组合/单票仓位与「持仓与风险」Tab 统一为多空完整口径（兼容多标的）

> 编号：P-20260818-position_weight_magnitude
> 状态：讨论中
> 日期：2026-08-18
> 关联迭代：待填（收尾时填 V 号）
> 关联：commit / run（收尾时补）

## 项目调研

- 现状口径（`agent/backtest/engines/base.py` metrics 段）：`avg_portfolio_weight` = `target_pos.sum(axis=1).mean()`、`max_portfolio_weight` = `.max()`、`max_single_weight`（V038 后）= 按 `config.logical_groups` 分组带符号求和后 `.max()`——三者都是**净敞口（带符号）**口径；且 `max` 聚合会丢弃空头日（负值）→ **最大类指标只反映多头侧峰值**。
- V034 已实现与用户观察需求**同口径**的数据：digest `daily_position`（毛 `sum|w|` / 净 `sum w` / 单边=按组取多空大边，日取峰值）与 `daily_risk`，图 1/图 2 已按此渲染。**指标区与图的数据口径不一致**（指标净敞口 vs 图毛/单边）是用户困惑根源。
- 本次实测（v437fix9，2024-2026）：`metrics.csv` 的 `max_portfolio_weight` / `max_single_weight` 为 10.91%，而同一份 `positions.csv` 经「持仓与风险」Tab 的毛/单边口径得到 18.75%；2024-07-23 为空头峰值 -18.75%，2026-03-04 为多头峰值 +10.91%。这不是 config 分组错误，而是指标区最大值聚合丢弃负向峰值的现存 bug。
- 多标的场景口径行为（关键分析，用户提出 RB 多 + TA 空 + FG 多）：
  - **毛持仓** = `sum|w|` = 所有标的多空权重绝对值之和 → **总资金占用量**（多空都算）；
  - **单边**（按 `config.logical_groups` 组内取 max(多头和,|空头和|) 跨组合计）= 各标的各自的大边之和 → **真实保证金占用**（按期货"同一合约对锁单边收保证金"）。**多标的且各标的方向独立时，单边 = 毛**（组间不互抵）；两者只在"同一标的内多空并存（锁仓）"时不同（单边 < 毛）；
  - **净敞口** = `sum w` = 多空相抵后的**市场风险净暴露**（RB +0.1 + TA -0.08 + FG +0.12 → +0.14）。
- 用户观察目标（不关乎多空）：①平均每天资金利用率 = avg 毛持仓；②持仓最大时用了多少仓位 = max 毛持仓；③哪个单票仓位最大 = 单票（按 `config.logical_groups` 分组）单边权重峰值。三者恰好都是**毛/单边口径**，与 V034 图 1 一致，与现有净敞口指标区不同。
- 逐标的观察的性能边界（V034 已实测）：组合级序列（2400 点 ≈ 96KB）可进 digest；全标的逐标的序列（100 标的 × 2400 天 ≈ 24 万点 ≈ 8.9MB）不得进 digest，需 API 现读 positions.csv 按需返回（V034 已记为二期可迭代点）。

## 需求目标

- 做什么：让指标区（`avg_portfolio_weight` / `max_portfolio_weight` / `max_single_weight`）能回答用户三个资金管理问题，**口径从"净敞口"改为"毛/单边（不关乎多空）"**：
  1. `avg_portfolio_weight` → 平均资金利用率 = avg(毛持仓 `sum|w|`)（恒正，可改指标名或保留名+文档说明）；
  2. `max_portfolio_weight` → 持仓最大时的仓位占用 = max(毛持仓)（v437fixB：20.97% → 41.28%）；
  3. `max_single_weight` → 最大单票仓位 = 按 `config.logical_groups` 分组后各组单边权重的峰值（多空都算），**并指出是哪个标的**（新增 companion 字段或指标）。
- 范围 / 边界：
  - 只改引擎指标计算（base.py metrics 段）+ digest 摘要口径 + 文档 + 测试；**不动** V034 的 digest 序列/图（它们已是毛/单边口径，直接复用）。
  - `avg_portfolio_weight` 改毛口径后，"平均净敞口方向"信息丢失——通过 V034 图 1 净持仓线保留；是否新增 `avg_net_weight` 待拍板。
  - 旧 run 指标不重跑保持旧值；新 run 新口径（指标语义变更需文档与 HowToUse 同步，向后兼容说明）。
  - 多标的**逐标的**观察（每标的持仓叠加/下拉框）本期是否做待拍板（V034 二期可迭代点）。
- 验收标准（待拍板后细化）：
  - v437fixB 重跑：`max_portfolio_weight` = 41.28%（空头侧），`avg_portfolio_weight` = avg(毛)（1.80% 量级，非 -0.49%），`max_single_weight` = 41.28% 且指向 TA；
  - 多标的合成 run：RB 多 + TA 空 + FG 多 → 毛 = 单边 = 三标的绝对值之和、净 = 带符号和；`max_single_weight` 返回最大那个标的及其值；
  - 无 `logical_groups` 的单标 run：单票口径退回单 code 毛口径；
  - 旧指标字段兼容（旧 run 读旧值不崩）。

## 实现方案（讨论中）

1. **base.py metrics 段**：
   - `avg_portfolio_weight` = `target_pos.abs().sum(axis=1).mean()`（毛口径平均）；
   - `max_portfolio_weight` = `target_pos.abs().sum(axis=1).max()`（毛口径峰值）；
   - `max_single_weight` = 按 `config.logical_groups` 分组后各组单边（max(多头和,|空头和|)）逐 bar 求值，再取全局峰值；新增 `max_single_weight_code`（峰值对应标的/组名）→ 落到 metrics/run_card/digest。
   - 复用 V033 的 `_single_weight_by_group` 思路或提取共享函数（与 digest 的 `daily_position_and_risk` 单边逻辑一致，避免两处口径漂移）。
2. **digest.py**：`position_risk_summary` 与 LLM 摘要同步（毛/单边口径已一致，仅确认字段映射）；`_metric_meaning` 文案更新。
3. **多标的逐标的观察**（待拍板做不做）：
   - 若做：V034 二期可迭代点落地——API 现读 positions.csv 按标的返回序列 + 前端下拉框；组合级不动。
   - 若不做：`max_single_weight_code` 给出"哪个标的"，组合级先够用。
4. **文档**：HowToUse 8.27（指标口径段落重写：三个指标改为毛/单边、avg 语义、max 指向空头侧）+ 8.45 联动；ITERATION_LOG；计划收尾。
5. **测试**：指标口径断言（多空日、多标的合成 run、无 `logical_groups` 回退、旧 run 兼容）。

## 执行清单

（待拍板后细化）

## 开工前核对

（待拍板；当前讨论中，禁止改业务代码）

## 验证

（待拍板后补全）

## 讨论记录

- 2026-08-18 用户提出：V034 图里 2014-01-24 空头 41.28% vs 指标区 max_portfolio_weight 20.97% 不一致 → 评估结论：图 1 毛/单边多空都算（无 bug）；指标区 max 类指标是"净敞口最大正值"，`max` 丢弃空头日（-41.28% 取不到）——**历史遗留口径缺陷**（2026-08-11 指标改名时即如此），V033/V034 未引入也未修复，属**独立需求**。
- 2026-08-18 用户划界确认：V033 只要求"单票最大持仓算对"（加仓聚合），未要求修"max 只看多头"的老问题；老问题是另一个需求 → 本计划。
- 2026-08-18 用户明确观察目标（不关乎多空）：①平均每天资金利用率；②持仓最大时的仓位占用；③哪个单票仓位最大。并给出多标的场景（同账户 3-4 标的，RB 多 + TA 空 + FG 多）。
- 2026-08-18 评估（Codex/ZCode）：用户三点观察需求 = **毛/单边口径**（不关乎多空），与 V034 图 1 口径一致、与指标区净敞口口径不同；多标的下毛=单边（除非同标的锁仓）、净敞口多空相抵；`max_single_weight` 需指出"哪个标的"（新增 companion 字段）；逐标的观察= V034 二期可迭代点（性能边界已实测：全标的 8.9MB 不得进 digest）。
- 2026-08-19 用户确认：本问题按 bug 处理；报告顶部 `metrics.csv` 的“最大组合持仓 / 单票最大持仓”应与 WebUI「持仓与风险」Tab 的多空完整口径一致，后续实现以 Tab 图表使用的毛/单边聚合为准；本计划继续保持“讨论中”，暂不改业务代码。
- 待拍板点：
  1. `avg_portfolio_weight` 改毛口径后，是否新增 `avg_net_weight`（净敞口平均）保留方向信息？（倾向不加，图 1 净线已够；或加，成本低）
  2. `max_single_weight_code` 命名与展示（指标区/run_card/digest 都带？）；
  3. 本期是否一并落地逐标的观察（V034 二期：API 按需 + 下拉框）？（倾向本期不做，先组合级 + 标的指向；多标的策略上线前再做）
  4. 指标名是否改（如 avg_portfolio_weight → 平均资金利用率）还是保留原名+文档说明？（倾向保留原名，避免破坏已有引用/对比）
  5. 指标区 `avg_portfolio_weight` 用收盘毛、`max_portfolio_weight` 用峰值毛确认？（倾向是，与图 1/图 2 职责对齐；图 1 是否改收盘口径见 P-20260818-daily_position_risk_charts 讨论记录——上线后迭代）

## 风险 / 注意

- 指标口径变更影响历史对比：新 run 的 max_portfolio_weight 会从"多头峰值"变成"多空都算的峰值"（v437fixB 20.97%→41.28%），旧 run 不重跑保持旧值——HowToUse 需写明"2026-08-18 起新 run 口径"。
- 引擎"目标权重"是开仓时定的比例，浮亏时真实资金利用率会随权益被动上升（引擎不模拟逐日盯市）——avg/max 毛口径反映"策略目标层面占用"，非真实逐日资金利用率，需文档注明（与 V034 8.45 一致）。
- 单边口径依赖 `config.logical_groups` 配置：无配置时单票 = 单 code 毛口径（V038 已定义回退）。
- 两处单边实现（base.py metrics 与 digest 聚合）必须同口径，避免漂移——提取共享函数。
