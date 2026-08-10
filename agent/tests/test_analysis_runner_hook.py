"""Runner/tool wiring tests for deterministic charts and the LLM report hook."""

from __future__ import annotations

import json

import backtest.analysis.charts as charts_module
import backtest.analysis.report as report_module
from backtest.runner import _finalize_run_analysis
from src.tools.write_run_analysis_tool import WriteRunAnalysisTool

from tests._analysis_fixtures import write_run_dir


def test_finalize_generates_charts_without_llm_by_default(tmp_path, monkeypatch) -> None:
    run_dir = write_run_dir(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(
        charts_module,
        "generate_chart_artifacts",
        lambda _run_dir: calls.append("charts") or {"generated": True, "pngs": []},
    )
    monkeypatch.setattr(
        report_module,
        "generate_analysis_report",
        lambda *args, **kwargs: calls.append("report"),
    )

    _finalize_run_analysis(run_dir, with_analysis=False)

    assert calls == ["charts"]


def test_finalize_with_analysis_calls_report_after_charts(tmp_path, monkeypatch) -> None:
    run_dir = write_run_dir(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(
        charts_module,
        "generate_chart_artifacts",
        lambda _run_dir: calls.append("charts") or {"generated": True, "pngs": []},
    )
    monkeypatch.setattr(
        report_module,
        "generate_analysis_report",
        lambda *args, **kwargs: calls.append("report"),
    )

    _finalize_run_analysis(run_dir, with_analysis=True)

    assert calls == ["charts", "report"]


def test_write_run_analysis_tool_uses_agent_writer(tmp_path, monkeypatch) -> None:
    run_dir = write_run_dir(tmp_path)
    captured: dict = {}

    def fake_generate(run_dir_arg, **kwargs):
        captured["run_dir"] = str(run_dir_arg)
        captured["generated_by"] = kwargs.get("generated_by")
        return {"status": "ok", "meta": {"status": "ok"}}

    monkeypatch.setattr(report_module, "generate_analysis_report", fake_generate)
    monkeypatch.setenv("VIBE_TRADING_ALLOWED_RUN_ROOTS", str(tmp_path))

    result = WriteRunAnalysisTool().execute(run_dir=str(run_dir))

    assert captured["generated_by"] == "agent"
    payload = json.loads(result)
    assert payload["status"] == "ok"
