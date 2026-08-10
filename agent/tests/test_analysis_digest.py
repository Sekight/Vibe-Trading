"""Unit tests for the deterministic analysis digest (pairing/buckets/MAE-MFE)."""

from __future__ import annotations

from pathlib import Path

from backtest.analysis.digest import (
    add_mae_mfe,
    build_digest,
    holding_buckets,
    monthly_pnl,
    pair_trades,
)

from tests._analysis_fixtures import write_run_dir


def _trade_row(
    side: str,
    code: str = "A",
    pnl: float = 0.0,
    holding_days: int = 0,
    ts: str = "2024-01-02",
    return_pct: float = 0.0,
) -> dict:
    return {
        "code": code,
        "side": side,
        "timestamp": ts,
        "price": 10.0,
        "qty": 100,
        "pnl": pnl,
        "return_pct": return_pct,
        "holding_days": holding_days,
        "reason": "test",
    }


def test_pair_trades_uses_per_code_fifo() -> None:
    rows = [
        _trade_row("buy", "A", ts="2024-01-02"),
        _trade_row("buy", "A", ts="2024-01-03"),
        _trade_row("sell", "A", pnl=50.0, holding_days=3, ts="2024-01-06", return_pct=5.0),
        _trade_row("sell", "A", pnl=-30.0, holding_days=4, ts="2024-01-10", return_pct=-3.0),
    ]
    trades = pair_trades(rows)

    assert len(trades) == 2
    assert trades[0]["entry_ts"] == "2024-01-02"
    assert trades[0]["exit_ts"] == "2024-01-06"
    assert trades[0]["pnl"] == 50.0
    assert trades[0]["win"] is True
    assert trades[1]["entry_ts"] == "2024-01-03"
    assert trades[1]["pnl"] == -30.0
    assert trades[1]["win"] is False


def test_pair_trades_ignores_non_trade_rows() -> None:
    trades = pair_trades([{"code": "A", "side": "hold", "pnl": 1.0}])
    assert trades == []


def test_holding_buckets_always_returns_six_fixed_buckets() -> None:
    trades = [
        {"holding_days": 1, "pnl": 10.0, "return_pct": 1.0, "win": True},
        {"holding_days": 10, "pnl": -5.0, "return_pct": -0.5, "win": False},
        {"holding_days": 100, "pnl": 20.0, "return_pct": 2.0, "win": True},
    ]
    buckets = holding_buckets(trades)

    assert [b["bucket"] for b in buckets] == ["≤3天", "4-7天", "8-15天", "16-30天", "31-60天", ">60天"]
    assert buckets[0]["count"] == 1
    assert buckets[0]["avg_return_pct"] == 1.0
    assert buckets[1]["count"] == 0
    assert buckets[2]["count"] == 1
    assert buckets[2]["win_rate"] == 0.0
    assert buckets[5]["count"] == 1
    assert buckets[5]["win_rate"] == 1.0


def test_monthly_pnl_aggregates_by_exit_month() -> None:
    trades = [
        {"exit_ts": "2024-01-10", "pnl": 10.0},
        {"exit_ts": "2024-01-20", "pnl": -3.0},
        {"exit_ts": "2025-03-01", "pnl": 7.0},
        {"exit_ts": "", "pnl": 99.0},
    ]
    result = monthly_pnl(trades)

    assert len(result) == 2
    assert result[0] == {"year": 2024, "month": 1, "pnl": 7.0, "count": 2}
    assert result[1] == {"year": 2025, "month": 3, "pnl": 7.0, "count": 1}


def test_add_mae_mfe_excludes_entry_day_and_marks_same_day_na(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260808_111111_00_sameday")
    artifacts = run_dir / "artifacts"
    (artifacts / "ohlcv_600097.SH.csv").write_text(
        "trade_date,open,high,low,close,volume\n"
        "2024-01-02,10,10.5,9.5,10.2,100\n"
        "2024-01-03,10.2,11.0,9.6,10.8,100\n"
        "2024-01-04,10.8,11.2,9.4,9.8,100\n",
        encoding="utf-8",
    )
    trades = [
        {
            "code": "600097.SH",
            "direction": "long",
            "entry_ts": "2024-01-02",
            "exit_ts": "2024-01-04",
            "entry_price": 10.0,
            "win": True,
        },
        {
            "code": "600097.SH",
            "direction": "long",
            "entry_ts": "2024-01-04",
            "exit_ts": "2024-01-04",
            "entry_price": 10.8,
            "win": True,
        },
    ]
    enriched = add_mae_mfe(run_dir, trades)

    assert enriched[0]["mae_pct"] == 6.0
    assert enriched[0]["mfe_pct"] == 12.0
    assert enriched[1]["mae_pct"] is None
    assert enriched[1]["mfe_pct"] is None




def test_build_digest_reads_synthetic_run(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path)
    digest = build_digest(run_dir)

    assert digest["run_id"] == run_dir.name
    assert digest["config"]["codes"] == ["600097.SH"]
    assert digest["metrics"]["total_return"] == 0.05
    assert digest["trade_summary"]["count"] == 2
    assert digest["trade_summary"]["wins"] == 1
    assert digest["trade_summary"]["losses"] == 1
    assert len(digest["equity"]) == 3
    assert digest["equity"][0]["cum_return_pct"] == 0.0
    assert len(digest["monthly_pnl"]) == 2
    assert len(digest["buckets"]) == 6
    assert digest["reproducibility"]["config_hash"] == "cfg-abc"
