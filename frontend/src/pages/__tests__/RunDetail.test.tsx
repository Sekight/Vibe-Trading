import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { RunDetail } from "../RunDetail";
import type { RunData } from "@/lib/api";
import { echarts } from "@/lib/echarts";

const apiMock = vi.hoisted(() => ({
  getRun: vi.fn(),
  getRunCode: vi.fn(),
  getRunAnalysis: vi.fn(),
  getRunAnalysisCharts: vi.fn(),
  getRunPositionGroups: vi.fn(),
  getRunPositionGroupSeries: vi.fn(),
  fetchRunAnalysisPng: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ api: apiMock }));
vi.mock("@/components/charts/CandlestickChart", () => ({
  CandlestickChart: () => <div data-testid="candlestick-chart" />,
}));
vi.mock("@/components/charts/EquityChart", () => ({
  EquityChart: () => <div data-testid="equity-chart" />,
}));
vi.mock("@/lib/echarts", () => ({
  echarts: {
    init: vi.fn(() => ({
      setOption: vi.fn(),
      resize: vi.fn(),
      dispose: vi.fn(),
    })),
    getInstanceByDom: vi.fn(() => undefined),
  },
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

function renderRunDetail(path = "/runs/old") {
  const router = createMemoryRouter(
    [{ path: "/runs/:runId", element: <RunDetail /> }],
    { initialEntries: [path] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

describe("RunDetail page", () => {
  beforeEach(() => {
    apiMock.getRun.mockReset();
    apiMock.getRunCode.mockReset();
    apiMock.getRunAnalysis.mockReset();
    apiMock.getRunAnalysisCharts.mockReset();
    apiMock.getRunPositionGroups.mockReset();
    apiMock.getRunPositionGroupSeries.mockReset();
    apiMock.fetchRunAnalysisPng.mockReset();
  });

  it("does not let an older route load replace the current run or code", async () => {
    const oldRun = deferred<RunData>();
    const oldCode = deferred<Record<string, string>>();
    const newRun = deferred<RunData>();
    const newCode = deferred<Record<string, string>>();

    apiMock.getRun.mockImplementation((runId: string) => runId === "old" ? oldRun.promise : newRun.promise);
    apiMock.getRunCode.mockImplementation((runId: string) => runId === "old" ? oldCode.promise : newCode.promise);

    const router = renderRunDetail();
    await act(async () => { await router.navigate("/runs/new"); });

    await act(async () => {
      newRun.resolve({ status: "success", run_id: "new", prompt: "New run" });
      newCode.resolve({ "new.py": "NEW_CODE" });
      await Promise.all([newRun.promise, newCode.promise]);
    });
    expect(await screen.findByText("New run")).toBeInTheDocument();

    await act(async () => {
      oldRun.resolve({ status: "success", run_id: "old", prompt: "Old run" });
      oldCode.resolve({ "old.py": "OLD_CODE" });
      await Promise.all([oldRun.promise, oldCode.promise]);
    });

    expect(screen.getByText("New run")).toBeInTheDocument();
    expect(screen.queryByText("Old run")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Code" }));
    expect(await screen.findByText("NEW_CODE")).toBeInTheDocument();
    expect(screen.queryByText("OLD_CODE")).not.toBeInTheDocument();
  });

  it("ignores a chart response that finishes after the route changes", async () => {
    const oldChart = deferred<RunData>();
    apiMock.getRun.mockImplementation((runId: string, params: Record<string, string>) => {
      if (runId === "old" && params.chart_payload === "summary") {
        return Promise.resolve({ status: "success", run_id: "old", prompt: "Old run", chart_symbols: ["OLD"] });
      }
      if (runId === "old" && params.chart_symbol === "OLD") return oldChart.promise;
      return Promise.resolve({ status: "success", run_id: "new", prompt: "New run" });
    });
    apiMock.getRunCode.mockResolvedValue({});

    const router = renderRunDetail();
    expect(await screen.findByText("Old run")).toBeInTheDocument();
    await waitFor(() => {
      expect(apiMock.getRun).toHaveBeenCalledWith("old", { chart_symbol: "OLD" });
    });

    await act(async () => { await router.navigate("/runs/new"); });
    expect(await screen.findByText("New run")).toBeInTheDocument();

    await act(async () => {
      oldChart.resolve({
        status: "success",
        run_id: "old",
        chart_symbols: ["OLD"],
        trade_log: [{ note: "OLD TRADE" }],
      });
      await oldChart.promise;
    });

    expect(screen.getByText("New run")).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "OLD" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Trades" }));
    expect(screen.queryByText("OLD TRADE")).not.toBeInTheDocument();
  });

  it("exposes run status and tab state while keeping the trades table scrollable", async () => {
    apiMock.getRun.mockResolvedValue({
      status: "success",
      run_id: "accessible",
      prompt: "Accessible run",
      trade_log: [{
        time: "2026-07-29",
        code: "AAPL",
        side: "BUY",
        price: "200",
        qty: "2",
        reason: "signal",
      }],
    });
    apiMock.getRunCode.mockResolvedValue({});

    renderRunDetail("/runs/accessible");

    await screen.findByText("Accessible run");
    expect(screen.getByText("Completed")).toHaveClass("sr-only");
    expect(screen.getByRole("heading", { level: 1, name: "accessible" })).toHaveClass("text-2xl", "font-semibold");
    expect(screen.getByRole("tablist")).toBeInTheDocument();

    const chartTab = screen.getByRole("tab", { name: "Chart" });
    const tradesTab = screen.getByRole("tab", { name: "Trades" });
    expect(chartTab).toHaveAttribute("aria-selected", "true");
    expect(chartTab).toHaveClass("font-medium");
    expect(tradesTab).toHaveAttribute("aria-selected", "false");

    fireEvent.click(tradesTab);

    expect(tradesTab).toHaveAttribute("aria-selected", "true");
    expect(tradesTab).toHaveClass("font-medium");
    const table = screen.getByRole("table");
    expect(table.parentElement).toHaveClass("overflow-x-auto", "rounded-xl", "border");
    expect(screen.getByRole("columnheader", { name: "Time" })).toHaveClass("ps-4");
  });

  it("renders the commission column between return and holding days", async () => {
    apiMock.getRun.mockResolvedValue({
      status: "success",
      run_id: "commission",
      prompt: "Commission run",
      trade_log: [{
        time: "2026-07-29",
        code: "AAPL",
        side: "BUY",
        price: "200",
        qty: "2",
        pnl: "5",
        return_pct: "2.5",
        commission: "0.8",
        holding_days: "3",
        holding_bars: "3",
        reason: "signal",
      }],
    });
    apiMock.getRunCode.mockResolvedValue({});

    renderRunDetail("/runs/commission");

    await screen.findByText("Commission run");
    fireEvent.click(screen.getByRole("tab", { name: "Trades" }));

    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toEqual([
      "Time", "Code", "Side", "Price", "Qty",
      "P&L", "Return", "Commission", "Held (days)", "Held (bars)", "Reason",
    ]);
    expect(screen.getByText("0.8")).toBeInTheDocument();
  });

  it("loads all trades once, keeps the disabled state, and groups logical symbols", async () => {
    const makeTrade = (index: number) => {
      const variants = [
        { code: "TA0001.ZCE", side: "buy", pnl: "0", holding_bars: "0" },
        { code: "TA0002.ZCE", side: "sell", pnl: "0", holding_bars: "0" },
        { code: "TA0003.ZCE", side: "sell", pnl: "1", holding_bars: "1" },
        { code: "RB0001.ZCE", side: "buy", pnl: "-1", holding_bars: "1" },
      ];
      const variant = variants[index % variants.length];
      return {
        time: `2026-01-${String((index % 28) + 1).padStart(2, "0")}`,
        price: "100",
        qty: "1",
        reason: "signal",
        ...variant,
      };
    };
    const previewTrades = Array.from({ length: 120 }, (_, index) => makeTrade(index));
    const allTrades = Array.from({ length: 240 }, (_, index) => makeTrade(index));

    apiMock.getRun.mockResolvedValue({
      status: "success",
      run_id: "full-trades",
      prompt: "Full trades run",
      trade_log: previewTrades,
      artifacts_trades_csv: allTrades,
      chart_groups: [
        { logical_symbol: "TA_MAIN", display_name: "TA Main", codes: ["TA0001.ZCE", "TA0002.ZCE", "TA0003.ZCE"], chart_code: "TA0001.ZCE" },
        { logical_symbol: "RB_MAIN", display_name: "RB Main", codes: ["RB0001.ZCE"], chart_code: "RB0001.ZCE" },
      ],
    });
    apiMock.getRunCode.mockResolvedValue({});

    const router = renderRunDetail("/runs/full-trades");
    await screen.findByText("Full trades run");
    fireEvent.click(screen.getByRole("tab", { name: "Trades" }));

    expect(screen.getByText("120 trades")).toBeInTheDocument();
    const loadButton = screen.getByRole("button", { name: "Load all trades" });
    expect(loadButton).toBeEnabled();
    expect(loadButton).toHaveClass("border-border/60", "text-muted-foreground", "whitespace-normal", "max-w-[14rem]");
    expect(loadButton).not.toHaveClass("bg-primary/10", "text-primary");
    expect(loadButton.closest(".ms-auto")).toBeNull();
    expect(screen.getByRole("button", { name: "Show 20 more" })).toBeInTheDocument();

    fireEvent.click(loadButton);

    expect(await screen.findByText("240 trades")).toBeInTheDocument();
    const loadedButton = screen.getByRole("button", { name: "All 240 trades loaded" });
    expect(loadedButton).toBeDisabled();
    expect(screen.queryByRole("button", { name: /Show .* more/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole("row").length).toBeLessThan(240);

    const symbolSelect = screen.getByRole("combobox", { name: "Symbol" });
    expect(screen.getByRole("option", { name: "TA Main" })).toBeInTheDocument();
    fireEvent.change(symbolSelect, { target: { value: "TA_MAIN" } });
    expect(await screen.findByText("180 trades")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "All 240 trades loaded" })).toBeDisabled();

    fireEvent.click(screen.getByRole("tab", { name: "Chart" }));
    fireEvent.click(screen.getByRole("tab", { name: "Trades" }));
    expect(await screen.findByRole("button", { name: "All 240 trades loaded" })).toBeDisabled();
    expect(router.state.location.pathname).toBe("/runs/full-trades");
  });

  it("keeps the full trade source after switching the chart symbol", async () => {
    const previewTrades = [
      { time: "2026-01-01", code: "TA0001.ZCE", side: "buy", price: "100", qty: "1", pnl: "0", holding_bars: "0", reason: "signal" },
      { time: "2026-01-02", code: "TA0001.ZCE", side: "sell", price: "101", qty: "1", pnl: "1", holding_bars: "1", reason: "signal" },
    ];
    const allTrades = [...previewTrades, {
      time: "2026-01-03", code: "RB0001.ZCE", side: "buy", price: "200", qty: "1", pnl: "0", holding_bars: "0", reason: "signal",
    }];
    const chartGroups = [
      { logical_symbol: "TA_MAIN", display_name: "TA Main", codes: ["TA0001.ZCE"], chart_code: "TA0001.ZCE" },
      { logical_symbol: "RB_MAIN", display_name: "RB Main", codes: ["RB0001.ZCE"], chart_code: "RB0001.ZCE" },
    ];
    const summary = {
      status: "success",
      run_id: "chart-full-trades",
      prompt: "Chart full trades run",
      chart_symbols: ["TA0001.ZCE", "RB0001.ZCE"],
      chart_groups: chartGroups,
      price_series: { "TA0001.ZCE": [{ time: "2026-01-01", open: 100, high: 101, low: 99, close: 100, volume: 1 }] },
      trade_log: previewTrades,
      artifacts_trades_csv: allTrades,
    };
    apiMock.getRun.mockImplementation((_runId: string, params?: Record<string, string>) => {
      if (params?.chart_symbol) {
        return Promise.resolve({
          ...summary,
          price_series: { [params.chart_symbol]: [{ time: "2026-01-01", open: 200, high: 201, low: 199, close: 200, volume: 1 }] },
          artifacts_trades_csv: undefined,
        });
      }
      return Promise.resolve(summary);
    });
    apiMock.getRunCode.mockResolvedValue({});

    renderRunDetail("/runs/chart-full-trades");
    await screen.findByText("Chart full trades run");
    fireEvent.click(screen.getByRole("tab", { name: "Trades" }));
    fireEvent.click(screen.getByRole("button", { name: "Load all trades" }));
    expect(await screen.findByRole("button", { name: "All 3 trades loaded" })).toBeDisabled();

    fireEvent.click(screen.getByRole("tab", { name: "Chart" }));
    fireEvent.change(screen.getByLabelText("Symbol"), { target: { value: "RB0001.ZCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Show only" }));
    await waitFor(() => expect(apiMock.getRun).toHaveBeenCalledWith("chart-full-trades", { chart_symbol: "RB0001.ZCE" }));

    fireEvent.click(screen.getByRole("tab", { name: "Trades" }));
    expect(await screen.findByRole("button", { name: "All 3 trades loaded" })).toBeDisabled();
  });

  it("keeps ChartTab mounted when switching tabs (window/state preserved)", async () => {
    apiMock.getRun.mockResolvedValue({
      status: "success",
      run_id: "keepmount",
      prompt: "Keep mount run",
    });
    apiMock.getRunCode.mockResolvedValue({});

    renderRunDetail("/runs/keepmount");

    await screen.findByText("Keep mount run");
    // ChartTab 无数据占位（此前切走标签会卸载该占位）
    expect(screen.getByText("No chart data available")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Trades" }));
    // ChartTab 保持挂载 → 占位仍在 DOM（被 CSS 隐藏）
    expect(screen.getByText("No chart data available")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Chart" }));
    expect(screen.getByText("No chart data available")).toBeInTheDocument();
  });

  it("pads and scroll-wraps run-card key/value and artifact tables", async () => {
    apiMock.getRun.mockResolvedValue({
      status: "success",
      run_id: "card",
      prompt: "Run card",
      run_card: {
        backtest: { engine: "vectorized" },
        artifacts: [{ path: "artifacts/result.json", size_bytes: 42, sha256: "abc123" }],
      } as NonNullable<RunData["run_card"]>,
    });
    apiMock.getRunCode.mockResolvedValue({});

    renderRunDetail("/runs/card");

    await screen.findByText("Run card");
    fireEvent.click(screen.getByRole("tab", { name: "Run Card" }));

    const keyCell = await screen.findByText("engine");
    expect(keyCell).toHaveClass("ps-4");
    expect(keyCell.closest("table")?.parentElement).toHaveClass("overflow-x-auto");
    expect(screen.getByRole("columnheader", { name: "Path" })).toHaveClass("ps-4");
    expect(screen.getByText("artifacts/result.json")).toHaveClass("ps-4");
  });

  it("renders the analysis charts tab with ECharts payloads", async () => {
    apiMock.getRun.mockResolvedValue({
      status: "success", run_id: "an-charts", prompt: "Charts run",
    });
    apiMock.getRunCode.mockResolvedValue({});
    apiMock.getRunAnalysisCharts.mockResolvedValue({
      run_id: "an-charts",
      available: true,
      charts: {
        equity_return: [{ date: "2024-01-05", value: 1.2 }],
        drawdown: [{ date: "2024-01-05", value: -1.2 }], pnl_scatter: [], monthly_heatmap: [], pnl_vs_holding: [], mae_mfe: [], holding_buckets: [],
      },
      pngs: [],
    });

    renderRunDetail("/runs/an-charts");
    await screen.findByText("Charts run");
    fireEvent.click(screen.getByRole("tab", { name: "Analysis Charts" }));

    expect(apiMock.getRunAnalysisCharts).toHaveBeenCalledWith("an-charts");
    expect(await screen.findByText("Equity curve (cumulative return %)")).toBeInTheDocument();
    expect(screen.getAllByText("No data for this chart").length).toBeGreaterThan(0);

    type AxisNameOption = { xAxis?: { name: string; nameLocation: string }; yAxis?: { name: string; nameLocation?: string } };
    const chartOptions = vi.mocked(echarts.init).mock.results.map((result) => result.value?.setOption.mock.calls[0]?.[0] as AxisNameOption);
    const equityOption = chartOptions.find((option) => option.xAxis?.name === "Date");
    const drawdownOption = chartOptions.find((option) => option.yAxis?.name === "Drawdown (%)");
    expect(equityOption?.xAxis.nameLocation).toBe("middle");
    expect(drawdownOption?.yAxis?.nameLocation).toBe("start");
  });

  it("labels an empty MAE/MFE chart as not computed instead of a generic no-data card", async () => {
    apiMock.getRun.mockResolvedValue({
      status: "success", run_id: "an-fastrun", prompt: "Fastrun run",
    });
    apiMock.getRunCode.mockResolvedValue({});
    apiMock.getRunAnalysisCharts.mockResolvedValue({
      run_id: "an-fastrun",
      available: true,
      charts: {
        equity_return: [], drawdown: [], pnl_scatter: [], monthly_heatmap: [],
        pnl_vs_holding: [], mae_mfe: [], holding_buckets: [],
      },
      pngs: [],
    });

    renderRunDetail("/runs/an-fastrun");
    await screen.findByText("Fastrun run");
    fireEvent.click(screen.getByRole("tab", { name: "Analysis Charts" }));

    expect(await screen.findByText(/MAE\/MFE not computed/)).toBeInTheDocument();
  });

  it("renders the position-risk legend terms in bold", async () => {
    apiMock.getRun.mockResolvedValue({
      status: "success", run_id: "positions", prompt: "Positions run",
    });
    apiMock.getRunCode.mockResolvedValue({});
    apiMock.getRunAnalysisCharts.mockResolvedValue({
      run_id: "positions",
      available: true,
      charts: {
        daily_position: [{ date: "2024-01-05", gross_pct: 10, net_pct: 6, single_pct: 10 }],
        daily_risk: [{ date: "2024-01-05", risk_pct: 10 }],
      },
      pngs: [],
    });
    apiMock.getRunPositionGroups.mockResolvedValue({ run_id: "positions", groups: [] });

    renderRunDetail("/runs/positions");
    await screen.findByText("Positions run");
    fireEvent.click(screen.getByRole("tab", { name: "Positions & Risk" }));

    expect((await screen.findByText("Gross")).tagName).toBe("STRONG");
    expect(screen.getByText("Net").tagName).toBe("STRONG");
    expect(screen.getByText("Single-sided").tagName).toBe("STRONG");
  });

  it("renders the analysis report tab with markdown and status", async () => {
    apiMock.getRun.mockResolvedValue({
      status: "success", run_id: "an-report", prompt: "Report run",
    });
    apiMock.getRunCode.mockResolvedValue({});
    apiMock.getRunAnalysis.mockResolvedValue({
      run_id: "an-report",
      markdown: "## 一句话结论\n策略有效",
      status: { status: "ok", generated_by: "runner", generated_at: "now", llm_usage: { total_tokens: 33 } },
    });

    renderRunDetail("/runs/an-report");
    await screen.findByText("Report run");
    fireEvent.click(screen.getByRole("tab", { name: "Analysis" }));

    expect(apiMock.getRunAnalysis).toHaveBeenCalledWith("an-report");
    expect(await screen.findByText("策略有效")).toBeInTheDocument();
    expect(screen.getByText(/total_tokens/)).toBeInTheDocument();
    expect(document.querySelector(".prose")).toBeTruthy();
  });

  it("shows the empty state for runs without an analysis report", async () => {
    apiMock.getRun.mockResolvedValue({
      status: "success", run_id: "an-empty", prompt: "Empty run",
    });
    apiMock.getRunCode.mockResolvedValue({});
    apiMock.getRunAnalysis.mockResolvedValue({
      run_id: "an-empty", markdown: null, status: null,
    });

    renderRunDetail("/runs/an-empty");
    await screen.findByText("Empty run");
    fireEvent.click(screen.getByRole("tab", { name: "Analysis" }));

    expect(await screen.findByText("No analysis report")).toBeInTheDocument();
  });
});
