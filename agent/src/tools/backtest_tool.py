"""Single-entry backtest workflow tool.

The public MCP surface intentionally keeps one ``backtest`` tool. Its action
selects the lifecycle stage so an external Agent does not have to choose among
several similarly named tools.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from backtest.loaders.registry import VALID_SOURCES
from src.agent.progress import emit_progress
from src.agent.tools import BaseTool
from src.backtest_capabilities import (
    BACKTEST_ACTIONS,
    BACKTEST_SPEEDS,
    CORE_ARTIFACT_RELATIVE_PATHS,
    DEFAULT_ACTION,
    DEFAULT_SPEED,
    DEFAULT_USE_CACHE,
    REQUIRED_COMPLETED_RUN_FILES,
    backtest_tool_schema,
    resolve_execution,
)
from src.core.runner import Runner
from src.tools.path_utils import safe_run_dir


def _json_error(error: str, *, error_type: str = "error", **extra: Any) -> str:
    payload: dict[str, Any] = {
        "status": "error",
        "error_type": error_type,
        "error": error,
    }
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def _load_config(run_path: Path) -> dict[str, Any]:
    config_path = run_path / "config.json"
    if not config_path.exists():
        raise ValueError("config.json not found")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"config.json parse error: {exc}") from exc
    if not isinstance(config, dict):
        raise ValueError("config.json must contain a JSON object")
    return config


def _core_artifact_hashes(run_path: Path) -> dict[str, str | None]:
    """Hash immutable inputs/core outputs for post-processing isolation checks."""
    hashes: dict[str, str | None] = {}
    for relative in CORE_ARTIFACT_RELATIVE_PATHS:
        path = run_path / relative
        if not path.is_file():
            hashes[relative] = None
            continue
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _artifact_paths(run_path: Path) -> dict[str, str]:
    """Return stable paths for core and derived artifacts that exist."""
    paths: dict[str, str] = {}
    candidates = [
        *CORE_ARTIFACT_RELATIVE_PATHS,
        "analysis.digest.json",
        "analysis.md",
        "analysis.status.json",
        "analysis.prompt.md",
    ]
    for relative in candidates:
        path = run_path / relative
        if path.exists():
            paths[relative] = str(path)
    charts_dir = run_path / "analysis_charts"
    if charts_dir.is_dir():
        for path in sorted(charts_dir.glob("*.png")):
            paths[str(path.relative_to(run_path))] = str(path)
    return paths


def _completed_run_guard(run_path: Path) -> None:
    missing = [
        relative
        for relative in REQUIRED_COMPLETED_RUN_FILES
        if not (run_path / relative).is_file()
    ]
    if missing:
        raise ValueError(
            "post-processing requires a completed run; missing " + ", ".join(missing)
        )


def _run_engine(
    run_path: Path,
    *,
    speed: str,
    use_cache: bool,
    execution_overrides: Mapping[str, str] | None,
) -> tuple[Any, dict[str, Any]]:
    """Run the existing runner subprocess with workflow-only overrides."""
    agent_root = Path(__file__).resolve().parents[2]
    entry_script = agent_root / "backtest" / "runner.py"
    cli_args = [str(run_path)]
    if speed == "fast":
        cli_args.append("--fastrun")
    if execution_overrides:
        cli_args.extend(
            ["--execution-json", json.dumps(dict(execution_overrides), ensure_ascii=False)]
        )

    emit_progress(
        "simulate",
        message=f"running backtest engine (speed={speed}, cache={use_cache})",
    )
    runner = Runner(timeout=300)
    result = runner.execute(
        entry_script,
        run_path,
        cwd=agent_root,
        cli_args=cli_args,
        env_overrides={"VIBE_TRADING_DATA_CACHE": "1" if use_cache else "0"},
    )
    return result, {
        "exit_code": result.exit_code,
        "stdout": result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
        "stderr": result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr,
        "runner_artifacts": {name: str(path) for name, path in result.artifacts.items()},
    }


def _postprocess(
    run_path: Path,
    *,
    action: str,
    execution: dict[str, str],
) -> tuple[bool, dict[str, Any]]:
    """Run charts/report only and assert core artifacts were not changed."""
    before = _core_artifact_hashes(run_path)
    if action == "charts":
        from backtest.analysis.charts import generate_chart_artifacts

        result = generate_chart_artifacts(run_path)
        details: dict[str, Any] = {
            "charts": result.get("charts", {}),
            "pngs": result.get("pngs", []),
            "charts_generated": bool(result.get("generated")),
        }
    elif action == "report":
        from backtest.analysis.report import generate_analysis_report

        result = generate_analysis_report(run_path, generated_by="mcp")
        report_ok = result.get("status") == "ok"
        details = {
            "report": result,
            "report_generated": report_ok,
        }
    else:  # pragma: no cover - guarded by the public dispatcher
        raise ValueError(f"unsupported post-processing action: {action}")

    after = _core_artifact_hashes(run_path)
    if before != after:
        changed = [key for key in before if before[key] != after[key]]
        return False, {
            "error_type": "core_artifact_mutation",
            "error": "post-processing changed core artifacts: " + ", ".join(changed),
            "core_artifact_hashes_before": before,
            "core_artifact_hashes_after": after,
            **details,
        }
    details["core_artifact_hashes"] = after
    details["execution"] = execution
    if action == "report" and not report_ok:
        details["error"] = result.get("error", "report generation failed")
        return False, details
    return True, details


def _base_response(
    run_path: Path,
    *,
    action: str,
    speed: str | None,
    use_cache: bool | None,
    execution: dict[str, str],
) -> dict[str, Any]:
    return {
        "action": action,
        "speed": speed,
        "cache_enabled": use_cache,
        "backtest_reran": False,
        "charts_generated": False,
        "report_generated": False,
        "execution": execution,
        "run_dir": str(run_path),
        "artifacts": _artifact_paths(run_path),
    }


def run_backtest(
    run_dir: str,
    *,
    action: str = DEFAULT_ACTION,
    speed: str = DEFAULT_SPEED,
    use_cache: bool = DEFAULT_USE_CACHE,
    execution: Mapping[str, Any] | None = None,
) -> str:
    """Execute one action of the single-entry Vibe-Trading backtest workflow."""
    emit_progress("validate", message="validating run_dir and backtest action")
    try:
        run_path = safe_run_dir(run_dir)
        if action not in BACKTEST_ACTIONS:
            raise ValueError(f"action must be one of {BACKTEST_ACTIONS}, got: {action!r}")
        if speed not in BACKTEST_SPEEDS:
            raise ValueError(f"speed must be one of {BACKTEST_SPEEDS}, got: {speed!r}")
        config = _load_config(run_path)
        effective_execution = resolve_execution(config, execution)
    except ValueError as exc:
        return _json_error(str(exc), error_type="validation", action=action)

    effective_speed = "normal" if action == "full" else speed
    effective_cache: bool | None = use_cache if action in {"run", "full"} else None
    response = _base_response(
        run_path,
        action=action,
        speed=effective_speed,
        use_cache=effective_cache,
        execution=effective_execution,
    )

    if action in {"charts", "report"}:
        try:
            _completed_run_guard(run_path)
            ok, details = _postprocess(
                run_path,
                action=action,
                execution=effective_execution,
            )
        except (OSError, ValueError, RuntimeError) as exc:
            return _json_error(str(exc), error_type="postprocess", **response)
        response.update(details)
        response["artifacts"] = _artifact_paths(run_path)
        response["status"] = "ok" if ok else "error"
        if action == "report" and response.get("report", {}).get("status") == "failed":
            response["status"] = "error"
            if response.get("report", {}).get("error"):
                response["error"] = response["report"]["error"]
        return json.dumps(response, ensure_ascii=False)

    # A run/full action is the only path that may invoke Runner/loader/engine.
    try:
        if "source" not in config:
            raise ValueError("config.json missing 'source' field")
        if config["source"] not in VALID_SOURCES:
            raise ValueError(
                f"source must be one of {VALID_SOURCES}, got: {config['source']}"
            )
        signal_path = run_path / "code" / "signal_engine.py"
        if not signal_path.exists():
            raise ValueError("code/signal_engine.py not found")
        result, details = _run_engine(
            run_path,
            speed=effective_speed,
            use_cache=bool(use_cache),
            execution_overrides=execution,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        return _json_error(str(exc), error_type="execution", **response)

    response.update(details)
    response["backtest_reran"] = True
    response["status"] = "ok" if result.success else "error"
    response["artifacts"] = _artifact_paths(run_path)
    if not result.success:
        response["error"] = f"backtest runner exited with code {result.exit_code}"
        return json.dumps(response, ensure_ascii=False)

    if action == "full":
        for post_action in ("charts", "report"):
            try:
                ok, post_details = _postprocess(
                    run_path,
                    action=post_action,
                    execution=effective_execution,
                )
            except (OSError, ValueError, RuntimeError) as exc:
                response["status"] = "error"
                response["error"] = str(exc)
                break
            response.update(post_details)
            if post_action == "charts":
                response["charts_generated"] = bool(post_details.get("charts_generated"))
            else:
                response["report_generated"] = bool(post_details.get("report_generated"))
            if not ok:
                response["status"] = "error"
                response["error"] = post_details.get("error", "post-processing failed")
                break
        response["artifacts"] = _artifact_paths(run_path)
    return json.dumps(response, ensure_ascii=False)


class BacktestTool(BaseTool):
    """Single public backtest workflow tool."""

    name = "backtest"
    description = (
        "Run or post-process a Vibe-Trading run through one entry point. "
        "Defaults to fast backtest, no PNG/report, and loader cache disabled unless requested."
    )
    parameters = backtest_tool_schema()
    repeatable = True
    is_readonly = False

    def execute(self, **kwargs: Any) -> str:
        """Execute the requested workflow action."""
        return run_backtest(
            kwargs["run_dir"],
            action=kwargs.get("action", DEFAULT_ACTION),
            speed=kwargs.get("speed", DEFAULT_SPEED),
            use_cache=kwargs.get("use_cache", DEFAULT_USE_CACHE),
            execution=kwargs.get("execution"),
        )
