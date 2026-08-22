# Vibe-Trading 工作计划日志

> 计划文档 = 开工前契约；ITERATION_LOG = 完工后记忆；HowToUse = 使用手册。项目规则见项目根 AGENTS.md。本目录随源码仓库 git 管理。

## 状态

- 讨论中：未确认，禁止改业务代码
- 已确认：开工前核对通过 + 用户确认，可以照文档实现
- 已完成：状态归档，文件留在原地，不移动
- 已废弃：讨论中止或用户放弃；保留文件，不再当作活跃计划；计划文档头部标注“已废弃，见计划 README”，不写 ITERATION_LOG
- 兜底：状态缺失、状态不明或与执行清单不一致 = 讨论中

## 双向关联（收尾时互填）

- 计划文档 `关联迭代` 填 V 号；ITERATION_LOG `关联` 填计划编号 P-...

## 优化系列索引

| 系列 | 完整迭代链 | 当前 | 下一方向 |
|---|---|---|---|
| 逻辑标的 / 金字塔加仓 | P-20260818-single_weight_group → P-20260819-logical_symbol_groups（A） → B-native-pyramid-legs | A | B |

## 计划索引

| 编号 | 状态 | 日期 | 标题 | 文件 | 关联迭代 |
|---|---|---|---|---|---|
| P-20260814-timeline_charts_fix | 已完成 | 2026-08-14 | 回测分析时间精度与小周期图表修复 | P-20260814-timeline_charts_fix.md | V018 |
| P-20260814-trade_action_ui | 已完成 | 2026-08-14 | 交易方向与开平动作展示（图表 + 交易表） | P-20260814-trade_action_ui.md | V020 |
| P-20260814-total_commission | 已完成 | 2026-08-14 | 总手续费与单边手续费落盘展示 | P-20260814-total_commission.md | V024 |
| P-20260815-futures_stop_tick | 已完成 | 2026-08-15 | 期货止损成交价按最小变动价位取整 | P-20260815-futures_stop_tick.md | V026 |
| P-20260816-chart_window_preserve | 已完成 | 2026-08-16 | 图表页保持行情可视时间窗口 | P-20260816-chart_window_preserve.md | V027 / V028 |
| P-20260816-contract_switch_auto | 讨论中 | 2026-08-16 | 换约规则自动识别主连切换日 | P-20260816-contract_switch_auto.md | 待填 |
| P-20260816-cache_env_once | 已完成 | 2026-08-16 | loader 缓存只配置一次（直跑 runner 也加载 vibe_home/.env） | P-20260816-cache_env_once.md | V042 |
| P-20260817-reports_dir_selector | 讨论中 | 2026-08-17 | WebUI 报告页目录选择器（支持 runs 子目录分类） | P-20260817-reports_dir_selector.md | 待填 |
| P-20260817-trade_log_full_load | 已完成 | 2026-08-17 | WebUI 交易明细一键加载全部（统计刷新，默认仍截断 500） | P-20260817-trade_log_full_load.md | V039 / V040 |
| P-20260817-fastrun | 已完成 | 2026-08-17 | 回测 fastrun：--without-regime / --without-mae-mfe / --fastrun 跳过 digest 分析 | P-20260817-fastrun.md | V032 |
| P-20260818-single_weight_group | 已完成 | 2026-08-18 | max_single_weight 按策略声明 weight_groups 分组合并（加仓计单标的口径） | P-20260818-single_weight_group.md | V033 |
| P-20260818-daily_position_risk_charts | 已完成 | 2026-08-18 | 新 tab「持仓与风险」：每日组合持仓（收盘口径）+ 账户风险度（单边+100%线）；上线后迭代图 1 改收盘口径 | P-20260818-daily_position_risk_charts.md | V034 / V035 |
| P-20260818-position_weight_magnitude | 讨论中 | 2026-08-18 | 指标区最大组合/单票仓位与持仓与风险 Tab 统一为多空完整口径（兼容多标的） | P-20260818-position_weight_magnitude.md | 待填 |
| P-20260818-daily_position_risk_charts_v2 | 已完成 | 2026-08-18 | 单标的每日持仓图（持仓与风险 tab v2：下拉框按需加载，收盘默认/峰值切换） | P-20260818-daily_position_risk_charts_v2.md | V036 |
| P-20260818-chart_current_interval | 已废弃 | 2026-08-18 | 报告页行情 K 线增加当前回测周期（范围已收敛为仅 4H，见 P-20260819-chart_4h_interval） | P-20260818-chart_current_interval.md | 待填 |
| P-20260818-backtest_2h_interval | 已废弃 | 2026-08-18 | 回测引擎支持 2H（两小时）周期（独立计划已并入交易时间聚合议题） | P-20260818-backtest_2h_interval.md | 待填 |
| P-20260818-trading_time_aggregation | 讨论中 | 2026-08-18 | 回测与前端支持按交易时间聚合（同花顺式，可选开关，默认自然时间兼容） | P-20260818-trading_time_aggregation.md | 待填 |
| P-20260819-chart_4h_interval | 已完成 | 2026-08-19 | 报告页行情 K 线增加 4H 周期（与 1D 同级） | P-20260819-chart_4h_interval.md | V037 |
| P-20260819-logical_symbol_groups | 已完成 | 2026-08-19 | A方案：config 驱动逻辑标的分组，兼容伪单位加仓与多标的图表 | P-20260819-logical_symbol_groups.md | V038 |
| P-20260820-execution_mode_state_machine | 讨论中 | 2026-08-20 | 回测引擎正常交易与止损成交路径解耦 | P-20260820-execution_mode_state_machine.md | 待填 |
| P-20260822-mcp_backtest_workflow | 讨论中 | 2026-08-22 | MCP 回测模式与外部 Agent 协作工作流 | P-20260822-mcp_backtest_workflow.md | 待填 |

