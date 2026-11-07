"""Graph and baseline behavior tests (no network, no real LLM)."""

from __future__ import annotations

import json
from typing import Any

from langgraph_agent.baseline import LinearBaseline
from langgraph_agent.graph import build_graph, decide, resume
from langgraph_agent.tools import build_action_registry

PARAMS: dict[str, dict[str, Any]] = {
    "market_data": {
        "codes": ["600519.SH"],
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "source": "baostock",
    },
    "backtest": {
        "codes": ["600519.SH"],
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "strategy": "双均线",
        "source": "baostock",
    },
    "report": {},
    "clarify": {"text": "请补充标的和日期。"},
    "stop": {"reason": "thanks"},
}


class ScriptedLLM:
    """Queue-backed chat client for graph tests."""

    model_name = "scripted"
    runtime_snapshot = None

    def __init__(
        self,
        plan_payloads: list[Any] | None = None,
        tool_calls: list[list[Any]] | None = None,
    ) -> None:
        self.plan_payloads = list(plan_payloads or [])
        self.tool_calls = list(tool_calls or [])

    def chat(self, messages, tools=None, timeout=None):  # noqa: ANN001, ARG002
        from src.providers.chat import LLMResponse

        if tools:
            calls = self.tool_calls.pop(0) if self.tool_calls else []
            return LLMResponse(content="", tool_calls=calls)
        payload = self.plan_payloads.pop(0)
        if isinstance(payload, Exception):
            raise payload
        if isinstance(payload, dict):
            return LLMResponse(content=json.dumps(payload, ensure_ascii=False))
        return LLMResponse(content=str(payload))


def make_plan(
    *types: str,
    confidence: float = 0.9,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    overrides = params or {}
    return {
        "plan": [f"执行 {kind}" for kind in types],
        "subtasks": [
            {
                "type": kind,
                "reason": kind,
                "params": overrides.get(kind, PARAMS.get(kind, {})),
            }
            for kind in types
        ],
        "confidence": confidence,
    }


def make_graph(llm: ScriptedLLM, *, enable_review: bool = False):
    return build_graph(
        llm=llm,
        registry=build_action_registry(),
        enable_review=enable_review,
        max_steps=3,
    )


def test_single_intent_market_data() -> None:
    graph = make_graph(ScriptedLLM([make_plan("market_data")]))
    response = decide(graph, "拉一下 600519.SH 2024 年的日线")
    assert response["interrupted"] is False
    assert response["actions"] == ["MARKET_DATA"]
    assert response["steps"] == 1
    assert response["planSource"] == "llm"
    nodes = {item.get("node") for item in response["trace"]}
    assert {"decode", "plan", "decompose", "route", "execute", "validate", "summarize"} <= nodes


def test_multi_intent_executes_all_subtasks() -> None:
    graph = make_graph(ScriptedLLM([make_plan("market_data", "backtest")]))
    response = decide(graph, "拉 600519.SH 2024 日线，然后跑 20 日均线回测")
    assert response["actions"] == ["MARKET_DATA", "BACKTEST"]
    assert response["steps"] == 2


def test_invalid_json_falls_back_to_rules() -> None:
    graph = make_graph(ScriptedLLM(["not json", "still not json"]))
    response = decide(graph, "帮我跑个回测")
    assert response["planSource"] == "rule"
    assert response["actions"] == ["CLARIFY"]


def test_low_confidence_interrupt_and_approve() -> None:
    graph = make_graph(
        ScriptedLLM([make_plan("backtest", confidence=0.5)]),
        enable_review=True,
    )
    first = decide(graph, "用 20 日均线回测 600519.SH 2024 年")
    assert first["interrupted"] is True
    assert first["actions"] == []
    assert first["interrupt"]["action"] == "BACKTEST"

    second = resume(graph, first["threadId"], approved=True)
    assert second["interrupted"] is False
    assert second["actions"] == ["BACKTEST"]


def test_low_confidence_reject_downgrades_to_clarify() -> None:
    graph = make_graph(
        ScriptedLLM([make_plan("backtest", confidence=0.5)]),
        enable_review=True,
    )
    first = decide(graph, "用 20 日均线回测 600519.SH 2024 年")
    second = resume(graph, first["threadId"], approved=False, note="参数不对，先别跑")
    assert second["actions"] == ["CLARIFY"]
    assert "参数不对" in second["finalText"]


def test_max_steps_stops_and_marks_remaining() -> None:
    graph = make_graph(
        ScriptedLLM([make_plan("market_data", "backtest", "report")])
    )
    response = decide(graph, "拉数据、跑回测、出报告", max_steps=1)
    assert response["actions"] == ["MARKET_DATA"]
    assert response["stoppedReason"] == "max_steps"


def test_threads_are_isolated() -> None:
    graph = make_graph(ScriptedLLM([
        make_plan("market_data"),
        make_plan("clarify"),
    ]))
    first = decide(graph, "拉一下 600519.SH 2024 日线")
    second = decide(graph, "帮我跑个回测")
    assert first["threadId"] != second["threadId"]
    assert first["actions"] == ["MARKET_DATA"]
    assert second["actions"] == ["CLARIFY"]


def test_report_subtask_after_backtest() -> None:
    graph = make_graph(ScriptedLLM([make_plan("backtest", "report")]))
    response = decide(graph, "跑 600519.SH 2024 回测，再给一份报告")
    assert response["actions"] == ["BACKTEST", "REPORT"]
    assert response["steps"] == 2


def test_baseline_can_only_land_one_action() -> None:
    from src.providers.chat import ToolCallRequest

    llm = ScriptedLLM(tool_calls=[[
        ToolCallRequest(id="call-1", name="backtest", arguments=PARAMS["backtest"]),
    ]])
    baseline = LinearBaseline(llm=llm, registry=build_action_registry())
    response = baseline.run("拉数据、跑回测、出报告")
    assert response["actions"] == ["BACKTEST"]
    assert response["steps"] == 1
