"""Standalone FastAPI demo for the LangGraph quant prototype.

Run with::

    cd agent
    ..\\.venv\\Scripts\\python.exe -m langgraph_agent.server --port 9200

The app is intentionally not mounted on the production ``api_server.py``: it is
a local, unauthenticated demo bound to 127.0.0.1. Do not expose it publicly.
"""

from __future__ import annotations

import argparse
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .graph import build_graph, decide, get_state_summary, resume
from .tools import build_action_registry


class DecideRequest(BaseModel):
    """Request body for ``POST /agent/decide``."""

    question: str = Field(..., min_length=1)
    sessionId: str | None = None
    requireHumanReview: bool = False
    maxSteps: int = Field(3, ge=1, le=10)


class ResumeRequest(BaseModel):
    """Request body for ``POST /agent/resume``."""

    threadId: str = Field(..., min_length=1)
    approved: bool
    note: str = ""


def create_app(
    *,
    live_tools: bool = False,
    sqlite_path: str | None = None,
) -> FastAPI:
    """Create the demo app.

    Args:
        live_tools: Use real market-data/backtest/report tools.
        sqlite_path: Optional SQLite checkpoint file for cross-process resume.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="P0-2 LangGraph Quant Agent",
        version="0.1.0",
        description="Offline prototype: state graph + planning + human-in-the-loop.",
    )
    graph = build_graph(
        registry=build_action_registry(live=live_tools),
        sqlite_path=sqlite_path,
        enable_review=True,
        max_steps=3,
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "live_tools": live_tools}

    @app.post("/agent/decide")
    def decide_endpoint(request: DecideRequest) -> dict[str, Any]:
        return decide(
            graph,
            request.question,
            session_id=request.sessionId or "",
            require_human_review=request.requireHumanReview,
            max_steps=request.maxSteps,
        )

    @app.post("/agent/resume")
    def resume_endpoint(request: ResumeRequest) -> dict[str, Any]:
        try:
            return resume(
                graph,
                request.threadId,
                approved=request.approved,
                note=request.note,
            )
        except Exception as exc:  # noqa: BLE001 - surface a readable 400
            raise HTTPException(
                status_code=400,
                detail=f"resume failed: {type(exc).__name__}: {exc}",
            ) from exc

    @app.get("/agent/state/{thread_id}")
    def state_endpoint(thread_id: str) -> dict[str, Any]:
        try:
            return get_state_summary(graph, thread_id)
        except Exception as exc:  # noqa: BLE001 - unknown thread is a 404
            raise HTTPException(
                status_code=404,
                detail=f"thread not found: {type(exc).__name__}: {exc}",
            ) from exc

    return app


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="P0-2 LangGraph demo server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9200)
    parser.add_argument("--sqlite", default="", help="SQLite checkpoint file")
    parser.add_argument("--live-tools", action="store_true")
    args = parser.parse_args(argv)

    import uvicorn

    app = create_app(live_tools=args.live_tools, sqlite_path=args.sqlite or None)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
