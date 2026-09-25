"""Tests for the stockdb direct-connect loader (P-20260925).

Unit tests monkeypatch the module-level SDK state — no service, no network.
The live smoke class at the bottom runs only when the stockdb service and SDK
are actually reachable (skipped everywhere else).
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

import backtest.loaders.stockdb_loader as sdl
from backtest.loaders.stockdb_loader import (
    DataLoader,
    _build_daily_frame,
    _build_minute_frame,
    _load_fq_table,
    _normalize_records,
    _parse_code,
    _parse_extra_fields,
    _rebuild_daily_pre_close,
    _resample_minute,
    _tcp_probe,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _daily_record(date, o, h, low, c, vol=1000.0, pct=None, pre_close=None, **extra):
    rec = {"date": date, "open": o, "high": h, "low": low, "close": c,
           "volume": vol, "amount": vol * c, "name": "X"}
    if pct is not None:
        rec["pct_chg"] = pct
    if pre_close is not None:
        # M042: stockdb's own pre_close is polluted — the builder must ignore it.
        rec["pre_close"] = pre_close
    rec.update(extra)
    return rec


@pytest.fixture
def fq_table(monkeypatch):
    """Fake factor table: 600519 has an ex-div on 20240105 (cum 1.0 → 1.25)."""
    monkeypatch.setattr(sdl, "_fq_dates", {"600519": ["20240105"]})
    monkeypatch.setattr(sdl, "_fq_cums", {"600519": [1.25]})
    return sdl


# ---------------------------------------------------------------------------
# Symbol parsing
# ---------------------------------------------------------------------------

class TestParseCode:
    def test_suffixed_and_bare(self):
        assert _parse_code("600519.SH") == "600519"
        assert _parse_code("000001.SZ") == "000001"
        assert _parse_code("600519") == "600519"

    def test_case_and_prefix_insensitive(self):
        assert _parse_code("600519.sh") == "600519"
        assert _parse_code("local:600519.SH") == "600519"
        assert _parse_code("stockdb:600519.SH") == "600519"

    def test_etf_prefixes_allowed(self):
        assert _parse_code("510050.SH") == "510050"
        assert _parse_code("159915.SZ") == "159915"

    def test_bj_rejected(self):
        assert _parse_code("430047.BJ") is None
        assert _parse_code("830799.BJ") is None

    def test_garbage_rejected(self):
        assert _parse_code("AAPL") is None
        assert _parse_code("12345") is None
        assert _parse_code("") is None


# ---------------------------------------------------------------------------
# extra_fields whitelist
# ---------------------------------------------------------------------------

class TestExtraFieldsWhitelist:
    def test_daily_full_whitelist(self):
        got = _parse_extra_fields(
            ["turnover", "amount", "industry_l1", "hack_column"],
            sdl._DAILY_EXTRA_FIELDS,
        )
        assert got == ["turnover", "amount", "industry_l1"]

    def test_minute_only_amount_and_industry(self):
        got = _parse_extra_fields(
            ["turnover", "amount", "float_share", "industry_l1"],
            sdl._MINUTE_EXTRA_FIELDS,
        )
        assert got == ["amount", "industry_l1"]

    def test_none_fields(self):
        assert _parse_extra_fields(None, sdl._DAILY_EXTRA_FIELDS) == []


# ---------------------------------------------------------------------------
# pre_close rebuild (M042)
# ---------------------------------------------------------------------------

class TestRebuildDailyPreClose:
    def test_pct_backout_exact(self):
        df = pd.DataFrame({"close": [100.0, 105.0, 99.0],
                           "pct_chg": [np.nan, 5.0, -5.7142857]})
        pre = _rebuild_daily_pre_close(df)
        assert np.isnan(pre.iloc[0])
        assert pre.iloc[1] == pytest.approx(100.0, abs=1e-9)
        assert pre.iloc[2] == pytest.approx(105.0, abs=1e-4)

    def test_polluted_stockdb_pre_close_never_used(self):
        # M042 scenario: the record's own pre_close (1605.59) contradicts
        # pct_chg — the rebuilt value backouts the TRUE prior close (~1726.02).
        df = pd.DataFrame({"close": [1685.01], "pct_chg": [-2.375],
                           "pre_close": [1605.59]})
        pre = _rebuild_daily_pre_close(df)
        assert pre.iloc[0] == pytest.approx(1685.01 / 0.97625, rel=1e-9)
        assert pre.iloc[0] != 1605.59

    def test_fallback_shift_without_pct(self):
        df = pd.DataFrame({"close": [10.0, 11.0, 12.0]})  # ETF: no pct_chg at all
        pre = _rebuild_daily_pre_close(df)
        assert np.isnan(pre.iloc[0])
        assert pre.iloc[1] == 10.0
        assert pre.iloc[2] == 11.0


# ---------------------------------------------------------------------------
# fq adjustment
# ---------------------------------------------------------------------------

class TestAdjustDivisor:
    def test_hfq(self, fq_table):
        # divisor = 1/cum: ÷1.0 before ex-div (unchanged), ÷0.8 on/after (×1.25)
        assert sdl._adjust_divisor("600519", "20240104", "hfq") == 1.0
        assert sdl._adjust_divisor("600519", "20240105", "hfq") == pytest.approx(0.8)
        assert sdl._adjust_divisor("600519", "20240301", "hfq") == pytest.approx(0.8)

    def test_qfq_anchored_to_latest(self, fq_table):
        # divisor = latest/cum: 1.25/1.0 before ex-div (×0.8), 1.0 on/after
        assert sdl._adjust_divisor("600519", "20240104", "qfq") == 1.25
        assert sdl._adjust_divisor("600519", "20240105", "qfq") == 1.0

    def test_none_is_identity(self, fq_table):
        assert sdl._adjust_divisor("600519", "20240105", "none") == 1.0

    def test_unknown_code_identity(self, fq_table):
        assert sdl._adjust_divisor("000001", "20240105", "hfq") == 1.0


class TestLoadFqTable:
    def test_parses_query_result_shape(self, monkeypatch):
        class FakeQ:
            def get(self, _):
                return [["复权:600519:20240105", 1.25], ["复权:000001:20230103", 2.0]]

        class FakeRd:
            def get(self, _):
                return FakeQ()

        dates, cums = _load_fq_table(FakeRd())
        assert dates["600519"] == ["20240105"]
        assert cums["600519"] == [1.25]
        assert dates["000001"] == ["20230103"]


# ---------------------------------------------------------------------------
# Frame builders
# ---------------------------------------------------------------------------

class TestBuildDailyFrame:
    def test_columns_and_polluted_pre_close_dropped(self, fq_table):
        recs = [
            _daily_record(20240102, 10.0, 11.0, 9.5, 10.5, pct=5.0, pre_close=7.7),
            _daily_record(20240103, 10.6, 11.5, 10.4, 11.0, pct=4.7619048, pre_close=8.1),
            _daily_record(20240105, 11.0, 12.0, 10.9, 11.5, pct=4.5454545, pre_close=8.4),
        ]
        df = _build_daily_frame(recs, "600519", "none", [], "")
        assert list(df.columns) == ["open", "high", "low", "close", "pre_close", "volume"]
        # Row 0 has pct_chg → backed out (10.5/1.05); polluted 7.7 must not appear.
        assert df["pre_close"].iloc[0] == pytest.approx(10.0, abs=1e-9)
        assert df["pre_close"].iloc[1] == pytest.approx(10.5, abs=1e-6)
        # fq=none: prices pass through untouched.
        assert df["close"].iloc[0] == 10.5

    def test_hfq_applied_on_and_after_exdiv(self, fq_table):
        recs = [
            _daily_record(20240104, 10.0, 10.0, 10.0, 10.0),
            _daily_record(20240105, 10.0, 10.0, 10.0, 10.0),
        ]
        df = _build_daily_frame(recs, "600519", "hfq", [], "")
        assert df["close"].iloc[0] == 10.0   # cum 1.0 before ex-div
        assert df["close"].iloc[1] == 12.5   # ×1.25 on/after ex-div

    def test_extra_columns_passthrough(self, fq_table):
        recs = [_daily_record(20240102, 10.0, 11.0, 9.5, 10.5,
                              turnover=1.5, float_share=1e9)]
        df = _build_daily_frame(recs, "600519", "none",
                                ["turnover", "float_share"], "")
        assert "turnover" in df.columns and "float_share" in df.columns

    def test_industry_categorical(self, fq_table):
        recs = [_daily_record(20240102, 10.0, 11.0, 9.5, 10.5)]
        df = _build_daily_frame(recs, "600519", "none", ["industry_l1"], "食品饮料")
        assert str(df["industry_l1"].dtype) == "category"
        assert df["industry_l1"].iloc[0] == "食品饮料"

    def test_invalid_ohlc_dropped(self, fq_table):
        recs = [
            _daily_record(20240102, 10.0, 9.0, 9.5, 10.5),  # high < low → dropped
            _daily_record(20240103, 10.0, 11.0, 9.5, 10.5),
        ]
        df = _build_daily_frame(recs, "600519", "none", [], "")
        assert len(df) == 1


class TestNormalizeRecords:
    def test_dict_list_passthrough(self):
        assert _normalize_records([{"a": 1}]) == [{"a": 1}]

    def test_key_value_pairs(self):
        assert _normalize_records([("k", {"a": 1})]) == [{"a": 1}]

    def test_bare_dict(self):
        assert _normalize_records({"a": 1}) == [{"a": 1}]

    def test_none(self):
        assert _normalize_records(None) == []


# ---------------------------------------------------------------------------
# Minute path
# ---------------------------------------------------------------------------

def _minute_record(ymdhms, o, h, low, c, vol=100.0, amt=None):
    return {"date": ymdhms, "open": o, "high": h, "low": low, "close": c,
            "volume": vol, "amount": amt if amt is not None else vol * c}


class TestBuildMinuteFrame:
    def test_pre_close_mapped_from_daily(self):
        recs = [_minute_record("20250603093000", 10.0, 10.1, 9.9, 10.0),
                _minute_record("20250603093100", 10.0, 10.2, 10.0, 10.1)]
        mapping = {"600519:20250603": 9.8}
        df = _build_minute_frame(recs, "600519", "none", [], "", mapping)
        assert (df["pre_close"] == 9.8).all()

    def test_hfq_applied(self, fq_table):
        recs = [_minute_record("20250603093000", 10.0, 10.1, 9.9, 10.0)]
        # 20250603 sits after the fake ex-div (20240105, cum 1.25) → ×1.25
        df = _build_minute_frame(recs, "600519", "hfq", [], "", {})
        assert df["close"].iloc[0] == 12.5


class TestResampleMinute:
    def _one_day_1m(self, base=10.0):
        # 240 one-minute bars 09:30-11:30 / 13:00-15:00 on 2025-06-03
        stamps = [pd.Timestamp("2025-06-03 09:30") + pd.Timedelta(minutes=i)
                  for i in range(120)]
        stamps += [pd.Timestamp("2025-06-03 13:00") + pd.Timedelta(minutes=i)
                   for i in range(120)]
        prices = base + np.arange(240) * 0.01
        return pd.DataFrame(
            {"open": prices, "high": prices + 0.05, "low": prices - 0.05,
             "close": prices, "volume": 100.0, "amount": prices * 100.0,
             "pre_close": 9.8},
            index=pd.DatetimeIndex(stamps, name="timestamp"),
        )

    def test_5m_counts_and_ohlc(self):
        df = self._one_day_1m()
        res = _resample_minute(df, "5m")
        assert len(res) == 48
        first = res.iloc[0]
        assert first["open"] == pytest.approx(df["open"].iloc[0])
        assert first["close"] == pytest.approx(df["close"].iloc[4])
        assert first["high"] == pytest.approx(df["high"].iloc[0:5].max())
        assert first["low"] == pytest.approx(df["low"].iloc[0:5].min())
        assert first["volume"] == pytest.approx(500.0)
        assert first["amount"] == pytest.approx(df["amount"].iloc[0:5].sum())

    def test_pre_close_constant_within_day(self):
        df = self._one_day_1m()
        res = _resample_minute(df, "5m")
        assert (res["pre_close"] == 9.8).all()

    def test_1h_natural_clock_counts(self):
        # Natural clock: 09:00-10:00 (30 bars), 10:00-11:00 (60),
        # 11:00-12:00 (30), 13:00-14:00 (60), 14:00-15:00 (60) → 5 buckets.
        df = self._one_day_1m()
        res = _resample_minute(df, "1H")
        assert len(res) == 5
        assert res.iloc[0]["close"] == pytest.approx(df["close"].iloc[29])
        assert res.iloc[1]["close"] == pytest.approx(df["close"].iloc[89])

    def test_lunch_gap_not_forward_filled(self):
        df = self._one_day_1m()
        res = _resample_minute(df, "30m")
        assert not res["close"].isna().any()


# ---------------------------------------------------------------------------
# DataLoader.fetch routing / fail-closed / key contract
# ---------------------------------------------------------------------------

def _fake_rows(sym_date_close):
    return {sym: [_daily_record(d, 10.0, 10.5, 9.5, close) for d, close in dates]
            for sym, dates in sym_date_close.items()}


class TestFetchRouting:
    def test_rejects_unsupported_interval(self, monkeypatch):
        monkeypatch.setattr(sdl, "_load_sdk", lambda: True)
        loader = DataLoader()
        assert loader.fetch(["600519.SH"], "2024-01-01", "2024-02-01",
                            interval="4H") == {}

    def test_fails_closed_without_sdk(self, monkeypatch):
        monkeypatch.setattr(sdl, "_load_sdk", lambda: False)
        loader = DataLoader()
        assert loader.fetch(["600519.SH"], "2024-01-01", "2024-02-01") == {}

    def test_returns_original_code_keys(self, monkeypatch):
        monkeypatch.setattr(sdl, "_load_sdk", lambda: True)
        monkeypatch.setattr(sdl, "_pipe_mget",
                            lambda table, syms, tq: _fake_rows(
                                {"600519": [("20240102", 10.0)]}))
        loader = DataLoader()
        out = loader.fetch(["600519.SH"], "2024-01-01", "2024-02-01")
        assert list(out) == ["600519.SH"]
        df = out["600519.SH"]
        assert df.index[0] == pd.Timestamp("2024-01-02")
        assert {"open", "high", "low", "close", "pre_close"} <= set(df.columns)

    def test_minute_uses_minute_table_and_daily_pre_close(self, monkeypatch):
        monkeypatch.setattr(sdl, "_load_sdk", lambda: True)
        captured = {}

        def fake_pipe(table, syms, tq):
            captured[table] = tq
            if table == sdl._MINUTE_TABLE:
                return {"600519": [_minute_record("20250603093000", 10.0, 10.1, 9.9, 10.0)]}
            return {"600519": [_daily_record(20250603, 10.0, 10.5, 9.5, 10.0, pct=2.0)]}

        monkeypatch.setattr(sdl, "_pipe_mget", fake_pipe)
        loader = DataLoader()
        out = loader.fetch(["600519.SH"], "2025-06-01", "2025-06-30", interval="1m")
        assert sdl._MINUTE_TABLE in captured
        df = out["600519.SH"]
        # daily pre_close = 10.0/(1+2%) = 9.8039…, rounded to 9.8 (cent precision)
        assert df["pre_close"].iloc[0] == pytest.approx(9.8)

    def test_window_end_inclusive_for_minutes(self, monkeypatch):
        monkeypatch.setattr(sdl, "_load_sdk", lambda: True)
        monkeypatch.setattr(
            sdl, "_pipe_mget",
            lambda table, syms, tq: (
                {s: [_daily_record(20250603, 10.0, 10.5, 9.5, 10.0, pct=1.0)]
                 for s in syms}
                if table == sdl._DAILY_TABLE else
                {s: [_minute_record("20250603150000", 10.0, 10.1, 9.9, 10.0)]
                 for s in syms}
            ),
        )
        loader = DataLoader()
        out = loader.fetch(["600519.SH"], "2025-06-03", "2025-06-03", interval="1m")
        assert len(out["600519.SH"]) == 1  # 15:00 bar on the end day survives

    def test_fq_mode_env(self, monkeypatch):
        monkeypatch.delenv("VIBE_TRADING_STOCKDB_FQ", raising=False)
        assert DataLoader._fq_mode() == "hfq"
        monkeypatch.setenv("VIBE_TRADING_STOCKDB_FQ", "none")
        assert DataLoader._fq_mode() == "none"
        monkeypatch.setenv("VIBE_TRADING_STOCKDB_FQ", "bogus")
        assert DataLoader._fq_mode() == "hfq"

    def test_bj_code_skipped_not_fatal(self, monkeypatch):
        monkeypatch.setattr(sdl, "_load_sdk", lambda: True)
        monkeypatch.setattr(sdl, "_pipe_mget",
                            lambda table, syms, tq: _fake_rows(
                                {"600519": [("20240102", 10.0)]}))
        loader = DataLoader()
        out = loader.fetch(["430047.BJ", "600519.SH"], "2024-01-01", "2024-02-01")
        assert list(out) == ["600519.SH"]


class TestIsAvailable:
    def test_false_without_env(self, monkeypatch):
        monkeypatch.delenv(sdl._SDK_PATH_ENV, raising=False)
        assert DataLoader().is_available() is False

    def test_false_when_port_closed(self, monkeypatch, tmp_path):
        monkeypatch.setenv(sdl._SDK_PATH_ENV, str(tmp_path))  # a dir, import fails anyway
        monkeypatch.setattr(sdl, "_tcp_probe", lambda *a, **k: False)
        monkeypatch.setattr("importlib.import_module", lambda name: object())
        assert DataLoader().is_available() is False

    def test_tcp_probe_false_on_refused(self):
        # Port 1 on localhost is virtually never listening.
        assert _tcp_probe("127.0.0.1", 1, timeout=0.2) is False


# ---------------------------------------------------------------------------
# Live smoke (skipped unless the stockdb service + SDK are actually available)
# ---------------------------------------------------------------------------

def _live_ready() -> bool:
    if not os.getenv(sdl._SDK_PATH_ENV):
        return False
    try:
        sdk_dir = os.path.abspath(os.getenv(sdl._SDK_PATH_ENV))
        if sdk_dir not in sys.path:
            sys.path.insert(0, sdk_dir)
        import stock_sdk  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return _tcp_probe(sdl._env_host(), sdl._env_port())


@pytest.mark.skipif(not _live_ready(), reason="stockdb service/SDK not available")
class TestLiveStockdb:
    def test_daily_smoke(self):
        loader = DataLoader()
        out = loader.fetch(["600519.SH"], "2024-01-02", "2024-01-10")
        df = out.get("600519.SH")
        assert df is not None and not df.empty
        assert df.index[0] == pd.Timestamp("2024-01-02")

    def test_minute_smoke(self):
        loader = DataLoader()
        out = loader.fetch(["600519.SH"], "2025-06-03", "2025-06-03", interval="5m")
        df = out.get("600519.SH")
        # Natural clock: 24 morning + 24 afternoon buckets, PLUS two single-bar
        # tail buckets (11:30 / 15:00 close-stamped bars) = 50. The exchange-
        # software 48-bar trading clock is a different (documented) convention.
        assert df is not None and len(df) == 50
