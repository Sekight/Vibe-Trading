"""LLM-backed analysis report generation (analysis.md + analysis.status.json).

Both the agent tool and the direct runner path call
:func:`generate_analysis_report`; the caller only supplies ``generated_by`` so
the status file records which writer produced the report (single-writer rule).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from backtest.analysis.digest import load_digest, render_digest_for_llm

ANALYSIS_MD_FILENAME = "analysis.md"
ANALYSIS_STATUS_FILENAME = "analysis.status.json"
ANALYSIS_PROMPT_FILENAME = "analysis.prompt.md"

SYSTEM_PROMPT = """你是一名专业的量化交易策略审阅分析师。你会收到一份回测摘要（digest），任务是基于摘要写一份 Markdown 分析报告。

硬性要求：
1. 只使用摘要中给出的数字，绝不编造或外推任何指标、交易或行情数据。
2. 结构固定：## 一句话结论 / ## 结论详解 / ## 指标解读 / ## 交易行为诊断 / ## 交易环境分析 / ## 稳健性验证 / ## 风险与改进建议。
3. 结论详解要解释结论的依据和主要矛盾，不能只重复结论。
4. 指标解读必须覆盖摘要中全部指标，按“性能 / 基准相对 / 风险 / 仓位与换手 / 再平衡”分组逐项解读，不得遗漏，也不要只挑好看的数字；指标表格必须保留摘要给出的“指标 | 含义 | 值”三列，含义列内容以摘要为准不得改写；结合分组说明指标之间的一致或矛盾。
5. 交易行为诊断基于交易概览、持仓分桶、月度损益、MAE/MFE 等摘要数据；数据缺失时写“无数据”，不要补一个看似合理的值。
6. 交易环境分析基于 Beta 回归、Regime 分析等摘要数据，解释交易发生的市场环境（系统性暴露程度、高相关 FUSED 状态）对收益的影响，不重复交易行为结论；数据缺失时写“无数据”。
7. 稳健性验证基于蒙特卡洛等摘要数据，评估结论在统计上的可靠性（样本量、p 值、模拟区间），只做稳健性判断，不要把 p 值当作交易行为；数据缺失时写“无数据”。
8. 风险与改进建议要可执行，明确指出最需要监控或修改的规则。
9. 用中文输出，数字保留摘要原值；表格用 Markdown 管道表；列表一律用 Markdown 有序列表，每条单独一行，不要把所有条目挤在同一段落。
10. 全文控制在 1200-2500 字，结论必须直接、可执行，不要空话。"""


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_analysis_status(
    run_dir: Path,
    status: str,
    *,
    generated_by: str,
    error: Optional[str] = None,
    llm_usage: Optional[Dict[str, Any]] = None,
    reproducibility: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write analysis.status.json with a strict JSON-safe payload."""
    payload: Dict[str, Any] = {
        "status": status,
        "generated_by": generated_by,
        "generated_at": _iso_now(),
    }
    if error:
        payload["error"] = str(error)[:500]
    if llm_usage:
        payload["llm_usage"] = llm_usage
    if reproducibility:
        payload["config_hash"] = reproducibility.get("config_hash")
        payload["strategy_hash"] = reproducibility.get("strategy_hash")
    path = Path(run_dir) / ANALYSIS_STATUS_FILENAME
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return payload


def _default_llm_call(prompt: str):
    """Call the configured provider synchronously with the analysis prompt.

    Returns ``(content, usage_metadata)`` so the caller can persist real token
    usage when the provider reports it."""
    from src.providers.chat import ChatLLM  # noqa: PLC0415

    timeout = int(os.getenv("VIBE_TRADING_ANALYSIS_TIMEOUT", "120"))
    response = ChatLLM().chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        timeout=timeout,
    )
    content = (response.content or "").strip()
    if not content:
        raise RuntimeError("LLM returned an empty analysis")
    return content, response.usage_metadata


def _coerce_llm_result(result: Any):
    """Accept ``(content, usage)`` or plain ``content`` from an injected call."""
    if isinstance(result, tuple) and len(result) == 2:
        content, usage = result
        return content, (usage if isinstance(usage, dict) else None)
    return result, None


def generate_analysis_report(
    run_dir: Path,
    *,
    generated_by: str = "runner",
    llm_call: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    """Generate analysis.md + analysis.status.json for a completed run.

    LLM failures are recorded as ``status: failed`` and never re-raised so a
    successful backtest is never downgraded by an analysis failure.

    Args:
        run_dir: Run directory containing run_card.json / artifacts.
        generated_by: ``"agent"`` or ``"runner"`` (single-writer provenance).
        llm_call: Optional callable ``(prompt) -> markdown`` for tests.
    """
    run_dir = Path(run_dir)
    run_card = run_dir / "run_card.json"
    metrics = run_dir / "artifacts" / "metrics.csv"
    if not run_card.exists() or not metrics.exists():
        payload = write_analysis_status(
            run_dir,
            "skipped",
            generated_by=generated_by,
            error="run_card.json or artifacts/metrics.csv missing",
        )
        return {"status": "skipped", "meta": payload}

    try:
        digest = load_digest(run_dir)
        prompt = render_digest_for_llm(digest)
        digest_sha256 = hashlib.sha256(
            json.dumps(digest, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        (run_dir / ANALYSIS_PROMPT_FILENAME).write_text(prompt, encoding="utf-8")
        print(json.dumps({
            "analysis_prompt": {
                "path": str(run_dir / ANALYSIS_PROMPT_FILENAME),
                "digest_sha256": digest_sha256,
                "prompt_chars": len(prompt),
                "prompt_lines": prompt.count("\n") + 1,
            }
        }, ensure_ascii=False))
        content, llm_usage = _coerce_llm_result((llm_call or _default_llm_call)(prompt))
        if not content or not content.strip():
            raise RuntimeError("LLM returned an empty analysis")
        header = (
            "> generated_by: {generated_by}\n"
            "> generated_at: {generated_at}\n"
            "> run_id: {run_id}\n\n"
        ).format(
            generated_by=generated_by,
            generated_at=_iso_now(),
            run_id=run_dir.name,
        )
        (run_dir / ANALYSIS_MD_FILENAME).write_text(
            header + content.strip() + "\n",
            encoding="utf-8",
        )
        payload = write_analysis_status(
            run_dir,
            "ok",
            generated_by=generated_by,
            reproducibility=digest.get("reproducibility") or {},
            llm_usage=llm_usage,
        )
        return {"status": "ok", "meta": payload}
    except Exception as exc:  # noqa: BLE001 - analysis is best-effort by design
        payload = write_analysis_status(
            run_dir,
            "failed",
            generated_by=generated_by,
            error=str(exc),
        )
        return {"status": "failed", "error": str(exc)[:500], "meta": payload}
