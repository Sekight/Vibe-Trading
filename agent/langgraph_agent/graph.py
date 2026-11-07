"""StateGraph assembly and thin decide/resume helpers."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from .nodes import AgentDeps, after_validate, make_after_route, make_nodes
from .state import AgentState, initial_state
from .tools import build_action_registry


def _checkpointer(sqlite_path: str | Path | None):
    """Return a MemorySaver or a SqliteSaver.

    Args:
        sqlite_path: Optional SQLite file for cross-process resume. Requires
            the ``langgraph-checkpoint-sqlite`` optional dependency.

    Returns:
        A LangGraph checkpointer instance.
    """
    if not sqlite_path:
        return MemorySaver()
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError as exc:  # pragma: no cover - depends on optional package
        raise RuntimeError(
            "SqliteSaver requires langgraph-checkpoint-sqlite; install it with "
            "`pip install langgraph-checkpoint-sqlite` or run without --sqlite"
        ) from exc
    conn = sqlite3.connect(str(sqlite_path), check_same_thread=False)
    return SqliteSaver(conn)


def build_graph(
    *,
    llm: Any | None = None,
    registry: Any | None = None,
    checkpointer: Any | None = None,
    sqlite_path: str | Path | None = None,
    max_steps: int = 3,
    enable_review: bool = True,
):
    """Build and compile the state graph.

    Args:
        llm: Chat client; defaults to the project ``ChatLLM``.
        registry: Five-tool registry; defaults to stub adapters.
        checkpointer: Explicit checkpointer; overrides ``sqlite_path``.
        sqlite_path: SQLite checkpoint file for cross-process resume.
        max_steps: Hard cap on executed subtasks.
        enable_review: When False, skip the human gate (used by batch eval).

    Returns:
        A compiled LangGraph application.
    """
    if llm is None:
        from src.providers.chat import ChatLLM

        llm = ChatLLM()
    if registry is None:
        registry = build_action_registry()

    deps = AgentDeps(
        llm=llm,
        registry=registry,
        max_steps=max_steps,
        enable_review=enable_review,
    )
    nodes = make_nodes(deps)

    graph = StateGraph(AgentState)
    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.add_edge(START, "decode")
    graph.add_edge("decode", "plan")
    graph.add_edge("plan", "decompose")
    graph.add_edge("decompose", "route")
    graph.add_conditional_edges(
        "route",
        make_after_route(deps),
        {
            "validate": "validate",
            "human_review": "human_review",
            "execute": "execute",
        },
    )
    graph.add_edge("human_review", "execute")
    graph.add_edge("execute", "route")
    graph.add_conditional_edges(
        "validate",
        after_validate,
        {"plan": "plan", "fallback": "fallback", "summarize": "summarize"},
    )
    graph.add_edge("fallback", "summarize")
    graph.add_edge("summarize", END)

    saver = checkpointer if checkpointer is not None else _checkpointer(sqlite_path)
    return graph.compile(checkpointer=saver)


def thread_config(thread_id: str) -> dict[str, Any]:
    """Build the LangGraph config for one checkpoint thread."""
    return {"configurable": {"thread_id": thread_id}}


def decide(
    graph: Any,
    question: str,
    *,
    session_id: str = "",
    profile: dict[str, Any] | None = None,
    require_human_review: bool = False,
    thread_id: str | None = None,
    max_steps: int = 3,
) -> dict[str, Any]:
    """Run one decision from a fresh state.

    Args:
        graph: Compiled graph.
        question: User request.
        session_id: Optional caller session id.
        profile: Optional defaults.
        require_human_review: Force the human gate before a backtest.
        thread_id: Optional thread id; generated when omitted.
        max_steps: Hard cap on executed subtasks.

    Returns:
        Normalized response dict (see :func:`to_response`).
    """
    thread_id = thread_id or uuid.uuid4().hex
    state = initial_state(
        question,
        session_id=session_id,
        profile=profile,
        require_human_review=require_human_review,
        max_steps=max_steps,
    )
    result = graph.invoke(state, thread_config(thread_id))
    return to_response(result, thread_id)


def resume(
    graph: Any,
    thread_id: str,
    *,
    approved: bool,
    note: str = "",
) -> dict[str, Any]:
    """Resume an interrupted thread with an approval decision.

    Args:
        graph: Compiled graph.
        thread_id: Thread id returned by :func:`decide`.
        approved: Whether the pending high-cost action is approved.
        note: Optional reviewer note (used as the clarify text on rejection).

    Returns:
        Normalized response dict.
    """
    result = graph.invoke(
        Command(resume={"approved": bool(approved), "note": note}),
        thread_config(thread_id),
    )
    return to_response(result, thread_id)


def get_state_summary(graph: Any, thread_id: str) -> dict[str, Any]:
    """Return a compact snapshot of a thread.

    Args:
        graph: Compiled graph.
        thread_id: Checkpoint thread id.

    Returns:
        ``{"values", "next", "interrupts"}`` where interrupts are plain values.
    """
    snapshot = graph.get_state(thread_config(thread_id))
    interrupts = []
    for item in getattr(snapshot, "interrupts", None) or ():
        interrupts.append(getattr(item, "value", item))
    return {
        "values": snapshot.values,
        "next": list(snapshot.next),
        "interrupts": interrupts,
    }


def to_response(result: dict[str, Any], thread_id: str) -> dict[str, Any]:
    """Normalize a graph result into the API/eval response shape.

    Args:
        result: Raw graph invocation result.
        thread_id: Thread id used for the invocation.

    Returns:
        JSON-serializable response.
    """
    interrupts = result.get("__interrupt__") or []
    payload = None
    if interrupts:
        first = interrupts[0]
        payload = getattr(first, "value", first)
    return {
        "threadId": thread_id,
        "actions": list(result.get("final_actions") or []),
        "plan": list(result.get("plan") or []),
        "subtasks": list(result.get("subtasks") or []),
        "steps": int(result.get("current_step", 0)),
        "confidence": result.get("confidence"),
        "planSource": result.get("plan_source", ""),
        "finalText": result.get("final_text", ""),
        "stoppedReason": result.get("stopped_reason", ""),
        "errors": list(result.get("errors") or []),
        "interrupted": bool(interrupts),
        "interrupt": payload,
        "llmCalls": int(result.get("llm_calls", 0)),
        "promptTokens": int(result.get("prompt_tokens", 0)),
        "completionTokens": int(result.get("completion_tokens", 0)),
        "trace": list(result.get("trace") or []),
    }
