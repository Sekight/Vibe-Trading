"""通用 K 线抓取脚本：复用 Vibe-Trading 的 fetch_data_map 数据层。

功能：
- 对一组标的（如 600519.SH / 000300.SH）抓取指定区间日线/任意 Vibe-Trading
  支持周期，默认 source=auto，自动走腾讯 -> 东财 -> baostock 等兜底链。
- 每个标的单独调用 fetch_data_map，单标的失败不会中断整批，失败清单会落盘。
- 输出为每标的一个 parquet（out_dir/kline/<code>.parquet），另写 manifest.json。
- --append 增量模式：读取已有 parquet/csv，只联网补头尾缺口并合并去重，
  多标的同时生效，已完整覆盖的标的不再联网。

用法（建议在 vibe-trading-src 仓库根目录用 venv python 运行）：
    E:\\gitCloneProgram\\vibe-trading-src\\.venv\\Scripts\\python.exe agent/scripts/lib/fetch_kline.py --codes 600519.SH,000001.SZ --start-date 2025-01-01 --end-date 2025-12-31 --out-dir C:/tmp/kline --source auto

    # 从文件读标的（每行一个代码，多个标的一起抓）
    E:\\gitCloneProgram\\vibe-trading-src\\.venv\\Scripts\\python.exe agent/scripts/lib/fetch_kline.py --codes-file universe.txt --start-date 2025-01-01 --end-date 2025-12-31 --out-dir C:/tmp/kline

    # 增量补齐：600519.SH、600300.SH 已有旧区间，只下载缺失的头尾
    E:\\gitCloneProgram\\vibe-trading-src\\.venv\\Scripts\\python.exe agent/scripts/lib/fetch_kline.py --append --codes 600519.SH,600300.SH --start-date 2018-01-02 --end-date 2025-12-31 --out-dir C:/tmp/kline

说明：
- agent 目录默认按本文件位置推导（agent/scripts/lib -> agent），
  也可用环境变量 VIBE_TRADING_SRC 覆盖仓库根目录。
- 写 parquet 需要 pyarrow；未安装时自动降级为 CSV，并在日志中提示。
- append 只补头部/尾部缺口；如果怀疑旧文件中间缺数据，用普通模式整段重拉。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# 默认取本文件所在仓库根目录：agent/scripts/lib -> agent -> 仓库根。
_DEFAULT_SRC_ROOT = Path(__file__).resolve().parents[2].parent
_SRC_ROOT = Path(os.environ.get("VIBE_TRADING_SRC", str(_DEFAULT_SRC_ROOT)))
_AGENT_DIR = _SRC_ROOT / "agent"


@dataclass
class FetchKlineResult:
    """一次抓取任务的汇总结果。"""

    out_dir: Path
    saved: dict[str, int] = field(default_factory=dict)  # code -> row count
    failed: list[str] = field(default_factory=list)
    already_covered: list[str] = field(default_factory=list)
    gap_skipped: list[str] = field(default_factory=list)
    effective_sources: list[str] = field(default_factory=list)
    manifest_path: Path | None = None

    @property
    def ok(self) -> bool:
        return bool(self.saved) and not self.failed


def _ensure_agent_on_path() -> None:
    """把 Vibe-Trading agent 目录加入 sys.path，用于 import backtest.runner。"""
    if str(_AGENT_DIR) not in sys.path:
        sys.path.insert(0, str(_AGENT_DIR))
    if not _AGENT_DIR.exists():
        raise FileNotFoundError(
            f"Vibe-Trading agent 目录不存在: {_AGENT_DIR}；"
            f"请设置环境变量 VIBE_TRADING_SRC 指向 vibe-trading-src"
        )


def _save_frame(frame, path: Path) -> str:
    """写 DataFrame 为 parquet，pyarrow 缺失时降级 CSV。返回实际文件类型。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        frame.to_parquet(path, index=True)
        return "parquet"
    except ImportError:
        logger.warning("pyarrow 未安装，%s 降级为 CSV", path.name)
        frame.to_csv(path.with_suffix(".csv"), index=True, encoding="utf-8-sig")
        return "csv"


def _load_existing(kline_dir: Path, code: str) -> Optional[pd.DataFrame]:
    """读取已有 parquet/csv；没有或损坏时返回 None。"""
    parquet_path = kline_dir / f"{code}.parquet"
    if parquet_path.exists():
        try:
            return pd.read_parquet(parquet_path)
        except Exception as exc:  # noqa: BLE001 - 旧文件损坏按无文件处理
            logger.warning("%s 已有 parquet 读取失败，按无文件处理: %s", code, exc)
            return None
    csv_path = kline_dir / f"{code}.csv"
    if csv_path.exists():
        try:
            return pd.read_csv(csv_path, index_col=0, parse_dates=True)
        except Exception as exc:  # noqa: BLE001 - 旧文件损坏按无文件处理
            logger.warning("%s 已有 csv 读取失败，按无文件处理: %s", code, exc)
            return None
    return None


def _missing_ranges(
    existing: Optional[pd.DataFrame], start_date: str, end_date: str
) -> list[tuple[str, str]]:
    """根据已有数据覆盖范围，计算需要联网补的头尾缺口。"""
    if existing is None or existing.empty:
        return [(start_date, end_date)]
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    first = pd.Timestamp(existing.index.min())
    last = pd.Timestamp(existing.index.max())
    gaps: list[tuple[str, str]] = []
    if start < first:
        gaps.append((start_date, (first - pd.Timedelta(days=1)).strftime("%Y-%m-%d")))
    if last < end:
        gaps.append(((last + pd.Timedelta(days=1)).strftime("%Y-%m-%d"), end_date))
    return gaps


def fetch_kline(
    codes: list[str],
    start_date: str,
    end_date: str,
    out_dir: str | Path,
    *,
    source: str = "auto",
    interval: str = "1D",
    append: bool = False,
) -> FetchKlineResult:
    """抓取一组标的的 K 线并落盘。

    Args:
        codes: Vibe-Trading 代码，如 ``600519.SH``、``000300.SH``。
        start_date: 含起始日 ``YYYY-MM-DD``。
        end_date: 含结束日 ``YYYY-MM-DD``。
        out_dir: 输出根目录，K 线写入 ``out_dir/kline/``。
        source: 数据源，默认 ``auto`` 走项目兜底链。
        interval: 周期，默认 ``1D``。
        append: 增量模式，只补已有文件头尾缺口；多标的一起生效。

    Returns:
        FetchKlineResult：成功/失败清单、已覆盖清单、实际生效数据源、manifest 路径。
    """
    _ensure_agent_on_path()
    from backtest.runner import fetch_data_map  # 延迟导入，便于 CLI 帮助等场景

    out_root = Path(out_dir)
    kline_dir = out_root / "kline"
    kline_dir.mkdir(parents=True, exist_ok=True)

    codes = [c.strip() for c in codes if c and c.strip()]
    if not codes:
        raise ValueError("codes 为空，至少需要一个标的")

    logger.info(
        "开始抓取 K 线：codes=%d start=%s end=%s source=%s interval=%s append=%s",
        len(codes), start_date, end_date, source, interval, append,
    )

    result = FetchKlineResult(out_dir=out_root)
    used_sources: set[str] = set()

    for idx, code in enumerate(codes, start=1):
        out_file = kline_dir / f"{code}.parquet"
        existing: Optional[pd.DataFrame] = None
        if append:
            existing = _load_existing(kline_dir, code)

        if existing is not None and not existing.empty:
            gaps = _missing_ranges(existing, start_date, end_date)
            if not gaps:
                result.already_covered.append(code)
                result.saved[code] = int(len(existing))
                logger.info(
                    "[%d/%d] %s 已完整覆盖 %s ~ %s，跳过联网",
                    idx, len(codes), code,
                    existing.index.min().date(), existing.index.max().date(),
                )
                continue

            parts: list[pd.DataFrame] = [existing]
            for gap_start, gap_end in gaps:
                config = {
                    "codes": [code],
                    "start_date": gap_start,
                    "end_date": gap_end,
                    "source": source,
                    "interval": interval,
                }
                try:
                    fetch_result = fetch_data_map(config)
                    frame = fetch_result.data_map.get(code)
                    if frame is None or frame.empty:
                        logger.warning(
                            "[%d/%d] %s 缺口 %s~%s 无数据，视为已覆盖",
                            idx, len(codes), code, gap_start, gap_end,
                        )
                        continue
                    parts.append(frame)
                    used_sources.update(fetch_result.effective_sources or [])
                    logger.info(
                        "[%d/%d] %s 补齐缺口 %s ~ %s rows=%d",
                        idx, len(codes), code, gap_start, gap_end, len(frame),
                    )
                except Exception as exc:  # noqa: BLE001 - 缺口失败时保留已有数据
                    result.gap_skipped.append(code)
                    logger.warning(
                        "[%d/%d] %s 补齐缺口 %s~%s 失败，保留已有数据: %s",
                        idx, len(codes), code, gap_start, gap_end, exc,
                    )
                    continue

            merged = pd.concat(parts)
            merged = merged[~merged.index.duplicated(keep="last")].sort_index()
            merged.index.name = "trade_date"
            fmt = _save_frame(merged, out_file)
            result.saved[code] = int(len(merged))
            logger.info(
                "[%d/%d] %s 增量合并完成 rows=%d range=%s~%s type=%s",
                idx, len(codes), code, len(merged),
                merged.index.min().date(), merged.index.max().date(), fmt,
            )
            continue

        config = {
            "codes": [code],
            "start_date": start_date,
            "end_date": end_date,
            "source": source,
            "interval": interval,
        }
        try:
            fetch_result = fetch_data_map(config)
            frame = fetch_result.data_map.get(code)
            if frame is None or frame.empty:
                logger.warning("[%d/%d] %s 无数据", idx, len(codes), code)
                result.failed.append(code)
                continue

            fmt = _save_frame(frame, out_file)
            result.saved[code] = int(len(frame))
            used_sources.update(fetch_result.effective_sources or [])
            logger.info(
                "[%d/%d] %s 保存成功 rows=%d file=%s type=%s",
                idx, len(codes), code, len(frame), out_file.name, fmt,
            )
        except Exception as exc:  # noqa: BLE001 - 单标的失败不应中断整批
            logger.warning("[%d/%d] %s 抓取失败: %s", idx, len(codes), code, exc)
            result.failed.append(code)

    result.effective_sources = sorted(used_sources)
    manifest = {
        "task": "fetch_kline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "append": append,
        "codes_requested": len(codes),
        "codes_saved": len(result.saved),
        "codes_failed": len(result.failed),
        "codes_already_covered": len(result.already_covered),
        "codes_gap_skipped": len(result.gap_skipped),
        "start_date": start_date,
        "end_date": end_date,
        "source": source,
        "interval": interval,
        "effective_sources": result.effective_sources,
        "rows_by_code": dict(sorted(result.saved.items())),
        "failed": sorted(result.failed),
        "already_covered": sorted(result.already_covered),
        "gap_skipped": sorted(result.gap_skipped),
        "out_dir": str(out_root.resolve()),
    }
    result.manifest_path = out_root / "manifest.json"
    result.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(
        "抓取完成 saved=%d failed=%d already_covered=%d effective_sources=%s manifest=%s",
        len(result.saved), len(result.failed), len(result.already_covered),
        result.effective_sources, result.manifest_path,
    )
    return result


def _read_codes(codes: str | None, codes_file: str | None) -> list[str]:
    if codes and codes_file:
        raise SystemExit("--codes 与 --codes-file 只能二选一")
    if codes_file:
        return [
            line.strip()
            for line in Path(codes_file).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    if codes:
        return [c.strip() for c in codes.split(",") if c.strip()]
    raise SystemExit("必须提供 --codes 或 --codes-file")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="复用 Vibe-Trading 数据层抓取 K 线并落盘 parquet"
    )
    parser.add_argument("--codes", help="逗号分隔的代码，如 600519.SH,000001.SZ")
    parser.add_argument("--codes-file", help="代码文件，每行一个")
    parser.add_argument("--start-date", required=True, help="起始日 YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="结束日 YYYY-MM-DD")
    parser.add_argument("--out-dir", required=True, help="输出目录")
    parser.add_argument("--source", default="auto", help="数据源，默认 auto")
    parser.add_argument("--interval", default="1D", help="周期，默认 1D")
    parser.add_argument("--append", action="store_true", help="增量补齐：只下载已有文件的头尾缺口并合并")
    args = parser.parse_args()

    result = fetch_kline(
        _read_codes(args.codes, args.codes_file),
        args.start_date,
        args.end_date,
        args.out_dir,
        source=args.source,
        interval=args.interval,
        append=args.append,
    )
    print(json.dumps({
        "saved": len(result.saved),
        "failed": result.failed,
        "already_covered": result.already_covered,
        "effective_sources": result.effective_sources,
        "manifest": str(result.manifest_path),
    }, ensure_ascii=False))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
