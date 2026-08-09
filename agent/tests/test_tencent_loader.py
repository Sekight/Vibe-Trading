"""Tests for Tencent's daily-only market-data contract."""

from __future__ import annotations

import pandas as pd

from backtest.loaders import tencent_loader


def test_fetch_one_paginates_backward_to_cover_start_date(monkeypatch) -> None:
    import json
    import urllib.request
    from urllib.parse import parse_qs, urlparse

    calls: list[tuple[str, str]] = []

    class _FakeResp:
        def __init__(self, text: str) -> None:
            self._text = text

        def read(self) -> bytes:
            return self._text.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> bool:
            return False

    def fake_urlopen(req, timeout: int = 15):
        qs = parse_qs(urlparse(req.full_url).query)
        parts = qs["param"][0].split(",")
        start_s, end_s = parts[2], parts[3]
        calls.append((start_s, end_s))
        idx = pd.bdate_range(start=start_s, end=end_s)[-500:]
        klines = [
            [d.strftime("%Y-%m-%d"), "10.0", "10.1", "10.2", "9.9", "1000"]
            for d in idx
        ]
        payload = {"code": 0, "data": {"sh600519": {"qfqday": klines}}}
        return _FakeResp(json.dumps(payload))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    loader = tencent_loader.DataLoader()
    df = loader._fetch_one("600519.SH", "2023-01-01", "2025-12-31")

    assert df is not None
    assert len(calls) >= 2
    assert df.index.min() <= pd.Timestamp("2023-01-05")
    assert df.index.max() == pd.Timestamp("2025-12-31")
    assert df.index.is_unique


def test_intraday_request_does_not_return_daily_bars(monkeypatch) -> None:
    calls: list[str] = []
    daily = pd.DataFrame(
        {
            "open": [10.0],
            "high": [11.0],
            "low": [9.0],
            "close": [10.5],
            "volume": [100.0],
        },
        index=pd.DatetimeIndex([pd.Timestamp("2026-01-05")]),
    )
    loader = tencent_loader.DataLoader()
    monkeypatch.setattr(
        tencent_loader,
        "cached_loader_fetch",
        lambda **kwargs: kwargs["fetch"](),
    )
    monkeypatch.setattr(
        loader,
        "_fetch_one",
        lambda code, start, end: calls.append(code) or daily,
    )

    result = loader.fetch(
        ["600519.SH"],
        "2026-01-01",
        "2026-01-31",
        interval="1m",
    )

    assert result == {}
    assert calls == []
