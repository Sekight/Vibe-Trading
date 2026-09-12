"""stockdb -> Parquet A 股日线数据仓导出工具（vibe-trading 数据源接入 P-20260905 阶段 1）。

把本地 stockdb 服务（127.0.0.1:7899，LevelDB）的沪深 A 股日线行情、复权因子、
证券生命周期、申万一级行业、交易日历导出为 data-bridge 可读取的 Parquet 文件。

运行前提：
  - stockdb.exe 正在运行（127.0.0.1:7899）；
  - Python 环境能 import stock_sdk（把 stockdb 的 pybao 目录加入 PYTHONPATH）；
  - pandas + pyarrow（写 Parquet）。

用法示例（Git Bash / PowerShell）：
  PYTHONPATH=E:/data/free-stockdb-windows-v0.3.2-more-power/stockdb/pybao \\
    python tools/export_stockdb_ashare.py --out data/stockdb_ashare --start 20110101

常用参数：
  --start 20110101    数据起点（MA120 预热 + 样本内 2012 起点，2011 起足够）
  --end   20260905    数据终点（默认今天）
  --prefixes 0,3,6    证券前缀：0=深A、3=创业板、6=沪A（默认全部）；9=北交所可选
  --limit 100         仅导出前 N 只（测试模式）
  --codes-file x.txt  只导出文件里列出的 6 位代码（断点续跑）
  --stages daily,calendar,securities,industry  默认全部
  --out <dir>         输出目录（默认 ./data/stockdb_ashare）

产物（out 目录下）：
  daily.parquet       日线宽表：date/code/name/open/high/low/close/pre_close/
                      volume/amount/turnover/float_share/float_mv/total_mv/is_st
                      + open_hfq/high_hfq/low_hfq/close_hfq（后复权=原始价×当日累计因子）
  calendar.parquet    交易日历（由 daily 日期并集推导，标注口径）
  securities.parquet  代码/名称/上市日/退市日/是否退市（退市股票保留，防幸存者偏差）
  industry.parquet    申万一级行业（stockdb 板块当前状态，非历史时点）
  manifest.json       导出元信息（时间/范围/版本），复现可溯源

口径说明：
  - 后复权价 = 原始价 × 当日累计复权因子（与 stockdb SDK fq="hfq" 一致，round 2 位）；
  - turnover 为换手率 %、amount 为元、volume 为股、float_share 为股，均取自 stockdb 字段；
  - 脚本幂等：同参数重跑会覆盖旧文件；失败不中断已写分片（分阶段落盘）。
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pyarrow as pa

START_DEFAULT = "20110101"


def _today_int() -> str:
    return time.strftime("%Y%m%d")


def _resolve_codes(rd, prefixes: list[str], limit: int | None, codes_file: str | None) -> list[str]:
    """证券清单：股票前缀 + 可选白名单文件 + 测试 limit。"""
    if codes_file:
        raw = [ln.strip() for ln in Path(codes_file).read_text(encoding="utf-8").splitlines()]
        codes = [c for c in raw if c.isdigit() and len(c) == 6]
        print(f"[securities] 白名单文件共 {len(codes)} 只")
    else:
        table = rd.get("股票代码")
        codes: list[str] = []
        for p in prefixes:
            codes.extend(str(c) for c in table.get(p))
        print(f"[securities] 前缀 {prefixes} 共 {len(codes)} 只")
    if limit:
        codes = codes[:limit]
        print(f"[securities] --limit {limit}，取前 {len(codes)} 只")
    return codes


def _load_fq_cums(rd) -> dict[str, tuple[list[str], list[float]]]:
    """复权因子全表：code -> (dates 升序, cums)。与 stock_sdk 的预加载同款。"""
    tmp: dict[str, list[tuple[str, float]]] = defaultdict(list)
    try:
        raw = rd.get("复权*").get("cum")
        for item in raw:
            key_str, cum_val = item[0], float(item[1])
            parts = key_str.split(":")
            if len(parts) >= 3:
                tmp[parts[1]].append((parts[2], cum_val))
    except Exception as exc:  # noqa: BLE001 - 因子缺失时降级为不复权
        print(f"[fq] 读取复权因子失败: {exc}；降级 hfq=raw")
    return {c: ([d for d, _ in sorted(v)], [x for _, x in sorted(v)]) for c, v in tmp.items()}


def _cum_on(date_str: str, dates: list[str], cums: list[float]) -> float:
    idx = bisect.bisect_right(dates, date_str) - 1
    return cums[idx] if idx >= 0 else 1.0


def _fetch_daily(rd, code: str, start: str, end: str, fq: dict, retries: int = 3) -> list[dict]:
    dates_l, cums_l = fq.get(code, ([], []))
    for attempt in range(retries):
        try:
            rows = rd.get_data(code, start=start, end=end, frequency="1d", fq=None)
            out = []
            for r in rows:
                if not isinstance(r, dict):
                    continue
                date_str = str(r.get("date", ""))
                if len(date_str) != 8:
                    continue
                cum = _cum_on(date_str, dates_l, cums_l)
                rec = dict(r)
                # 与 stock_sdk fq="hfq" 同款折算路径（raw / (1.0/cum)），保证逐位一致。
                for fld in ("open", "high", "low", "close"):
                    raw_val = r.get(fld)
                    try:
                        rec[f"{fld}_hfq"] = (
                            round(float(raw_val) / (1.0 / cum), 2) if raw_val is not None else None
                        )
                    except (TypeError, ValueError):
                        rec[f"{fld}_hfq"] = None
                out.append(rec)
            return out
        except Exception as exc:  # noqa: BLE001 - 连接层错误重试
            if attempt == retries - 1:
                print(f"[daily] {code} 失败(重试 {retries} 次): {exc}")
                return []
            time.sleep(1 + attempt)
    return []


def _export_daily(rd, codes: list[str], start: str, end: str, out_dir: Path, fq: dict) -> int:
    """逐股取数，按行数分片落盘（daily_shard_*.parquet），最后流式合并 daily.parquet。

    全市场 5000+ 只、1200 万+ 行无法一次进内存（曾触发 ArrayMemoryError），
    分片把峰值压到单片体积；合并用 ParquetWriter 逐片流式写出，不整体 concat。
    返回总行数。
    """
    import pyarrow.parquet as pq

    SHARD_ROWS = 800_000
    frames: list[pd.DataFrame] = []
    shards: list[Path] = []
    total_rows = 0
    t0 = time.time()
    for i, code in enumerate(codes):
        rows = _fetch_daily(rd, code, start, end, fq)
        if rows:
            frames.append(pd.DataFrame(rows))
        cur_rows = sum(len(f) for f in frames)
        if frames and (cur_rows >= SHARD_ROWS or i == len(codes) - 1):
            df = pd.concat(frames, ignore_index=False)
            df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")
            df = df.sort_values(["date", "code"]).reset_index(drop=True)
            shard = out_dir / f"daily_shard_{len(shards):03d}.parquet"
            df.to_parquet(shard, index=False)
            shards.append(shard)
            total_rows += len(df)
            frames = []
        if (i + 1) % 200 == 0 or i == len(codes) - 1:
            el = time.time() - t0
            print(f"[daily] {i + 1}/{len(codes)} 只，{el / (i + 1):.2f}s/只，累计 {el:.0f}s")
    if not shards:
        return 0
    # 流式合并分片 -> daily.parquet（逐片只读单片，峰值可控）
    schema = pq.read_schema(shards[0])
    with pq.ParquetWriter(out_dir / "daily.parquet", schema) as writer:
        for shard in shards:
            writer.write_table(pq.read_table(shard))
    for shard in shards:
        shard.unlink()
    return total_rows


def _export_calendar(out_dir: Path) -> None:
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    dates = pc.unique(pq.read_table(out_dir / "daily.parquet", columns=["date"])["date"])
    cal = pd.DataFrame({"trade_date": [d.strftime("%Y-%m-%d") for d in dates.to_pylist()]})
    cal.to_parquet(out_dir / "calendar.parquet", index=False)
    print(f"[calendar] {len(cal)} 个交易日（由 daily 日期并集推导）")


def _export_securities(delisted: set[str], out_dir: Path) -> None:
    import pyarrow.parquet as pq

    tab = pq.read_table(out_dir / "daily.parquet", columns=["code", "name", "date"])
    df = tab.to_pandas()
    g = df.groupby("code")
    rows = []
    for code, sub in g:
        rows.append(
            {
                "code": code,
                "name": sub["name"].dropna().iloc[-1] if sub["name"].notna().any() else "",
                "list_date": sub["date"].min().strftime("%Y-%m-%d"),
                "delist_date": sub["date"].max().strftime("%Y-%m-%d"),
                "is_delisted": code in delisted,
            }
        )
    sec = pd.DataFrame(rows)
    sec.to_parquet(out_dir / "securities.parquet", index=False)
    print(f"[securities] {len(sec)} 只（含退市 {int(sec['is_delisted'].sum())} 只）")


def _export_industry(rd, codes: list[str], out_dir: Path) -> None:
    try:
        import stock_sdk

        stock_sdk.warm_default_connection()
        bk = stock_sdk.bk
    except Exception as exc:  # noqa: BLE001
        print(f"[industry] 无法加载板块索引，跳过: {exc}")
        return
    rows = []
    for i, code in enumerate(codes):
        try:
            names = bk.get(code, 1, "name")
            industry = names[0] if names else ""
        except Exception:  # noqa: BLE001
            industry = ""
        rows.append({"code": code, "industry_l1": industry})
        if (i + 1) % 1000 == 0:
            print(f"[industry] {i + 1}/{len(codes)}")
    ind = pd.DataFrame(rows)
    ind.to_parquet(out_dir / "industry.parquet", index=False)
    print(f"[industry] {len(ind)} 只（申万一级，当前状态近似）")


def _fetch_new_rows(rd, codes: list[str], since: str, end: str, fq: dict) -> pd.DataFrame:
    """增量取数：逐股只拉 since 次日 ~ end 的 bar（含 hfq 折算），返回新行 DataFrame。

    列与全量导出一致（25 列）；请求体量小（每只几天），耗时以请求往返为主。
    """
    frames: list[pd.DataFrame] = []
    t0 = time.time()
    for i, code in enumerate(codes):
        rows = _fetch_daily(rd, code, since, end, fq)
        if rows:
            frames.append(pd.DataFrame(rows))
        if (i + 1) % 500 == 0 or i == len(codes) - 1:
            el = time.time() - t0
            print(f"[incr] {i + 1}/{len(codes)} 只，{el / (i + 1):.3f}s/只，累计 {el:.0f}s")
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")
    return df.sort_values(["date", "code"]).reset_index(drop=True)


def _merge_incremental(orig_path: Path, new_df: pd.DataFrame) -> int:
    """把新行合并进 daily.parquet（流式，内存峰值 = 单 batch + 新行）。

    原文件按 (date, code) 升序；新行 date 均大于原文件最大日期，故排序后位于尾部——
    用 ParquetWriter 逐 batch 复制原文件再追加新行，避免全表载入内存（批量读写控 IO）。
    返回合并后总行数。
    """
    import pyarrow.parquet as pq

    src = pq.ParquetFile(orig_path)
    schema = src.schema_arrow
    tmp = orig_path.with_suffix(".parquet.tmp")
    n_old = src.metadata.num_rows
    with pq.ParquetWriter(tmp, schema) as w:
        for batch in src.iter_batches(batch_size=1_000_000):
            w.write_batch(batch)
        if not new_df.empty:
            # 对齐列顺序/类型后追加（新行 date 均大于原文件，排序位置在尾部）
            new_tbl = pa.Table.from_pandas(new_df[schema.names], schema=schema, preserve_index=False)
            w.write_table(new_tbl)
    # Windows 下目标文件可能被杀毒/索引短暂锁住，重试 replace
    for attempt in range(5):
        try:
            tmp.replace(orig_path)
            break
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(2)
    return n_old + len(new_df)


def _update_fq_snapshot(fq: dict, out_dir: Path) -> None:
    """把在线复权表与本地 fq_factor.parquet 快照 diff，追加新 (code, date, cum) 行。

    fq 为在线全量 {code: (dates, cums)}；快照仅 0.3MB，直接整表重写。
    """
    snap_path = out_dir / "fq_factor.parquet"
    if not snap_path.exists():
        return  # 无快照则跳过（全量模式重建）
    old = pd.read_parquet(snap_path)
    old_keys = set(zip(old["code"].astype(str), old["date"].astype(str)))
    rows = []
    for code, (dates, cums) in fq.items():
        for d, c in zip(dates, cums):
            if (code, d) not in old_keys:
                rows.append({"code": code, "date": d, "cum": c})
    if not rows:
        print("[fq] 复权因子快照无新增")
        return
    new = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
    new = new.sort_values(["code", "date"]).reset_index(drop=True)
    new.to_parquet(snap_path, index=False)
    print(f"[fq] 快照追加 {len(rows)} 行（新除权日），共 {len(new):,} 行")


def main() -> None:
    parser = argparse.ArgumentParser(description="stockdb -> Parquet A 股日线数据仓导出")
    parser.add_argument("--out", default="data/stockdb_ashare", help="输出目录")
    parser.add_argument("--start", default=START_DEFAULT, help="起点 YYYYMMDD，默认 20110101")
    parser.add_argument("--end", default=None, help="终点 YYYYMMDD，默认今天")
    parser.add_argument("--since", default=None,
                        help="增量模式：只取 since 次日 ~ end 的新 bar 合并进现有 daily.parquet"
                             "（YYYYMMDD，通常传现有数据的最后交易日；需 daily.parquet 已存在）")
    parser.add_argument("--prefixes", default="0,3,6", help="证券前缀，默认 0,3,6（北交所 9 可选）")
    parser.add_argument("--limit", type=int, default=None, help="测试模式：只取前 N 只")
    parser.add_argument("--codes-file", default=None, help="只导出该文件列出的 6 位代码")
    parser.add_argument("--stages", default="daily,calendar,securities,industry", help="逗号分隔阶段")
    args = parser.parse_args()

    end = args.end or _today_int()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stages = {s.strip() for s in args.stages.split(",") if s.strip()}

    print(f"[init] stockdb 导出：{args.start} ~ {end}，输出 {out_dir}")
    try:
        import stock_sdk

        stock_sdk.init(socket_timeout=30)
        rd = stock_sdk.rd
    except Exception as exc:  # noqa: BLE001
        print(f"[init] 无法连接 stockdb（确认 stockdb.exe 在 127.0.0.1:7899 运行）: {exc}")
        sys.exit(1)

    prefixes = [p.strip() for p in args.prefixes.split(",") if p.strip()]
    codes = _resolve_codes(rd, prefixes, args.limit, args.codes_file)
    if not codes:
        print("[init] 没有可导出的证券代码")
        sys.exit(1)

    manifest: dict = {
        "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "start": args.start,
        "end": end,
        "prefixes": prefixes,
        "n_codes": len(codes),
        "calibration": "hfq = raw_close x 当日累计复权因子; turnover(%); amount(元); volume(股); industry 为当前申万一级",
    }

    delisted: set[str] = set()
    try:
        # 退市表为历史记录流（"退市:seq:*"，同 code 多条），去重后为唯一退市代码集。
        delisted = {str(c) for c in rd.vals("退市", "*", "*")}
        manifest["n_delisted"] = len(delisted)
    except Exception as exc:  # noqa: BLE001
        print(f"[securities] 读取退市表失败: {exc}")

    daily_rows = 0
    if "daily" in stages:
        fq = _load_fq_cums(rd)
        print(f"[daily] 复权因子覆盖 {len(fq)} 只")
        if args.since:
            # ── 增量模式：只取 since 之后的新 bar，流式合并进现有 daily.parquet ──
            daily_path = out_dir / "daily.parquet"
            if not daily_path.exists():
                print(f"[incr] 找不到 {daily_path}，增量模式需先有全量导出；改用全量")
            else:
                since = args.since
                # since 语义 = 现有数据的最后交易日，取数从其次日开始（避免 since 当天重复导入）
                since_dt = pd.Timestamp(since)
                since_next = (since_dt + pd.Timedelta(days=1)).strftime("%Y%m%d")
                # 更新复权因子快照（增量区间内除权日的新 cum 行）
                _update_fq_snapshot(fq, out_dir)
                new_df = _fetch_new_rows(rd, codes, since_next, end, fq)
                print(f"[incr] 取到新行 {len(new_df):,}（{since_next} 起），开始流式合并…")
                t0 = time.time()
                daily_rows = _merge_incremental(daily_path, new_df)
                print(f"[incr] 合并完成：总行数 {daily_rows:,}，IO 耗时 {time.time()-t0:.0f}s")
                manifest["mode"] = "incremental"
                manifest["since"] = since
                # calendar 由 daily 日期并集重推（只读 date 列，小内存）
                import pyarrow.compute as pc
                import pyarrow.parquet as pq
                dates = pc.unique(pq.read_table(daily_path, columns=["date"])["date"]).to_pylist()
                cal = pd.DataFrame({"trade_date": sorted(pd.Timestamp(d).strftime("%Y-%m-%d") for d in dates)})
                cal.to_parquet(out_dir / "calendar.parquet", index=False)
                print(f"[calendar] {len(cal)} 个交易日（增量后重推）")
                manifest["daily_rows"] = daily_rows
                # 增量模式跳过 securities/industry（对收益计算无影响；需要时用全量模式刷新）
                (out_dir / "manifest.json").write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print("[done] manifest:", json.dumps(manifest, ensure_ascii=False))
                return
        daily_rows = _export_daily(rd, codes, args.start, end, out_dir, fq)
        manifest["daily_rows"] = daily_rows

    daily_exists = (out_dir / "daily.parquet").exists()
    if "calendar" in stages and daily_exists:
        _export_calendar(out_dir)

    if "securities" in stages and daily_exists:
        _export_securities(delisted, out_dir)

    if "industry" in stages:
        _export_industry(rd, codes, out_dir)

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("[done] manifest:", json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()