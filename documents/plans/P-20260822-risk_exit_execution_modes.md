# 计划：正常出场与保护性止损执行模式重构

> 编号：P-20260822-risk_exit_execution_modes
> 状态：已完成
> 日期：2026-08-22
> 关联迭代：V043
> 关联：Mistake_Journal M035；前置计划 P-20260820-execution_mode_state_machine（已废弃）；工作区验证完成，尚未提交 commit

## 项目调研

- 旧计划 P-20260820-execution_mode_state_machine 已废弃：原方案让 `entry_mode` 同时控制正常开仓和正常平仓，再让 `exit_mode=stop` 插入止损逻辑；该方案虽然能覆盖部分组合，但字段职责不正交，继续扩展会让普通出场和保护止损相互耦合。
- 当前 `agent/backtest/engines/base.py`：`_same_bar` 由 `entry_mode` 派生；`_align()` 用它决定整条 target signal 是否 shift；`_open_fill_price()` 和 `_close_fill_price()` 也共用它。因此当前代码的正常开仓、正常信号平仓和止损填价仍由一套状态控制。
- 当前 `BaseEngine`：`exit_mode="stop"` 只在 `entry_mode="close"` 时加载 `stop_prices`，且 `_close_fill_price()` 只在已有 target 平仓/反转信号进入 `_rebalance()` 时被调用；止损不是独立的持仓级触发器。`next_open/stop` 当前直接被组合白名单拒绝。
- 当前 `_rebalance()`：已有同方向 `Position` 时不会按新的 target weight 调整 size；项目现有金字塔加仓通过多个伪单位 code 表示，每个伪单位是独立执行 Position，`logical_groups` 只负责逻辑展示聚合。
- 当前文档与目标语义：HowToUse 8.34 和 V003 仍使用旧的二元 `entry_mode/exit_mode` 解释；本计划以代码重构后的新语义为准，旧字段的兼容映射必须显式处理，不能静默改变旧 run 的结果。
- 当前 sizing 事实：`BaseEngine._plan_open_order()` 已经在实际执行 bar 使用实际 fill price 计算目标权重对应的 size，但公式是 `target_weight × equity × leverage`，不是按止损距离计算风险手数；策略没有返回 qty/risk intent 的标准契约。
- 当前策略接口事实：`SignalEngine.generate(data_map)` 在回测前一次性调用，没有 next-open 成交回调；策略可以计算 ATR 和输出自定义序列，但不能在看到下一根实际开盘后再回到策略方法重新计算手数。
- 既有基线（2026-08-20）：回测执行/市场引擎/执行时序定向测试 `396 passed, 2 skipped`；现有测试尚未覆盖独立 active stop、`next_open/stop`、普通平仓与硬止损同 bar 冲突、止损状态更新等场景。本期实现后同一核心回归集合为 `412 passed, 2 skipped`。

## 需求目标

- 将执行职责拆成三个互相独立的配置维度：
  - `entry_mode`：正常开仓、加仓的成交路径；允许 `next_open` / `close`。
  - `exit_mode`：正常信号平仓、止盈信号、减仓、反转时平旧仓的成交路径；允许 `next_open` / `close`。
  - `stop_loss_mode`：引擎保护性止损策略；第一期只允许 `none` / `hard`。
- 保持并支持以下四个常用 preset（旧组合写法只是简写，不再把 `stop` 塞进 `exit_mode`）：

  | preset | entry_mode | exit_mode | stop_loss_mode |
  |---|---|---|---|
  | `next_open/next_open` | `next_open` | `next_open` | `none` |
  | `close/close` | `close` | `close` | `none` |
  | `close/stop` | `close` | `close` | `hard` |
  | `next_open/stop` | `next_open` | `next_open` | `hard` |

- `stop_loss_mode=hard` 的语义：持仓建立后维护 active stop；价格触及保护价时，不等待策略 target 变为 0，独立生成止损平仓；止损优先于普通信号平仓。
- 第一阶段暂不开放以下正常出场非对称组合：
  - `entry_mode=next_open` + `exit_mode=close`；
  - `entry_mode=close` + `exit_mode=next_open`。
  这两个组合保留为未来能力，不能因为暂不开放就把它们判定为不合理。
- 第一阶段不对外增加 `take_profit_mode`；内部设计预留通用风险退出状态，使未来可增加硬止盈而不重写止损管线。
- 加仓范围：第一期沿用当前伪单位 code 的执行模型；同一 symbol 的真实 partial add/reduce 不在本计划内。
- next-open 以损定量范围：本期不实现“实际 next-open 入场价确定后，再按 stop distance/risk budget 计算手数和绝对止损价”；`next_open/stop` 只消费策略在信号阶段已经提供的绝对 `stop_prices`，仓位继续按现有 target-weight sizing。
- 验收标准（一句话）：正常订单只读取 `entry_mode` / `exit_mode`，硬止损只读取 `stop_loss_mode`，四个 preset 的信号成交、硬止损、反转、跳空和市场规则行为均可独立验证。

## 实现方案

### 1. 配置与执行语义

1. 新增公共 execution profile / validator，分别校验 `entry_mode`、`exit_mode` 和 `stop_loss_mode`；二元组合集合只用于拒绝本期暂不开放的非对称 normal pair，不再承担 normal/stop 的内部语义。
2. `entry_mode` 只进入 normal open/add handler；`exit_mode` 只进入 normal close/reduce/reversal handler；`stop_loss_mode` 只进入 protective stop handler。
3. 三条路径可以共用最终的资金释放、手续费、TradeRecord 记账函数，但不共用“是否触发、何时成交、成交价如何确定”的判断分支。
4. 旧配置兼容建议：
   - 缺少新字段：默认 `entry_mode=next_open`、`exit_mode=next_open`、`stop_loss_mode=none`，保持旧默认行为；
   - 新配置使用 `entry_mode=close`、`exit_mode=close`、`stop_loss_mode=hard` 表达原来的 `close/stop` 意图；
   - 新配置不再支持 `exit_mode=stop`：runner 检测到后应在加载数据/策略前失败，并返回明确的迁移 warning；旧配置文件保留，不自动改写。必要时通过 execution schema version 区分旧的“信号触发止损填价”和新的“独立保护止损”。

### 2. 正常订单管线

- 原始 SignalEngine target 先形成正常目标变化：开仓、伪单位加仓、减仓、正常止盈/出场、反转。
- `next_open` 正常动作建立 pending order，在下一根该 symbol 的实际 bar 开盘成交；不能只依赖一条整体 shift 后的 target 矩阵来隐藏订单状态。
- `close` 正常动作在当前决策 bar 收盘执行。
- 反转固定为：先处理旧仓 normal close，再处理新方向 normal open；旧仓受 T+1、涨跌停或其他市场规则阻塞时，不得开新方向仓。
- 同一 symbol 真实同方向 target weight 改变仍不在本期实现；伪单位新 code 的加仓按独立 normal open 处理。

### 3. 硬止损管线（P0）

- `stop_loss_mode=none`：不建立引擎保护止损；策略自己把 target 改为 0 的动作仍属于 normal exit，按 `exit_mode` 成交。
- `stop_loss_mode=hard`：策略通过 `stop_prices` 提供每个 code 的候选保护价；引擎在持仓建立后维护 active stop，不依赖 target 平仓信号。
- 入场当根 stop 按 entry phase 落地：`close` 入场不能回看入场前已经走完的 low/high，从下一根 bar 监控；`next_open` 入场在开盘成交后立即监控当根 bar。
- `next_open` 入场若开盘已经穿过 stop（多单 `open < stop`、空单 `open > stop`），取消 pending entry，不入场、不生成止损交易、不产生双边手续费；这是本次用户确认的实盘规则。若开盘没有穿 stop，但入场后当根 low/high 触发，则先按开盘入场，再按 hard-stop 规则退出。
- 新 stop 价在当前 bar 收盘形成，默认下一根 bar 才更新 active stop；当前 bar 先使用已经激活的旧 stop，避免 M023 的同 bar 回溯假象。也就是说，“下一根生效”只针对新 stop 更新，不会让已经存在的 stop 在当前 bar 失效。
- `NaN` 默认表示本 bar 不更新，沿用上一个有效 active stop；如果策略需要主动撤销止损，不能复用 NaN，需增加显式 stop cancel 语义。
- 多单：`low <= stop` 触发；空单：`high >= stop` 触发。
- 跳空：多单 `open < stop` 按实际 open，空单 `open > stop` 按实际 open；非跳空按 stop 价，并应用已有方向感知滑点和期货 tick 规则。
- 硬止损优先于 normal exit；同一 bar 只允许一笔平仓，reason 必须是 `stop`。默认不允许止损后同 bar 重新开仓。
- 市场规则阻止止损成交时，不能把“触发”当成“已平仓”；保留持仓并记录 blocked/retry 语义。
- 日线 OHLC 的 hard stop 是 bar 级近似，不等同于真实 tick 级立即成交；报告和文档必须如实说明。

### 4. 未来通用风险退出预留（本期不开放）

- 内部建议抽象为 `RiskExitState` / `RiskExitOrder`，目前只填 stop 字段，未来可增加 `take_profit_prices`。
- 未来硬止盈建议新增 `take_profit_mode=none|hard`，而不是让普通 `exit_mode` 或 `target_profit_mode` 承担两种职责。
- 硬止盈未来还需单独定义跳空穿越、同 bar 止损与止盈同时触发、tick 取整和同 bar 再入场；在这些规则未拍板前不加入本期验收。

### 5. 市场规则与产物

- `can_execute()` / `prospective_fill_price()` 的 hard-stop 路径通过引擎当前 fill phase 与原始成交价 override 传递明确的止损成交上下文；市场规则不再用普通 `_same_bar` 路径猜测止损应按开盘还是 stop 价检查。
- 同步覆盖 A 股/印度 T+1、A 股/印度/韩国/期货涨跌停、期货 tick、Composite 子引擎和 Crypto strict 的成交证据来源。
- 当前源码事实：`TradeRecord` 只有 `exit_reason`；`_rebalance()` 普通平仓固定传 `signal`；`_write_artifacts()` 的入场行也固定写 `reason=signal`，所以当前 CSV 中无法区分入场原因、普通出场和“止损价成交但由 signal 触发”的情况。
- 本期简化方案：不新增 `fill_phase`、`action` 或 signal time；继续使用已有 `reason`，但修正其来源，至少区分 `signal`、`stop`、`liquidation`、`end_of_backtest`。成交是 next-open、close 还是 stop price，本期按 K 线时间、价格和配置解释，不单独扩展字段。
- 后续若需要严格审计，再增加 `action` / `fill_mode` / `entry_reason`；其中 `fill_phase` 表示“订单最终以什么成交路径成交”，不是“为什么交易”，但不进入本期验收。
- `positions.csv` 继续表示目标权重，不承诺已成交；pending、blocked 和 stop 强平以交易明细为准。

### 6. 策略层与引擎层职责

| 事项 | 策略层 | 引擎层 |
|---|---|---|
| 止损价如何计算 | 负责，输出 `stop_prices` | 不改价、不强制收紧或放宽 |
| 止损是否允许放宽 | 负责，策略输出新的候选价 | 只按策略给出的价更新 active stop |
| 新 stop 何时生效 | 提供本 bar 候选值 | 规定下一 bar 生效，避免回看当前 bar |
| 持仓是否真实建立 | 无法确认，当前接口无成交回调 | 负责，只有实际 fill 后才激活 stop |
| next-open gap 后取消/保留入场 | 当前 SignalEngine 无法基于未来开盘决定 | 负责执行政策；如要策略决定，需扩展订单/成交回调接口 |
| 触发、跳空、市场限制、优先级 | 不负责 | 负责硬止损实际触发与成交 |

当前策略接口是一次性 `generate(data_map)`，策略可以在内部用 pandas/numpy 计算任意动态 stop，也可以自行限制 stop 不放宽；但它不能在 next-open 订单实际成交后收到回调。因此“策略决定止损价”与“引擎决定止损执行”必须保留边界。

### 7. 以损定量与依赖实际入场价的止损

- 典型公式“止损价 = 实际入场价 - 2 × ATR”不能让策略在信号 bar 直接产出绝对 stop price：next-open 的实际入场价此时未知。若策略偷看下一根 open，会引入未来函数。
- 推荐新增可选的风险意图，而不是增加策略回调：策略在信号 bar 输出已知的 `stop_distance`（例如 `2 × ATR`）和 `risk_budget`/风险比例；pending order 携带这份快照到实际成交 bar。
- 引擎在 next-open 实际 fill 后计算：
  1. 以实际成交价（含本引擎最终记账的滑点口径）确定 active stop；
  2. 以实际 entry-stop 距离、合约乘数/股数单位、手续费、滑点、保证金和仓位上限计算 size；
  3. 创建 Position 与 active stop；若入场当根触发，继续按已拍板的 hard-stop 规则处理。
- `target_weight` sizing 与 risk-based sizing 应是两个显式模式，默认仍为现有 `target_weight`，不能在策略同时输出风险意图时静默覆盖旧仓位计算。
- 策略仍负责 ATR、止损距离公式、风险预算和是否放宽；引擎负责实际价格相关的 size/stop 换算、市场规则和成交。只有策略需要“成交后改变下一步策略状态”等更复杂能力时，才需要新增 fill callback/事件式 SignalEngine，第一期不建议引入。
- 本期明确不实现这项能力；本计划的 `next_open/stop` 只支持“策略预先提供绝对 stop price、引擎执行硬止损”，不承诺依赖实际 next-open 入场价的 stop distance/风险手数。

## 后续迭代方向：next-open 以损定量

本期刻意不做 next-open 实际成交后的以损定量，但保留本次调研作为后续迭代准备。当前局限是：策略在 `generate(data_map)` 一次性运行时不知道下一根实际 open，不能因实际 entry price 计算绝对 stop，也不能据此计算最终 lots；当前引擎只按 target weight sizing。

后续若要补齐，建议研究和拆分以下能力：

1. 策略风险意图契约：策略输出信号 bar 已知的 `stop_distance`（如 `2×ATR`）、`risk_fraction`/`risk_budget` 和必要的伪单位/加仓意图，不输出假定 close 成交后的 lots。
2. pending order 快照：next-open 订单携带风险意图到实际成交 bar；信号 bar 的 ATR/距离冻结，不能用下一根 bar 的数据回看信号。
3. fill-time sizing：引擎取得实际 entry fill（含滑点口径）后计算 stop price、单手风险、手续费、乘数、保证金、tick/lot 取整和组合风险上限，再决定是否能开仓。
4. entry-gap policy：本期已确定“开盘穿过绝对 stop 则取消入场”；未来需明确当 stop distance 依赖实际 entry 时，取消判断使用入场前候选 stop、开盘推导 stop，还是采用 bracket order 语义。
5. 策略状态同步：当前 SignalEngine 没有 fill callback；如果加仓触发、base entry、equity 或后续信号必须依赖真实成交，需要评估事件式 SignalEngine / fill callback，或把持仓状态迁移到引擎。
6. 伪单位与组合风险：每个 pseudo-unit 的风险预算、同一逻辑组上限、已有 active stop、加仓后总风险和失败/阻塞订单都要能与引擎实际 Position 对齐。
7. 迁移验证：对同一策略并排比较 current-close、next-open target-weight、next-open risk-based 三种结果，区分执行模型变化与策略逻辑变化，不能直接拿收益率作优劣结论。

## 执行清单

1. 冻结三字段名称、四个 preset、旧配置迁移语义和 `stop_loss_mode=hard` 的优先级规则。
2. 新增公共配置校验与 execution profile，更新 runner 早失败校验。
3. 将 BaseEngine 拆成 normal order handler、pending order、active stop handler 和共享 accounting。
4. 完成 `next_open/stop` P0，以及 `close/stop` 的普通平仓/硬止损分离。
5. 保证 `next_open/next_open`、`close/close` 回归结果与默认/关闭保护止损语义一致。
6. 覆盖市场限制、跳空、反转、末 bar、warmup/backtest window、伪单位加仓和费用归因。
7. 更新 HowToUse 8.34、策略生成/SDM 契约和必要的迁移说明；不在本期增加硬止盈配置。
8. 在文档中明确 next-open 以损定量暂不支持，并把后续迭代方向留档。
9. 完成定向测试、runner smoke run，按项目规则更新 Mistake_Journal 与 ITERATION_LOG。

## 开工前核对

- 需求目标 / 范围与讨论记录一致：通过——三字段、四个 preset、`next_open/stop` P0、next-open 入场当根止损和 gap 穿止损取消入场均已实现。
- 范围/边界无被后续讨论反转但仍保留的旧约束：通过——旧计划已废弃；本期不做 next-open 以损定量、硬止盈、同一 symbol 真实 partial add/reduce 和 `fill_phase`。
- 执行清单覆盖需求目标与验收标准：通过——覆盖四 preset、normal/stop 分离、active stop、迁移、市场规则、reason 修正和伪单位加仓。
- 验收标准可验证：通过——gap、入场当根、同 bar 冲突、旧配置失败、新三字段通过和四个 smoke 均有明确测试场景。
- 元信息已填：通过——关联迭代为 V043。

## 验证

- 配置层：四个 preset 通过；`next_open/close`、`close/next_open` 明确失败；旧字段迁移 warning 可观察。新增 runner 回归确认 `next_open + next_open + hard` 三字段配置进入 schema/引擎路径。
- normal order：开仓、伪单位加仓、正常平仓/止盈、反转先平后开分别对拍 `entry_mode` / `exit_mode`。
- hard stop：无 target=0 也能触发；long/short、仅在指定 gap 条件下按 open、next-open gap 取消入场、next-open 入场当根触发、tick、同 bar 冲突、策略放宽 stop、止损被市场规则阻塞后的重试均有 synthetic tests；本期不测试 risk-based sizing。
- 回归层：核心执行/市场引擎集合 `412 passed, 2 skipped`；ChinaA/ChinaFutures/Composite/Crypto strict 相关覆盖通过；runner/security/run-card 补充集合 `86 passed`；目标源码 `py_compile` 通过。
- 工件层：`trades.csv` reason、成交时间、费用、holding bars、目标权重口径一致；缺少新字段但不含 legacy `exit_mode=stop` 的旧配置按默认模式运行，legacy stop 配置则在产物生成前明确失败。
- smoke 与迁移映射：旧真实 run `china_future_30m_v437fix9_scaled_daily_ma10_ma20_ma60_adx_combo6_portfolio60_single50_currentclose_2024_2026_07` 保持不改，runner 实测在数据加载前输出 warning 并以 exit code 1 拒绝旧 `exit_mode=stop`；旧组合与新三字段映射如下：
  - 旧 `next_open/next_open` → 新 `entry_mode=next_open`、`exit_mode=next_open`、`stop_loss_mode=none`；
  - 旧 `close/close` → 新 `entry_mode=close`、`exit_mode=close`、`stop_loss_mode=none`；
  - 旧 `close/stop` → 新 `entry_mode=close`、`exit_mode=close`、`stop_loss_mode=hard`；
  - `next_open/stop` 的新模式 → `entry_mode=next_open`、`exit_mode=next_open`、`stop_loss_mode=hard`；旧写法 `entry_mode=next_open`、`exit_mode=stop` 已验证为迁移失败并 warning，而不是当作新模式执行。
- 新增回归测试：`exit_mode=stop` legacy 配置在数据加载前失败，错误信息包含迁移提示；对应三字段配置通过 schema 校验并进入引擎执行路径；`trades.csv` 的 hard stop 出场 reason 为 `stop`。

## 讨论记录

- 2026-08-22 用户要求：废弃旧计划，重新基于最新设计创建计划。
- 2026-08-22 设计结论：`entry_mode` 只控制开仓/加仓，`exit_mode` 只控制正常信号出场，新增 `stop_loss_mode` 控制保护性硬止损。
- 2026-08-22 设计结论：`stop_loss_mode` 第一阶段只支持 `none|hard`；硬止损独立于 normal exit，触发后优先平仓；未来硬止盈使用独立 `take_profit_mode`，本期只预留通用风险退出框架。
- 2026-08-22 设计范围：四个常用 preset 作为本期目标；`next_open/stop` 为 P0；`next_open/close`、`close/next_open` 暂不开放。
- 2026-08-22 用户拍板：确认三字段方案、硬止损独立且优先、旧配置保留并 warning；新配置不再支持 `exit_mode=stop`，检测到该字段组合时回测失败并给出迁移提示；第一阶段继续使用伪单位加仓，不实现同一 symbol 的真实 partial add/reduce。
- 2026-08-22 用户补充止损 gap 规则：只有多单跳空低开且 `open < stop`、或空单跳空高开且 `open > stop` 时按 open 成交；其他触发情况按止损价成交。
- 2026-08-22 用户对第 3 项有异议：`next_open` 入场若入场当根触发 stop，需要单独讨论“开盘后立即止损 / 取消入场 / 下一根才激活”的语义。
- 2026-08-22 用户拍板第 3 项：`next_open` 入场当根启用止损；若多单开盘低于 stop、或空单开盘高于 stop，取消入场，不产生双边手续费；若开盘未穿 stop、入场后当根触发，则先入场再止损。
- 2026-08-22 用户确认第 4 项：新 stop 默认下一根 bar 生效，NaN 沿用上一个有效 stop；Codex 补充说明该规则只约束 stop 更新，不会让旧 active stop 在当前 bar 失效。
- 2026-08-22 用户要求调查 `reason`：当前实现疑似把 entry/exit reason 都写成 `signal`；已定位到 `_rebalance()` 固定传 `signal` 与 `_write_artifacts()` 入场行硬编码。本期先只修正 `reason`，不增加 `action` / `fill_phase`。
- 2026-08-22 策略层调研：SignalEngine 目前只有一次性 `generate(data_map)`，可以计算并输出动态 `stop_prices`，也可以自行限制止损放宽；但看不到 next-open 的未来实际开盘，也没有成交回调，因此 gap 后是否取消/保留入场属于引擎执行政策，不能仅由当前策略代码决定。
- 2026-08-22 用户提出新问题：以损定量策略的 stop 依赖 next-open 实际入场价（例如 entry - 2×ATR），同时手数也依赖实际 entry-stop 距离；调研结论是当前 target-weight sizing 可在引擎实际 fill 后计算，但策略层没有 fill callback。推荐策略输出 stop distance/risk budget，pending order 携带快照，引擎在实际 fill 后完成 stop/size 换算。

## 已确认决策

1. **已确认**：字段为 `entry_mode`、`exit_mode`、`stop_loss_mode`，其中 `stop_loss_mode=none|hard`。
2. **已确认**：`hard` 独立触发、优先于 normal exit；仅在规定 gap 条件下按 open，其余触发按 stop 价。
3. **已确认**：`next_open` 入场当根启用 stop；开盘穿过 stop 则取消入场，否则开盘入场后当根可触发 stop。
4. **已确认并已落地**：新 stop 下一根 bar 生效，NaN 沿用旧 active stop；`next_open` 入场当根在开盘成交后立即监控。
5. **已确认**：旧配置保留并 warning；新配置不支持 `exit_mode=stop`，检测到即失败并提示迁移；新配置使用三字段。
6. **已确认**：第一阶段只沿用伪单位加仓，不实现同一 symbol 的真实 partial add/reduce。
7. **本期简化建议**：只修正已有 `reason`，不新增 `fill_phase` / `action` / signal time；后续需要严格审计时再扩展事件 schema。
8. **已确认暂不实现**：next-open 实际成交后按 stop distance/risk budget 以损定量；该局限和后续研究方向已单独记录。

## 风险 / 注意

- 不能只新增 `stop_loss_mode` 字段；若 normal order 和 risk exit 仍共用同一 fill 分支，耦合问题会原样保留。
- `stop_loss_mode=hard` 会改变已有 `close/stop` 策略的成交语义；旧配置迁移必须可观察，不能静默改变历史 run。
- 日线 bar 无法还原止损/止盈同 bar 的真实先后；本期硬止盈不开放，硬止损采用保守、可测试的固定优先级。
- A 股跌停、T+1 和其他市场限制可能阻止硬止损成交；必须区分触发、委托和成交。
- 当前同 symbol 真实增仓/减仓不在本期；伪单位加仓每个 code 独立维护 Position/active stop，logical group 不参与执行。
- `next_open/stop` 的关键不是再加一个白名单，而是同时拥有 normal next-open pending order 和 independent active stop；两条路径必须各自可审计。
- 本期 next-open/stop 的止损价必须在信号阶段已经可知；依赖实际 entry price 的止损和手数仍是已知局限，不应在回测结果中伪装成已支持。

## 实现结果

- 新增三字段校验与 runner 早失败迁移提示；正常信号订单、next-open pending intent、独立 active hard stop、gap 成交/取消入场、入场当根止损和市场规则阻塞重试已接入 BaseEngine 及相关市场引擎。
- 本期仍不支持 next-open 实际成交价之后的 stop-distance/risk-budget 以损定量；`next_open/stop` 继续使用策略信号阶段已知的绝对 `stop_prices` 与现有 target-weight sizing。后续迭代方向已在“后续迭代方向：next-open 以损定量”单列。
- 本期未增加 `take_profit_mode`、`fill_phase`、`action` 或 fill callback；普通出场与硬止损仍通过已有 `reason` 最小化区分。
