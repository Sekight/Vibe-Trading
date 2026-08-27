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


CAPABILITY_REGISTRY_VERSION = "2026-08-27.2"
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
                    "code/signal_engine.py. The config.json inside it follows "
                    "the engine-owned BacktestConfigSchema, including indicator "
                    "warm-up and execution/statistics windows plus logical_groups; config fields "
                    "are not top-level MCP arguments."
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


def backtest_config_schema() -> dict[str, Any]:
    """Return the engine-owned JSON schema for ``run_dir/config.json``.

    Import lazily so callers that only need the MCP call schema do not load the
    full runner module during module import.  The runner model remains the
    authoritative source for config fields, types, defaults, and descriptions.
    """
    from backtest.runner import BacktestConfigSchema

    return BacktestConfigSchema.model_json_schema()


def _schema_type_label(schema: Mapping[str, Any]) -> str:
    """Render a compact human-readable label from a JSON-schema fragment."""
    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        non_null = [item for item in any_of if item.get("type") != "null"]
        if len(non_null) == 1 and isinstance(non_null[0], Mapping):
            return f"optional {_schema_type_label(non_null[0])}"
        return " | ".join(_schema_type_label(item) for item in any_of)

    ref = schema.get("$ref")
    if isinstance(ref, str):
        return ref.rsplit("/", 1)[-1]

    schema_type = schema.get("type")
    if schema_type == "array":
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            return f"array[{_schema_type_label(item_schema)}]"
        return "array"
    if schema_type == "object":
        return "object"
    if isinstance(schema_type, str):
        return schema_type
    return "value"


def _schema_default_label(schema: Mapping[str, Any], *, required: bool) -> str:
    if required:
        return "必填"
    if "default" not in schema or schema.get("default") is None:
        return "省略"
    default = schema["default"]
    if isinstance(default, bool):
        return "true" if default else "false"
    return str(default)


def _backtest_config_schema_rows() -> tuple[tuple[str, str, str, str], ...]:
    schema = backtest_config_schema()
    return _schema_rows(schema)


def _schema_rows(schema: Mapping[str, Any]) -> tuple[tuple[str, str, str, str], ...]:
    """Return ordered field rows from a JSON-schema object."""
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    rows: list[tuple[str, str, str, str]] = []
    for name, raw_field in properties.items():
        if not isinstance(raw_field, Mapping):
            continue
        rows.append(
            (
                str(name),
                _schema_type_label(raw_field),
                _schema_default_label(raw_field, required=name in required),
                str(raw_field.get("description") or ""),
            )
        )
    return tuple(rows)


def _backtest_config_definition_rows(
    schema: Mapping[str, Any],
) -> tuple[tuple[str, str, tuple[tuple[str, str, str, str], ...]], ...]:
    """Return nested config definitions and their generated field rows."""
    definitions = schema.get("$defs") or {}
    result: list[tuple[str, str, tuple[tuple[str, str, str, str], ...]]] = []
    for name, raw_definition in definitions.items():
        if not isinstance(raw_definition, Mapping):
            continue
        rows = _schema_rows(raw_definition)
        if rows:
            result.append(
                (
                    str(name),
                    str(raw_definition.get("description") or ""),
                    rows,
                )
            )
    return tuple(result)


def render_backtest_config_summary(*, markdown: bool = False) -> str:
    """Render the self-describing config contract for Agents and docs."""
    rows = _backtest_config_schema_rows()
    schema = backtest_config_schema()
    definitions = _backtest_config_definition_rows(schema)
    if markdown:
        lines = [
            "### `config.json` 配置契约（由 `BacktestConfigSchema` 生成）",
            "",
            "以下字段属于 `run_dir/config.json`，不是 `backtest` MCP 工具的顶层参数。",
            "",
            "| 字段 | 类型 | 必填/默认 | 说明 |",
            "|---|---|---|---|",
        ]
        lines.extend(
            f"| `{name}` | `{field_type}` | `{default}` | {description} |"
            for name, field_type, default, description in rows
        )
        for name, definition_description, definition_rows in definitions:
            lines.extend(
                [
                    "",
                    f"#### `{name}` 元素结构",
                    definition_description,
                    "",
                    "| 字段 | 类型 | 必填/默认 | 说明 |",
                    "|---|---|---|---|",
                ]
            )
            lines.extend(
                f"| `{field_name}` | `{field_type}` | `{default}` | {description} |"
                for field_name, field_type, default, description in definition_rows
            )
        if schema.get("additionalProperties") is not False:
            lines.extend(
                [
                    "",
                    "未列出的字段仍可作为引擎专属扩展字段；实际执行以 runner 和对应引擎校验为准。",
                ]
            )
        return "\n".join(lines)

    lines = [
        "- `run_dir/config.json` follows the engine-owned `BacktestConfigSchema`; "
        "these are file fields, not top-level MCP arguments.",
        "  Config fields (generated from `BacktestConfigSchema`):",
    ]
    lines.extend(
        f"  - `{name}` ({field_type}, {default}): {description}"
        for name, field_type, default, description in rows
    )
    for name, definition_description, definition_rows in definitions:
        lines.append(f"  - `{name}` item structure: {definition_description}")
        lines.extend(
            f"    - `{field_name}` ({field_type}, {default}): {description}"
            for field_name, field_type, default, description in definition_rows
        )
    if schema.get("additionalProperties") is not False:
        lines.append(
            "  - Unlisted fields remain available for engine-specific extensions; "
            "the runner and selected engine are authoritative at execution time."
        )
    return "\n".join(lines)


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
    config_summary = render_backtest_config_summary(markdown=True)
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

{config_summary}

配置模型中的 `start_date/end_date`、`backtest_start/end` 和 `logical_groups` 字段说明定义了数据预热、实际执行窗口和逻辑标的合并口径；MCP 不会替 Agent 推算 lookback 或重写数据层、引擎层。

图表/报告是已完成 run 的后处理：它们可以读取或更新派生的 `analysis.digest.json`，但不得改变核心 `config.json`、策略代码、`run_card.json`、`metrics.csv`、`trades.csv`、`positions.csv`、`equity.csv`。

MCP schema 摘要：`{schema['properties']['action']['enum']}`；缓存默认 `{schema['properties']['use_cache']['default']}`。
""".rstrip()


BRIDGE_WORKFLOW_RULES: tuple[str, ...] = (
    "Vibe-Trading 的目录结构：策略 run 应有 config.json、code/signal_engine.py，以及由系统生成的 artifacts/、run_card.json 等结果文件。",
    "config.json 的基本格式：字段、类型、默认值和使用关系以 MCP 暴露的 BacktestConfigSchema 为准；其中 start_date/end_date 用于行情加载和指标预热，backtest_start/backtest_end 用于实际交易与收益、回撤、metrics 统计（例如 MA300 要提前准备至少 300 根有效 K 线），同一真实标的若拆成多个执行 code，必须在 config.json.logical_groups 中归入同一 group，WebUI 才会按一个标的显示；配置前核对配置 schema，不要把这些字段当成 MCP 顶层参数。",
    "signal_engine.py 的接口要求：只实现 SignalEngine 及其 generate(data_map) 策略逻辑，遵守现有信号、索引和安全约束。",
    "可调用的 MCP 工具：先使用当前 MCP 注册表提供的工具；回测统一使用单一 backtest 入口，调用前核对 MCP tool schema，不自行假定已不存在的工具或参数。",
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
    config_summary = render_backtest_config_summary()
    return f"""Vibe-Trading backtest workflow contract (registry {CAPABILITY_REGISTRY_VERSION}):
- To run or analyze a backtest, call the `backtest` tool. `fast_backtest`, `generate_charts`, and `generate_report` are workflow labels, not separate tools to install or call.
- Default external-Agent route: action=run, speed=fast, use_cache=false. This runs loader, SignalEngine, and the built-in engine, but skips PNG, the report LLM, and implicit loader-cache enablement. Set use_cache=true only when the user explicitly asks to reuse cached market data.
- charts and report are post-processing actions for an already completed run. They must not start a loader, SignalEngine, or backtest engine. Derived analysis.digest.json may be refreshed; core run artifacts must remain unchanged.
- report calls one report LLM. It is not strategy generation and must not start an optimization loop.
- full is an explicit run -> charts -> report workflow.
- Strategy generation and backtesting are separate phases. Require human confirmation before the first backtest. Do not rewrite backtest engines or loaders.
- Use execution fields entry_mode, exit_mode, and stop_loss_mode only through the registered schema. Legacy exit_mode=stop must surface a migration error.
- Configure `run_dir/config.json` from the engine-owned `BacktestConfigSchema` summary below. These are file fields, not top-level `backtest` arguments; the strategy must keep data loading/warm-up and execution/statistics windows separate, and must group execution codes for one real instrument in `logical_groups`.
{config_summary}
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
