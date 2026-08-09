"""Tests for the runner's data-coverage warning guard."""

from __future__ import annotations

import pandas as pd

from backtest.runner import _data_coverage_warnings


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
