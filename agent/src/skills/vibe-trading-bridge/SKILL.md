---
name: vibe-trading-bridge
description: Vibe-Trading 与外部 Agent 协作时的目录、策略生成、人工确认、回测和迭代边界。
category: tool
---

1. Vibe-Trading 的目录结构：策略 run 应有 config.json、code/signal_engine.py，以及由系统生成的 artifacts/、run_card.json 等结果文件。
2. config.json 的基本格式：由 Agent 配置数据源、标的、周期、日期、回测窗口、成本和当前三字段执行契约；start_date/end_date 用于加载行情并提供指标预热数据，backtest_start/backtest_end 用于实际交易与收益、回撤、metrics 统计（例如 MA300 要提前准备至少 300 根有效 K 线，策略仍需正确处理预热 bar）；同一真实标的若拆成多个执行 code，必须在 config.json.logical_groups 中归入同一 group，WebUI 才会按一个标的显示 K 线、持仓风险、交易筛选和统计；具体字段和允许值以当前引擎契约为准。
3. signal_engine.py 的接口要求：只实现 SignalEngine 及其 generate(data_map) 策略逻辑，遵守现有信号、索引和安全约束。
4. 可调用的 MCP 工具：先使用当前 MCP 注册表提供的工具；回测统一使用单一 backtest 入口，不自行假定已不存在的工具或参数。
5. 禁止修改回测引擎和数据加载器：市场规则、取数、成交、费用、artifacts 由 Vibe-Trading 负责。
6. 生成阶段与回测阶段必须分离：先完成策略代码和配置，再单独进行 MCP 回测、结果读取和后续分析。
7. 回测前必须经过人工确认：Agent 只能在用户确认策略逻辑、配置和执行模式后调用回测。
8. 回测后必须读取 trades.csv、positions.csv、metrics.csv：同时结合 equity.csv、run_card.json 检查逐笔交易、持仓和汇总指标。
9. 迭代时一次只改一个问题：每个变体使用独立 run 副本，记录改动、预期影响和实际结果。
10. 失败时禁止自动无限重试：先分类为配置、接口、数据、引擎或策略问题，报告阻塞原因并请求下一步决定。
