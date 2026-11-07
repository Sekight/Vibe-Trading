"""CLI for the 45-case quant evaluation (graph vs linear)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .baseline import LinearBaseline
from .evaluator import (
    file_sha256,
    load_cases,
    score_case,
    summarize,
    validate_cases,
)
from .graph import build_graph, decide
from .nodes import _extract_json
from .prompts import build_linear_messages, build_plan_messages, prompt_sha256
from .tools import build_action_registry

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
DEFAULT_CASES = PACKAGE_DIR / "eval" / "cases.jsonl"


class MockLLM:
    """Deterministic keyword stub for wiring tests and ``--mock`` smoke runs.

    Never use ``--mock`` numbers in the report: they measure the harness, not
    the model.
    """

    model_name = "mock"
    runtime_snapshot = None

    def chat(self, messages, tools=None, timeout=None):  # noqa: ANN001, ARG002
        from src.providers.chat import LLMResponse, ToolCallRequest

        question = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                question = str(message.get("content", ""))
                break
        subtasks = _mock_subtasks(question)
        if tools:
            first = subtasks[0]
            params = dict(first.get("params") or {})
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="mock-call",
                        name=str(first.get("type")),
                        arguments=params,
                    )
                ],
            )
        return LLMResponse(
            content=json.dumps({
                "plan": [item.get("reason", "") for item in subtasks],
                "subtasks": [
                    {"type": item["type"], "reason": item.get("reason", ""), "params": item.get("params", {})}
                    for item in subtasks
                ],
                "confidence": 0.9,
            }, ensure_ascii=False)
        )


def _mock_subtasks(question: str) -> list[dict[str, Any]]:
    from .nodes import _extract_codes, _extract_dates, _strategy_from_text

    codes = _extract_codes(question)
    start, end = _extract_dates(question)
    strategy = _strategy_from_text(question)
    has_backtest = any(word in question for word in ("回测", "策略", "均线", "动量"))
    has_report = any(word in question for word in ("报告", "分析", "解释", "归因", "回撤", "夏普"))
    has_data = any(word in question for word in ("日线", "行情", "K线", "k线", "数据", "拉", "取", "下载"))
    has_stop = any(word in question for word in ("谢谢", "结束", "先这样", "再见", "不用了", "没别的事"))

    if has_stop and not (has_backtest or has_report or has_data):
        return [{"type": "stop", "reason": "结束语", "params": {"reason": "thanks"}}]
    if has_backtest and (not codes or not start):
        return [{"type": "clarify", "reason": "回测缺少参数", "params": {"text": "请补充标的和日期。"}}]

    subtasks: list[dict[str, Any]] = []
    if has_data and not has_backtest and not has_report:
        subtasks.append({
            "type": "market_data",
            "reason": "拉取行情",
            "params": {"codes": codes, "start_date": start, "end_date": end, "source": "baostock"},
        })
    if has_backtest:
        subtasks.append({
            "type": "backtest",
            "reason": "跑回测",
            "params": {"codes": codes, "start_date": start, "end_date": end, "strategy": strategy, "source": "baostock"},
        })
    if has_report:
        subtasks.append({"type": "report", "reason": "生成报告", "params": {}})
    if not subtasks:
        subtasks.append({"type": "clarify", "reason": "无法判断动作", "params": {"text": "请说明要行情、回测还是报告。"}})
    return subtasks[:3]


def _git_meta() -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
        )
        return commit, dirty
    except OSError:
        return "", True


def _run_one(
    impl: str,
    case: dict[str, Any],
    *,
    graph: Any | None,
    baseline: LinearBaseline | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    if impl == "graph":
        response = decide(
            graph,
            case["question"],
            profile={"default_source": "baostock"},
            require_human_review=False,
            max_steps=3,
        )
        actions = response.get("actions") or []
        steps = response.get("steps", 0)
        llm_calls = response.get("llmCalls", 0)
        prompt_tokens = response.get("promptTokens", 0)
        completion_tokens = response.get("completionTokens", 0)
        final_text = response.get("finalText", "")
        stopped_reason = response.get("stoppedReason", "")
        errors = response.get("errors", [])
        trace = response.get("trace", [])
    else:
        response = baseline.run(case["question"])
        actions = response.get("actions") or []
        steps = response.get("steps", 0)
        llm_calls = response.get("llmCalls", 0)
        prompt_tokens = response.get("promptTokens", 0)
        completion_tokens = response.get("completionTokens", 0)
        final_text = response.get("finalText", "")
        stopped_reason = "done"
        errors = []
        trace = response.get("trace", [])
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    score = score_case(case, actions)
    return {
        "id": case.get("id"),
        "type": case.get("type"),
        "question": case.get("question"),
        "expected": score["expected"],
        "actual": score["actual"],
        "pass": score["pass"],
        "recall": score["recall"],
        "steps": steps,
        "llmCalls": llm_calls,
        "promptTokens": prompt_tokens,
        "completionTokens": completion_tokens,
        "latencyMs": latency_ms,
        "finalText": final_text,
        "stoppedReason": stopped_reason,
        "errors": errors,
        "trace": trace,
    }


def _build_llm(mock: bool):
    if mock:
        return MockLLM()
    from src.providers.chat import ChatLLM

    return ChatLLM()


def _check_llm(llm: Any) -> int:
    question = "拉一下 600519.SH 2024 年的日线，跑一个双均线回测，然后给我一份报告。"
    messages = build_plan_messages(question, {"default_source": "baostock"})
    started = time.perf_counter()
    response = llm.chat(messages)
    elapsed = time.perf_counter() - started
    content = getattr(response, "content", "") or ""
    try:
        data = _extract_json(content)
        types = [item.get("type") for item in data.get("subtasks", [])]
        invalid = [item for item in types if item not in {"market_data", "backtest", "report", "clarify", "stop"}]
        if invalid or not types:
            print(f"LLM JSON invalid: types={types}")
            return 1
        print(json.dumps({
            "status": "ok",
            "elapsed_s": round(elapsed, 2),
            "model": getattr(llm, "model_name", "unknown"),
            "provider": getattr(getattr(llm, "runtime_snapshot", None), "provider", ""),
            "subtasks": types,
            "confidence": data.get("confidence"),
            "usage": getattr(response, "usage_metadata", None),
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"LLM JSON parse failed after {elapsed:.2f}s: {type(exc).__name__}: {exc}")
        print(content[:800])
        return 1


def _print_summary(impl: str, summary: dict[str, Any]) -> None:
    print(
        f"{impl}: n={summary['n_cases']} "
        f"single={summary['single_action_accuracy']:.3f} "
        f"multi_exact={summary['multi_action_exact_match']:.3f} "
        f"multi_recall={summary['multi_action_recall']:.3f} "
        f"steps={summary['avg_steps']} tokens={summary['avg_tokens']} "
        f"p95={summary['p95_latency_ms']}ms"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P0-2 quant agent evaluation")
    parser.add_argument("--impl", choices=["graph", "linear"], default="graph")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--out", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--sqlite", default="", help="SQLite checkpoint path (graph only)")
    parser.add_argument("--live-tools", action="store_true", help="Use real tools (slow)")
    parser.add_argument("--check-data", action="store_true")
    parser.add_argument("--check-llm", action="store_true")
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    if args.check_data:
        errors = validate_cases(cases, expected_total=45)
        if errors:
            print("DATA INVALID")
            for error in errors:
                print(f"- {error}")
            return 1
        print(f"DATA OK: {len(cases)} cases (40 single + 5 multi)")
        return 0

    if not args.check_llm:
        errors = validate_cases(cases, expected_total=45)
        if errors:
            print("DATA INVALID")
            for error in errors:
                print(f"- {error}")
            return 1

    llm = _build_llm(args.mock)
    if args.check_llm:
        return _check_llm(llm)

    if args.limit:
        cases = cases[: args.limit]

    registry = build_action_registry(live=args.live_tools)
    graph = None
    baseline = None
    if args.impl == "graph":
        graph = build_graph(
            llm=llm,
            registry=registry,
            sqlite_path=args.sqlite or None,
            max_steps=3,
            enable_review=False,
        )
    else:
        baseline = LinearBaseline(llm=llm, registry=registry, max_steps=3)

    results = []
    for case in cases:
        row = _run_one(args.impl, case, graph=graph, baseline=baseline)
        results.append(row)
        status = "PASS" if row["pass"] else "FAIL"
        print(f"[{status}] {row['id']} expected={row['expected']} actual={row['actual']}")

    metrics = summarize(results)
    failures = [row for row in results if not row["pass"]]
    prompt = (
        prompt_sha256(build_plan_messages("probe", {"default_source": "baostock"}))
        if args.impl == "graph"
        else prompt_sha256(build_linear_messages("probe", {"default_source": "baostock"}))
    )
    commit, dirty = _git_meta()
    meta = {
        "impl": args.impl,
        "model": getattr(llm, "model_name", "unknown"),
        "provider": getattr(getattr(llm, "runtime_snapshot", None), "provider", ""),
        "temperature": os.getenv("LANGCHAIN_TEMPERATURE", "0.0"),
        "prompt_sha256": prompt,
        "dataset": Path(args.cases).name,
        "dataset_sha256": file_sha256(args.cases),
        "git_commit": commit,
        "git_dirty": dirty,
        "mock": bool(args.mock),
        "live_tools": bool(args.live_tools),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    out_dir = Path(args.out) if args.out else (
        PACKAGE_DIR / "runs" / f"{args.impl}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "results.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in results:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {"meta": meta, "metrics": metrics, "failures": failures}
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    _print_summary(args.impl, metrics)
    print(f"wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
