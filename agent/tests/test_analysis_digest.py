"""Unit tests for the deterministic analysis digest (pairing/buckets/MAE-MFE)."""

from __future__ import annotations

from pathlib import Path

import json

import pytest

from backtest.analysis.digest import (
    add_mae_mfe,
    build_digest,
    group_metrics,
    holding_buckets,
    load_digest,
    monthly_pnl,
    pair_trades,
    render_digest_for_llm,
)

import pandas as pd

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


def test_build_digest_reads_benchmark_curve_and_validation(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260811_000000_00_bench")
    (run_dir / "artifacts" / "equity.csv").write_text(
        "timestamp,equity,drawdown,benchmark_equity\n"
        "2024-01-05,1000000,0,1000000\n"
        "2024-01-20,1010000,-0.01,1010000\n"
        "2024-02-15,1050000,0,990000\n",
        encoding="utf-8",
    )
    (run_dir / "artifacts" / "validation.json").write_text(
        json.dumps({"monte_carlo": {"p_value_sharpe": 0.123, "n_simulations": 1000}}),
        encoding="utf-8",
    )
    digest = build_digest(run_dir)

    assert digest["equity"][0]["benchmark_cum_return_pct"] == 0.0
    assert digest["equity"][0]["benchmark_drawdown_pct"] == 0.0
    assert digest["equity"][1]["benchmark_cum_return_pct"] == 1.0
    assert digest["equity"][2]["benchmark_cum_return_pct"] == -1.0
    assert digest["equity"][2]["benchmark_drawdown_pct"] == pytest.approx(-1.9802, abs=1e-4)
    assert digest["validation"]["monte_carlo"]["p_value_sharpe"] == 0.123


def test_load_digest_builds_on_the_fly_without_persisting(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260811_111111_00_digest")
    digest = load_digest(run_dir)
    assert digest["run_id"] == run_dir.name
    assert not (run_dir / "analysis.digest.json").exists()


def test_group_metrics_covers_all_scalars_and_keeps_benchmark_label() -> None:
    metrics = {
        "total_return": 0.05, "annual_return": 0.2, "final_value": 1050000.0,
        "sharpe": 0.8, "sortino": 0.7, "calmar": 0.6, "max_drawdown": -0.1,
        "win_rate": 0.5, "profit_factor": 2.0, "profit_loss_ratio": 2.5,
        "trade_count": 20, "avg_holding_days": 10, "max_consecutive_loss": 3,
        "benchmark_label": "000300.SH", "benchmark_ticker": "000300.SH",
        "benchmark_return": 0.03, "benchmark_beta": 0.9,
        "excess_return": 0.02, "information_ratio": 0.4, "tracking_error": 0.1,
        "risk_xray_annualized_vol": 0.2, "risk_xray_avg_invested": 0.8,
        "risk_xray_effective_n": 3, "risk_xray_hhi": 0.5,
        "risk_xray_max_drawdown": -0.2, "beta_to_equal_weight": 0.95,
        "monte_carlo_p_value_sharpe": 0.1, "monte_carlo_p_value_max_dd": 0.2,
        "monte_carlo_n_simulations": 500,
        "avg_portfolio_weight": 0.5, "max_portfolio_weight": 0.8, "max_single_weight": 0.4,
        "avg_turnover": 0.05, "total_turnover": 1.0,
        "rebalance_turnover_mean": 0.1, "rebalance_turnover_max": 0.2,
        "rebalance_count": 10,
        "extra_scalar": 7,
    }
    groups = group_metrics(metrics)
    labels = [label for label, _ in groups]
    assert labels == ["性能", "基准相对", "风险", "仓位与换手", "再平衡", "其他"]
    assigned = {key for _, items in groups for key, _ in items}
    assert assigned == set(metrics)


def test_render_digest_for_llm_includes_benchmark_and_grouped_metrics(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260811_222222_00_render")
    digest = build_digest(run_dir)
    prompt = render_digest_for_llm(digest)

    assert "## 指标解读（全量指标）" in prompt
    assert "### 性能" in prompt
    assert "| 指标 | 含义 | 值 |" in prompt
    assert "| total_return | 累计总收益率 | 0.05 |" in prompt
    assert "| trade_count | 成交笔数（完成回合的交易数） | 2 |" in prompt
    assert "equal-weight(universe)" in prompt
    assert "## 核心指标" not in prompt
    assert "## Regime 摘要" in prompt
    assert "无数据" in prompt


def test_build_digest_includes_regime_summary_for_two_assets(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260811_333333_00_regime")
    artifacts = run_dir / "artifacts"
    # write_run_dir ships one single-asset OHLCV file; drop it so the digest
    # regime uses exactly the two assets this test constructs.
    (artifacts / "ohlcv_600097.SH.csv").unlink()
    dates = pd.bdate_range("2024-01-02", periods=120)
    for idx, code in enumerate(["A.SH", "B.SH"]):
        rows = []
        drift = 0.0
        for ts in dates:
            drift += 0.05 + idx * 0.01
            close = 10.0 + idx + drift + (ts.day % 3) * 0.1
            rows.append({
                "trade_date": ts.strftime("%Y-%m-%d"),
                "open": close, "high": close + 0.2, "low": close - 0.2,
                "close": close, "volume": 1000,
            })
        pd.DataFrame(rows).to_csv(
            artifacts / f"ohlcv_{code}.csv", index=False, encoding="utf-8"
        )
    (run_dir / "config.json").write_text(
        json.dumps({
            "codes": ["A.SH", "B.SH"],
            "regime": {"corr_window": 20, "smooth_window": 3},
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    digest = build_digest(run_dir)
    regime = digest["regime"]
    assert "skipped" not in regime
    assert regime["labels"] == ["A.SH", "B.SH"]
    assert len(regime["dates"]) == len(regime["fused"])
    assert regime["fused_pct"] is not None
    assert isinstance(regime["episodes"], list)
    assert set(regime["trade_summary"]) == {"fused", "defused", "unknown"}

    prompt = render_digest_for_llm(digest)
    assert "## Regime 摘要" in prompt
    assert "FUSED 时间占比" in prompt
