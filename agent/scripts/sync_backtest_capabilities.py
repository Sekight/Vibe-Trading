"""Synchronize the backtest capability registry into docs and the bridge skill.

Usage from the repository root::

    agent/.venv/Scripts/python.exe agent/scripts/sync_backtest_capabilities.py
    agent/.venv/Scripts/python.exe agent/scripts/sync_backtest_capabilities.py --check
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = REPO_ROOT / "agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from src.backtest_capabilities import sync_generated_files  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report generated-file drift without modifying files",
    )
    args = parser.parse_args()
    changed = sync_generated_files(REPO_ROOT, check=args.check)
    if changed:
        mode = "drift" if args.check else "updated"
        print(f"{mode}:" if args.check else "updated:")
        for path in changed:
            print(f"- {path.relative_to(REPO_ROOT)}")
        return 1 if args.check else 0
    print("generated files are in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
