# 计划：回测引擎支持 2H（两小时）周期

> 编号：P-20260818-backtest_2h_interval
> 短标题规则：单词间用 _ 连接，不使用 -（例如 P-20260814-timeline_charts_fix）
> 状态：已废弃
> 日期：2026-08-18
> 关联迭代：待填
> 关联：待填

> 已废弃（2026-08-19）：不再把“引擎先支持自然时间 2H”作为独立需求或实现入口。2H 的交易日语义、聚合算法和前端一致性应统一由 P-20260818-trading_time_aggregation 讨论；该计划未确认前不启动 2H 业务代码。若后续仍要支持 2H，应从该计划的已确认口径另建或恢复实施计划。

## 项目调研

- `agent/backtest/runner.py` 的 `_VALID_INTERVALS` 目前只有 `1m/5m/15m/30m/1H/4H/1D`，`BacktestConfigSchema` 在读取 `config.json` 时直接拒绝 `2H`；这是当前“不能跑”的第一道闸门——2026-08-18。
- `agent/backtest/loaders/local_loader.py` 通过 `_RESAMPLE_RULES` 对本地 CSV/Parquet/DuckDB 做现场 OHLCV 聚合，当前有 `1H/4H` 映射，没有 `2H`；缺映射时会告警并原样返回源 bar，不能当作 2H 回测——2026-08-18。
- `agent/backtest/metrics.py` 的 `_normalize_interval` 和 `_BARS_PER_DAY` 没有 2H，当前 `calc_bars_per_year("2H", ...)` 会走默认 1 bar/day，导致年化收益、Sharpe 等指标失真；`agent/backtest/analysis/digest.py` 已有 2H 的持仓时长换算表，但不能替代主指标年化表——2026-08-18。
- `fetch_data_map` 会把请求周期原样传给具体 loader；各在线源能力不一致：Tushare 当前只取到 1H，yfinance 已有“取 1H 后聚合 4H”的模式，OKX/CCXT 的上游协议可能原生支持 2H，日线源则不应伪造 2H。不能只改 runner allowlist 就宣称所有数据源都支持——2026-08-18。
- 回测引擎 `BaseEngine` 对 2H 没有额外的成交时间分支；除数据加载、年化因子和少数周期断言外，2H 可沿用现有日内 bar 执行路径——2026-08-18。
- `HowToUse.md` 8.42 已明确记录“2H 当前不支持”及 runner/local_loader/metrics 三个核心落点；本计划将其从待改说明升级为实现验收说明——2026-08-18。

## 需求目标

- 做什么：让回测配置可以使用标准周期 token `"2H"`，并在本地数据桥回测链路中按两小时 bar 正确加载、执行、落盘和计算指标。
- 核心范围：`runner` 周期契约、local loader 2H 聚合、指标年化口径、相关测试和使用文档；保证本地 1m/1H 数据请求 2H 时不会静默返回原始细周期。
- 在线源边界：不把“引擎接受 2H”误写成“每个供应商都原生支持 2H”。对已有可靠原生 2H 或已有安全的 1H→2H 聚合模式的源，按源能力补适配和测试；不支持的源必须显式失败/返回缺失，让现有 fallback/provenance 机制处理，不能降级成 1H 或 1D 后继续跑。
- 大小写约定：与现有 runner 一致，回测配置使用大写 `2H`；内部 loader 可以兼容 `2h` 别名，但不放宽 runner 现有小时周期的大小写规则。
- 验收标准（一句话）：一个以 `source: local`、细粒度本地数据和 `interval: "2H"` 运行的真实/合成回测能成功完成，产物的行情行间隔为 2 小时、交易执行按 2H bar、年化指标使用正确的 2H bars-per-day，且不支持的在线源不会静默伪装成 2H。

## 实现方案

1. **统一周期契约**
   - `agent/backtest/runner.py`：将 `2H` 加入 `_VALID_INTERVALS`，同步模块 docstring 和错误提示相关测试。
   - 更新静态断言/契约测试，避免 `_VALID_INTERVALS` 的精确集合断言因新增周期误报。

2. **本地数据桥 2H 聚合**
   - `agent/backtest/loaders/local_loader.py`：增加 `"2H": "2h"` 与兼容别名 `"2h": "2h"`。
   - 沿用现有 `open:first / high:max / low:min / close:last / volume:sum`；保留 `trade_date:last`，确保期货夜盘与日线聚合链路不丢交易日信息。
   - 对 1m/5m/15m/30m/1H 输入分别验证 2H 输出；对于源粒度粗于 2H 的文件继续告警并不伪造细数据。

3. **指标年化口径**
   - `agent/backtest/metrics.py`：`_normalize_interval` 识别 `2h → 2H`。
   - `_BARS_PER_DAY` 为 2H 补齐各已登记 source 的合理值：A 股/期货本地交易时段按现有 1H/4H 口径推导，US/印度/KRX 等按各自 session，crypto/MT5 等 24 小时源按 12 根/天；具体数值以当前表的 session 约定和测试断言为准，不能统一硬编码成 2。
   - 与 `analysis/digest.py` 已有 2H 持仓时长换算表对拍，避免 metrics 与 digest 展示口径再次分叉。

4. **在线源能力边界与适配**
   - 先建立 2H 能力清单：local 必须支持；对已有 1H→4H 处理模式的 yfinance 等，按相同但可复用的聚合方式补 2H；对 OKX/CCXT 等协议明确支持 2H 的源增加映射并验证请求 token。
   - 对 Tushare、日线-only loader、交易所不支持 2H 的 CCXT 实例等，不将 1H/日线结果冒充 2H；必要时返回空结果/明确 warning，让 runner 的现有 fallback 和 run card effective source 记录真实来源。
   - 这一层只做与回测链路相关的 loader，不扩展到独立交易 connector 的周期枚举，除非测试证明回测路径复用了该 connector。

5. **端到端与文档**
   - 用合成 local 1H 数据跑最小回测，检查 `artifacts/ohlcv_*.csv` 的时间间隔、trade_date、trades/equity/metrics/run_card 的 interval 记录。
   - 更新 `HowToUse.md` 8.42：说明 `2H` 已成为引擎合法周期、本地数据桥如何提供细粒度源、在线源按能力区分；同时保留前端 `2h` 展示与后端 `2H` 回测的大小写/职责说明。

## 执行清单

1. 完成开工前核对，确认 2H 核心验收以 local 数据桥为必测路径，在线源按能力矩阵处理。
2. 更新 runner 周期白名单、文档字符串和相关契约测试。
3. 更新 local loader 的 2H/2h resample 规则，补 OHLCV/trade_date 聚合测试。
4. 更新 metrics 的 2H 规范化与 bars-per-day 表，补各市场类型年化断言。
5. 审计并按范围更新可安全支持 2H 的在线 loader；为不支持源保留显式失败/不降级测试。
6. 做 local 2H 最小端到端回测，检查 artifact 行距、指标和 run card。
7. 更新 HowToUse、计划状态、ITERATION_LOG，并在收尾前记录新坑/边界。

## 开工前核对

- 需求目标 / 范围与讨论记录一致
- 范围/边界无被后续讨论反转但仍保留的旧约束
- 执行清单覆盖需求目标与验收标准
- 验收标准可验证
- 元信息已填（关联允许为待填）

## 验证

- `cd agent; ..\.venv\Scripts\python.exe -m pytest tests/test_engine_robustness.py tests/test_local_loader.py tests/test_local_loader_interval_case.py tests/test_metrics.py -q`（按实际环境调整路径）。
- 在线 loader 的定向 interval-map/拒绝降级测试。
- 合成 local 2H run：确认 `config.json` 的 `interval` 为 `2H`，`artifacts/ohlcv_*.csv` 相邻 bar 为 2 小时，`calc_bars_per_year` 不再走默认 252×1，且 run card 的 effective source/interval 与实际一致。
- 失败回归：`3D` 仍被 runner 拒绝；细粒度不足的本地文件仍告警而不是向上/向下伪造；不支持的在线 source 不返回日线冒充 2H。

## 讨论记录

- 2026-08-18，用户提出：希望回测引擎支持两个小时周期，并与“报告页增加当前回测周期”一起调研、判断是否需要计划。
- 2026-08-18，Codex 调研判定：这是引擎/数据加载/指标跨模块中改动，必须建立计划；在用户确认计划前不写业务代码。
- 2026-08-18，Codex 建议核心验收以 local Data Bridge 为必通路径。原因是 local loader 已有任意粒度向粗周期聚合的通用结构，且当前项目的期货 4H 长周期回测实际依赖这条离线链路；在线源不统一支持 2H，必须按源能力处理，不能为了“看起来支持”静默改变 bar 粒度。

- 2026-08-18，进一步调研确认：现有 local loader 与天勤的 2H/4H 都是自然时钟、零点对齐分桶；同花顺/东方财富采用按交易日累计交易时间切分。对 TA 而言，自然时间 2H 会产生多个半交易时段桶，不能与行情软件的 2H 图直接对齐（见 Mistake_Journal M029）。
- 2026-08-19，用户决定：暂不单独实现 2H 回测。范围变更：原=直接扩展 runner、loader、metrics 与在线源的 2H 支持；现=先由 P-20260818-trading_time_aggregation 统一讨论交易时间聚合口径，独立 2H 计划归档为已废弃。该结论不等于自动确认交易时间聚合计划，也不启动任何 2H 代码。

## 风险 / 注意

- 2H 的年化 bars-per-day 不是所有市场都等于 2：美股 6.5 小时交易时段、A 股 4 小时、crypto 24 小时、期货/外汇交易时段各不相同；必须沿用 metrics 现有 source/session 口径。
- 数据源降级可能改变实际来源；只要发生 fallback，run card 必须保留 effective source，文档不能把它描述成原请求源原生 2H。
- `HowToUse` 当前“2H 不支持”的文字在实现完成前保持现状；计划确认后、代码验证完成时再更新，避免文档先于事实。
