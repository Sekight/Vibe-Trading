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
