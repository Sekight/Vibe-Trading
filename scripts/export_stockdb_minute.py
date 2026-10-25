"""stockdb -> Parquet A 股分钟线数据仓导出工具（stockdb_ashare 日线仓的分钟版）。

把本地 stockdb 服务（127.0.0.1:7899）`分钟k` 表的 1 分钟 K 线导出为与日线数据仓
（stockdb_ashare）同风格的 Parquet，按年分文件，供 vibe-trading 因子研究/回测加载。

实测数据边界（2026-09-25，以当次导出 manifest 为准）：
  - 粒度：1 分钟，每日 241 根（上午 09:30:00-11:30:00 + 下午 13:00:00-15:00:00，
    stockdb 原生分钟戳，首根 09:30:00、末根 15:00:00）；
  - 起点：2025-01-02（stockdb 分钟数据最早从 2025 年开始，2014-2024 实测为空）；
  - 终点：随同步浮动。历史段（data/ 一次性包）到包快照日；近期段随 data1 增量包
    更新——data1 是滑动窗口，每次 数据更新.exe 会替换旧窗口文件，窗口外未导出的
    近期 K 线会丢失，故同步后应尽早运行本脚本；
  - 单根字段：code/date/open/high/low/close/volume/amount（无日线专有字段如
    pre_close/turnover/is_st）。

运行前提：
  - stockdb.exe 正在运行（127.0.0.1:7899）；
  - PYTHONPATH 指向 stockdb 的 pybao 目录（import stock_sdk）；
  - pandas + pyarrow（vibe-trading venv）。

用法示例（vibe-trading 仓库根目录，Git Bash）：
  PYTHONPATH=E:/data/free-stockdb-windows-v0.3.2-more-power/stockdb/pybao \\
    python scripts/export_stockdb_minute.py --out data/stockdb_minute --start 20250101

常用参数：
  --start 20250101       起点 YYYYMMDD（stockdb 分钟数据自 2025-01 起）
  --end   20260924       终点 YYYYMMDD（默认今天；最新一日可能是部分覆盖）
  --prefixes 0,3,6       证券前缀：0=深A、3=创业板、6=沪A（默认同日线仓）；9=北交所
  --codes 000001,600633  只导指定代码（试跑/补数）
  --limit N              只取前 N 只（测试模式）
  --no-fq                不追加后复权列（默认复用 stockdb_ashare/fq_factor.parquet）
  --fq-file PATH         复权因子快照路径（默认 data/stockdb_ashare/fq_factor.parquet）
  --shard-rows N         单分片行数（默认 2,000,000）

产物（out 目录下）：
  minute_YYYY.parquet  按年分文件；行序 = 分片写入顺序（代码块），片内按 (date,time,code) 升序
                       （与 daily.parquet 的分片拼接布局一致）
  manifest.json        导出元信息（窗口/行数/复权口径/实测边界）

口径说明：
  - 列与日线仓对齐：date=交易日(datetime64)、time=HHMMSS(int64)、code、OHLC 原始价（元）、
    volume（股）、amount（元）；
  - 分钟 bar 为 stockdb 原始值（不复权）；*_hfq = 原始价 × 当日累计复权因子
    （按交易日 bisect 取 ≤当日最近因子，与日线仓同式 raw/(1.0/cum)）；
  - 源头怪癖：stockdb 分钟值行原始字段序为 open,close,high,low（非 o/h/l/c），
    本脚本已按实测纠正；部分交易日有 242 根（多一根 13:00:00 零成交 bar，午间快照），
    个别分钟键值为空（无成交），已跳过；
  - 幂等：同参数重跑覆盖旧文件；失败不中断已写分片。
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
import time
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

COLUMNS = ["date", "time", "code", "open", "high", "low", "close", "volume", "amount"]
# stockdb 分钟值行原始顺序（实测 2026-09-25，用 o/c/h/l 互不相等的 bar 钉死）：
# [code, date14, open, close, high, low, volume, amount] —— 注意 close 在 high 之前！
ROW_FIELDS = ["code", "date14", "open", "close", "high", "low", "volume", "amount"]
ROW_WIDTH = 8


def _today_int() -> str:
    return time.strftime("%Y%m%d")


def _resolve_codes(
    rd,
    prefixes: list[str],
    limit: int | None,
    codes_file: str | None,
    codes_arg: str | None,
) -> list[str]:
    """证券清单：--codes 直接指定 > 白名单文件 > 股票代码表前缀；再叠加 --limit。"""
    if codes_arg:
        codes = [c.strip() for c in codes_arg.split(",") if c.strip().isdigit()]
        print(f"[securities] --codes 指定 {len(codes)} 只: {codes}")
    elif codes_file:
        raw = [ln.strip() for ln in Path(codes_file).read_text(encoding="utf-8").splitlines()]
        codes = [c for c in raw if c.isdigit() and len(c) == 6]
        print(f"[securities] 白名单文件共 {len(codes)} 只")
    else:
        table = rd.get("股票代码")
        codes: list[str] = []
        for p in prefixes:
            codes.extend(str(c) for c in table.get(p, []))
        print(f"[securities] 前缀 {prefixes} 共 {len(codes)} 只")
    if limit:
        codes = codes[:limit]
        print(f"[securities] --limit {limit}，取前 {len(codes)} 只")
    return codes


def _load_fq(fq_file: Path | None) -> dict[str, tuple[list[str], list[float]]]:
    """复权因子快照：code -> (除权日升序表, cum 表)。来自日线仓 fq_factor.parquet。

    注意：表里只存除权日的 cum，使用时按交易日 bisect 取"≤当日最近因子"（与日线仓同式）。
    """
    candidates = (
        [fq_file] if fq_file else
        [Path("data/stockdb_ashare/fq_factor.parquet"), Path("E:/data/stockdb_ashare/fq_factor.parquet")]
    )
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        print(f"[fq] 找不到复权因子快照（试过 {candidates}），跳过后复权列（--fq-file 可指定路径）")
        return {}
    df = pd.read_parquet(path)
    df["date"] = df["date"].astype(str)
    out: dict[str, tuple[list[str], list[float]]] = {}
    for code, sub in df.groupby("code"):
        sub = sub.sort_values("date")
        out[str(code)] = (sub["date"].tolist(), sub["cum"].astype(float).tolist())
    print(f"[fq] 复权因子覆盖 {len(out)} 只（{path}）")
    return out


def _fetch_minute(rd, code: str, start: str, end: str, retries: int = 3) -> list[list]:
    """单股全窗口分钟行 -> [code, date14, o, h, l, c, v, a]（时间降序）。

    vals() 元素为 [完整键名, 值行] 嵌套，取 item[1]；兼容直接返回值行的形态。
    """
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            res = rd.get("分钟k", code, f"{start}<{end}")
            raw = res.vals() if hasattr(res, "vals") else res
            rows = []
            for item in raw or []:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    raise ValueError(f"分钟行结构异常: {item!r}")
                val = item[1]
                if val is None or (isinstance(val, (list, tuple)) and not val):
                    continue  # 键存在但值为空的分钟（无成交记录），跳过
                if not isinstance(val, (list, tuple)) or len(val) != ROW_WIDTH:
                    raise ValueError(f"分钟行宽度异常: {len(val) if hasattr(val, '__len__') else '?'} != {ROW_WIDTH}，{item[0]}")
                rows.append(list(val))
            return rows
        except Exception as exc:  # noqa: BLE001 - 连接层错误重试
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(1 + attempt)
    print(f"[minute] {code} 失败(重试 {retries} 次): {last_exc}")
    return []


def _rows_to_df(rows: list[list], fq_entry: tuple[list[str], list[float]] | None) -> pd.DataFrame:
    """原始行 -> 标准列；fq_entry 非空时追加 *_hfq（按 bar 所属交易日 bisect 取累计因子）。"""
    df = pd.DataFrame(rows, columns=ROW_FIELDS)
    # date14 可能被推断为 float（个别行缺字段），先显式归一为 int64（2e13 < 2^53，无精度损失）
    d14 = pd.to_numeric(df["date14"]).astype("int64")
    df["date"] = pd.to_datetime((d14 // 1_000_000).astype(str), format="%Y%m%d")
    df["time"] = d14 % 1_000_000
    df = df.drop(columns=["date14"])
    for f in ("open", "high", "low", "close", "amount"):
        df[f] = pd.to_numeric(df[f]).astype("float64")
    df["volume"] = pd.to_numeric(df["volume"]).fillna(0).astype("int64")
    if fq_entry:
        dates, cums = fq_entry
        days = df["date"].dt.strftime("%Y%m%d")
        cum_map = {}
        for d in days.unique():
            i = bisect.bisect_right(dates, d) - 1
            cum_map[d] = cums[i] if i >= 0 else 1.0
        cum = days.map(cum_map)
        scale = 1.0 / cum  # 与日线仓同式：hfq = raw / (1.0/cum)
        for fld in ("open", "high", "low", "close"):
            df[f"{fld}_hfq"] = (df[fld] / scale).round(2)
    return df[COLUMNS + ([f"{f}_hfq" for f in ("open", "high", "low", "close")] if fq_entry else [])]


def _export(rd, codes: list[str], start: str, end: str, out_dir: Path, fq: dict, shard_rows: int) -> dict:
    """逐股取数 -> 按年缓冲 -> 满片落盘 -> 收尾各年流式合并。返回统计 dict。"""
    has_fq = bool(fq)
    buffers: dict[int, list[pd.DataFrame]] = {}
    shard_counts: dict[int, int] = {}
    year_rows: dict[int, int] = {}
    buffered: dict[int, int] = {}
    total_rows = 0
    n_with_data = 0
    t0 = time.time()

    def flush(year: int, force: bool = False) -> None:
        if year not in buffers or not buffers[year]:
            return
        if not force and buffered.get(year, 0) < shard_rows:
            return
        df = pd.concat(buffers[year], ignore_index=True).sort_values(["date", "time", "code"])
        n = shard_counts.get(year, 0)
        shard = out_dir / f"minute_{year}_shard_{n:03d}.parquet"
        df.to_parquet(shard, index=False)
        shard_counts[year] = n + 1
        buffers[year] = []
        buffered[year] = 0

    for i, code in enumerate(codes):
        rows = _fetch_minute(rd, code, start, end)
        if rows:
            n_with_data += 1
            df = _rows_to_df(rows, fq.get(code) if has_fq else None)
            for year, sub in df.groupby(df["date"].dt.year):
                y = int(year)
                buffers.setdefault(y, []).append(sub)
                buffered[y] = buffered.get(y, 0) + len(sub)
                year_rows[y] = year_rows.get(y, 0) + len(sub)
                total_rows += len(sub)
                flush(y)
        if (i + 1) % 100 == 0 or i == len(codes) - 1:
            el = time.time() - t0
            done = i + 1
            eta = el / done * (len(codes) - done) / 60 if done else 0
            print(
                f"[minute] {done}/{len(codes)} 只，{el / done:.2f}s/只，累计 {el:.0f}s，"
                f"ETA {eta:.0f}min，行数 {total_rows:,}"
            )

    # 收尾：各年剩余缓冲落为末片，再流式合并为 minute_YYYY.parquet
    for y in sorted(buffers):
        flush(y, force=True)
    files: dict[str, dict] = {}
    for y in sorted(shard_counts):
        shards = sorted(out_dir / f"minute_{y}_shard_{n:03d}.parquet" for n in range(shard_counts[y]))
        target = out_dir / f"minute_{y}.parquet"
        schema = pq.read_schema(shards[0])
        with pq.ParquetWriter(target, schema) as writer:
            for shard in shards:
                writer.write_table(pq.read_table(shard))
        for shard in shards:
            shard.unlink()
        files[str(y)] = {"rows": year_rows.get(y, 0), "shards": shard_counts[y]}
        print(f"[merge] minute_{y}.parquet <- {shard_counts[y]} 片，{year_rows.get(y, 0):,} 行")
    return {
        "total_rows": total_rows,
        "n_codes_with_data": n_with_data,
        "per_year": files,
        "elapsed_sec": round(time.time() - t0, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="stockdb -> Parquet A 股分钟线数据仓导出")
    parser.add_argument("--out", default="data/stockdb_minute", help="输出目录")
    parser.add_argument("--start", default="20250101", help="起点 YYYYMMDD，stockdb 分钟数据自 2025-01 起")
    parser.add_argument("--end", default=None, help="终点 YYYYMMDD，默认今天")
    parser.add_argument("--prefixes", default="0,3,6", help="证券前缀，默认 0,3,6（北交所 9 可选）")
    parser.add_argument("--codes", default=None, help="逗号分隔的 6 位代码，只导这些（试跑/补数）")
    parser.add_argument("--limit", type=int, default=None, help="测试模式：只取前 N 只")
    parser.add_argument("--codes-file", default=None, help="只导出该文件列出的 6 位代码")
    parser.add_argument("--no-fq", action="store_true", help="不追加 *_hfq 后复权列")
    parser.add_argument("--fq-file", default=None,
                        help="复权因子快照路径（默认依次尝试 data/stockdb_ashare/ 与 E:/data/stockdb_ashare/）")
    parser.add_argument("--shard-rows", type=int, default=2_000_000, help="单分片行数")
    args = parser.parse_args()

    end = args.end or _today_int()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[init] stockdb 分钟导出：{args.start} ~ {end}，输出 {out_dir}")
    try:
        import stock_sdk

        stock_sdk.init(socket_timeout=60)
        rd = stock_sdk.rd
    except Exception as exc:  # noqa: BLE001
        print(f"[init] 无法连接 stockdb（确认 stockdb.exe 在 127.0.0.1:7899 运行）: {exc}")
        sys.exit(1)

    codes = _resolve_codes(rd, [p.strip() for p in args.prefixes.split(",") if p.strip()],
                           args.limit, args.codes_file, args.codes)
    if not codes:
        print("[init] 没有可导出的证券代码")
        sys.exit(1)

    fq = {} if args.no_fq else _load_fq(Path(args.fq_file) if args.fq_file else None)

    stats = _export(rd, codes, args.start, end, out_dir, fq, args.shard_rows)

    manifest = {
        "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "start": args.start,
        "end": end,
        "prefixes": [p.strip() for p in args.prefixes.split(",") if p.strip()],
        "n_codes": len(codes),
        "n_codes_with_data": stats["n_codes_with_data"],
        "granularity": "1m",
        "bar_stamp": "stockdb 原生分钟戳：每日 241 根，首根 09:30:00、末根 15:00:00",
        "fq": "hfq = raw x 当日累计复权因子（按交易日，来自日线仓 fq_factor.parquet）" if fq else "无（原始价）",
        "total_rows": stats["total_rows"],
        "per_year": stats["per_year"],
        "elapsed_sec": stats["elapsed_sec"],
        "note": "分钟数据起点为 2025-01-02（实测更早年份为空）；最新一日可能为部分覆盖，"
                "data1 增量为滑动窗口，同步后请尽早导出",
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("[done] manifest:", json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
