"""Unit tests for the LangGraph prototype state and corpus."""

from __future__ import annotations

from pathlib import Path

from langgraph_agent.evaluator import load_cases, validate_cases
from langgraph_agent.nodes import normalize_subtasks
from langgraph_agent.state import (
    ACTION_LABELS,
    ACTION_TYPES,
    VALID_ACTIONS,
    initial_state,
)


def test_initial_state_defaults() -> None:
    state = initial_state("拉 600519.SH 2024 日线")
    assert state["question"] == "拉 600519.SH 2024 日线"
    assert state["subtasks"] == []
    assert state["cursor"] == 0
    assert state["max_steps"] == 3
    assert state["final_actions"] == []
    assert state["trace"] == []
    assert state["require_human_review"] is False


def test_action_vocabulary_is_closed() -> None:
    assert set(ACTION_LABELS) == set(ACTION_TYPES)
    assert VALID_ACTIONS == {
        "MARKET_DATA",
        "BACKTEST",
        "REPORT",
        "CLARIFY",
        "STOP",
    }


def test_normalize_subtasks_dedupes_and_caps() -> None:
    raw = [
        {"type": "market_data", "params": {"codes": ["600519.SH"]}},
        {"type": "market_data", "params": {"codes": ["000001.SZ"]}},
        {"type": "backtest", "params": {}},
        {"type": "report", "params": {}},
        {"type": "stop", "params": {}},
        {"type": "unknown", "params": {}},
        "not-a-dict",
    ]
    subtasks = normalize_subtasks(raw)
    assert [item["type"] for item in subtasks] == [
        "market_data",
        "backtest",
        "report",
    ]
    assert [item["id"] for item in subtasks] == ["s1", "s2", "s3"]
    assert all(item["status"] == "pending" for item in subtasks)
    # First occurrence wins on a duplicate type.
    assert subtasks[0]["params"]["codes"] == ["600519.SH"]


def test_normalize_subtasks_accepts_empty() -> None:
    assert normalize_subtasks(None) == []
    assert normalize_subtasks([]) == []


def test_corpus_is_quant_native_and_complete() -> None:
    cases_path = Path(__file__).resolve().parents[1] / "langgraph_agent" / "eval" / "cases.jsonl"
    cases = load_cases(cases_path)
    assert len(cases) == 45
    errors = validate_cases(cases, expected_total=45)
    assert errors == []
    assert sum(1 for case in cases if len(case["expect"]["actions"]) == 1) == 40
    assert sum(1 for case in cases if len(case["expect"]["actions"]) > 1) == 5
    joined = " ".join(case["question"] for case in cases)
    for term in ("简历", "岗位", "招聘", "SEND_RESUME", "RETENTION"):
        assert term not in joined
