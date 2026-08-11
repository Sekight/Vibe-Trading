"""Build a deterministic analysis digest from a completed backtest run.

The digest is the single source of truth for both the LLM report prompt and
the chart payloads. It never reads raw OHLCV wholesale into the LLM prompt;
large series are summarized/capped here.
"""

from __future__ import annotations

import csv
import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import math

import pandas as pd

# Digest persistence is intentionally disabled (2026-08-11): the digest is
# always built on the fly from run artifacts. If very large runs need a JSON
# cache again, re-enable by uncommenting DIGEST_FILENAME / write_digest_json
# and restoring the file-read branch in load_digest below.
# DIGEST_FILENAME = "analysis.digest.json"


BUCKET_EDGES: List[tuple] = [
    (0, 3),
    (4, 7),
    (8, 15),
    (16, 30),
    (31, 60),
    (61, None),
]
BUCKET_LABELS = ["≤3天", "4-7天", "8-15天", "16-30天", "31-60天", ">60天"]


METRIC_GROUPS: List[tuple] = [
    ("性能", [
        "total_return", "annual_return", "final_value", "sharpe", "sortino",
        "calmar", "max_drawdown", "win_rate", "profit_factor",
        "profit_loss_ratio", "trade_count", "avg_holding_days",
        "max_consecutive_loss",
    ]),
    ("基准相对", [
        "benchmark_label", "benchmark_ticker", "benchmark_return",
        "benchmark_beta", "excess_return", "information_ratio",
        "tracking_error",
    ]),
    ("风险", [
        "risk_xray_annualized_vol", "risk_xray_avg_invested",
        "risk_xray_effective_n", "risk_xray_hhi", "risk_xray_max_drawdown",
        "beta_to_equal_weight", "monte_carlo_p_value_sharpe",
        "monte_carlo_p_value_max_dd", "monte_carlo_n_simulations",
    ]),
    ("仓位与换手", [
        # avg_position_weight / max_position_weight are deprecated (2026-08-11);
        # old runs keep those keys, new runs write the portfolio/single names.
        "avg_portfolio_weight", "max_portfolio_weight", "max_single_weight",
        "avg_turnover",
        "total_turnover", "rebalance_turnover_mean", "rebalance_turnover_max",
    ]),
    ("再平衡", ["rebalance_count"]),
]


METRIC_MEANINGS: Dict[str, str] = {
    # 性能
    "total_return": "累计总收益率", "annual_return": "年化收益率",
    "final_value": "期末账户价值", "sharpe": "夏普比率（单位风险的超额收益）",
    "sortino": "索提诺比率（仅以下行波动衡量风险）",
    "calmar": "卡玛比率（年化收益 / 最大回撤绝对值）",
    "max_drawdown": "策略净值最大回撤（实际资金曲线，含现金与交易成本）",
    "win_rate": "胜率（盈利交易占比）", "profit_factor": "盈亏因子（总盈利 / 总亏损）",
    "profit_loss_ratio": "平均盈亏比（按盈亏金额计算）",
    "trade_count": "成交笔数（完成回合的交易数）", "avg_holding_days": "平均持仓（交易日 / bar 数）",
    "max_consecutive_loss": "最大连续亏损笔数",
    # 基准相对
    "benchmark_label": "基准标签（本次对比基准的标识）",
    "benchmark_ticker": "基准标的代码", "benchmark_return": "基准区间收益率",
    "benchmark_beta": "对基准的 Beta（组合随基准波动的程度）",
    "excess_return": "超额收益（策略收益 - 基准收益）",
    "information_ratio": "信息比率（超额收益 / 跟踪误差）",
    "tracking_error": "跟踪误差（超额收益的波动）",
    # 风险
    "risk_xray_annualized_vol": "风险透视：年化波动率",
    "risk_xray_avg_invested": "风险透视：平均投入仓位",
    "risk_xray_effective_n": "风险透视：有效持仓数（分散度）",
    "risk_xray_hhi": "风险透视：HHI 集中度",
    "risk_xray_max_drawdown": "风险透视：平均持仓篮子最大回撤（权重归一化为满仓，不含现金与成本）",
    "beta_to_equal_weight": "相对等权组合的 Beta",
    "monte_carlo_p_value_sharpe": "蒙特卡洛：Sharpe 置换检验 p 值",
    "monte_carlo_p_value_max_dd": "蒙特卡洛：最大回撤置换检验 p 值",
    "monte_carlo_n_simulations": "蒙特卡洛：模拟次数",
    # 仓位与换手
    "avg_portfolio_weight": "平均组合仓位（全组合目标仓位均值）",
    "max_portfolio_weight": "最大组合仓位（全组合目标仓位峰值）",
    "max_single_weight": "单票最大目标仓位",
    "avg_turnover": "平均换手率", "total_turnover": "累计换手率",
    "rebalance_turnover_mean": "再平衡平均换手", "rebalance_turnover_max": "再平衡最大换手",
    # 再平衡
    "rebalance_count": "再平衡次数",
    # 旧字段（2026-08-11 弃用，旧 run 仍可能出现）
    "avg_position_weight": "平均组合仓位（旧字段名，已弃用）",
    "max_position_weight": "最大组合仓位（旧字段名，已弃用）",
}


def _metric_meaning(key: str) -> str:
    """Return a concise Chinese explanation for a metric key."""
    return METRIC_MEANINGS.get(key, "自定义/派生指标，按字段名理解")


def _is_scalar_metric(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def group_metrics(metrics: Dict[str, Any]) -> List[tuple]:
    """Split scalar metrics into prompt groups; leftovers stay visible."""
    assigned: set = set()
    groups: List[tuple] = []
    for label, keys in METRIC_GROUPS:
        items = [(key, metrics[key]) for key in keys if key in metrics]
        if items:
            assigned.update(key for key, _ in items)
            groups.append((label, items))
    leftovers = [
        (key, value) for key, value in metrics.items()
        if key not in assigned and _is_scalar_metric(value)
    ]
    if leftovers:
        groups.append(("其他", leftovers))
    return groups


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    """Load a JSON file, returning None when missing or unreadable."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def load_csv(path: Path) -> List[Dict[str, Any]]:
    """Load a CSV file into row dicts, returning [] when missing/unreadable."""
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except Exception:
        return []


def _json_safe_digest(value: Any) -> Any:
    """Return a JSON-strict copy (non-finite floats become null)."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _json_safe_digest(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_digest(item) for item in value]
    return value


# def write_digest_json(run_dir: Path) -> Dict[str, Any]:
#     """Build and persist the deterministic analysis digest as JSON (disabled)."""
#     digest = build_digest(run_dir)
#     path = Path(run_dir) / DIGEST_FILENAME
#     path.write_text(
#         json.dumps(_json_safe_digest(digest), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
#         encoding="utf-8",
#     )
#     return digest


def load_digest(run_dir: Path) -> Dict[str, Any]:
    """Build the deterministic analysis digest on the fly from run artifacts."""
    # Persisted-file branch removed on purpose: digest is never written to
    # disk (see the commented-out persistence helpers above). Re-enable the
    # file read here if a JSON cache is brought back for large runs.
    # path = Path(run_dir) / DIGEST_FILENAME
    # if path.exists():
    #     try:
    #         loaded = json.loads(path.read_text(encoding="utf-8"))
    #         if isinstance(loaded, dict) and "equity" in loaded:
    #             return loaded
    #     except (OSError, ValueError):
    #         pass
    return build_digest(run_dir)


def _float(row: Dict[str, Any], key: str, default: Optional[float] = None) -> Optional[float]:
    """Best-effort float conversion of a CSV field."""
    value = row.get(key)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(row: Dict[str, Any], key: str, default: int = 0) -> int:
    value = _float(row, key, None)
    if value is None:
        return default
    return int(value)


def _date_prefix(value: Any) -> Optional[str]:
    """Normalize a timestamp to YYYY-MM-DD (or None)."""
    if value is None:
        return None
    text = str(value).strip()
    if len(text) >= 10:
        return text[:10]
    return None


def pair_trades(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pair entry/exit rows into round-trip trades using per-code FIFO.

    Entry rows carry ``pnl == 0`` and ``holding_days == 0``; exit rows carry
    the realized pnl. Buy entry -> long, sell entry -> short.
    """
    trades: List[Dict[str, Any]] = []
    open_queues: Dict[str, deque] = {}

    for row in rows:
        code = str(row.get("code") or "").strip()
        side = str(row.get("side") or "").strip().lower()
        if not code or side not in {"buy", "sell"}:
            continue
        pnl = _float(row, "pnl", 0.0) or 0.0
        holding_days = _int(row, "holding_days", 0)
        is_exit = abs(pnl) > 1e-9 or holding_days > 0
        if not is_exit:
            open_queues.setdefault(code, deque()).append(row)
            continue

        queue = open_queues.get(code)
        entry = queue.popleft() if queue else None
        direction = "long" if (entry or {}).get("side") == "buy" else "short"
        trades.append({
            "entry_ts": _date_prefix((entry or {}).get("timestamp")) or _date_prefix(row.get("timestamp")),
            "exit_ts": _date_prefix(row.get("timestamp")),
            "code": code,
            "direction": direction,
            "entry_price": _float(entry, "price") if entry else None,
            "exit_price": _float(row, "price"),
            "qty": _float(entry, "qty") if entry else None,
            "pnl": pnl,
            "return_pct": _float(row, "return_pct", 0.0) or 0.0,
            "holding_days": holding_days,
            "reason": str(row.get("reason") or ""),
            "win": pnl > 0,
        })
    return trades


def trade_summary(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate round-trip trades into headline stats."""
    count = len(trades)
    if count == 0:
        return {
            "count": 0, "wins": 0, "losses": 0, "total_pnl": 0.0,
            "avg_return_pct": 0.0, "win_rate": 0.0,
            "avg_holding_days": 0.0, "profit_loss_ratio": None,
        }
    wins = [t for t in trades if t["win"]]
    losses = [t for t in trades if not t["win"]]
    total_pnl = sum(t["pnl"] for t in trades)
    avg_return = sum(t["return_pct"] for t in trades) / count
    avg_holding = sum(t["holding_days"] for t in trades) / count
    profit_loss_ratio: Optional[float] = None
    if wins and losses:
        avg_win = sum(t["return_pct"] for t in wins) / len(wins)
        avg_loss = abs(sum(t["return_pct"] for t in losses) / len(losses))
        if avg_loss > 0:
            profit_loss_ratio = round(avg_win / avg_loss, 4)
    return {
        "count": count,
        "wins": len(wins),
        "losses": len(losses),
        "total_pnl": round(total_pnl, 4),
        "avg_return_pct": round(avg_return, 4),
        "win_rate": round(len(wins) / count, 4),
        "avg_holding_days": round(avg_holding, 2),
        "profit_loss_ratio": profit_loss_ratio,
    }


def monthly_pnl(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate realized pnl by exit year/month (closed-trade basis)."""
    grouped: Dict[str, Dict[str, Any]] = {}
    for trade in trades:
        exit_ts = trade.get("exit_ts") or ""
        if len(exit_ts) < 7:
            continue
        key = exit_ts[:7]
        try:
            year, month = int(key[:4]), int(key[5:7])
        except ValueError:
            continue
        bucket = grouped.setdefault(key, {"year": year, "month": month, "pnl": 0.0, "count": 0})
        bucket["pnl"] = round(bucket["pnl"] + trade["pnl"], 4)
        bucket["count"] += 1
    return [grouped[key] for key in sorted(grouped)]


def _bucket_for_holding(days: int) -> int:
    for index, (lo, hi) in enumerate(BUCKET_EDGES):
        if days >= lo and (hi is None or days <= hi):
            return index
    return len(BUCKET_EDGES) - 1


def holding_buckets(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fixed 6-bucket holding-period statistics (0 rows are never omitted)."""
    rows: List[Dict[str, Any]] = []
    for index, label in enumerate(BUCKET_LABELS):
        lo, hi = BUCKET_EDGES[index]
        bucket = [t for t in trades if (t["holding_days"] >= lo and (hi is None or t["holding_days"] <= hi))]
        count = len(bucket)
        wins = [t for t in bucket if t["win"]]
        losses = [t for t in bucket if not t["win"]]
        total_pnl = sum(t["pnl"] for t in bucket)
        avg_return = round(sum(t["return_pct"] for t in bucket) / count, 4) if count else 0.0
        win_rate = round(len(wins) / count, 4) if count else 0.0
        avg_profit_loss_ratio: Optional[float] = None
        if wins and losses:
            avg_win = sum(t["return_pct"] for t in wins) / len(wins)
            avg_loss = abs(sum(t["return_pct"] for t in losses) / len(losses))
            if avg_loss > 0:
                avg_profit_loss_ratio = round(avg_win / avg_loss, 4)
        rows.append({
            "bucket": label,
            "min_days": lo,
            "max_days": hi,
            "count": count,
            "total_pnl": round(total_pnl, 4),
            "avg_return_pct": avg_return,
            "win_rate": win_rate,
            "avg_profit_loss_ratio": avg_profit_loss_ratio,
        })
    return rows


def _load_ohlcv(run_dir: Path, code: str) -> Dict[str, Dict[str, float]]:
    """Load one symbol's OHLCV artifact as date -> ohlc dict."""
    safe_name = code.replace(":", "_").replace("/", "_").replace("\\", "_")
    path = run_dir / "artifacts" / f"ohlcv_{safe_name}.csv"
    rows = load_csv(path)
    bars: Dict[str, Dict[str, float]] = {}
    for row in rows:
        ts = _date_prefix(row.get("trade_date") or row.get("timestamp") or row.get("time"))
        if not ts:
            continue
        high = _float(row, "high")
        low = _float(row, "low")
        close = _float(row, "close")
        if high is None or low is None:
            continue
        bars[ts] = {"high": high, "low": low, "close": close}
    return bars


def add_mae_mfe(run_dir: Path, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Annotate trades with MAE/MFE percent magnitudes (entry day excluded).

    Daily bars cannot locate the entry timestamp inside the entry bar, so the
    entry bar is excluded to avoid look-ahead. Same-day round trips have no
    post-entry bars and get ``mae_pct=None`` / ``mfe_pct=None`` (N/A).
    """
    cache: Dict[str, Dict[str, Dict[str, float]]] = {}
    enriched: List[Dict[str, Any]] = []
    for trade in trades:
        code = trade["code"]
        entry_ts = trade.get("entry_ts")
        exit_ts = trade.get("exit_ts")
        entry_price = trade.get("entry_price")
        if not entry_ts or not exit_ts or entry_price is None:
            enriched.append({**trade, "mae_pct": None, "mfe_pct": None})
            continue
        bars = cache.setdefault(code, _load_ohlcv(run_dir, code))
        window = [
            bars[ts]
            for ts in bars
            if entry_ts < ts <= exit_ts
        ]
        if not window:
            enriched.append({**trade, "mae_pct": None, "mfe_pct": None})
            continue
        high_max = max(item["high"] for item in window)
        low_min = min(item["low"] for item in window)
        if trade["direction"] == "long":
            mae = max(0.0, (entry_price - low_min) / entry_price * 100.0)
            mfe = max(0.0, (high_max - entry_price) / entry_price * 100.0)
        else:
            mae = max(0.0, (high_max - entry_price) / entry_price * 100.0)
            mfe = max(0.0, (entry_price - low_min) / entry_price * 100.0)
        enriched.append({
            **trade,
            "mae_pct": round(mae, 4),
            "mfe_pct": round(mfe, 4),
        })
    return enriched


def ohlcv_summary(run_dir: Path) -> List[Dict[str, Any]]:
    """Per-symbol OHLCV coverage summary (counts only, never full bars)."""
    artifacts = run_dir / "artifacts"
    summary: List[Dict[str, Any]] = []
    if not artifacts.is_dir():
        return summary
    for path in sorted(artifacts.glob("ohlcv_*.csv")):
        code = path.stem.removeprefix("ohlcv_")
        rows = load_csv(path)
        dates = [_date_prefix(r.get("trade_date") or r.get("timestamp") or r.get("time")) for r in rows]
        dates = [d for d in dates if d]
        summary.append({
            "code": code,
            "rows": len(dates),
            "first_date": dates[0] if dates else None,
            "last_date": dates[-1] if dates else None,
        })
    return summary


def _load_close_prices(run_dir: Path) -> Dict[str, pd.Series]:
    """Load per-symbol close series from run OHLCV artifacts."""
    artifacts = run_dir / "artifacts"
    series: Dict[str, pd.Series] = {}
    if not artifacts.is_dir():
        return series
    for path in sorted(artifacts.glob("ohlcv_*.csv")):
        code = path.stem.removeprefix("ohlcv_")
        dates: List[str] = []
        closes: List[float] = []
        for row in load_csv(path):
            ts = _date_prefix(row.get("trade_date") or row.get("timestamp") or row.get("time"))
            close = _float(row, "close")
            if ts and close is not None and close > 0:
                dates.append(ts)
                closes.append(close)
        if len(dates) >= 2:
            series[code] = pd.Series(closes, index=pd.Index(dates, name="date"), dtype=float)
    return series


def _regime_from_run(run_dir: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a compact correlation-regime summary from run artifacts."""
    close_prices = _load_close_prices(run_dir)
    if len(close_prices) < 2:
        return {"skipped": "needs at least 2 assets with OHLCV artifacts"}
    items = [(code, close_prices[code].sort_index()) for code in sorted(close_prices)]
    aligned = pd.concat([series for _, series in items], axis=1).dropna()
    aligned.columns = [code for code, _ in items]
    returns = aligned.pct_change(fill_method=None).dropna()
    if len(returns) < 2:
        return {"skipped": "insufficient return observations"}
    try:
        from backtest.regime import compute_regime_analysis
        params = config.get("regime") or {}
        return compute_regime_analysis(returns, **params)
    except (ValueError, TypeError) as exc:
        return {"skipped": str(exc)}


def _regime_trade_summary(trades: List[Dict[str, Any]], fused_by_date: Dict[str, int]) -> Dict[str, Any]:
    """Aggregate round-trip trades by the entry date's FUSED state."""
    groups: Dict[str, List[Dict[str, Any]]] = {"fused": [], "defused": [], "unknown": []}
    for trade in trades:
        state = fused_by_date.get(str(trade.get("entry_ts") or ""))
        if state is None:
            groups["unknown"].append(trade)
        elif state:
            groups["fused"].append(trade)
        else:
            groups["defused"].append(trade)
    out: Dict[str, Any] = {}
    for label, items in groups.items():
        count = len(items)
        if count == 0:
            out[label] = {"count": 0, "pnl": 0.0, "win_rate": None}
            continue
        wins = sum(1 for trade in items if trade.get("win"))
        out[label] = {
            "count": count,
            "pnl": round(sum(trade.get("pnl") or 0.0 for trade in items), 4),
            "win_rate": round(wins / count, 4),
        }
    return out


def _metrics_from_run(run_dir: Path) -> Dict[str, Any]:
    rows = load_csv(run_dir / "artifacts" / "metrics.csv")
    if rows:
        parsed: Dict[str, Any] = {}
        for key, value in rows[0].items():
            if not key or value in ("", None):
                continue
            try:
                parsed[key] = int(float(value)) if key in {"trade_count", "max_consecutive_loss"} else float(value)
            except (TypeError, ValueError):
                parsed[key] = value
        return parsed
    card = load_json(run_dir / "run_card.json") or {}
    return dict(card.get("metrics") or {})


def build_digest(run_dir: Path) -> Dict[str, Any]:
    """Build the full deterministic analysis digest for a run directory."""
    run_dir = Path(run_dir)
    config = load_json(run_dir / "config.json") or {}
    run_card = load_json(run_dir / "run_card.json") or {}
    risk_xray = load_json(run_dir / "artifacts" / "risk_xray.json") or {}

    raw_trades = load_csv(run_dir / "artifacts" / "trades.csv")
    trades = add_mae_mfe(run_dir, pair_trades(raw_trades))
    trades_sorted = sorted(trades, key=lambda t: (t.get("entry_ts") or "", t.get("exit_ts") or ""))

    equity_rows = load_csv(run_dir / "artifacts" / "equity.csv")
    initial_cash = float(config.get("initial_cash") or 1_000_000.0)
    equity_curve: List[Dict[str, Any]] = []
    benchmark_peak: Optional[float] = None
    for row in equity_rows:
        ts = _date_prefix(row.get("timestamp") or row.get("time"))
        equity = _float(row, "equity")
        if not ts or equity is None:
            continue
        bench_equity = _float(row, "benchmark_equity")
        benchmark_cum_return_pct: Optional[float] = None
        benchmark_drawdown_pct: Optional[float] = None
        if bench_equity is not None:
            benchmark_cum_return_pct = round((bench_equity / initial_cash - 1.0) * 100.0, 4)
            benchmark_peak = bench_equity if benchmark_peak is None else max(benchmark_peak, bench_equity)
            if benchmark_peak:
                benchmark_drawdown_pct = round((bench_equity - benchmark_peak) / benchmark_peak * 100.0, 4)
        equity_curve.append({
            "date": ts,
            "cum_return_pct": round((equity / initial_cash - 1.0) * 100.0, 4),
            "drawdown_pct": round((_float(row, "drawdown", 0.0) or 0.0) * 100.0, 4),
            "benchmark_cum_return_pct": benchmark_cum_return_pct,
            "benchmark_drawdown_pct": benchmark_drawdown_pct,
        })

    metrics = _metrics_from_run(run_dir)
    summary = trade_summary(trades)
    mae_values = [t["mae_pct"] for t in trades if t.get("mae_pct") is not None]
    mfe_values = [t["mfe_pct"] for t in trades if t.get("mfe_pct") is not None]
    top_winners = sorted([t for t in trades if t["win"]], key=lambda t: t["pnl"], reverse=True)[:5]
    top_losers = sorted([t for t in trades if not t["win"]], key=lambda t: t["pnl"])[:5]
    validation = load_json(run_dir / "artifacts" / "validation.json") or {}

    regime = _regime_from_run(run_dir, config)
    if regime and not regime.get("skipped"):
        fused_by_date = dict(zip(regime.get("dates") or [], regime.get("fused") or []))
        regime["trade_summary"] = _regime_trade_summary(trades_sorted, fused_by_date)

    return {
        "run_id": run_dir.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            key: config.get(key)
            for key in ("codes", "start_date", "end_date", "interval", "source", "initial_cash", "engine", "commission", "benchmark")
            if key in config
        },
        "metrics": metrics,
        "risk_xray": risk_xray,
        "validation": validation,
        "equity": equity_curve,
        "trades": trades_sorted,
        "trade_summary": summary,
        "monthly_pnl": monthly_pnl(trades_sorted),
        "buckets": holding_buckets(trades_sorted),
        "mae_mfe_summary": {
            "with_data": len(mae_values),
            "avg_mae_pct": round(sum(mae_values) / len(mae_values), 4) if mae_values else None,
            "avg_mfe_pct": round(sum(mfe_values) / len(mfe_values), 4) if mfe_values else None,
        },
        "top_winners": top_winners,
        "top_losers": top_losers,
        "ohlcv_summary": ohlcv_summary(run_dir),
        "reproducibility": run_card.get("reproducibility") or {},
        "regime": regime,
    }


def _markdown_cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def render_digest_for_llm(digest: Dict[str, Any], max_trades: int = 20) -> str:
    """Render the digest as a compact, token-capped Markdown prompt body."""
    config = digest.get("config") or {}
    metrics = digest.get("metrics") or {}
    summary = digest.get("trade_summary") or {}
    lines: List[str] = [
        "## 运行信息",
        f"- run_id: {digest.get('run_id', '')}",
        f"- 标的: {', '.join(config.get('codes') or []) or '-'}",
        f"- 区间: {config.get('start_date') or '-'} ~ {config.get('end_date') or '-'}",
        f"- 周期/数据源: {config.get('interval') or '-'} / {config.get('source') or '-'}",
        "",
        f"- 基准: {_markdown_cell(metrics.get('benchmark_label') or config.get('benchmark') or 'equal-weight(universe)')}",
        "",
        "## 指标解读（全量指标）",
    ]
    prompt_metrics = dict(metrics)
    risk_xray = digest.get("risk_xray") or {}
    corr = risk_xray.get("correlation") or {}
    if corr.get("beta_to_equal_weight") is not None:
        prompt_metrics["beta_to_equal_weight"] = corr["beta_to_equal_weight"]
    validation = digest.get("validation") or {}
    monte_carlo = validation.get("monte_carlo") or {}
    derived_values = {
        "monte_carlo_p_value_sharpe": monte_carlo.get("p_value_sharpe"),
        "monte_carlo_p_value_max_dd": monte_carlo.get("p_value_max_dd"),
        "monte_carlo_n_simulations": monte_carlo.get("n_simulations"),
    }
    for key, value in derived_values.items():
        if value is not None:
            prompt_metrics[key] = value
    groups = group_metrics(prompt_metrics)
    if not groups:
        lines.append("- 无指标数据")
    for label, items in groups:
        lines.extend(["", f"### {label}", "| 指标 | 含义 | 值 |", "|---|---|---|"])
        lines.extend(
            f"| {key} | {_metric_meaning(key)} | {_markdown_cell(value)} |"
            for key, value in items
        )

    lines.extend([
        "",
        "## 交易概览",
        f"- 笔数: {summary.get('count', 0)}，盈利 {summary.get('wins', 0)} / 亏损 {summary.get('losses', 0)}",
        f"- 总盈亏: {_markdown_cell(summary.get('total_pnl'))}",
        f"- 平均单笔收益率: {_markdown_cell(summary.get('avg_return_pct'))}%",
        f"- 胜率: {_markdown_cell(summary.get('win_rate'))}",
        f"- 平均盈亏比（按单笔收益率）: {_markdown_cell(summary.get('profit_loss_ratio'))}",
        f"- 平均持仓（自然日）: {_markdown_cell(summary.get('avg_holding_days'))} 天",
        "",
        "## 持仓分桶（按平仓记录）",
        "| 桶 | 笔数 | 合计盈亏 | 平均收益率% | 胜率 | 平均盈亏比 |",
        "|---|---|---|---|---|---|",
    ])
    for bucket in digest.get("buckets") or []:
        lines.append(
            f"| {bucket['bucket']} | {bucket['count']} | {_markdown_cell(bucket['total_pnl'])} "
            f"| {_markdown_cell(bucket['avg_return_pct'])} | {_markdown_cell(bucket['win_rate'])} "
            f"| {_markdown_cell(bucket['avg_profit_loss_ratio'])} |"
        )

    lines.extend(["", "## 月度损益（按平仓年月）", "| 年-月 | 盈亏 | 笔数 |", "|---|---|---|"])
    for item in (digest.get("monthly_pnl") or [])[:24]:
        lines.append(f"| {item['year']}-{item['month']:02d} | {_markdown_cell(item['pnl'])} | {item['count']} |")

    lines.extend(["", "## Top 盈利 / 亏损", "| 类型 | 平仓日 | 代码 | 方向 | 盈亏 | 收益率% | 持仓（自然日） |", "|---|---|---|---|---|---|---|"])
    for label, trades in (("盈利", digest.get("top_winners") or []), ("亏损", digest.get("top_losers") or [])):
        for trade in trades[:5]:
            lines.append(
                f"| {label} | {trade.get('exit_ts') or '-'} | {trade.get('code') or '-'} "
                f"| {trade.get('direction') or '-'} | {_markdown_cell(trade.get('pnl'))} "
                f"| {_markdown_cell(trade.get('return_pct'))} | {trade.get('holding_days')} |"
            )

    mae_mfe = digest.get("mae_mfe_summary") or {}
    lines.extend([
        "",
        "## MAE/MFE（日线近似，入场日不计）",
        f"- 有效样本: {mae_mfe.get('with_data', 0)}",
        f"- 平均 MAE: {_markdown_cell(mae_mfe.get('avg_mae_pct'))}%",
        f"- 平均 MFE: {_markdown_cell(mae_mfe.get('avg_mfe_pct'))}%",
    ])

    risk = digest.get("risk_xray") or {}
    if risk:
        drawdown = risk.get("drawdown") or {}
        vol = risk.get("volatility") or {}
        conc = risk.get("concentration") or {}
        lines.extend([
            "",
            "## 风险透视",
            f"- 最大回撤: {_markdown_cell(drawdown.get('max_drawdown'))}（{drawdown.get('max_drawdown_start', '-')} 起）",
            f"- 年化波动: {_markdown_cell(vol.get('annualized_vol'))}",
            f"- 有效持仓数: {_markdown_cell(conc.get('effective_n'))}",
            f"- HHI: {_markdown_cell(conc.get('hhi'))}",
        ])

    lines.extend(["", "## 行情覆盖", "| 代码 | 行数 | 区间 |", "|---|---|---|"])
    for item in (digest.get("ohlcv_summary") or [])[:20]:
        lines.append(
            f"| {item['code']} | {item['rows']} | {item.get('first_date') or '-'} ~ {item.get('last_date') or '-'} |"
        )

    regime = digest.get("regime") or {}
    lines.extend(["", "## Regime 摘要"])
    if regime.get("skipped"):
        lines.append(f"- 无数据: {regime['skipped']}")
    else:
        lines.append(f"- FUSED 时间占比: {_markdown_cell(regime.get('fused_pct'))}")
        lines.append(f"- FUSED 段数: {len(regime.get('episodes') or [])}")
        trade_regime = regime.get("trade_summary") or {}
        for label in ("fused", "defused", "unknown"):
            item = trade_regime.get(label) or {}
            lines.append(
                f"- {label}: {item.get('count', 0)} 笔 / 盈亏 {_markdown_cell(item.get('pnl'))} "
                f"/ 胜率 {_markdown_cell(item.get('win_rate'))}"
            )

    lines.append("")
    if len(digest.get("trades") or []) > max_trades:
        lines.append(f"> 完整交易明细共 {len(digest['trades'])} 笔，仅展示摘要；不要编造未提供的数字。")
    return "\n".join(lines)
