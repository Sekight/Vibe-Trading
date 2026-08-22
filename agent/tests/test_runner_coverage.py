"""Tests for the runner's data-coverage warning guard."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from backtest.runner import BacktestConfigSchema, _data_coverage_warnings, main


def _frame(start: str, periods: int = 30) -> pd.DataFrame:
    idx = pd.bdate_range(start=start, periods=periods)
    return pd.DataFrame(
        {"open": [10.0] * periods, "close": [10.0] * periods},
        index=idx,
    )


def test_no_warning_for_short_holiday_boundary() -> None:
    # Requested start is a Sunday (2026-01-04); first bar is Monday 01-05.
    config = {"start_date": "2026-01-04"}
    data = {"X": _frame("2026-01-05")}
    assert _data_coverage_warnings(config, data) == []


def test_warns_when_data_starts_materially_late() -> None:
    config = {"start_date": "2026-01-01"}
    data = {"X": _frame("2026-02-02")}
    warnings = _data_coverage_warnings(config, data)
    assert len(warnings) == 1
    assert "X starts 2026-02-02" in warnings[0]


def test_empty_and_none_frames_are_ignored() -> None:
    config = {"start_date": "2026-01-01"}
    data = {
        "EMPTY": pd.DataFrame(),
        "NONE": None,
        "OK": _frame("2026-01-05"),
    }
    assert _data_coverage_warnings(config, data) == []


def test_invalid_start_date_returns_no_warnings() -> None:
    data = {"X": _frame("2026-01-05")}
    assert _data_coverage_warnings({"start_date": "nonsense"}, data) == []


def test_legacy_exit_mode_stop_is_rejected_for_migration() -> None:
    """The overloaded legacy stop spelling must fail before data loading."""
    with pytest.raises(ValueError, match="legacy exit_mode='stop'"):
        BacktestConfigSchema(
            codes=["X"],
            start_date="2026-01-01",
            end_date="2026-01-31",
            entry_mode="close",
            exit_mode="stop",
        )


def test_next_open_stop_three_field_config_is_accepted() -> None:
    """The P0 hard-stop preset must pass the runner schema contract."""
    config = BacktestConfigSchema(
        codes=["rb2410.SHFE"],
        start_date="2026-01-01",
        end_date="2026-01-31",
        entry_mode="next_open",
        exit_mode="next_open",
        stop_loss_mode="hard",
    )
    assert config.entry_mode == "next_open"
    assert config.exit_mode == "next_open"
    assert config.stop_loss_mode == "hard"


def test_runner_rejects_legacy_exit_mode_stop_before_loading_data(
    tmp_path, monkeypatch, capsys
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "config.json").write_text(
        json.dumps({"exit_mode": "stop"}), encoding="utf-8"
    )
    monkeypatch.setenv("VIBE_TRADING_ALLOWED_RUN_ROOTS", str(tmp_path))

    with pytest.raises(SystemExit):
        main(run_dir)

    output = capsys.readouterr().out
    assert "legacy exit_mode='stop' rejected" in output
    assert "migrate" in output
