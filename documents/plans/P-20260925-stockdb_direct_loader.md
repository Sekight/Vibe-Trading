# 计划：stockdb 直连 loader（source="stockdb"，本地服务取数，免导出快照）

> 编号：P-20260925-stockdb_direct_loader
> 状态：已完成
> 日期：2026-09-25（2026-09-26 最终拍板并完成，范围变更：分钟线纳入本期）
> 关联迭代：V050
> 关联：run ~/.vibe-trading/runs/vt_e2e_stockdb_daily、~/.vibe-trading/runs/vt_e2e_stockdb_min5；P-20260905-stockdb_ma_convergence_data（方案 A，V048；本计划 = 其方案 B）

## 项目调研

> 外部（实测，2026-09-25，Python 3.13.7 + PYTHONPATH=<stockdb>/pybao）：

- **连接本质**：stockdb 数据目录（data/data1，LevelDB ~24GB）由 `stockdb.exe` 服务进程持有，监听 `127.0.0.1:7899`；SDK（pybao/stockdb.pyd + stock_sdk.py）走 **socket** 读服务，不直接读 LevelDB 文件 → 直连方案的前提是服务常驻。
- **SDK 可用性**：`import stock_sdk` 在当前解释器 3.13.7 下实测可导入（pybao 内另有 3.14t 版本 pyd 备用）；`get_data(fq="hfq")` 正常返回。
- **接口**：`get_data(code|code_list, start, end, frequency='1d', fq='qfq'|'hfq'|None, fields, as_df)`，单码/批量（pipeline）皆可；字段实测：`date(int YYYYMMDD)/open/high/low/close/pre_close/pct_chg/volume(股)/amount(元)/turnover(%)/float_share/float_mv/total_mv/is_st/pe_ttm/pb/vol_ratio/name`。
- **性能实测**：批量 10 只全历史（2012 起，31419 行）**1.29s**；10 只 1.7 年 0.18s → 小池直连完全够用，全市场级另说。
- **行业（bk）性能实测**：`warm_default_connection` 0.3s，预热后 10 只 `bk.get(code,1,"name")` 计时 **0.00s**（≈0.4ms/只，5200 只秒级）→ 行业标签可作 extra_fields 静态列透传。
- **分钟数据实测（2026-09-25 修正）**：stockdb 原库**有** 1 分钟 bar——`rd.vals("分钟k","600519","*")` 101468 根有效 bar，覆盖 **2025-01-02 → 2026-09-24（421 交易日）**，全证券；此前 `get_data(frequency='1m')` 查空是调用姿势问题非库缺失。方案 A 导出仓不含分钟、P-20260909 相关会话（打板策略复现）调研时只看了日线导出仓才得出"分钟级放弃"。分钟 loader 支持不在本期，但"日线选股 + 分钟执行"两阶段路径的数据基础存在（见讨论记录四轮）。
- **坑（实测复核，外部数据源坑，实测复核）**：`pre_close` 字段被前复权污染——茅台 20240102 raw `pre_close=1605.59` vs 真实昨收 ≈1726（`close/pre_close-1=+4.95%` 与 `pct_chg=-2.375%` 自相矛盾）；且 SDK `fq="hfq"` 只把污染值同比例折算，**比例仍错**。`pct_chg` 字段干净（=真实涨跌幅）。→ 直连 loader 若透传 stockdb 的 pre_close，china_a 引擎涨跌停带（`historical_base_price` 优先 bar 的 `pre_close`，base.py:577）必错。
- **复权语义**：hfq = raw × 当日累计因子，锚定历史，新增除权不改历史值（loader cache 安全）；qfq 锚定最新、历史会变（cache 失效风险）。

> 内部（代码查证，2026-09-25）：

- loader 注册体系：`backtest/loaders/registry.py`（`VALID_SOURCES`、`_loader_modules`、`FALLBACK_CHAINS`、`_NO_NETWORK_FALLBACK_SOURCES`）+ `@register` 装饰器；回归测试 `test_valid_sources_covers_all_registered_loaders` 要求两处同步。
- runner 显式 source 路径：`fetch_data_map` → `_normalize_codes`（stockdb 无需改写）→ `loader.fetch(codes, start, end, fields=config.get("extra_fields") or None, interval)`（runner.py:1564）——**`extra_fields` 对任意 loader 透传**，stockdb 可直接复用该约定透传 turnover 等列。
- 配置契约：`BacktestConfigSchema` 为 `extra="allow"`（runner.py:143）→ 新增 stockdb 专属键（如 `stockdb_fq`）无需改 schema；`source` 校验器只认 `VALID_SOURCES`。
- 引擎路由按市场不按 source：`a_share in markets → ChinaAEngine`（runner.py:1379），source="stockdb" + `600519.SH` 自动命中，无需改引擎。
- `calc_bars_per_year`：未知 source 默认 252 交易日（metrics.py:165），stockdb 无需专门条目。
- `.env` 由 runner 经 dotenv 载入 os.environ（runner.py:35-39）→ loader 可用 `os.getenv` 读 SDK 路径等配置。
- 测试布局：`agent/tests/test_*_loader.py` 有现成模板。
- ST ±5% 档引擎按代码前缀近似（china_a.py:187 无法从代码识别 ST）→ `is_st` 列仅供策略用，不影响引擎。

## 需求目标

- 做什么：新增 **source="stockdb"** 数据源——数据源为 stockdb 时，vibe-trading 通过 SDK 直连本地 stockdb 服务取数（日线），跳过方案 A 的"导出 Parquet 快照 + data-bridge 登记"环节。**零导出、零加工、零数据落盘**：SDK 实时读服务 → DataFrame 直接进回测内存（data_map），不写任何中间数据文件（见实现方案 1"零落盘"）。
- 范围 / 边界：
  - 只新增 loader 文件 + registry 三处集合登记；**不改** engines / runner 业务逻辑 / BacktestConfigSchema 字段。
  - **不产生任何数据副本**：不建导出仓、不写 parquet/csv 数据文件、不接 loader cache；run 目录产物（equity/metrics/ohlcv_*.csv 等）是回测产物，属既有机制，与数据源无关（见 1c）。
  - 本期范围（2026-09-26 拍板）：**日线（1D）+ 分钟（1m 原生，5m/15m/30m/1H 由 1m 聚合）+ ETF（沪 5 / 深 1 前缀基金）+ 行业列（industry_l1）**。指数成分/权重、北交所（前缀 9）、交易日历不做（数据未验证/场景用不到）。分钟数据窗口约束：stockdb 原库 1m 覆盖 **2025-01-02 → 2026-09-24**，窗口外无分钟数据。
  - **不替代方案 A**：导出快照保留，用于离线复现 / 无服务环境；B 用于"有服务常驻时免导出直取"。
  - fail-closed：显式 `source="stockdb"` 但服务不可用时**报错不降级**（不静默换成腾讯网络数据），并加入 `_NO_NETWORK_FALLBACK_SOURCES`。
- 验收标准（一句话）：显式 `source="stockdb"` 的小池 A 股 run 经 MCP `backtest` 端到端跑通且 run 卡片记录 stockdb 溯源，同一标的区间与方案 A 快照数值对拍一致，重建的 `pre_close` 与 `pct_chg` 自洽（股票）/ 连续（ETF），额外列透传生效，ETF 抽验通过。

## 实现方案

### 1. 新 loader：`agent/backtest/loaders/stockdb_loader.py`

- `@register`，`name="stockdb"`，`markets={"a_share"}`，`requires_auth=False`。
- **SDK 注入**（懒加载，失败即 unavailable）：读环境变量 `VIBE_TRADING_STOCKDB_SDK_PATH`（.env 可配，指向 `<stockdb>/pybao`），`sys.path` 注入后 `import stock_sdk`；`VIBE_TRADING_STOCKDB_HOST/PORT` 可选（默认 127.0.0.1:7899）；首次使用时 `stock_sdk.init(socket_timeout=可配置，默认 10)`（SDK 本地默认 1s 对大查询偏紧）。
- `is_available()`：SDK 路径可解析 + import 成功 + TCP 端口连通（轻量 socket 探测，不拉数据）。
- `fetch(codes, start, end, *, interval="1D", fields=None)`：
  - 仅接受 `1D`，其余 interval 告警并返回空（对齐 tencent loader 行为）；
  - 代码规约：接受 `600519.SH|.SZ`（项目规约）与 6 位裸代码，内部去后缀调 SDK，**返回 key = 输入原始代码**（runner 的 missing 检查与引擎按键取数依赖此约定）；股票前缀 0/3/6 与 **ETF 前缀 5/1** 放行，`.BJ`（北交所）告警跳过；
  - 取数：SDK 批量 `get_data(codes_6, start, end, frequency="1d", fq=<配置>)`，**分批循环（每批 ≤300 只）**——单批转 DataFrame 后即释放原始 dict，防止全市场级（5200 只）一次 pipeline 把数千万行 dict 拉进内存（导出脚本当年 OOM 的同款根因）；单批异常降级逐股重试；
  - **复权实现（统一日线/分钟）**：取原始价（fq=None）+ 复权因子表自折算（`_load_fq_cums` 同款 bisect，hfq = raw × cum、qfq = raw × cum_latest/cum）——导出脚本已验证该折算与 SDK `fq="hfq"` 逐位一致；绕开 SDK fq 封装后日线/分钟共用一套折算代码；
  - **分钟路径（2026-09-26 纳入）**：
    - 取数走底层 `rd.vals("分钟k", code, time_query)`（SDK `get_data(frequency="1m")` 实测返回空、底层 vals 实测正常；实现前先做取数路径对照实验钉死，含批量 pipe 是否可用）；
    - interval 映射：`1m` 原生直返；`5m/15m/30m/1H` 由 1m 聚合（OHLCV first/max/min/last/sum + extra 列 last，自然时钟 resample——与 VTD 引擎/天勤口径一致；A 股 5/15/30 分钟自然时钟与交易时钟恰好对齐无歧义，**1H 与看盘软件 60m 交易时钟不同**，文档标注）；
    - **分钟 pre_close 重建**：涨跌停带基准 = 当日交易所昨收（当日所有分钟 bar 恒定），非上一根分钟 bar——取该股当日日线的重建 pre_close（hfq 空间）映射到每根分钟 bar（日线点查/小表映射，数据量 = 每股每天 1 条）；
    - 分钟窗口约束：数据覆盖 2025-01-02 起，窗口早于该日期的部分自然为空（coverage warning 提示）；分钟回测适合小池（数百只内），全市场分钟不可行；
  - 列规整：date(int) → UTC-naive DatetimeIndex（对齐 local loader 契约），OHLCV 数值化 + `validate_ohlc`；
  - **pre_close 重建（本方案关键点）**：丢弃 stockdb 的 `pre_close` 字段，重建规则 = 优先 `close / (1 + pct_chg/100)`（pct_chg 干净，raw 空间还原交易所真实前收；hfq 空间数学等价于 shift(1)），pct_chg 缺失时回退 `close.shift(1)`（**ETF 即此路径**：实测 ETF 的 pct_chg/name 为 None，hfq 空间 shift(1) 数学等价故正确；raw 模式 ETF 除权日有比例误差，文档标注）；重建值始终保留（引擎涨跌停带刚需）；
  - 额外列：`fields`（= config `extra_fields`）声明式透传（turnover/amount/float_share/is_st/pe_ttm/pb/total_mv/float_mv/vol_ratio/name/pct_chg/**industry_l1** 白名单内取交集）；未声明时列最小（OHLCV + pre_close），行为与 tencent 一致；**industry_l1 特殊路径**：请求含该列时预热后逐股 `bk.get(code,1,"name")`（实测 ≈0.4ms/只）取申万一级标签填充该股每根 bar（当前状态口径，同方案 A industry.parquet 的近似语义）；行业列为静态重复值，**以 `category` dtype 存储控内存**（全市场日线量级下仅数十 MB；data_map"每行=当日快照"契约下重复列免除策略侧对齐逻辑，优于旁路字典——后者需动 fetch 返回协议与 runner，违背本期边界）；
  - 复权配置：config 新键 `stockdb_fq`（`"hfq"` 默认 / `"qfq"` / `"none"`），映射到自折算模式（hfq = raw × 当日 cum；qfq = raw × cum_latest/cum；none = 原始价）；
  - **零落盘（不接 loader cache）**：fetch 直接取数不写任何文件——本地服务实测已够快（10 只全历史 1.3s），cache 无收益反而在 `VIBE_TRADING_DATA_CACHE=1` 时产生缓存 parquet（且 qfq 有失效问题），故 stockdb loader **不接入** `cached_loader_fetch`，彻底不产生数据文件。

### 1b. 使用方式（配置面）——data-bridge 完全不用配

- **data-bridge（`~/.vibe-trading/data-bridge/config.yaml`）零配置**：那是方案 A/local loader 专属的"逐 symbol 登记文件路径"机制，直连不需要（5200 只也无需登记）。
- 一次性配置 `~/.vibe-trading/.env`（runner 经 dotenv 载入环境）：
  - `VIBE_TRADING_STOCKDB_SDK_PATH=E:\data\free-stockdb-windows-v0.3.2-more-power\stockdb\pybao`（必填，指向 SDK 目录）
  - `VIBE_TRADING_STOCKDB_HOST` / `VIBE_TRADING_STOCKDB_PORT`（可选，默认 127.0.0.1:7899）
- run 的 `config.json` 示例：

```json
{
  "source": "stockdb",
  "codes": ["600519.SH", "000001.SZ"],
  "start_date": "2024-01-01",
  "end_date": "2025-12-31",
  "interval": "1D",
  "extra_fields": ["turnover", "amount", "float_share"],
  "stockdb_fq": "hfq"
}
```

- 前提：`stockdb.exe` 运行中（服务掉线时显式报错，提示重启，不降级到网络源）。

### 1c. 与 P-20260909（OHLCV 落库 / 报告页 K 线懒加载）的关系——照常生效，不受影响

- OHLCV 落库挂在**引擎层** `backtest/engines/base.py` `_write_artifacts`（`config["save_ohlcv"]` 控制，默认落库），发生在 loader 数据进入 data_map **之后**，与 source 无关——stockdb 直连取的数默认照样写 `ohlcv_*.csv`。
- 报告页 K 线默认空态 + 按需加载（`load_price_series(symbols=...)`）读的是 run 目录落库文件，同样不依赖数据源 → 直连 run 的 WebUI K 线行为与其它 source 完全一致。
- `--no-ohlcv` 开关照常可用（行为与其它 source 一致）。
- 口径说明：落库/图表显示的是 fq 后价格（默认 hfq），与方案 A local loader（读 `close_hfq` 列）行为一致，非新增差异。
- 数据新鲜度：按 stockdb 库同步时点为准，run 卡片 provenance 记 `stockdb`。

### 2. registry 登记三处（`backtest/loaders/registry.py`）

- `VALID_SOURCES` += `"stockdb"`；`_loader_modules` += `"backtest.loaders.stockdb_loader"`；`_NO_NETWORK_FALLBACK_SOURCES` += `"stockdb"`。
- **不进** `FALLBACK_CHAINS`（仅显式 source 使用，不改变 a_share 默认链为腾讯的行为）。

### 3. 数值对拍（B 直连 vs A 快照，同源双链路一致性）+ ETF 抽验

- 同标的同区间：B 直连 close（`stockdb_fq="hfq"`）vs 方案 A `daily.parquet` 的 `close_hfq` 抽样 ≥10 只逐位一致；raw 模式 vs `daily.parquet` 原始 close 一致。
- pre_close 自洽抽查：`close/pre_close - 1 ≈ pct_chg/100`（含除权日样本，覆盖 pre_close 污染坑场景）。
- ETF 抽验（方案 A 快照不含基金，无法对拍，改自洽校验）：510050/159915/510880 直连取数非空、OHLC 合法、hfq 折算生效（510880 除权日前后 hfq/raw 比值跳变）、pre_close 走 shift(1) 回退后 `close/pre_close-1` 连续（无除权日伪跳变）。

## 执行清单

1. 取数路径钉死实验（分钟）：`rd.vals("分钟k",...)` / pipe 批量 / `get_data(frequency="1m")` 为空的原因对照；分钟 dict 字段清单实测（有无 pre_close/pct_chg/amount）；结论写进 loader 实现注释。
2. registry 三处登记 + metrics 年化表补 stockdb 条目（`_TRADING_DAYS`/`_BARS_PER_DAY`：日线 252×1、分钟按 240 bar/日）+ 回归（`test_valid_sources_covers_all_registered_loaders` 通过，既有源行为不变）。
3. 实现 `stockdb_loader.py`：SDK 注入 / 连接配置 / 分批批量取数（日线）/ `rd.vals` 分钟取数 / 复权自折算（hfq/qfq/none）/ 列规整 / pre_close 重建（日线 pct_chg 反推+shift 回退；分钟日线映射）/ industry_l1（bk 查询 + category）/ extra_fields / 分钟聚合（5m/15m/30m/1H 自然时钟）/ 不接 cache。
4. 单测 `agent/tests/test_stockdb_loader.py`：monkeypatch SDK 层测列规约、pre_close 重建（日线/分钟）、fq 三态折算、extra_fields（含 industry_l1）、interval 映射与聚合、fail-closed、分批逻辑；live 测试以标记（skip 无服务环境）单列。
5. 对拍验证：hfq 对拍 / raw 对拍 / pre_close 自洽（含除权日）/ ETF 抽验 / 分钟自洽（1m vs 5m 聚合 OHLC 一致、分钟 pre_close=当日日线 pre_close、窗口边界）。
6. 端到端：① 日线小池 run（20-50 只，MCP `backtest`，`extra_fields=["turnover","amount","float_share","industry_l1"]`）；② 分钟小池 run（10-20 只、窗口 2025-06 ~ 2025-09、interval="5m" 或 "1m"）：核心 artifacts 齐全、run 卡片溯源 stockdb、透传列非全零、引擎涨跌停/T+1 路径正常。
7. 文档与收尾：HowToUse 新增"stockdb 直连"章节（用法、.env、fq 语义、pre_close 重建、1H 口径标注、分钟窗口约束、与方案 A 快照取舍）+ 8.40 指针；计划状态/README、ITERATION_LOG（pre_close 污染属外部数据源坑，不入项目账本，处理落在 loader 实现与 HowToUse 8.48）。

## 开工前核对

> 2026-09-26 核对结果（状态切"已确认"前逐项核对）：

- 需求目标 / 范围与讨论记录一致 —— **通过**（2026-09-26 拍板：日线+分钟+ETF+行业；指数/北交所/日历不做；不替代方案 A）
- 范围/边界无被后续讨论反转但仍保留的旧约束 —— **通过**（"分钟留后续"已按拍板移除；fail-closed / 不进 fallback 链 / 零落盘 / hfq 默认 / extra_fields 声明式均与历轮拍板一致）
- 执行清单覆盖需求目标与验收标准 —— **通过**（分钟新增取数路径实验、metrics 年化条目、pre_close 日线映射、分钟聚合、分钟端到端均已列入）
- 验收标准可验证 —— **通过**（对拍/自洽/端到端/fail-closed 均有明确判据；分钟端到端判据"成交发生在分钟 bar 时点"可从 trades.csv 核对）
- 元信息已填（关联允许为待填）—— **通过**

补充决策依据（拍板项未覆盖的实现口径，按推荐方案执行、计划留痕）：分钟聚合用自然时钟（与 VTD 引擎/天勤一致，E011/E012 口径教训）；1H 与看盘软件 60m 差异文档标注；分钟 pre_close=当日日线昨收映射（涨跌停带基准语义）；复权统一自折算（绕开 SDK get_data 分钟路径异常）。

## 验证

- 单测：`python -m pytest agent/tests/test_stockdb_loader.py agent/tests/ -k "valid_sources or loader" -x`（回归 + 新增）。
- 对拍：对拍脚本/测试输出"逐位一致只数 + pre_close 自洽最大偏差"（预期 close max|diff| = 0；自洽偏差 < 0.01 个百分点，除权日样本单独列出）。
- 端到端：MCP `backtest(action="run")` 日线 + 分钟各一个 run 目录，产出核心 artifacts；`run_card.json` effective_sources 含 stockdb；`data_map` 含声明的额外列（非全零）；分钟 run 的引擎成交发生在分钟 bar 时点。
- fail-closed：停掉 stockdb.exe 后显式请求报 `NoAvailableSourceError`，不出现网络源兜底。

## 讨论记录

- 2026-09-25 用户提出：做方案 A 计划（P-20260905）中的方案 B——VTD 直连 stockdb 本地数据（数据目录 data/data1），先调研实现方式并写计划确认。
- 2026-09-25 调研结论：SDK 走 socket 读 `stockdb.exe` 服务（不直接读 LevelDB 文件），服务常驻是前提；批量取数性能实测充足；最大发现是 stockdb `pre_close` 字段被前复权污染（外部坑，实测复核），直连 loader 必须重建 pre_close，否则涨跌停带判错——已纳入实现与验证。
- 2026-09-25 拍板项（随本计划确认）：① 默认 `stockdb_fq="hfq"`（对齐方案 A 与研报复现口径，可配置）；② 额外列按 `extra_fields` 声明式透传（默认列最小，与 tushare/local 约定一致）；③ 不进 fallback 链 + fail-closed；④ 分钟线 loader/北交所留后续，**ETF 与行业列（industry_l1）纳入本期**（四轮答疑后修订）。
- 2026-09-25 三轮答疑（用户四问）：
  1. **hfq**：后复权（见风险/口径说明），默认口径的理由——历史值稳定、含分红总回报、对齐方案 A 与研报复现。
  2. **不进 fallback 链**：stockdb 仅在显式 `source="stockdb"` 时使用，不顶替腾讯成为 a_share 默认/兜底源；显式请求失败 fail-closed 报错不降级，防止数据口径被静默替换。
  3. **留后续项逐一澄清 + ETF 纳入**：分钟线（全市场 ~5 亿行任何 source 不可行，小池场景留后续）、行业（截面数据与 loader bar 契约不匹配，方案 A industry.parquet 已覆盖）、北交所（数据质量与引擎规则未验证、场景用不到）——均为有意延后非做不了。**ETF 实测在 stockdb 中有数据**（沪 5/深 1 前缀基金，复权因子表 1318 条基金除权记录，510050/159915/510880 hfq 折算正常；pct_chg/name 字段缺失走 shift(1) 回退），纳入本期支持（成本低）。
  4. **OOM 评估**：全市场日线可跑（loader 分批取数设计，峰值与现有 source 同级；报告层 V049 已修）；全市场分钟任何 source 都不可行。已补"分批取数（每批 ≤300 只）"设计与内存分级风险条目。
- 2026-09-25 四轮答疑（用户两问 + 事实修正）：
  1. **事实修正（用户指出）**：此前"stockdb 原库无分钟数据"结论**错误**——是 `get_data(frequency='1m')` 调用姿势问题；`rd.vals("分钟k",code,"*")` 实测 600519 有 101468 根 1m bar，覆盖 **2025-01-02 → 2026-09-24**。P-20260905"24GB 大头是分钟线"记录正确；sess_6516cbd7（打板策略复现）当时只看了方案 A 日线导出仓。
  2. **行业**：用户理解正确——行业标签=静态字段，走 extra_fields 透传即可（bk 实测 ≈0.4ms/只零成本），**industry_l1 纳入本期**（当前状态口径，同方案 A 近似）。
  3. **"日线选股 + 分钟执行"两阶段路径**（打板策略场景）：VTD 单 run 仅支持单一 interval（config["interval"]），不支持 run 内混周期；不改引擎的等效做法 = **两阶段工作流**——阶段 1 日线全市场选股（连板数需全市场日线，用方案 A 快照或本计划直连日线）输出每日龙头名单与窗口并集（数百只级）；阶段 2 分钟 run（interval="1m"/"5m"，codes=并集，signal_engine 内置读日线选股结果 + 分钟 bar 执行），排板限价/盘中止损/尾盘卖出均为分钟级真实时点。数据量级：300 只 × 421 天 × 240 bar ≈ 3000 万根 1m（5m ≈ 600 万），可行。约束：分钟回测窗口必须落在 2025-01-02~2026-09-24 覆盖期内；分钟复权口径/涨停价推导待立项专项验证。**不进本期**，打板复现开工时另立计划。
- 2026-09-26 五轮答疑（行业列冗余）：用户问"每根 bar 重复同一行业值是否冗余"。结论：冗余客观存在但无害——category dtype 下全市场日线仅数十 MB、未声明则零开销；重复列契合 data_map"每行=当日快照"契约（策略免对齐逻辑），旁路字典需动 fetch 返回协议与 runner（本期不改），且天然兼容未来历史时点行业数据。计划补 category dtype 实现细节。
- 2026-09-26 **最终拍板（范围变更：原=分钟 loader 留后续 → 现=分钟纳入本期）**：用户确认 ① hfq 默认可配置；② extra_fields 声明式透传、默认列最小；③ 不进 fallback 链 + fail-closed；④ **分钟、行业、ETF 本轮都做**。随拍板补充实现口径（推荐方案已获默认认可）：分钟取数走 rd.vals 底层 + 复权自折算统一日线/分钟；1m 原生、5m/15m/30m/1H 自然时钟聚合；分钟 pre_close=当日日线昨收映射；metrics 年化表补 stockdb 条目。计划状态切"已确认"。
- 2026-09-25 二轮答疑（用户三问）：
  1. **是否零导出**——确认直连不导出、不加工、不落任何数据文件（与方案 A 的差异即砍掉导出步）；由此计划修订：**不接 loader cache**（原"走 opt-in cache"改掉），`VIBE_TRADING_DATA_CACHE` 即使开启也不为 stockdb 产生缓存文件，彻底零落盘。
  2. **data-bridge 配置**——确认直连模式 data-bridge 零配置，只需 `.env` 配 SDK 路径（一次性）+ config.json 写 `source="stockdb"` 与 codes；已补"使用方式（配置面）"小节。
  3. **P-20260909 落库/懒加载兼容性**——已查证落库在引擎层 `_write_artifacts`（source 无关）、懒加载读 run 目录落库文件（source 无关），直连照常生效；已补"1c"小节并纳入验收关注。

## 风险 / 注意

- **服务依赖**：stockdb.exe 必须常驻；曾出现大查询后掉线（P-20260905 记录），is_available 探测 + fail-closed 报错信息中提示"重启 stockdb.exe"。该问题属外部数据源环境约束，不入 Mistake_Journal。
- **pyd 与解释器绑定**：`stockdb.pyd` 按特定 CPython 版本编译，当前 3.13.7 实测可用；VTD 升级解释器时需同步更换 pybao 内 pyd（升级风险记录在 HowToUse）。
- **socket_timeout**：SDK 本地默认 1s，全历史大查询可能超时；loader init 显式设 10s（可配置）。
- **raw 模式除权日**：pct_chg 反推的 pre_close 已含除权调整（正确）；若 pct_chg 缺失回退 shift(1) 在 raw 空间的除权日有比例误差——文档标注。
- **内存分级（全市场场景）**：全市场**日线**（5200 只 ≈1920 万行）可跑——loader 分批取数后内存峰值 ≈ data_map 本身 + 单批 dict，与现有 source（tencent 逐股）同级，不因直连引入新 OOM；报告层 OOM 已由 V049（按需加载）修复。全市场**分钟**（~5 亿行）任何数据源都不可行，不在本方案范围（分钟只适合小池/单标的，留后续）。
- 停牌日无 bar：与 tencent/local 一致按数据索引驱动，无需专门处理。
