"""Node implementations for the quant LangGraph prototype."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from langgraph.types import interrupt

from .prompts import build_plan_messages
from .state import (
    ACTION_TO_TOOL,
    ACTION_TYPES,
    VALID_ACTIONS,
    AgentState,
)
from .tools import TOOL_TO_ACTION

_CODE_RE = re.compile(r"\b\d{6}\.(?:SH|SZ|BJ)\b", re.IGNORECASE)
_DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")
_YEAR_RE = re.compile(r"(20\d{2})\s*年")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass
class AgentDeps:
    """Dependencies bound into node closures.

    Attributes:
        llm: Any object with ``chat(messages, tools=None, timeout=None)``
            returning an object with ``content`` and ``usage_metadata``.
        registry: Tool registry with the five action tools.
        max_steps: Hard cap on executed subtasks.
        enable_review: When False, the human gate is skipped (used by eval).
    """

    llm: Any
    registry: Any
    max_steps: int = 3
    enable_review: bool = True


def _entry(node: str, **fields: Any) -> dict[str, Any]:
    """Build one trace record."""
    return {"ts": round(time.time(), 3), "node": node, **fields}


def _usage(resp: Any) -> tuple[int, int]:
    """Return (prompt_tokens, completion_tokens) from an LLM response."""
    usage = getattr(resp, "usage_metadata", None) or {}
    try:
        return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
    except (TypeError, ValueError):
        return 0, 0


def _extract_json(text: str) -> dict[str, Any]:
    """Parse a JSON object from a model response.

    Accepts a bare object or one wrapped in a Markdown code fence. Raises
    ``ValueError`` when no object can be parsed.
    """
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object found")
    data = json.loads(raw[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def _clamp_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.6
    return max(0.0, min(1.0, number))


def normalize_subtasks(raw: Any) -> list[dict[str, Any]]:
    """Normalize planner output into at most three valid subtasks.

    Rules: drop non-dict entries, drop unknown types, dedupe by type (keep the
    first), cap at three, assign stable ids, and force ``status=pending``.

    Args:
        raw: Value of the planner's ``subtasks`` field.

    Returns:
        Normalized subtask list (possibly empty).
    """
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type", "")).strip()
        if kind not in ACTION_TYPES or kind in seen:
            continue
        seen.add(kind)
        params = item.get("params")
        out.append({
            "id": f"s{len(out) + 1}",
            "type": kind,
            "reason": str(item.get("reason", ""))[:300],
            "params": params if isinstance(params, dict) else {},
            "status": "pending",
        })
        if len(out) >= 3:
            break
    return out


def _extract_codes(question: str) -> list[str]:
    return [code.upper() for code in _CODE_RE.findall(question)]


def _extract_dates(question: str) -> tuple[str, str]:
    explicit = _DATE_RE.findall(question)
    if len(explicit) >= 2:
        return explicit[0], explicit[1]
    years = _YEAR_RE.findall(question)
    if years:
        year = years[0]
        return f"{year}-01-01", f"{year}-12-31"
    return "", ""


def _strategy_from_text(question: str) -> str:
    if "双均线" in question or "均线" in question:
        return "双均线"
    if "动量" in question:
        return "20日动量"
    return "20日动量"


def _rule_plan(question: str) -> tuple[list[dict[str, Any]], list[str], str]:
    """Deterministic fallback used when the LLM fails twice.

    Args:
        question: Decoded user request.

    Returns:
        ``(subtasks, plan, confidence)``.
    """
    codes = _extract_codes(question)
    start, end = _extract_dates(question)
    strategy = _strategy_from_text(question)
    has_backtest = any(word in question for word in ("回测", "策略", "均线", "动量"))
    has_report = any(
        word in question for word in ("报告", "分析", "解释", "归因", "回撤", "夏普")
    )
    has_data = any(
        word in question for word in ("日线", "行情", "K线", "k线", "数据", "拉", "取", "下载")
    )
    has_stop = any(
        word in question for word in ("谢谢", "结束", "先这样", "再见", "不用了", "没别的事")
    )

    if has_stop and not (has_backtest or has_report or has_data):
        return (
            [{"id": "s1", "type": "stop", "reason": "结束语", "params": {}, "status": "pending"}],
            ["结束本轮对话"],
            0.9,
        )

    if has_backtest and (not codes or not start):
        return (
            [{
                "id": "s1",
                "type": "clarify",
                "reason": "回测缺少标的或日期",
                "params": {"text": "请补充标的代码和起止日期，我再跑回测。"},
                "status": "pending",
            }],
            ["补齐回测参数"],
            0.6,
        )

    subtasks: list[dict[str, Any]] = []
    plan: list[str] = []
    if has_data and not has_backtest and not has_report:
        subtasks.append({
            "id": "s1",
            "type": "market_data",
            "reason": "用户要行情数据",
            "params": {
                "codes": codes,
                "start_date": start,
                "end_date": end,
                "source": "baostock",
                "interval": "1D",
            },
            "status": "pending",
        })
        plan.append("拉取行情")
    if has_backtest:
        subtasks.append({
            "id": f"s{len(subtasks) + 1}",
            "type": "backtest",
            "reason": "用户要跑策略回测",
            "params": {
                "codes": codes,
                "start_date": start,
                "end_date": end,
                "strategy": strategy,
                "source": "baostock",
            },
            "status": "pending",
        })
        plan.append("跑策略回测")
    if has_report:
        subtasks.append({
            "id": f"s{len(subtasks) + 1}",
            "type": "report",
            "reason": "用户要回测报告",
            "params": {},
            "status": "pending",
        })
        plan.append("生成回测报告")

    if not subtasks:
        return (
            [{
                "id": "s1",
                "type": "clarify",
                "reason": "无法判断动作",
                "params": {"text": "请说明你要行情、回测还是报告，并补充标的和日期。"},
                "status": "pending",
            }],
            ["追问缺失信息"],
            0.5,
        )
    return subtasks[:3], plan[:3], 0.7


def _no_subtask_clarify() -> dict[str, Any]:
    return {
        "id": "s1",
        "type": "clarify",
        "reason": "规划结果为空",
        "params": {"text": "请补充标的代码、起止日期和策略（或说明你要行情、回测还是报告）。"},
        "status": "pending",
    }


def make_nodes(deps: AgentDeps) -> dict[str, Any]:
    """Create node callables bound to ``deps``.

    Args:
        deps: LLM, registry, step cap, and review switch.

    Returns:
        Mapping of node name to ``state -> partial update`` callable.
    """

    def decode(state: AgentState) -> dict[str, Any]:
        raw = str(state.get("question", ""))
        cleaned = raw.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = _CONTROL_RE.sub("", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        errors = list(state.get("errors", []))
        if len(cleaned) > 2000:
            errors.append({
                "node": "decode",
                "error": "input truncated",
                "original_length": len(cleaned),
            })
            cleaned = cleaned[:2000]
        return {
            "question": cleaned,
            "errors": errors,
            "trace": [_entry("decode", original_length=len(raw), kept_length=len(cleaned))],
        }

    def plan(state: AgentState) -> dict[str, Any]:
        question = state.get("question", "")
        profile = state.get("profile") or {}
        prior_errors = state.get("errors", [])
        repair_note = ""
        if state.get("repair_attempted") and prior_errors:
            last = prior_errors[-1]
            repair_note = str(last.get("error") or last)[:300]
        messages = build_plan_messages(question, profile, repair_note=repair_note)
        errors = list(prior_errors)
        llm_calls = int(state.get("llm_calls", 0))
        prompt_tokens = int(state.get("prompt_tokens", 0))
        completion_tokens = int(state.get("completion_tokens", 0))

        for attempt in (1, 2):
            try:
                resp = deps.llm.chat(messages)
                llm_calls += 1
                used_prompt, used_completion = _usage(resp)
                prompt_tokens += used_prompt
                completion_tokens += used_completion
                data = _extract_json(getattr(resp, "content", "") or "")
                subtasks = normalize_subtasks(data.get("subtasks"))
                if not subtasks:
                    raise ValueError("planner returned no valid subtasks")
                plan_lines = [str(item)[:200] for item in (data.get("plan") or [])][:3]
                if not plan_lines:
                    plan_lines = [str(item.get("reason", ""))[:200] for item in subtasks]
                confidence = _clamp_confidence(data.get("confidence", 0.8))
                source = "llm" if attempt == 1 else "llm_repair"
                reset = (
                    {"completed": [], "cursor": 0, "current_step": 0}
                    if state.get("repair_attempted")
                    else {}
                )
                return {
                    "plan": plan_lines,
                    "subtasks": subtasks,
                    "confidence": confidence,
                    "plan_source": source,
                    "errors": errors,
                    "llm_calls": llm_calls,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "validation_failed": False,
                    "force_fallback": False,
                    **reset,
                    "trace": [_entry(
                        "plan",
                        attempt=attempt,
                        source=source,
                        subtasks=[item["type"] for item in subtasks],
                        confidence=confidence,
                    )],
                }
            except Exception as exc:  # noqa: BLE001 - every failure path is explicit
                errors.append({
                    "node": "plan",
                    "attempt": attempt,
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                })
                messages = build_plan_messages(
                    question,
                    profile,
                    repair_note=f"{type(exc).__name__}: {exc}"[:300],
                )

        subtasks, plan_lines, confidence = _rule_plan(question)
        reset = (
            {"completed": [], "cursor": 0, "current_step": 0}
            if state.get("repair_attempted")
            else {}
        )
        return {
            "plan": plan_lines,
            "subtasks": subtasks,
            "confidence": confidence,
            "plan_source": "rule",
            "errors": errors,
            "llm_calls": llm_calls,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "validation_failed": False,
            "force_fallback": False,
            **reset,
            "trace": [_entry("plan", attempt="rule_fallback", source="rule")],
        }

    def decompose(state: AgentState) -> dict[str, Any]:
        subtasks = normalize_subtasks(state.get("subtasks"))
        errors = list(state.get("errors", []))
        if not subtasks:
            subtasks = [_no_subtask_clarify()]
            errors.append({"node": "decompose", "error": "no valid subtasks; clarified"})
        return {
            "subtasks": subtasks,
            "cursor": 0,
            "current_step": 0,
            "completed": [],
            "current_subtask": {},
            "errors": errors,
            "trace": [_entry("decompose", types=[item["type"] for item in subtasks])],
        }

    def route(state: AgentState) -> dict[str, Any]:
        subtasks = state.get("subtasks") or []
        cursor = int(state.get("cursor", 0))
        max_steps = int(state.get("max_steps", deps.max_steps))
        if cursor >= len(subtasks) or int(state.get("current_step", 0)) >= max_steps:
            return {
                "current_subtask": {},
                "trace": [_entry("route", decision="validate", cursor=cursor)],
            }
        return {
            "current_subtask": dict(subtasks[cursor]),
            "trace": [_entry(
                "route",
                decision="subtask",
                cursor=cursor,
                type=subtasks[cursor].get("type"),
            )],
        }

    def human_review(state: AgentState) -> dict[str, Any]:
        current = dict(state.get("current_subtask") or {})
        answer = interrupt({
            "question": str(state.get("question", ""))[:300],
            "action": "BACKTEST",
            "params": current.get("params", {}),
            "confidence": state.get("confidence", 1.0),
        })
        approved = bool(answer.get("approved")) if isinstance(answer, dict) else bool(answer)
        note = str(answer.get("note", "")) if isinstance(answer, dict) else ""
        reviewed = list(state.get("reviewed", []))
        if current.get("id"):
            reviewed.append(current["id"])

        if approved:
            return {
                "reviewed": reviewed,
                "current_subtask": {**current, "status": "approved"},
                "trace": [_entry("human_review", approved=True, subtask=current.get("id"))],
            }

        subtasks: list[dict[str, Any]] = []
        downgraded: dict[str, Any] = {}
        for item in state.get("subtasks", []):
            if item.get("id") == current.get("id"):
                item = dict(item)
                item["type"] = "clarify"
                item["status"] = "downgraded"
                item["reason"] = (str(item.get("reason", "")) + " [rejected:backtest→clarify]").strip()
                item["params"] = {
                    "text": note or "回测未获批准。请确认标的、日期和策略后我再执行。"
                }
                downgraded = item
            subtasks.append(item)
        return {
            "subtasks": subtasks,
            "current_subtask": downgraded,
            "reviewed": reviewed,
            "trace": [_entry("human_review", approved=False, subtask=current.get("id"))],
        }

    def execute(state: AgentState) -> dict[str, Any]:
        current = dict(state.get("current_subtask") or {})
        if not current:
            return {"trace": [_entry("execute", skipped="no current subtask")]}
        subtasks = [dict(item) for item in (state.get("subtasks") or [])]
        completed = list(state.get("completed") or [])
        cursor = int(state.get("cursor", 0))
        current_step = int(state.get("current_step", 0))
        errors = list(state.get("errors") or [])
        subtask_id = current.get("id", "")

        if subtask_id and any(rec.get("subtask_id") == subtask_id for rec in completed):
            return {
                "cursor": cursor + 1,
                "trace": [_entry("execute", skipped="duplicate", subtask=subtask_id)],
            }

        kind = str(current.get("type", ""))
        params = dict(current.get("params") or {})
        if kind == "report":
            run_dir = str(state.get("last_run_dir", ""))
            if run_dir:
                params["run_dir"] = run_dir
        tool_name = ACTION_TO_TOOL.get(kind)
        if tool_name:
            raw = deps.registry.execute(tool_name, params)
        else:
            raw = json.dumps({"status": "error", "error": f"unknown subtask type {kind}"})

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"status": "error", "error": raw[:300]}

        action = str(data.get("action") or TOOL_TO_ACTION.get(kind, "CLARIFY"))
        ok = data.get("status") == "ok"
        summary = str(data.get("summary") or data.get("text") or "")[:500]
        record = {
            "subtask_id": subtask_id,
            "action": action,
            "params": params,
            "status": "done" if ok else "error",
            "summary": summary,
            "run_dir": str(data.get("run_dir") or ""),
        }
        completed.append(record)
        for index, item in enumerate(subtasks):
            if item.get("id") == subtask_id:
                subtasks[index] = {**item, "status": "done" if ok else "error"}
        if not ok:
            errors.append({
                "node": "execute",
                "subtask": subtask_id,
                "error": str(data.get("error") or "tool returned error")[:300],
            })

        last_run_dir = str(state.get("last_run_dir", ""))
        if kind == "backtest" and data.get("run_dir"):
            last_run_dir = str(data["run_dir"])

        cursor += 1
        current_step += 1
        max_steps = int(state.get("max_steps", deps.max_steps))
        stopped_reason = str(state.get("stopped_reason", ""))
        if current_step >= max_steps and cursor < len(subtasks):
            stopped_reason = "max_steps"
            for index in range(cursor, len(subtasks)):
                subtasks[index] = {**subtasks[index], "status": "skipped"}
            errors.append({
                "node": "execute",
                "error": "max_steps reached",
                "skipped": len(subtasks) - cursor,
            })

        return {
            "completed": completed,
            "subtasks": subtasks,
            "cursor": cursor,
            "current_step": current_step,
            "last_run_dir": last_run_dir,
            "stopped_reason": stopped_reason,
            "errors": errors,
            "trace": [_entry(
                "execute",
                subtask=subtask_id,
                type=kind,
                action=action,
                status=record["status"],
                run_dir=record["run_dir"],
            )],
        }

    def validate(state: AgentState) -> dict[str, Any]:
        errors = list(state.get("errors") or [])
        validation_errors: list[dict[str, Any]] = []
        completed = state.get("completed") or []
        subtasks = state.get("subtasks") or []

        if state.get("stopped_reason") != "max_steps":
            done = {
                rec.get("subtask_id")
                for rec in completed
                if rec.get("status") == "done"
            }
            expected = {item.get("id") for item in subtasks}
            missing = expected - done
            if missing:
                validation_errors.append({
                    "node": "validate",
                    "error": "missing subtasks",
                    "ids": sorted(missing),
                })
        for rec in completed:
            if rec.get("action") not in VALID_ACTIONS:
                validation_errors.append({
                    "node": "validate",
                    "error": "action not in enum",
                    "action": rec.get("action"),
                })
            if rec.get("status") == "error":
                validation_errors.append({
                    "node": "validate",
                    "error": "tool failed",
                    "subtask_id": rec.get("subtask_id"),
                })

        if not validation_errors:
            return {
                "validation_failed": False,
                "force_fallback": False,
                "trace": [_entry("validate", status="pass")],
            }

        errors.extend(validation_errors)
        if not state.get("repair_attempted"):
            return {
                "errors": errors,
                "validation_failed": True,
                "repair_attempted": True,
                "trace": [_entry("validate", status="repair", errors=len(validation_errors))],
            }
        return {
            "errors": errors,
            "validation_failed": True,
            "force_fallback": True,
            "trace": [_entry("validate", status="fallback", errors=len(validation_errors))],
        }

    def fallback(state: AgentState) -> dict[str, Any]:
        return {
            "final_actions": ["CLARIFY"],
            "final_text": "这次请求我没能拆成可靠的动作。请补充标的、日期和策略，或换个说法。",
            "stopped_reason": "validation_failed",
            "trace": [_entry("fallback", errors=len(state.get("errors") or []))],
        }

    def summarize(state: AgentState) -> dict[str, Any]:
        completed = state.get("completed") or []
        actions: list[str] = []
        texts: list[str] = []
        for rec in completed:
            action = rec.get("action")
            if rec.get("status") == "done" and action in VALID_ACTIONS and action not in actions:
                actions.append(str(action))
            text = str(rec.get("summary") or "").strip()
            if text:
                texts.append(text)
        if not actions:
            actions = ["CLARIFY"]
            texts.append("请补充标的代码、起止日期和策略。")
        return {
            "final_actions": actions,
            "final_text": "\n".join(dict.fromkeys(texts)),
            "stopped_reason": state.get("stopped_reason") or "done",
            "trace": [_entry("summarize", actions=actions)],
        }

    return {
        "decode": decode,
        "plan": plan,
        "decompose": decompose,
        "route": route,
        "human_review": human_review,
        "execute": execute,
        "validate": validate,
        "fallback": fallback,
        "summarize": summarize,
    }


def make_after_route(deps: AgentDeps):
    """Create the conditional-edge function that follows ``route``."""

    def after_route(state: AgentState) -> str:
        if not state.get("current_subtask"):
            return "validate"
        current = state.get("current_subtask") or {}
        if deps.enable_review and current.get("type") == "backtest":
            needs_review = bool(state.get("require_human_review")) or float(
                state.get("confidence", 1.0)
            ) < 0.7
            reviewed = set(state.get("reviewed", []))
            if needs_review and current.get("id") not in reviewed:
                return "human_review"
        return "execute"

    return after_route


def after_validate(state: AgentState) -> str:
    """Route after validation: repair, fall back, or summarize."""
    if state.get("force_fallback"):
        return "fallback"
    if state.get("validation_failed"):
        return "plan"
    return "summarize"
