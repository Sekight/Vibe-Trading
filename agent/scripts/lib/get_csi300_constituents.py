"""获取沪深300历史成分股：baostock 主源，akshare/sina 兜底。

功能：
- baostock 按候选日期（默认每年 1 月 1 日、7 月 1 日，外加区间起止日）查询
  当时成分，按 updateDate 去重，得到无幸存者偏差的历史 membership 长表。
- 候选日期是“查询日”，实际成分调整日以 baostock 返回的 updateDate 为准。
- 单个日期 baostock 全部失败时走兜底：akshare 中证权重 -> akshare 中证目录 ->
  新浪成分。兜底只能取“当前最新一期”，会标记为近似数据，不冒充历史快照。
- 输出 membership.parquet / membership.csv / snapshots.json 到 out-dir。

用法（建议在 vibe-trading-src 仓库根目录用 venv python 运行）：
    E:\\gitCloneProgram\\vibe-trading-src\\.venv\\Scripts\\python.exe agent/scripts/lib/get_csi300_constituents.py --start-date 2020-01-01 --end-date 2026-12-31 --out-dir C:/tmp/csi300

参数：
    --index          成分指数代码，默认 399300.SZ；支持 300/000300/000905 等
    --snapshot-dates 覆盖候选查询日，逗号分隔（联调用，如 2024-07-01,2026-07-31）
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# baostock 查询函数名 -> 支持的指数代码（去掉交易所后缀后的数字部分）。
_BAOSTOCK_INDEX_FUNCS = {
    "300": "query_hs300_stocks",
    "000300": "query_hs300_stocks",
    "399300": "query_hs300_stocks",
    "000905": "query_zz500_stocks",
    "399905": "query_zz500_stocks",
    "000016": "query_sz50_stocks",
}

# akshare 的 csindex symbol 与指数代码映射。
_AKSHARE_INDEX_SYMBOLS = {
    "399300": "000300",
    "399905": "000905",
}


@dataclass
class MembershipResult:
    """历史成分股抓取结果。"""

    df: pd.DataFrame
    snapshots: list[dict] = field(default_factory=list)
    source_used: str = "baostock"
    warnings: list[str] = field(default_factory=list)
    out_dir: Optional[Path] = None
    membership_parquet: Optional[Path] = None
    membership_csv: Optional[Path] = None
    snapshots_json: Optional[Path] = None


def _normalize_cn_code(raw: object) -> Optional[str]:
    """把各种来源的 A 股代码归一化成 ``600519.SH`` / ``000001.SZ``。

    兼容 baostock 的 ``sh.600000``、常规的 ``600000.SH``、akshare 的
    ``600000`` / ``sh600000`` 等写法。
    """
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text or text == "nan":
        return None
    if "." in text:
        left, right = text.rsplit(".", 1)
        if left in {"sh", "sz", "bj"} and right.isdigit():
            return f"{right.zfill(6)}.{left.upper()}"
        if right in {"sh", "sz", "bj"} and left.isdigit():
            return f"{left.zfill(6)}.{right.upper()}"
        return None
    if text[:2] in {"sh", "sz", "bj"} and text[2:].isdigit():
        prefix, digits = text[:2], text[2:]
        return f"{digits.zfill(6)}.{prefix.upper()}"
    if not text.isdigit():
        return None
    digits = text.zfill(6)[-6:]
    if digits.startswith(("6", "9")):
        return f"{digits}.SH"
    if digits.startswith(("0", "2", "3")):
        return f"{digits}.SZ"
    if digits.startswith(("4", "8")):
        return f"{digits}.BJ"
    return None


def _candidate_dates(
    start_date: str, end_date: str, snapshot_dates: Optional[list[str]] = None
) -> list[str]:
    """生成候选查询日：默认每年 1/7 月调股后各查一次，另加区间起止日。"""
    if snapshot_dates:
        parsed = [pd.Timestamp(d) for d in snapshot_dates]
        return sorted({d.strftime("%Y-%m-%d") for d in parsed})

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    dates: set[str] = set()
    year = start.year
    while year <= end.year:
        for month, day in ((1, 1), (7, 1)):
            candidate = pd.Timestamp(f"{year}-{month:02d}-{day:02d}")
            if start <= candidate <= end:
                dates.add(candidate.strftime("%Y-%m-%d"))
        year += 1
    dates.add(start.strftime("%Y-%m-%d"))
    dates.add(end.strftime("%Y-%m-%d"))
    return sorted(dates)


def _query_baostock_snapshot(
    func_name: str, query_date: str, *, max_retries: int, base_sleep: float
) -> tuple[list[list[str]], list[str]]:
    """带重试的 baostock 成分查询，返回 (rows, fields)。"""
    import baostock as bs

    last_error: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            rs = getattr(bs, func_name)(query_date)
            if rs.error_code != "0":
                raise RuntimeError(f"{func_name}({query_date}) error: {rs.error_msg}")
            rows: list[list[str]] = []
            while rs.next():
                rows.append(rs.get_row_data())
            if not rows:
                raise RuntimeError(f"{func_name}({query_date}) 返回空")
            return rows, list(rs.fields)
        except Exception as exc:  # noqa: BLE001 - 统一走重试/兜底
            last_error = exc
            logger.warning(
                "%s 第 %d/%d 次查询 %s 失败: %s",
                func_name, attempt, max_retries, query_date, exc,
            )
            if attempt < max_retries:
                time.sleep(base_sleep * (2 ** (attempt - 1)))
    assert last_error is not None
    raise last_error


def _run_with_timeout(fn: Callable[[], object], timeout: float) -> object:
    """在线程池里执行，防止无 timeout 的 akshare 调用挂死。"""
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        return future.result(timeout=timeout)


def _extract_codes_from_frame(frame: pd.DataFrame) -> list[str]:
    """从 akshare/sina 成分表里提取代码列并归一化。"""
    if frame is None or frame.empty:
        return []
    code_col = None
    for col in frame.columns:
        if any(key in str(col) for key in ("代码", "code", "Code")):
            code_col = col
            break
    if code_col is None:
        return []
    codes: list[str] = []
    for raw in frame[code_col].tolist():
        normalized = _normalize_cn_code(raw)
        if normalized and normalized not in codes:
            codes.append(normalized)
    return codes


def _fetch_latest_fallback(
    index: str, *, max_retries: int, base_sleep: float, timeout: float
) -> tuple[list[str], str]:
    """兜底链：akshare 中证权重 -> akshare 中证目录 -> 新浪成分。

    akshare/sina 只能给当前最新一期成分，调用方会把它标记为近似快照。
    """
    digits = "".join(ch for ch in index if ch.isdigit())
    symbol = _AKSHARE_INDEX_SYMBOLS.get(digits, digits)
    import akshare as ak

    candidates: list[tuple[str, Callable[[], object], str]] = [
        ("akshare_csindex_weight",
         lambda: ak.index_stock_cons_weight_csindex(symbol=symbol),
         "akshare_csindex_weight"),
        ("akshare_csindex_cons",
         lambda: ak.index_stock_cons_csindex(symbol=symbol),
         "akshare_csindex_cons"),
        ("sina_cons",
         lambda: ak.index_stock_cons(symbol=symbol),
         "sina_cons"),
    ]
    for name, fn, source_name in candidates:
        for attempt in range(1, max_retries + 1):
            try:
                logger.info("兜底源 %s 第 %d/%d 次尝试 (symbol=%s)", name, attempt, max_retries, symbol)
                frame = _run_with_timeout(fn, timeout)
                codes = _extract_codes_from_frame(frame)
                if codes:
                    logger.info("兜底源 %s 返回 %d 只成分", name, len(codes))
                    return codes, source_name
            except Exception as exc:  # noqa: BLE001 - 尝试下一个兜底源
                logger.warning("兜底源 %s 第 %d 次失败: %s", name, attempt, exc)
                if attempt < max_retries:
                    time.sleep(base_sleep * (2 ** (attempt - 1)))
    raise RuntimeError(f"全部兜底源失败: {index}")


def get_csi300_constituents(
    start_date: str,
    end_date: str,
    index: str = "399300.SZ",
    *,
    out_dir: Optional[str | Path] = None,
    snapshot_dates: Optional[list[str]] = None,
    sleep_seconds: float = 0.2,
    max_retries: int = 3,
    fallback_timeout: float = 30.0,
) -> MembershipResult:
    """获取指数历史成分股长表。

    Args:
        start_date: 区间起始日 ``YYYY-MM-DD``（会加入候选查询日）。
        end_date: 区间结束日 ``YYYY-MM-DD``（会加入候选查询日）。
        index: 指数代码，默认 ``399300.SZ``。
        out_dir: 输出目录，写 membership.parquet/csv 与 snapshots.json。
        snapshot_dates: 显式候选查询日；缺省按每年 1/7 月生成。
        sleep_seconds: 每次 baostock 查询后的限流间隔。
        max_retries: 每个查询/兜底源的最大重试次数。
        fallback_timeout: 兜底源单次调用超时（秒）。

    Returns:
        MembershipResult：membership 长表与快照元数据。
    """
    digits = "".join(ch for ch in index if ch.isdigit())
    func_name = _BAOSTOCK_INDEX_FUNCS.get(digits)
    if func_name is None:
        raise ValueError(
            f"不支持的指数 {index}；baostock 目前支持 {sorted(_BAOSTOCK_INDEX_FUNCS)}"
        )

    import baostock as bs

    dates = _candidate_dates(start_date, end_date, snapshot_dates)
    logger.info(
        "开始抓取成分股 index=%s start=%s end=%s 候选查询日=%d",
        index, start_date, end_date, len(dates),
    )

    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"baostock 登录失败: {login.error_msg}")
    logger.info("baostock 登录成功")

    rows_by_update: dict[str, dict[str, str]] = {}
    snapshot_meta: dict[str, dict] = {}
    failed_dates: list[str] = []
    warnings: list[str] = []

    try:
        for query_date in dates:
            try:
                rows, fields = _query_baostock_snapshot(
                    func_name, query_date, max_retries=max_retries, base_sleep=sleep_seconds
                )
            except Exception as exc:  # noqa: BLE001 - 单日期失败进入兜底
                failed_dates.append(query_date)
                warnings.append(f"baostock 查询 {query_date} 失败: {exc}")
                continue

            # fields 顺序: updateDate, code, code_name
            date_idx = fields.index("updateDate") if "updateDate" in fields else 0
            code_idx = fields.index("code") if "code" in fields else 1
            name_idx = fields.index("code_name") if "code_name" in fields else 2
            for row in rows:
                update_date = row[date_idx]
                normalized = _normalize_cn_code(row[code_idx])
                if not normalized:
                    continue
                rows_by_update.setdefault(update_date, {})[normalized] = row[name_idx]
            snapshot_meta[query_date] = {
                "query_date": query_date,
                "update_date": rows[0][date_idx] if rows else None,
                "count": len(rows),
                "source": "baostock",
            }
            logger.info(
                "查询日 %s 返回 %d 只，updateDate=%s",
                query_date, len(rows), rows[0][date_idx] if rows else None,
            )
            time.sleep(sleep_seconds)
    finally:
        bs.logout()

    # 单日期 baostock 失败时，用“当前最新一期”兜底，并明确标记为近似。
    if failed_dates:
        fallback_codes, fallback_source = _fetch_latest_fallback(
            index, max_retries=max_retries, base_sleep=sleep_seconds, timeout=fallback_timeout
        )
        latest_update = max(rows_by_update, default=end_date)
        for query_date in failed_dates:
            for code in fallback_codes:
                rows_by_update.setdefault(latest_update, {})[code] = ""
            snapshot_meta[query_date] = {
                "query_date": query_date,
                "update_date": latest_update,
                "count": len(fallback_codes),
                "source": fallback_source,
            }
        warnings.append(
            f"{len(failed_dates)} 个查询日使用兜底最新快照({fallback_source})，"
            f"非真实历史成分: {failed_dates}"
        )
        logger.warning("使用兜底最新快照，近似填充日期: %s", failed_dates)

    records: list[dict] = []
    for update_date, members in rows_by_update.items():
        for code, name in sorted(members.items()):
            records.append({"update_date": update_date, "code": code, "code_name": name})
    df = pd.DataFrame(records, columns=["update_date", "code", "code_name"])
    if not df.empty:
        df = df.sort_values(["update_date", "code"]).reset_index(drop=True)

    snapshots = [
        {
            "query_date": meta["query_date"],
            "update_date": meta["update_date"],
            "count": meta["count"],
            "source": meta["source"],
        }
        for meta in sorted(snapshot_meta.values(), key=lambda m: m["query_date"])
    ]
    result = MembershipResult(
        df=df,
        snapshots=snapshots,
        source_used="baostock" if not failed_dates else "baostock+fallback",
        warnings=warnings,
    )

    if out_dir is not None:
        out_root = Path(out_dir)
        out_root.mkdir(parents=True, exist_ok=True)
        result.out_dir = out_root
        result.membership_parquet = out_root / "membership.parquet"
        result.membership_csv = out_root / "membership.csv"
        result.snapshots_json = out_root / "snapshots.json"
        df.to_parquet(result.membership_parquet, index=False)
        df.to_csv(result.membership_csv, index=False, encoding="utf-8-sig")
        result.snapshots_json.write_text(
            json.dumps(snapshots, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(
            "membership 落盘 rows=%d snapshots=%d files=%s/%s/%s",
            len(df), len(snapshots),
            result.membership_parquet.name, result.membership_csv.name,
            result.snapshots_json.name,
        )

    logger.info(
        "成分股抓取完成 unique_update_dates=%d unique_codes=%d source=%s warnings=%d",
        df["update_date"].nunique() if not df.empty else 0,
        df["code"].nunique() if not df.empty else 0,
        result.source_used, len(warnings),
    )
    return result


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="获取指数历史成分股（baostock 主源）")
    parser.add_argument("--start-date", default="2020-01-01", help="区间起始日")
    parser.add_argument("--end-date", default="2026-12-31", help="区间结束日")
    parser.add_argument("--index", default="399300.SZ", help="指数代码，默认 399300.SZ")
    parser.add_argument("--out-dir", help="输出目录（不传则只返回不落盘）")
    parser.add_argument("--snapshot-dates", help="覆盖候选查询日，逗号分隔")
    parser.add_argument("--sleep", type=float, default=0.2, help="查询间隔秒")
    parser.add_argument("--max-retries", type=int, default=3, help="最大重试次数")
    parser.add_argument("--fallback-timeout", type=float, default=30.0, help="兜底超时秒")
    args = parser.parse_args()

    snapshot_dates = None
    if args.snapshot_dates:
        snapshot_dates = [d.strip() for d in args.snapshot_dates.split(",") if d.strip()]

    result = get_csi300_constituents(
        args.start_date,
        args.end_date,
        args.index,
        out_dir=args.out_dir,
        snapshot_dates=snapshot_dates,
        sleep_seconds=args.sleep,
        max_retries=args.max_retries,
        fallback_timeout=args.fallback_timeout,
    )
    print(json.dumps({
        "rows": len(result.df),
        "snapshots": len(result.snapshots),
        "unique_codes": int(result.df["code"].nunique()) if not result.df.empty else 0,
        "source": result.source_used,
        "warnings": result.warnings,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
