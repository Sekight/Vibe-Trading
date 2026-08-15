# 计划：回测分析时间精度与小周期图表修复

> 编号：P-20260814-timeline_charts_fix
> 状态：已完成
> 日期：2026-08-14
> 关联迭代：V018
> 关联：run `rb_futures_5m_20250901_29_v1`

## 需求目标

- 做什么：修复 5 类影响小周期（5m/1m/20m 等）回测分析的问题：①交易时间最小精度只有天；②持仓时间相关指标单位混乱；③K 线周期按钮与时间精度错误；④净值/回撤曲线从数据起点开始，含大片空仓预热段；⑤月度热力图、盈亏 vs 持仓、持仓分桶对短线交易失去作用。
- 不做哪些：不改回测引擎的成交/资金/仓位逻辑；不改策略出入场规则；不迁移或删除旧 run；不做 1m 行情显示（已调研并记录可行方案，后续涉及 1m 交易时再做）；不做 trend_eternal 全量 load all 优化。
- 验收标准（一句话）：5m run 的交易与 K 线显示到分钟；持仓指标单位可读且口径统一；行情 K 线支持 5m/15m/20m/1h/2h/1D/1W/1M/1Y 前端聚合且 1D 按 trade_date（期货夜盘归次日）；净值/回撤从 backtest_start 开始；持仓图按 bar/分钟分桶，热力图支持日/周/月切换；相关单测、前端构建和截图核对通过。

## 实现方案

（涉及文件/模块、关键设计；已确认）

1. 时间精度链路与 trade_date
   - `agent/backtest/engines/base.py`：`trades.csv` 的 timestamp 写入完整 `YYYY-MM-DD HH:MM:SS`；新增 `holding_bars` 列。
   - local loader：保留源数据 `trade_date` 列，5m/15m 等聚合时 `trade_date` 取桶内 last；base.py 写 `ohlcv_*.csv` artifact 时保留该列。
   - `agent/backtest/analysis/digest.py`：`_date_prefix` 只在日线场景使用；equity/trades/ohlcv 链路保留完整时间；读取 `trade_date`。
   - `agent/src/ui_services.py`：`_normalize_price_rows`、`_flatten_data_map`、`build_trade_markers` 去掉 `format_run_date` 截断，保留完整时间并透传 `trade_date`。
   - 源数据无 `trade_date` 时回退规则：`datetime >= 21:00` 归下一自然日，并记录警告。

2. 持仓单位口径
   - `agent/backtest/metrics.py`：新增 `avg_holding_bars`；`avg_holding_days` 按 `bars_per_day`（由 bars_per_year/interval 推导）换算成真实天数。
   - `trades.csv`：`holding_bars` 为持仓 bar 数；`holding_days` 保留但明确为自然日口径。
   - `digest.py` 的 `trade_summary` 与 `frontend/src/lib/formatters.ts` 标签统一为新口径（如“平均持仓（bar）/（天）”），LLM 报告措辞同步。

3. K 线周期（前端聚合，隐藏后端指标）
   - `frontend/src/components/charts/CandlestickChart.tsx`：周期按钮改为 5m/15m/20m/1h/2h/1D/1W/1M/1Y，按基础 interval 动态显示（5m run 显示全部；1D run 只显示 1D/1W/1M/1Y；1m run 显示全部）。原 1M/3M/6M/1Y/ALL 时间范围按钮移除，缩放交给 dataZoom。
   - 前端新增 resample 工具：分钟周期按时间戳对齐；1D/1W/1M/1Y 按 `trade_date` 对齐；OHLC 聚合 first/max/min/last、volume sum。
   - 周期切换后 MA/BOLL/MACD/RSI/KDJ 全部由前端基于聚合结果重算，后端 `indicator_series` 隐藏。
   - tooltip 显示完整时间。
   - 数据评估：rb 单标的 5841 根/331KB，前端聚合 <11ms 量级；trend 单标的约 2081 根/约 100KB，更小；trend 全量 564 文件共 68.8MB/110 万行，保持按需加载单标的，不做 load all 优化。

4. 回测窗口与净值/回撤起点
   - `config.json` 新增 `backtest_start` / `backtest_end`；`start_date` / `end_date` 继续负责数据加载与指标预热。
   - 引擎 `_execute_bars` 的执行窗口截断到 `[backtest_start, backtest_end]`：数据全量加载、指标全量生成，但净值/回撤/metrics 从 backtest_start 开始，不再包含预热空仓段。
   - runner 实例化 `SignalEngine` 后注入 `trade_start` / `trade_end`；rb 策略删除 `_TRADE_START_STR` 硬编码，统一读属性。
   - digest 的 config 段带 backtest 字段，并纳入 digest 指纹，避免手动改 config 后 WebUI 分析图仍读旧缓存。
   - 旧 config 无 backtest 字段时回退 `start_date/end_date`；校验 `backtest_start >= start_date`、`backtest_end <= end_date`。

5. 持仓分桶与热力图
   - `holding_buckets`：由固定自然日桶改为按持仓 bar 数分桶（例如 `<5 根、5-10、10-20、20-40、>40`，可按 interval 换算分钟）。
   - `pnl_vs_holding`：横坐标改为持仓 bar 数或分钟。
   - 热力图：digest 输出日/周/月三种粒度 PnL，前端切换；默认自动规则 ≤7 天→日、≤31 天→周、更长→月。

6. 1m 行情显示（本轮不做，方案预留）
   - 瓶颈：rb 1m 约 8.5 万根/标的，artifact CSV 约 7-8MB，API JSON 预计 15-20MB+；JSON 解析与 ECharts candlestick 全量渲染是主要瓶颈（candlestick 无 large 模式），8.5 万根会明显卡顿。
   - 可行方案：后端区间/数量切片接口 + 前端 dataZoom 懒加载；或本地预生成多周期 price_series 缓存；1m 周期默认只加载最近 1 个交易日/最近 5000 根。

## 执行清单

- 1. 拍板确认：backtest_start/end 执行窗口截断；热力图日/周/月切换；旧 run digest 重建只做需要的 run；1m 行情本轮不做并记录方案；trade_date 期货日 K；周期切换隐藏后端指标。
- 2. 后端时间精度与 trade_date：local loader / base.py / digest.py / ui_services.py。
- 3. 引擎执行窗口：backtest_start/end 截断 + runner 注入 trade_start/trade_end + rb 策略去硬编码。
- 4. 持仓单位修复：metrics.py / trades.csv / digest / formatters / LLM 报告。
- 5. 前端 K 线周期：resample 工具 + CandlestickChart 周期按钮 + trade_date 聚合 + 隐藏后端指标。
- 6. 净值/回撤起点：依赖引擎执行窗口截断，digest/charts 同步。
- 7. 持仓分桶与热力图：digest 输出日/周/月 PnL + bar 分桶，前端三张图。
- 8. 测试与验证：pytest、npm test/build、重建 rb digest、截图核对。
- 9. 收尾留痕：ITERATION_LOG.md、HowToUse.md、计划状态与 README 索引。

## 验证

- `pytest tests/test_analysis_digest.py tests/test_engine_execution_modes.py tests/test_local_loader.py -q`。
- 前端：`npm test -- RunDetail`、`npm run build`，桌面/窄屏截图核对 K 线周期、tooltip、热力图切换。
- 重建 `rb_futures_5m_20250901_29_v1` 的 digest 后核对：trades 显示到分钟；`avg_holding_bars=20.5`、`avg_holding_days` 换算合理；K 线 1D 按 trade_date（夜盘归次日）；净值/回撤起点落在 backtest_start；持仓图出现有效分桶、热力图支持日/周/月。

## 讨论记录

（append-only：谁提出、选项、结论）

- 2026-08-13，用户提出 5 类问题，要求先调研不改代码。
- 2026-08-14，Codex 完成源码调研并给出根因：时间在多处被截成 `YYYY-MM-DD`（base.py 写 CSV、digest `_date_prefix`、ui_services `format_run_date`）；`avg_holding_days` 实际存 bar 数而 digest 又存 0 天，两套口径打架；K 线 `RANGE_BARS` 硬编码日线 bar 数；digest equity 从数据起点开始且日期重复；持仓图用自然日/月度导致短线数据退化。
- 2026-08-14，用户拍板：①config.json 新增 backtest_start/backtest_end（回测窗口），start_date/end_date 仅作数据加载窗口，runner 向 SignalEngine 注入 trade_start/trade_end 并去掉 rb 策略硬编码；②热力图增加日/周/月切换，默认按回测时长自动选；③询问“旧 run digest 一次性重建”含义；④行情左上角改为周期按钮 5m/15m/20m/1h/2h/1D/1W/1M/1Y，后端聚合暂不做，用 trend_eternal_2020_2026 与 rb_futures_5m_20250901_29_v1 评估。
- 2026-08-14，Codex 评估：方案①建议 engine 执行窗口截断（数据全量生成指标，执行/净值从 backtest_start 开始），digest 的 config 带 backtest 字段并纳入指纹，避免手动改 config 后 digest 不生效；方案③解释为重建 analysis.digest.json 缓存，只重建需要的 run 即可；方案④建议周期按钮按基础 interval 动态显示（1D run 只显示 1D/1W/1M/1Y），前端聚合为 O(n)，rb 5841 根聚合 <11ms、trend 单标的 2081 根更小；trend 全量 564 文件 68.8MB/110 万行，load all 不可行，仍按单标的加载。
- 2026-08-14，用户确认：①加 trade_date 列做期货日 K；②切换周期只前端计算并隐藏后端 indicator；③1m 行情本轮不做，要求调研局限与可行方案并记录到文档；④周期按钮替换原时间范围按钮，缩放交给 dataZoom。
- 2026-08-14，1m 调研结论：rb 1m 约 8.5 万根/标的，artifact CSV 约 7-8MB，API JSON 预计 15-20MB+，JSON 解析与 ECharts candlestick 全量渲染是主要瓶颈（candlestick 无 large 模式）；可行方案为后端区间/数量切片接口 + 前端 dataZoom 懒加载，或本地预生成多周期 price_series 缓存；默认 1m 只加载最近 1 个交易日/最近 5000 根。本轮不实现。

## 风险 / 注意

- MAE/MFE、regime、LLM 报告当前依赖日期粒度，改完整时间后需一起回归。
- 旧 run 的 `analysis.digest.json` 是持久化产物，不重建不会自动获得修复；只重建需要的 run。
- trade_date 依赖源数据/loader 保留；若源 CSV 无该列，回退按 21:00 归次日的规则生成并记录警告。
- engine 执行窗口截断会影响 metrics 口径（从预热窗口变为回测窗口），旧 run 无 backtest 字段时回退原行为。
- 周期切换隐藏后端 indicator_series 后，策略自定义指标在 K 线图上暂时不可见，后续可做按周期后端重算。
- 字段名/单位变化影响 WebUI 指标卡、run_card、LLM 报告，需要同步 label 与说明。
