# 计划：单标的加仓权重聚合——max_single_weight 按策略声明分组

> 编号：P-20260818-single_weight_group
> 状态：已完成
> 日期：2026-08-18
> 关联迭代：V033
> 关联：commit `8ee5f0b`；run `ta_turtle_4h_v438_swg_2014_2023`

## 项目调研

- `max_single_weight` / `max_portfolio_weight` 计算位于 `agent/backtest/engines/base.py:912-916`：组合 = `target_pos.sum(axis=1)`（带符号求和），单票 = `target_pos.max(axis=1).max()`（单 code 权重峰值）。TA 策略用 4 个伪单位（TA0001-0004.ZCE）表达加仓，故单票口径 4.88% ≠ 组合口径 14.18%（4 单位权重之和）。
- 指标链路：base.py 的 `m` 字典 → `metrics.csv`（base.py:1543-1544）与 `write_run_card`（base.py:988-997）→ run_card.json/md；digest 与 WebUI 只读产物（digest.py 读 metrics.csv/trades.csv，前端 formatters.ts 只做显示格式化）。改 base.py 一处，三处产物自动同步。
- 伪单位事实基础：`~/.vibe-trading/data-bridge/config.yaml` 中 TA0001-0006.ZCE 六条 symbol 全部指向同一 `TA_1m.csv`（共享同一标的行情）。
- `_validate_signal_engine_class`（runner.py:505）只校验 `__init__` 无必选参数 + 有 `generate()` 方法，策略新增类属性 `weight_groups` 不会被校验拒绝。
- 现有测试：`test_engine_robustness.py:739` 单 code 策略断言 `max_single_weight == 1.0`——无分组声明时保持单 code 口径，不受影响。

## 需求目标

- 做什么：让引擎支持"同一标的的加仓（伪单位 codes）按单标的聚合"——策略在 `signal_engine.py` 里声明 `weight_groups`（dict：组名 → [codes]），引擎计算 `max_single_weight` 时按组**带符号求和**取峰值；无声明时维持现状（单 code 口径）。
- 范围 / 边界：
  - 只改引擎指标计算（base.py）、digest 释义、新增测试与文档；**不改 config schema、不改执行/成交逻辑、不改其他指标**（avg/max_portfolio_weight、risk_xray、by_symbol 等）。
  - 聚合口径 = 带符号求和（净敞口），与 `max_portfolio_weight` 口径一致。
  - 未声明分组的 code 保持单 code 一组（向后兼容，默认行为零变化）。
  - 旧 run 产物不动；仅新 run 生效。
- 验收标准：
  - TA 4 伪单位 run：声明 `weight_groups` 后 `max_single_weight == max_portfolio_weight`（同向持仓时自然相等）。
  - 无声明 run：指标与改动前一致（现有测试通过）。
  - 同组内出现反向持仓（人为构造）：`max_single_weight` = 组内净敞口峰值（多空抵消），不是毛敞口。
  - metrics.csv / run_card.json / run_card.md 三处同步反映新值。

## 实现方案

1. `agent/backtest/engines/base.py` 新增辅助函数 `_single_weight_by_group(target_pos, weight_groups)`：
   - `weight_groups` 为空 / None → 原样返回 `target_pos`；
   - 构建 code → 组名映射（未声明 code 以自身为组名，保持单 code 口径）；同一 code 出现在多个组 → 取最后一个并 `print` warning；
   - 按组对 `target_pos` 列做带符号求和（`target_pos.T.groupby(groups).sum().T`），返回聚合后 DataFrame。
2. base.py metrics 段（912-916 行）接入：
   ```python
   position_weight_series = target_pos.sum(axis=1)
   if len(position_weight_series):
       m["avg_portfolio_weight"] = float(position_weight_series.mean())
       m["max_portfolio_weight"] = float(position_weight_series.max())
       groups = getattr(signal_engine, "weight_groups", None)
       single_pos = _single_weight_by_group(target_pos, groups)
       m["max_single_weight"] = float(single_pos.max(axis=1).max())
   ```
3. `agent/backtest/analysis/digest.py:119-120` 中文释义更新：`max_single_weight` 由"单票最大目标仓位"改为"单标的最大目标仓位（策略 weight_groups 分组聚合口径，未声明时按单代码）"。
4. 测试（`agent/tests/test_engine_robustness.py` 新增）：
   - 两 code 同组同向 → `max_single == max_portfolio`；
   - 两 code 同组反向 → `max_single` = 净敞口峰值（小于毛敞口）；
   - 部分 code 未声明 → 未声明 code 保持单 code 口径；
   - 无 `weight_groups` → 与现行为一致。
5. HowToUse FAQ 新增 8.43 与 8.44（见执行清单第 5 步）。

## 执行清单

1. base.py：新增 `_single_weight_by_group` + metrics 段接入（含重复映射 warning）。
2. digest.py 释义更新。
3. 新增测试（test_engine_robustness.py）。
4. 验证：pytest 相关用例 + TA 4 伪单位 run 实测 `max_single == max_portfolio`，确认 metrics.csv / run_card.md 同步。
5. HowToUse FAQ 8.43（加仓如何算为单标的持仓，写清策略代码 `weight_groups` 怎么填）与 8.44（同标的相反方向持仓仓位怎么算：净敞口口径、期货单边保证金对应、锁仓 ≠ 平仓），并写明两点注意（策略侧声明为硬编码、反向持仓时单票与组合口径可能不一致）。
6. 收尾：ITERATION_LOG 新增 V033 + 计划 README 表更新（状态已完成、关联迭代）+ 计划文档状态与关联补全。

## 开工前核对

- 需求目标 / 范围与讨论记录一致：通过（方案 B 策略声明 + 带符号求和，用户 2026-08-18 确认）
- 范围/边界无被后续讨论反转但仍保留的旧约束：通过（未采用 config 字段方案，无残留约束）
- 执行清单覆盖需求目标与验收标准：通过
- 验收标准可验证：通过（TA run 对比 + 构造反向持仓用例）
- 元信息已填（关联允许为待填）：通过

## 验证

- `cd agent && python -m pytest tests/test_engine_robustness.py -k "weight"` 及引擎相关全量。
- TA 4 伪单位 run（如 ta_turtle_4h_v438_2014_2023 的 signal_engine 加 `weight_groups`）用 fastrun 重跑，断言 `max_single_weight == max_portfolio_weight`（14.18%），并核对 metrics.csv / run_card.md 同步。
- 无声明 run 回归：现有测试全绿即默认行为零变化。

## 讨论记录

- 2026-08-18 用户提问：V438 WebUI 报告 `max_portfolio_weight`(14.18%) 与 `max_single_weight`(4.88%) 为何不等 → 结论：4 个伪单位权重之和 vs 单 code 权重峰值，不矛盾。
- 2026-08-18 用户要求调研：把同一标的加仓视为同一标的，让 `max_single_weight` 也等于 14.18%（RUNCARD/metrics.csv 同步），好不好实现 → 调研结论：好实现，改动集中在 base.py 一处，metrics.csv / run_card 自动同步。
- 2026-08-18 拍板 1（分组来源）：方案 B——策略文件 `signal_engine.py` 声明 `weight_groups` 属性，引擎读取聚合；不用 config.json 字段（每次建 run 重复维护、config 塞策略语义），不在引擎写死 TA（通用引擎不为单品种开特例）。
- 2026-08-18 拍板 2（聚合口径）：带符号求和（净敞口）。依据：国内商品期货（含郑商所 TA）同合约对锁保证金按单边收取，实际占用资金与风险 = 净敞口；与 `max_portfolio_weight` 口径一致；TA 策略 4 单位恒同向，该拍板对 TA 无实际数字影响。
- 2026-08-18 用户要求：HowToUse FAQ 新增两条——①加仓如何算为单标的持仓（写清策略代码怎么填）；②同标的相反方向持仓仓位怎么算。同时提示两点必须在 HowToUse 写清：策略侧声明是硬编码；同标的有反向持仓时仓位显示可能让人误会。

## 风险 / 注意

- 策略侧硬编码声明：`weight_groups` 在策略文件里写死，若换标的 / 换分组未同步声明，聚合口径会错——HowToUse 8.43 写明"声明必须与 codes 保持一致"。
- 反向持仓时"单票仓位"（组内净敞口）与"组合仓位"（全组净敞口之和）可能不一致，单票净敞口可大于组合净敞口——HowToUse 8.44 写明口径与场景。
- 重复映射（同一 code 声明在多个组）只打印 warning 不阻断，属策略声明错误。
- 本次只改 `max_single_weight`；`by_symbol_stats`、positions.csv、risk_xray 等仍按 code 口径，不随本次改动。
