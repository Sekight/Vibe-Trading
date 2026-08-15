# Vibe-Trading 项目迭代记录（ITERATION_LOG）

> 定位：过去做了什么、为什么、关键结论、去哪找细节；怎么用看 HowToUse，怎么做看计划文档。
> 项目规则唯一源：`AGENTS.md`（仓库根）。

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
- 参考：计划 P-20260814-timeline_charts_fix；run `rb_futures_5m_20250901_29_v1`、`daily_regression_10stocks`；全局日志 E064/E065/E066；commit 待补。
- 回归补充（2026-08-14）：按用户要求跑回归与日线 run 副本；发现并修复两处：①日线 trades 时间输出 `2023-03-08 00:00:00`，base.py 按 interval 自适应为纯日期；②ChartTab 残留旧 CandlestickChart 行导致重复渲染两个 K 线图、日线页面出现全部周期按钮，删除旧行。

### V019 · K 线 tooltip OHLC 错位修复（2026-08-14）
- 需求/背景：用户反馈 K 线悬浮框 O/H/L/C 错位，O 随 K 线递增（2025-09-01 显示 64、09-02 显示 65……），涨幅与涨跌额随之全错；1D 周期最明显。
- 实现：新增 `frontend/src/lib/candleOhlc.ts`（`pickCandleOhlc`：优先取 `params.data`，兼容 ECharts value 首位带索引的情况，取末尾 4 个元素，并对 OHLC 做合法性自检）；CandlestickChart tooltip 改用该工具；`resample.ts` 对输入做 Number 归一化并按 time 稳定排序，防止字符串/缺失字段错位。
- 反复讨论点：先排查主连数据，结论是 8/29 等日期主连与新浪 RB0 一致，250 天仅 2 个切换日差一天（暂不改 skill）；随后用 O 递增特征定位到 tooltip 把 ECharts 传入 value 的首位索引当成了 open。
- 关键细节：ECharts candlestick 的 `params.value` 可能带前导 index/x 维度，不能按前 4 个元素直接解构；`params.data` 是原始 [open, close, low, high]，优先使用最稳。
- 为什么这样做：展示层修复不碰回测/数据；自检能拦截未来任何 OHLC 错位，避免继续显示离谱涨幅。
- 验证：前端 vitest 413 passed（新增 candleOhlc/resample 单测）、npm build 通过；后端相关 pytest 160 passed；Chrome CDP 实际悬停 1D K 线，2025-09-01 显示 `O:3150 H:3161 L:3094 C:3115 -1.11%`，O 不再递增。
- 影响/注意：仅前端展示；主连切换规则差异保持原样，待后续单独讨论；旧 WebUI 页面需刷新/重启后端进程加载新 dist。
- 参考：无计划文档；run `rb_futures_5m_20250901_29_v1`；commit 待补。

### V020 · 交易方向与开平动作展示（2026-08-14）
- 需求/背景：K 线标记把平多显示成 S、平空显示成 B；交易表把平仓显示成卖出/买入，无法区分开平与多空。用户希望图表用 B/S/CB/CS 四类，交易表用多开/空开/多平/空平四类。
- 实现：新增 `frontend/src/lib/tradeActions.ts`（open/close + long/short 动作模型，可复用虚拟币/外汇）；`ui_services.build_trade_markers` 输出 action/direction；CandlestickChart 标记 B（多开）红、S（空开）绿、CB（多平）绿、CS（空平）红；TradesTab 方向文本四类、筛选 chips 四类、顶部计数四类；i18n 5 语言新增四个方向 key。
- 反复讨论点：颜色分组最初误写为“多开/多平绿、空开/空平红”，用户纠正为按原始 side：多开/空平（买入）红、空开/多平（卖出）绿，与图表颜色一致；用户拍板筛选分四类、颜色按图表语义、B/S 保持现状、买入/卖出文本改为多开/空开。
- 关键细节：开平判定用 pnl/holding_bars/holding_days，兼容旧 run；动作模型不绑定 A 股/期货字段名，后续虚拟币/外汇复用；不更新 HowToUse（用户指定）。
- 为什么这样做：开平与多空是交易语义基础信息，展示层统一模型避免图表和交易表各算一套。
- 验证：前端 vitest 全量 418 passed（2 个无关用例并发超时单独重跑通过，新增 tradeActions 19 passed）、npm build 通过；后端 `pytest tests/test_ui_services.py tests/test_analysis_digest.py tests/test_analysis_charts.py -q` 33 passed；Chrome CDP 验证交易表四分类文本与筛选（空开筛选只显示空开）、API markers 输出 open/close + long/short。
- 影响/注意：交易表筛选 chips 从买入/卖出改为四类，属于用户可见行为变化；旧 WebUI 需刷新/重启后端加载新 dist。
- 参考：计划 P-20260814-trade_action_ui；run `rb_futures_5m_20250901_29_v1`；commit 待补。

### V021 · K 线多笔交易标记合并（2026-08-14）
- 需求/背景：同一根 K 线上有多笔交易时 B/S/CB/CS 标记重叠，影响观看体验；希望同 bar 多笔合并显示。
- 实现：新增 `frontend/src/lib/tradeMarkers.ts`（mergeBarTradeMarks）；CandlestickChart 先把标记映射到当前周期 bar，再按 bar 分组合并。规则：同类型合并保留原色；类型不唯一合并为灰色 T（#9ca3af）；多个 T 只保留一个；合并标记放在 bar 最高价上方；tooltip 显示 `N 笔：B x1 @ 3150；CB x1 @ 3155` 摘要。
- 反复讨论点：用户要求 B+CB / S+CS 合并为 T；Codex 建议其他混合类型也一律合并 T、T 放最高价上方、图上不加数字、tooltip 显示明细，用户确认按推荐执行。
- 关键细节：合并粒度跟随当前周期（5m→1D 自动变化）；单笔标记保持原行为；不影响交易表与后端数据。
- 为什么这样做：展示层按 bar 聚合，减少遮挡同时保留逐笔信息。
- 验证：前端 vitest 431 passed、npm build 通过；后端相关 pytest 33 passed；Chrome 截图确认 1D 周期下同 bar 多笔交易显示灰色 T。
- 影响/注意：仅 K 线图展示；WebUI 刷新/重启后端加载新 dist。
- 参考：无计划文档；run `rb_futures_5m_20250901_29_v1`；commit 待补。
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
- 关联：计划目录 `documents/plans/`；无 commit（待提交）。
