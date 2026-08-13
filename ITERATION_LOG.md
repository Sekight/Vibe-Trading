# Vibe-Trading 项目迭代记录（ITERATION_LOG）

> 用途：解决“只记得大概、忘了当初为什么”的问题。一条记录 = 一次迭代（一轮需求 / 修复 / 优化）。
> 定位：`HowToUse.md` 讲“怎么用”，本文件讲“每次改了什么需求、怎么实现、反复讨论过什么、有哪些细节、为什么这么做”。
> 与 git 的关系：本文件给 git 历史补充“动机与取舍”；commit hash / run_id 负责还原代码与复现结果。

---

## 一、使用规则

1. **写入时机**：每次迭代收尾（测试通过、交付完成）时追加，当日事当日毕；不积攒、不补写流水账。
2. **一条一个主题**：一次迭代写一条；多个独立改动就写多条，不要“一揽子”混写。
3. **字段完整**：需求/背景、实现、反复讨论点、关键细节、为什么这样做、验证、影响/注意、参考 八项；没有就写“无”或“待补”。
4. **协作讨论留痕**：`反复讨论点` 必须同时写“用户 ↔ Codex 双方讨论”（谁提出、怎么定）和“Codex 执行中关注的技术点”；补录条目注明来源（会话记录 / commit / 全局日志）。
5. **可复现**：每条尽量带 commit hash、run_id、测试命令与结果，保证几个月后能一键复现。
6. **查找规则**：新需求 / 新迭代先看计划目录；回顾过去先查本文件，再按条目“参考”中的计划编号定位计划文档；使用问题查 HowToUse.md；文档与代码冲突以代码为准。
7. **不改历史**：新条目只追加；旧结论被推翻时，在旧条目内部标注“结论已废弃，以 V0XX 为准”，保留原文。

---

## 二、条目模板

```markdown
### V0XX · 简短标题（日期）
- 需求/背景：为什么做这次迭代（用户诉求、bug、新数据需求……）
- 实现：改了哪些文件/模块/配置，核心逻辑一句话
- 反复讨论点：用户 ↔ Codex 双方讨论的问题与最终结论（谁提出、怎么定）；再列 Codex 执行中反复确认的技术点
- 关键细节：容易再踩的细节，例如夜盘跨日、单次条数上限、默认值兼容
- 为什么这样做：当时考虑过的备选方案与取舍
- 验证：测试命令/结果、run_id、指标前后对比
- 影响/注意：会影响谁、需要怎么回归、相关 HowToUse 章节
- 参考：commit hash / run_id / 全局日志编号 / 计划编号 P-...（收尾时填）
```

---

## 三、索引

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

> 补录说明：V001-V009 为补录条目，依据 git 历史、HowToUse、全局复利与踩坑日志、`C:\Users\mumu\.codex\sessions` 会话记录回溯整理；当时未留痕的字段标“待补”。从下一条起，每次迭代收尾直接写正文。

---

## 四、迭代正文

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
