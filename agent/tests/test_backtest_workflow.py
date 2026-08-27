"""Tests for the single-entry MCP backtest workflow contract."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src import backtest_capabilities as capabilities
from src.tools import backtest_tool
from tests._analysis_fixtures import write_run_dir


class _FakeRunner:
    calls: list[dict] = []

    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    def execute(self, entry_script, run_dir, *, cwd=None, cli_args=None, env_overrides=None):
        self.calls.append(
            {
                "entry_script": entry_script,
                "run_dir": run_dir,
                "cwd": cwd,
                "cli_args": list(cli_args or []),
                "env_overrides": dict(env_overrides or {}),
            }
        )
        return SimpleNamespace(
            success=True,
            exit_code=0,
            stdout="runner-ok",
            stderr="",
            artifacts={},
        )


def _make_strategy_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    (run_dir / "code").mkdir(parents=True)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "source": "local",
                "codes": ["local:AAPL.US"],
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "interval": "1D",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "code" / "signal_engine.py").write_text(
        "class SignalEngine:\n"
        "    def generate(self, data_map):\n"
        "        return {}\n",
        encoding="utf-8",
    )
    return run_dir


def _call(run_dir: Path, monkeypatch: pytest.MonkeyPatch, **kwargs) -> dict:
    monkeypatch.setenv("VIBE_TRADING_ALLOWED_RUN_ROOTS", str(run_dir.parent))
    return json.loads(backtest_tool.run_backtest(str(run_dir), **kwargs))


def test_registry_contract_has_one_public_tool_and_four_execution_presets() -> None:
    schema = capabilities.backtest_tool_schema()
    instructions = capabilities.render_mcp_instructions()
    capability_markdown = capabilities.render_capability_markdown()

    assert capabilities.BACKTEST_ACTIONS == ("run", "charts", "report", "full")
    assert "use_cache=false" in instructions
    assert "start_date" in instructions and "backtest_start" in instructions
    assert "logical_groups" in instructions
    assert "indicator warm-up" in schema["properties"]["run_dir"]["description"]
    assert "execution/statistics" in schema["properties"]["run_dir"]["description"]
    assert "logical_groups" in schema["properties"]["run_dir"]["description"]
    assert "start_date" in capability_markdown and "backtest_start" in capability_markdown
    assert "logical_groups" in capability_markdown
    assert schema["properties"]["action"]["enum"] == list(capabilities.BACKTEST_ACTIONS)
    assert schema["properties"]["speed"]["default"] == "fast"
    assert schema["properties"]["use_cache"]["default"] is False
    assert set(schema["properties"]["execution"]["properties"]) == {
        "entry_mode",
        "exit_mode",
        "stop_loss_mode",
    }
    assert len(capabilities.execution_presets()) == 4
    assert capabilities.validate_execution_request(
        {"entry_mode": "close", "exit_mode": "close", "stop_loss_mode": "hard"}
    ) == {"entry_mode": "close", "exit_mode": "close", "stop_loss_mode": "hard"}


def test_bridge_skill_is_the_ten_rule_boundary_only() -> None:
    from src.agent.skills import SkillsLoader

    loader = SkillsLoader(user_skills_dir=Path("__no_user_skills__"))
    content = loader.get_content("vibe-trading-bridge")
    numbered = [
        line for line in content.splitlines()
        if line.split(".", 1)[0].isdigit() and ". " in line
    ]

    assert len(numbered) == 10
    assert "action=\"charts\"" not in content
    assert "stop_loss_mode=\"hard\"" not in content
    assert "start_date/end_date" in content
    assert "backtest_start/backtest_end" in content
    assert "MA300" in content
    assert "logical_groups" in content


def test_default_run_forwards_fastrun_without_implicit_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_dir = _make_strategy_run(tmp_path)
    _FakeRunner.calls = []
    monkeypatch.setattr(backtest_tool, "Runner", _FakeRunner)

    body = _call(run_dir, monkeypatch)

    assert body["status"] == "ok"
    assert body["action"] == "run"
    assert body["speed"] == "fast"
    assert body["cache_enabled"] is False
    assert body["backtest_reran"] is True
    assert "--fastrun" in _FakeRunner.calls[0]["cli_args"]
    assert _FakeRunner.calls[0]["env_overrides"] == {"VIBE_TRADING_DATA_CACHE": "0"}


def test_normal_run_does_not_forward_fastrun(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_dir = _make_strategy_run(tmp_path)
    _FakeRunner.calls = []
    monkeypatch.setattr(backtest_tool, "Runner", _FakeRunner)

    body = _call(run_dir, monkeypatch, speed="normal")

    assert body["status"] == "ok"
    assert body["speed"] == "normal"
    assert "--fastrun" not in _FakeRunner.calls[0]["cli_args"]


def test_full_workflow_runs_normal_then_charts_then_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = _make_strategy_run(tmp_path)
    _FakeRunner.calls = []
    monkeypatch.setattr(backtest_tool, "Runner", _FakeRunner)
    stages: list[str] = []

    def _fake_postprocess(path: Path, *, action: str, execution: dict[str, str]):
        assert path == run_dir
        assert execution == {
            "entry_mode": "next_open",
            "exit_mode": "next_open",
            "stop_loss_mode": "none",
        }
        stages.append(action)
        if action == "charts":
            return True, {"charts_generated": True, "pngs": []}
        return True, {
            "report_generated": True,
            "report": {"status": "ok"},
        }

    monkeypatch.setattr(backtest_tool, "_postprocess", _fake_postprocess)
    body = _call(run_dir, monkeypatch, action="full")

    assert body["status"] == "ok"
    assert body["speed"] == "normal"
    assert body["backtest_reran"] is True
    assert body["charts_generated"] is True
    assert body["report_generated"] is True
    assert stages == ["charts", "report"]
    assert "--fastrun" not in _FakeRunner.calls[0]["cli_args"]


def test_execution_override_is_in_memory_and_not_written_to_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = _make_strategy_run(tmp_path)
    original = (run_dir / "config.json").read_bytes()
    _FakeRunner.calls = []
    monkeypatch.setattr(backtest_tool, "Runner", _FakeRunner)

    body = _call(
        run_dir,
        monkeypatch,
        execution={
            "entry_mode": "close",
            "exit_mode": "close",
            "stop_loss_mode": "hard",
        },
        use_cache=False,
    )

    assert body["status"] == "ok"
    assert body["execution"] == {
        "entry_mode": "close",
        "exit_mode": "close",
        "stop_loss_mode": "hard",
    }
    assert (run_dir / "config.json").read_bytes() == original
    args = _FakeRunner.calls[0]["cli_args"]
    assert "--execution-json" in args
    assert json.loads(args[args.index("--execution-json") + 1]) == {
        "entry_mode": "close",
        "exit_mode": "close",
        "stop_loss_mode": "hard",
    }
    assert _FakeRunner.calls[0]["env_overrides"] == {"VIBE_TRADING_DATA_CACHE": "0"}


def test_legacy_exit_mode_fails_before_runner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_dir = _make_strategy_run(tmp_path)
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    config["exit_mode"] = "stop"
    (run_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

    class _MustNotRun:
        def __init__(self, *args, **kwargs):
            raise AssertionError("runner must not start for legacy execution mode")

    monkeypatch.setattr(backtest_tool, "Runner", _MustNotRun)
    body = _call(run_dir, monkeypatch)

    assert body["status"] == "error"
    assert body["error_type"] == "validation"
    assert "legacy exit_mode='stop'" in body["error"]


def test_charts_postprocess_does_not_start_runner_and_preserves_core_hashes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = write_run_dir(tmp_path, "charts_only")

    class _MustNotRun:
        def __init__(self, *args, **kwargs):
            raise AssertionError("runner must not start for charts action")

    monkeypatch.setattr(backtest_tool, "Runner", _MustNotRun)
    before = backtest_tool._core_artifact_hashes(run_dir)
    body = _call(run_dir, monkeypatch, action="charts")
    after = backtest_tool._core_artifact_hashes(run_dir)

    assert body["status"] == "ok"
    assert body["backtest_reran"] is False
    assert body["charts_generated"] is True
    assert before == after
    assert body["cache_enabled"] is None
    assert list((run_dir / "analysis_charts").glob("*.png"))


def test_report_postprocess_does_not_start_runner_and_preserves_core_hashes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = write_run_dir(tmp_path, "report_only")

    class _MustNotRun:
        def __init__(self, *args, **kwargs):
            raise AssertionError("runner must not start for report action")

    def _fake_report(path: Path, *, generated_by: str):
        assert path == run_dir
        assert generated_by == "mcp"
        (path / "analysis.prompt.md").write_text("prompt", encoding="utf-8")
        (path / "analysis.md").write_text("# report", encoding="utf-8")
        (path / "analysis.status.json").write_text('{"status":"ok"}', encoding="utf-8")
        return {"status": "ok", "meta": {"generated_by": generated_by}}

    monkeypatch.setattr(backtest_tool, "Runner", _MustNotRun)
    import backtest.analysis.report as report_module

    monkeypatch.setattr(report_module, "generate_analysis_report", _fake_report)
    before = backtest_tool._core_artifact_hashes(run_dir)
    body = _call(run_dir, monkeypatch, action="report")
    after = backtest_tool._core_artifact_hashes(run_dir)

    assert body["status"] == "ok"
    assert body["backtest_reran"] is False
    assert body["report_generated"] is True
    assert before == after
    assert not (run_dir / "analysis_charts").exists()


def test_postprocess_requires_completed_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_dir = _make_strategy_run(tmp_path)

    class _MustNotRun:
        def __init__(self, *args, **kwargs):
            raise AssertionError("runner must not start for missing-artifact postprocess")

    monkeypatch.setattr(backtest_tool, "Runner", _MustNotRun)
    body = _call(run_dir, monkeypatch, action="charts")

    assert body["status"] == "error"
    assert body["error_type"] == "postprocess"
    assert "completed run" in body["error"]


def test_mcp_backtest_schema_is_registry_schema() -> None:
    import mcp_server

    tools = asyncio.run(mcp_server.mcp.list_tools())
    tool = next(item for item in tools if item.name == "backtest")
    assert tool.parameters == capabilities.backtest_tool_schema()
    assert "generate_charts" not in {item.name for item in tools}
    assert "generate_report" not in {item.name for item in tools}


def test_mcp_call_forwards_single_entry_action_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    import mcp_server

    captured: dict = {}

    def _fake_run_backtest(run_dir: str, **kwargs) -> str:
        captured["run_dir"] = run_dir
        captured.update(kwargs)
        return '{"status":"ok"}'

    monkeypatch.setattr("src.tools.backtest_tool.run_backtest", _fake_run_backtest)
    asyncio.run(
        mcp_server.mcp.call_tool(
            "backtest",
            {
                "run_dir": "C:/runs/example",
                "action": "charts",
                "speed": "fast",
                "use_cache": True,
            },
        )
    )

    assert captured == {
        "run_dir": "C:/runs/example",
        "action": "charts",
        "speed": "fast",
        "use_cache": True,
        "execution": None,
    }


def test_small_local_runner_fast_normal_artifact_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Run the real engine on a tiny in-memory local snapshot.

    This is the compact end-to-end proof for the plan's fast/normal contract:
    trading artifacts stay equal, fast only drops expensive digest sections,
    and neither route creates PNG/report files implicitly.
    """
    import backtest.runner as runner_module

    def _new_run(name: str) -> Path:
        run_dir = tmp_path / name
        (run_dir / "code").mkdir(parents=True)
        config = {
            "source": "local",
            "codes": ["AAPL.US"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-10",
            "interval": "1D",
            "initial_cash": 100_000,
            "commission": 0.0003,
            "entry_mode": "next_open",
            "exit_mode": "next_open",
            "stop_loss_mode": "none",
        }
        (run_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
        (run_dir / "code" / "signal_engine.py").write_text(
            "import pandas as pd\n"
            "\n"
            "class SignalEngine:\n"
            "    def generate(self, data_map):\n"
            "        code, frame = next(iter(data_map.items()))\n"
            "        signal = pd.Series(0.0, index=frame.index)\n"
            "        signal.iloc[1:4] = 1.0\n"
            "        return {code: signal}\n",
            encoding="utf-8",
        )
        return run_dir

    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    frame = pd.DataFrame(
        {
            "open": [10.0 + i for i in range(10)],
            "high": [10.5 + i for i in range(10)],
            "low": [9.5 + i for i in range(10)],
            "close": [10.2 + i for i in range(10)],
            "volume": [1000.0] * 10,
        },
        index=dates,
    )
    frame.index.name = "timestamp"

    def _fake_fetch(config):
        return runner_module.DataFetchResult(
            data_map={"AAPL.US": frame.copy()},
            codes=["AAPL.US"],
            source="local",
            loader=None,
            effective_sources=["local"],
        )

    monkeypatch.setattr(runner_module, "fetch_data_map", _fake_fetch)
    monkeypatch.setenv("VIBE_TRADING_ALLOWED_RUN_ROOTS", str(tmp_path))
    from src.config.accessor import reset_env_config

    reset_env_config()
    fast_dir = _new_run("fast")
    normal_dir = _new_run("normal")

    runner_module.main(
        fast_dir,
        without_regime=True,
        without_mae_mfe=True,
        execution_overrides={
            "entry_mode": "close",
            "exit_mode": "close",
            "stop_loss_mode": "none",
        },
    )
    runner_module.main(
        normal_dir,
        execution_overrides={
            "entry_mode": "close",
            "exit_mode": "close",
            "stop_loss_mode": "none",
        },
    )

    for run_dir in (fast_dir, normal_dir):
        assert (run_dir / "run_card.json").exists()
        assert (run_dir / "artifacts" / "metrics.csv").exists()
        assert (run_dir / "artifacts" / "trades.csv").exists()
        assert (run_dir / "artifacts" / "positions.csv").exists()
        assert (run_dir / "artifacts" / "equity.csv").exists()
        assert not (run_dir / "analysis_charts").exists()
        assert not (run_dir / "analysis.md").exists()

    for relative in (
        "artifacts/metrics.csv",
        "artifacts/trades.csv",
        "artifacts/positions.csv",
        "artifacts/equity.csv",
    ):
        assert (fast_dir / relative).read_bytes() == (normal_dir / relative).read_bytes()

    fast_digest = json.loads((fast_dir / "analysis.digest.json").read_text(encoding="utf-8"))["digest"]
    normal_digest = json.loads((normal_dir / "analysis.digest.json").read_text(encoding="utf-8"))["digest"]
    assert "regime" not in fast_digest
    assert "mae_mfe_summary" not in fast_digest
    assert "regime" in normal_digest
    assert "mae_mfe_summary" in normal_digest
    # The source config remains untouched even when MCP applies an in-memory
    # execution override to the fast run.
    assert json.loads((fast_dir / "config.json").read_text(encoding="utf-8"))["entry_mode"] == "next_open"
    shutil.rmtree(tmp_path / "fast", ignore_errors=True)
    shutil.rmtree(tmp_path / "normal", ignore_errors=True)
