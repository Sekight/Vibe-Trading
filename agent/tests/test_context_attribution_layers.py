"""Tests for the post-backtest analysis contract in the system prompt."""

from __future__ import annotations

import builtins

import pytest

from backtest.loaders.registry import VALID_SOURCES
from src.agent.context import ContextBuilder


@pytest.mark.unit
class TestPostBacktestAnalysisPresence:
    """Verify the system prompt delegates analysis to write_run_analysis."""

    def test_system_prompt_instructs_write_run_analysis(self):
        from src.agent.context import _SYSTEM_PROMPT

        assert "write_run_analysis" in _SYSTEM_PROMPT
        assert "analysis.md" in _SYSTEM_PROMPT
        assert "analysis.status.json" in _SYSTEM_PROMPT

    def test_system_prompt_forbids_inline_attribution_duplication(self):
        from src.agent.context import _SYSTEM_PROMPT

        assert "do not repeat the full attribution analysis inline" in _SYSTEM_PROMPT

    def test_system_prompt_keeps_backtest_diagnose_reference(self):
        from src.agent.context import _SYSTEM_PROMPT

        assert 'load_skill("backtest-diagnose")' in _SYSTEM_PROMPT


@pytest.mark.unit
class TestPromptIntegrity:
    """Verify prompt formatting and structural integrity."""

    def test_system_prompt_format_succeeds(self):
        """Verify .format() with all required placeholders doesn't raise KeyError."""
        from src.agent.context import _SYSTEM_PROMPT

        result = _SYSTEM_PROMPT.format(
            tool_count=10,
            skill_count=5,
            data_source_count=18,
            tool_descriptions="[test tools]",
            skill_descriptions="[test skills]",
            memory_summary="[test memory]",
            memory_section="[test section]",
            current_datetime="2025-01-01 12:00:00",
        )
        assert len(result) > 1000
        # Ensure no unformatted placeholders remain
        # (JSON braces are OK, but single { } with names are not)
        assert "{tool_count}" not in result
        assert "{skill_count}" not in result
        assert "{data_source_count}" not in result

    def test_rationale_self_contained(self):
        """The prompt contract is documented inline, not via a gitignored docs/ path."""
        from pathlib import Path
        import src.agent.context as ctx_module

        source = Path(ctx_module.__file__).read_text(encoding="utf-8")
        # The write_run_analysis contract must be present and self-contained.
        assert "write_run_analysis" in source
        # The internal docs/ tree is gitignored and never published; the module
        # must not point at a file that won't exist in the distributed repo.
        assert "docs/" not in source


@pytest.mark.unit
class TestCountDataSources:
    """Regression tests for dynamic data-source count in the system prompt."""

    def test_count_data_sources_matches_registry(self) -> None:
        """Live count derives from VALID_SOURCES minus the auto selector."""
        assert ContextBuilder._count_data_sources() == len(VALID_SOURCES - {"auto"})

    def test_count_data_sources_import_failure_returns_18(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Import failures fall back to 18 without propagating."""
        real_import = builtins.__import__

        def failing_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: ANN001
            if name == "backtest.loaders.registry":
                raise ImportError("simulated registry import failure")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", failing_import)
        assert ContextBuilder._count_data_sources() == 18
