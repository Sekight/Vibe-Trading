# 计划：A方案——config 驱动逻辑标的分组

> 编号：P-20260819-logical_symbol_groups
> 状态：已完成
> 日期：2026-08-19
> 关联迭代：V038
> 关联：未提交

## 项目调研

- 当前 TA 海龟策略用 `TA0001.ZCE`~`TA0004.ZCE` 四个伪单位代码表达同一主连的四次金字塔单位；`signal_engine.py` 用 `codes[idx]` 把代码位置当作单位槽位，不能只删成一个 code 而保持现有独立止损语义。
- 当前回测引擎的 `max_single_weight` 从 `signal_engine.weight_groups` 读取分组；`P-20260818-single_weight_group` 已完成该能力，但分组来源是策略代码硬编码。
- 当前 digest 的持仓与风险分组也通过读取策略 `weight_groups` 得到；当前 WebUI 图表则从 `artifacts/ohlcv_*.csv` 的文件代码生成 `chart_symbols`，不会读取逻辑标的概念。
- 当前 `config.json` 的 `BacktestConfigSchema` 使用 `extra="allow"`，可以增加逻辑分组字段而不破坏既有配置字段；runner 的配置仍保留顶层 `codes` 作为实际执行代码列表。
- 当前 `TA_1m.csv` 被多个 data-bridge symbol 映射是执行层兼容方案；本计划不改变 data-bridge 的取数方式、不把相同 path 自动推断为同一标的，避免误合并真实不同标的。
- 相关使用说明位于 `HowToUse.md` 8.43 与 8.45；其中 8.43 当前描述的是策略侧 `weight_groups` 硬编码，需要在本计划验收后改为 config 唯一来源。

## 需求目标

- 做什么：引入 config 驱动的逻辑标的分组，让伪单位代码仍参与回测执行，但指标、持仓风险分析和 WebUI 行情图按逻辑标的展示。
- 分组唯一来源：`config.json` 的 `logical_groups`；新代码不再读取或要求策略 `SignalEngine.weight_groups`。
- 多标的兼容：`logical_groups` 必须是数组，一个策略可以配置多个逻辑标的；每个逻辑标的可以包含一个或多个执行代码。
- 配置形态：

  ```json
  {
    "codes": [
      "local:TA0001.ZCE",
      "local:TA0002.ZCE",
      "local:TA0003.ZCE",
      "local:TA0004.ZCE",
      "local:RB0001.ZCE",
      "local:RB0002.ZCE"
    ],
    "logical_groups": [
      {
        "logical_symbol": "TA_MAIN",
        "display_name": "TA主连",
        "codes": [
          "local:TA0001.ZCE",
          "local:TA0002.ZCE",
          "local:TA0003.ZCE",
          "local:TA0004.ZCE"
        ],
        "chart_code": "local:TA0001.ZCE"
      },
      {
        "logical_symbol": "RB_MAIN",
        "display_name": "RB主连",
        "codes": [
          "local:RB0001.ZCE",
          "local:RB0002.ZCE"
        ],
        "chart_code": "local:RB0001.ZCE"
      }
    ]
  }
  ```

- 语义约束：
  - `logical_symbol` 全局唯一、非空；`display_name` 非空，缺省时使用 `logical_symbol`。
  - 每个分组 `codes` 非空；组成员必须存在于顶层 `codes`，比较时兼容 `local:` 前缀归一化。
  - 一个执行代码最多属于一个逻辑组；重复归属直接报配置错误，不静默覆盖。
  - `chart_code` 可选；省略时使用分组第一个成员；若填写，必须属于本组。
  - 顶层 `codes` 中未出现在任何组的代码自动成为单代码逻辑组，保持向后兼容。
  - 没有 `logical_groups` 的旧 config 按“每个 code 一个逻辑标的”处理。

- 范围 / 边界：
  - 保留现有伪单位执行模型、加仓逻辑、独立止损、成交时点和手续费口径不变。
  - 本计划只改变逻辑标的元数据的来源和消费方式，不实现 B 方案的原生 leg 持仓模型。
  - 不根据相同 data-bridge path、相同 OHLCV hash 或代码名称自动推断分组；逻辑归属必须由 config 明确声明。
  - 不改变旧 run 已落盘的 artifacts；旧 run 缺少 `logical_groups` 时使用兼容的单代码展示，若要分组需在其 config 中补充配置后重新生成相关产物。

- 验收标准（一句话）：一个 TA 四伪单位 run 在 config 声明一个 `logical_groups` 后，指标/持仓风险/行情 K 线只呈现一个 TA 逻辑标的；一个含 TA、RB 等多个逻辑标的的 run 显示多个逻辑标的且每组只显示一张代表行情图；策略代码不再需要 `weight_groups` 硬编码。

## 实现方案

### 1. 建立共享逻辑分组解析器

- 新增 `agent/backtest/logical_groups.py`（或等价的共享模块），集中实现：
  - code 归一化（仅用于比较，保留原始 code 作为 artifacts / 交易字段）；
  - `logical_groups` 解析、默认 singleton 分组和严格校验；
  - code → logical group、logical group → member codes、logical group → chart code 的查询；
  - 逻辑标的配置的稳定序列化/返回结构，供 runner、digest、UI 共用。
- 解析器不得读取策略代码的 `weight_groups`，避免产生第二个事实来源。

### 2. runner 与配置边界

- 在 `agent/backtest/runner.py` 的配置校验/回测启动路径调用逻辑分组校验。
- 配置错误 fail closed，至少覆盖：空组、重复 `logical_symbol`、组成员不在顶层 codes、同一 code 多组归属、无效 chart_code。
- 保持 `config.json` 顶层 `codes` 为执行代码；`logical_groups` 只表达执行代码到逻辑标的的关系。
- 将已解析的逻辑分组信息写入 run card / run context 或等价可追溯产物，保证后端和前端不必重新猜测分组。

### 3. 指标与持仓风险分析切换到 config 来源

- `agent/backtest/engines/base.py`：`max_single_weight` 从 config 解析结果取组，不再调用 `getattr(signal_engine, "weight_groups", None)`。
- 保持 `max_portfolio_weight`、毛/净/单边口径和既有 signed-sum 语义不变。
- `agent/backtest/analysis/digest.py`：`daily_position_and_risk`、`position_groups`、`single_group_daily_series` 改为读取 config 分组；缺省组仍为单 code。
- 旧 run 没有分组配置时，digest 继续按单 code 生成结果，不能因为策略文件仍存在旧属性而改变“config 唯一来源”规则。

### 4. WebUI 行情图按逻辑标的展示

- `agent/src/ui_services.py`：由 `load_chart_symbols()` 改为基于逻辑分组返回代表代码与逻辑标的元数据；一个组只返回一个 chart code。
- `agent/src/api/runs_routes.py` 与 API 类型：在保持既有 chart payload 兼容的前提下补充逻辑标的列表，例如 `{logical_symbol, display_name, chart_code, member_codes}`。
- 交易标记处理：选择一个逻辑标的时，读取该组全部成员的 markers，并把它们映射到代表 chart code，确保 TA0002~TA0004 的加仓/平仓标记不会因为图表只加载 TA0001 而消失。
- `frontend/src/pages/RunDetail.tsx`：选择器、已选标签、图表标题显示逻辑标的 `display_name`；内部请求仍使用代表 chart code，避免破坏现有 API 查询参数。
- `frontend/src/lib/api.ts`：增加逻辑标的元数据类型；保留旧 `chart_symbols` 字段作为兼容字段，逐步让前端使用结构化分组信息。

### 5. B 方案的可迭代接口

- A 方案字段优先使用 `logical_symbol`、`display_name`、`codes`、`chart_code`，避免绑定 `weight_groups` 这个策略实现名称。
- B 方案未来可把同一 `logical_symbol` 下的 `codes` 替换为引擎内部 `legs` / `leg_id`，保留逻辑标的 ID 和 WebUI 展示层接口。
- 本计划不提前改变 `SignalEngine.generate()` 返回契约、不改变 `Position` / `TradeRecord`，B 方案另建独立计划并做原生 leg 模型设计。

## 执行清单

1. [x] 完成开工前核对并经用户确认计划；状态由“讨论中”切换为“已确认”。
2. [x] 新增逻辑分组共享解析器及配置校验，覆盖单标的、多标的、singleton fallback、重复归属和 chart_code 校验。
3. [x] 修改 runner / base engine，使 `max_single_weight` 使用 config 分组，不再读取策略 `weight_groups`。
4. [x] 修改 digest 持仓与风险分析，使用同一份 config 分组；确认旧 run / 无分组 config 行为不变。
5. [x] 修改后端 chart symbol/marker payload，使一个逻辑组只返回一个代表行情图且保留所有组内交易标记。
6. [x] 修改 WebUI 图表选择器、标题和类型定义，兼容单标的与多个逻辑标的。
7. [x] 补齐后端单测、digest 单测、UI service/API 测试和前端定向测试。
8. [x] 用 TA 四伪单位真实 run 验证：图表仅显示一个 TA 逻辑标的，`max_single_weight` / 持仓风险图聚合正确，TA0001~TA0004 的交易标记均可见。
9. [x] 用多逻辑组单测验证：每个逻辑标的一张图、组间互不吞数据、未分组代码按 singleton 展示。
10. [x] 需求验证完成后更新 `HowToUse.md`：
    - 重写 8.43，移除“策略 `weight_groups` 硬编码”作为使用要求，改为 `config.json.logical_groups` 数组配置；
    - 更新 8.45，说明持仓与风险 tab、单标的下拉框和行情图均按逻辑标的分组；
    - 增加单标的四单位、多标的多组、未分组代码的配置示例和兼容说明。
11. [x] 收尾更新本计划状态、计划 README、`ITERATION_LOG.md`；本轮沿用已记录的 M031 结构性问题。

## 开工前核对

（状态从“讨论中”切到“已确认”前由 Codex 逐项核对；核对结果按清单逐项展示“通过 / 未通过 + 发现项”）

- 需求目标 / 范围与讨论记录一致：通过——用户确认按 A 方案实施，config 逻辑分组为唯一来源，并要求支持多标的数组。
- 范围/边界无被后续讨论反转但仍保留的旧约束：通过——B 方案只记录设计锚点，不在本次实现。
- 执行清单覆盖需求目标与验收标准：通过——包含解析、指标、digest、API、WebUI、标记映射、测试和 HowToUse 收尾。
- 验收标准可验证：通过——有 TA 单组、TA+RB 多组、旧 config fallback、标记映射和错误配置场景。
- 元信息已填（关联允许为待填）：通过。

## 验证

- 配置解析单测：
  - 无 `logical_groups` → 每个 code 一个 singleton；
  - 一个四单位组 → 一个逻辑标的、chart_code 默认/显式选择正确；
  - TA + RB 多组 → 两个逻辑标的且成员不串组；
  - 重复 code、未知 code、重复 logical_symbol、无效 chart_code → fail closed。
- 引擎/指标：
  - config 分组同向权重时 `max_single_weight == max_portfolio_weight`；
  - 同组多空时仍按既有 signed-sum 口径；
  - 策略删除 `weight_groups` 后结果仍由 config 正确聚合；
  - 无分组旧行为回归通过。
- digest / 持仓风险：
  - 图 1、图 2、图 3 的逻辑标的分组一致；
  - TA 组内毛/净/单边口径与现有 8.45 定义一致。
- 行情图：
  - chart selector 只列逻辑标的；
  - TA 四个执行代码只出一张 K 线；
  - 四个执行代码的交易标记都落到 TA 代表图；
  - 多逻辑标的各自独立显示；
  - 旧 run / 无分组 run 不崩溃。
- 真实验证：使用 `ta_turtle_4h_v437fix_2014_2023` 的副本新增 `logical_groups` 后，用官方 runner + `--fastrun` 重跑；不覆盖原 run。结果：`trade_count=114`、`total_return=0.47704`、`max_single_weight=max_portfolio_weight=0.1453009`；UI chart symbols 仅 `TA0001.ZCE`，组内交易标记 228 条均映射到代表图。
- 后端验证：`pytest agent/tests/test_logical_groups.py agent/tests/test_analysis_digest.py agent/tests/test_engine_robustness.py agent/tests/test_api_infrastructure.py -q` → 131 passed、1 skipped。
- 前端验证：`npm run test:run -- src/components/charts/__tests__/CandlestickChart.test.tsx src/pages/__tests__/RunDetail.test.tsx` → 17 passed；`npm run build` → 通过。

## 讨论记录

- 2026-08-19，用户确认采用 A 方案：保留伪单位执行代码，通过 config 逻辑分组解决行情图、持仓与风险分析的逻辑标的混层问题。
- 2026-08-19，用户确认分组唯一来源为 config，不再在策略代码中硬编码 `weight_groups`。
- 2026-08-19，用户补充范围：必须兼容一个策略同时回测多个标的，`config.json` 使用数组形式配置多个逻辑分组。
- 2026-08-19，范围确认：需求验证完成后更新 `HowToUse.md`，同时覆盖 8.45 当前策略硬编码说明和这种加仓形式的 config 配置方法。
- 2026-08-19，设计约束：A 方案为当前迭代；B 方案作为后续可迭代方向，A 的字段命名和接口应为未来原生 leg 模型保留迁移空间。
- 2026-08-19，B 方案设计锚点：未来将把“伪单位 code”升级为“一个 `logical_symbol` 下的多个原生 `leg_id`”。行情层只加载和落盘一个真实标的；策略输出逻辑标的目标仓位及 leg 级入场/加仓/止损状态；引擎内部按 `(logical_symbol, leg_id)` 管理持仓，支持独立止损、部分平仓、手续费、保证金和强平；交易明细增加 `logical_symbol` / `leg_id`，positions/artifacts 同时提供逻辑标的聚合与 leg 明细，WebUI 默认展示逻辑标的、可展开查看各 leg。B 方案必须保持 A 的 `logical_symbol` 配置语义，另建计划并用 A 版 TA 黄金 run 做收益、交易数、止损价和费用逐项对拍后再切换。

## 风险 / 注意

- **配置错误风险**：逻辑分组是唯一事实来源，成员漏配或错配会影响指标、风险图、行情图和交易标记归属；必须 fail closed 并提供清晰错误信息。
- **多标的风险**：不同逻辑组的代码不能互相吞并；图表、digest、markers、positions 必须使用同一 group resolver，不能各自实现一套分组逻辑。
- **行情代表风险**：`chart_code` 只代表行情图；如果组成员不是同一底层行情，必须报错或警告，不能静默把不同价格画成一个逻辑标的。
- **旧 run 兼容风险**：旧 run 缺少 config 分组时保持单 code fallback；旧策略中的 `weight_groups` 不作为新分组来源，避免形成双事实来源。
- **伪单位产物仍重复**：A 方案不消除执行层四份 OHLCV 快照，只在逻辑展示和统计层聚合；彻底消除重复行情文件属于 B 方案范围。
- **B 方案边界**：未来 B 方案将涉及原生 leg、独立止损、部分平仓、交易明细和 artifact schema，必须单独建计划、单独做黄金 run 对拍，不能在本计划中顺手实现。
