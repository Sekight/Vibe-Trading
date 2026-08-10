"""Agent tool: generate and persist the LLM analysis report for a run.

Called by the agent after a successful ``backtest`` so the report is written
once, by the agent path. The direct runner path uses the same generator via
``python -m backtest.runner <run_dir> --with-analysis`` (single writer).
"""

from __future__ import annotations

import json
from pathlib import Path

from src.agent.tools import BaseTool
from src.tools.path_utils import safe_run_dir


class WriteRunAnalysisTool(BaseTool):
    """Generate analysis.md + analysis.status.json for a completed backtest."""

    name = "write_run_analysis"
    description = (
        "Generate and save the post-backtest analysis report (analysis.md + "
        "analysis.status.json) in the run directory. Call once after the "
        "backtest tool succeeds and run_card.json exists; do not repeat the "
        "full attribution analysis inline afterward."
    )
    parameters = {
        "type": "object",
        "properties": {
            "run_dir": {"type": "string", "description": "Path to the backtest run directory"},
        },
        "required": ["run_dir"],
    }
    repeatable = True
    is_readonly = False

    def execute(self, **kwargs: str) -> str:
        """Generate the report and return a JSON status envelope."""
        run_dir = safe_run_dir(kwargs["run_dir"])
        from backtest.analysis.report import generate_analysis_report  # noqa: PLC0415

        result = generate_analysis_report(Path(run_dir), generated_by="agent")
        return json.dumps(result, ensure_ascii=False)
