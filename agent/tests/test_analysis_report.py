"""Tests for LLM analysis report generation (analysis.md + status)."""

from __future__ import annotations

from pathlib import Path

from backtest.analysis.report import generate_analysis_report

from tests._analysis_fixtures import write_run_dir


def test_ok_report_persists_markdown_and_usage(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path)
    calls: list[str] = []

    def fake_llm(prompt: str):
        calls.append(prompt)
        return "# 分析\n\n结论：策略有效。", {"input_tokens": 11, "output_tokens": 22, "total_tokens": 33}

    result = generate_analysis_report(run_dir, generated_by="runner", llm_call=fake_llm)

    assert result["status"] == "ok"
    assert len(calls) == 1
    assert "核心指标" in calls[0]
    markdown = (run_dir / "analysis.md").read_text(encoding="utf-8")
    assert "> generated_by: runner" in markdown
    assert "策略有效" in markdown
    status = (run_dir / "analysis.status.json").read_text(encoding="utf-8")
    assert '"status": "ok"' in status
    assert '"total_tokens": 33' in status
    assert '"config_hash": "cfg-abc"' in status


def test_ok_report_accepts_plain_string_llm_call(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260808_444444_00_plain")

    result = generate_analysis_report(
        run_dir,
        generated_by="agent",
        llm_call=lambda prompt: "## 一句话结论\n可执行。",
    )

    assert result["status"] == "ok"
    status = (run_dir / "analysis.status.json").read_text(encoding="utf-8")
    assert '"generated_by": "agent"' in status
    assert "llm_usage" not in status


def test_failed_report_never_raises(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260808_555555_00_fail")

    def broken_llm(_prompt: str):
        raise RuntimeError("provider down")

    result = generate_analysis_report(run_dir, generated_by="runner", llm_call=broken_llm)

    assert result["status"] == "failed"
    assert "provider down" in result["error"]
    assert not (run_dir / "analysis.md").exists()
    status = (run_dir / "analysis.status.json").read_text(encoding="utf-8")
    assert '"status": "failed"' in status
    assert "provider down" in status


def test_missing_run_card_is_skipped(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260808_666666_00_skip")
    (run_dir / "run_card.json").unlink()

    result = generate_analysis_report(run_dir, generated_by="runner")

    assert result["status"] == "skipped"
    status = (run_dir / "analysis.status.json").read_text(encoding="utf-8")
    assert '"status": "skipped"' in status
    assert "missing" in status


def test_agent_and_runner_generated_by_are_distinct(tmp_path: Path) -> None:
    agent_dir = write_run_dir(tmp_path, "20260808_777777_00_agent")
    runner_dir = write_run_dir(tmp_path, "20260808_888888_00_runner")
    generate_analysis_report(agent_dir, generated_by="agent", llm_call=lambda p: "agent body")
    generate_analysis_report(runner_dir, generated_by="runner", llm_call=lambda p: "runner body")

    assert "generated_by: agent" in (agent_dir / "analysis.md").read_text(encoding="utf-8")
    assert "generated_by: runner" in (runner_dir / "analysis.md").read_text(encoding="utf-8")
