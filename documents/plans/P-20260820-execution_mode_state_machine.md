# 计划：回测引擎正常交易与止损成交路径解耦

> 编号：P-20260820-execution_mode_state_machine
> 状态：已废弃
> 日期：2026-08-20
> 关联迭代：待填（收尾时填 V 号）
> 关联：Mistake_Journal M035；commit / run（收尾时补）

> ⚠️ 已废弃，见新计划 `P-20260822-risk_exit_execution_modes`。原文保留，历史讨论不删除。

## 项目调研

- M035（2026-08-20）：当前代码拒绝 `next_open/close`、`next_open/stop`、`close/next_open` 三种非对称组合；根因是 `BaseEngine` 用开仓模式同时控制整体信号 shift、`_same_bar` 与开/平成交路径。根据用户后续确认，`next_open/stop` 是最高优先级，本计划将它从 M035 后续范围提升为 P0；`next_open/close`、`close/next_open` 仍暂不开放。
- `agent/backtest/engines/base.py`：`_align(..., shift_bars=...)` 把整条目标仓位序列一起 shift；`_same_bar` 由 `entry_mode` 决定；`_open_fill_price()`、`_close_fill_price()`、`prospective_fill_price()` 都依赖这一个状态。当前三种白名单组合能运行，主要是因为它们恰好共享同一类时点，而不是因为开仓、正常平仓和止损已真正解耦。
- `agent/backtest/engines/base.py`：当前 `exit_mode="stop"` 只在已有平仓/反转信号进入 `_close_fill_price()` 时读取 `stop_prices`；止损不会独立监控持仓，也没有入场后的引擎级止损状态。`close/stop` 下普通信号平仓因此可能误走止损价路径。
- `agent/backtest/runner.py`：`BacktestConfigSchema` 当前没有显式声明或校验 `entry_mode` / `exit_mode`，非法组合要等行情加载、策略加载之后才由 `BaseEngine.__init__()` 抛错；策略生成文档和 `strategy-dev-manager` 模板也没有完整描述成交模式与 `stop_prices` 契约。
- `agent/backtest/engines/china_a.py`、`india_equity.py`、`korea_equity.py`、`china_futures.py`、`global_futures.py`：价格限制检查假设 `prospective_fill_price()` 当前使用开盘价或 `_same_bar` 对应的收盘价。解耦后必须让市场规则知道本次是开盘、收盘还是止损成交，否则会出现“检查按开盘、实际按收盘”或反之的静默误判；`CompositeEngine` 还要把执行阶段同步给子引擎。
- `agent/backtest/engines/crypto.py`：严格永续模式的事件证据把普通开仓/平仓的价格来源写成 `execution_open`，若支持收盘正常平仓或不同止损路径，事件来源需要随实际 fill phase 修正。
- `agent/backtest/models.py` 与 `BaseEngine._write_artifacts()`：`Position` / `TradeRecord` 目前只有成交时间，没有信号时间或订单状态；`trades.csv` 的 `reason` 是重要审计入口，但当前正常信号平仓统一记为 `signal`，止损若由同一函数触发也无法区分。`positions.csv` 是目标权重而非保证成交的实际持仓，待引入待成交订单后必须继续明确这一口径。
- 既有文档：V003 / HowToUse 8.34 将 `entry_mode` 描述为开仓时点、`exit_mode` 描述为全部平仓时点；结合本次用户补充，目标语义应修正为“`entry_mode` = 开仓 + 正常信号/止盈平仓路径；`exit_mode` = 保护性止损平仓路径”。
- 基线验证（2026-08-20）：`cd agent && ..\\.venv\\Scripts\\python.exe -m pytest tests/test_engine_execution_modes.py tests/test_base_engine.py tests/test_execution_causality.py tests/test_engine_robustness.py tests/test_china_a_engine.py tests/test_china_futures_engine.py tests/test_global_equity_engine.py tests/test_global_futures_engine.py tests/test_india_equity_engine.py tests/test_korea_equity_engine.py tests/test_crypto_engine.py tests/test_composite_engine_fallback.py tests/test_composite_currency_guard.py tests/test_signal_alignment_perf.py -q` → `396 passed, 2 skipped`。现有测试只覆盖当前三种白名单的局部填价行为，尚未覆盖独立止损、正常平仓与止损同 bar、入场后状态维护等语义。

## 难度评估

| 范围 | 难度 | 结论 |
|---|---|---|
| 只改组合白名单/报错条件 | 低 | 不可接受：不会解决当前 `entry_mode`、正常平仓、止损路径耦合，且会制造错误成交价。 |
| 保持现有三种组合并优先补 `next_open/stop` | 中高 | 需要改 `BaseEngine` 执行生命周期、止损状态、市场规则阶段、配置校验和回归测试；这是当前推荐的第一阶段范围。 |
| 同时开放 `next_open/close`、`close/next_open` 等剩余非对称组合 | 高 | 需要完整的独立信号/订单/成交状态机，建议后续再做。 |

## 需求目标

- 做什么：让引擎按“正常交易路径 / 止损路径”语义执行；保持现有三种组合，并把 `next_open/stop` 作为 P0 补齐：
  1. `next_open / next_open`
  2. `close / close`
  3. `close / stop`
  4. `next_open / stop`（P0：正常信号次日开盘，保护止损按止损路径）
- 语义基线（按用户 2026-08-20 补充，当前仍待确认）：
  - `entry_mode` 控制正常目标仓位变化：开仓、加仓、减仓，以及策略产生的正常信号平仓/止盈平仓和反转中的旧仓平仓。
  - `exit_mode` 只控制保护性止损平仓的发现与成交路径，不改变普通信号平仓价格。
  - `next_open` 表示把对应的正常动作或止损动作排到下一根可交易 bar 的开盘；`close` 表示在当前决策 bar 收盘按收盘口径处理；`stop` 表示触发后按止损价成交，跳空穿越时按实际开盘价成交。
- 范围 / 边界：
  - 本计划只新增 `next_open/stop`；`next_open/close`、`close/next_open` 仍暂不开放。内部抽象应为后续开放它们留下清晰扩展点。
  - 只改回测执行、配置/策略契约、相关 artifacts 与文档测试；不改交易连接器实盘下单路径，不把回测 `stop` 直接映射为实盘订单。
  - 保持未配置模式的旧默认行为可复现；没有提供 `stop_prices` 的旧策略不能因为新增止损状态而静默改变结果。
- 验收标准（一句话）：四种目标组合下，正常信号平仓永远走 `entry_mode`，保护性止损永远走 `exit_mode`，反转先平旧仓再开新仓，止损/跳空/市场规则/末 bar/预热窗口均有确定且可回归的结果。

## 推荐实现方案（讨论中）

### 1. 把执行对象拆成“正常目标”和“保护性止损”

1. 保留策略输出的原始目标权重作为“正常信号”，把开仓、加仓、减仓、正常止盈/出场和反转旧仓平仓都视为 normal order，不要再用一个 `_same_bar` 同时表达所有成交行为。
2. 内部增加明确的执行阶段/订单类型，至少区分：
   - `normal_open`：正常开仓或加仓；
   - `normal_adjust`：同一 symbol 的正常减仓/调仓（如果本期决定支持真实增减仓）；
   - `normal_close`：信号/止盈/反转平仓；
   - `stop_close`：保护性止损平仓；
   - `liquidation` / `end_of_backtest`：引擎或生命周期强制平仓。
3. `entry_mode` 决定 `normal_open` 和 `normal_close` 的 fill phase；`exit_mode` 决定 `stop_close` 的 fill phase。普通信号平仓不得因为 `exit_mode="stop"` 而读取止损价。
4. 用独立的 `ExecutionProfile`/校验函数集中维护合法值和合法组合，供 `runner.py` schema 与 `BaseEngine` 共用，避免白名单在多个文件漂移。

### 2. 为 `next_open` 建立待成交订单

- 待成交订单至少保存：symbol、方向、目标权重、信号时间、计划成交时间/下一根 bar、订单类型、退出原因、止损价快照（如适用）。
- 每根 bar 的推荐顺序：
  1. 先处理到期的 next-open 订单；
  2. 对已有持仓按止损路径检查并产生/执行 stop order；
  3. 读取本 bar 的正常目标信号，先处理所有正常平仓/反转的旧仓；
  4. 重新计算平仓后的可用权益，再统一规划新开仓；
  5. 执行 close 类正常开仓，或把 next-open 正常开仓放入订单队列；
  6. 在 bar 结束时更新下一根 bar 才生效的止损状态并记录权益。
- 同一 symbol 只能有一个有效的方向转换链；重复 close/stop 不能生成两笔平仓。末根 bar 没有下一根开盘时，next-open 待成交订单不应被伪造成已成交；现有持仓仍按明确的 end-of-backtest 规则强平并记 reason。
- 混合市场/节假日场景按该 symbol 的下一根实际 bar 处理，不能把统一日历上的前向填充价格当成该标的真实可成交 bar。

### 3. 目标组合的建议行为

| 组合 | 正常开仓 | 正常信号/止盈平仓 | 保护性止损平仓（建议定义） |
|---|---|---|---|
| `next_open/next_open` | 信号 bar 产生订单，下一根实际 bar 开盘成交 | 下一根实际 bar 开盘成交 | 当前 bar 触发后排队，下一根实际 bar 开盘成交；若没有 `stop_prices`，保持旧策略的无自动保护止损行为并告警/记录 |
| `close/close` | 信号 bar 收盘成交 | 信号 bar 收盘成交 | 用当前 bar 的 OHLC 判断触发，按当前 bar 收盘成交（这是日线 OHLC 的收盘近似，需用户确认） |
| `close/stop` | 信号 bar 收盘成交 | 信号 bar 收盘成交，不能走 stop 价格 | 用当前 bar 的 OHLC 判断触发；未跳空时按止损价，跳空穿越时按开盘价，再应用方向感知滑点与期货 tick 取整 |
| `next_open/stop`（P0） | 信号 bar 产生订单，下一根实际 bar 开盘成交 | 下一根实际 bar 开盘成交 | 当前 bar 触发后，当前持仓在下一根实际 bar 开盘按 stop 路径成交；未跳空按止损价，跳空按开盘价 |

### 4. 止损状态与 bar 内时序

- `stop_prices[code]` 视为策略在该决策 bar 收盘形成的候选保护价；它不是直接等同于当前 bar 的已成交止损单。
- 入场当根默认不激活止损：收盘入场时，入场前的 low/high 不能用来把刚刚收盘买入的仓位“回溯平掉”；next-open 入场也默认从下一根 bar 开始监控，避免同一根 OHLC 同时承载开仓和止损而引入路径假设。若用户要更激进的入场 bar 生效，需单独拍板并增加专门测试。
- 入场时保存止损快照；后续 bar 的新止损价在该 bar 收盘更新，下一根 bar 才生效。这样不会用当前 bar 的 close/low/high 计算出一个止损后再回头作用于同一根 bar。
- 默认建议：后续非 NaN 止损价更新 active stop，NaN 表示“本 bar 不更新”，继续沿用上一有效止损；整个持仓从未得到有效止损价时不自动平仓，但写 warning/审计信息。是否改为 `exit_mode=stop` 缺失止损即 fail closed 待拍板。
- 多空方向分别判断：多单 `low <= stop`，空单 `high >= stop`；跳空多单 `open < stop` 按 open，跳空空单 `open > stop` 按 open；非跳空才按止损价，期货按已有多单 floor/空单 ceil 规则取整，跳空实际 open 不取整。
- 同一 bar 同时出现 stop 触发和正常信号平仓时，建议 stop 先结算、只生成一笔交易并以 `stop` 归因；是否允许止损后同 bar 反向开仓，建议默认不允许，下一根 bar 再按新信号决定。
- 低频 OHLC 无法还原 bar 内先后顺序；本计划不添加虚构的盘中路径，所有“触发后收盘”或“止损价成交”都必须在文档/报告中标注为 bar 级近似。

### 5. 反转、资金与市场规则

- 任何方向反转都固定为“先平旧仓，再开新仓”；旧仓因 T+1、涨跌停或市场限制未能平掉时，不得开新方向仓。
- 同一根 bar 的所有正常旧仓先统一释放，再按平仓后的资本/权益重新规划开仓，避免用平仓前的权益计算新仓位造成手续费或盈亏后的轻微超配。
- `can_execute()` / `prospective_fill_price()` 应接收或读取明确的 execution phase，而不是读取 `_same_bar`：价格限制检查必须与实际 open/close/stop fill 使用同一价格源和滑点方向。
- 覆盖 A 股/印度 T+1、A 股/印度/韩国/期货涨跌停、期货 tick 取整、Composite 子引擎派发、Crypto strict 的 execution/mark price 分离。市场规则不应因模式重构而失去原有边界。
- 继续保持 M023 的保守 bar 顺序：先按当前已激活止损判断，再更新下一根有效的新止损；不能把整根 bar 的 high/low 当成可任意排序的成交序列。

### 6. 配置、策略契约和 artifacts

- `runner.py`：在数据加载和策略加载前校验 `entry_mode`、`exit_mode` 取值及组合；错误信息明确列出当前允许的四种目标组合。
- `agent/backtest/execution_modes.py`（建议新建）或等价公共模块：集中维护模式常量、profile 和 pair validator；`BaseEngine` 不再单独维护一份字符串白名单。
- `strategy-generate` / `strategy-dev-manager`：补齐配置字段、正常信号平仓与 `stop_prices` 的职责说明；模板不能把止损逻辑只写成“把 target weight 设为 0”后又假装引擎已拥有保护止损。
- `generate_backtest_config` 是否增加可选的 `entry_mode` / `exit_mode` 参数需要拍板；若不增加，至少要确保生成后的配置可被 agent 按用户语义补全。
- `TradeRecord` / `trades.csv`：至少保证正常平仓与保护止损的 `reason` 不混淆；建议增加 fill phase 或 signal time 字段，便于解释“信号日”和“成交日”不一致。是否本轮扩展 artifacts schema 待拍板，旧 run 读取必须兼容。
- `positions.csv` 继续表示策略目标/执行目标权重，不承诺每个目标都已经成交；真实成交以 `trades.csv` 为准，文档明确 pending/blocked/stop 后的差异。

## 可选的更简单实现（仅限确认不需要自动保护止损时）

- 如果用户最终确认 `stop_prices` 只是“策略已经发出平仓信号后的成交价参考”，而不是引擎自动监控的保护止损，那么可以保留 `_align` 的 target shift，只做以下最小修正：
  1. 用 `entry_mode` 独立决定正常开仓和正常信号平仓的 fill price；
  2. 仅当退出原因是 stop 时调用 stop fill；
  3. `close/stop` 的普通信号平仓固定按 close；
  4. 统一配置校验和补足目标组合回归测试。
- 该方案成本低、兼容性好，但不能满足“入场后维护 active stop、stop 不依赖 target 变成 0、next-open stop 订单排队”等更强语义，也不能直接解决 M035 的非对称组合。除非用户明确选择信号驱动止损，否则不推荐把它作为最终设计。

## 加仓/减仓边界

- 当前 `BaseEngine._rebalance()` 对已有同方向持仓不会按新 target weight 调整 size；项目现有金字塔策略通过多个伪单位 code 拆成多笔独立 Position，再用 `logical_groups` 合并展示。因此当前计划若只改成交时点，`entry_mode` 对“加仓”的含义默认是伪单位新增订单，而不是同一 symbol 原地增仓。
- 若用户要求同一 symbol 从 20% 调到 40% 真的追加、从 40% 调到 10% 真的减仓，本期必须新增 partial close / add order / 目标 size 对比 / 手续费与持仓归因，不能把它藏在普通 `_rebalance` 改动里；这会显著扩大计划范围。
- 建议第一期保持现有伪单位兼容模型，只保证伪单位的正常开仓/平仓都走 `entry_mode`；真实单 symbol 增减仓另建子计划，除非用户明确要求本期一并实现。

## 执行清单（待拍板后冻结）

1. 冻结组合范围（`next_open/stop` 已列为 P0）、`entry_mode`/`exit_mode` 语义、stop 是自动监控还是信号驱动，以及加仓是否只沿用伪单位模型。
2. 建立公共 execution profile/配置校验，先补非法配置在 runner 早失败的测试。
3. 重构 BaseEngine 的正常订单、待成交订单、active stop 和阶段感知 fill/market-rule 检查。
4. 处理反转顺序、平仓后重新 sizing、末 bar、统一日历/实际交易日、backtest window 与 warmup 边界。
5. 更新 Composite/Crypto strict/价格限制/tick/费用/交易归因的适配和回归。
6. 补四种目标组合 synthetic end-to-end 测试、旧默认回归测试、止损矩阵测试与市场边界测试。
7. 更新 `HowToUse.md`、策略 skills/templates、必要时更新 `generate_backtest_config`，再按项目规则收尾记录 M035 状态与 ITERATION_LOG。

## 开工前核对

（当前为讨论中，禁止改业务代码；用户确认方案后逐项展示“通过 / 未通过 + 发现项”，并先把本计划及 `documents/plans/README.md` 状态改为“已确认”。）

- 需求目标 / 范围与讨论记录一致：未通过——等待确认是否按“现有三种 + `next_open/stop` P0”执行，以及是否把 exit_mode 定义为自动保护止损路径。
- 范围/边界无被后续讨论反转但仍保留的旧约束：未通过——当前 HowToUse 仍把 exit_mode 解释为全部平仓时点，需要按最终语义修正文档。
- 执行清单覆盖需求目标与验收标准：通过——已覆盖正常信号、止损、pending、反转、市场规则、配置、产物和回归。
- 验收标准可验证：未通过——`close/close` 的止损 close 近似、止损缺失行为、同 bar 止损后是否允许反转仍待拍板。
- 元信息已填（关联允许为待填）：通过。

## 验证（实现阶段填写）

- 配置层：四种目标组合通过；`next_open/close`、`close/next_open` 按当前范围保持明确失败；错误在数据加载前返回。
- 引擎层：用无手续费/无滑点 synthetic OHLC 逐 bar 对拍 entry、normal exit、stop exit、gap、long/short、reversal 和末 bar。
- 回归层：现有基线 `396 passed, 2 skipped` 不退化；A 股/期货/Composite/Crypto strict 相关定向测试通过。
- 工件层：`trades.csv` 的 signal/stop/end reason、成交时间、费用、持仓 bar 数和 `positions.csv` 目标权重口径一致；旧 run 缺新列时前端/验证器不崩。
- 文档/策略层：HowToUse 8.34、策略生成/SDM 契约与实际行为一致；至少跑一份 `next_open/next_open`、`close/close`、`close/stop` 的真实 runner smoke run。

## 讨论记录

- 2026-08-20 用户提出：希望引擎支持 `next_open/next_open`、`close/close`、`close/stop`，要求先全面调研难度、坑、实现方式和待拍板项。
- 2026-08-20 用户补充了 M035 外部建议：不能只改组合白名单，至少要考虑独立信号/成交、next-open 待成交订单、入场后止损状态、反转顺序、入场 bar 止损生效和跳空止损。
- 2026-08-20 用户进一步澄清目标语义：`entry_mode` 应是“开仓 + 正常信号/止盈平仓”的路径，`exit_mode` 应是“止损平仓”的路径。本计划据此把当前文档/代码中“exit_mode 控制全部平仓”的解释标记为待修正。
- 2026-08-20 用户补充：`entry_mode` 还应覆盖加仓；计划新增“加仓/减仓边界”章节，区分现有伪单位加仓与同一 symbol 真实增减仓。
- 2026-08-20 用户补充：最常用的组合是 `next_open/stop` 与 `close/stop`，其中 `close/stop` 已有基础支持，`next_open/stop` 优先级最高；计划将 `next_open/stop` 提升为 P0，剩余 `next_open/close`、`close/next_open` 暂缓。
- 2026-08-20 Codex 调研：当前 `_rebalance()` 只对“无持仓”执行 `_plan_open_order()`；伪单位加仓因此会走 entry path，但同一 symbol 的同方向目标权重变化不会真实增仓/减仓。`logical_groups` 只负责逻辑归并，不改变执行层 Position。

## 待用户拍板

1. **范围**：是否确认保持三种现有组合，并把 `next_open/stop` 作为 P0；`next_open/close`、`close/next_open` 暂缓？（建议：是。）
2. **stop 语义**：`stop_prices` 是否由引擎自动监控并在未出现 target=0 时也触发？（建议：是；没有 stop_prices 的旧策略保持兼容并记录 warning。）
3. **`next_open/next_open` 的止损**：stop 在当前 bar 触发后是否排队到下一根开盘？（建议：是；这是该组合下 exit_mode=next_open 的直接含义。）
4. **`close/close` 的止损**：触发后是否按当前 bar 收盘成交的 bar 级近似？（建议：是；文档明确这是 OHLC 近似，而不是盘中止损价。）
5. **入场当根止损**：是否默认不生效？（建议：是；从下一根 bar 开始，避免 lookback/路径假象。）
6. **同 bar 冲突**：止损触发与正常信号平仓同时出现时是否 stop 优先、只平一次，并禁止同 bar 反向开仓？（建议：是。）
7. **止损更新**：NaN 是否表示沿用上一有效 stop，新的 stop 在下一根 bar 生效？（建议：是。）
8. **缺止损处理**：`exit_mode=stop` 但策略没有有效 `stop_prices` 时，是 warning 后无保护运行，还是直接 fail closed？（建议第一期 warning 兼容；严格模式可后续增加。）
9. **配置生成**：是否把 `entry_mode` / `exit_mode` 作为 `generate_backtest_config` 的可选参数并写入策略生成模板？（建议：是，避免用户意图在自动生成 config 时丢失。）
10. **审计字段**：是否本轮新增 signal time / fill phase 到 `TradeRecord` 与 `trades.csv`？（建议：至少新增 fill phase 或等价字段；若追求最小改动，可先只修正 `reason`，信号时间另建小计划。）
11. **加仓**：本期是否只支持现有多个伪单位 code 的正常加仓，还是要支持同一 symbol 的真实增仓/减仓？（建议：第一期保持伪单位模型，真实增减仓另建计划。）

## 风险 / 注意

- “当前三组合已在白名单”不等于语义已完成；只改白名单会把普通信号平仓误当止损平仓，属于高风险错误。
- 如果两个字段被定义为独立的 normal/stop 路径，概念上应能解释完整的 `2 × 3` 组合矩阵；本期只开放三种是范围控制，不应把另外三种误写成“不合理”。其中 `next_open/stop` 对很多日线策略尤其自然：正常信号次日开盘，保护止损按止损价。
- `entry_mode` 和 `exit_mode` 的新语义会让现有 `HowToUse`、V003 迭代记录和策略生成技能出现历史描述冲突；实施后必须以代码为真相并明确兼容边界，不静默改写历史结论。
- 自动保护止损可能改变已有策略结果；建议只有当 `stop_prices` 实际存在时才启用新增自动路径，没有该字段的旧 run 保持旧行为。
- 日线 OHLC 不能知道同一根 bar 内先后顺序；stop、signal、反转、止盈若共存必须依赖固定保守规则并用 synthetic bar 测试锁定。
- A 股跌停/印度 circuit/T+1 可能使止损无法成交；不能把“触发了止损”直接当作“已经平仓”，应保留持仓并记录 blocked/未成交状态或明确重试语义。
- pending order 的 size 应在实际成交 bar 按可观察价格/权益计算，不能把信号 bar 的 close 偷渡到次日开盘；反转时平仓后的费用、盈亏和资金释放要影响新开仓 sizing。
- `backtest_start` 只截执行窗口但仍需要 warmup；若待成交订单来自窗口外前一根信号，必须明确是否允许在窗口首 bar 开盘成交，不能无声丢单。
- 旧 `trades.csv`、验证器、前端交易表和 Crypto strict 证据都可能只认识现有字段；新增字段必须向后兼容，不能以重跑旧 run 为前提。
- M023 已证明 bar 级“同 bar 立即更新 stop 再触发”会制造虚构成交；本计划默认采用“当前 active stop 先判断、下一 bar 更新”的顺序。
