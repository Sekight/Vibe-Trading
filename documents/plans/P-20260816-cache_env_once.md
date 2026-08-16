# 计划：loader 缓存只配置一次（直跑 runner 也加载 vibe_home/.env）

> 编号：P-20260816-cache_env_once
> 状态：讨论中
> 日期：2026-08-16
> 关联迭代：待填（收尾时填 V 号）
> 关联：commit / run（收尾时补）

## 项目调研

- 内部·配置：`VIBE_TRADING_DATA_CACHE=1` 写在 `<vibe_home>\.env`（默认 `~/.vibe-trading/.env`），按 HowToUse 8.35 是一次性配置——设计意图是"开一次，所有回测入口都生效"。来源：HowToUse 8.35（2026-08-16 读）。
- 内部·根因：`agent/backtest/runner.py` 顶部 `load_dotenv()` 无参数，只找 CWD（agent/）及父目录的 `.env`；仓库里没有 `.env`，所以 `<vibe_home>/.env` 从不被加载。而 `backtest/loaders/base.py` 的 `loader_cache_enabled()` 走 `src/config/accessor.get_env_config()` → `os.getenv`，缓存开关完全依赖进程环境变量——env 没加载 = 缓存关。来源：读 runner.py / base.py / accessor.py（2026-08-16）。
- 内部·现有机制：CLI / preflight / ui_services 都走 `src/providers/llm._ensure_dotenv()`，候选顺序 `~/.vibe-trading/.env` → `agent/.env` → `cwd/.env`；`src/config/paths.get_runtime_root()` 支持 `VIBE_TRADING_HOME` 覆盖。唯独 runner 不调用它。来源：读 llm.py / paths.py（2026-08-16）。
- 内部·实证：直跑 `python -m backtest.runner` 时 `loader_cache_enabled()=False`；`export VIBE_TRADING_DATA_CACHE=1` 后 = True；缓存目录 `~/.vibe-trading/cache/loaders/local` 只有当初 rb 2022-2025 一次留下的 1 个 parquet。来源：本机实测（2026-08-16）。
- 内部·非问题项：缓存 key = 版本 + source + symbol + timeframe + start/end + fields，内容寻址——换标的/区间本来就产生新 key，这是设计使然，不在本次范围。来源：base.py `make_loader_cache_key`（2026-08-16）。

## 需求目标

- 做什么：让 `python -m backtest.runner <run_dir>` 直跑时也自动加载 `<vibe_home>/.env`，恢复"缓存只配置一次"的设计语义；不再要求每次命令前手动带 `VIBE_TRADING_DATA_CACHE=1`。
- 范围 / 边界：只动 runner 的 env 加载；不改 loader 缓存逻辑、不改 key 算法、不动 CLI/WebUI 已有行为（它们已走 `_ensure_dotenv`）。
- 验收标准（一句话）：不带任何前缀环境变量直跑 runner，`loader_cache_enabled()` 为 True 且缓存 parquet 落盘到 `<vibe_home>\cache\loaders`。

## 实现方案

- 方案 A（推荐）：runner.py 启动时复用现有 `_ensure_dotenv()`（从 `src.providers.llm` 导入）替代/补充无参 `load_dotenv()`；或显式 `load_dotenv(get_runtime_root() / ".env")`。改动小、与其他回测入口行为一致。
- 方案 B：在 `agent/.env` 放 `VIBE_TRADING_DATA_CACHE=1`（`.env` 不进 git）——能修，但仍是"手工再配一次"，新环境易漏；不解决"设计是一次性"的本意，只作 A 的补充说明。
- 方案 C：维持现状，每次命令前 `export`/前缀带变量——即当前 workaround，用户已明确不接受（设计应是一次性）。
- 讨论结论：倾向 A；B 仅作为 A 落地后的可选局部覆盖；C 仅作回退。

## 执行清单

1. runner.py：用 `_ensure_dotenv()`（或 `load_dotenv(vibe_home/.env)`）替换/补充无参 `load_dotenv()`
2. 直跑 runner 验证：不带 env 前缀，`loader_cache_enabled()`=True，新标的/区间缓存落盘
3. 回归：WebUI/CLI 入口不受影响（已走 `_ensure_dotenv`）；现有 rb 缓存仍命中
4. HowToUse 8.35 的"待优化"条目更新为已修复说明

## 开工前核对

（状态从"讨论中"切到"已确认"前逐项核对；核对结果按清单逐项展示"通过 / 未通过 + 发现项"）

- 需求目标 / 范围与讨论记录一致
- 范围/边界无被后续讨论反转但仍保留的旧约束
- 执行清单覆盖需求目标与验收标准
- 验收标准可验证
- 元信息已填（关联允许为待填）

## 验证

（落地后）不设 `VIBE_TRADING_DATA_CACHE` 环境变量，直跑 `python -m backtest.runner "<run_dir>"`：新区间取数后 `cache\loaders\local` 出现对应 sha256 parquet；同一区间二次跑不再取数（缓存命中）。

## 讨论记录

- 2026-08-16 用户提出：缓存设计上应"只启动一次"，现在每次都要在请求里显式带 `VIBE_TRADING_DATA_CACHE=1`，不合理；要求评估并优化。
- 2026-08-16 调研：根因是 runner 的无参 `load_dotenv()` 不加载 `<vibe_home>/.env`，而 loader 缓存开关读 `os.getenv`；CLI/UI 已用 `_ensure_dotenv()` 正确加载。结论：改 runner 一处即可恢复设计语义。
- 方案讨论：A（复用 `_ensure_dotenv` / 显式加载 vibe_home/.env，推荐）；B（agent/.env 手工加一行，治标）；C（维持 export，仅回退）。

## 风险 / 注意

- `_ensure_dotenv()` 有一次性全局标记（`_dotenv_loaded`）；runner 是独立进程，调用无副作用。
- 只在首个候选 .env 存在时加载，行为与 CLI 一致，不会重复覆盖环境。
- 改动只影响 runner 进程内 env；沙箱临时 HOME 路径（WebUI/agent 子进程）不受影响，维持现状。
