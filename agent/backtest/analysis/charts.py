"""Deterministic analysis chart payloads and local PNG generation.

Chart payloads are computed from :func:`backtest.analysis.digest.build_digest`
so the Web UI (ECharts) and the saved PNGs always describe the same numbers.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from backtest.analysis.digest import load_digest

logger = logging.getLogger(__name__)

RED = "#dc2626"
GREEN = "#16a34a"
BLUE = "#2563eb"
ORANGE = "#f59e0b"

CHART_SPECS: List[Dict[str, str]] = [
    {"key": "equity_return", "filename": "equity_return.png", "title": "净值曲线（累计收益率 %）"},
    {"key": "drawdown", "filename": "drawdown.png", "title": "策略净值回撤瀑布图（水下曲线 %）"},
    {"key": "pnl_scatter", "filename": "pnl_scatter.png", "title": "单笔盈亏散点（红赚绿亏）"},
    {"key": "monthly_heatmap", "filename": "monthly_heatmap.png", "title": "月度损益热力图（红赚绿亏）"},
    {"key": "pnl_vs_holding", "filename": "pnl_vs_holding.png", "title": "盈亏 vs 持仓时长（自然日）"},
    {"key": "mae_mfe", "filename": "mae_mfe.png", "title": "MAE/MFE 散点（金标准图）"},
    {"key": "holding_buckets", "filename": "holding_buckets.png", "title": "持仓分桶盈亏与胜率（自然日）"},
]

CHART_KEYS = [spec["key"] for spec in CHART_SPECS]


def compute_chart_payload(digest: Dict[str, Any]) -> Dict[str, Any]:
    """Return chart-ready JSON payloads keyed by chart key."""
    trades = digest.get("trades") or []
    ordered = sorted(trades, key=lambda t: (t.get("entry_ts") or "", t.get("exit_ts") or ""))
    return {
        "equity_return": [
            {
                "date": point.get("date"),
                "value": point.get("cum_return_pct"),
                "benchmark": point.get("benchmark_cum_return_pct"),
            }
            for point in (digest.get("equity") or [])
            if point.get("date")
        ],
        "drawdown": [
            {
                "date": point.get("date"),
                "value": point.get("drawdown_pct"),
                "benchmark": point.get("benchmark_drawdown_pct"),
            }
            for point in (digest.get("equity") or [])
            if point.get("date")
        ],
        "pnl_scatter": [
            {
                "index": index + 1,
                "entry_ts": trade.get("entry_ts"),
                "code": trade.get("code"),
                "direction": trade.get("direction"),
                "return_pct": trade.get("return_pct"),
                "win": bool(trade.get("win")),
            }
            for index, trade in enumerate(ordered)
        ],
        "monthly_heatmap": [
            {"year": item.get("year"), "month": item.get("month"), "pnl": item.get("pnl"), "count": item.get("count")}
            for item in (digest.get("monthly_pnl") or [])
        ],
        "pnl_vs_holding": [
            {
                "holding_days": trade.get("holding_days"),
                "return_pct": trade.get("return_pct"),
                "pnl": trade.get("pnl"),
                "win": bool(trade.get("win")),
                "code": trade.get("code"),
            }
            for trade in ordered
        ],
        "mae_mfe": [
            {
                "entry_ts": trade.get("entry_ts"),
                "code": trade.get("code"),
                "mae_pct": trade.get("mae_pct"),
                "mfe_pct": trade.get("mfe_pct"),
                "win": bool(trade.get("win")),
            }
            for trade in ordered
            if trade.get("mae_pct") is not None and trade.get("mfe_pct") is not None
        ],
        "holding_buckets": list(digest.get("buckets") or []),
    }


def _setup_matplotlib() -> Any:
    """Import and configure matplotlib (lazy; raises ImportError if absent)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    try:
        plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
    except Exception:
        pass
    return plt


def _render_equity_return(plt: Any, payload: Dict[str, Any], path: Path) -> None:
    points = payload.get("equity_return") or []
    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
    if points:
        ax.plot([p["date"] for p in points], [p["value"] for p in points], color=BLUE, linewidth=1.4, label="策略")
        ax.axhline(0, color="#94a3b8", linewidth=0.8)
    benchmark_points = [p for p in points if p.get("benchmark") is not None]
    if benchmark_points:
        ax.plot(
            [p["date"] for p in benchmark_points],
            [p["benchmark"] for p in benchmark_points],
            color=ORANGE,
            linewidth=1.2,
            label="基准",
        )
    if points or benchmark_points:
        ax.legend(loc="best")
    ax.set_title("净值曲线（累计收益率 %）")
    ax.set_xlabel("日期")
    ax.set_ylabel("累计收益率 %")
    ax.grid(True, alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _render_drawdown(plt: Any, payload: Dict[str, Any], path: Path) -> None:
    points = payload.get("drawdown") or []
    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
    if points:
        ax.fill_between(
            [p["date"] for p in points],
            [p["value"] for p in points],
            0,
            color=RED,
            alpha=0.55,
            linewidth=0,
            label="策略",
        )
    benchmark_points = [p for p in points if p.get("benchmark") is not None]
    if benchmark_points:
        ax.plot(
            [p["date"] for p in benchmark_points],
            [p["benchmark"] for p in benchmark_points],
            color=ORANGE,
            linewidth=1.2,
            label="基准",
        )
    if points or benchmark_points:
        ax.legend(loc="best")
    ax.set_title("策略净值回撤瀑布图（水下曲线 %）")
    ax.set_xlabel("日期")
    ax.set_ylabel("距历史高点的回撤 %")
    ax.grid(True, alpha=0.25)
    ax.invert_yaxis()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _render_pnl_scatter(plt: Any, payload: Dict[str, Any], path: Path) -> None:
    points = payload.get("pnl_scatter") or []
    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
    if points:
        colors = [RED if p["win"] else GREEN for p in points]
        ax.scatter(
            [p["index"] for p in points],
            [p["return_pct"] for p in points],
            c=colors,
            s=28,
            alpha=0.85,
        )
    ax.axhline(0, color="#94a3b8", linewidth=0.8)
    ax.set_title("单笔盈亏散点（红=盈利，绿=亏损）")
    ax.set_xlabel("交易序号（按开仓时间排序）")
    ax.set_ylabel("单笔收益率 %")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _render_monthly_heatmap(plt: Any, payload: Dict[str, Any], path: Path) -> None:
    import numpy as np  # noqa: PLC0415
    from matplotlib.colors import TwoSlopeNorm  # noqa: PLC0415

    points = payload.get("monthly_heatmap") or []
    if not points:
        fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
        ax.text(0.5, 0.5, "无交易数据", ha="center", va="center")
        ax.set_axis_off()
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return

    years = sorted({p["year"] for p in points})
    months = list(range(1, 13))
    matrix = np.full((len(years), 12), float("nan"))
    for point in points:
        if point["year"] in years and 1 <= point["month"] <= 12:
            matrix[years.index(point["year"])][point["month"] - 1] = point["pnl"]

    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
    finite = matrix[~np.isnan(matrix)]
    vmax = max(abs(float(finite.max())) if len(finite) else 1.0, 1.0)
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    im = ax.imshow(matrix, cmap="RdYlGn", norm=norm, aspect="auto")
    ax.set_yticks(range(len(years)), labels=[str(year) for year in years])
    ax.set_xticks(range(12), labels=[str(m) for m in months])
    ax.set_xlabel("月份")
    ax.set_ylabel("年份")
    ax.set_title("月度损益热力图（红=盈利，绿=亏损）")
    fig.colorbar(im, ax=ax, label="盈亏")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _render_pnl_vs_holding(plt: Any, payload: Dict[str, Any], path: Path) -> None:
    points = payload.get("pnl_vs_holding") or []
    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
    if points:
        colors = [RED if p["win"] else GREEN for p in points]
        ax.scatter(
            [p["holding_days"] for p in points],
            [p["return_pct"] for p in points],
            c=colors,
            s=28,
            alpha=0.85,
        )
    ax.axhline(0, color="#94a3b8", linewidth=0.8)
    ax.set_title("盈亏 vs 持仓时长（自然日）（红=盈利，绿=亏损）")
    ax.set_xlabel("持仓时长（自然日）")
    ax.set_ylabel("单笔收益率 %")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _render_mae_mfe(plt: Any, payload: Dict[str, Any], path: Path) -> None:
    import numpy as np  # noqa: PLC0415

    points = payload.get("mae_mfe") or []
    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
    if points:
        colors = [RED if p["win"] else GREEN for p in points]
        ax.scatter(
            [p["mae_pct"] for p in points],
            [p["mfe_pct"] for p in points],
            c=colors,
            s=28,
            alpha=0.85,
        )
        all_values = [p["mae_pct"] for p in points] + [p["mfe_pct"] for p in points]
        upper = max(all_values) * 1.1 if all_values else 1.0
        diag = np.linspace(0, max(upper, 1.0), 100)
        ax.plot(diag, diag, linestyle="--", color="#64748b", linewidth=1.0)
    ax.set_title("MAE/MFE 散点（红=盈利，绿=亏损；虚线 y=x）")
    ax.set_xlabel("MAE 最大不利浮亏 %")
    ax.set_ylabel("MFE 最大有利浮盈 %")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _render_holding_buckets(plt: Any, payload: Dict[str, Any], path: Path) -> None:
    buckets = payload.get("holding_buckets") or []
    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
    labels = [b["bucket"] for b in buckets]
    if buckets:
        avg_returns = [b["avg_return_pct"] for b in buckets]
        win_rates = [b["win_rate"] * 100.0 for b in buckets]
        colors = [RED if value >= 0 else GREEN for value in avg_returns]
        x_positions = list(range(len(buckets)))
        ax.bar(x_positions, avg_returns, color=colors, alpha=0.85, label="平均单笔收益率 %")
        ax.set_ylabel("平均单笔收益率 %")
        ax.axhline(0, color="#94a3b8", linewidth=0.8)
        ax_twin = ax.twinx()
        ax_twin.plot(x_positions, win_rates, color=BLUE, marker="o", linewidth=1.4, label="胜率 %")
        ax_twin.set_ylabel("胜率 %")
        ax_twin.set_ylim(0, 105)
        ax.set_xticks(x_positions, labels)
        ax.set_xlabel("持仓天数分桶（自然日）")
        lines, line_labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax_twin.get_legend_handles_labels()
        ax.legend(lines + lines2, line_labels + labels2, loc="upper right")
    ax.set_title("持仓分桶：平均收益率与胜率（自然日）")
    ax.grid(True, alpha=0.25, axis="y")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def generate_pngs(run_dir: Path, payload: Dict[str, Any]) -> List[Dict[str, str]]:
    """Write analysis_charts/*.png for every chart. Returns saved file info.

    Missing matplotlib or a per-chart drawing failure is logged and skipped
    so deterministic chart data remains available to the Web UI regardless.
    """
    try:
        plt = _setup_matplotlib()
    except Exception as exc:  # pragma: no cover - environment-dependent
        logger.warning("matplotlib unavailable; skipping PNG generation: %s", exc)
        return []

    charts_dir = Path(run_dir) / "analysis_charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    saved: List[Dict[str, str]] = []
    renderers = {
        "equity_return": _render_equity_return,
        "drawdown": _render_drawdown,
        "pnl_scatter": _render_pnl_scatter,
        "monthly_heatmap": _render_monthly_heatmap,
        "pnl_vs_holding": _render_pnl_vs_holding,
        "mae_mfe": _render_mae_mfe,
        "holding_buckets": _render_holding_buckets,
    }
    for spec in CHART_SPECS:
        key = spec["key"]
        renderer = renderers.get(key)
        if renderer is None:
            continue
        out_path = charts_dir / spec["filename"]
        try:
            renderer(plt, payload, out_path)
        except Exception as exc:  # pragma: no cover - drawing is best-effort
            logger.warning("chart %s PNG failed: %s", key, exc)
            continue
        saved.append({"key": key, "filename": spec["filename"], "path": str(out_path)})
    return saved


def list_pngs(run_dir: Path) -> List[Dict[str, str]]:
    """List saved PNG metadata without regenerating anything."""
    charts_dir = Path(run_dir) / "analysis_charts"
    if not charts_dir.is_dir():
        return []
    return [
        {"key": path.stem, "filename": path.name, "path": str(path)}
        for path in sorted(charts_dir.glob("*.png"))
    ]


def generate_chart_artifacts(run_dir: Path) -> Dict[str, Any]:
    """Build chart payloads and generate PNGs for a completed run."""
    digest = load_digest(run_dir)
    payload = compute_chart_payload(digest)
    pngs = generate_pngs(run_dir, payload)
    return {"charts": payload, "pngs": pngs, "generated": bool(pngs)}
