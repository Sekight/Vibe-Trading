"""Deterministic post-backtest analysis: digest, charts, and LLM report.

This package consumes a completed run directory (run_card.json, metrics.csv,
trades.csv, equity.csv, ohlcv_*.csv, risk_xray.json) and produces:

- ``analysis.md`` + ``analysis.status.json`` (LLM report, optional)
- ``analysis_charts/*.png`` (deterministic charts)
- chart-ready JSON payloads for the Web UI
"""

from backtest.analysis.digest import build_digest, pair_trades
from backtest.analysis.charts import (
    compute_chart_payload,
    generate_chart_artifacts,
)
from backtest.analysis.report import generate_analysis_report

__all__ = [
    "build_digest",
    "pair_trades",
    "compute_chart_payload",
    "generate_chart_artifacts",
    "generate_analysis_report",
]
