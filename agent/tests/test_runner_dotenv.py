"""Regression tests for direct-runner dotenv and loader-cache bootstrap."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import src.providers.llm as llm


def _probe_runner_environment(runtime_home: Path) -> dict[str, object]:
    """Import the runner in a clean process and report resolved cache config."""
    agent_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("VIBE_TRADING_DATA_CACHE", None)
    env.pop("VIBE_TRADING_DATA_CACHE_ROOT", None)
    env["VIBE_TRADING_HOME"] = str(runtime_home)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{agent_dir}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(agent_dir)
    )
    probe = (
        "import json\n"
        "import backtest.runner\n"
        "from backtest.loaders.base import loader_cache_enabled, loader_cache_root\n"
        "print(json.dumps({'enabled': loader_cache_enabled(), 'root': str(loader_cache_root())}))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=agent_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_runtime_env_path_defaults_to_user_home(monkeypatch) -> None:
    monkeypatch.delenv("VIBE_TRADING_HOME", raising=False)

    assert llm._runtime_env_path() == Path.home() / ".vibe-trading" / ".env"


def test_runner_loads_custom_runtime_dotenv_and_cache_root(tmp_path: Path) -> None:
    runtime_home = tmp_path / "runtime-home"
    cache_root = tmp_path / "custom-loader-cache"
    runtime_home.mkdir()
    (runtime_home / ".env").write_text(
        "VIBE_TRADING_DATA_CACHE=1\n"
        f'VIBE_TRADING_DATA_CACHE_ROOT="{cache_root.as_posix()}"\n',
        encoding="utf-8",
    )

    resolved = _probe_runner_environment(runtime_home)

    assert resolved["enabled"] is True
    assert Path(str(resolved["root"])) == cache_root


def test_runner_bootstrap_writes_and_hits_loader_cache(tmp_path: Path) -> None:
    runtime_home = tmp_path / "runtime-home"
    cache_root = tmp_path / "custom-loader-cache"
    runtime_home.mkdir()
    (runtime_home / ".env").write_text(
        "VIBE_TRADING_DATA_CACHE=1\n"
        f'VIBE_TRADING_DATA_CACHE_ROOT="{cache_root.as_posix()}"\n',
        encoding="utf-8",
    )

    agent_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("VIBE_TRADING_DATA_CACHE", None)
    env.pop("VIBE_TRADING_DATA_CACHE_ROOT", None)
    env["VIBE_TRADING_HOME"] = str(runtime_home)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{agent_dir}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(agent_dir)
    )
    probe = (
        "import json\n"
        "import pandas as pd\n"
        "import backtest.runner\n"
        "from backtest.loaders.base import cached_loader_fetch, loader_cache_enabled, loader_cache_root\n"
        "frame = pd.DataFrame({'open': [1.0], 'high': [1.0], 'low': [1.0], 'close': [1.0]}, index=pd.to_datetime(['2024-01-02']))\n"
        "calls = {'count': 0}\n"
        "def fetch():\n"
        "    calls['count'] += 1\n"
        "    return frame\n"
        "kwargs = {'source': 'local', 'symbol': 'CACHE_TEST', 'timeframe': '1D', 'start_date': '2024-01-01', 'end_date': '2024-01-02', 'fields': None}\n"
        "cached_loader_fetch(**kwargs, fetch=fetch)\n"
        "cached_loader_fetch(**kwargs, fetch=fetch)\n"
        "root = loader_cache_root()\n"
        "print(json.dumps({'enabled': loader_cache_enabled(), 'fetches': calls['count'], 'parquet_count': len(list(root.rglob('*.parquet')))}))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=agent_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    resolved = json.loads(result.stdout.strip().splitlines()[-1])

    assert resolved == {"enabled": True, "fetches": 1, "parquet_count": 1}
