"""Tests for BaseEngine entry_mode / exit_mode execution semantics.

Covers the default next_open behavior, same-bar close fills, stop-price
exits (min(open, stop) on a gap day), and invalid mode combinations.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd
import pytest

from backtest.engines.china_a import ChinaAEngine


def _bar(open_px: float = 10.0, high: float = 11.0,
         low: float = 9.5, close: float = 10.5) -> pd.Series:
    return pd.Series({
        "open": open_px,
        "high": high,
        "low": low,
        "close": close,
    })


class TestExecutionModeFills:
    def test_default_modes_fill_at_next_open(self) -> None:
        engine = ChinaAEngine({"initial_cash": 1_000_000})
        assert engine._same_bar is False
        bar = _bar()
        assert engine._open_fill_price(bar) == 10.0
        assert engine._close_fill_price(bar, pd.Timestamp("2026-01-02"), "X") == 10.0

    def test_close_close_fills_at_decision_bar_close(self) -> None:
        engine = ChinaAEngine({
            "initial_cash": 1_000_000,
            "entry_mode": "close",
            "exit_mode": "close",
        })
        assert engine._same_bar is True
        bar = _bar()
        assert engine._open_fill_price(bar) == 10.5
        assert engine._close_fill_price(bar, pd.Timestamp("2026-01-02"), "X") == 10.5

    def test_close_stop_fills_at_min_open_stop_when_stop_touched(self) -> None:
        engine = ChinaAEngine({
            "initial_cash": 1_000_000,
            "entry_mode": "close",
            "exit_mode": "stop",
        })
        engine._bar_idx = 0
        engine._code_to_col = {"X": 0}
        engine._stop_arr = np.array([[10.0]])
        bar = _bar(open_px=10.0, low=9.8, close=9.9)
        assert engine._close_fill_price(bar, pd.Timestamp("2026-01-02"), "X") == 10.0

    def test_close_stop_uses_close_when_stop_not_touched(self) -> None:
        engine = ChinaAEngine({
            "initial_cash": 1_000_000,
            "entry_mode": "close",
            "exit_mode": "stop",
        })
        engine._bar_idx = 0
        engine._code_to_col = {"X": 0}
        engine._stop_arr = np.array([[9.5]])
        bar = _bar(open_px=10.0, low=9.8, close=10.2)
        assert engine._close_fill_price(bar, pd.Timestamp("2026-01-02"), "X") == 10.2

    def test_stop_fill_caps_at_open_when_gap_below_stop(self) -> None:
        engine = ChinaAEngine({
            "initial_cash": 1_000_000,
            "entry_mode": "close",
            "exit_mode": "stop",
        })
        engine._bar_idx = 0
        engine._code_to_col = {"X": 0}
        engine._stop_arr = np.array([[10.0]])
        bar = _bar(open_px=9.0, low=8.8, close=9.1)
        assert engine._close_fill_price(bar, pd.Timestamp("2026-01-02"), "X") == 9.0

    @pytest.mark.parametrize(
        "entry_mode,exit_mode",
        [
            ("next_open", "close"),
            ("next_open", "stop"),
            ("close", "next_open"),
        ],
    )
    def test_unsupported_mode_combinations_raise(
        self, entry_mode: str, exit_mode: str,
    ) -> None:
        with pytest.raises(ValueError):
            ChinaAEngine({
                "initial_cash": 1_000_000,
                "entry_mode": entry_mode,
                "exit_mode": exit_mode,
            })


class _FlatLoader:
    name = "flat"

    def __init__(self, frame: pd.DataFrame) -> None:
        self._frame = frame

    def fetch(self, codes, start_date, end_date, **kwargs) -> Dict[str, pd.DataFrame]:
        return {codes[0]: self._frame}


class _SignalEngine:
    def __init__(self) -> None:
        self.stop_prices: Dict[str, pd.Series] = {}

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        code = next(iter(data_map))
        idx = data_map[code].index
        weights = pd.Series(0.0, index=idx, dtype=float)
        weights.iloc[0] = 1.0
        stops = pd.Series(np.nan, index=idx, dtype=float)
        stops.iloc[1] = 9.5
        self.stop_prices[code] = stops
        return {code: weights}


class TestCloseStopEndToEnd:
    def test_entry_at_close_and_stop_exit_min_open_stop(self, tmp_path) -> None:
        dates = pd.DatetimeIndex([
            pd.Timestamp("2026-01-05"),
            pd.Timestamp("2026-01-06"),
            pd.Timestamp("2026-01-07"),
        ])
        frame = pd.DataFrame({
            "open": [10.0, 9.8, 9.8],
            "high": [10.2, 9.9, 10.0],
            "low": [9.9, 9.4, 9.7],
            "close": [10.0, 9.7, 9.9],
            "volume": [1000.0, 1000.0, 1000.0],
        }, index=dates)
        config = {
            "codes": ["X"],
            "start_date": "2026-01-05",
            "end_date": "2026-01-07",
            "initial_cash": 1_000_000,
            "entry_mode": "close",
            "exit_mode": "stop",
            "slippage": 0.0,
            "commission_rate": 0.0,
            "commission_min": 0.0,
            "stamp_tax": 0.0,
            "transfer_fee": 0.0,
        }
        engine = ChinaAEngine(config)
        signal = _SignalEngine()
        engine.run_backtest(config, _FlatLoader(frame), signal, tmp_path)

        assert len(engine.trades) == 1
        trade = engine.trades[0]
        assert trade.entry_time == dates[0]
        assert trade.entry_price == pytest.approx(10.0)
        assert trade.exit_time == dates[1]
        assert trade.exit_price == pytest.approx(9.5)
