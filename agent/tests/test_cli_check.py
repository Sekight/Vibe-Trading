"""Tests for the run-health check command (analysis.md + analysis_charts)."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from cli import _legacy

EXPECTED_CHARTS = [
    "equity_return.png",
    "drawdown.png",
    "pnl_scatter.png",
    "monthly_heatmap.png",
    "pnl_vs_holding.png",
    "mae_mfe.png",
    "holding_buckets.png",
]


def _make_run(
    runs_dir: Path,
    name: str = "run1",
    *,
    charts: list[str] | None = None,
    analysis: bool = False,
) -> Path:
    run_dir = runs_dir / name
    for relative in (
        "req.json",
        "config.json",
        "code/signal_engine.py",
        "run_card.json",
        "artifacts/metrics.csv",
        "artifacts/trades.csv",
        "logs/runner_stdout.txt",
    ):
        path = run_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    if analysis:
        (run_dir / "analysis.md").write_text("analysis", encoding="utf-8")
    if charts:
        charts_dir = run_dir / "analysis_charts"
        charts_dir.mkdir(exist_ok=True)
        for chart in charts:
            (charts_dir / chart).write_bytes(b"\x89PNG\r\n\x1a\n")
    return run_dir


def _run_check(
    monkeypatch, tmp_path: Path, name: str = "run1", **kwargs
) -> tuple[int, str]:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(exist_ok=True)
    _make_run(runs_dir, name, **kwargs)
    console = Console(record=True, force_terminal=False, color_system=None, width=140)
    monkeypatch.setattr(_legacy, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(_legacy, "console", console)
    exit_code = _legacy.cmd_check(name)
    return exit_code, console.export_text()


def test_check_reports_analysis_md_and_all_charts(monkeypatch, tmp_path) -> None:
    exit_code, out = _run_check(
        monkeypatch, tmp_path, charts=EXPECTED_CHARTS, analysis=True
    )

    assert exit_code == _legacy.EXIT_SUCCESS
    assert "analysis.md" in out
    assert "OK" in out
    assert "analysis_charts/*.png" in out
    assert "OK (7)" in out
    assert "REPORT OK" in out


def test_check_warns_on_missing_charts_but_keeps_report_ok(
    monkeypatch, tmp_path
) -> None:
    exit_code, out = _run_check(monkeypatch, tmp_path, charts=EXPECTED_CHARTS[:3])

    assert exit_code == _legacy.EXIT_SUCCESS
    assert "analysis_charts/*.png" in out
    assert "warning (3/7)" in out
    assert "n/a (optional)" in out
    assert "REPORT OK" in out


def test_check_warns_when_no_charts_exist(monkeypatch, tmp_path) -> None:
    exit_code, out = _run_check(monkeypatch, tmp_path, charts=[])

    assert exit_code == _legacy.EXIT_SUCCESS
    assert "warning (0/7)" in out
    assert "REPORT OK" in out


def test_check_still_fails_when_core_report_is_missing(
    monkeypatch, tmp_path
) -> None:
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "run1"
    run_dir.mkdir(parents=True)
    (run_dir / "req.json").write_text("{}", encoding="utf-8")
    console = Console(record=True, force_terminal=False, color_system=None, width=140)
    monkeypatch.setattr(_legacy, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(_legacy, "console", console)

    exit_code = _legacy.cmd_check("run1")
    out = console.export_text()

    assert exit_code == _legacy.EXIT_RUN_FAILED
    assert "NO REPORT" in out
