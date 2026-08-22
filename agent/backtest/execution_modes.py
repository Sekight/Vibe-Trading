"""Execution-mode validation shared by the runner and market engines."""

from __future__ import annotations

from typing import Final


NORMAL_EXECUTION_MODES: Final[frozenset[str]] = frozenset({"next_open", "close"})
STOP_LOSS_MODES: Final[frozenset[str]] = frozenset({"none", "hard"})
SUPPORTED_NORMAL_PAIRS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("next_open", "next_open"),
        ("close", "close"),
    }
)


def validate_execution_modes(
    entry_mode: str,
    exit_mode: str,
    stop_loss_mode: str = "none",
) -> None:
    """Validate the current three-field execution contract.

    ``exit_mode="stop"`` was the legacy overloaded spelling.  It is
    intentionally rejected so callers migrate to ``stop_loss_mode="hard"``
    instead of silently changing the meaning of an old run.
    """
    if exit_mode == "stop":
        raise ValueError(
            "legacy exit_mode='stop' is no longer supported; use "
            "exit_mode='close' plus stop_loss_mode='hard' and migrate the config"
        )
    if entry_mode not in NORMAL_EXECUTION_MODES:
        raise ValueError(
            f"unsupported entry_mode {entry_mode!r}; "
            "expected 'next_open' or 'close'"
        )
    if exit_mode not in NORMAL_EXECUTION_MODES:
        raise ValueError(
            f"unsupported exit_mode {exit_mode!r}; "
            "expected 'next_open' or 'close' (stop is now stop_loss_mode)"
        )
    if (entry_mode, exit_mode) not in SUPPORTED_NORMAL_PAIRS:
        raise ValueError(
            f"unsupported normal execution combination "
            f"{entry_mode}/{exit_mode}; supported combinations are "
            "next_open/next_open and close/close"
        )
    if stop_loss_mode not in STOP_LOSS_MODES:
        raise ValueError(
            f"unsupported stop_loss_mode {stop_loss_mode!r}; "
            "expected 'none' or 'hard'"
        )
