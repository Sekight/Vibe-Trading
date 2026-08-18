# Vibe-Trading 项目迭代记录（ITERATION_LOG）

> 定位：过去做了什么、为什么、关键结论、去哪找细节；怎么用看 HowToUse，怎么做看计划文档。
> 项目规则唯一源：`AGENTS.md`（仓库根）。
> 历史条目中的本机绝对路径是历史事实，不代表当前路径；新条目一律用相对路径或占位符。

## 写前须知

1. 满足 AGENTS.md“收尾留痕”条件才写；一条一个主题；纯机械/纯文档小改不写。
2. 编号：写前重读本文件，取当前最大编号 + 1；写后复读校验，撞号则改为当前最大 + 1；已删除编号不补号；不预填、不凭记忆。
3. 不改历史；结论废弃在旧条目内标注“结论已废弃，以 V0XX 为准”。
4. 追加正文时，同步在索引表加一行。

## 索引
| 编号 | 日期 | 主题 | 一句话摘要 |
|---|---|---|---|
| V001 | 2026-08-07 | 建立 HowToUse 与 cmd 显示兼容 | 本地手册落地；cmd Rich 乱码用 Win32 控制台 API 根治 |
| V002 | 2026-08-10 | 持仓手数与 local 数据加载修复 | 补录条目，细节待补 |
| V003 | 2026-08-10 | 腾讯分页 / A股路由 / 成交模式 | 500 根分页；A 股走 A 股引擎；支持收盘成交与止损出场 |
| V004 | 2026-08-10~11 | 分析报告与图表 | 分析图 / LLM 报告 / 蒙特卡洛 / 基准落库并进 WebUI |
| V005 | 2026-08-12 | digest 落库与调参文档 | digest 现场构建缓存；指标解释；快速调参流程 |
| V006 | 2026-08-12~13 | 数据落库脚本与策略复刻 | 沪深300 落库脚本；《趋势永存》复刻修复 |
| V007 | 2026-08-10 | 本地部署与源码仓库切换 | pip 安装转 git clone 源码，editable 复用依赖并删除 pip 版 |
| V008 | 2026-08-11~12 | 参数调优、local 数据与基准 | 1~10 参数扫描；local 快照/缺标的行为；沪深300 基准离线化 |
| V009 | 2026-08-12 | A股负收益样本筛选 | 只取两个交易日 hfq 收盘价比较，4.4 秒命中 10 只 |
| V010 | 2026-08-13 | Pylance 导入提示修复 | run 脚本两行 lib 导入加 pyright ignore，消除 reportMissingImports |
| V011 | 2026-08-13 | rb 主连 5m 期货多空镜像回测 | 心忆 1m→5m local 聚合，引擎方向感知止损+跳点滑点，2% 风险仓位 13 笔 9 月回测 |
| V012 | 2026-08-14 | 项目 AGENTS.md 与计划文档工作流 | 项目工作台 + E:\document 计划目录，先计划、确认后实现 |
| V013 | 2026-08-14 | 查找规则分场景与计划双向索引 | ITERATION_LOG 管过去、计划文档管怎么做；状态归档防断链 |
| V015 | 2026-08-14 | 迭代日志写入阈值 | 大/中与含决策/坑/行为变化的改动必记；纯机械小改靠 git 留痕 |
| V016 | 2026-08-14 | 开工前核对闸门 | 确认前必过核对清单；“不做哪些”改为范围/边界 |
| V017 | 2026-08-14 | 规则补齐：进度恢复/废弃出口/核对展示 | git 为准恢复进度；已废弃状态；核对结果逐项展示 |
| V018 | 2026-08-14 | 回测分析时间精度与小周期图表修复 | 完整时间/trade_date、backtest 窗口、持仓单位、K线周期前端聚合、日/周/月热力图 |
| V019 | 2026-08-14 | K 线 tooltip OHLC 错位修复 | tooltip 改用 p.data/末尾 4 值并做 OHLC 自检，O 不再显示递增索引 |
| V020 | 2026-08-14 | 交易方向与开平动作展示 | K 线 B/S/CB/CS 与交易表多开/空开/多平/空平四分类，颜色按原始 side 语义 |
| V021 | 2026-08-14 | K 线多笔交易标记合并 | 同 bar 多笔交易合并为单字母，混合类型显示灰色 T，tooltip 保留逐笔摘要 |
| V022 | 2026-08-14 | 状态同步与索引维护规则补齐 | 确认后同步 README；日志同步索引；编号写后校验不补号 |
| V023 | 2026-08-15 | 计划目录迁入仓库与路径可移植化 | documents/plans 随源码管理；规则文档用占位符替换本机路径 |
| V024 | 2026-08-15 | 总手续费与单边手续费落盘展示 | trades.csv 每行单边 commission、total_commission 进 metrics/run_card/digest/WebUI，新建交易成本分组 |
| V025 | 2026-08-15 | 计划模板新增"项目调研"可选章节 | 调研/讨论事实基线查了才写；规则只落模板一处，不新增其他文档条目 |
| V026 | 2026-08-15 | 期货止损成交价 tick 取整 | 引擎侧 _TICK 静态表（88 品种），止损成交价多单 floor/空单 ceil，消除不可成交小数价格 |
| V027 | 2026-08-16 | 图表页保持行情可视时间窗口 | 调指标/切副图/切标签/加标的不再重置 K 线窗口；共享窗口机制 + ChartTab 保持挂载 |
| V028 | 2026-08-16 | 图表页多标的共享图表设置 | 指标/副图/周期/窗口提升为 run 级共享，切标的全保持；换 run 显式重置不串 |
| V029 | 2026-08-16 | 行情副图新增 ATR 指标 | 副图按钮新增 atr（14 周期 Wilder 平滑），纯前端增量、性能无感 |
| V030 | 2026-08-16 | 回测提速：默认跳过 PNG + loader 缓存 | 7 张 PNG 占回测 93%（约 557s）是唯一瓶颈；runner 默认不生图（--with-charts 才生），配合 VIBE_TRADING_DATA_CACHE 三年 15m 回测 596s→11s |
| V031 | 2026-08-16 | 建立项目踩坑日志 Mistake_Journal | 新建项目专属坑的认知与状态账本（M001-M020 存量收录）；坑先入账本、状态权威、单向指针；AGENTS/HowToUse 同步入口 |
| V032 | 2026-08-17 | 回测 fastrun：跳过 digest 慢分析 | runner 新增 --fastrun / --without-regime / --without-mae-mfe，跳过 regime/MAE-MFE；3 年 5m 回测 766s→32s（digest 构建 750s→1.1s）；digest 省略对应字段、报告整段跳过、前端 MAE/MFE 卡片占位 |
| V033 | 2026-08-18 | max_single_weight 按策略声明分组合并 | 策略声明 weight_groups（伪单位归属同一标的），单票仓位按组带符号求和（净敞口）；TA 4 单位同向时 max_single == max_portfolio；无声明保持单 code 口径；HowToUse 8.43/8.44 |
| V034 | 2026-08-18 | WebUI 新 tab「持仓与风险」：每天最大组合持仓 + 每天账户风险度 | digest 新增每日毛/净/单边三口径序列与 LLM 派生摘要；图 1 毛持仓默认可叠加净/单边，图 2 单边口径+100% 强平线标红；单边按 weight_groups 取大边（M028）；二期可迭代点：逐标的+下拉框按需加载 |
| V035 | 2026-08-18 | 持仓与风险 tab 图 1 改「每日组合持仓」收盘口径 | 图 1 三线改取收盘值（同刻快照，夜盘 bar 排除），图 2 保持日峰值（职责分工：图 1 日常、图 2 峰值风险）；HowToUse 8.45 补多标的角度 |
| V036 | 2026-08-18 | 持仓与风险 tab 新增「单标的每日持仓」图 | 下拉框选标的（weight_groups 分组+峰值标注），毛/净/单边三线，收盘默认/峰值切换；API 现读 positions.csv 按需加载（不进 digest）；HowToUse 8.45 三图说明 |
> 补录说明：V001-V009 为补录条目，依据 git 历史、HowToUse、全局复利与踩坑日志、`C:\Users\mumu\.codex\sessions` 会话记录回溯整理；当时未留痕的字段标“待补”。从下一条起，每次迭代收尾直接写正文。

## 模板

```markdown
### V0XX · 简短标题（日期）
- 一句话总结：本次迭代做了什么
- 为什么：核心原因 / 最终拍板（至少一句）
- 关键细节：实现要点 / 坑 / 注意（有计划文档时可写“详见计划 P-...”，无计划文档时必写实现要点和坑）
- 验证：测试命令或 run 结果（没有写“无”）
- 关联：计划 P-...（无则不写）/ commit / run / HowToUse 章节
```

填写规则：
- 5 个字段固定，没有的内容写“无”，不允许缺字段。
- 有计划文档：关键细节可写“详见计划 P-...”，或只补计划里没有的新坑。
- 无计划文档：关键细节必须写实现要点和坑。
- 为什么必填；关联至少填 commit。

---

## 迭代正文
### V001 · 建立 HowToUse 与 cmd 显示兼容（2026-08-07）
- 需求/背景：本地使用需要一份持续更新的中文手册；cmd 下 Rich 转义 `[36m` 等乱码影响阅读。
- 实现：新建 `HowToUse.md`；输出主题配置 `legacy_windows=True`，走 Win32 控制台 API。
- 反复讨论点：用户反复问 cmd / PowerShell / 终端到底什么区别、为什么短命令有时找不到、执行策略“禁止运行脚本”怎么放开；讨论只放开当前窗口（`-Scope Process`）还是永久放开（结论：`-Scope Process`，关窗即失效）；cmd 里 `[36m` 乱码怎么根治（结论：Win32 控制台 API，不依赖注册表）。
- 关键细节：激活后短命令与完整路径指向同一个 `vibe-trading.exe`；`-Scope Process` 只对当前窗口生效。
- 为什么这样做：注册表 VirtualTerminalLevel 实测不生效，Win32 API 从根源避免 ANSI 解析；手册按“概念→日常流程→FAQ→速查”组织，新问题只追加。
- 验证：cmd 下实测无 `[36m` 乱码。
- 影响/注意：`HowToUse.md` 此后持续追加，不删历史。
- 参考：commit `eb16b3b`；全局日志 E029/E030。

### V002 · 持仓手数与 local 数据加载修复（2026-08-10）
- 需求/背景：回测结果要展示持仓手数；local 数据源加载有问题。
- 实现：commit `77c0543`（本条目为补录，具体文件与实现细节未留痕，标“待补”）。
- 反复讨论点：无留痕（待补）。
- 关键细节：local loader 用法最终沉淀在 HowToUse 8.16。
- 为什么这样做：待补（当时未记录）。
- 验证：待补。
- 影响/注意：local loader 是离线回测主入口。
- 参考：commit `77c0543`。

### V003 · 腾讯分页 / A股路由 / 成交模式配置化（2026-08-10）
- 需求/背景：腾讯长区间被静默截断到 500 根；A 股 `tencent/local` 回测误走 CryptoEngine（出现可做空、无涨跌停的错误特征）；策略要求“14:55 判断、尾盘买入、止损价离场”，原引擎固定次日开盘成交。
- 实现：`tencent_loader.py` 单段 500 根向后分页；`runner._create_market_engine` 按 `markets` 含 `a_share` 返回 `ChinaAEngine`；`engines/base.py` 新增 `entry_mode/exit_mode`（默认 `next_open/next_open`），止损价由策略 `stop_prices` 传入。
- 反复讨论点：
  - 用户先让我画 runner 时序图，然后拿 run `20260808_032625_05_e9f25e` 追问“为什么跑进了加密货币引擎”“按你解释的逻辑应该是 a_share 才对”“为什么 config 里 source 是 tencent 不是 auto”，最后追问“这一步你要怎么改”（结论：引擎按标的市场路由，不是按数据源名）。
  - 成交时点：策略要“当日判断、尾盘买入、止损离场”，讨论是否做成配置（结论：`entry_mode/exit_mode` 配置化，默认值保持旧行为）；止损跳空怎么成交（结论：`min(开盘, 止损价)`）。
  - 后续用户又问 config.json 是 LLM 还是代码生成、能否保证“输入一句策略就生成正确 config”，并想要自动化流程（结论：config 由 `generate_backtest_config` 唯一生成，LLM 不直接写 config；需同步补 config 模板与校验逻辑）。
- 关键细节：腾讯单次最多 500 根且不报错；loader 缓存版本 3→4 让旧坏缓存失效；同盘模式 `shift_bars=0`；A 股代码必须带交易所后缀。
- 为什么这样做：数据源名不等于市场；写死成交时点无法复刻真实策略；配置默认值保证旧 run 不重跑也语义不变。
- 验证：A 股路由回归测试；v02 策略 24 笔、`total_return +32.5%`、100 股整数倍。
- 影响/注意：旧 run 配置不写新字段仍是旧行为；相关 HowToUse 8.24/8.35/8.38/8.39。
- 参考：commit `256c63a`；全局日志 E050/E051/E052；会话 08-10T01-37、08-11T23-43。

### V004 · 回测分析报告、分析图、蒙特卡洛与基准（2026-08-10~11）
- 需求/背景：回测结果需要可读的图表和 LLM 报告；要有稳健性验证；基准收益展示到 WebUI、基准标的可指定。
- 实现：新增分析 API `/runs/{id}/analysis` 系列与分析图；`analysis.md` / `analysis.status.json` / digest 落库；蒙特卡洛；benchmark 可配置，`auto` 按后缀识别 A 股并默认 `000300.SH`，失败降级等权。
- 反复讨论点：
  - 用户三批反馈视觉问题：缺 PNG/坐标说明、轴名被截断、回撤图 Y 轴说明落到底部、Markdown 纯文本可读性差；要求看真实页面而不是只看 tests/build（结论：前端视觉改动完成标准 = 浏览器截图核对）。
  - 分析图是否全部落 PNG（结论：digest 缓存优先，PNG 兜底）；基准取不到怎么办（结论：降级等权并在 run_card warnings 记录）；大 run 前端加载慢怎么解决（结论：digest 现场构建落库 + 指纹校验）。
- 关键细节：分析不阻塞回测；`generated_by` 区分 agent/runner；digest 指纹校验；5 语言 README 的 API 表要同步；`/docs` 需重启后端才刷新；ECharts 带 `inverse` 的轴 `nameLocation` 会反转。
- 为什么这样做：报告可复用、少烧 token；图表与报告口径统一从同一份 digest 取数。
- 验证：局部测试 + `npm run build`；浏览器截图核对布局（曾因只看 tests/build 返工，见 E056）。
- 影响/注意：HowToUse 8.36/8.37；前端视觉改动必须截图核对。
- 参考：commits `6e63f86` `5251437` `f2efdba`；全局日志 E053/E054/E056。

### V005 · digest 落库、易混淆指标解释、快速调参文档（2026-08-12）
- 需求/背景：大 run 分析图加载慢；“交易日持仓 / 自然日持仓”易混淆；调参反复烧 LLM。
- 实现：`analysis.digest.json` 现场构建并持久化，读时先校验 artifacts 指纹；指标名与含义加解释；HowToUse 新增 8.38（调参）/ 8.39（换标的）等。
- 反复讨论点：
  - 用户先按 8.38 做“反弹日后第 6 根 K 线”窗口 1~10 参数扫描并要 CSV 对比，随后问“为什么用本地数据每个副本还下载 ohlcv_*.csv，能改成不落库吗”（结论：快照是 runner 行为，批量调参后手动清理，记入 8.38）。
  - 用户问 local 只配 5 只、另外 5 只能否自动联网拉（结论：fail closed，不自动补，需配 data-bridge）。
  - 用户问基准用沪深300 且其他标的用本地数据，能否保证拉到（结论：先修基准 loader 走 local/data-bridge，yfinance 对 A 股指数不稳，见 8.26）。
  - 用户问换 10 只标的重跑怎么做最快（结论：复制 run 改 config 直接 runner，不烧 LLM）。
  - 技术点：`VIBE_TRADING_DATA_CACHE` 什么时候开（结论：WebUI/沙箱基本无效，直接 runner 固定区间才有用，更推荐 data-bridge）；参数探索不走 LLM，最后只给 top 候选写报告；改原 run 还是复制副本（结论：副本）。
- 关键细节：指纹一致直接读缓存，不一致才重建；删 `analysis_charts` / `ohlcv_*.csv` 会丢 digest 部分概览；`local:` 是 codes 前缀不是 source；数据闭区间截取只校验起点不校验终点。
- 为什么这样做：digest 一次构建多处复用，避免 WebUI 每次重算；参数探索要确定性、可复现、低成本。
- 验证：10 组参数扫描 CSV 对比；digest 落库后 WebUI 读取验证。
- 影响/注意：调参要清理产物；`trades.csv` 被 WPS/Excel 占用会 PermissionError。
- 参考：commits `d4a71e5` `c650f65` `50a8dd1`；会话 08-12T00-31。

### V006 · 数据落库脚本与《趋势永存》复刻（2026-08-12~13）
- 需求/背景：沪深300 成分股与历史 K 线要落库供离线回测；复刻聚宽《趋势永存》策略。
- 实现：`agent/scripts` 的 `lib/` + `run/` 结构（fetch_kline、get_csi300_constituents、run_fetch_csi300_kline）；baostock 主源 + akshare 兜底；修复“熊市不买”误清仓。
- 反复讨论点（本轮是我们讨论最密集的一次）：
  - 用户先给一段交易系统文案让我总结、分析可执行性，随后贴出聚宽完整代码，问能否在 vibe-trading 实现并回测（先只调研）。
  - 用户说“我几乎不可能下载所有成分股数据到本地”，让我评估 2020-2026 在线取日线的可行性。
  - 用户问能否单独跑 vibe-trading 的拉数据模块、脚本应放哪个目录、为什么 `alpha_bench_tool.py` 在 tools 不在 scripts（结论：那是项目原有代码；本项目新增开发脚本固定放 `agent/scripts`）。
  - 脚本设计：用户要求单一职责、模块化，我第一次拆太细被否；用户拍板 `lib/`（fetch_kline、get_csi300_constituents）+ `run/`（run_fetch_csi300_kline）三脚本结构；并要求 000300.SH 当普通标的由 fetch_kline 抓、成分脚本加 `--index` 参数、顶层“函数 + main()”、README 覆盖原有脚本。
  - 历史成分股怎么取：先讨论 akshare/tushare，用户没有 tushare token（有也只有 100 积分，权重最低）；最后用户从知乎文章找到 baostock `query_hs300_stocks` 历史成分表并贴给我，结论：baostock 主源 + akshare 兜底，考虑限流、重试、兜底和关键日志。
  - 目录纠错：我曾把代码建在 `work/scripts`，用户纠正必须放 `E:\gitCloneProgram\vibe-trading-src\agent\scripts` 并清空临时目录（E059）。
  - 文档反复改：README 目录结构、多余反引号、`--index` 用法、脚本注释里的续行符；用户问 parquet 还是 csv（结论：建议 parquet，data-bridge 两者都能用）、增量最快怎么做（结论：`--append` 补缺口合并）、append 能否多标的同时生效。
  - 复刻执行：用户要求先列执行清单、确认后再执行，最后“好，按 1~8 来执行”；执行中发现“熊市不买”被误实现成“全部清仓”，确认语义后修复（E062）；90 日动量向量化用 `np.polyfit` 抽样对拍（E063）。
- 关键细节：baostock 代码形如 `sh.600000`，归一化兼容 4 种写法；数据起点 2018-01-01 是休市日，用 01-02；append 要区分“本来无数据”和“拉取失败”；YAML 重复 `sources:` 键会静默丢数据；SignalEngine 默认值用字面量过 AST 门禁。
- 为什么这样做：脚本随仓库可复现；策略复刻必须忠实原始买卖语义，且数值实现必须对拍参考实现。
- 验证：滚动回归对拍最大绝对误差 `2.7e-12`；修复后 2020-2026 总收益 `1.90% → 25.14%`。
- 影响/注意：agent/scripts README 同步；data-bridge config 合并先解析再写；HowToUse 第 9 节脚本速查。
- 参考：全局日志 E059-E063；会话 08-12T07-13。

### V007 · 本地部署与源码仓库切换（2026-08-10）
- 需求/背景：用户要在 Windows 本地部署 Vibe-Trading（HKUDS），并希望以后自己改造代码、push 到自己的 GitHub 仓库。
- 实现：先 pip 安装验证，再切到 git clone 的源码仓库 `E:\gitCloneProgram\vibe-trading-src`，editable 安装复用依赖；删除 pip 版残留和误建 `.git` 的废弃目录；配置 git remote；后续补充 WebUI 构建/开发模式与 HowToUse。
- 反复讨论点：
  - 用户反复问 pip 安装与 git clone 两条路到底什么区别、pip 版为什么不能跑前端、git clone 改代码是否即时生效、依赖能否复用、要不要卸载 pip 版（结论：源码 editable 安装改代码即生效，前端需 setup/dev；用户决定卸载 pip 版）。
  - GitHub clone 一直失败，用户手动下载项目 zip 交给 Codex 继续操作（E028）。
- 关键细节：editable 安装后改 Python 源码即时生效；前端需 `vibe-trading setup` / `vibe-trading dev`；本机 Node LTS 用 winget 安装（E031）；github 主域不通时走 codeload/手动 zip。
- 为什么这样做：用户要长期二次开发，源码仓库 + git 才能追溯修改、push 到自己的仓库。
- 验证：`vibe-trading --version` / `--help`；配置 key 后的冒烟 run 跑通。
- 影响/注意：之后所有改动都落在 `vibe-trading-src`；HowToUse 第 1/5/7 章。
- 参考：全局日志 E027/E028/E031/E055；会话 08-10T22-07、08-10T22-21。

### V008 · 参数调优、local 数据与基准（2026-08-11~12）
- 需求/背景：用户按 8.38 做“反弹日后第 6 根 K 线内首次收盘突破中轨”策略的窗口参数 1~10 扫描并汇总 CSV；同时要搞清 local 数据快照、缺标的是否自动补、基准沪深300 如何离线可复现。
- 实现：参数扫描脚本（run 副本 + 改 `signal_engine.py` 顶部常量 + runner 汇总 `metrics.csv` 到 parameter_tuning 目录）；HowToUse 8.38/8.39 沉淀副本清理与快速换标的流程；基准链路修复，000300.SH 可通过 data-bridge/local 离线加载。
- 反复讨论点：
  - 用户问“为什么用本地数据，每个副本还下载 ohlcv_*.csv，能改成不落库吗”（结论：行情快照是 runner 行为，批量调参后手动清理，记录到 8.38）。
  - 用户问“指定 10 只，local 只配 5 只，剩下的能自动拉吗”（结论：不能，fail closed；需要把缺的标的补进 data-bridge）。
  - 用户问“基准标的用沪深300 需要怎么做？能保证拉到数据吗，其他标的用本地数据”（结论：先修基准 loader 走 local/data-bridge，再配 000300.SH CSV，不能依赖 yfinance 等网络路径）。
  - 用户问“策略不变，换成 10 只标的重跑怎么做最快”（结论：复制 run、改 config 的 codes/source/日期，直接 runner 重跑，0 token）。
- 关键细节：`local:` 是 codes 前缀不是 source；本地数据闭区间截取只校验起点不校验终点；`trades.csv` 被 WPS/Excel 占用会 PermissionError；参数扫描不烧 LLM，最后只给 top 候选 `--with-analysis`。
- 为什么这样做：参数探索要确定性、低成本、可横向对比；基准口径必须可审计，不能“看起来像沪深300”。
- 验证：10 组参数扫描 CSV 对比；000300.SH 基准修复后用 local 数据验证。
- 影响/注意：HowToUse 8.26/8.35/8.37/8.38/8.39。
- 参考：commit `27e6f22`、`c650f65`；会话 08-12T00-31。

### V009 · A股负收益样本筛选（2026-08-12）
- 需求/背景：用户要在沪深主板随机找 10 只“2022-01-01 ~ 2024-12-31 后复权股价净下跌”的标的（作为回测样本；2022-01-01 休市，实际按 2021-12-31 起算）。
- 实现：巨潮全量 A 股清单过滤沪深主板（排除 ST/退市），腾讯 `proxy.finance.qq.com` 单日 hfq 接口取两端收盘价比较，固定随机种子 + 每批 20 只 + 4 线程 + 请求间随机错峰 + 命中 10 只提前终止（E057 链路）。
- 反复讨论点：
  - 用户看到第一版全量三年 K 线方案后追问“你不需要给我跑标的的全量 k 线，分别算这 2 天的后复权股价再作比较就行了。你为什么跑这么久？？”（结论：两端价格即可判定涨跌，只取两天）。
  - 用户提供东财 `push2his` 和腾讯 `web.ifzq.gtimg.cn` 两个单日接口，问能否用于该任务（结论：腾讯 proxy 域更稳，东财 push2 当前环境不可作主源）。
  - 用户要求先讲防限流、加速方案再执行；中途还要求把临时代码、结果数据全部删除，只保留结论。
- 关键细节：2022-01-01 休市，回退 7 日窗口取最近交易日；腾讯 hfq 响应字段取 `data.{symbol}.hfqday`；Session headers 用模块级常量保证连接复用；固定随机种子保证可复现。
- 为什么这样做：免费源有单次条数/限流限制，先小样本验证再放量；两端价格比较是最短路径。
- 验证：约 4.4 秒命中 10 只，与 2024-12-31 hfq 收盘价表核对。
- 影响/注意：方法论沉淀到全局日志 E057；后续“两日区间随机抽样”可复用该链路。
- 参考：全局日志 E057；会话 08-12T02-42、08-12T02-55。

### V010 · Pylance 导入提示修复（2026-08-13）
- 需求/背景：用户问为什么 VSCode Pylance 对 `run_fetch_csi300_kline.py` 报两个 `reportMissingImports`；原因是 run 脚本用 `sys.path.insert` 动态注入 `lib` 目录，Pylance 静态分析不执行代码，无法解析 `fetch_kline` / `get_csi300_constituents` 两个顶层模块。
- 实现：`agent/scripts/run/run_fetch_csi300_kline.py` 两行导入保留 `# noqa: E402`，同一行追加 `# pyright: ignore[reportMissingImports]`。
- 反复讨论点：用户 ↔ Codex 讨论三个方案——①仓库根加 `.vscode/settings.json` 配 `python.analysis.extraPaths`；②导入行内加 pyright ignore；③把 scripts 改成包导入。结论：用户选方案 2，最小改动且不破坏“仓库根直接运行脚本”的现有用法。
- 关键细节：Pylance 不执行 `sys.path.insert`，所以运行时正常、编辑器报错；`pyright: ignore[reportMissingImports]` 需与该行放在一起。
- 为什么这样做：方案 3 会改变调用方式，方案 1 会新增仓库级配置，方案 2 只影响两行注释。
- 验证：`python -m py_compile agent/scripts/run/run_fetch_csi300_kline.py` 通过；脚本实际运行逻辑未改。
- 影响/注意：VSCode 重载窗口后 Pylance 波浪线应消失；不影响任何命令与数据层。
- 参考：会话 08-13；无 commit / run_id。

### V011 · rb 主连 5m 期货多空镜像回测（2026-08-13）
- 需求/背景：用户要用 Vibe-Trading 跑国内期货回测：rb 螺纹钢主连，数据源心忆 `.min` 1m（E:\application\心忆交易导师(期货版)\Data\rb），策略同款 run `20260808_032625_05_e9f25e`，针对期货加入做空镜像；反弹窗口改为 3 根（含）以内，反弹日不算第 1 根；仓位按每笔风险 = 原始本金 2%（初始 10 万）；回测 2025-09-01~09-29，数据往前多取用于指标预热。
- 实现：①心忆 1m 主连转 `work/xinyi_rb/rb_1m.csv`（85530 根），data-bridge 注册 `rb0000.SHFE`，local loader 现场聚合 5m（5841 根）；②引擎 `base.py` 止损成交价改方向感知（多单 low≤stop 按 min(open,stop)，空单 high≥stop 按 max(open,stop)），`china_futures.py` 新增 `slippage_points` 绝对跳点滑点；③策略 `rb_futures_5m_20250901_29_v1/code/signal_engine.py`：3 根反弹窗口、多空镜像、反向信号只平不开、同向不重复开仓、2% 风险整数手、权重上限 40%；④`config.json`：source=local、interval=5m、start 2025-06-01、end 2025-09-29、initial_cash=100000、margin_rate_override=0.08、slippage_points=1、entry/exit=close/stop。
- 反复讨论点：用户拍板 5m 周期；同一标的只持一个方向，反向信号只平不开；止盈镜像为多单 close≥上轨后 low≤中轨、空单 close≤下轨后 high≥中轨；反弹日不算第 1 根；手续费开平各万 1（rb 内置 commission 即万 1，不用 commission_override）、滑点 1 跳；预热不改引擎，只把 start_date 往前取，metrics 会覆盖预热段。Codex 执行中踩坑：顶层非字面量赋值和 @staticmethod 被 runner AST 门禁拒绝（E064）。
- 关键细节：`local:` 是 codes 前缀；rb 乘数 10、保证金 8% 对应杠杆 12.5；策略权重 = 手数×价格×乘数/(初始本金×杠杆)，cap 0.4 时实际单笔风险略低于 2%（09-03 16 手约 1.86%）；trades.csv 只输出日期、avg_holding_days 实为持仓 bar 数、trades.pnl 不含手续费，9 月绩效需从 equity.csv 截取（E065）。
- 为什么这样做：保持原 run 的布林+MACD+ATR 出入场语义，只做方向镜像与期货仓位/费用口径；数据只存 1m 主数据，周期由 local loader 聚合，后续 1h/20m 改 interval 即可复用。
- 验证：`pytest tests/test_engine_execution_modes.py tests/test_china_futures_engine.py -q` 52 passed；runner 复现 `final_value 99482.98`，13 笔交易全部落在 2025-09，做空 3 笔（09-04/09-16/09-19），止损 2 笔成交价方向对拍通过；9 月 return -0.5170%、max_drawdown -9.9383%（09-24 10:45 逐 bar 浮亏极值）、win_rate 7/13、手续费差额 = 期末权益 − trades.pnl 合计。
- 影响/注意：引擎改动影响所有期货回测（做空止损从旧实现方向修正），已有相关单测覆盖；run 目录 `rb_futures_5m_20250901_29_v1` 可直接换 interval 重跑 1h/20m；metrics 全窗口含 6-8 月空仓预热段，正式看 9 月请用截取口径。
- 参考：run_id `rb_futures_5m_20250901_29_v1`；全局日志 E064/E065；引擎改动 `agent/backtest/engines/base.py`、`china_futures.py`、`agent/tests/test_engine_execution_modes.py`。
### V012 · 项目 AGENTS.md 与计划文档工作流（2026-08-14）
- 需求/背景：用户要为 Vibe-Trading 建立项目级全局工作台（AGENTS.md），并增加“开工前计划文档”工作流：实现需求/迭代前先写计划、讨论到确认再写码，缓解细节遗忘与上下文压缩导致的工作混乱。
- 实现：新建 `AGENTS.md`（项目文档体系 + 7 条项目规则 + 计划分级）；新建 `E:\document\project_implementation_plan\vibe-trading`（git init、README 索引、`_template.md`、archive）；全局工作台 Vibe-Trading 规则改为移动+指针（v7.0）；HowToUse 第 11 节补 AGENTS/计划目录；全局日志补 E064-E066 索引与 E066 可复用方法。
- 结论已废弃，以 V013 为准：其中“archive/ 物理归档”已改为“状态归档，文件不移动”。
- 反复讨论点：
  - 计划文档放源码仓库还是 E:\document（用户拍板：E:\document，避免污染源码）；是否 git init（用户拍板：做）。
  - AGENTS.md 要不要项目地图（结论：不要，README_zh 已有 Project Structure；只留规则依赖的关键路径）。
  - 要不要完整工作流（结论：不要，只保留规则闸门，避免限制 agent 发挥）。
  - 模板字段多少（结论：4 必填 + 3 按需，不预建空章节）。
  - 状态机（结论：三态 讨论中/已确认/已完成；状态缺失按讨论中兜底，禁止改业务代码）。
- 关键细节：AGENTS.md 被上游 .gitignore 忽略，未纳入 git（本地规则文件）；计划目录独立 git 仓库初始提交 `868e070`；E064/E065 此前缺索引，本次一并补齐。
- 为什么这样做：规则+指针防双处漂移；精简模板降低维护负担；保守兜底不依赖 agent 自觉。
- 验证：AGENTS.md / 计划模板 / 工作台 v7.0 / HowToUse / 全局日志 E066 全部读回核对；计划目录 git log 正常。
- 影响/注意：后续 Vibe-Trading 任务按 AGENTS.md 规则闸门执行；大/中改动先建计划，小改动直接做但收尾写 ITERATION_LOG。
- 参考：本条目；全局日志 E066；计划仓库 commit `868e070`。

### V013 · 查找规则分场景与计划双向索引（2026-08-14）
- 需求/背景：用户复盘后提出三点优化：①查找顺序不该是一条链，ITERATION_LOG 是“过去”入口，计划文档是“怎么做”的细节；②ITERATION_LOG 与计划文档需要双向索引；③文档不全时要在“省时间”和“保证正确”之间平衡。
- 实现：AGENTS.md 改为分场景查找规则，新增规则 8“文档是索引，代码是真相”；计划目录采用状态归档（方案 A），README 增加双向关联说明与编号列；`_template.md` 增加编号/关联迭代字段；ITERATION_LOG 使用规则与模板同步；HowToUse 查找规则同步。
- 反复讨论点：
  - ITERATION_LOG 定位 = 过去做了什么、为什么，具体怎么做按索引找计划文档（用户提出，采纳）。
  - 双向索引何时加：写 ITERATION_LOG 收尾时（用户提出，采纳）；收尾动作三处同步。
  - 归档断链：方案 A 状态归档、文件不移动（用户拍板），链接永不失效。
  - 正确性与 token 平衡：分档聚焦核对，文档与代码冲突以代码为准（讨论后采纳）。
- 关键细节：计划编号 P-YYYYMMDD-短标题；关联迭代 V0XX；archive 目录废弃，物理归档不再使用。
- 为什么这样做：文档是索引不是真相；分场景查找省 token；状态归档让引用永久有效。
- 验证：AGENTS.md / 计划 README / 模板 / ITERATION_LOG / HowToUse 五处读回核对，旧链式表述无残留。
- 影响/注意：后续收尾必须三处同步（ITERATION_LOG、计划状态与关联、README 索引）；V012 的 archive 设计以本条目为准。
- 参考：本条目；计划仓库 commit（见 git log）。

### V015 · 迭代日志写入阈值（2026-08-14）
- 需求/背景：用户认为纯文档修改、随手小 bug 修复不值得每次都写迭代日志，避免噪音。
- 实现：项目 AGENTS.md 第 2/3/5 条改为“按条件记录”：大/中迭代、含决策/坑/行为变化、影响用户可见行为的改动必须写；纯机械/纯文档小改不强制，靠 git commit 留痕；删除 V014（计划短标题下划线，属纯机械改动，按新阈值不记录）。
- 反复讨论点：阈值按“改动大小”还是“是否有决策/坑”（结论：后者）；用户拍板认可。
- 关键细节：V014 已删除且不补号，后续编号从 V015 继续。
- 为什么这样做：日志记“为什么”不记流水账；机械改动由 git 历史承担。
- 验证：AGENTS.md / ITERATION_LOG / HowToUse 三处规则与索引一致，无 V014 残留。
- 影响/注意：后续小改动默认不写 ITERATION_LOG，除非含决策/坑/用户可见变化。
- 参考：本条目；无计划文档。

### V016 · 开工前核对闸门（2026-08-14）
- 一句话总结：状态切到“已确认”前新增开工前核对清单；需求目标改为“做什么 + 范围/边界”，取消独立“不做哪些”。
- 为什么：多轮讨论后文档可能滞后；负向清单“不做哪些”容易过期反转，改为范围/边界并靠核对清单兜底。
- 关键细节：核对不过只改文档不动代码；范围反转在讨论记录标注“范围变更：原→现”；小改动无计划文档不涉及核对。
- 验证：模板 / AGENTS.md 规则 4 / 计划 README / HowToUse 四处读回一致。
- 关联：无计划文档；HowToUse 第 11 节。

### V017 · 规则补齐：进度恢复/废弃出口/核对展示（2026-08-14）
- 一句话总结：补充恢复进度依据、计划创建后登记、已废弃状态、开工前核对展示格式、确认后状态更新，并清理索引空行。
- 为什么：陌生 agent 模拟发现这些缺口：进度恢复无依据、计划创建后可能漏登记、放弃的计划无出口、核对结果格式不明确、确认后状态归属不清。
- 关键细节：恢复进度以 git status / git diff 为准；计划 README 状态新增“已废弃”；新建计划后登记 README；核对结果逐项“通过 / 未通过 + 发现项”；用户确认后 agent 先改状态再写码。
- 验证：AGENTS.md / 计划模板 / 计划 README / ITERATION_LOG 读回一致，索引空行已清理。
- 关联：无计划文档；HowToUse 第 11 节。

### V018 · 回测分析时间精度与小周期图表修复（2026-08-14）
- 需求/背景：用户指出 5 类问题：①trades.csv/WebUI 交易时间最小精度只有天；②metrics/run_card 的持仓时间单位混乱（avg_holding_days 实际是 bar 数，digest 又按自然日算出 0 天）；③行情 K 线周期按钮（1M/3M/6M/1Y/ALL）硬编码日线 bar 数、tooltip 只显示天；④净值/回撤从数据起点开始，含大片预热空仓；⑤月度热力图、盈亏 vs 持仓、持仓分桶对短线交易失去作用。
- 实现：①local loader 保留源数据 trade_date 列并在聚合时取 last，ohlcv artifact 输出完整 timestamp + trade_date；trades.csv 写完整时间并新增 holding_bars；②metrics.py 新增 avg_holding_bars，avg_holding_days 按 bars_per_day 换算；③digest 全链路保留完整时间、buckets 改为 bar 分桶、新增 period_pnl（日/周/月）；④config 新增 backtest_start/backtest_end，引擎执行窗口截断到回测窗口，runner 向 SignalEngine 注入 trade_start/trade_end，rb 策略去掉硬编码；⑤前端新增 resample 工具，K 线周期按钮改为 5m/15m/20m/1h/2h/1D/1W/1M/1Y（按基础 interval 动态显示），1D/1W/1M/1Y 按 trade_date 分桶，隐藏后端 indicator_series，热力图支持日/周/月切换。
- 反复讨论点：用户先要求调研不改代码；拍板 backtest_start/end 分离数据窗口与回测窗口、热力图日/周/月切换、trade_date 期货日 K、周期切换只前端计算并隐藏后端指标、1m 行情本轮不做；Codex 建议引擎执行窗口截断（而不是只裁剪展示），digest 纳入 config 指纹自动重建。
- 关键细节：backtest_end 纯日期会被解析为 00:00 截掉最后一天，需按整天包含处理；digest 与 metrics 的 avg_holding_days 换算曾不一致，统一以 metrics.csv 为准；trades.csv 完整时间后 MAE/MFE 的 ohlcv key 也要完整时间；日线 run 的 trades 时间只显示日期、日内显示到分钟；1m 数据约 8.5 万根/标的，前端全量渲染会卡，后续用切片接口/懒加载。
- 为什么这样做：数据窗口负责指标预热，回测窗口负责执行与展示；前端聚合避免后端接口改造，隐藏后端指标避免周期切换后时间错位；trade_date 保证期货夜盘归次日。
- 验证：后端回归 `pytest tests/test_analysis_digest.py tests/test_analysis_charts.py tests/test_analysis_api.py tests/test_analysis_runner_hook.py tests/test_base_engine.py tests/test_engine_execution_modes.py tests/test_china_futures_engine.py tests/test_metrics.py tests/test_metrics_calc_integer_index.py tests/test_metrics_tracking_error.py tests/test_local_loader.py tests/test_local_loader_interval_case.py tests/test_ui_services.py tests/test_backtest_runner_security.py tests/test_runner_coverage.py tests/test_runner_env.py -q` 243 passed；前端 `npm run build` 通过、vitest 401 passed；Chrome 截图确认 rb 5m run 与日线 run `daily_regression_10stocks` 的周期按钮、时间格式、净值起点正常。
- 影响/注意：旧 run 的 analysis.digest.json 需要重建（schema v3）；config 新增 backtest_start/end 后 metrics 口径变为回测窗口；K 线周期切换后后端 indicator_series 暂时隐藏；1m 行情显示留待后续迭代。
- 参考：计划 P-20260814-timeline_charts_fix；run `rb_futures_5m_20250901_29_v1`、`daily_regression_10stocks`；全局日志 E064/E065/E066；commit `544ff45`。
- 回归补充（2026-08-14）：按用户要求跑回归与日线 run 副本；发现并修复两处：①日线 trades 时间输出 `2023-03-08 00:00:00`，base.py 按 interval 自适应为纯日期；②ChartTab 残留旧 CandlestickChart 行导致重复渲染两个 K 线图、日线页面出现全部周期按钮，删除旧行。

### V019 · K 线 tooltip OHLC 错位修复（2026-08-14）
- 需求/背景：用户反馈 K 线悬浮框 O/H/L/C 错位，O 随 K 线递增（2025-09-01 显示 64、09-02 显示 65……），涨幅与涨跌额随之全错；1D 周期最明显。
- 实现：新增 `frontend/src/lib/candleOhlc.ts`（`pickCandleOhlc`：优先取 `params.data`，兼容 ECharts value 首位带索引的情况，取末尾 4 个元素，并对 OHLC 做合法性自检）；CandlestickChart tooltip 改用该工具；`resample.ts` 对输入做 Number 归一化并按 time 稳定排序，防止字符串/缺失字段错位。
- 反复讨论点：先排查主连数据，结论是 8/29 等日期主连与新浪 RB0 一致，250 天仅 2 个切换日差一天（暂不改 skill）；随后用 O 递增特征定位到 tooltip 把 ECharts 传入 value 的首位索引当成了 open。
- 关键细节：ECharts candlestick 的 `params.value` 可能带前导 index/x 维度，不能按前 4 个元素直接解构；`params.data` 是原始 [open, close, low, high]，优先使用最稳。
- 为什么这样做：展示层修复不碰回测/数据；自检能拦截未来任何 OHLC 错位，避免继续显示离谱涨幅。
- 验证：前端 vitest 413 passed（新增 candleOhlc/resample 单测）、npm build 通过；后端相关 pytest 160 passed；Chrome CDP 实际悬停 1D K 线，2025-09-01 显示 `O:3150 H:3161 L:3094 C:3115 -1.11%`，O 不再递增。
- 影响/注意：仅前端展示；主连切换规则差异保持原样，待后续单独讨论；旧 WebUI 页面需刷新/重启后端进程加载新 dist。
- 参考：无计划文档；run `rb_futures_5m_20250901_29_v1`；commit `544ff45`。

### V020 · 交易方向与开平动作展示（2026-08-14）
- 需求/背景：K 线标记把平多显示成 S、平空显示成 B；交易表把平仓显示成卖出/买入，无法区分开平与多空。用户希望图表用 B/S/CB/CS 四类，交易表用多开/空开/多平/空平四类。
- 实现：新增 `frontend/src/lib/tradeActions.ts`（open/close + long/short 动作模型，可复用虚拟币/外汇）；`ui_services.build_trade_markers` 输出 action/direction；CandlestickChart 标记 B（多开）红、S（空开）绿、CB（多平）绿、CS（空平）红；TradesTab 方向文本四类、筛选 chips 四类、顶部计数四类；i18n 5 语言新增四个方向 key。
- 反复讨论点：颜色分组最初误写为“多开/多平绿、空开/空平红”，用户纠正为按原始 side：多开/空平（买入）红、空开/多平（卖出）绿，与图表颜色一致；用户拍板筛选分四类、颜色按图表语义、B/S 保持现状、买入/卖出文本改为多开/空开。
- 关键细节：开平判定用 pnl/holding_bars/holding_days，兼容旧 run；动作模型不绑定 A 股/期货字段名，后续虚拟币/外汇复用；不更新 HowToUse（用户指定）。
- 为什么这样做：开平与多空是交易语义基础信息，展示层统一模型避免图表和交易表各算一套。
- 验证：前端 vitest 全量 418 passed（2 个无关用例并发超时单独重跑通过，新增 tradeActions 19 passed）、npm build 通过；后端 `pytest tests/test_ui_services.py tests/test_analysis_digest.py tests/test_analysis_charts.py -q` 33 passed；Chrome CDP 验证交易表四分类文本与筛选（空开筛选只显示空开）、API markers 输出 open/close + long/short。
- 影响/注意：交易表筛选 chips 从买入/卖出改为四类，属于用户可见行为变化；旧 WebUI 需刷新/重启后端加载新 dist。
- 参考：计划 P-20260814-trade_action_ui；run `rb_futures_5m_20250901_29_v1`；commit `544ff45`。

### V021 · K 线多笔交易标记合并（2026-08-14）
- 需求/背景：同一根 K 线上有多笔交易时 B/S/CB/CS 标记重叠，影响观看体验；希望同 bar 多笔合并显示。
- 实现：新增 `frontend/src/lib/tradeMarkers.ts`（mergeBarTradeMarks）；CandlestickChart 先把标记映射到当前周期 bar，再按 bar 分组合并。规则：同类型合并保留原色；类型不唯一合并为灰色 T（#9ca3af）；多个 T 只保留一个；合并标记放在 bar 最高价上方；tooltip 显示 `N 笔：B x1 @ 3150；CB x1 @ 3155` 摘要。
- 反复讨论点：用户要求 B+CB / S+CS 合并为 T；Codex 建议其他混合类型也一律合并 T、T 放最高价上方、图上不加数字、tooltip 显示明细，用户确认按推荐执行。
- 关键细节：合并粒度跟随当前周期（5m→1D 自动变化）；单笔标记保持原行为；不影响交易表与后端数据。
- 为什么这样做：展示层按 bar 聚合，减少遮挡同时保留逐笔信息。
- 验证：前端 vitest 431 passed、npm build 通过；后端相关 pytest 33 passed；Chrome 截图确认 1D 周期下同 bar 多笔交易显示灰色 T。
- 影响/注意：仅 K 线图展示；WebUI 刷新/重启后端加载新 dist。
- 参考：无计划文档；run `rb_futures_5m_20250901_29_v1`；commit `544ff45`。
- 回归补充（2026-08-14）：按用户要求回归股票日 K run `daily_regression_10stocks`；前端全量 421 passed（4 个无关用例并发超时单独重跑 18 passed）、npm build 通过、后端相关 pytest 39 passed；Chrome 验证日线 K 线图正常渲染（B/CB 标记、日期轴、无报错），交易表四分类与筛选正常。

### V022 · 状态同步与索引维护规则补齐（2026-08-14）
- 一句话总结：明确确认后同步 README 状态、写日志必须同步索引、编号写后校验与不补号、已废弃留痕约定。
- 为什么：再次模拟发现：已确认时 README 可能不同步；日志正文与索引可能漂移；并发撞号仍无写后校验；已废弃计划无留痕约定。
- 关键细节：确认后更新计划 README 状态；写 ITERATION_LOG 时同步索引行；撞号后写者改最大+1；删除编号不补号；已废弃在计划文档头部标注、不写日志。
- 验证：AGENTS.md / ITERATION_LOG 写前须知 / 计划 README 读回一致。
- 关联：无计划文档；HowToUse 第 11 节。
### V023 · 计划目录迁入仓库与路径可移植化（2026-08-15）
- 一句话总结：计划目录迁入 `documents/plans/` 随源码 git 管理；规则文档去掉本机绝对路径，改为 `<repo_root>` / `<vibe_home>` 占位。
- 为什么：要支持其他电脑 / 其他 agent 协同开发，仓库内规则与计划必须 clone 可得，且不能依赖本机 `E:\document`、`C:\Users\mumu` 等路径。
- 关键细节：`.gitignore` 增加 `!AGENTS.md` 使 AGENTS 进入 git；AGENTS 全局规则改为“环境存在则遵守，否则本项目自治”；HowToUse 42 处硬编码路径替换为占位符；旧 `E:\document` 计划目录保留但不再活跃；历史迭代记录中的绝对路径保留。
- 验证：rg 确认 AGENTS / HowToUse / documents/plans 无本机绝对路径；git ls-files 确认 AGENTS 与计划文件被跟踪。
- 关联：计划目录 `documents/plans/`；commit `9979031`、`37c0f0a`。

### V024 · 总手续费与单边手续费落盘展示（2026-08-15）
- 一句话总结：trades.csv 每行记录单边手续费（开仓行=entry_commission、平仓行=exit_commission）；metrics/run_card 新增 `total_commission`；digest LLM 报告新建「交易成本」分组；WebUI 顶部指标展示总手续费。
- 为什么：手续费原先只体现在期末权益差额里，用户看不到总手续费与逐笔单边费用，跨市场对比（期货 vs A 股）口径也无处核对。
- 关键细节：TradeRecord 新增 `entry_commission`（默认 0.0，兼容旧构造）；trades.csv 事件式两行/回合，`commission` 列放 `pnl` 后；`total_commission` = Σ TradeRecord.commission = Σ trades.csv 行 commission，run_card 由 metrics 全量自动携带；digest 按 METRIC_GROUPS 自动渲染，用户拍板方案 A 新建「交易成本」分组（不并入「仓位与换手」）；旧 run 缺字段时前端/digest 按缺失容忍；顺带清理 V018 遗留重复行（trade_cols 双写、_empty_metrics 重复 key、DISPLAY_ORDER 重复项、digest 重复持仓行、_fmt_ts ("1d","1d") 笔误）。
- 验证：后端 165 passed（新增 metrics total_commission、digest 交易成本分组/渲染、base_engine trades.csv 单边落盘、futures 全周期手续费流）；前端 vitest 432 passed、npm build 通过；重跑 A 股日线 run `20260808_032625_05_e9f25e`：trades.csv 70 行（35 开 + 35 平）commission 合计 16125.2623，与 metrics.csv/run_card/digest 完全一致，买入侧抽查公式吻合（佣金 max(万2.5,5) + 过户费万0.1，卖出加印花税万5），LLM 报告含「交易成本 | total_commission | 总手续费」。
- 影响/注意：rb run `rb_futures_5m_20250901_29_v1` 的 code/signal_engine.py 今日被外部进程置零损坏（全 0 字节，daily 备份亦已置零，E:\CodexWorkSpace 无源码），无法重跑核对其预期合计 1155.31；rb 1m 数据与 data-bridge 配置完好，恢复策略文件后可直接重跑复验。期货手续费路径已由新增全周期单测覆盖（rb 万1 × 乘数 10）。
- 回归补充（2026-08-15）：用户找回策略文件后重跑 `rb_futures_5m_20250901_29_v1`：trades.csv 26 行（13 开 + 13 平）commission 合计 1155.3084，与 metrics.csv/run_card/digest/LLM 报告完全一致，符合计划预期约 1155.31；期货口径抽查吻合（rb 万1 × 乘数 10，开平对称、无印花税）；正文"无法重跑"结论作废，以此补充为准。
- 回归补充（2026-08-15）：用户发现 WebUI 交易表无手续费列——排查确认 trades.csv 与 API trade_log 一直有 commission，是 TradesTab 硬编码列未渲染。修复：TradesTab 加 commission 列（hasCommission 检测，位于 pnl 后，金额千分位 2 位小数）、5 语言包加 runDetail.commission、补 RunDetail 组件测试（列头+数值断言）；前端 433 passed、build 通过；API 实测 trade_log 26 行全带 commission、合计 1155.3084 与 metrics.total_commission 一致。教训已记全局踩坑日志 E003（清单里明确写的浏览器验证不能静默跳过）。
- 关联：计划 P-20260814-total_commission；commit `9eb9f8a`、`4d9bdb1`、`c8f36b1`；run `rb_futures_5m_20250901_29_v1`、`20260808_032625_05_e9f25e`。

### V025 · 计划模板新增"项目调研"可选章节（2026-08-15）
- 一句话总结：计划模板 `_template.md` 新增可选"项目调研"章节（置于需求目标之前），只记录实际调研过、或与用户讨论确认过的事实，查了才写。
- 为什么：跨会话/换 agent 后，开工前的调研结论（如 futures_stop_tick 的 tick 数据源、快照位置、方案取舍）没有结构化落点，最容易在上下文压缩中丢失；且"项目现状"类命名会误导为当前状态，改名"项目调研"后命名自带时效。
- 关键细节：规则只落在模板一处——注释写明"没查不写、不为了写而查、每条注明调研/讨论时间与来源"；AGENTS、计划 README、HowToUse 与存量计划均不改（新规则不追溯旧计划，避免为对齐而回填、为回填而编造）；开工前核对清单不加项。讨论时用户拍板：规则越多 agent 越易混乱，优先精简（呼应 V012 精简模板决策），原 4 道防漂移锁瘦身为"命名消化时效 + 模板注释即规则"两处。
- 验证：`_template.md` 读回核对，章节位于需求目标之前；ITERATION_LOG 索引与正文同步，编号写后校验 V025 无冲突。
- 关联：无计划文档；commit `5d044ae`（模板改动随 P-20260815 确认提交一并入库）。

### V026 · 期货止损成交价按最小变动价位取整（2026-08-15）
- 一句话总结：引擎侧新增 `_TICK` 静态表（88 品种），止损成交价按 tick 取整——多单 floor、空单 ceil，消除 rb 3143.7571 这类交易所不可成交的小数价格。
- 为什么：策略止损价 = low_min ± 0.3×ATR 带小数，引擎同 bar 止损按 `min/max(open, stop)` 直接以小数 stop 成交；rb 最小变动价位 1 元，交易所不存在小数成交价。盈亏靠合约乘数换算不受影响，但价格粒度不真实。
- 关键细节：`china_futures.py` 新增 `_TICK` 表（数据源：东财期货品种及交易规则接口 `/emfApi/pzjy/getPZJYInfo`，2026-08-15 抓取 88 品种、月均价合约 L_F/PP_F/V_F 未收录；接口编码不稳定 GBK/UTF-8 混用，需轮试解码；快照 E:\zcodeWorkSpace\期货品种最小变动价位.json）；`base.py` 新增 `get_price_tick` 默认钩子（None=不取整，A 股/境外引擎继承默认）与 `_round_stop_fill`（floor/ceil 到 tick）；跳空穿破按实际开盘价成交不取整；止损「设置价」仍由策略输出，仅「成交价」取整（方案 B 取舍：risk_per_lot 手数仍按策略原止损价算）。项目调研与三方案讨论见计划 P-20260815-futures_stop_tick。
- 验证：新增 5 组单测（tick 查表 rb/IF/au/T/未知、floor/ceil、长/空止损、跳穿不取整）；后端 188 passed；重跑 rb run 价格全整数（3143.7571→3143、3169.2857→3170），`100000 + pnl合计 − 手续费合计 = final_value` 一致，total_commission 1155.3084→1149.089（取整口径）；A 股日线 run `20260808_032625_05_e9f25e` 无回归（total_commission 仍 16125.2623）。
- 影响/注意：取整方向保守——多单 floor 卖出价更低、空单 ceil 买回价更高，绩效比取整前略悲观；`_TICK` 为静态表，新品种/规则调整后会过期，数据源与快照已留档，需要时重新抓取；`_MULTIPLIER` 本次未扩（数据源无手续费字段，避免乘数全费率缺的不对称）。
- 关联：计划 P-20260815-futures_stop_tick；commit `62b1c38`、`5d044ae`；run `rb_futures_5m_20250901_29_v1`、`20260808_032625_05_e9f25e`。

### V027 · 图表页保持行情可视时间窗口（2026-08-16）
- 一句话总结：调 indicators / 切副图 vol/macd/rsi/kdj / 切换标签 不再把 K 线可视窗口重置回默认；加标的时新图加载到当前同组窗口；删标的不影响其余图；换 run 恢复默认。
- 为什么：缩放/滑动状态只存在 ECharts 实例内，`setOption(notMerge=true)` 每次用「最后 250 根」硬覆盖 dataZoom.start；标签切换条件渲染卸载组件导致副图/指标/周期/窗口全丢；用户在多标的分析中频繁被重置打断。
- 关键细节：①模块级共享窗口 `sharedWindow`——datazoom 事件记录窗口百分比，`resolveZoom` 在 setOption 前沿用（调指标/副图不再重置），新图挂载时加入当前同组窗口，最后一张图卸载时清空（换 run 全卸载即归零，run 隔离无需额外代码，沿用 RunDetail runId effect 清空 selectedSymbols）；②ChartTab 保持挂载 + 非图表标签 CSS 隐藏（跨标签保留全部状态，重显靠既有 ResizeObserver 触发 resize）；③周期切换（行为 4）本轮不做；多标的窗口按百分比联动（与 echarts.connect 组行为一致）。纯前端，全部改动在 CandlestickChart.tsx + RunDetail.tsx，ChartTab 无 props 变更。
- 验证：新增 `chartWindow` 纯逻辑单测 5 个（默认窗口/沿用窗口/越界夹取）、RunDetail 保持挂载测试；前端全量 439 passed、npm build 通过。交互验证待用户浏览器实测（滑到非默认区间后调指标/切副图/切标签/加删标的/换 run）。
- 影响/注意：ECharts 实例在非图表标签时保持存活（内存可接受）；图表隐藏时容器 0 尺寸，重新显示依赖 ResizeObserver resize；`HowToUse.md` 的 macOS 协同改动为用户未提交内容，未纳入本次提交。
- 关联：计划 P-20260816-chart_window_preserve；commit `544658b`、`27dbd57`；run 无（纯前端改动）。

### V028 · 图表页多标的共享图表设置（2026-08-16）
- 一句话总结：把 指标/副图/周期/可视窗口 提升为 run 级共享状态，多标的切换标的（showOnly/删增）时全部保持；换 run 显式重置、不串数据。
- 为什么：V027 交付后用户反馈——多标的切换标的同时 indicators/副图/周期/时间窗口全部重置。根因：①指标/副图/周期是各图内部 useState，新挂载的图总是默认值；②模块级共享窗口「最后一张图卸载时清空」在切换标的经过全部卸载时误清窗口。
- 关键细节：新增 `chartWindow.ts` 的 `ChartView`（sub/overlays/period/window）与 `DEFAULT_CHART_VIEW`；RunDetail 持有 `chartView` 共享状态，runId effect 显式重置（与现有重置并列）；CandlestickChart 改受控组件（sub/overlays/period/window 来自 props、datazoom 事件上报窗口、工具栏全部走 onViewChange）；移除模块级 sharedWindow/计数清空；period 为 null 时各图回退 periods[0]（run 基础周期），新图挂载不会覆盖用户已选周期；ChartTab 保持挂载（V027）保留。
- 验证：前端全量 443 passed（含新增 CandlestickChart 组件测试 4 个：窗口随 props 应用、datazoom 事件上报、指标/副图切换窗口保持、默认窗口兜底）、npm build 通过；后端回归 188 passed（本次零 Python 改动，完整后端套件未跑——用户指示验证文档场景而非全量后端）。文档验证场景：场景 1/2（调指标/副图保持窗口）、3/4（加标的/切换标的入同窗口）由组件测试覆盖核心机制，场景 2（切标签）与场景 5/6（run 隔离）由架构保证（状态提升 + runId 显式重置）+ 既有 RunDetail 保持挂载测试；最终浏览器交互清单待用户实测。
- 影响/注意：ChartTab props 新增 chartView/onChartViewChange；多标的共用同一套指标设置（与窗口联动语义一致，比较口径统一）；datazoom 事件每次触发都会更新共享窗口并重渲染各图（setOption 效应依赖不含 window，不触发重建）。
- 回归补充（2026-08-16）：用户验证功能正常后反馈行情窗口拖动每次只能移动固定小步（V028 引入的回归）。根因：窗口入 React 状态后，datazoom 事件 → setChartView → 重渲染 → ChartTab 的 `markers={...filter(...)}` 每次生成新数组 → CandlestickChart setOption 效应依赖含 markers → 效应重跑 → 用滞后的窗口值 setOption → 与拖动打架。修复：可视窗口移出 React 状态改 run 级 ref（拖动零重渲染，run 切换时置空），markers 在 ChartTab 用 useMemo 稳定引用；组件测试更新（datazoom 写 ref、setOption 随 ref 应用窗口）；前端全量 443 passed + build 通过；拖动平滑由用户目视验证。
- 关联：计划 P-20260816-chart_window_preserve；commit `c907306`、`e4adcf1`、`ae5ad2c`；run 无（纯前端改动）。

### V029 · 行情副图新增 ATR 指标（2026-08-16）
- 一句话总结：WebUI 报告-图表行情页副图新增 ATR（14 周期，Wilder 平滑），与 vol/macd/rsi/kdj 同一排按钮切换，纯前端增量。
- 为什么：用户希望在行情副图加入波动率类指标；ATR 与 RSI 同为 O(n) 递推、后端零参与，属低成本高复用的小改动（用户拍板不写计划文档）。
- 关键细节：纯前端——后端 `charts.py` 只生成 PNG 静态图、digest 不参与行情指标，前端本就 `void indicators`（只用前端重算）。①`lib/indicators.ts` 新增 `calcATR(highs, lows, closes, period=14)`：TR = max(高−低, |高−前收|, |低−前收|)，首个 ATR = 前 14 个 TR 均值，此后 Wilder 平滑 `(ATR×(n−1)+TR)/n`，period 索引前返回 null（与 calcRSI 同风格）；②`lib/chartWindow.ts` 的 `Sub` 类型加 `"atr"`；③`CandlestickChart.tsx` 三处：indicatorCache 加 `atr`（与其余指标同批无条件预计算，每次数据变更仅多一次 O(n) 遍历，毫秒级无感）、渲染分支 `else if (sub === "atr")` 单折线（复用 RSI 写法）、副图按钮数组加 `"atr"`。i18n 无需改（副图按钮为硬编码小写 id + CSS uppercase）；tooltip 走通用分支自动显示 ATR 值；多标的共享 `ChartView.sub` 使 ATR 自动随切标的全图保持。
- 验证：`npx vitest run` 前端全量 449 passed（新增 calcATR 单测 5 个 + CandlestickChart atr 渲染用例 1 个）、`tsc --noEmit` 通过。交互验证（点 atr 按钮看折线）由用户浏览器目视确认。
- 关联：commit `eaa15b0`；run 无（纯前端改动）。

### V030 · 回测提速：默认跳过 PNG 图表 + loader 缓存（2026-08-16）
- 一句话总结：runner 默认不再生成 7 张 `analysis_charts/*.png`（加 `--with-charts` 才生图），配合 `VIBE_TRADING_DATA_CACHE=1`，三年 15m 回测从 596s 降到约 11s。
- 为什么：分段计时（cProfile + 分阶段计时）拆出 7 张 PNG（matplotlib）占全程 93%（约 557s），是唯一瓶颈；WebUI 分析图读 `analysis.digest.json` 算 ECharts、PNG 只是兜底图片（HowToUse 8.36 已注明）；数据侧由 loader 缓存（8.35）覆盖。
- 关键细节：`runner.py` 的 `main`/`_finalize_run_analysis` 新增 `with_charts` 参数（默认 False），`__main__` 加 `--with-charts`；digest 仍默认生成（WebUI 依赖）。耗时拆解（3 年 15m、缓存命中）：数据加载+聚合 0.6s、策略 generate 0.3s、引擎 run_backtest ~3s（其中逐 bar 执行约 2s；trades.csv/metrics/run_card 写入合计 <0.6s，不是耗时项）、digest ~5s、7 张 PNG ~557s。各阶段耗时已记入 HowToUse 8.38。
- 验证：默认跑 11s 且输出无 analysis_charts；`--with-charts` 才生成 PNG（约 557s）；指标/trades/digest 与生图版完全一致（回测确定性不受影响）。
- 影响/注意：命令行回测默认行为变化（以前自动生成 PNG）；需要 PNG 的场合（报告/贴图）加 `--with-charts`。HowToUse 8.38 已同步（含"每次回测自动生成 PNG"旧描述修正）。
- 关联：commit `4621fb3`；HowToUse 8.38/8.35；run `_cmp_v3_15m_v32_2022_2025`。

### V031 · 建立项目踩坑日志 Mistake_Journal（2026-08-16）
- 一句话总结：新建 `Mistake_Journal.md` 作为 vibe-trading 专属坑的认知与状态唯一账本；存量坑一次性收录（M001-M020）；AGENTS 规则/文档地图/查找规则与 HowToUse 第 11 节同步入口。
- 为什么：坑此前分散在 HowToUse（解法）、ITERATION_LOG（叙事）、全局日志（通用经验）三处，没有"坑是否已修复"的集中权威；经多轮讨论（是否建、是否冗余、存量迁移 vs 指针、账本定位）收敛为"认知与状态集中一处"的方案，避免为维护而维护（呼应 V012 精简模板、V015 写入阈值）。
- 关键细节：分工判据=跨项目通用→全局日志、使用解法→HowToUse、迭代叙事→ITERATION_LOG、vibe-trading 专属坑认知与状态→账本；维护规则=坑先入账本（入口）、状态权威在账本（HowToUse 日期标注仅为时效提示）、单向指针（账本→外部，不反向逐条）、修复/废弃条目内标注留痕、每周日自动任务确认后的坑清单入账本；存量 20 条从 HowToUse 8.x 与 ITERATION_LOG 提炼，状态抄自 HowToUse 现有日期标注；不收录全局日志条目（重叠坑一句话指回 E 号，如 M018→E003）；AGENTS 规则 2（收尾先入账本）/4（文档分流）、文档地图、查找规则同步。
- 验证：账本 M001-M020 编号连续、索引与正文一致；AGENTS（规则 2/4、地图、查找）/ HowToUse 第 11 节 / ITERATION_LOG 索引与正文读回一致。
- 关联：无计划文档；commit `914be47`。

### V032 · 回测 fastrun：--fastrun 跳过 digest 慢分析（2026-08-17）
- 一句话总结：给 `python -m backtest.runner <run_dir>` 增加 `--fastrun` / `--without-regime` / `--without-mae-mfe` 三个 CLI flag 控制回测后 digest 的计算内容；`--fastrun` 跳过 regime（相关性）与 MAE/MFE 分析，3 年 5m 回测从 766s 降到约 32s（端到端），digest 构建本身 750s→1.1s。
- 为什么：3 年 5m 缓存命中回测 766s 中 digest 约 750s 占 98%（cProfile 定位：`compute_edge_density` 每 bar 做一次 60-bar 窗口滚动 corr，`add_mae_mfe` 每笔交易遍历该标的全量 bar 筛持仓窗口，O(trades×bars)）；regime 对单标的/伪单位组合价值有限、MAE/MFE 属诊断性指标，调参场景可整体跳过（Mistake_Journal M027、全局 E010）。
- 关键细节：
  - `digest.py`：`build_digest` / `write_digest_json` 新增 `include_regime` / `include_mae_mfe`（默认 True）；跳过时 digest **整体省略** `regime` / `mae_mfe_summary` key（区分"未计算"与"无数据"）；`render_digest_for_llm` 两段改条件渲染（key 缺失整段跳过，完整版渲染与改动前逐字一致）。
  - `runner.py`：`__main__` 加三个 flag；`FASTRUN_SKIPS = {"regime", "mae_mfe"}` 模块级跳表常量（后续新增耗时步骤只追加集合）；`main` / `_finalize_run_analysis` 关键字参数透传。
  - 前端：RunDetail AnalysisChartsTab 的 mae_mfe 卡片在 payload 为空时显示"未计算（fastrun 模式或无可分析窗口）"占位而非空图；5 语言包新增 `chartMaeMfeNoData` 键。
  - 拍板边界：fastrun 重跑覆盖该 run 已有完整 digest（完整重跑可恢复）；`load_digest` 惰性重建=完整版（不写 digest 标记）；MCP backtest 工具不透传 flag（本次只覆盖 CLI）。
- 验证：
  - 新增单测：`build_digest` 跳过后无 regime/mae_mfe_summary key 且其余字段与完整版一致、`write_digest_json` 透传、`render_digest_for_llm` 精简 digest 不输出两段、`compute_chart_payload["mae_mfe"]==[]`；前端 mae_mfe 空 payload 占位测试。
  - 后端 pytest（analysis digest/charts/report/api + runner 相关）全绿（除 2 个存量失败，见下）；前端 vitest 450 passed + `npm run build` 通过。
  - 真实 run（3 年 5m ta_turtle）：同一 run 完整版 vs `--fastrun`——`metrics.csv`/`trades.csv`/`equity.csv` 字节一致（引擎不受影响）；digest 排除 generated_at/run_id/regime/mae_mfe_summary/trades 的 mae-mfe 字段后逐字段一致；CLI `--fastrun` 端到端 31.7s。
  - 存量修复：`test_analysis_runner_hook.py` 2 个用例在 HEAD 即失败（`_finalize_run_analysis` 的 `with_charts` 默认 False，V030 行为变更后测试仍断言默认生成图表）——已同步为三个用例：默认跳过 charts/report、`with_charts=True` 生成 charts 不调 LLM、`with_charts=True + with_analysis=True` 顺序 charts→report。
- 影响/注意：命令行默认行为不变；fastrun run 在 WebUI 的 MAE/MFE 卡片显示占位、LLM 报告不含 Regime/MAE-MFE 段（属预期降级）；HowToUse 8.38 已同步（含"fastrun 覆盖 digest 可完整重跑恢复"）。
- 关联：计划 P-20260817-fastrun；Mistake_Journal M027；全局 E010；commit `41e52dd`。

### V033 · max_single_weight 按策略声明分组合并（单标的口径）（2026-08-18）
- 一句话总结：引擎 `max_single_weight` 支持按"逻辑标的"聚合——策略在 `signal_engine.py` 声明 `weight_groups`（哪些 code 属于同一标的，如 TA 的 4 个伪单位），引擎按组**带符号求和**取峰值；无声明保持原"单 code"口径。TA 4 伪单位 run 实测 `max_single_weight == max_portfolio_weight`（0.14098），metrics.csv / run_card.json / run_card.md 三处同步。
- 为什么：V438 WebUI 报告 `max_portfolio_weight`(14.18%) 与 `max_single_weight`(4.88%) 数值差引起疑问——4 个伪单位（TA0001-0004.ZCE 共享同一 TA_1m.csv）其实是同一标的的加仓，单票口径应算整个标的；`max_single_weight` 按单 code 取峰值（4.88%）而组合按 4 单位之和（14.18%），不是 bug 但口径易误解。用户要求"加仓视为同一标的"，单票也变 14.18%，RUNCARD/metrics.csv 同步。
- 关键细节：
  - 分组来源拍板（方案 B）：策略文件声明 `weight_groups` 类属性（`{"TA": ["TA0001.ZCE", ...]}`），不用 config.json 字段（per-run 重复维护、config 塞策略语义）、不在引擎写死 TA（通用引擎不为单品种开特例）；`_validate_signal_engine_class` 只校验 __init__/generate，新增类属性无校验风险。
  - 聚合口径拍板：**带符号求和（净敞口）**，与 `max_portfolio_weight` 一致；依据是国内商品期货（含郑商所 TA）同一合约对锁保证金按单边收取，实际占用资金与风险 = 净敞口；锁仓 ≠ 平仓（持仓挂账、结算保证金按净额）。TA 策略 4 单位恒同向，该拍板对 TA 无实际数字影响。
  - 实现：`agent/backtest/engines/base.py` 新增模块级 `_single_weight_by_group(target_pos, weight_groups)`——空/非 dict 原样返回（向后兼容）；code→组映射未声明者以自身为组名；同一 code 声明多组取最后 + warning；`target_pos.T.groupby(keys).sum().T` 带符号合并。metrics 段（912-916 行）`getattr(signal_engine, "weight_groups", None)` 接入，改一处 metrics.csv / run_card 自动同步（digest 与 WebUI 只读产物）。
  - digest.py 释义更新：`max_single_weight` 注明"策略声明 weight_groups 时按组分组合并、带符号净敞口；未声明按单代码"。
- 验证：
  - 新增 6 个测试（`test_engine_robustness.py` TestSingleWeightGroup）：同组同向求和、同组反向净抵消、未声明 code 保持单 code、无/非 dict 声明原样返回、端到端 run 断言 `max_single == max_portfolio`。全量 `test_engine_robustness.py` 55 passed 1 skipped；digest/runner_hook 24 passed。
  - 真实 run：复制 v438（4H 10 年）加 `weight_groups` 声明 fastrun 重跑——`max_single_weight = max_portfolio_weight = 0.14098`（改动前单 code 4.88%）；metrics.csv / run_card.md 值一致。
- 影响/注意：默认行为零变化（无声明 run 与改动前一致）；只影响新 run；只影响 `max_single_weight`（by_symbol/risk_xray/positions.csv 仍按 code 口径）。策略侧声明是硬编码（换标的需同步）；同标的反向持仓时单票净敞口可能大于组合净敞口，口径易混——HowToUse 8.43/8.44 已写明。
- 关联：计划 P-20260818-single_weight_group；HowToUse 8.43/8.44；run `ta_turtle_4h_v438_swg_2014_2023`；commit `8ee5f0b`（含 V034 同批提交）。

### V034 · WebUI 新 tab「持仓与风险」：每天最大组合持仓 + 每天账户风险度（2026-08-18）
- 一句话总结：WebUI 报告页「分析图」右边、「分析」左边新增「持仓与风险」tab，两张图——①每天最大组合持仓（毛/净/单边三口径日取峰值，默认只显示毛持仓、图例可叠加）；②每天账户风险度（单边口径 = 保证金/权益，100% 强平虚线、超线标红）。digest 新增 `daily_position` / `daily_risk` 全量时序 + `position_risk_summary` 派生摘要（LLM 只拿摘要，不进全量序列）。
- 为什么：用户看不到"每天最大持仓"和"每天账户风险"两个关键风控图。行业规则调研确认：风险度 = 占用保证金 ÷ 客户权益 ×100%（客户权益含浮盈浮亏），>100% 追保、100%~120% 强平（各公司不同）。用户拍板：图 1 用毛/净/单边三口径（单边 = 真实期货对锁单边保证金）、图 2 用单边口径、日取峰值、单独开 tab；digest 去留经调研后确认写入（耗时 148ms + 156KB 可忽略，且 `compute_chart_payload` 签名不变、图表/LLM 单点同源）。
- 关键细节：
  - digest.py：`daily_position_and_risk(run_dir, weight_groups)` 读 positions.csv 按交易日聚合——毛 `sum|w|`、净 `sum w`（取 |净| 最大那根带符号）、单边按 `weight_groups` 组内取 `max(多头和, |空头和|)` 跨组合计，日取峰值；`daily_risk` = 单边（引擎保证金恒 = |权重|×权益，杠杆在 size/margin 两步抵消，故风险度 = 单边权重）。`_strategy_weight_groups` 从 code/signal_engine.py 读策略 weight_groups（无则单边=毛）；`_DIGEST_SOURCE_FILES` 加入 positions.csv（指纹联动重建）；`load_digest` 对旧 digest 做**增量兼容**——指纹只差 positions.csv 时仅补算持仓/风险序列（~0.15s），保留 regime/MAE-MFE 不触发全量重建（否则旧 run 首次访问 10 年 4H 约 11s）。
  - LLM 摘要：`position_risk_summary`（毛/风险 max、avg、超 50/80/100% 天数与占比、风险度最高日期），`render_digest_for_llm` 新增「仓位与风险摘要」段，**不渲染全量日序列**（测试断言字段名不出现在 prompt）。
  - 前端：RunDetail.tsx 新增 `PositionsRiskTab`（复用 charts API 的 daily_position/daily_risk）+ `DailyPositionChart`（legend 默认只显示毛、点图例叠加净/单边）+ `DailyRiskChart`（markLine 100% + 超线标红）；Tab 类型/按钮顺序改（analysisCharts → positions → analysis）；5 语言包 i18n（12 个新 key）。
  - 坑（M028）：单边实现初版写成 `pos_sum + |neg_sum|`，恒等于毛持仓（数学恒等式），锁仓样本应 20% 却得 40%；改为 `max(多头和, |空头和|)`。测试含锁仓日断言（gross=40/net=0/single=20）防回归。
- 验证：
  - 后端：test_analysis_digest.py 新增 4 用例（三口径日聚合含空头/锁仓日、缺 positions.csv 容错、build_digest/payload 字段、LLM 摘要段且不含全量序列字段名）——digest/charts/runner_hook/run_card 45 passed。
  - 前端：tsc 通过；vitest 450 passed；`npm run build` 成功（32.8s）。
  - 真实 run：v438 复制加 weight_groups（swg2）fastrun 端到端——digest 落盘 daily_position/daily_risk 各 2433 天，空头日 2014-01-09 gross=21.77/net=-21.77/single=21.77，risk max 21.77 / avg 1.42，over100 0 天，与手工核对一致。
- 影响/注意：新 tab 数据来自 digest（组合级序列 2400 点常驻，fastrun 也生成，不进跳表）；LLM 报告新增「仓位与风险摘要」段（token 增量极小）；口径差异（开仓价 vs 结算价、引擎逐 code 全额占用、目标权重口径）写进 HowToUse 8.45；**二期可迭代点**：逐标的持仓 + 下拉框按需加载（100 标的全量 8.9MB 不得进 digest，需 API 现读 positions.csv）。
- 关联：计划 P-20260818-daily_position_risk_charts；Mistake_Journal M028；HowToUse 8.36/8.45；run `ta_turtle_4h_v438_swg2_2014_2023`；commit `8ee5f0b`（含 V033 同批提交）。

### V035 · 持仓与风险 tab 图 1 改「每日组合持仓」收盘口径（2026-08-18）
- 一句话总结：图 1 从"每天最大组合持仓（日取峰值）"改为「**每日组合持仓（取收盘值计算）**」——三条线（毛/净/单边）都取每个交易日收盘时（最后一根日盘 bar，夜盘 bar 归下一交易日不参与）的持仓，是同刻快照；图 2「每天账户风险度」保持日峰值（含夜盘）。HowToUse 8.45 补充多标的是怎么看持仓与风险。
- 为什么：用户指出图 1 的"日取峰值"逻辑复杂（三条线峰值可能来自同一天不同 bar，非同一时刻快照，易误读）；且图 2 账户风险度（日峰值单边）已承担"最大持仓/峰值风险"职责，图 1 只需反映每天大概状态。收盘口径三条线取同一根 bar，职责分工清晰：图 1 看日常状态、图 2 看峰值风险。
- 关键细节：
  - digest.py `daily_position_and_risk` 拆分两套聚合：`daily_position` 取每自然日中 bar 时间 < 20:00 的最后一根（夜盘 20:00+ 归下一交易日、排除）；`daily_risk` 取每自然日 single 的 max（峰值，含夜盘）。实测 v437fixB：daily_position 2432 天（1 天纯夜盘无收盘）、daily_risk 2433 天；收盘毛 avg 1.96% < 峰值 single avg 2.08%（逻辑自洽）。
  - 摘要/LLM 文案：`position_risk_summary` 的 gross 系列基于收盘（文案"毛持仓(日峰值)"→"收盘毛持仓"），risk 系列基于峰值；测试同步。
  - 前端：图 1 标题「每天最大组合持仓」→「每日组合持仓」、标注"日取峰值"→"取收盘值计算"（新增 i18n key `positionsCloseNote`）；图 2 保留"日取峰值"；5 语言包更新。
  - 多标的角度写入 HowToUse 8.45：毛线看总占用（多标的下单边=毛）、净线只看方向、图 2 看峰值风险、"哪个标的最重"是二期可迭代点。
- 验证：test_analysis_digest.py 聚合测试改为收盘/峰值双口径断言（含"峰值 bar ≠ 收盘 bar"和夜盘 bar 排除用例）——25 passed；前端 tsc + vitest 450 passed；v437fixB fastrun 重跑核对（2014-01-09/24 收盘毛 41.28%、风险峰值 41.28%、over100 0 天）。
- 影响/注意：图 1 语义变更（峰值→收盘），新 digest 生效（旧 digest 缓存命中旧口径——需要重跑 run 或等指纹变化重建）；收盘 bar 定义为"非夜盘（<20:00）最后一根"，对 TA 4H（08/12/20 三根）取 12:00 日盘收盘；夜盘归交易日更精确的处理（按 trade_date）留待后续。
- 关联：计划 P-20260818-daily_position_risk_charts（上线后迭代）；HowToUse 8.45；run `ta_turtle_4h_v437fixB_2014_2023`；commit `15db5e1`。

### V036 · 持仓与风险 tab 新增「单标的每日持仓」图（2026-08-18）
- 一句话总结：「持仓与风险」tab 新增第三张图「单标的每日持仓」——下拉框选择标的（按策略 `weight_groups` 分组的逻辑标的，伪单位合并，选项标注峰值仓位），显示该标的每日毛/净/单边三线，默认收盘、可切换峰值；数据按需加载（新增 API 现读 positions.csv，单标的 ~140KB/次，不进 digest）。
- 为什么：V034 二期可迭代点（逐标的 + 下拉框按需加载）——多标的账户（RB/TA/FG 多空混合）需要逐标的观察"哪个标的最重"，组合级图只能看总数。用户拍板：收盘默认+峰值切换、毛/净/单边三线、不做叠加对比、按 weight_groups 分组；默认展示标的=列表第一个 + 下拉框标注峰值。
- 关键细节：
  - digest.py 重构抽取共享函数：`_per_bar_exposure`（每 bar 毛/净/单边）、`_daily_close_and_peak`（收盘=非夜盘最后一根/峰值=当日 single max）、`_position_series_pct`、`_load_positions_frame`；新增 `position_groups`（逻辑标的列表+峰值）、`single_group_daily_series`（单标的收盘/峰值序列）。组合级 `daily_position_and_risk` 改用共享函数（口径零变化，25 测试通过）。
  - API（runs_routes.py）：`GET /runs/{id}/analysis/positions/groups`（标的列表）、`GET /runs/{id}/analysis/positions/{group}`（单标的序列，现读 positions.csv 不落 digest）。
  - 前端：`SingleSymbolPositionCard`（下拉框 + 收盘/峰值切换 + 三线 ECharts；峰值模式单线=单边峰值，与图 2 同口径）；tab 顶部常驻三口径说明条（`positionsLegendNote`：毛=总占用 / 净=净敞口可负 / 单边=对锁取大边，5 语言）；i18n 5 语言新增 3 key。
- 验证：test_analysis_digest.py 新增 2 用例（position_groups 伪单位合并/多组独立/组合级跨组求和；缺 positions.csv 容错）——27 passed；前端 tsc + vitest 450 + build 全过；v437fixB 实测 groups=[TA(4 伪单位, 峰值 41.28)]，单标的 close 2432 天/peak 2433 天，与组合级逐字段一致。
- 影响/注意：单标的数据不进 digest（100 标的 ≈ 14MB）；收盘/峰值口径与组合级图 1/图 2 完全一致；无 weight_groups 时按原始 code 分组（V033 回退语义）。HowToUse 8.45 更新（三张图 + 多标的角度 + 可迭代点：多标的叠加对比模式）。
- 关联：计划 P-20260818-daily_position_risk_charts_v2；HowToUse 8.45；run `ta_turtle_4h_v437fixB_2014_2023`；commit 待补。
