# agent/scripts agent 开发与能力维护脚本

本目录只保留 **agent 自身的开发与能力维护脚本**：项目原有的三个开发脚本 +
能力注册表同步生成器。数据抓取/导出类脚本（CSI300 成分股、K 线抓取、stockdb 导出）
已整体迁至仓库根 `scripts/`（见 `scripts/README.md`），两目录以此为界，同一套配套
工作流不再拆散。

## 目录结构

```text
agent/scripts/
├── README.md
├── sync_backtest_capabilities.py   # 能力注册表 → MCP/skill/文档 同步生成器
├── bench_performance.py            # 原有：运算符/权益路径性能基准
├── w4a_run_benches.py              # 原有：alpha zoo × universe 基准驱动
└── w4a_patch_blog.py               # 原有：基准博客 HTML 补丁（与 w4a_run_benches 配套）
```

## 脚本说明

- **sync_backtest_capabilities.py**：从 `src/backtest_capabilities.py` 的单一注册表生成
  MCP server instructions、vibe-trading-bridge skill 能力索引和 HowToUse/README 能力块；
  `--check` 检测生成物漂移。用法：

  ```powershell
  E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe agent/scripts/sync_backtest_capabilities.py
  E:\gitCloneProgram\vibe-trading-src\.venv\Scripts\python.exe agent/scripts/sync_backtest_capabilities.py --check
  ```

- **bench_performance.py**：性能基准，对比新旧 operator/equity 路径（开发专用，
  不随包发布）。运行：`python agent/scripts/bench_performance.py`。

- **w4a_run_benches.py**：跑 4 组 alpha zoo × universe 基准，产出 HTML/JSON 报告到
  `~/.vibe-trading/reports/`；配套的博客补丁 `w4a_patch_blog.py` 留在本目录与它保持配套。

- **w4a_patch_blog.py**：读取 `~/.vibe-trading/reports/bench_summary.json`
  （`w4a_run_benches.py` 产出），幂等地把 alpha 博客 HTML 的 TBD 占位替换为真实结果。

## 已迁至 scripts/ 的内容（2026-09-05）

以下脚本原在本目录，已整体迁至仓库根 `scripts/`，结构与用法见 `scripts/README.md`：

- `lib/fetch_kline.py` → `scripts/lib/fetch_kline.py`
- `lib/get_csi300_constituents.py` → `scripts/lib/get_csi300_constituents.py`
- `run/run_fetch_csi300_kline.py` → `scripts/run/run_fetch_csi300_kline.py`
- `scripts/export_stockdb_ashare.py`（初版在 agent/scripts，V048 新写，一并迁出）