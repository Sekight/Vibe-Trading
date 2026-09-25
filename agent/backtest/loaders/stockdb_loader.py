"""stockdb direct-connect loader: A-share daily/minute bars from the local stockdb service.

``source="stockdb"`` reads in real time over a socket from the local
``stockdb.exe`` service (default ``127.0.0.1:7899``). No intermediate files are
produced: no export snapshot, no loader cache — bars go straight into memory
(P-20260925-stockdb_direct_loader).

Setup:
  - ``stockdb.exe`` must be running;
  - ``VIBE_TRADING_STOCKDB_SDK_PATH`` → the stockdb ``pybao`` dir (holds
    ``stockdb.pyd`` + ``stock_sdk.py``; the .pyd is bound to a CPython version —
    measured working on 3.13);
  - optional ``VIBE_TRADING_STOCKDB_HOST`` / ``VIBE_TRADING_STOCKDB_PORT`` /
    ``VIBE_TRADING_STOCKDB_TIMEOUT`` (seconds; the SDK's 1s local default is too
    tight for large range queries — an oversized query silently returns empty).

Measured data coverage (2026-09-25): daily bars from 2011; 1m bars
2025-01-02 → last sync date. Full-market minute backtests are infeasible on any
source (~0.5B rows); minute runs are for pools of hundreds of symbols.

Key decisions (see the plan for rationale):
  - fq: config key ``stockdb_fq`` = ``"hfq"`` (default) / ``"qfq"`` / ``"none"``.
    Adjustment is applied in-loader from the 复权 factor table — verified
    bit-identical to the SDK's ``fq="hfq"`` path (same rounding as
    ``scripts/export_stockdb_ashare.py``) — and shared by the daily and minute
    paths. The SDK's ``get_data(frequency="1m")`` path is not used (measured
    empty at its default 1s socket timeout; raw ``rd.vals``/``pipe`` is reliable).
  - stockdb's own ``pre_close`` field is qfq-polluted (measured: ~73% of
    rows sit below 0.99× the true prior close — an external-source pitfall,
    recorded in the plan's research notes) and the engine's
    price-limit band prefers ``bar["pre_close"]`` — so the field is dropped and
    rebuilt. Daily bars: ``close / (1 + pct_chg/100)`` (pct_chg is clean; exact
    in raw space, and in adjusted space equal to ``close.shift(1)``), falling
    back to ``close.shift(1)`` when pct_chg is missing (ETFs have no pct_chg).
    Minute bars: the minute table carries no pre_close/pct_chg, and the band
    base is the exchange's *prior-day* close (constant within the day, not the
    previous minute bar) — so the day's DAILY rebuilt pre_close is mapped onto
    every minute bar.
  - Extra columns are declarative via ``fields`` (config ``extra_fields``):
    daily whitelist turnover/amount/float_share/float_mv/total_mv/is_st/pe_ttm/
    pb/vol_ratio/name/pct_chg/industry_l1; the minute table only carries
    amount, so the minute whitelist is amount/industry_l1. ``industry_l1`` fills
    the SW level-1 tag per symbol via ``bk`` (current-state semantics, same
    approximation as plan A's industry.parquet) on every bar, stored as
    ``category`` — repeated static values are deliberate: a data_map row is a
    full daily snapshot, so strategies read ``bar["industry_l1"]`` without any
    side-table alignment (category keeps the repetition at ~tens of MB even for
    full-market daily).
  - Minute intervals: ``1m`` native; ``5m/15m/30m/1H`` aggregated in-loader on
    the natural clock (same convention as the engine / TqSdk, E011/E012). For
    A-share sessions the natural clock coincides with the trading clock at
    5/15/30 minutes; at 1H it does NOT match exchange-software 60m bars
    (09:00-10:00 buckets hold only the 09:30-09:59 half session).
  - Zero persistence: no loader cache (``VIBE_TRADING_DATA_CACHE`` never
    triggers for this source).
"""

from __future__ import annotations

import bisect
import importlib
import logging
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from backtest.loaders.base import validate_date_range, validate_ohlc
from backtest.loaders.registry import register

logger = logging.getLogger(__name__)

_SDK_PATH_ENV = "VIBE_TRADING_STOCKDB_SDK_PATH"
_HOST_ENV = "VIBE_TRADING_STOCKDB_HOST"
_PORT_ENV = "VIBE_TRADING_STOCKDB_PORT"
_TIMEOUT_ENV = "VIBE_TRADING_STOCKDB_TIMEOUT"

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 7899
_DEFAULT_TIMEOUT_S = 10

# Full-market daily is ~5200 symbols; batch the pipe so the raw dict payload of
# one batch never exceeds a few hundred symbols (same OOM shape the export
# tool hit). Retry granularity is per-symbol after a batch failure.
_BATCH_CODES = 300
_RETRY_BACKOFF_S = (0.5, 1.5, 4.0)

_DAILY_TABLE = "日k"
_MINUTE_TABLE = "分钟k"

# 股票 0(深A)/3(创业板)/6(沪A) + ETF/LOF 5(沪基金)/1(深基金)。北交所(9/8/4)不支持。
_ALLOWED_PREFIXES = frozenset({"0", "3", "6", "5", "1"})

# Whitelisted passthrough fields per bar table. The minute table only stores
# amount besides OHLCV (measured 2026-09-25); anything else in extra_fields is
# silently absent for minute intervals (whitelist intersection stays empty).
_DAILY_EXTRA_FIELDS = frozenset(
    {"turnover", "amount", "float_share", "float_mv", "total_mv",
     "is_st", "pe_ttm", "pb", "vol_ratio", "name", "pct_chg", "industry_l1"}
)
_MINUTE_EXTRA_FIELDS = frozenset({"amount", "industry_l1"})

# Natural-clock resample rules for minute intervals (pandas aliases). 1m needs
# no aggregation; 1H deliberately uses the engine's natural clock (differs from
# exchange-software 60m trading-clock bars — see module docstring).
_MINUTE_RESAMPLE_RULES = {
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1H": "1h",
    "1h": "1h",
}

_OHLCV_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}

# SDK module + preloaded 复权 factor table, resolved once per process.
_sdk: Any = None
# code6 -> (ex-div dates ascending, cumulative factors); same shape as the
# export tool's snapshot (verified hfq = raw × cum matches SDK fq="hfq").
_fq_dates: Dict[str, List[str]] = {}
_fq_cums: Dict[str, List[float]] = {}
_sdk_ready = False


def _env_host() -> str:
    return os.getenv(_HOST_ENV, _DEFAULT_HOST).strip() or _DEFAULT_HOST


def _env_port() -> int:
    try:
        return int(os.getenv(_PORT_ENV, str(_DEFAULT_PORT)))
    except ValueError:
        return _DEFAULT_PORT


def _env_timeout_s() -> int:
    try:
        return int(os.getenv(_TIMEOUT_ENV, str(_DEFAULT_TIMEOUT_S)))
    except ValueError:
        return _DEFAULT_TIMEOUT_S


def _load_fq_table(rd: Any) -> tuple[Dict[str, List[str]], Dict[str, List[float]]]:
    """Load the whole 复权 factor table once: code -> (dates asc, cums)."""
    dates_by: Dict[str, List[str]] = {}
    cums_by: Dict[str, List[float]] = {}
    try:
        raw = rd.get("复权*").get("cum")
        pairs: Dict[str, List[tuple[str, float]]] = {}
        for item in raw or []:
            key_str, cum_val = item[0], float(item[1])
            parts = key_str.split(":")
            if len(parts) >= 3:
                pairs.setdefault(parts[1], []).append((parts[2], cum_val))
        for code, pv in pairs.items():
            pv.sort(key=lambda x: x[0])
            dates_by[code] = [d for d, _ in pv]
            cums_by[code] = [c for _, c in pv]
    except Exception as exc:  # noqa: BLE001 - factor load failure degrades to raw prices
        logger.warning("stockdb loader: failed to load 复权 factor table (%s); "
                       "adjusted prices degrade to raw", exc)
    return dates_by, cums_by


def _load_sdk() -> bool:
    """Lazily import stock_sdk, init the connection, and preload factors.

    warm=False: bk warm-up is deferred until an industry_l1 request actually
    needs it, so plain OHLCV fetches stay fast to first byte.
    """
    global _sdk, _sdk_ready, _fq_dates, _fq_cums
    if _sdk_ready:
        return True
    sdk_path = os.getenv(_SDK_PATH_ENV, "").strip()
    if not sdk_path:
        logger.warning(
            "stockdb loader unavailable: set %s to the stockdb pybao directory",
            _SDK_PATH_ENV,
        )
        return False
    path = Path(sdk_path).expanduser()
    if not path.is_dir():
        logger.warning("stockdb loader unavailable: %s=%s is not a directory",
                       _SDK_PATH_ENV, sdk_path)
        return False
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
    try:
        sdk = importlib.import_module("stock_sdk")
    except Exception as exc:  # noqa: BLE001 - import failure means unavailable
        logger.warning("stockdb loader unavailable: import stock_sdk failed: %s "
                       "(pyd is CPython-version bound; measured OK on 3.13)", exc)
        return False
    try:
        sdk.init(host=_env_host(), port=_env_port(),
                 socket_timeout=_env_timeout_s(), warm=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("stockdb loader unavailable: init failed: %s "
                       "(is stockdb.exe running on %s:%s?)",
                       exc, _env_host(), _env_port())
        return False
    _fq_dates, _fq_cums = _load_fq_table(sdk.rd)
    _sdk = sdk
    _sdk_ready = True
    logger.info("stockdb loader ready: %s:%s, %d symbols with fq factors",
                _env_host(), _env_port(), len(_fq_dates))
    return True


def _tcp_probe(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _parse_code(code: str) -> Optional[str]:
    """``600519.SH``/``600519`` → 6-digit symbol, or None (unsupported/warn).

    The returned key of every fetch result is the ORIGINAL input code (the
    runner's missing-symbol check and the engine both key on it); only the
    suffix-stripped form goes to the SDK.
    """
    clean = code.split(":", 1)[1] if code.lower().startswith(("local:", "stockdb:")) else code
    sym = clean.strip().upper().split(".")[0]
    if len(sym) != 6 or not sym.isdigit():
        logger.warning("stockdb loader: unsupported symbol %r (need 6-digit A-share/ETF)",
                       code)
        return None
    if sym[0] not in _ALLOWED_PREFIXES:
        logger.warning("stockdb loader: symbol %r skipped (prefix %s not supported; "
                       "Beijing-exchange 9/8/4 excluded)", code, sym[0])
        return None
    return sym


def _pipe_mget(table: str, syms: List[str], time_query: str) -> Dict[str, List[dict]]:
    """Batched pipe mget; falls back to per-symbol vals with bounded retries.

    Measured payload shapes (2026-09-26): with multiple symbols ``do()`` returns
    one entry per symbol, each entry a ``[key, dict]`` pair list for that
    symbol; with a single symbol it returns a FLAT pair list (length = row
    count, not 1). Length equality with ``syms`` disambiguates — a single-symbol
    query returning exactly one row parses identically under both readings.
    """
    rd = _sdk.rd
    try:
        pp = rd.pipe()
        for sym in syms:
            pp.mget(table, sym, time_query)
        raw = pp.do()
        if not isinstance(raw, list):
            raw = [raw]
        if len(raw) == len(syms):
            return {sym: _normalize_records(items) for sym, items in zip(syms, raw)}
        if len(syms) == 1:
            return {syms[0]: _normalize_records(raw)}
        logger.warning(
            "stockdb loader: unexpected pipe payload (%d entries for %d symbols); "
            "keeping the first entry only — rerun may need per-symbol fallback",
            len(raw), len(syms),
        )
        return {syms[0]: _normalize_records(raw), **{s: [] for s in syms[1:]}}
    except Exception as exc:  # noqa: BLE001 - batch failure degrades to per-symbol
        logger.warning("stockdb loader: pipe mget failed for %d symbols (%s); "
                       "retrying per symbol", len(syms), exc)
        out: Dict[str, List[dict]] = {}
        for sym in syms:
            out[sym] = _retry_vals(table, sym, time_query)
        return out


def _normalize_records(items: Any) -> List[dict]:
    """Pipe/vals payloads arrive as dict lists, (key, dict) pairs, or a bare dict."""
    if items is None:
        return []
    if isinstance(items, dict):
        return [items]
    if isinstance(items, list):
        if items and isinstance(items[0], (list, tuple)):
            return [it[1] for it in items if isinstance(it, (list, tuple)) and len(it) > 1]
        return [it for it in items if isinstance(it, dict)]
    return []


def _retry_vals(table: str, sym: str, time_query: str) -> List[dict]:
    for attempt, backoff in enumerate(_RETRY_BACKOFF_S):
        try:
            return _normalize_records(_sdk.rd.vals(table, sym, time_query))
        except Exception as exc:  # noqa: BLE001 - transient socket errors
            if attempt == len(_RETRY_BACKOFF_S) - 1:
                logger.warning("stockdb loader: %s %s failed after retries: %s",
                               table, sym, exc)
                return []
            time.sleep(backoff)
    return []


def _cum_on(date8: str, code6: str) -> float:
    """Cumulative adjustment factor effective on ``date8`` (1.0 before first ex-div)."""
    dates = _fq_dates.get(code6)
    if not dates:
        return 1.0
    idx = bisect.bisect_right(dates, date8) - 1
    return _fq_cums[code6][idx] if idx >= 0 else 1.0


def _price_decimals(code6: str) -> int:
    """SDK-matching rounding: funds quote at 0.001, stocks at 0.01."""
    return 3 if code6.startswith(("1", "5")) else 2


def _adjust_divisor(code6: str, date8: str, fq_mode: str) -> float:
    """Divisor applied to raw prices for ``fq_mode`` — the SDK's exact formula.

    The SDK folds via ``price / (1.0 / cum)`` (hfq) and ``price / (f_latest /
    f_current)`` (qfq), then rounds. Division is NOT float-identical to
    multiplying by ``cum`` (~0.1% of rows sit on a round boundary and differ by
    one cent), so the divisor form is used verbatim for bit-parity with
    ``get_data(fq=...)`` and the plan-A export snapshot.
    """
    if fq_mode == "none":
        return 1.0
    cum = _cum_on(date8, code6)
    if fq_mode == "hfq":
        return 1.0 / cum if cum else 1.0
    cums = _fq_cums.get(code6)
    latest = cums[-1] if cums else 1.0
    return (latest / cum) if cum else 1.0


def _parse_extra_fields(fields: Optional[List[str]], whitelist: frozenset) -> List[str]:
    if not fields:
        return []
    return [f for f in fields if f in whitelist]


def _load_industry_map(code6s: List[str]) -> Dict[str, str]:
    """SW level-1 industry per symbol (current state; ~0.4ms/symbol measured)."""
    try:
        _sdk.warm_default_connection()
    except Exception as exc:  # noqa: BLE001 - warm-up failure still tries bk below
        logger.warning("stockdb loader: industry warm-up failed: %s", exc)
    out: Dict[str, str] = {}
    bk = getattr(_sdk, "bk", None)
    if bk is None:
        return out
    for sym in code6s:
        try:
            names = bk.get(sym, 1, "name")
            out[sym] = names[0] if names else ""
        except Exception:  # noqa: BLE001 - one bad symbol must not kill the batch
            out[sym] = ""
    return out


def _yyyymmdd(date_str: str) -> str:
    return pd.Timestamp(date_str).strftime("%Y%m%d")


def _rebuild_daily_pre_close(df: pd.DataFrame) -> pd.Series:
    """Rebuild pre_close from close + pct_chg (stockdb's own field is polluted).

    ``close/(1+pct_chg/100)`` is exact in raw space and, in an adjusted space,
    equals ``close.shift(1)`` (the cum ratio on ex-div days reproduces the
    exchange's adjusted prior close). Rows without pct_chg (ETFs) fall back to
    shift(1); the first row's NaN is correct (no band on the first bar).
    """
    pct = pd.to_numeric(df.get("pct_chg"), errors="coerce") if "pct_chg" in df else None
    close = df["close"]
    if pct is not None:
        by_factor = close / (1.0 + pct / 100.0)
        return by_factor.where(pct.notna() & (pct != -100.0), close.shift(1))
    return close.shift(1)


def _build_daily_frame(
    records: List[dict],
    code6: str,
    fq_mode: str,
    extras: List[str],
    industry: str,
) -> Optional[pd.DataFrame]:
    recs = [r for r in records if isinstance(r, dict) and r.get("date")]
    if not recs:
        return None
    df = pd.DataFrame(recs)
    date8 = df["date"].astype(str).str.zfill(8)
    df.index = pd.to_datetime(date8, format="%Y%m%d", errors="coerce")
    df.index.name = "timestamp"

    divisors = [_adjust_divisor(code6, d, fq_mode) for d in date8]
    decimals = _price_decimals(code6)
    for col in ("open", "high", "low", "close"):
        if col not in df:
            return None
        df[col] = (pd.to_numeric(df[col], errors="coerce")
                   / pd.Series(divisors, index=df.index)).round(decimals)
    if "volume" in df:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

    # stockdb's own pre_close is polluted (measured) — dropped unconditionally.
    df["pre_close"] = _rebuild_daily_pre_close(df).round(decimals)

    keep = ["open", "high", "low", "close", "pre_close"]
    if "volume" in df:
        keep.append("volume")
    for col in extras:
        if col == "industry_l1":
            continue
        if col in df.columns and col not in keep:
            keep.append(col)
    df = df[keep]
    df = df[pd.notna(df.index)]
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = validate_ohlc(df)
    if df.empty:
        return None
    for col in ("open", "high", "low", "close", "pre_close"):
        df[col] = df[col].astype("float64")
    if "industry_l1" in extras:
        df["industry_l1"] = pd.Categorical([industry] * len(df))
    return df


def _fetch_daily(
    self_code_map: Dict[str, str],
    start_date: str,
    end_date: str,
    extras: List[str],
    fq_mode: str,
) -> Dict[str, pd.DataFrame]:
    tq = f"{_yyyymmdd(start_date)}>{_yyyymmdd(end_date)}"
    industry_map = (
        _load_industry_map(list(dict.fromkeys(self_code_map.values())))
        if "industry_l1" in extras else {}
    )
    syms = list(self_code_map)
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    result: Dict[str, pd.DataFrame] = {}
    for i in range(0, len(syms), _BATCH_CODES):
        orig_batch = syms[i:i + _BATCH_CODES]
        # The LevelDB keys are bare 6-digit symbols; query with those and map
        # rows back to the ORIGINAL request codes the result must be keyed by.
        code6_batch = [self_code_map[orig] for orig in orig_batch]
        rows_by_code = _pipe_mget(_DAILY_TABLE, code6_batch, tq)
        for orig in orig_batch:
            code6 = self_code_map[orig]
            df = _build_daily_frame(
                rows_by_code.get(code6, []),
                code6,
                fq_mode,
                extras,
                industry_map.get(code6, ""),
            )
            if df is None or df.empty:
                continue
            # Belt-and-braces window clip: the LevelDB range expression already
            # bounds the query, but the loader owns the inclusive-window contract.
            df = df[(df.index >= start_ts) & (df.index <= end_ts)]
            if df.empty:
                continue
            result[orig] = df
    return result


def _fetch_daily_pre_close_map(
    code6s: List[str], start_date: str, end_date: str
) -> Dict[str, float]:
    """(code6, yyyymmdd) → rebuilt daily pre_close, for minute-bar band base.

    The price-limit band derives from the exchange's prior-DAY close, constant
    across the day's minute bars — never the previous minute bar's close.
    """
    tq = f"{_yyyymmdd(start_date)}>{_yyyymmdd(end_date)}"
    mapping: Dict[str, float] = {}
    unique = list(dict.fromkeys(code6s))
    for i in range(0, len(unique), _BATCH_CODES):
        batch = unique[i:i + _BATCH_CODES]
        rows_by_code = _pipe_mget(_DAILY_TABLE, batch, tq)
        for code6 in batch:
            recs = [r for r in rows_by_code.get(code6, [])
                    if isinstance(r, dict) and r.get("date")]
            if not recs:
                continue
            df = pd.DataFrame(recs)
            date8 = df["date"].astype(str).str.zfill(8)
            decimals = _price_decimals(code6)
            divisors = [_adjust_divisor(code6, d, "hfq") for d in date8]
            close = (pd.to_numeric(df["close"], errors="coerce")
                     / pd.Series(divisors, index=df.index)).round(decimals)
            pct = pd.to_numeric(df.get("pct_chg"), errors="coerce") if "pct_chg" in df else None
            if pct is not None:
                pre = (close / (1.0 + pct / 100.0)).where(
                    pct.notna() & (pct != -100.0), close.shift(1))
            else:
                pre = close.shift(1)
            pre = pre.round(decimals)
            for d, v in zip(date8, pre):
                if pd.notna(v) and v > 0:
                    mapping[f"{code6}:{d}"] = float(v)
    return mapping


def _build_minute_frame(
    records: List[dict],
    code6: str,
    fq_mode: str,
    extras: List[str],
    industry: str,
    pre_close_map: Dict[str, float],
) -> Optional[pd.DataFrame]:
    recs = [r for r in records if isinstance(r, dict) and r.get("date")]
    if not recs:
        return None
    df = pd.DataFrame(recs)
    date14 = df["date"].astype(str).str.zfill(14)
    try:
        df.index = pd.to_datetime(date14, format="%Y%m%d%H%M%S")
    except ValueError:
        logger.warning("stockdb loader: unexpected minute date format for %s, skipped",
                       code6)
        return None
    df.index.name = "timestamp"

    date8 = date14.str[:8]
    divisors = [_adjust_divisor(code6, d, fq_mode) for d in date8]
    decimals = _price_decimals(code6)
    for col in ("open", "high", "low", "close"):
        if col not in df:
            return None
        df[col] = (pd.to_numeric(df[col], errors="coerce")
                   / pd.Series(divisors, index=df.index)).round(decimals)
    if "volume" in df:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

    df["pre_close"] = [pre_close_map.get(f"{code6}:{d}") for d in date8]
    df["pre_close"] = pd.to_numeric(df["pre_close"], errors="coerce")

    keep = ["open", "high", "low", "close", "pre_close"]
    if "volume" in df:
        keep.append("volume")
    for col in extras:
        if col == "industry_l1":
            continue
        if col in df.columns and col not in keep:
            keep.append(col)
    df = df[keep]
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = validate_ohlc(df)
    if df.empty:
        return None
    for col in ("open", "high", "low", "close", "pre_close"):
        df[col] = df[col].astype("float64")
    if "industry_l1" in extras:
        df["industry_l1"] = pd.Categorical([industry] * len(df))
    return df


def _resample_minute(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    """Natural-clock aggregation 1m → 5m/15m/30m/1H (engine/TqSdk convention)."""
    rule = _MINUTE_RESAMPLE_RULES.get(interval)
    if rule is None:
        return df
    agg = dict(_OHLCV_AGG)
    if "amount" in df.columns:
        agg["amount"] = "sum"
    if "pre_close" in df.columns:
        agg["pre_close"] = "first"  # band base is constant within the day
    for col in df.columns:
        if col not in agg:
            agg[col] = "last"
    res = df.resample(rule).agg(agg)
    res = res.dropna(subset=["open", "high", "low", "close"])
    res.index.name = df.index.name
    return res


@register
class DataLoader:
    """stockdb direct-connect loader (local stockdb.exe service over socket)."""

    name = "stockdb"
    markets = {"a_share"}
    requires_auth = False

    def __init__(self) -> None:
        pass

    def is_available(self) -> bool:
        """True when the SDK is configured/importable AND the service port answers.

        Deliberately light: no data is fetched, no factor table loaded — the
        fail-closed contract (source="stockdb" must not degrade to a network
        source) means an unavailable service surfaces as an explicit error at
        fetch time with full context.
        """
        sdk_path = os.getenv(_SDK_PATH_ENV, "").strip()
        if not sdk_path:
            return False
        path = Path(sdk_path).expanduser()
        if not path.is_dir():
            return False
        probe_path = str(path)
        if probe_path not in sys.path:
            try:
                sys.path.insert(0, probe_path)
                importlib.import_module("stock_sdk")
            except Exception:  # noqa: BLE001 - pyd/interpreter mismatch etc.
                return False
        return _tcp_probe(_env_host(), _env_port())

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
        if not _load_sdk():
            return {}

        interval_key = str(interval).strip()
        if interval_key.upper() in ("1D", "D", "DAY", "DAILY"):
            return self._fetch(codes, start_date, end_date, fields, daily=True)
        if interval_key == "1m" or interval_key in _MINUTE_RESAMPLE_RULES:
            return self._fetch(codes, start_date, end_date, fields, daily=False,
                               interval=interval_key)
        logger.warning("stockdb loader supports 1D and 1m/5m/15m/30m/1H bars; "
                       "rejecting interval=%r", interval)
        return {}

    def _fetch(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        fields: Optional[List[str]],
        daily: bool,
        interval: str = "1D",
    ) -> Dict[str, pd.DataFrame]:
        code_map: Dict[str, str] = {}
        for code in codes:
            sym = _parse_code(code)
            if sym is not None:
                code_map[code] = sym
        if not code_map:
            return {}

        whitelist = _DAILY_EXTRA_FIELDS if daily else _MINUTE_EXTRA_FIELDS
        extras = _parse_extra_fields(fields, whitelist)
        industry_map: Dict[str, str] = {}
        if "industry_l1" in extras:
            industry_map = _load_industry_map(list(dict.fromkeys(code_map.values())))
        fq_mode = self._fq_mode()

        if daily:
            return _fetch_daily(code_map, start_date, end_date, extras, fq_mode)

        # Minute path: bands need the day's daily pre_close, so pull the daily
        # rebuilt pre_close for the same window first (one row per symbol-day).
        pre_close_map = _fetch_daily_pre_close_map(
            list(code_map.values()), start_date, end_date)
        tq = (f"{_yyyymmdd(start_date)}000000>{_yyyymmdd(end_date)}235959")
        syms = list(code_map)
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        result: Dict[str, pd.DataFrame] = {}
        for i in range(0, len(syms), _BATCH_CODES):
            orig_batch = syms[i:i + _BATCH_CODES]
            code6_batch = [code_map[orig] for orig in orig_batch]
            rows_by_code = _pipe_mget(_MINUTE_TABLE, code6_batch, tq)
            for orig in orig_batch:
                df = _build_minute_frame(
                    rows_by_code.get(code_map[orig], []),
                    code_map[orig],
                    fq_mode,
                    extras,
                    industry_map.get(code_map[orig], ""),
                    pre_close_map,
                )
                if df is None or df.empty:
                    continue
                # Clip to [start, end] inclusive of the whole end day (minute
                # timestamps on the end date must survive a bare-midnight bound).
                df = df[(df.index >= start_ts) & (df.index <= end_ts)]
                if df.empty:
                    continue
                if interval != "1m":
                    df = _resample_minute(df, interval)
                    if df.empty:
                        continue
                result[orig] = df
        return result

    @staticmethod
    def _fq_mode() -> str:
        """Adjustment mode from ``VIBE_TRADING_STOCKDB_FQ`` (default ``hfq``).

        The loader's fetch contract carries no config dict (only codes, dates,
        ``fields`` and ``interval``), so the fq knob lives in the env mirror
        (``~/.vibe-trading/.env``) next to the SDK path — one place, set once.
        """
        mode = os.getenv("VIBE_TRADING_STOCKDB_FQ", "hfq").strip().lower()
        return mode if mode in ("hfq", "qfq", "none") else "hfq"
