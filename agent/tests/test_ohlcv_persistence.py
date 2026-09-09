"""Regression tests for OHLCV persistence and per-symbol price loading.

Covers P-20260909-ohlcv_no_persist_and_chart_lazy:
- ``load_price_series`` / ``_load_ohlcv_artifacts`` filter by requested symbols
  (the fix for whole-market runs OOMing on page open).
- ``_write_artifacts`` honors ``config["save_ohlcv"]`` (default True keeps the
  old always-persist behavior; ``--no-ohlcv`` sets it False).
- ``build_run_analysis`` returns chart symbols without a full OHLCV load and
  only loads price rows for the requested symbols.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from backtest.engines.china_a import ChinaAEngine
from src.ui_services import (
    _load_ohlcv_artifacts,
    build_run_analysis,
    load_price_series,
)

from tests._analysis_fixtures import write_run_dir


def _make_ohlcv_run(root: Path, run_id: str = "ohlcv_filter_test") -> Path:
    """A minimal run whose artifacts carry two OHLCV symbols."""
    run_dir = write_run_dir(root, run_id=run_id)
    artifacts = run_dir / "artifacts"

    # Second symbol with its own distinct close values.
    rows = [
        {"trade_date": "2024-01-02", "open": 20, "high": 21, "low": 19, "close": 20.5, "volume": 100},
        {"trade_date": "2024-01-03", "open": 20.5, "high": 22, "low": 20, "close": 21, "volume": 120},
    ]
    pd.DataFrame(rows).to_csv(artifacts / "ohlcv_000001.SZ.csv", index=False, encoding="utf-8")

    config_path = run_dir / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["codes"] = ["600097.SH", "000001.SZ"]
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return run_dir


def test_load_price_series_filters_to_requested_symbols(tmp_path: Path) -> None:
    """Requesting one symbol must only read that symbol's OHLCV file."""
    run_dir = _make_ohlcv_run(tmp_path)
    rows = load_price_series(run_dir, symbols=["000001.SZ"])
    codes = {str(row.get("code")) for row in rows}
    assert codes == {"000001.SZ"}
    assert len(rows) == 2


def test_load_price_series_without_symbols_returns_all(tmp_path: Path) -> None:
    """Default (no symbols) keeps the old full-scan behavior."""
    run_dir = _make_ohlcv_run(tmp_path)
    rows = load_price_series(run_dir)
    codes = {str(row.get("code")) for row in rows}
    assert codes == {"600097.SH", "000001.SZ"}


def test_load_ohlcv_artifacts_filters(tmp_path: Path) -> None:
    """Direct artifact loader honours the symbols filter."""
    run_dir = _make_ohlcv_run(tmp_path)
    rows = _load_ohlcv_artifacts(run_dir, symbols=["600097.SH"])
    codes = {str(row.get("code")) for row in rows}
    assert codes == {"600097.SH"}
    assert len(rows) > 0


def test_build_run_analysis_chart_symbols_and_filtered_prices(tmp_path: Path) -> None:
    """Chart symbols come from the artifact listing and price rows are filtered."""
    run_dir = _make_ohlcv_run(tmp_path)
    analysis = build_run_analysis(run_dir, symbols=["000001.SZ"])
    assert "000001.SZ" in (analysis.get("chart_symbols") or [])
    price_codes = set()
    for group in (analysis.get("price_series") or {}).values():
        for bar in group:
            price_codes.add(str(bar.get("code")))
    assert price_codes <= {"000001.SZ"}


def _engine_and_inputs(config: dict):
    """Build a ChinaAEngine plus minimal _write_artifacts inputs."""
    engine = ChinaAEngine(config)
    data_map = {
        "000001.SZ": pd.DataFrame(
            {"trade_date": ["2024-01-02"], "open": [10], "high": [11], "low": [9], "close": [10.5], "volume": [100]}
        ),
    }
    dates = pd.DatetimeIndex(["2024-01-02"])
    equity_series = pd.Series([1_000_000.0], index=dates)
    bench_equity = pd.Series([1_000_000.0], index=dates)
    bench_ret = pd.Series([0.0], index=dates)
    target_pos = pd.DataFrame({"000001.SZ": [0.0]}, index=dates)
    return engine, data_map, dates, equity_series, bench_equity, bench_ret, target_pos


def test_write_artifacts_persists_ohlcv_by_default(tmp_path: Path) -> None:
    """Without save_ohlcv in config, OHLCV is still written (backward compat)."""
    engine, *inputs = _engine_and_inputs({"interval": "1D"})
    out = tmp_path / "run"
    engine._write_artifacts(out, *inputs, metrics={"total_return": 0.01}, codes=["000001.SZ"])
    assert (out / "artifacts" / "ohlcv_000001.SZ.csv").is_file()
    assert (out / "artifacts" / "equity.csv").is_file()
    assert (out / "artifacts" / "trades.csv").is_file()


def test_write_artifacts_skips_ohlcv_when_disabled(tmp_path: Path) -> None:
    """save_ohlcv=False (--no-ohlcv) skips OHLCV but keeps the rest."""
    engine, *inputs = _engine_and_inputs({"interval": "1D", "save_ohlcv": False})
    out = tmp_path / "run"
    engine._write_artifacts(out, *inputs, metrics={"total_return": 0.01}, codes=["000001.SZ"])
    assert not (out / "artifacts" / "ohlcv_000001.SZ.csv").exists()
    assert (out / "artifacts" / "equity.csv").is_file()
    assert (out / "artifacts" / "trades.csv").is_file()
    assert (out / "artifacts" / "metrics.csv").is_file()


def test_build_run_analysis_without_symbols_does_not_load_ohlcv(tmp_path: Path) -> None:
    """A parameterless full request (no chart_symbol) must not load any OHLCV.

    Callers such as the Compare page only read metrics/equity_curve, so a
    whole-market run must never have its thousands of OHLCV files loaded into
    memory just to answer such a request.
    """
    run_dir = _make_ohlcv_run(tmp_path)
    analysis = build_run_analysis(run_dir, symbols=None)
    # No K-line data loaded when no symbol is requested.
    assert analysis.get("price_series") == {}
    assert analysis.get("indicator_series") == {}
    # Chart symbols are still available (from the artifact listing) so the
    # front-end symbol picker stays populated.
    assert set(analysis.get("chart_symbols") or []) >= {"600097.SH", "000001.SZ"}

