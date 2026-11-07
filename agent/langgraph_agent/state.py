"""State schema and action vocabulary for the quant LangGraph prototype.

The state is deliberately flat and JSON-serializable: every node returns a
partial update, and LangGraph's checkpointer persists the whole dict after
each node. ``trace`` is the only append-only field (``operator.add``); every
other field is replaced wholesale by the node that owns it.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

# Subtask types accepted from the planner. Keep this list short: the point of
# the prototype is explicit decomposition, not a general-purpose tool router.
ACTION_TYPES: tuple[str, ...] = (
    "market_data",
    "backtest",
    "report",
    "clarify",
    "stop",
)

# User-visible action labels used by the evaluator and the API response.
ACTION_LABELS: dict[str, str] = {
    "market_data": "MARKET_DATA",
    "backtest": "BACKTEST",
    "report": "REPORT",
    "clarify": "CLARIFY",
    "stop": "STOP",
}

VALID_ACTIONS = frozenset(ACTION_LABELS.values())

# Tools that must exist in the registry for each subtask type.
ACTION_TO_TOOL: dict[str, str] = {
    "market_data": "market_data",
    "backtest": "backtest",
    "report": "report",
    "clarify": "clarify",
    "stop": "stop",
}


class Subtask(TypedDict, total=False):
    """One planned unit of work.

    Attributes:
        id: Stable id (``s1``, ``s2``...) assigned by ``decompose``.
        type: One of :data:`ACTION_TYPES`.
        reason: One-line rationale from the planner (for trace/UI only).
        params: Tool arguments (codes, dates, strategy, run_dir...).
        status: ``pending`` | ``done`` | ``skipped`` | ``downgraded`` | ``approved``.
    """

    id: str
    type: str
    reason: str
    params: dict[str, Any]
    status: str


class ActionRecord(TypedDict, total=False):
    """One executed subtask, as recorded by the ``execute`` node."""

    subtask_id: str
    action: str
    params: dict[str, Any]
    status: str
    summary: str
    run_dir: str


class AgentState(TypedDict, total=False):
    """Shared graph state.

    ``trace`` uses ``operator.add`` so nodes can append without clobbering
    each other. All other keys are whole-value replacements.
    """

    # Input
    question: str
    session_id: str
    profile: dict[str, Any]
    require_human_review: bool

    # Planning
    plan: list[str]
    subtasks: list[Subtask]
    confidence: float
    plan_source: str  # llm | llm_repair | rule

    # Execution
    cursor: int
    current_step: int
    max_steps: int
    current_subtask: dict[str, Any]
    completed: list[ActionRecord]
    reviewed: list[str]
    errors: list[dict[str, Any]]
    validation_failed: bool
    repair_attempted: bool
    force_fallback: bool
    last_run_dir: str

    # Result
    final_actions: list[str]
    final_text: str
    stopped_reason: str  # done | max_steps | validation_failed | llm_fallback

    # Accounting
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int

    # Observability
    trace: Annotated[list[dict[str, Any]], operator.add]


def initial_state(
    question: str,
    *,
    session_id: str = "",
    profile: dict[str, Any] | None = None,
    require_human_review: bool = False,
    max_steps: int = 3,
) -> AgentState:
    """Build a fully-initialized state for one graph invocation.

    Args:
        question: Raw user request.
        session_id: Optional caller session id (stored in state for the API).
        profile: Optional defaults such as ``{"source": "baostock"}``.
        require_human_review: Force the human gate before a backtest.
        max_steps: Hard cap on executed subtasks.

    Returns:
        Initial :class:`AgentState`.
    """
    return {
        "question": question,
        "session_id": session_id,
        "profile": dict(profile or {}),
        "require_human_review": require_human_review,
        "plan": [],
        "subtasks": [],
        "confidence": 1.0,
        "plan_source": "",
        "cursor": 0,
        "current_step": 0,
        "max_steps": max_steps,
        "current_subtask": {},
        "completed": [],
        "reviewed": [],
        "errors": [],
        "validation_failed": False,
        "repair_attempted": False,
        "force_fallback": False,
        "last_run_dir": "",
        "final_actions": [],
        "final_text": "",
        "stopped_reason": "",
        "llm_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "trace": [],
    }
