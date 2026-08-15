import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { CandlestickChart } from "../CandlestickChart";
import type { PriceBar } from "@/lib/api";
import type { ChartView } from "@/lib/chartWindow";

// 用假 echarts 实例捕获 setOption / datazoom 事件，验证「窗口保持」核心机制。
const { chartInstance, setOption, on } = vi.hoisted(() => {
  const setOption = vi.fn();
  const on = vi.fn();
  return {
    chartInstance: {
      group: "",
      setOption,
      on,
      off: vi.fn(),
      resize: vi.fn(),
      dispose: vi.fn(),
    },
    setOption,
    on,
  };
});

vi.mock("@/lib/echarts", () => ({
  echarts: { init: vi.fn(() => chartInstance) },
  CHART_GROUP: "test-charts",
  connectCharts: vi.fn(),
}));

// jsdom 无 ResizeObserver
class FakeResizeObserver {
  observe() {}
  disconnect() {}
  unobserve() {}
}
vi.stubGlobal("ResizeObserver", FakeResizeObserver);

const BARS: PriceBar[] = Array.from({ length: 1000 }, (_, i) => ({
  time: `2025-01-${String((i % 28) + 1).padStart(2, "0")} ${String(i % 24).padStart(2, "0")}:00`,
  open: 100 + i * 0.1,
  high: 101 + i * 0.1,
  low: 99 + i * 0.1,
  close: 100.5 + i * 0.1,
  volume: 1000,
}));

function makeWindowRef() {
  return { current: null as { start: number; end: number } | null };
}

function props(overrides: Partial<Parameters<typeof CandlestickChart>[0]> = {}) {
  return {
    data: BARS,
    baseInterval: "5m",
    sub: "vol" as ChartView["sub"],
    overlays: ["ma5", "ma20"] as ChartView["overlays"],
    period: null,
    windowRef: makeWindowRef(),
    onViewChange: vi.fn(),
    ...overrides,
  };
}

function lastOptionDataZoom() {
  const last = setOption.mock.calls[setOption.mock.calls.length - 1];
  return last?.[0]?.dataZoom?.[0] as { start: number; end: number } | undefined;
}

beforeEach(() => {
  setOption.mockClear();
  on.mockClear();
});

describe("CandlestickChart 可视窗口保持（文档验证场景 1/3/4 的核心机制）", () => {
  it("场景1/2：调指标/副图时沿用当前窗口（来自共享 ref），不重置回默认", () => {
    const windowRef = makeWindowRef();
    windowRef.current = { start: 30, end: 100 };
    const { rerender } = render(
      <CandlestickChart {...props({ windowRef, sub: "vol", overlays: ["ma5"] })} />,
    );
    const callsBefore = setOption.mock.calls.length;

    // 切换副图（sub 变化）——窗口 ref 不变
    rerender(<CandlestickChart {...props({ windowRef, sub: "macd", overlays: ["ma5"] })} />);
    expect(setOption.mock.calls.length).toBeGreaterThan(callsBefore);
    expect(lastOptionDataZoom()).toMatchObject({ start: 30, end: 100 });

    // 切换指标（overlays 变化）——窗口 ref 不变
    rerender(<CandlestickChart {...props({ windowRef, sub: "macd", overlays: ["ma5", "boll"] })} />);
    expect(lastOptionDataZoom()).toMatchObject({ start: 30, end: 100 });
  });

  it("场景3：新图（共享 ref 已有窗口）挂载时直接落在该窗口，而非默认最后 250 根", () => {
    const windowRef = makeWindowRef();
    windowRef.current = { start: 30, end: 100 };
    render(<CandlestickChart {...props({ windowRef })} />);
    expect(lastOptionDataZoom()).toMatchObject({ start: 30, end: 100 });
  });

  it("场景3/4：无共享窗口时用默认窗口（最后 250 根）", () => {
    render(<CandlestickChart {...props()} />);
    // 1000 根 → 默认 start = 100 - 250/1000*100 = 75
    expect(lastOptionDataZoom()).toMatchObject({ start: 75, end: 100 });
  });

  it("场景3/4：datazoom 事件把当前窗口写入共享 ref（供新图与回写沿用），不触发 onViewChange", () => {
    const windowRef = makeWindowRef();
    const onViewChange = vi.fn();
    render(<CandlestickChart {...props({ windowRef, onViewChange })} />);
    const handler = on.mock.calls.find((call) => call[0] === "datazoom")?.[1];
    expect(handler).toBeDefined();

    handler({ start: 30, end: 100 });
    expect(windowRef.current).toEqual({ start: 30, end: 100 });
    expect(onViewChange).not.toHaveBeenCalled();

    // batch 形式（多 dataZoom 组件）
    handler({ batch: [{ start: 40, end: 90 }] });
    expect(windowRef.current).toEqual({ start: 40, end: 90 });
  });

  it("atr 副图渲染 ATR 折线", () => {
    render(<CandlestickChart {...props({ sub: "atr" as ChartView["sub"] })} />);
    const last = setOption.mock.calls[setOption.mock.calls.length - 1];
    const series = last?.[0]?.series as any[] | undefined;
    expect(series?.some((s) => s.name === "ATR" && s.type === "line")).toBe(true);
  });
});
