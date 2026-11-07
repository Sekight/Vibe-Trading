"""Real end-to-end demo: market data -> backtest -> report.

Unlike ``run_eval.py`` (stub tools for speed), this script calls the real
production tools. It is the acceptance proof that the quant chain actually
works, and the recording script for the interview demo.

Run with a working provider, e.g.::

    cd agent
    set LANGCHAIN_PROVIDER=deepseek
    set LANGCHAIN_MODEL_NAME=deepseek-chat
    ..\\.venv\\Scripts\\python.exe -m langgraph_agent.live_demo
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable

from .tools import BacktestAdapter, MarketDataAdapter, ReportAdapter


def _timed(label: str, call: Callable[[], str]) -> tuple[dict[str, Any], float]:
    """Run one tool call, parse its JSON, and print a one-line status.

    Args:
        label: Step label for the console.
        call: Zero-argument callable returning a JSON string.

    Returns:
        ``(parsed_payload, elapsed_seconds)``.
    """
    started = time.perf_counter()
    raw = call()
    elapsed = time.perf_counter() - started
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"status": "error", "error": raw[:500]}
    print(
        f"[{label}] {elapsed:.2f}s status={data.get('status')} "
        f"summary={str(data.get('summary', ''))[:160]}"
    )
    if data.get("error"):
        print(f"[{label}] error={str(data['error'])[:400]}")
    return data, round(elapsed, 2)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="P0-2 real quant chain demo")
    parser.add_argument("--symbols", default="600519.SH,000001.SZ")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--source", default="baostock")
    parser.add_argument("--strategy", default="20日动量")
    parser.add_argument(
        "--run-root",
        default=str(Path.home() / ".vibe-trading" / "runs"),
        help="Base directory for the live backtest run",
    )
    parser.add_argument("--skip-report", action="store_true")
    args = parser.parse_args(argv)

    codes = [part.strip() for part in args.symbols.split(",") if part.strip()]
    market = MarketDataAdapter(live=True)
    backtest = BacktestAdapter(live=True, run_root=Path(args.run_root))
    report = ReportAdapter(live=True)

    market_data, market_seconds = _timed(
        "market_data",
        lambda: market.execute(
            codes=codes,
            start_date=args.start,
            end_date=args.end,
            source=args.source,
            interval="1D",
        ),
    )
    backtest_data, backtest_seconds = _timed(
        "backtest",
        lambda: backtest.execute(
            codes=codes,
            start_date=args.start,
            end_date=args.end,
            strategy=args.strategy,
            source=args.source,
        ),
    )

    run_dir = str(backtest_data.get("run_dir") or "")
    report_data: dict[str, Any] = {"status": "skipped"}
    report_seconds = 0.0
    if not args.skip_report and backtest_data.get("status") == "ok" and run_dir:
        report_data, report_seconds = _timed(
            "report",
            lambda: report.execute(run_dir=run_dir),
        )

    summary = {
        "status": "ok"
        if market_data.get("status") == "ok" and backtest_data.get("status") == "ok"
        else "error",
        "symbols": codes,
        "range": [args.start, args.end],
        "source": args.source,
        "market_data": {
            "status": market_data.get("status"),
            "seconds": market_seconds,
            "summary": market_data.get("summary"),
        },
        "backtest": {
            "status": backtest_data.get("status"),
            "seconds": backtest_seconds,
            "run_dir": run_dir,
            "metrics": backtest_data.get("metrics", {}),
        },
        "report": {
            "status": report_data.get("status"),
            "seconds": report_seconds,
            "report_path": report_data.get("report_path", ""),
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
