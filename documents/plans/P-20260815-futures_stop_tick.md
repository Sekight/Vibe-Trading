# 计划：期货止损成交价按最小变动价位取整

> 编号：P-20260815-futures_stop_tick
> 短标题规则：单词间用 _ 连接，不使用 -（例如 P-20260814-timeline_charts_fix）
> 状态：已完成
> 日期：2026-08-15
> 关联迭代：V026
> 关联：commit `62b1c38`、`5d044ae`；run `rb_futures_5m_20250901_29_v1`、`20260808_032625_05_e9f25e`

## 项目调研

**外部（接口/网页）**
- 东财「品种及交易规则」页面为静态壳，数据由接口 `GET /emfApi/pzjy/getPZJYInfo` 动态返回，含 `minimumPrice`（最小变动价位）、`jydw`（交易单位）、`varietiesCN/EN`（品种名/代码）——2026-08-15，https://www.eastmoneyfutures.com/pages/service/jygz.html
- 接口可稳定提取 **91 品种 / 6 交易所**全量规则，tick 文本可解析为数值（1元/吨→1、0.2点→0.2、0.02元/克→0.02、0.005元→0.005、1元/500千克→1）——2026-08-15，接口实测
- 接口编码不稳定：节点间 GBK/UTF-8 混用（Content-Type 恒为 UTF-8），需 utf-8→gb18030→gbk 轮试 + 中文关键词校验——2026-08-15，接口实测
- 该接口无手续费字段，补不了 `_COMMISSION`——2026-08-15，接口实测
- 数据快照留档：`E:\zcodeWorkSpace\期货品种最小变动价位.json`（91 条）——2026-08-15，抓取

**内部（代码/项目现状）**
- 引擎现有四张表（`_MULTIPLIER` 58 条兜底 10、`_COMMISSION` 37 条、`_MARGIN_RATE` 45 条、`_PRICE_LIMIT`）均为硬编码 dict、带默认兜底，无接口无自动更新；`_TICK` 同构可行——2026-08-15，agent/backtest/engines/china_futures.py
- `_extract_product` 保留合约代码大小写（rb 小写、IF/CF 大写），静态表键须与之匹配——2026-08-15，china_futures.py:112
- 东财 91 品种与 `_MULTIPLIER` 大小写不敏感核对：覆盖 58、缺失 33（AO/BR/OP/LG/BZ/PS/PT/PD/EC 等新品），已覆盖乘数全部一致；JD 鸡蛋报价单位 500kg（5 吨/手 = 10 个报价单位），引擎 `jd=10` 正确——2026-08-15，快照 vs china_futures.py
- 类继承 `ChinaFuturesEngine → FuturesBaseEngine → BaseEngine`，`GlobalFuturesEngine` 同走 FuturesBaseEngine；tick 钩子放 BaseEngine 默认 None 即可隔离境外/复合引擎——2026-08-15，engines/*.py

## 需求目标

- 做什么：让期货止损「成交价」符合品种最小变动价位（tick），消除 trades.csv / WebUI 中 rb 3143.7571 这类交易所不可成交的小数价格。引擎侧新增静态 `_TICK` 表，止损成交价按 tick 取整（多单 floor、空单 ceil）。
- 范围 / 边界：只改 `china_futures.py`（新增 `_TICK` 表 + tick 查询）与 `base.py`（`_close_fill_price` 止损成交价取整）；策略与多空信号、仓位、手续费、乘数逻辑不动；A 股 / 现货引擎不受影响；`_TICK` 建全量 91 品种，未知品种兜底不取整。
- 验收标准（一句话）：重跑 `rb_futures_5m_20250901_29_v1` 后 trades.csv 所有成交价均为 1 元整数（rb tick），且盈亏 / 手续费按取整后价格口径一致；新增 tick 取整单测（rb=1 / IF=0.2 / au=0.02 / 未知品种）覆盖。

## 实现方案

- `china_futures.py` 顶部新增 `_TICK: dict[str, float]`（与 `_MULTIPLIER` 同位置同风格，key 大小写混合按品种），全量 91 品种，值取自东财快照数值（`rb=1.0`、`IF=0.2`、`au=0.02`、`T=0.005`、`JD=1.0`…）；表上方注释注明数据源 URL、抓取日期与编码坑。
- `china_futures.py` 实现 `get_price_tick(symbol)`：`_extract_product(symbol)` → `_TICK.get(product)`，返回 `Optional[float]`（未知品种 None）。
- `base.py` `_close_fill_price`：止损分支（多单 `low ≤ stop`、空单 `high ≥ stop`）——若开盘未跳穿（多单 `open ≥ stop`、空单 `open ≤ stop`），成交价 = stop，再按 tick 取整：多单 `floor(stop / tick) * tick`、空单 `ceil(stop / tick) * tick`；若跳穿则按实际 open 成交（真实价格，不取整）；tick 为 None 不取整。取整钩子放 BaseEngine 默认返回 None、ChinaFuturesEngine 覆写，`_close_fill_price` 保持引擎无关。
- 注意：止损「设置价」仍由策略输出（可能带小数），只有「成交价」在引擎侧取整；`risk_per_lot` 手数仍按策略原止损价计算（方案 B 固有取舍，见风险）。

## 执行清单

1. `china_futures.py`：新增 `_TICK` 表（全量 91，对照快照逐条核对）与 `get_price_tick()`。
2. `base.py`：`_close_fill_price` 止损成交价按 tick floor/ceil 取整（含跳穿分支区分、tick=None 不取整）。
3. 单测：tick 取整（rb=1 多单 floor/空单 ceil、IF=0.2、au=0.02、未知品种不取整、跳穿按 open）+ 期货全周期回归（trades.csv 价格整数、total_commission 口径）。
4. 重跑 `rb_futures_5m_20250901_29_v1` 与 A 股日线 run `20260808_032625_05_e9f25e`，核对绩效变化。
5. 收尾：ITERATION_LOG、计划状态、README 索引。

## 开工前核对

（状态从“讨论中”切到“已确认”前由 Codex 逐项核对；核对结果按清单逐项展示“通过 / 未通过 + 发现项”）

- 需求目标 / 范围与讨论记录一致
- 范围/边界无被后续讨论反转但仍保留的旧约束
- 执行清单覆盖需求目标与验收标准
- 验收标准可验证
- 元信息已填（关联允许为待填）

## 验证

- 单测：`pytest tests/test_china_futures_engine.py tests/test_base_engine.py tests/test_metrics.py tests/test_engine_execution_modes.py -q`。
  - 新增用例：`_close_fill_price` 多单 floor / 空单 ceil 到 tick（rb=1、IF=0.2、au=0.02）；跳穿按 open 不取整；未知品种不取整；全周期后 trades.csv 价格全整数。
- 重跑 `rb_futures_5m_20250901_29_v1`：原 3143.7571 / 3169.2857 两条止损行变为 3143 / 3170；trades.csv 所有价格整数；pnl = 手数×乘数×整数价差，与 equity.csv 期末权益差额核对；total_commission 随取整后价格核对。
- 重跑 A 股日线 run `20260808_032625_05_e9f25e`：确认不受影响（A 股不经过期货 `_TICK`）。

## 讨论记录

（append-only：谁提出、选项、结论；范围/边界反转时标注“范围变更：原=... → 现=...”）

- 2026-08-15，用户发现：rb run 交易表出现 3143.7571（2025-09-17 10:05 多平）与 3169.2857（2025-09-19 13:50 平空）两条小数价格，询问原因。
- 2026-08-15，Codex 排查：策略止损价 = low_min ± 0.3×ATR 未按 tick 取整，引擎同 bar 止损按 `min/max(open, stop)` 直接以小数 stop 成交；rb 最小变动价位 1 元，3143.7571 不可成交。盈亏靠合约乘数（rb=10）换算，价格带小数不影响盈亏正确性，仅价格粒度不真实。
- 2026-08-15，Codex 提出方案 A（策略侧 tick 取整，推荐）/ B（引擎侧 tick 表）/ C（保持现状）；用户暂未拍板，先建计划文档待考虑。
- 2026-08-15，用户提议：解析东财期货交易规则接口 `/emfApi/pzjy/getPZJYInfo` 后维护成**静态硬编码表**（代码内 map，如 `_TICK`），数据源在计划文档与代码注释中说明；该数据极少变化，即使变化也不影响回测引擎。
- 2026-08-15，Codex 调研：该接口可稳定提取 **91 品种**最小变动价位+交易单位（注意：接口编码不稳定，GBK/UTF-8 混用，需 utf-8→gb18030→gbk 轮试+中文校验的健壮解码）；与引擎现有 `_MULTIPLIER`（58 条硬编码 dict，兜底 10）交叉核对，覆盖 58/91、缺失 33（AO/BR/OP/LG/BZ/PS/PT/PD/EC 等新品），已覆盖乘数全部一致（JD 鸡蛋报价单位 500kg，5 吨/手=10 个报价单位，引擎 jd=10 正确）；现有四张表（_MULTIPLIER/_COMMISSION/_MARGIN_RATE/_PRICE_LIMIT）均为硬编码 dict 带默认兜底，`_TICK` 同构可行；该接口无手续费字段，补不了 _COMMISSION。
- 2026-08-15，用户拍板：①方案 B（引擎侧 `_TICK` 表）；②建全量 91 品种静态表，未知品种兜底不取整；③取整方向保守——多单 floor、空单 ceil；④数据快照 `E:\zcodeWorkSpace\期货品种最小变动价位.json` 作建表对照。

## 风险 / 注意

- 止损「设置价」仍由策略输出（带小数），仅「成交价」取整；`risk_per_lot` 手数仍按策略原止损价计算，成交价取整后单笔风险与设计值有细微偏差（方案 B 固有取舍，绩效以复跑为准）。
- `_TICK` 为静态表，新品种上市或规则调整后会过期；回测引擎对 tick 精度不敏感，过期仅影响取整粒度，不影响盈亏正确性。数据源与快照已留档，需要时重新抓取更新。
- 取整用 `floor(x / tick) * tick` / `ceil(x / tick) * tick` 实现，避免浮点误差（如 au=0.02、T=0.005、TL=0.01）。
- 引擎当前只覆盖 58/91 乘数；本次不扩 `_MULTIPLIER`（数据源无手续费字段，避免乘数全、费率缺的不对称），留作后续。
