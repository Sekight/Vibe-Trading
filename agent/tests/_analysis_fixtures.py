"""Shared synthetic-run helpers for analysis digest/chart/report tests."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def write_run_dir(root: Path, run_id: str = "20260808_000000_00_abc123") -> Path:
    """Create a minimal successful run directory under ``root``."""
    run_dir = root / run_id
    (run_dir / "code").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)

    config = {
        "codes": ["600097.SH"],
        "start_date": "2024-01-01",
        "end_date": "2024-03-31",
        "source": "tencent",
        "interval": "1D",
        "initial_cash": 1_000_000,
        "engine": "daily",
        "commission": 0.0003,
    }
    (run_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    run_card = {
        "schema_version": "1",
        "run_id": run_id,
        "reproducibility": {"config_hash": "cfg-abc", "strategy_hash": "strat-def"},
        "metrics": {
            "total_return": 0.05,
            "annual_return": 0.2,
            "max_drawdown": -0.1,
            "sharpe": 0.8,
            "trade_count": 2,
            "final_value": 1_050_000,
        },
    }
    (run_dir / "run_card.json").write_text(json.dumps(run_card, ensure_ascii=False), encoding="utf-8")

    (run_dir / "artifacts" / "metrics.csv").write_text(
        "total_return,annual_return,max_drawdown,sharpe,trade_count,final_value\n"
        "0.05,0.2,-0.1,0.8,2,1050000\n",
        encoding="utf-8",
    )
    (run_dir / "artifacts" / "trades.csv").write_text(
        "code,side,timestamp,price,qty,pnl,return_pct,holding_days,reason\n"
        "600097.SH,buy,2024-01-05,10,10000,0,0,0,entry\n"
        "600097.SH,sell,2024-01-20,11,10000,10000,10,11,exit\n"
        "600097.SH,buy,2024-02-01,11,10000,0,0,0,entry\n"
        "600097.SH,sell,2024-02-15,10.5,10000,-5000,-4.545,10,exit\n",
        encoding="utf-8",
    )
    (run_dir / "artifacts" / "equity.csv").write_text(
        "timestamp,equity,drawdown\n"
        "2024-01-05,1000000,0\n"
        "2024-01-20,1010000,-0.01\n"
        "2024-02-15,1050000,0\n",
        encoding="utf-8",
    )
    (run_dir / "artifacts" / "risk_xray.json").write_text(
        json.dumps({"exposure": {"max": 0.8}}),
        encoding="utf-8",
    )

    dates = pd.bdate_range("2024-01-02", "2024-03-29")
    rows = []
    for index, ts in enumerate(dates):
        base = 10.0 + (index % 5) * 0.4
        rows.append(
            {
                "trade_date": ts.strftime("%Y-%m-%d"),
                "open": round(base, 2),
                "high": round(base + 0.5, 2),
                "low": round(base - 0.5, 2),
                "close": round(base + 0.2, 2),
                "volume": 1_000_000,
            }
        )
    pd.DataFrame(rows).to_csv(
        run_dir / "artifacts" / "ohlcv_600097.SH.csv",
        index=False,
        encoding="utf-8",
    )
    return run_dir
