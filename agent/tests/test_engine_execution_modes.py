"""Tests for BaseEngine normal execution and independent hard stops.

Covers the default next_open behavior, same-bar close fills, independent
stop-price exits (including gap handling), and invalid mode combinations.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd
import pytest

from backtest.engines.china_a import ChinaAEngine
from backtest.engines.china_futures import ChinaFuturesEngine


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
            "exit_mode": "close",
            "stop_loss_mode": "hard",
        })
        bar = _bar(open_px=10.0, low=9.8, close=9.9)
        assert engine._stop_fill_price(bar, 10.0, 1, "X") == 10.0

    def test_close_stop_uses_close_when_stop_not_touched(self) -> None:
        engine = ChinaAEngine({
            "initial_cash": 1_000_000,
            "entry_mode": "close",
            "exit_mode": "close",
            "stop_loss_mode": "hard",
        })
        bar = _bar(open_px=10.0, low=9.8, close=10.2)
        assert engine._stop_fill_price(bar, 9.5, 1, "X") is None
        assert engine._close_fill_price(bar, pd.Timestamp("2026-01-02"), "X") == 10.2

    def test_stop_fill_caps_at_open_when_gap_below_stop(self) -> None:
        engine = ChinaAEngine({
            "initial_cash": 1_000_000,
            "entry_mode": "close",
            "exit_mode": "close",
            "stop_loss_mode": "hard",
        })
        bar = _bar(open_px=9.0, low=8.8, close=9.1)
        assert engine._stop_fill_price(bar, 10.0, 1, "X") == 9.0

    def test_close_stop_short_fills_at_max_open_stop_when_stop_touched(self) -> None:
        engine = ChinaAEngine({
            "initial_cash": 1_000_000,
            "entry_mode": "close",
            "exit_mode": "close",
            "stop_loss_mode": "hard",
        })
        bar = _bar(open_px=11.0, high=11.2, low=9.8, close=10.5)
        assert engine._stop_fill_price(bar, 10.0, -1, "X") == 11.0

    def test_close_stop_short_uses_close_when_stop_not_touched(self) -> None:
        engine = ChinaAEngine({
            "initial_cash": 1_000_000,
            "entry_mode": "close",
            "exit_mode": "close",
            "stop_loss_mode": "hard",
        })
        bar = _bar(open_px=10.0, high=9.9, low=9.5, close=10.2)
        assert engine._stop_fill_price(bar, 10.5, -1, "X") is None
        assert engine._close_fill_price(bar, pd.Timestamp("2026-01-02"), "X") == 10.2

    def test_normal_close_does_not_use_stop_price(self) -> None:
        engine = ChinaAEngine({
            "initial_cash": 1_000_000,
            "entry_mode": "close",
            "exit_mode": "close",
            "stop_loss_mode": "hard",
        })
        bar = _bar(open_px=10.0, low=9.0, close=9.8)
        assert engine._close_fill_price(
            bar, pd.Timestamp("2026-01-02"), "X"
        ) == 9.8

    def test_china_futures_slippage_points(self) -> None:
        engine = ChinaFuturesEngine({
            "initial_cash": 100_000,
            "slippage_points": 1.0,
        })
        assert engine.apply_slippage(3000.0, 1) == 3001.0
        assert engine.apply_slippage(3000.0, -1) == 2999.0

    @pytest.mark.parametrize(
        "entry_mode,exit_mode,stop_loss_mode",
        [
            ("next_open", "close", "none"),
            ("close", "next_open", "none"),
            ("next_open", "stop", "none"),
        ],
    )
    def test_unsupported_mode_combinations_raise(
        self, entry_mode: str, exit_mode: str, stop_loss_mode: str,
    ) -> None:
        with pytest.raises(ValueError):
            ChinaAEngine({
                "initial_cash": 1_000_000,
                "entry_mode": entry_mode,
                "exit_mode": exit_mode,
                "stop_loss_mode": stop_loss_mode,
            })

    @pytest.mark.parametrize(
        "entry_mode,exit_mode,stop_loss_mode",
        [
            ("next_open", "next_open", "none"),
            ("close", "close", "none"),
            ("close", "close", "hard"),
            ("next_open", "next_open", "hard"),
        ],
    )
    def test_new_execution_presets_are_valid(
        self, entry_mode: str, exit_mode: str, stop_loss_mode: str,
    ) -> None:
        ChinaAEngine({
            "initial_cash": 1_000_000,
            "entry_mode": entry_mode,
            "exit_mode": exit_mode,
            "stop_loss_mode": stop_loss_mode,
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
        stops.iloc[0] = 9.5
        self.stop_prices[code] = stops
        return {code: weights}


class _ScenarioSignalEngine:
    def __init__(self, weights, stops) -> None:
        self._weights = list(weights)
        self._stops = list(stops)
        self.stop_prices: Dict[str, pd.Series] = {}

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        code = next(iter(data_map))
        idx = data_map[code].index
        self.stop_prices[code] = pd.Series(self._stops, index=idx, dtype=float)
        return {
            code: pd.Series(self._weights, index=idx, dtype=float),
        }


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
            "exit_mode": "close",
            "stop_loss_mode": "hard",
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
        rows = pd.read_csv(tmp_path / "artifacts" / "trades.csv")
        assert rows.iloc[-1]["reason"] == "stop"

    def test_strategy_stop_update_can_widen_without_engine_clamp(self, tmp_path) -> None:
        dates = pd.DatetimeIndex([
            pd.Timestamp("2026-01-05"),
            pd.Timestamp("2026-01-06"),
            pd.Timestamp("2026-01-07"),
        ])
        frame = pd.DataFrame({
            "open": [100.0, 100.0, 100.0],
            "high": [101.0, 101.0, 101.0],
            "low": [99.0, 99.5, 96.0],
            "close": [100.0, 100.0, 96.5],
            "volume": [1000.0, 1000.0, 1000.0],
        }, index=dates)
        config = {
            "codes": ["rb2410.SHFE"],
            "start_date": "2026-01-05",
            "end_date": "2026-01-07",
            "initial_cash": 100_000,
            "entry_mode": "close",
            "exit_mode": "close",
            "stop_loss_mode": "hard",
            "slippage": 0.0,
            "slippage_points": 0.0,
            "commission_override": 0.0,
        }
        engine = ChinaFuturesEngine(config)
        signal = _ScenarioSignalEngine([1.0, 1.0, 1.0], [98.0, 97.0, np.nan])

        engine.run_backtest(config, _FlatLoader(frame), signal, tmp_path)

        assert len(engine.trades) == 1
        assert engine.trades[0].exit_time == dates[2]
        assert engine.trades[0].exit_price == pytest.approx(97.0)

    def test_blocked_hard_stop_is_retried_instead_of_signal_close(
        self, tmp_path, monkeypatch
    ) -> None:
        dates = pd.DatetimeIndex([
            pd.Timestamp("2026-01-05"),
            pd.Timestamp("2026-01-06"),
        ])
        frame = pd.DataFrame({
            "open": [100.0, 100.0],
            "high": [101.0, 101.0],
            "low": [99.0, 94.0],
            "close": [100.0, 95.0],
            "volume": [1000.0, 1000.0],
        }, index=dates)
        config = {
            "codes": ["rb2410.SHFE"],
            "start_date": "2026-01-05",
            "end_date": "2026-01-06",
            "initial_cash": 100_000,
            "entry_mode": "close",
            "exit_mode": "close",
            "stop_loss_mode": "hard",
            "slippage": 0.0,
            "slippage_points": 0.0,
            "commission_override": 0.0,
        }
        engine = ChinaFuturesEngine(config)
        original_can_execute = engine.can_execute

        def block_only_hard_stop(symbol, direction, bar):
            if engine._fill_phase == "stop":
                return False
            return original_can_execute(symbol, direction, bar)

        monkeypatch.setattr(engine, "can_execute", block_only_hard_stop)
        signal = _ScenarioSignalEngine([1.0, 0.0], [98.0, np.nan])

        engine.run_backtest(config, _FlatLoader(frame), signal, tmp_path)

        assert len(engine.trades) == 1
        assert engine.trades[0].exit_reason == "end_of_backtest"
        assert engine.trades[0].exit_time == dates[1]


class TestNextOpenStopEndToEnd:
    def _config(self) -> dict:
        return {
            "codes": ["rb2410.SHFE"],
            "start_date": "2026-01-05",
            "end_date": "2026-01-06",
            "initial_cash": 100_000,
            "entry_mode": "next_open",
            "exit_mode": "next_open",
            "stop_loss_mode": "hard",
            "slippage": 0.0,
            "slippage_points": 0.0,
            "commission_override": 0.0,
        }

    def test_entry_bar_stop_is_active_after_next_open_fill(self, tmp_path) -> None:
        dates = pd.DatetimeIndex([
            pd.Timestamp("2026-01-05"),
            pd.Timestamp("2026-01-06"),
        ])
        frame = pd.DataFrame({
            "open": [100.0, 100.0],
            "high": [102.0, 101.0],
            "low": [99.0, 97.0],
            "close": [100.0, 97.0],
            "volume": [1000.0, 1000.0],
        }, index=dates)
        config = self._config()
        engine = ChinaFuturesEngine(config)
        signal = _ScenarioSignalEngine([1.0, 1.0], [98.0, np.nan])

        engine.run_backtest(config, _FlatLoader(frame), signal, tmp_path)

        assert len(engine.trades) == 1
        trade = engine.trades[0]
        assert trade.entry_time == dates[1]
        assert trade.exit_time == dates[1]
        assert trade.entry_price == pytest.approx(100.0)
        assert trade.exit_price == pytest.approx(98.0)
        assert trade.exit_reason == "stop"

    def test_gap_through_stop_cancels_next_open_entry(self, tmp_path) -> None:
        dates = pd.DatetimeIndex([
            pd.Timestamp("2026-01-05"),
            pd.Timestamp("2026-01-06"),
            pd.Timestamp("2026-01-07"),
        ])
        frame = pd.DataFrame({
            "open": [10.0, 9.0, 9.0],
            "high": [10.2, 9.2, 9.2],
            "low": [9.9, 8.8, 8.8],
            "close": [10.0, 9.1, 9.1],
            "volume": [1000.0, 1000.0, 1000.0],
        }, index=dates)
        config = self._config()
        config["end_date"] = "2026-01-07"
        engine = ChinaFuturesEngine(config)
        signal = _ScenarioSignalEngine([1.0, 0.0, 0.0], [9.8, np.nan, np.nan])

        engine.run_backtest(config, _FlatLoader(frame), signal, tmp_path)

        assert engine.trades == []
