"""Unit tests for the deterministic analysis digest (pairing/buckets/MAE-MFE)."""

from __future__ import annotations

from pathlib import Path

import json

import pytest

from backtest.analysis.digest import (
    METRIC_MEANINGS,
    add_mae_mfe,
    build_digest,
    daily_position_and_risk,
    group_metrics,
    holding_buckets,
    load_digest,
    monthly_pnl,
    pair_trades,
    position_groups,
    render_digest_for_llm,
    single_group_daily_series,
    write_digest_json,
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
        {"holding_bars": 3, "pnl": 10.0, "return_pct": 1.0, "win": True},
        {"holding_bars": 10, "pnl": -5.0, "return_pct": -0.5, "win": False},
        {"holding_bars": 100, "pnl": 20.0, "return_pct": 2.0, "win": True},
    ]
    buckets = holding_buckets(trades)

    assert [b["bucket"] for b in buckets] == ["0-4根", "5-10根", "11-20根", "21-40根", "41-80根", ">80根"]
    assert buckets[0]["count"] == 1
    assert buckets[0]["avg_return_pct"] == 1.0
    assert buckets[1]["count"] == 1
    assert buckets[2]["count"] == 0
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




def test_load_digest_builds_and_persists_when_file_missing(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260811_111111_00_digest")
    digest = load_digest(run_dir)
    assert digest["run_id"] == run_dir.name
    payload = json.loads((run_dir / "analysis.digest.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 3
    assert payload["digest"]["run_id"] == run_dir.name
    assert payload["sources"]["artifacts/trades.csv"]["size"] > 0


def test_write_digest_json_persists_schema_sources_and_digest(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260811_111111_00_digest")
    write_digest_json(run_dir)
    payload = json.loads((run_dir / "analysis.digest.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 3
    assert payload["digest"]["metrics"]["total_return"] == 0.05
    assert payload["sources"]["artifacts/equity.csv"]["size"] > 0


def test_load_digest_reads_a_fresh_persisted_copy(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260811_111111_00_digest")
    write_digest_json(run_dir)
    digest_path = run_dir / "analysis.digest.json"
    payload = json.loads(digest_path.read_text(encoding="utf-8"))
    payload["digest"]["run_id"] = "tampered-cached-run"
    digest_path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_digest(run_dir)["run_id"] == "tampered-cached-run"


def test_load_digest_rebuilds_when_an_artifact_changes(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260811_111111_00_digest")
    write_digest_json(run_dir)
    trades_path = run_dir / "artifacts" / "trades.csv"
    trades_path.write_text(trades_path.read_text(encoding="utf-8") + "extra\n", encoding="utf-8")

    digest = load_digest(run_dir)
    assert digest["run_id"] == run_dir.name
    payload = json.loads((run_dir / "analysis.digest.json").read_text(encoding="utf-8"))
    assert payload["sources"]["artifacts/trades.csv"]["size"] == trades_path.stat().st_size


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
        "total_commission": 100.0,
        "extra_scalar": 7,
    }
    groups = group_metrics(metrics)
    labels = [label for label, _ in groups]
    assert labels == ["性能", "基准相对", "风险", "仓位与换手", "交易成本", "再平衡", "其他"]
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
    assert "平均持仓: " in prompt
    assert "平均盈亏比（按单笔收益率）" in prompt
    assert "equal-weight(universe)" in prompt
    assert "## 核心指标" not in prompt
    assert "## Regime 摘要" in prompt
    assert "无数据" in prompt


def test_render_digest_for_llm_includes_total_commission_group(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260811_444444_00_comm")
    digest = build_digest(run_dir)
    digest["metrics"]["total_commission"] = 123.45
    prompt = render_digest_for_llm(digest)

    assert "### 交易成本" in prompt
    assert "| total_commission | 总手续费" in prompt
    assert "123.45" in prompt


def test_metric_meanings_are_unambiguous() -> None:
    assert "策略净值最大回撤" in METRIC_MEANINGS["max_drawdown"]
    assert "按每交易日 bar 数换算" in METRIC_MEANINGS["avg_holding_days"]
    assert "平均持仓篮子最大回撤" in METRIC_MEANINGS["risk_xray_max_drawdown"]
    assert "按盈亏金额" in METRIC_MEANINGS["profit_loss_ratio"]
    assert "总手续费" in METRIC_MEANINGS["total_commission"]


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


def test_build_digest_skips_regime_and_mae_mfe_when_disabled(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260817_000000_00_fastrun")
    digest = build_digest(run_dir, include_regime=False, include_mae_mfe=False)

    assert "regime" not in digest
    assert "mae_mfe_summary" not in digest
    assert all("mae_pct" not in trade and "mfe_pct" not in trade for trade in digest["trades"])
    # The untouched sections are still present and identical to the full build.
    # top_winners/top_losers are excluded: they embed trade rows whose
    # mae_pct/mfe_pct legitimately differ between the two builds.
    full = build_digest(run_dir)
    for key in (
        "metrics", "equity", "trade_summary", "monthly_pnl", "period_pnl",
        "buckets", "ohlcv_summary", "reproducibility",
    ):
        assert digest[key] == full[key]
    assert full["mae_mfe_summary"]["with_data"] == 2


def test_build_digest_skip_flags_are_independent(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260817_000000_00_partial")
    only_regime = build_digest(run_dir, include_mae_mfe=False)
    assert "mae_mfe_summary" not in only_regime
    assert "regime" in only_regime

    only_mae_mfe = build_digest(run_dir, include_regime=False)
    assert "regime" not in only_mae_mfe
    assert "mae_mfe_summary" in only_mae_mfe


def test_render_digest_for_llm_omits_skipped_sections(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260817_000000_00_render")
    full = build_digest(run_dir)
    prompt_full = render_digest_for_llm(full)
    assert "## MAE/MFE（bar 级，入场 bar 不计）" in prompt_full
    assert "## Regime 摘要" in prompt_full

    skipped = build_digest(run_dir, include_regime=False, include_mae_mfe=False)
    prompt_skipped = render_digest_for_llm(skipped)
    assert "## MAE/MFE（bar 级，入场 bar 不计）" not in prompt_skipped
    assert "## Regime 摘要" not in prompt_skipped
    assert "## 交易概览" in prompt_skipped
    assert "## 持仓分桶" in prompt_skipped


def test_write_digest_json_forwards_include_params(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260817_000000_00_persist")
    write_digest_json(run_dir, include_regime=False, include_mae_mfe=False)
    payload = json.loads((run_dir / "analysis.digest.json").read_text(encoding="utf-8"))
    assert "regime" not in payload["digest"]
    assert "mae_mfe_summary" not in payload["digest"]
    # A fresh load still returns the persisted (skipped) digest, not a rebuild.
    assert "regime" not in load_digest(run_dir)


# ---------------------------------------------------------------------------
# daily_position / daily_risk — per-day peak of gross/net/single-sided weights
# ---------------------------------------------------------------------------


def test_daily_position_and_risk_aggregation(tmp_path: Path) -> None:
    """daily_position = close-of-day snapshot (last day-session bar, evening
    bars excluded); daily_risk = daily peak of the single exposure (evening
    bars included). Covers a net-short day, a locked (long + short) day, and a
    day where the peak bar is NOT the closing bar."""
    run_dir = write_run_dir(tmp_path, "20260818_000000_00_posrisk")
    (run_dir / "artifacts" / "positions.csv").write_text(
        "timestamp,AAA,BBB\n"
        "2024-01-02 09:00:00,0.4,0.0\n"   # day1 bar1: gross .4 (day-session peak)
        "2024-01-02 14:00:00,0.3,0.0\n"   # day1 bar2: gross .3 (close of day)
        "2024-01-02 20:00:00,0.5,0.0\n"   # day1 bar3: gross .5 (evening, excluded from close)
        "2024-01-03 09:00:00,-0.2,0.1\n"  # day2: gross .3 net -.1 single max(.1,|-.2|)=.2
        "2024-01-04 09:00:00,0.2,-0.2\n"  # day3 locked: gross .4 net 0 single .2
        ,
        encoding="utf-8",
    )
    groups = {"G": ["AAA", "BBB"]}
    daily_position, daily_risk = daily_position_and_risk(run_dir, groups)
    by_date = {item["date"]: item for item in daily_position}
    risk_by_date = {item["date"]: item["risk_pct"] for item in daily_risk}
    # Close-of-day values (day-session last bar; 20:00 evening bar excluded).
    assert by_date["2024-01-02"]["gross_pct"] == 30.0
    assert by_date["2024-01-02"]["net_pct"] == 30.0
    assert by_date["2024-01-02"]["single_pct"] == 30.0
    assert by_date["2024-01-03"]["gross_pct"] == 30.0
    assert by_date["2024-01-03"]["net_pct"] == -10.0
    assert by_date["2024-01-03"]["single_pct"] == 20.0
    assert by_date["2024-01-04"]["gross_pct"] == 40.0
    assert by_date["2024-01-04"]["net_pct"] == 0.0
    assert by_date["2024-01-04"]["single_pct"] == 20.0
    # Peak risk: the biggest single exposure of the day, evening bar included.
    assert risk_by_date["2024-01-02"] == 50.0
    assert risk_by_date["2024-01-03"] == 20.0
    assert risk_by_date["2024-01-04"] == 20.0
    # Without a grouping, single-sided == gross (no per-group lock handling).
    dp2, _ = daily_position_and_risk(run_dir, None)
    assert dp2[0]["single_pct"] == 30.0
    assert dp2[1]["single_pct"] == 30.0


def test_daily_position_missing_positions_csv_returns_empty(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260818_000000_00_nopos")
    assert daily_position_and_risk(run_dir, None) == ([], [])


def test_build_digest_includes_daily_series_and_payload(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260818_000000_00_digestpos")
    digest = build_digest(run_dir)  # synthetic run ships no positions.csv
    assert digest["daily_position"] == []
    assert digest["daily_risk"] == []
    assert digest["position_risk_summary"] is None

    from backtest.analysis.charts import compute_chart_payload
    payload = compute_chart_payload(digest)
    assert payload["daily_position"] == []
    assert payload["daily_risk"] == []


def test_render_digest_for_llm_risk_summary_without_full_series(tmp_path: Path) -> None:
    """The LLM prompt gets the derived summary, never the full daily series."""
    run_dir = write_run_dir(tmp_path, "20260818_000000_00_llmrisk")
    (run_dir / "artifacts" / "positions.csv").write_text(
        "timestamp,AAA\n"
        "2024-01-02 09:00:00,0.2\n"
        "2024-01-03 09:00:00,-0.2\n"
        "2024-01-04 09:00:00,1.2\n"   # 120% -> over the 100% liquidation line
        ,
        encoding="utf-8",
    )
    digest = build_digest(run_dir)
    summary = digest["position_risk_summary"]
    assert summary["risk_max_pct"] == 120.0
    assert summary["risk_over_100"]["days"] == 1
    assert summary["risk_over_100"]["pct"] == pytest.approx(33.33)

    prompt = render_digest_for_llm(digest)
    assert "## 仓位与风险摘要" in prompt
    assert "收盘毛持仓 最大/平均" in prompt
    assert "风险度 ≥100% 天数/占比" in prompt
    assert "1 天 / 33.33%" in prompt
    # Full-series field names and structures must never reach the LLM prompt.
    assert "gross_pct" not in prompt
    assert "net_pct" not in prompt
    assert "single_pct" not in prompt
    assert "risk_pct" not in prompt
    assert '"date"' not in prompt


def test_load_digest_incrementally_backfills_positions_on_old_digest(tmp_path: Path) -> None:
    """A V034-era digest (sources without positions.csv) is back-filled fast
    instead of fully rebuilt: existing regime/MAE-MFE fields survive."""
    run_dir = write_run_dir(tmp_path, "20260818_000000_00_olddigest")
    (run_dir / "artifacts" / "positions.csv").write_text(
        "timestamp,AAA\n2024-01-02 09:00:00,0.2\n",
        encoding="utf-8",
    )
    full = build_digest(run_dir)
    # Simulate an old persisted digest: drop positions.csv from its sources.
    from backtest.analysis.digest import _artifact_fingerprint, write_digest_json
    write_digest_json(run_dir, full)
    path = run_dir / "analysis.digest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["sources"].pop("artifacts/positions.csv")
    payload["digest"].pop("daily_position", None)
    payload["digest"].pop("daily_risk", None)
    payload["digest"].pop("position_risk_summary", None)
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_digest(run_dir)
    assert loaded["daily_position"] == full["daily_position"]
    assert loaded["daily_risk"] == full["daily_risk"]
    assert loaded["position_risk_summary"] == full["position_risk_summary"]
    # Slow, expensive sections of the old digest were preserved, not rebuilt.
    assert "regime" in loaded
    assert "mae_mfe_summary" in loaded
    # The back-filled digest is persisted with the new fingerprint (cache hits next time).
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["sources"] == _artifact_fingerprint(run_dir)



# ---------------------------------------------------------------------------
# single-symbol daily position series — position_groups / single_group_daily_series
# ---------------------------------------------------------------------------


def test_position_groups_merges_pseudo_units(tmp_path: Path) -> None:
    """weight_groups merges pseudo units into one logical group; codes without
    a declaration stay as their own group; each group reports peak exposure."""
    run_dir = write_run_dir(tmp_path, "20260818_000000_00_groups")
    (run_dir / "artifacts" / "positions.csv").write_text(
        "timestamp,RB01,RB02,TA01\n"
        "2024-01-02 09:00:00,0.1,0.1,-0.08\n"
        "2024-01-03 09:00:00,0.2,-0.1,0.0\n",
        encoding="utf-8",
    )
    (run_dir / "code" / "signal_engine.py").write_text(
        "class SignalEngine:\n"
        "    weight_groups = {'RB': ['RB01', 'RB02']}\n"
        "    def generate(self, data_map):\n"
        "        return {c: __import__('pandas').Series(dtype=float) for c in data_map}\n",
        encoding="utf-8",
    )
    groups = position_groups(run_dir)
    by_group = {g["group"]: g for g in groups}
    assert set(by_group) == {"RB", "TA01"}
    assert by_group["RB"]["codes"] == ["RB01", "RB02"]
    assert by_group["TA01"]["codes"] == ["TA01"]

    rb = single_group_daily_series(run_dir, by_group["RB"]["codes"])
    ta = single_group_daily_series(run_dir, by_group["TA01"]["codes"])
    rb_close = {x["date"]: x for x in rb["close"]}
    ta_close = {x["date"]: x for x in ta["close"]}
    # RB group: RB01 + RB02 merged (gross/net/single on the pair).
    assert rb_close["2024-01-02"]["gross_pct"] == 20.0
    assert rb_close["2024-01-02"]["net_pct"] == 20.0
    assert rb_close["2024-01-03"]["net_pct"] == 10.0      # 0.2 - 0.1
    assert rb_close["2024-01-03"]["single_pct"] == 20.0   # max(0.2, |−0.1|)
    # TA is its own group (short day).
    assert ta_close["2024-01-02"]["gross_pct"] == 8.0
    assert ta_close["2024-01-02"]["net_pct"] == -8.0
    assert ta_close["2024-01-02"]["single_pct"] == 8.0
    # Portfolio level sums across groups independently.
    dp, _ = daily_position_and_risk(run_dir, {"RB": ["RB01", "RB02"]})
    close = {x["date"]: x for x in dp}
    assert close["2024-01-02"]["gross_pct"] == 28.0  # 0.1+0.1+0.08
    assert close["2024-01-02"]["net_pct"] == 12.0   # 0.2 - 0.08
    assert close["2024-01-02"]["single_pct"] == 28.0  # RB 0.2 + TA 0.08


def test_single_group_series_empty_when_positions_missing(tmp_path: Path) -> None:
    run_dir = write_run_dir(tmp_path, "20260818_000000_00_nosingle")
    assert position_groups(run_dir) == []
    assert single_group_daily_series(run_dir, ["AAA"]) == {"close": [], "peak": []}
