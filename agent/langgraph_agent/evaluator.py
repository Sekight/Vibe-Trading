"""Dataset loading, scoring, and comparison-report rendering."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

from .state import ACTION_TYPES, VALID_ACTIONS

HR_TERMS = ("简历", "岗位", "招聘", "SEND_RESUME", "RETENTION", "COMMAND_HR")


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    """Load a JSONL case file.

    Args:
        path: Path to ``cases.jsonl``.

    Returns:
        Parsed cases; blank lines are skipped.
    """
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def validate_cases(
    cases: list[dict[str, Any]],
    *,
    expected_total: int | None = None,
) -> list[str]:
    """Validate the case schema and domain guardrails.

    Args:
        cases: Parsed cases.
        expected_total: Optional exact count check.

    Returns:
        Error strings; empty means valid.
    """
    errors: list[str] = []
    seen: set[str] = set()
    single = 0
    multi = 0
    for index, case in enumerate(cases, start=1):
        case_id = str(case.get("id", "")).strip()
        if not case_id:
            errors.append(f"case #{index}: missing id")
        elif case_id in seen:
            errors.append(f"case {case_id}: duplicate id")
        seen.add(case_id)
        question = str(case.get("question", "")).strip()
        if not question:
            errors.append(f"case {case_id}: empty question")
        if any(term in question for term in HR_TERMS):
            errors.append(f"case {case_id}: HR term leaked into a quant corpus")
        actions = (case.get("expect") or {}).get("actions")
        if not isinstance(actions, list) or not actions:
            errors.append(f"case {case_id}: expect.actions must be a non-empty list")
            continue
        invalid = [action for action in actions if action not in VALID_ACTIONS]
        if invalid:
            errors.append(f"case {case_id}: invalid actions {invalid}")
        if len(actions) == 1:
            single += 1
        else:
            multi += 1
        # Multi-intent cases use a case category (multi_intent), not an action.
        if len(actions) == 1 and case.get("type") and case["type"] not in ACTION_TYPES:
            errors.append(f"case {case_id}: invalid type {case['type']}")
    if expected_total is not None and len(cases) != expected_total:
        errors.append(f"expected {expected_total} cases, found {len(cases)}")
    if single != 40 or multi != 5:
        errors.append(f"expected 40 single-intent + 5 multi-intent, found {single} + {multi}")
    return errors


def score_case(
    case: dict[str, Any],
    actions: list[str],
) -> dict[str, Any]:
    """Score one prediction against the expected action set.

    Args:
        case: Case dict.
        actions: Predicted action labels.

    Returns:
        ``{"pass", "recall", "expected", "actual"}``.
    """
    expected = list((case.get("expect") or {}).get("actions") or [])
    actual = list(dict.fromkeys(actions))
    expected_set = set(expected)
    actual_set = set(actual)
    recall = (
        len(expected_set & actual_set) / len(expected_set)
        if expected_set
        else 1.0
    )
    return {
        "pass": expected_set == actual_set,
        "recall": round(recall, 4),
        "expected": expected,
        "actual": actual,
    }


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return round(ordered[index], 2)


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-case results into comparable metrics.

    Args:
        results: Result rows produced by ``run_eval``.

    Returns:
        Metric dict with definitions implicit in the names and denominators
        recorded under ``denominators``.
    """
    single = [row for row in results if len(row.get("expected") or []) == 1]
    multi = [row for row in results if len(row.get("expected") or []) > 1]
    tokens = [
        int(row.get("promptTokens", 0)) + int(row.get("completionTokens", 0))
        for row in results
    ]
    latencies = [float(row.get("latencyMs", 0)) for row in results]
    illegal = sum(
        1
        for row in results
        if any(action not in VALID_ACTIONS for action in (row.get("actual") or []))
    )
    by_type: dict[str, dict[str, float]] = {}
    for row in results:
        key = str(row.get("type") or "unknown")
        bucket = by_type.setdefault(key, {"total": 0, "passed": 0})
        bucket["total"] += 1
        bucket["passed"] += 1 if row.get("pass") else 0
    for bucket in by_type.values():
        bucket["accuracy"] = round(bucket["passed"] / bucket["total"], 4) if bucket["total"] else 0.0

    return {
        "n_cases": len(results),
        "single_action_accuracy": round(
            sum(1 for row in single if row.get("pass")) / len(single), 4
        ) if single else 0.0,
        "multi_action_exact_match": round(
            sum(1 for row in multi if row.get("pass")) / len(multi), 4
        ) if multi else 0.0,
        "multi_action_recall": round(
            statistics.fmean(float(row.get("recall", 0)) for row in multi), 4
        ) if multi else 0.0,
        "illegal_action_rate": round(illegal / len(results), 4) if results else 0.0,
        "avg_steps": round(statistics.fmean(float(row.get("steps", 0)) for row in results), 3) if results else 0.0,
        "avg_llm_calls": round(statistics.fmean(float(row.get("llmCalls", 0)) for row in results), 3) if results else 0.0,
        "avg_tokens": round(statistics.fmean(tokens), 1) if tokens else 0.0,
        "p95_latency_ms": _p95(latencies),
        "denominators": {
            "single_action": len(single),
            "multi_action": len(multi),
            "all": len(results),
        },
        "by_type": by_type,
    }


def file_sha256(path: str | Path) -> str:
    """Return the hex sha256 of a file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def render_comparison(
    summaries: dict[str, dict[str, Any]],
    meta: dict[str, Any],
) -> str:
    """Render ``compare.md`` from two summaries.

    Args:
        summaries: ``{"graph": summary, "linear": summary}``.
        meta: Run metadata (model, provider, hashes, commit...).

    Returns:
        Markdown document.
    """
    order = ["linear", "graph"]
    available = [name for name in order if name in summaries]
    metrics = [
        ("single_action_accuracy", "单意图动作准确率"),
        ("multi_action_exact_match", "多意图动作集完全一致"),
        ("multi_action_recall", "多意图动作覆盖率"),
        ("illegal_action_rate", "枚举外动作率"),
        ("avg_steps", "平均执行步数"),
        ("avg_llm_calls", "平均 LLM 调用次数"),
        ("avg_tokens", "平均 Token"),
        ("p95_latency_ms", "P95 延迟（ms）"),
    ]
    lines = [
        "# P0-2 量化 Agent：线性 ReAct vs LangGraph 对比",
        "",
        f"> 生成时间：{meta.get('generated_at', '')}",
        f"> 模型：{meta.get('model', '')}；provider：{meta.get('provider', '')}；temperature：{meta.get('temperature', '')}",
        f"> 数据集：{meta.get('dataset', '')}（sha256 `{meta.get('dataset_sha256', '')[:16]}`）",
        f"> git：`{meta.get('git_commit', '')}`，dirty={meta.get('git_dirty', '')}",
        "",
        "## 指标",
        "",
        "| 指标 | " + " | ".join(available) + " |",
        "|---|" + "|".join("---:" for _ in available) + "|",
    ]
    for key, label in metrics:
        cells = []
        for name in available:
            summary = summaries[name]
            cells.append(_fmt(summary.get(key, "")))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "> 分母：单意图 "
        + " / ".join(
            f"{name}={summaries[name].get('denominators', {}).get('single_action', '?')}"
            for name in available
        )
        + "；多意图 "
        + " / ".join(
            f"{name}={summaries[name].get('denominators', {}).get('multi_action', '?')}"
            for name in available
        )
        + "。",
        "",
        "## 分类型准确率",
        "",
        "| 类型 | " + " | ".join(available) + " |",
        "|---|" + "|".join("---:" for _ in available) + "|",
    ]
    types = sorted({key for name in available for key in summaries[name].get("by_type", {})})
    for kind in types:
        cells = []
        for name in available:
            bucket = summaries[name].get("by_type", {}).get(kind, {})
            cells.append(
                f"{bucket.get('accuracy', 0):.4f} ({bucket.get('passed', 0)}/{bucket.get('total', 0)})"
            )
        lines.append(f"| {kind} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## 失败样本（最多 3 条/实现）",
        "",
    ]
    for name in available:
        failures = summaries[name].get("failures", [])[:3]
        lines.append(f"### {name}")
        lines.append("")
        if not failures:
            lines.append("无失败样本。")
            lines.append("")
            continue
        for row in failures:
            lines.append(
                f"- `{row.get('id')}` expected={row.get('expected')} actual={row.get('actual')} "
                f"| {row.get('question', '')[:120]}"
            )
        lines.append("")
    lines += [
        "## 诚实边界",
        "",
        "- 45 条为合成语料，单轮、单模型；不能外推线上准确率。",
        "- 评测模式使用 stub 工具（只记录动作，不真跑回测）；真实链路见 `live_demo.py`。",
        "- 单意图准确率不应期待状态图更高；状态图的证据点在多意图、可中断、可恢复、可观测。",
        "- 平均 Token 的差异部分来自输出契约：线性提示词携带 5 个工具 schema，状态图的 plan 提示词不携带工具 schema；这不是纯模型成本对比。",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI: render ``compare.md`` from two ``summary.json`` files."""
    parser = argparse.ArgumentParser(description="Render the P0-2 comparison report")
    parser.add_argument("--graph", required=True, help="graph summary.json")
    parser.add_argument("--linear", required=True, help="linear summary.json")
    parser.add_argument("--out", required=True, help="output compare.md")
    args = parser.parse_args(argv)

    graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    linear = json.loads(Path(args.linear).read_text(encoding="utf-8"))
    meta = graph.get("meta") or {}
    summaries = {
        "graph": {**graph.get("metrics", {}), "failures": graph.get("failures", [])},
        "linear": {**linear.get("metrics", {}), "failures": linear.get("failures", [])},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        render_comparison(summaries, meta), encoding="utf-8", newline="\n"
    )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
