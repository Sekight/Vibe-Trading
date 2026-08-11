"""Tests for deterministic analysis chart payloads and PNG generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from backtest.analysis.charts import (
    CHART_SPECS,
    CHART_KEYS,
    compute_chart_payload,
    generate_chart_artifacts,
    generate_pngs,
    list_pngs,
)
from backtest.analysis.digest import build_digest

from tests._analysis_fixtures import write_run_dir


def test_compute_chart_payload_contains_all_chart_keys(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path)
    digest = build_digest(run_dir)
    payload = compute_chart_payload(digest)

    assert set(payload.keys()) == set(CHART_KEYS)
    assert len(payload["equity_return"]) == 3
    assert len(payload["pnl_scatter"]) == 2
    assert len(payload["monthly_heatmap"]) == 2
    assert len(payload["mae_mfe"]) == 2
    assert len(payload["holding_buckets"]) == 6
    assert payload["pnl_scatter"][0]["win"] is True
    assert payload["pnl_scatter"][1]["win"] is False


def test_generate_pngs_writes_analysis_charts_dir(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260808_222222_00_png")
    digest = build_digest(run_dir)
    payload = compute_chart_payload(digest)

    saved = generate_pngs(run_dir, payload)

    assert len(saved) == len(CHART_KEYS)
    charts_dir = run_dir / "analysis_charts"
    for spec in saved:
        assert (charts_dir / spec["filename"]).stat().st_size > 0
    assert len(list_pngs(run_dir)) == len(CHART_KEYS)


def test_generate_chart_artifacts_returns_payload_and_pngs(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260808_333333_00_all")
    result = generate_chart_artifacts(run_dir)

    assert result["generated"] is True
    assert result["pngs"]
    assert "equity_return" in result["charts"]


def test_compute_chart_payload_includes_benchmark_series(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260811_333333_00_chartbench")
    (run_dir / "artifacts" / "equity.csv").write_text(
        "timestamp,equity,drawdown,benchmark_equity\n"
        "2024-01-05,1000000,0,1000000\n"
        "2024-01-20,1010000,-0.01,1010000\n"
        "2024-02-15,1050000,0,990000\n",
        encoding="utf-8",
    )
    digest = build_digest(run_dir)
    payload = compute_chart_payload(digest)

    assert payload["equity_return"][0]["benchmark"] == 0.0
    assert payload["equity_return"][2]["benchmark"] == -1.0
    assert payload["drawdown"][2]["benchmark"] == pytest.approx(-1.9802, abs=1e-4)
    assert "benchmark" in payload["drawdown"][0]


def test_chart_spec_titles_clarify_units() -> None:
    titles = {spec["key"]: spec["title"] for spec in CHART_SPECS}
    assert "自然日" in titles["pnl_vs_holding"]
    assert "自然日" in titles["holding_buckets"]
    assert "策略净值" in titles["drawdown"]
