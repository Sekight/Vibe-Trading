"""Tests for ChinaFuturesEngine market rules.

Validates:
  - T+0: can close same-day positions (unlike A-shares)
  - Both long and short allowed
  - Price limit enforcement (varies by product)
  - Integer contract rounding
  - Commission (fixed per-lot and per-notional)
  - Contract multiplier lookup
  - Margin rate lookup
  - Product code extraction
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backtest.engines.china_futures import (
    ChinaFuturesEngine,
    _extract_product,
    _MULTIPLIER,
    _MARGIN_RATE,
    _COMMISSION,
    _PRICE_LIMIT,
    _DEFAULT_PRICE_LIMIT,
)
from backtest.models import Position


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bar(
    close: float = 5000.0,
    pre_close: float | None = None,
    pct_chg: float | None = None,
    settle: float | None = None,
    pre_settle: float | None = None,
    open_: float | None = None,
) -> pd.Series:
    d: dict = {"close": close, "open": open_ or close}
    if pre_close is not None:
        d["pre_close"] = pre_close
    if pct_chg is not None:
        d["pct_chg"] = pct_chg
    if settle is not None:
        d["settle"] = settle
    if pre_settle is not None:
        d["pre_settle"] = pre_settle
    return pd.Series(d)


def _make_engine(**overrides) -> ChinaFuturesEngine:
    config = {"initial_cash": 1_000_000, "codes": ["IF2406.CFFEX"]}
    config.update(overrides)
    return ChinaFuturesEngine(config)


# ---------------------------------------------------------------------------
# Product extraction
# ---------------------------------------------------------------------------


class TestExtractProduct:
    @pytest.mark.parametrize(
        "symbol, expected",
        [
            ("IF2406.CFFEX", "IF"),
            ("rb2410.SHFE", "rb"),
            ("au2412", "au"),
            ("CF501.ZCE", "CF"),
            ("sc2503.INE", "sc"),
            ("si2406.GFEX", "si"),
        ],
    )
    def test_extract(self, symbol: str, expected: str) -> None:
        assert _extract_product(symbol) == expected


# ---------------------------------------------------------------------------
# can_execute: T+0 (both directions allowed)
# ---------------------------------------------------------------------------


class TestDirectionAndT0:
    def test_long_allowed(self) -> None:
        engine = _make_engine()
        bar = _make_bar()
        assert engine.can_execute("IF2406.CFFEX", 1, bar) is True

    def test_short_allowed(self) -> None:
        """China futures allow short selling (unlike A-shares)."""
        engine = _make_engine()
        bar = _make_bar()
        assert engine.can_execute("IF2406.CFFEX", -1, bar) is True

    def test_close_same_day_allowed(self) -> None:
        """T+0: can close positions opened today."""
        engine = _make_engine()
        engine.positions["IF2406.CFFEX"] = Position(
            symbol="IF2406.CFFEX",
            direction=1,
            entry_price=5000.0,
            entry_time=pd.Timestamp("2025-06-10"),
            size=2.0,
            leverage=1 / 0.12,
        )
        bar = _make_bar()
        assert engine.can_execute("IF2406.CFFEX", 0, bar) is True


# ---------------------------------------------------------------------------
# can_execute: price limits
# ---------------------------------------------------------------------------


class TestPriceLimits:
    def test_stock_index_limit_up_blocks_long(self) -> None:
        """IF has ±10% limit; at limit-up, can't open long."""
        engine = _make_engine()
        bar = _make_bar(close=5500.0, pre_close=5000.0)  # +10%
        assert engine.can_execute("IF2406.CFFEX", 1, bar) is False

    def test_stock_index_limit_down_blocks_short(self) -> None:
        engine = _make_engine()
        bar = _make_bar(close=4500.0, pre_close=5000.0)  # -10%
        assert engine.can_execute("IF2406.CFFEX", -1, bar) is False

    def test_stock_index_within_limit(self) -> None:
        engine = _make_engine()
        bar = _make_bar(close=5200.0, pre_close=5000.0)  # +4%
        assert engine.can_execute("IF2406.CFFEX", 1, bar) is True

    def test_commodity_default_5pct(self) -> None:
        """Commodity like rb uses default ±5% limit."""
        engine = _make_engine(codes=["rb2410.SHFE"])
        bar = _make_bar(close=4250.0, pre_close=4000.0)  # +6.25% > 5%
        assert engine.can_execute("rb2410.SHFE", 1, bar) is False

    def test_commodity_within_limit(self) -> None:
        engine = _make_engine(codes=["rb2410.SHFE"])
        bar = _make_bar(close=4100.0, pre_close=4000.0)  # +2.5%
        assert engine.can_execute("rb2410.SHFE", 1, bar) is True

    def test_limit_down_blocks_long_close(self) -> None:
        """At limit-down, can't sell (close long position)."""
        engine = _make_engine()
        engine.positions["IF2406.CFFEX"] = Position(
            "IF2406.CFFEX", 1, 5000.0, pd.Timestamp("2025-06-09"), 2.0,
        )
        bar = _make_bar(close=4500.0, pre_close=5000.0)  # -10%
        assert engine.can_execute("IF2406.CFFEX", 0, bar) is False


# ---------------------------------------------------------------------------
# round_size
# ---------------------------------------------------------------------------


class TestRoundSize:
    def test_rounds_down_to_integer(self) -> None:
        engine = _make_engine()
        assert engine.round_size(2.7, 5000.0) == 2

    def test_exact_integer(self) -> None:
        engine = _make_engine()
        assert engine.round_size(5.0, 5000.0) == 5

    def test_less_than_one_becomes_zero(self) -> None:
        engine = _make_engine()
        assert engine.round_size(0.9, 5000.0) == 0

    def test_negative_clamps_to_zero(self) -> None:
        engine = _make_engine()
        assert engine.round_size(-2.0, 5000.0) == 0


# ---------------------------------------------------------------------------
# calc_commission
# ---------------------------------------------------------------------------


class TestCommission:
    def test_rate_commission_via_active_symbol(self) -> None:
        """calc_commission uses _active_symbol for product-specific rate."""
        engine = _make_engine()
        engine._active_symbol = "IF2406.CFFEX"
        comm = engine.calc_commission(2, 5000.0, 1, is_open=True)
        # 2 contracts × 5000 × 300 (multiplier) × 0.000023 = 69
        expected = 2 * 5000 * 300 * 0.000023
        assert comm == pytest.approx(expected, rel=0.01)

    def test_fixed_commission_via_active_symbol(self) -> None:
        """au uses fixed per-lot commission."""
        engine = _make_engine()
        engine._active_symbol = "au2412.SHFE"
        comm = engine.calc_commission(3, 500.0, 1, is_open=True)
        expected = 3 * 10.0  # 10 RMB per lot
        assert comm == pytest.approx(expected)

    def test_symbol_aware_rate_commission(self) -> None:
        engine = _make_engine()
        comm = engine.calc_commission_for_symbol("IF2406.CFFEX", 2, 5000.0, is_open=True)
        expected = 2 * 5000 * 300 * 0.000023
        assert comm == pytest.approx(expected, rel=0.01)

    def test_commission_override(self) -> None:
        engine = _make_engine(commission_override=0.001)
        comm = engine.calc_commission(5, 4000.0, 1, is_open=True)
        assert comm == pytest.approx(5 * 4000.0 * 0.001)


# ---------------------------------------------------------------------------
# Contract multiplier and margin rate
# ---------------------------------------------------------------------------


class TestContractMultiplier:
    @pytest.mark.parametrize(
        "symbol, expected",
        [
            ("IF2406.CFFEX", 300),
            ("IC2406.CFFEX", 200),
            ("rb2410.SHFE", 10),
            ("au2412.SHFE", 1000),
            ("sc2503.INE", 1000),
            ("c2501.DCE", 10),
            ("CF501.ZCE", 5),
        ],
    )
    def test_multipliers(self, symbol: str, expected: int) -> None:
        engine = _make_engine()
        assert engine.get_contract_multiplier(symbol) == expected


class TestMarginRate:
    def test_stock_index_12pct(self) -> None:
        engine = _make_engine()
        assert engine.get_margin_rate("IF2406.CFFEX") == 0.12

    def test_copper_8pct(self) -> None:
        engine = _make_engine()
        assert engine.get_margin_rate("cu2410.SHFE") == 0.08

    def test_unknown_product_default_10pct(self) -> None:
        engine = _make_engine()
        assert engine.get_margin_rate("XX9999.SHFE") == 0.10


# ---------------------------------------------------------------------------
# Slippage
# ---------------------------------------------------------------------------


class TestSlippage:
    def test_buy_slippage_increases_price(self) -> None:
        engine = _make_engine()
        assert engine.apply_slippage(5000.0, 1) > 5000.0

    def test_sell_slippage_decreases_price(self) -> None:
        engine = _make_engine()
        assert engine.apply_slippage(5000.0, -1) < 5000.0

    def test_custom_slippage(self) -> None:
        engine = _make_engine(slippage=0.002)
        assert engine.apply_slippage(5000.0, 1) == pytest.approx(5010.0)


# ---------------------------------------------------------------------------
# Leverage derived from margin
# ---------------------------------------------------------------------------


class TestLeverageFromMargin:
    def test_if_leverage(self) -> None:
        """IF margin=12% → leverage≈8.33."""
        engine = _make_engine(codes=["IF2406.CFFEX"])
        assert engine.default_leverage == pytest.approx(1 / 0.12, rel=0.01)

    def test_override_margin_rate(self) -> None:
        engine = _make_engine(margin_rate_override=0.20)
        assert engine.default_leverage == pytest.approx(5.0)

    def test_order_sizing_does_not_depend_on_symbol_order(self) -> None:
        timestamp = pd.Timestamp("2026-01-05")
        frame = pd.DataFrame(
            {"open": [5_000.0], "close": [5_000.0]},
            index=pd.DatetimeIndex([timestamp]),
        )
        first = _make_engine(codes=["IF2406.CFFEX", "T2406.CFFEX"])
        second = _make_engine(codes=["T2406.CFFEX", "IF2406.CFFEX"])

        first_order = first._plan_open_order(
            "IF2406.CFFEX", 0.5, frame, timestamp, 1_000_000.0
        )
        second_order = second._plan_open_order(
            "IF2406.CFFEX", 0.5, frame, timestamp, 1_000_000.0
        )

        assert first_order is not None
        assert second_order is not None
        assert first_order.size == second_order.size
        assert first_order.leverage == pytest.approx(1 / 0.12)
        assert second_order.leverage == pytest.approx(1 / 0.12)

    def test_composite_delegates_symbol_leverage(self) -> None:
        from backtest.engines.composite import CompositeEngine

        engine = CompositeEngine(
            {"initial_cash": 1_000_000, "codes": ["AAPL.US", "IF2406.CFFEX"]},
            ["AAPL.US", "IF2406.CFFEX"],
        )

        assert engine._leverage_for_symbol("IF2406.CFFEX") == pytest.approx(1 / 0.12)


def test_full_cycle_rb_commission_flows_to_metrics_and_trades_csv(tmp_path: Path) -> None:
    """rb 万1/side: per-side fees land in TradeRecord, total_commission and trades.csv."""
    from backtest.metrics import calc_metrics

    dates = pd.bdate_range("2025-09-01", periods=6)
    frame = pd.DataFrame({
        "open": [3100.0] * 6,
        "high": [3110.0] * 6,
        "low": [3090.0] * 6,
        "close": [3100.0] * 6,
        "pre_close": [3100.0] * 6,
        "pct_chg": [0.0] * 6,
        "settle": [3100.0] * 6,
        "pre_settle": [3100.0] * 6,
        "volume": [100] * 6,
    }, index=dates)
    engine = _make_engine(codes=["rb2410.SHFE"], interval="1D")
    targets = pd.DataFrame(
        {"rb2410.SHFE": [0.0, 1.0, 1.0, 1.0, 0.0, 0.0]}, index=dates
    )
    engine._execute_bars(
        dates,
        {"rb2410.SHFE": frame},
        frame[["close"]].rename(columns={"close": "rb2410.SHFE"}),
        targets,
        ["rb2410.SHFE"],
    )

    assert len(engine.trades) == 1
    t = engine.trades[0]
    multiplier = 10  # rb contract multiplier
    entry_fee = t.size * t.entry_price * multiplier * 0.0001
    exit_fee = t.size * t.exit_price * multiplier * 0.0001
    assert t.entry_commission == pytest.approx(entry_fee)
    assert t.commission == pytest.approx(entry_fee + exit_fee)

    equity = pd.Series(
        [s.equity for s in engine.equity_snapshots],
        index=[s.timestamp for s in engine.equity_snapshots],
    )
    m = calc_metrics(equity, engine.trades, engine.initial_capital, 252)
    assert m["total_commission"] == pytest.approx(t.commission)

    engine._write_artifacts(
        tmp_path,
        {"rb2410.SHFE": frame},
        dates,
        equity,
        pd.Series(1_000_000.0, index=dates),
        pd.Series(0.0, index=dates),
        targets,
        {},
        ["rb2410.SHFE"],
    )
    rows = pd.read_csv(tmp_path / "artifacts" / "trades.csv")
    assert rows["commission"].sum() == pytest.approx(t.commission)


# ---------------------------------------------------------------------------
# Minimum price tick: lookup + stop-fill rounding
# ---------------------------------------------------------------------------


class TestPriceTick:
    def test_tick_lookup(self) -> None:
        engine = _make_engine(codes=["rb2410.SHFE"])
        assert engine.get_price_tick("rb2410.SHFE") == 1.0
        assert engine.get_price_tick("IF2406.CFFEX") == 0.2
        assert engine.get_price_tick("au2412") == 0.02
        assert engine.get_price_tick("T2406.CFFEX") == 0.005
        assert engine.get_price_tick("UNKNOWN") is None

    def test_round_stop_fill_long_floor_short_ceil(self) -> None:
        engine = _make_engine(codes=["rb2410.SHFE"])
        # 多单 floor、空单 ceil 到 1 元
        assert engine._round_stop_fill(3143.7571, 1, "rb2410.SHFE") == 3143.0
        assert engine._round_stop_fill(3169.2857, -1, "rb2410.SHFE") == 3170.0
        # 小数档 tick：IF 0.2、au 0.02
        assert engine._round_stop_fill(3456.15, 1, "IF2406.CFFEX") == 3456.0
        assert engine._round_stop_fill(612.345, 1, "au2412") == pytest.approx(612.34)
        # 未知品种不取整
        assert engine._round_stop_fill(100.5, 1, "XXX") == 100.5

    def test_close_fill_price_long_floor(self) -> None:
        engine = _make_engine(codes=["rb2410.SHFE"])
        engine._same_bar = True
        engine.positions["rb2410.SHFE"] = Position(
            "rb2410.SHFE", 1, 3152.0, pd.Timestamp("2025-09-17"), 16.0
        )
        engine._stop_price = lambda ts, symbol: 3143.7571  # type: ignore[method-assign]
        bar = pd.Series({"open": 3155.0, "high": 3160.0, "low": 3140.0, "close": 3145.0})
        assert engine._close_fill_price(
            bar, pd.Timestamp("2025-09-17 10:05:00"), "rb2410.SHFE"
        ) == 3143.0
        # 跳空低开穿破止损：按实际开盘价成交，不取整
        bar_gap = pd.Series({"open": 3140.0, "high": 3160.0, "low": 3135.0, "close": 3145.0})
        assert engine._close_fill_price(
            bar_gap, pd.Timestamp("2025-09-17 10:05:00"), "rb2410.SHFE"
        ) == 3140.0

    def test_close_fill_price_short_ceil(self) -> None:
        engine = _make_engine(codes=["rb2410.SHFE"])
        engine._same_bar = True
        engine.positions["rb2410.SHFE"] = Position(
            "rb2410.SHFE", -1, 3160.0, pd.Timestamp("2025-09-19"), 15.0
        )
        engine._stop_price = lambda ts, symbol: 3169.2857  # type: ignore[method-assign]
        bar = pd.Series({"open": 3165.0, "high": 3175.0, "low": 3160.0, "close": 3170.0})
        assert engine._close_fill_price(
            bar, pd.Timestamp("2025-09-19 13:50:00"), "rb2410.SHFE"
        ) == 3170.0
