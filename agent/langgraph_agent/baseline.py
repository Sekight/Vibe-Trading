"""Linear ReAct baseline used for the harness comparison.

This is the *same* model, tool set, and protocol text as the graph, but the
control flow is the project's original shape: one LLM call, execute the first
tool call, stop. All five actions are terminal in this protocol, so the linear
path can only land one action per user message. That structural limit is what
the multi-intent cases measure.
"""

from __future__ import annotations

import json
from typing import Any

from .prompts import build_linear_messages
from .tools import TOOL_TO_ACTION, build_action_registry


class LinearBaseline:
    """Minimal linear ReAct loop (one terminal action per turn).

    Attributes:
        llm: Chat client.
        registry: Five-tool registry.
        max_steps: Loop cap. All actions are terminal, so the first tool call
            ends the run; the cap guards a malformed model response.
    """

    def __init__(
        self,
        *,
        llm: Any | None = None,
        registry: Any | None = None,
        max_steps: int = 3,
    ) -> None:
        if llm is None:
            from src.providers.chat import ChatLLM

            llm = ChatLLM()
        self.llm = llm
        self.registry = registry or build_action_registry()
        self.max_steps = max_steps

    def run(
        self,
        question: str,
        *,
        profile: dict[str, Any] | None = None,
        session_id: str = "",
    ) -> dict[str, Any]:
        """Execute one linear decision.

        Args:
            question: User request.
            profile: Optional defaults.
            session_id: Stored in the response for API parity.

        Returns:
            ``actions``, ``steps``, ``llmCalls``, token counts, ``finalText``,
            and ``trace``.
        """
        messages = build_linear_messages(question, profile)
        actions: list[str] = []
        texts: list[str] = []
        trace: list[dict[str, Any]] = []
        steps = 0
        llm_calls = 0
        prompt_tokens = 0
        completion_tokens = 0

        for _ in range(max(1, self.max_steps)):
            response = self.llm.chat(
                messages,
                tools=self.registry.get_definitions(),
            )
            llm_calls += 1
            usage = getattr(response, "usage_metadata", None) or {}
            try:
                prompt_tokens += int(usage.get("input_tokens", 0))
                completion_tokens += int(usage.get("output_tokens", 0))
            except (TypeError, ValueError):
                pass

            tool_calls = list(getattr(response, "tool_calls", None) or [])
            if not tool_calls:
                text = str(getattr(response, "content", "") or "").strip()
                if text:
                    texts.append(text)
                actions.append("CLARIFY")
                trace.append({
                    "node": "linear",
                    "decision": "text_without_tool",
                    "text": text[:300],
                })
                break

            call = tool_calls[0]
            steps += 1
            params = getattr(call, "arguments", None) or {}
            raw = self.registry.execute(call.name, params)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"status": "error", "error": raw[:300]}
            action = str(data.get("action") or TOOL_TO_ACTION.get(call.name, "CLARIFY"))
            actions.append(action)
            text = str(data.get("summary") or data.get("text") or "").strip()
            if text:
                texts.append(text)
            trace.append({
                "node": "linear",
                "decision": "tool_call",
                "tool": call.name,
                "action": action,
                "status": data.get("status"),
            })
            # Every action is terminal in this protocol: a linear loop cannot
            # continue to a second intent in the same turn.
            break

        unique_actions = list(dict.fromkeys(actions)) or ["CLARIFY"]
        return {
            "actions": unique_actions,
            "steps": steps,
            "llmCalls": llm_calls,
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "finalText": "\n".join(dict.fromkeys(text for text in texts if text)),
            "interrupted": False,
            "trace": trace,
            "sessionId": session_id,
        }
