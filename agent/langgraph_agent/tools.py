"""Quant tool adapters for the LangGraph prototype.

The graph never talks to loaders/engines directly. It calls a small
``ToolRegistry`` built here, and each adapter is a thin wrapper around an
existing production tool:

* ``market_data`` -> ``src.tools.market_data_tool.MarketDataTool``
* ``backtest``    -> ``src.tools.backtest_tool.run_backtest``
* ``report``      -> ``src.tools.write_run_analysis_tool.WriteRunAnalysisTool``
* ``clarify`` / ``stop`` -> graph-local actions, no external side effects.

``live=False`` (the default) returns deterministic stub payloads so the 45-case
evaluation is fast, repeatable, and free. ``live=True`` is used only by the
single end-to-end demo and by manual acceptance.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from src.agent.tools import BaseTool, ToolRegistry

TOOL_TO_ACTION: dict[str, str] = {
    "market_data": "MARKET_DATA",
    "backtest": "BACKTEST",
    "report": "REPORT",
    "clarify": "CLARIFY",
    "stop": "STOP",
}

SIGNAL_ENGINE_SOURCE = '''"""P0-2 live demo: 20-day momentum, equal weight."""
import pandas as pd


class SignalEngine:
    def generate(self, data_map):
        n = max(len(data_map), 1)
        target = {}
        for code, df in data_map.items():
            mom = df["close"].pct_change(20)
            target[code] = (mom > 0).astype(float) / n
        return target
'''


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(part) for part in value]


def _first_date(record: dict[str, Any]) -> str:
    for key, value in record.items():
        if "date" in str(key).lower() or "time" in str(key).lower():
            return str(value)
    return ""


class MarketDataAdapter(BaseTool):
    """Fetch OHLCV (live) or return a deterministic summary (stub)."""

    name = "market_data"
    description = (
        "Fetch OHLCV bars for A-share symbols. Use for requests that only ask "
        "for price/volume data. Required: codes, start_date, end_date."
    )
    parameters = {
        "type": "object",
        "properties": {
            "codes": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string"},
            "end_date": {"type": "string"},
            "source": {"type": "string", "default": "baostock"},
            "interval": {"type": "string", "default": "1D"},
        },
        "required": ["codes", "start_date", "end_date"],
    }
    repeatable = True
    is_readonly = True

    def __init__(self, live: bool = False) -> None:
        self.live = live

    def execute(self, **kwargs: Any) -> str:
        codes = _as_list(kwargs.get("codes"))
        start = str(kwargs.get("start_date", ""))
        end = str(kwargs.get("end_date", ""))
        source = str(kwargs.get("source") or "baostock")
        interval = str(kwargs.get("interval") or "1D")
        if not codes or not start or not end:
            return _json({
                "status": "error",
                "action": "MARKET_DATA",
                "error": "codes/start_date/end_date are required",
            })
        if not self.live:
            return _json({
                "status": "ok",
                "action": "MARKET_DATA",
                "stub": True,
                "summary": f"{len(codes)} symbols, {start}..{end}, source={source}",
                "codes": codes,
                "start_date": start,
                "end_date": end,
                "source": source,
                "interval": interval,
            })
        try:
            from src.tools.market_data_tool import MarketDataTool

            raw = MarketDataTool().execute(
                codes=codes,
                start_date=start,
                end_date=end,
                source=source,
                interval=interval,
                max_rows=50,
            )
            data = json.loads(raw)
            summary = {}
            for symbol, payload in data.items():
                if symbol.startswith("_"):
                    continue
                # Production response shape: {symbol: {rows, returned, data: [...]}}.
                records = payload.get("data") if isinstance(payload, dict) else payload
                if isinstance(records, list) and records:
                    summary[symbol] = {
                        "rows": int(payload.get("rows", len(records)))
                        if isinstance(payload, dict)
                        else len(records),
                        "returned": int(payload.get("returned", len(records)))
                        if isinstance(payload, dict)
                        else len(records),
                        "first": _first_date(records[0]),
                        "last": _first_date(records[-1]),
                    }
            return _json({
                "status": "ok",
                "action": "MARKET_DATA",
                "summary": f"{len(summary)} symbols returned",
                "symbols": summary,
                "unresolved": data.get("_unresolved", []),
                "source": source,
            })
        except Exception as exc:  # noqa: BLE001 - tool boundary reports errors as JSON
            return _json({
                "status": "error",
                "action": "MARKET_DATA",
                "error": f"{type(exc).__name__}: {exc}",
            })


class BacktestAdapter(BaseTool):
    """Run a small momentum backtest (live) or return a stub summary."""

    name = "backtest"
    description = (
        "Run a strategy backtest on A-share symbols. Use only when the user "
        "explicitly asks to backtest a strategy. Required: codes, start_date, "
        "end_date; optional strategy (default: 20-day momentum)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "codes": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string"},
            "end_date": {"type": "string"},
            "strategy": {"type": "string", "default": "20-day momentum"},
            "source": {"type": "string", "default": "baostock"},
        },
        "required": ["codes", "start_date", "end_date"],
    }
    repeatable = False
    is_readonly = False

    def __init__(self, live: bool = False, run_root: Path | None = None) -> None:
        self.live = live
        self.run_root = run_root or (Path.home() / ".vibe-trading" / "runs")

    def execute(self, **kwargs: Any) -> str:
        codes = _as_list(kwargs.get("codes"))
        start = str(kwargs.get("start_date", ""))
        end = str(kwargs.get("end_date", ""))
        source = str(kwargs.get("source") or "baostock")
        strategy = str(kwargs.get("strategy") or "20-day momentum")
        if not codes or not start or not end:
            return _json({
                "status": "error",
                "action": "BACKTEST",
                "error": "codes/start_date/end_date are required",
            })
        if not self.live:
            return _json({
                "status": "ok",
                "action": "BACKTEST",
                "stub": True,
                "summary": f"stub backtest: {len(codes)} symbols, {start}..{end}, {strategy}",
                "metrics": {
                    "total_return": 0.12,
                    "sharpe": 0.8,
                    "max_drawdown": -0.1,
                    "trade_count": 12,
                },
                "run_dir": "",
            })
        try:
            run_dir = self._prepare_run_dir(codes, start, end, source, strategy)
            from src.tools.backtest_tool import run_backtest

            raw = run_backtest(str(run_dir), action="run", speed="fast")
            result = json.loads(raw)
            metrics = _read_metrics(run_dir)
            return _json({
                "status": result.get("status", "error"),
                "action": "BACKTEST",
                "summary": f"backtest {run_dir.name}: {metrics}",
                "run_dir": str(run_dir),
                "metrics": metrics,
                "artifacts": result.get("artifacts", {}),
                "error": result.get("error", ""),
            })
        except Exception as exc:  # noqa: BLE001 - tool boundary reports errors as JSON
            return _json({
                "status": "error",
                "action": "BACKTEST",
                "error": f"{type(exc).__name__}: {exc}",
            })

    def _prepare_run_dir(
        self,
        codes: list[str],
        start: str,
        end: str,
        source: str,
        strategy: str,
    ) -> Path:
        import os

        from src.config.accessor import reset_env_config

        self.run_root.mkdir(parents=True, exist_ok=True)
        # The Runner spawns generated code with a fresh HOME, so its child
        # process only sees run roots passed through this env var. Add our
        # real run root and reset the cached config so safe_run_dir accepts it
        # in both the parent and the child.
        run_root_text = str(self.run_root.resolve())
        configured = os.environ.get("VIBE_TRADING_ALLOWED_RUN_ROOTS", "")
        roots = [item.strip() for item in configured.split(",") if item.strip()]
        if run_root_text not in roots:
            roots.append(run_root_text)
        os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = ",".join(roots)
        reset_env_config()
        run_dir = self.run_root / f"p02_langgraph_bt_{int(time.time() * 1000)}"
        (run_dir / "code").mkdir(parents=True, exist_ok=True)
        config = {
            "source": source,
            "codes": codes,
            "start_date": start,
            "end_date": end,
            "interval": "1D",
            "engine": "daily",
            "entry_mode": "next_open",
            "exit_mode": "next_open",
            "initial_cash": 1_000_000,
            "commission_rate": 0.0003,
            "commission_min": 5.0,
            "slippage": 0.001,
            "strategy": strategy,
        }
        (run_dir / "config.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (run_dir / "code" / "signal_engine.py").write_text(
            SIGNAL_ENGINE_SOURCE, encoding="utf-8"
        )
        return run_dir


class ReportAdapter(BaseTool):
    """Generate a post-backtest analysis report (live) or a stub summary."""

    name = "report"
    description = (
        "Write an analysis report for a completed backtest run. Use when the "
        "user asks for a report/attribution/explanation of backtest metrics."
    )
    parameters = {
        "type": "object",
        "properties": {"run_dir": {"type": "string"}},
        "required": ["run_dir"],
    }
    repeatable = False
    is_readonly = False

    def __init__(self, live: bool = False) -> None:
        self.live = live

    def execute(self, **kwargs: Any) -> str:
        run_dir = str(kwargs.get("run_dir") or "")
        if not self.live:
            # Eval mode scores intent classification, not run lookup: a report
            # request is valid even when no prior run exists in this turn.
            return _json({
                "status": "ok",
                "action": "REPORT",
                "stub": True,
                "summary": f"stub report for {Path(run_dir).name or 'latest run'}",
                "report_path": "",
            })
        if not run_dir:
            return _json({
                "status": "error",
                "action": "REPORT",
                "error": "run_dir is required (run a backtest first)",
            })
        try:
            from src.tools.write_run_analysis_tool import WriteRunAnalysisTool

            raw = WriteRunAnalysisTool().execute(run_dir=run_dir)
            result = json.loads(raw)
            meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
            report_path = str(meta.get("path") or "")
            if not report_path:
                for key in ("analysis_path", "report_path", "path"):
                    if result.get(key):
                        report_path = str(result[key])
                        break
            if not report_path:
                candidate = Path(run_dir) / "analysis.md"
                if candidate.exists():
                    report_path = str(candidate)
            return _json({
                "status": result.get("status", "ok"),
                "action": "REPORT",
                "summary": f"report generated for {Path(run_dir).name}",
                "report_path": report_path,
            })
        except Exception as exc:  # noqa: BLE001 - tool boundary reports errors as JSON
            return _json({
                "status": "error",
                "action": "REPORT",
                "error": f"{type(exc).__name__}: {exc}",
            })


class ClarifyAction(BaseTool):
    """Ask the user for missing information (no external side effect)."""

    name = "clarify"
    description = (
        "Ask a clarifying question when the request is missing the symbol, "
        "date range, or strategy. Never guess missing parameters."
    )
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
    }
    repeatable = False
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        text = str(kwargs.get("text") or "").strip()
        return _json({
            "status": "ok",
            "action": "CLARIFY",
            "text": text
            or "请补充标的代码、起止日期和策略（或说明你要行情、回测还是报告）。",
        })


class StopAction(BaseTool):
    """End the turn with a short acknowledgement."""

    name = "stop"
    description = "End the turn for thanks/small-talk; no tool or data access."
    parameters = {
        "type": "object",
        "properties": {"reason": {"type": "string"}},
    }
    repeatable = False
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        return _json({
            "status": "ok",
            "action": "STOP",
            "text": "好的，先到这里，随时可以继续。",
            "reason": str(kwargs.get("reason") or ""),
        })


def build_action_registry(
    *,
    live: bool = False,
    run_root: Path | None = None,
) -> ToolRegistry:
    """Build the five-tool registry used by the graph and the baseline.

    Args:
        live: Use real production tools instead of deterministic stubs.
        run_root: Base directory for live backtest run dirs.

    Returns:
        A ``ToolRegistry`` with ``market_data``, ``backtest``, ``report``,
        ``clarify`` and ``stop``.
    """
    registry = ToolRegistry()
    registry.register(MarketDataAdapter(live=live))
    registry.register(BacktestAdapter(live=live, run_root=run_root))
    registry.register(ReportAdapter(live=live))
    registry.register(ClarifyAction())
    registry.register(StopAction())
    return registry


def _read_metrics(run_dir: Path) -> dict[str, Any]:
    """Read a compact metric subset from a completed run.

    Args:
        run_dir: Run directory that should contain ``artifacts/metrics.csv``.

    Returns:
        Metric dict; empty when the file is missing or unreadable.
    """
    metrics_path = run_dir / "artifacts" / "metrics.csv"
    if not metrics_path.exists():
        return {}
    try:
        import csv

        with metrics_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            return {}
        row = rows[0]
        keys = (
            "total_return",
            "annual_return",
            "sharpe",
            "max_drawdown",
            "trade_count",
        )
        out: dict[str, Any] = {}
        for key in keys:
            if key in row:
                try:
                    out[key] = float(row[key])
                except (TypeError, ValueError):
                    out[key] = row[key]
        return out
    except OSError:
        return {}
