"""Tencent Finance loader: free, no-auth A-share data via HTTP API.

Uses Tencent's ifzq.gtimg.cn API which is not blocked by eastmoney's CDN.
Covers: A-shares (SH/SZ).  No API token required.

API format:
  https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh601595,day,2026-06-01,2026-06-13,500,qfq
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

import pandas as pd

from backtest.loaders.base import cached_loader_fetch, validate_date_range
from backtest.loaders.registry import register

logger = logging.getLogger(__name__)

_BASE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
_MAX_CHUNK_ROWS = 500


def _is_a_share(code: str) -> bool:
    return code.upper().endswith((".SZ", ".SH"))


@register
class DataLoader:
    """Tencent Finance A-share OHLCV loader (free, HTTP, no auth)."""

    name = "tencent"
    markets = {"a_share"}
    requires_auth = False

    def is_available(self) -> bool:
        """Always available — uses plain HTTP."""
        return True

    def __init__(self) -> None:
        pass

    def fetch(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        *,
        interval: str = "1D",
        fields: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        validate_date_range(start_date, end_date)
        del fields

        if interval.strip().lower() not in {"1d", "d", "day", "daily"}:
            logger.warning(
                "tencent supports daily bars only; rejecting interval=%s",
                interval,
            )
            return {}

        result: Dict[str, pd.DataFrame] = {}
        for code in codes:
            try:
                df = cached_loader_fetch(
                    source=self.name,
                    symbol=code,
                    timeframe=interval,
                    start_date=start_date,
                    end_date=end_date,
                    fields=None,
                    fetch=lambda code=code: self._fetch_one(code, start_date, end_date),
                )
                if df is not None and not df.empty:
                    result[code] = df
            except Exception as exc:
                logger.warning("tencent failed for %s: %s", code, exc)
        return result

    def _fetch_one(
        self, code: str, start_date: str, end_date: str,
    ) -> Optional[pd.DataFrame]:
        if not _is_a_share(code):
            return None

        parts = code.upper().split(".")
        symbol = parts[0]
        suffix = parts[1] if len(parts) > 1 else ""

        if suffix == "SH":
            tencent_code = f"sh{symbol}"
        elif suffix == "SZ":
            tencent_code = f"sz{symbol}"
        else:
            return None

        # The API caps a single request at _MAX_CHUNK_ROWS bars, so long ranges
        # are fetched in backward chunks: ask for the last 500 bars before a
        # cursor, then walk the cursor toward start_date until the range is
        # covered or the provider has no older rows.
        rows: List[dict] = []
        seen_dates: set = set()
        cursor_end = end_date
        for _ in range(80):
            url = (
                f"{_BASE_URL}?param={tencent_code},day,"
                f"{start_date},{cursor_end},{_MAX_CHUNK_ROWS},qfq"
            )

            import urllib.request
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://web.ifzq.gtimg.cn/",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")

            data = json.loads(raw)
            # Response: {"code":0,"data":{"sh601595":{"day":[["2026-06-01","21.32",...], ...]}}}
            stock_data = data.get("data", {})
            if not stock_data:
                break

            # Get the first (only) key
            stock_key = next(iter(stock_data), None)
            if not stock_key:
                break

            # Try "day" first, then "qfqday" (forward-adjusted)
            klines = stock_data[stock_key].get("qfqday") or stock_data[stock_key].get("day")
            if not klines:
                break

            chunk = []
            chunk_dates = []
            for k in klines:
                if len(k) >= 6:
                    d = k[0]
                    chunk_dates.append(d)
                    if d not in seen_dates:
                        seen_dates.add(d)
                        chunk.append({
                            "trade_date": d,
                            "open": float(k[1]),
                            "close": float(k[2]),
                            "high": float(k[3]),
                            "low": float(k[4]),
                            "volume": float(k[5]),
                        })
            if not chunk:
                break
            rows.extend(chunk)

            # A short chunk means the provider has no more rows in range.
            if len(chunk) < _MAX_CHUNK_ROWS or not chunk_dates:
                break
            earliest = min(chunk_dates)
            if earliest <= start_date:
                break
            next_end = (pd.Timestamp(earliest) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            if next_end < start_date:
                break
            cursor_end = next_end

        if not rows:
            return None

        df = pd.DataFrame(rows)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df.set_index("trade_date").sort_index()
        df = df[["open", "high", "low", "close", "volume"]].dropna(
            subset=["open", "high", "low", "close"]
        )
        return df
