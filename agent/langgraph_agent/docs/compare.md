# P0-2 量化 Agent：线性 ReAct vs LangGraph 对比

> 生成时间：2026-10-25T17:51:59
> 模型：deepseek-chat；provider：deepseek；temperature：0.0
> 数据集：cases.jsonl（sha256 `907e37ee23453a9b`）
> git：`6e8c075`，dirty=True

## 指标

| 指标 | linear | graph |
|---|---:|---:|
| 单意图动作准确率 | 0.95 | 0.975 |
| 多意图动作集完全一致 | 0 | 1 |
| 多意图动作覆盖率 | 0.4333 | 1 |
| 枚举外动作率 | 0 | 0 |
| 平均执行步数 | 0.978 | 1.156 |
| 平均 LLM 调用次数 | 1 | 1 |
| 平均 Token | 1233.2 | 679.8 |
| P95 延迟（ms） | 1202.2 | 1458.21 |

> 分母：单意图 linear=40 / graph=40；多意图 linear=5 / graph=5。

## 分类型准确率

| 类型 | linear | graph |
|---|---:|---:|
| backtest | 1.0000 (8/8) | 1.0000 (8/8) |
| clarify | 0.8750 (7/8) | 1.0000 (8/8) |
| market_data | 1.0000 (8/8) | 1.0000 (8/8) |
| multi_intent | 0.0000 (0/5) | 1.0000 (5/5) |
| report | 0.8750 (7/8) | 0.8750 (7/8) |
| stop | 1.0000 (8/8) | 1.0000 (8/8) |

## 失败样本（最多 3 条/实现）

### linear

- `rp008` expected=['REPORT'] actual=['CLARIFY'] | 给 000858.SZ 的回测出一份文字报告
- `cl008` expected=['CLARIFY'] actual=['REPORT'] | 分析一下回测结果
- `m001` expected=['MARKET_DATA', 'BACKTEST'] actual=['MARKET_DATA'] | 拉 600519.SH 2024 日线，然后跑 20 日均线回测

### graph

- `rp005` expected=['REPORT'] actual=['CLARIFY'] | 对 300750.SZ 的回测做收益归因分析

## 诚实边界

- 45 条为合成语料，单轮、单模型；不能外推线上准确率。
- 评测模式使用 stub 工具（只记录动作，不真跑回测）；真实链路见 `live_demo.py`。
- 单意图准确率不应期待状态图更高；状态图的证据点在多意图、可中断、可恢复、可观测。
- 平均 Token 的差异部分来自输出契约：线性提示词携带 5 个工具 schema，状态图的 plan 提示词不携带工具 schema；这不是纯模型成本对比。
