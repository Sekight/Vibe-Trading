"""Config-driven logical instrument groups for execution-code aliases.

The backtest still executes on the concrete codes in ``config["codes"]``.
``logical_groups`` only declares which execution codes represent one logical
instrument for metrics, risk views, and chart presentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


def clean_code(code: Any) -> str:
    """Return the artifact/runtime code, removing only a local prefix."""
    value = str(code or "").strip()
    if value.lower().startswith("local:"):
        return value.split(":", 1)[1].strip()
    return value


@dataclass(frozen=True)
class LogicalGroup:
    """One logical instrument and its concrete execution-code members."""

    logical_symbol: str
    display_name: str
    codes: tuple[str, ...]
    chart_code: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "logical_symbol": self.logical_symbol,
            "display_name": self.display_name,
            "codes": list(self.codes),
            "chart_code": self.chart_code,
        }


def parse_logical_groups(
    config: Mapping[str, Any] | None,
    available_codes: Iterable[str] | None = None,
) -> tuple[LogicalGroup, ...]:
    """Parse and validate config logical groups.

    Missing ``logical_groups`` is intentionally backward compatible: every
    available code becomes its own logical group. Codes are normalized only for
    matching, so callers can use either ``local:CODE`` or ``CODE`` in config.
    """
    config = config or {}
    raw_codes = list(available_codes if available_codes is not None else config.get("codes") or [])
    universe: list[str] = []
    seen_universe: set[str] = set()
    for raw_code in raw_codes:
        code = clean_code(raw_code)
        if not code:
            continue
        if code not in seen_universe:
            universe.append(code)
            seen_universe.add(code)

    raw_groups = config.get("logical_groups")
    if raw_groups is None:
        return tuple(
            LogicalGroup(code, code, (code,), code)
            for code in universe
        )
    if not isinstance(raw_groups, list):
        raise ValueError("logical_groups must be an array")

    # A UI reconstruction may have only artifacts and no usable top-level
    # codes. In that case the group members are the available universe; the
    # runner still validates against config["codes"] at its boundary.
    if not universe:
        for item in raw_groups:
            if isinstance(item, dict):
                for raw_code in item.get("codes") or []:
                    code = clean_code(raw_code)
                    if code and code not in seen_universe:
                        universe.append(code)
                        seen_universe.add(code)

    groups: list[LogicalGroup] = []
    assigned: dict[str, str] = {}
    logical_names: set[str] = set()
    for index, item in enumerate(raw_groups):
        if not isinstance(item, dict):
            raise ValueError(f"logical_groups[{index}] must be an object")
        logical_symbol = str(item.get("logical_symbol") or "").strip()
        if not logical_symbol:
            raise ValueError(f"logical_groups[{index}].logical_symbol is required")
        if logical_symbol in logical_names:
            raise ValueError(f"duplicate logical_symbol: {logical_symbol}")
        logical_names.add(logical_symbol)

        raw_members = item.get("codes")
        if not isinstance(raw_members, list) or not raw_members:
            raise ValueError(f"logical_groups[{index}].codes must be a non-empty array")
        members = tuple(clean_code(code) for code in raw_members)
        if any(not code for code in members):
            raise ValueError(f"logical_groups[{index}].codes contains an empty code")
        if len(set(members)) != len(members):
            raise ValueError(f"logical_groups[{index}].codes contains duplicates")

        unknown = [code for code in members if universe and code not in seen_universe]
        if unknown:
            raise ValueError(
                f"logical_groups[{index}] contains codes not present in config.codes: {unknown}"
            )
        for code in members:
            previous = assigned.get(code)
            if previous is not None:
                raise ValueError(
                    f"code {code!r} belongs to multiple logical_groups: {previous!r}, {logical_symbol!r}"
                )
            assigned[code] = logical_symbol

        chart_code = clean_code(item.get("chart_code") or members[0])
        if chart_code not in members:
            raise ValueError(
                f"logical_groups[{index}].chart_code must belong to its codes"
            )
        display_name = str(item.get("display_name") or logical_symbol).strip()
        groups.append(LogicalGroup(logical_symbol, display_name, members, chart_code))

    # Unlisted execution codes remain visible and analyzable as singleton
    # logical instruments, preserving the old behavior for partial configs.
    for code in universe:
        if code not in assigned:
            groups.append(LogicalGroup(code, code, (code,), code))
    return tuple(groups)


def groups_as_mapping(groups: Iterable[LogicalGroup]) -> dict[str, list[str]]:
    """Return the legacy group-name -> member-code shape for aggregation."""
    return {group.logical_symbol: list(group.codes) for group in groups}
