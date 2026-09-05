"""Tests for local loader ``extra_columns`` passthrough.

The config-driven local loader (data-bridge) historically kept only OHLCV +
``trade_date``. ``extra_columns`` lets a source pass additional columns
through to the signal engine without code changes. The default (no
``extra_columns``) must keep the legacy behavior byte-for-byte.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

import backtest.loaders.local_loader as local_loader


@pytest.fixture(autouse=True)
def _isolate_loader_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep these tests hermetic: the loader cache is opt-in via the host's
    ``.env`` (VIBE_TRADING_DATA_CACHE=1), and a stale disk entry from an
    earlier run must not serve (or receive) frames here."""
    import backtest.loaders.base as base

    monkeypatch.setattr(base, "loader_cache_enabled", lambda: False)


def _configure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sources: list[dict]) -> None:
    """Point the local loader at a temp config file."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"sources": sources}), encoding="utf-8")
    monkeypatch.setattr(local_loader, "_CONFIG_PATH", config_path)


def _daily_csv(tmp_path: Path, with_extra: bool = True, names: dict | None = None) -> Path:
    """2-day daily CSV; extra columns Turnover/Amount use lowercase names by default."""
    header = "Date,Open,High,Low,Close,Volume,turnover,amount"
    rows = [
        "2026-01-01,10,11,9,10.5,1000,1.2,500000",
        "2026-01-02,12,13,11,12.5,1500,0.8,600000",
    ]
    if not with_extra:
        header = "Date,Open,High,Low,Close,Volume"
        rows = [
            "2026-01-01,10,11,9,10.5,1000",
            "2026-01-02,12,13,11,12.5,1500",
        ]
    path = tmp_path / "daily.csv"
    path.write_text("\n".join([header, *rows]), encoding="utf-8")
    return path


def _base_source(csv_path: Path, extra_columns=None) -> dict:
    src = {
        "symbol": "AAA.SZ",
        "type": "csv",
        "path": str(csv_path),
        "columns": {
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        },
    }
    if extra_columns is not None:
        src["extra_columns"] = extra_columns
    return src


def test_extra_columns_list_passthrough_csv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_path = _daily_csv(tmp_path, with_extra=True)
    _configure(monkeypatch, tmp_path, [_base_source(csv_path, extra_columns=["turnover", "amount"])])

    df = local_loader.DataLoader().fetch(["AAA.SZ"], "2026-01-01", "2026-01-02")["AAA.SZ"]

    assert list(df["close"]) == [10.5, 12.5]
    assert list(df["turnover"]) == [1.2, 0.8]
    assert list(df["amount"]) == [500000.0, 600000.0]
    assert "name" not in df.columns  # non-declared columns still dropped


def test_extra_columns_dict_rename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    csv_path = tmp_path / "daily.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Date,Open,High,Low,Close,Volume,turnover_rate_pct,amount_yuan",
                "2026-01-01,10,11,9,10.5,1000,1.2,500000",
                "2026-01-02,12,13,11,12.5,1500,0.8,600000",
            ]
        ),
        encoding="utf-8",
    )
    extra = {"turnover": "turnover_rate_pct", "amount": "amount_yuan"}
    _configure(monkeypatch, tmp_path, [_base_source(csv_path, extra_columns=extra)])

    df = local_loader.DataLoader().fetch(["AAA.SZ"], "2026-01-01", "2026-01-02")["AAA.SZ"]

    assert list(df["turnover"]) == [1.2, 0.8]
    assert list(df["amount"]) == [500000.0, 600000.0]
    assert "turnover_rate_pct" not in df.columns


def test_extra_columns_absent_keeps_legacy_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_path = _daily_csv(tmp_path, with_extra=True)
    _configure(monkeypatch, tmp_path, [_base_source(csv_path)])  # no extra_columns

    df = local_loader.DataLoader().fetch(["AAA.SZ"], "2026-01-01", "2026-01-02")["AAA.SZ"]

    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert list(df["close"]) == [10.5, 12.5]


def test_extra_columns_missing_source_column_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_path = _daily_csv(tmp_path, with_extra=True)
    _configure(
        monkeypatch,
        tmp_path,
        [_base_source(csv_path, extra_columns=["turnover", "does_not_exist"])],
    )

    df = local_loader.DataLoader().fetch(["AAA.SZ"], "2026-01-01", "2026-01-02")["AAA.SZ"]

    # No crash; the declared column that exists is passed through, the missing
    # one is dropped silently.
    assert "turnover" in df.columns
    assert "does_not_exist" not in df.columns
    assert list(df["turnover"]) == [1.2, 0.8]


def test_extra_columns_parquet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pyarrow = pytest.importorskip("pyarrow")
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "open": [10.0, 12.0],
            "high": [11.0, 13.0],
            "low": [9.0, 11.0],
            "close": [10.5, 12.5],
            "volume": [1000, 1500],
            "float_share": [1e9, 1e9],
        }
    )
    parquet_path = tmp_path / "daily.parquet"
    frame.to_parquet(parquet_path, engine="pyarrow")

    src = {
        "symbol": "BBB.SH",
        "type": "parquet",
        "path": str(parquet_path),
        "extra_columns": ["float_share"],
    }
    _configure(monkeypatch, tmp_path, [src])

    df = local_loader.DataLoader().fetch(["BBB.SH"], "2026-01-01", "2026-01-02")["BBB.SH"]

    assert list(df["close"]) == [10.5, 12.5]
    assert list(df["float_share"]) == [1e9, 1e9]


def test_extra_columns_survive_coarser_resample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hourly bars with an extra column: 4H aggregation keeps the bucket-last value."""
    csv_path = tmp_path / "hourly.csv"
    rows = ["Date,Open,High,Low,Close,Volume,turnover"]
    bars = [
        ("2026-01-01 00:00:00", 10, 12, 9, 11, 100, 1.0),
        ("2026-01-01 01:00:00", 11, 13, 10, 12, 110, 1.1),
        ("2026-01-01 02:00:00", 12, 14, 11, 13, 120, 1.2),
        ("2026-01-01 03:00:00", 13, 15, 12, 14, 130, 1.3),
        ("2026-01-01 04:00:00", 14, 16, 13, 15, 140, 1.4),
        ("2026-01-01 05:00:00", 15, 17, 14, 16, 150, 1.5),
        ("2026-01-01 06:00:00", 16, 18, 15, 17, 160, 1.6),
        ("2026-01-01 07:00:00", 17, 19, 16, 18, 170, 1.7),
    ]
    rows += [f"{d},{o},{h},{lo},{c},{v},{t}" for d, o, h, lo, c, v, t in bars]
    csv_path.write_text("\n".join(rows), encoding="utf-8")

    src = {
        "symbol": "HHH.SZ",
        "type": "csv",
        "path": str(csv_path),
        "columns": {
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        },
        "extra_columns": ["turnover"],
    }
    _configure(monkeypatch, tmp_path, [src])

    df = local_loader.DataLoader().fetch(["HHH.SZ"], "2026-01-01", "2026-01-01", interval="4H")["HHH.SZ"]

    assert len(df) == 2
    assert list(df["turnover"]) == [1.3, 1.7]  # bucket-last values


def test_parse_extra_columns_forms() -> None:
    assert local_loader._parse_extra_columns(None) == ({}, [])
    assert local_loader._parse_extra_columns([]) == ({}, [])
    assert local_loader._parse_extra_columns(["a", "b"]) == ({"a": "a", "b": "b"}, ["a", "b"])
    assert local_loader._parse_extra_columns({"x": "y"}) == ({"y": "x"}, ["x"])
    # non-string list entries are filtered out
    assert local_loader._parse_extra_columns(["a", 123]) == ({"a": "a"}, ["a"])