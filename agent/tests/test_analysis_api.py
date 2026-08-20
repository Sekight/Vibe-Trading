"""API tests for the new /runs/{id}/analysis routes."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

import api_server
from backtest.analysis.charts import generate_chart_artifacts

from tests._analysis_fixtures import write_run_dir


def _client(monkeypatch, tmp_path: Path) -> TestClient:
    runs_dir = tmp_path
    monkeypatch.setattr(api_server, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(api_server, "_API_KEY", "")
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_runs_list_orders_custom_ids_by_directory_mtime(tmp_path: Path, monkeypatch) -> None:
    old_run = write_run_dir(tmp_path, "old_custom_report")
    new_run = write_run_dir(tmp_path, "new_custom_report")
    os.utime(old_run, (1_000, 1_000))
    os.utime(new_run, (2_000, 2_000))
    client = _client(monkeypatch, tmp_path)

    response = client.get("/runs?limit=300")

    assert response.status_code == 200
    assert [item["run_id"] for item in response.json()[:2]] == [
        "new_custom_report",
        "old_custom_report",
    ]


def test_analysis_route_returns_markdown_and_status(tmp_path: Path, monkeypatch) -> None:
    run_dir = write_run_dir(tmp_path, "20260809_000000_00_api")
    (run_dir / "analysis.md").write_text("> generated_by: runner\n\n结论", encoding="utf-8")
    (run_dir / "analysis.status.json").write_text(
        '{"status": "ok", "generated_by": "runner", "generated_at": "now"}',
        encoding="utf-8",
    )
    client = _client(monkeypatch, tmp_path)

    response = client.get(f"/runs/{run_dir.name}/analysis")

    assert response.status_code == 200
    body = response.json()
    assert body["markdown"] == "> generated_by: runner\n\n结论"
    assert body["status"]["status"] == "ok"
    assert body["benchmark"]["label"] == "equal-weight(universe)"


def test_analysis_route_missing_files_returns_nulls(tmp_path: Path, monkeypatch) -> None:
    run_dir = write_run_dir(tmp_path, "20260809_111111_00_nofiles")
    client = _client(monkeypatch, tmp_path)

    response = client.get(f"/runs/{run_dir.name}/analysis")

    assert response.status_code == 200
    assert response.json()["markdown"] is None
    assert response.json()["status"] is None


def test_analysis_route_returns_benchmark_metadata(tmp_path: Path, monkeypatch) -> None:
    run_dir = write_run_dir(tmp_path, "20260811_000000_00_benchapi")
    card_path = run_dir / "run_card.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    card["metrics"]["benchmark_label"] = "000300.SH"
    card["metrics"]["benchmark_ticker"] = "000300.SH"
    card["metrics"]["benchmark_return"] = 0.03
    card_path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    client = _client(monkeypatch, tmp_path)

    response = client.get(f"/runs/{run_dir.name}/analysis")

    assert response.status_code == 200
    benchmark = response.json()["benchmark"]
    assert benchmark["label"] == "000300.SH"
    assert benchmark["ticker"] == "000300.SH"
    assert benchmark["return"] == 0.03


def test_analysis_charts_route_returns_payloads(tmp_path: Path, monkeypatch) -> None:
    run_dir = write_run_dir(tmp_path, "20260809_222222_00_charts")
    generate_chart_artifacts(run_dir)
    client = _client(monkeypatch, tmp_path)

    response = client.get(f"/runs/{run_dir.name}/analysis/charts")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert "equity_return" in body["charts"]
    assert "holding_buckets" in body["charts"]
    assert len(body["pngs"]) == 7
    assert body["benchmark_label"] == "equal-weight(universe)"


def test_analysis_charts_route_missing_metrics_is_unavailable(tmp_path: Path, monkeypatch) -> None:
    run_dir = write_run_dir(tmp_path, "20260809_333333_00_nometrics")
    (run_dir / "artifacts" / "metrics.csv").unlink()
    client = _client(monkeypatch, tmp_path)

    response = client.get(f"/runs/{run_dir.name}/analysis/charts")

    assert response.status_code == 200
    assert response.json()["available"] is False


def test_analysis_png_route_serves_file(tmp_path: Path, monkeypatch) -> None:
    run_dir = write_run_dir(tmp_path, "20260809_444444_00_png")
    generate_chart_artifacts(run_dir)
    client = _client(monkeypatch, tmp_path)

    response = client.get(f"/runs/{run_dir.name}/analysis/charts/equity_return.png")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert len(response.content) > 100


def test_analysis_routes_reject_invalid_run_id(tmp_path: Path, monkeypatch) -> None:
    client = _client(monkeypatch, tmp_path)

    for path in [
        "/runs/foo.bar/analysis",
        "/runs/foo%0A/analysis",
        "/runs/foo.bar/analysis/charts",
        "/runs/foo.bar/analysis/charts/equity_return.png",
    ]:
        response = client.get(path)
        assert response.status_code == 400, path
        assert response.json()["detail"] == "invalid run_id"


def test_analysis_png_route_rejects_invalid_chart_name(tmp_path: Path, monkeypatch) -> None:
    run_dir = write_run_dir(tmp_path, "20260809_555555_00_badname")
    client = _client(monkeypatch, tmp_path)

    response = client.get(f"/runs/{run_dir.name}/analysis/charts/foo.bar.png")

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid chart_name"


def test_analysis_route_returns_404_for_missing_run(tmp_path: Path, monkeypatch) -> None:
    client = _client(monkeypatch, tmp_path)

    response = client.get("/runs/20260809_999999_00_missing/analysis")

    assert response.status_code == 404
