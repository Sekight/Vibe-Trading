"""Single source of truth for the external-Agent backtest workflow.

The registry deliberately describes the public workflow at a higher level than
the strategy-generation skills.  The MCP tool schema, server instructions,
bridge skill, and documentation blocks are all rendered from this module so a
new workflow capability has one maintenance point.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from backtest.execution_modes import (
    NORMAL_EXECUTION_MODES,
    STOP_LOSS_MODES,
    SUPPORTED_NORMAL_PAIRS,
    validate_execution_modes,
)


CAPABILITY_REGISTRY_VERSION = "2026-08-27.1"
DEFAULT_ACTION = "run"
DEFAULT_SPEED = "fast"
DEFAULT_USE_CACHE = False

CORE_ARTIFACT_RELATIVE_PATHS: tuple[str, ...] = (
    "config.json",
    "code/signal_engine.py",
    "run_card.json",
    "artifacts/metrics.csv",
    "artifacts/trades.csv",
    "artifacts/positions.csv",
    "artifacts/equity.csv",
)

REQUIRED_COMPLETED_RUN_FILES: tuple[str, ...] = (
    "run_card.json",
    "artifacts/metrics.csv",
)


@dataclass(frozen=True)
class BacktestCapability:
    """One public action/working-mode description."""

    capability_id: str
    action: str
    title: str
    description: str
    runner_flags: tuple[str, ...]
    produces: tuple[str, ...]
    skips: tuple[str, ...]
    requires_completed_run: bool = False


BACKTEST_CAPABILITIES: tuple[BacktestCapability, ...] = (
    BacktestCapability(
        capability_id="fast_backtest",
        action="run",
        title="快速回测",
        description="执行 loader、SignalEngine 和回测引擎，跳过可选的慢速 digest 分析。",
        runner_flags=("--fastrun",),
        produces=(
            "artifacts/metrics.csv",
            "artifacts/trades.csv",
            "artifacts/positions.csv",
            "artifacts/equity.csv",
            "run_card.json",
            "analysis.digest.json",
        ),
        skips=("analysis_charts/*.png", "analysis.md", "LLM 报告"),
    ),
    BacktestCapability(
        capability_id="normal_backtest",
        action="run",
        title="普通回测",
        description="执行完整回测和完整 digest，但不隐式生成图片或 LLM 报告。",
        runner_flags=(),
        produces=(
            "artifacts/metrics.csv",
            "artifacts/trades.csv",
            "artifacts/positions.csv",
            "artifacts/equity.csv",
            "run_card.json",
            "analysis.digest.json",
        ),
        skips=("analysis_charts/*.png", "analysis.md", "LLM 报告"),
    ),
    BacktestCapability(
        capability_id="generate_charts",
        action="charts",
        title="补生成分析图",
        description="读取已完成 run 的派生摘要并生成 PNG，不重新取数或执行策略。",
        runner_flags=(),
        produces=("analysis.digest.json（必要时）", "analysis_charts/*.png"),
        skips=("loader", "SignalEngine", "回测引擎", "analysis.md"),
        requires_completed_run=True,
    ),
    BacktestCapability(
        capability_id="generate_report",
        action="report",
        title="补生成分析报告",
        description="读取已完成 run 的派生摘要并调用一次报告 LLM，不重新回测。",
        runner_flags=(),
        produces=(
            "analysis.digest.json（必要时）",
            "analysis.md",
            "analysis.status.json",
            "analysis.prompt.md",
        ),
        skips=("loader", "SignalEngine", "回测引擎", "analysis_charts/*.png"),
        requires_completed_run=True,
    ),
    BacktestCapability(
        capability_id="full_backtest_workflow",
        action="full",
        title="完整回测工作流",
        description="按普通回测 → 图表后处理 → 报告后处理的顺序显式执行。",
        runner_flags=(),
        produces=(
            "核心回测 artifacts",
            "analysis.digest.json",
            "analysis_charts/*.png",
            "analysis.md",
            "analysis.status.json",
            "analysis.prompt.md",
        ),
        skips=(),
    ),
)

CAPABILITY_BY_ID: dict[str, BacktestCapability] = {
    item.capability_id: item for item in BACKTEST_CAPABILITIES
}
CAPABILITY_BY_ACTION: dict[str, tuple[BacktestCapability, ...]] = {}
for _capability in BACKTEST_CAPABILITIES:
    CAPABILITY_BY_ACTION.setdefault(_capability.action, tuple())
    CAPABILITY_BY_ACTION[_capability.action] = (
        *CAPABILITY_BY_ACTION[_capability.action],
        _capability,
    )

BACKTEST_ACTIONS: tuple[str, ...] = ("run", "charts", "report", "full")
BACKTEST_SPEEDS: tuple[str, ...] = ("fast", "normal")
EXECUTION_FIELDS: tuple[str, ...] = (
    "entry_mode",
    "exit_mode",
    "stop_loss_mode",
)

_EXECUTION_FIELD_DESCRIPTIONS: dict[str, str] = {
    "entry_mode": "正常开仓/加仓的成交时点",
    "exit_mode": "正常信号平仓/止盈/减仓/反转的成交时点",
    "stop_loss_mode": "是否启用独立保护性硬止损路径",
}

EXECUTION_DEFAULTS: dict[str, str] = {
    "entry_mode": "next_open",
    "exit_mode": "next_open",
    "stop_loss_mode": "none",
}


def execution_schema() -> dict[str, Any]:
    """Build the nested ``execution`` JSON schema from the shared contract."""
    return {
        "type": "object",
        "additionalProperties": False,
        "description": (
            "Optional execution overrides. Omitted fields keep the values in "
            "config.json; the MCP call never rewrites config.json."
        ),
        "properties": {
            "entry_mode": {
                "type": "string",
                "enum": sorted(NORMAL_EXECUTION_MODES),
                "description": _EXECUTION_FIELD_DESCRIPTIONS["entry_mode"],
            },
            "exit_mode": {
                "type": "string",
                "enum": sorted((*NORMAL_EXECUTION_MODES, "stop")),
                "description": (
                    f"{_EXECUTION_FIELD_DESCRIPTIONS['exit_mode']}; legacy 'stop' "
                    "is shown only to return a migration error"
                ),
            },
            "stop_loss_mode": {
                "type": "string",
                "enum": sorted(STOP_LOSS_MODES),
                "description": _EXECUTION_FIELD_DESCRIPTIONS["stop_loss_mode"],
            },
        },
    }


def backtest_tool_schema() -> dict[str, Any]:
    """Build the public single-tool schema from this registry."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "run_dir": {
                "type": "string",
                "description": (
                    "Run directory containing config.json and "
                    "code/signal_engine.py. In config.json, keep "
                    "start_date/end_date (data and indicator warm-up) separate "
                    "from backtest_start/backtest_end (execution/statistics); "
                    "put execution codes for one real instrument in one "
                    "logical_groups group."
                ),
            },
            "action": {
                "type": "string",
                "enum": list(BACKTEST_ACTIONS),
                "default": DEFAULT_ACTION,
                "description": (
                    "run=execute backtest; charts=only chart post-processing; "
                    "report=only report post-processing; full=run all stages"
                ),
            },
            "speed": {
                "type": "string",
                "enum": list(BACKTEST_SPEEDS),
                "default": DEFAULT_SPEED,
                "description": (
                    "run speed. fast maps to --fastrun; normal computes the "
                    "complete digest. Ignored by charts/report."
                ),
            },
            "use_cache": {
                "type": "boolean",
                "default": DEFAULT_USE_CACHE,
                "description": (
                    "Enable loader cache for run/full. Post-processing does not "
                    "load market data."
                ),
            },
            "execution": execution_schema(),
        },
        "required": ["run_dir"],
    }


def execution_presets() -> tuple[dict[str, str], ...]:
    """Return all supported normal-entry/exit plus stop-loss presets."""
    result: list[dict[str, str]] = []
    for entry_mode, exit_mode in sorted(SUPPORTED_NORMAL_PAIRS):
        for stop_loss_mode in sorted(STOP_LOSS_MODES):
            result.append(
                {
                    "entry_mode": entry_mode,
                    "exit_mode": exit_mode,
                    "stop_loss_mode": stop_loss_mode,
                }
            )
    return tuple(result)


def validate_execution_request(requested: Mapping[str, Any] | None) -> dict[str, str]:
    """Validate an MCP execution object without reading or changing a run."""
    if requested is None:
        return {}
    if not isinstance(requested, Mapping):
        raise ValueError("execution must be an object")
    unknown = sorted(set(requested) - set(EXECUTION_FIELDS))
    if unknown:
        raise ValueError(f"execution contains unsupported field(s): {', '.join(unknown)}")
    values = dict(EXECUTION_DEFAULTS)
    for field in EXECUTION_FIELDS:
        if field in requested:
            value = requested[field]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"execution.{field} must be a non-empty string")
            values[field] = value.strip()
    validate_execution_modes(**values)
    return {field: values[field] for field in EXECUTION_FIELDS if field in requested}


def resolve_execution(config: Mapping[str, Any], requested: Mapping[str, Any] | None) -> dict[str, str]:
    """Resolve effective modes from config plus optional MCP overrides."""
    values = dict(EXECUTION_DEFAULTS)
    for field in EXECUTION_FIELDS:
        value = config.get(field)
        if value is not None:
            values[field] = str(value)
    overrides = validate_execution_request(requested)
    values.update(overrides)
    validate_execution_modes(**values)
    return values


def _markdown_table_rows() -> str:
    rows: list[str] = []
    for item in BACKTEST_CAPABILITIES:
        flags = ", ".join(item.runner_flags) or "—"
        produces = "、".join(item.produces) or "—"
        skips = "、".join(item.skips) or "—"
        rows.append(
            f"| `{item.capability_id}` | `{item.action}` | {item.title}：{item.description} "
            f"| {flags} | {produces} | {skips} |"
        )
    return "\n".join(rows)


def render_capability_markdown(*, numbered: bool = False) -> str:
    """Render the generated user-facing capability matrix.

    ``HowToUse.md`` is a numbered manual and exposes this as section 12;
    README capability blocks remain unnumbered.
    """
    presets = "、".join(
        f"{p['entry_mode']}/{p['exit_mode']}/{p['stop_loss_mode']}"
        for p in execution_presets()
    )
    schema = backtest_tool_schema()
    heading = "## 12. MCP 回测工作流能力表（自动生成）" if numbered else "## MCP 回测工作流能力表（自动生成）"
    return f"""{heading}

> 来源：`agent/src/backtest_capabilities.py`；注册表版本：`{CAPABILITY_REGISTRY_VERSION}`。
> 回测时直接调用 `backtest` 工具即可。`fast_backtest`、`generate_charts`、`generate_report` 只是回测能力名称，不需要单独安装或调用。

默认调用：`backtest(run_dir, action=\"run\", speed=\"fast\", use_cache=false)`。
它会执行真实回测，但不生成 PNG、不调用报告 LLM，也不隐式启用行情缓存。用户明确要求复用行情时，再传入 `use_cache=true`；需要图片或报告时，再显式调用同一个工具的 `action=\"charts\"` 或 `action=\"report\"`。

| 能力 ID | action | 作用 | runner flags | 允许生成 | 明确跳过 |
|---|---|---|---|---|---|
{_markdown_table_rows()}

### 公共参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `run_dir` | 必填 | 已允许路径下的独立 run 目录 |
| `action` | `run` | `run`、`charts`、`report`、`full` |
| `speed` | `fast` | `fast` 使用 `--fastrun`；`normal` 生成完整 digest；charts/report 不重新回测 |
| `use_cache` | `false` | 只影响 run/full 的 loader cache；只有用户明确要求时传 `true`，单次设置不修改全局 `.env` |
| `execution` | 省略 | 可选覆盖 `config.json` 的三字段；不改写原 config |

`execution` 的字段是 `entry_mode`、`exit_mode`、`stop_loss_mode`。当前四个合法 preset 为：`{presets}`。
旧 `exit_mode=stop` 只用于返回迁移错误，不能自动解释为 hard stop。

数据预热区间与实际回测区间必须分开：`start_date` / `end_date` 用于加载行情并提供指标预热数据，`backtest_start` / `backtest_end` 用于实际交易及收益、回撤、metrics 统计；例如 MA300 至少需要在 `backtest_start` 前准备 300 根有效 K 线，且策略要正确使用或跳过预热 bar，MCP 不会替 Agent 推算 lookback 或重写数据层、引擎层。若同一真实标的拆成多个执行 code，必须在 `config.json.logical_groups` 中归入同一 group，WebUI 才会把 K 线、持仓风险、交易筛选和统计按一个标的显示。

图表/报告是已完成 run 的后处理：它们可以读取或更新派生的 `analysis.digest.json`，但不得改变核心 `config.json`、策略代码、`run_card.json`、`metrics.csv`、`trades.csv`、`positions.csv`、`equity.csv`。

MCP schema 摘要：`{schema['properties']['action']['enum']}`；缓存默认 `{schema['properties']['use_cache']['default']}`。
""".rstrip()


BRIDGE_WORKFLOW_RULES: tuple[str, ...] = (
    "Vibe-Trading 的目录结构：策略 run 应有 config.json、code/signal_engine.py，以及由系统生成的 artifacts/、run_card.json 等结果文件。",
    "config.json 的基本格式：由 Agent 配置数据源、标的、周期、日期、回测窗口、成本和当前三字段执行契约；start_date/end_date 用于加载行情并提供指标预热数据，backtest_start/backtest_end 用于实际交易与收益、回撤、metrics 统计（例如 MA300 要提前准备至少 300 根有效 K 线，策略仍需正确处理预热 bar）；同一真实标的若拆成多个执行 code，必须在 config.json.logical_groups 中归入同一 group，WebUI 才会按一个标的显示 K 线、持仓风险、交易筛选和统计；具体字段和允许值以当前引擎契约为准。",
    "signal_engine.py 的接口要求：只实现 SignalEngine 及其 generate(data_map) 策略逻辑，遵守现有信号、索引和安全约束。",
    "可调用的 MCP 工具：先使用当前 MCP 注册表提供的工具；回测统一使用单一 backtest 入口，不自行假定已不存在的工具或参数。",
    "禁止修改回测引擎和数据加载器：市场规则、取数、成交、费用、artifacts 由 Vibe-Trading 负责。",
    "生成阶段与回测阶段必须分离：先完成策略代码和配置，再单独进行 MCP 回测、结果读取和后续分析。",
    "回测前必须经过人工确认：Agent 只能在用户确认策略逻辑、配置和执行模式后调用回测。",
    "回测后必须读取 trades.csv、positions.csv、metrics.csv：同时结合 equity.csv、run_card.json 检查逐笔交易、持仓和汇总指标。",
    "迭代时一次只改一个问题：每个变体使用独立 run 副本，记录改动、预期影响和实际结果。",
    "失败时禁止自动无限重试：先分类为配置、接口、数据、引擎或策略问题，报告阻塞原因并请求下一步决定。",
)


def render_bridge_skill() -> str:
    """Render the pure workflow-boundary skill; parameter details stay in MCP."""
    body = "\n".join(f"{index}. {rule}" for index, rule in enumerate(BRIDGE_WORKFLOW_RULES, 1))
    return f"""---
name: vibe-trading-bridge
description: Vibe-Trading 与外部 Agent 协作时的目录、策略生成、人工确认、回测和迭代边界。
category: tool
---

{body}
"""


def render_mcp_instructions() -> str:
    """Render server-level routing instructions from the registry."""
    return f"""Vibe-Trading backtest workflow contract (registry {CAPABILITY_REGISTRY_VERSION}):
- To run or analyze a backtest, call the `backtest` tool. `fast_backtest`, `generate_charts`, and `generate_report` are workflow labels, not separate tools to install or call.
- Default external-Agent route: action=run, speed=fast, use_cache=false. This runs loader, SignalEngine, and the built-in engine, but skips PNG, the report LLM, and implicit loader-cache enablement. Set use_cache=true only when the user explicitly asks to reuse cached market data.
- charts and report are post-processing actions for an already completed run. They must not start a loader, SignalEngine, or backtest engine. Derived analysis.digest.json may be refreshed; core run artifacts must remain unchanged.
- report calls one report LLM. It is not strategy generation and must not start an optimization loop.
- full is an explicit run -> charts -> report workflow.
- Strategy generation and backtesting are separate phases. Require human confirmation before the first backtest. Do not rewrite backtest engines or loaders.
- Use execution fields entry_mode, exit_mode, and stop_loss_mode only through the registered schema. Legacy exit_mode=stop must surface a migration error.
- For small-period runs, keep the data window and execution window separate: `start_date`/`end_date` load bars and provide indicator warm-up data, while `backtest_start`/`backtest_end` define actual trading and return/drawdown/metrics statistics. For example, MA300 needs at least 300 valid bars before `backtest_start`; the strategy must use or skip warm-up bars because MCP does not infer lookback requirements.
- If multiple execution codes represent one real instrument (for example, pyramid/add-on pseudo codes), place them in the same `config.json.logical_groups` group. This is the source of truth that lets WebUI merge their K-line, position/risk, trade-filter, and statistics views; otherwise they are shown as separate instruments.
- If a run fails, classify the failure and stop; never retry indefinitely.
""".strip()


def _replace_generated_block(original: str, block: str, marker: str) -> str:
    begin = f"<!-- BEGIN GENERATED: {marker} -->"
    end = f"<!-- END GENERATED: {marker} -->"
    generated = f"{begin}\n{block.rstrip()}\n{end}"
    start = original.find(begin)
    if start < 0:
        separator = "\n" if original.endswith("\n") else "\n\n"
        return original.rstrip() + separator + generated + "\n"
    end_pos = original.find(end, start + len(begin))
    if end_pos < 0:
        raise ValueError(f"generated block {marker!r} has a begin marker but no end marker")
    end_pos += len(end)
    return original[:start] + generated + original[end_pos:]


def sync_generated_files(repo_root: Path, *, check: bool = False) -> list[Path]:
    """Synchronize generated docs/skill files, or report drift in check mode."""
    repo_root = Path(repo_root)
    outputs: dict[Path, str] = {
        repo_root / "agent" / "src" / "skills" / "vibe-trading-bridge" / "SKILL.md": render_bridge_skill(),
    }
    doc_blocks = {
        "HowToUse.md": render_capability_markdown(numbered=True),
        "README.md": render_capability_markdown(numbered=False),
    }
    for relative in ("HowToUse.md", "README.md"):
        path = repo_root / relative
        if not path.exists():
            continue
        current = path.read_text(encoding="utf-8")
        outputs[path] = _replace_generated_block(
            current, doc_blocks[relative], "backtest-capabilities"
        )

    changed: list[Path] = []
    for path, expected in outputs.items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != expected:
            changed.append(path)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(expected, encoding="utf-8")
    return changed
